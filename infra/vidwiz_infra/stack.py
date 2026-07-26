from collections.abc import Mapping

import aws_cdk as cdk
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_lambda_event_sources as event_sources,
)
from aws_cdk import (
    aws_lambda_python_alpha as lambda_python,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_sqs as sqs,
)
from constructs import Construct

from vidwiz_infra.bundling import lambda_bundling, shared_worker_bundling
from vidwiz_infra.lambda_specs import LAMBDA_SPECS_BY_KEY, LambdaSpec
from vidwiz_infra.settings import ProductionDeploymentConfig

STACK_NAME = "vidwiz-stack"
TRANSCRIPT_BUCKET_NAME = "vidwiz-prod"
AI_NOTE_QUEUE_NAME = "vidwiz-prod-ai-note-jobs"
AI_SUMMARY_QUEUE_NAME = "vidwiz-prod-ai-summary-jobs"


class VidwizStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        settings: ProductionDeploymentConfig,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._settings = settings

        for key, value in {
            "Project": "VidWiz",
            "Environment": "production",
            "ManagedBy": "CDK",
        }.items():
            cdk.Tags.of(self).add(key, value)

        bucket = s3.Bucket(
            self,
            "TranscriptBucket",
            bucket_name=TRANSCRIPT_BUCKET_NAME,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            enforce_ssl=True,
            versioned=False,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            auto_delete_objects=False,
        )
        bucket.apply_removal_policy(cdk.RemovalPolicy.RETAIN)

        ai_note_queue = sqs.Queue(
            self,
            "AiNoteQueue",
            queue_name=AI_NOTE_QUEUE_NAME,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            retention_period=cdk.Duration.days(4),
            visibility_timeout=cdk.Duration.seconds(
                settings.ai_note_timeout_seconds * 6
            ),
        )
        ai_summary_queue = sqs.Queue(
            self,
            "AiSummaryQueue",
            queue_name=AI_SUMMARY_QUEUE_NAME,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            retention_period=cdk.Duration.days(4),
            visibility_timeout=cdk.Duration.seconds(
                settings.ai_summary_timeout_seconds * 6
            ),
        )

        dispatcher = self._function(
            LAMBDA_SPECS_BY_KEY["transcript_dispatcher"],
            memory=settings.dispatcher_memory_mb,
            timeout=settings.dispatcher_timeout_seconds,
            environment={
                "VIDWIZ_INTERNAL_API_BASE_URL": str(
                    settings.vidwiz_internal_api_base_url
                ),
                "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": (
                    settings.vidwiz_internal_api_admin_token.get_secret_value()
                ),
                "SQS_AI_NOTE_QUEUE_URL": ai_note_queue.queue_url,
                "SQS_AI_SUMMARY_QUEUE_URL": ai_summary_queue.queue_url,
            },
        )
        note_worker = self._function(
            LAMBDA_SPECS_BY_KEY["ai_note_worker"],
            memory=settings.ai_note_memory_mb,
            timeout=settings.ai_note_timeout_seconds,
            environment={
                **self._worker_environment(
                    settings.vidwiz_internal_api_admin_token.get_secret_value(),
                    settings.openrouter_api_key.get_secret_value(),
                    TRANSCRIPT_BUCKET_NAME,
                ),
                "TRANSCRIPT_BUFFER_SECONDS": str(settings.transcript_buffer_seconds),
                "CONTEXT_SEGMENTS": str(settings.context_segments),
                "MIN_NOTE_LENGTH": str(settings.min_note_length),
                "MAX_NOTE_LENGTH": str(settings.max_note_length),
            },
        )
        summary_worker = self._function(
            LAMBDA_SPECS_BY_KEY["ai_summary_worker"],
            memory=settings.ai_summary_memory_mb,
            timeout=settings.ai_summary_timeout_seconds,
            environment={
                **self._worker_environment(
                    settings.vidwiz_internal_api_admin_token.get_secret_value(),
                    settings.openrouter_api_key.get_secret_value(),
                    TRANSCRIPT_BUCKET_NAME,
                ),
                "MIN_SUMMARY_LENGTH": str(settings.min_summary_length),
                "MAX_SUMMARY_LENGTH": str(settings.max_summary_length),
            },
        )

        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sqs:SendMessage"],
                resources=[
                    ai_note_queue.queue_arn,
                    ai_summary_queue.queue_arn,
                ],
            )
        )
        transcript_objects = (
            f"arn:{cdk.Aws.PARTITION}:s3:::{TRANSCRIPT_BUCKET_NAME}/transcripts/*"
        )
        for worker in (note_worker, summary_worker):
            worker.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["s3:GetObject"],
                    resources=[transcript_objects],
                )
            )

        note_worker.add_event_source(
            event_sources.SqsEventSource(
                ai_note_queue,
                batch_size=1,
                max_concurrency=2,
                report_batch_item_failures=False,
            )
        )
        summary_worker.add_event_source(
            event_sources.SqsEventSource(
                ai_summary_queue,
                batch_size=1,
                max_concurrency=2,
                report_batch_item_failures=False,
            )
        )
        invoke_permission = lambda_.CfnPermission(
            self,
            "TranscriptBucketInvokeDispatcher",
            action="lambda:InvokeFunction",
            function_name=dispatcher.function_name,
            principal="s3.amazonaws.com",
            source_account=settings.aws_account_id,
            source_arn=(f"arn:{cdk.Aws.PARTITION}:s3:::{TRANSCRIPT_BUCKET_NAME}"),
        )
        cfn_bucket = bucket.node.default_child
        assert isinstance(cfn_bucket, s3.CfnBucket)
        cfn_bucket.notification_configuration = (
            s3.CfnBucket.NotificationConfigurationProperty(
                lambda_configurations=[
                    s3.CfnBucket.LambdaConfigurationProperty(
                        event="s3:ObjectCreated:*",
                        function=dispatcher.function_arn,
                        filter=s3.CfnBucket.NotificationFilterProperty(
                            s3_key=s3.CfnBucket.S3KeyFilterProperty(
                                rules=[
                                    s3.CfnBucket.FilterRuleProperty(
                                        name="prefix", value="transcripts/"
                                    ),
                                    s3.CfnBucket.FilterRuleProperty(
                                        name="suffix", value=".json"
                                    ),
                                ]
                            )
                        ),
                    )
                ]
            )
        )
        cfn_bucket.add_resource_dependency(invoke_permission)

        self._outputs(
            bucket,
            ai_note_queue,
            ai_summary_queue,
            dispatcher,
            note_worker,
            summary_worker,
        )

    def _worker_environment(
        self,
        internal_api_admin_token: str,
        api_key: str,
        transcript_bucket_name: str,
    ) -> dict[str, str]:
        settings = self._settings
        # Intentional migration tradeoff: these credentials remain plaintext
        # Lambda environment variables. Move them to Secrets Manager or SSM in
        # a dedicated security change rather than altering this deployment path.
        return {
            "S3_TRANSCRIPT_BUCKET_NAME": transcript_bucket_name,
            "VIDWIZ_INTERNAL_API_BASE_URL": str(settings.vidwiz_internal_api_base_url),
            "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": internal_api_admin_token,
            "OPENROUTER_API_KEY": api_key,
            "OPENROUTER_BASE_URL": str(settings.openrouter_base_url),
            "OPENROUTER_MODEL": settings.openrouter_model,
            "MAX_RETRIES": str(settings.max_retries),
            "REQUEST_TIMEOUT": str(settings.request_timeout),
            "TRANSCRIPT_FETCH_MAX_RETRIES": str(settings.transcript_fetch_max_retries),
            "TRANSCRIPT_FETCH_RETRY_DELAY": str(settings.transcript_fetch_retry_delay),
        }

    def _function(
        self,
        spec: LambdaSpec,
        *,
        memory: int,
        timeout: int,
        environment: Mapping[str, str],
    ) -> lambda_python.PythonFunction:
        log_group = logs.LogGroup(
            self,
            f"{spec.construct_id}LogGroup",
            log_group_name=f"/aws/lambda/{spec.function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        role = iam.Role(
            self,
            f"{spec.construct_id}Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"{log_group.log_group_arn}:*"],
            )
        )
        function = lambda_python.PythonFunction(
            self,
            spec.construct_id,
            entry=str(spec.source),
            function_name=spec.function_name,
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.X86_64,
            index="handler.py",
            handler="lambda_handler",
            memory_size=memory,
            timeout=cdk.Duration.seconds(timeout),
            role=role,
            environment=dict(environment),
            tracing=lambda_.Tracing.DISABLED,
            log_group=log_group,
            bundling=(
                shared_worker_bundling()
                if spec.key in {"ai_note_worker", "ai_summary_worker"}
                else lambda_bundling()
            ),
        )
        function.node.add_dependency(log_group)
        return function

    def _outputs(
        self,
        bucket: s3.Bucket,
        ai_note_queue: sqs.Queue,
        ai_summary_queue: sqs.Queue,
        dispatcher: lambda_.Function,
        note_worker: lambda_.Function,
        summary_worker: lambda_.Function,
    ) -> None:
        outputs = {
            "TranscriptBucketName": bucket.bucket_name,
            "AiNoteQueueUrl": ai_note_queue.queue_url,
            "AiNoteQueueArn": ai_note_queue.queue_arn,
            "AiSummaryQueueUrl": ai_summary_queue.queue_url,
            "AiSummaryQueueArn": ai_summary_queue.queue_arn,
            "DispatcherFunctionName": dispatcher.function_name,
            "AiNoteWorkerFunctionName": note_worker.function_name,
            "AiSummaryWorkerFunctionName": summary_worker.function_name,
        }
        for construct_id, value in outputs.items():
            cdk.CfnOutput(self, construct_id, value=value)
