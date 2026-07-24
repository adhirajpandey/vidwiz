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
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_sqs as sqs,
)
from constructs import Construct

from vidwiz_infra.packaging import PACKAGES, asset_hash, package_path
from vidwiz_infra.settings import ProductionSettings

STACK_NAME = "vidwiz-stack"
BUCKET_NAME = "vidwiz-prod-transcripts"
AI_NOTE_QUEUE_NAME = "vidwiz-prod-ai-note-jobs"
AI_SUMMARY_QUEUE_NAME = "vidwiz-prod-ai-summary-jobs"
DISPATCHER_NAME = "vidwiz-prod-transcript-dispatcher"
AI_NOTE_WORKER_NAME = "vidwiz-prod-ai-note-worker"
AI_SUMMARY_WORKER_NAME = "vidwiz-prod-ai-summary-worker"


class VidwizStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        settings: ProductionSettings,
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

        vidwiz_token = cdk.CfnParameter(
            self,
            "VidwizToken",
            type="String",
            no_echo=True,
            description="Production internal API administrator token",
        )
        openrouter_api_key = cdk.CfnParameter(
            self,
            "OpenrouterApiKey",
            type="String",
            no_echo=True,
            description="Production OpenRouter API key",
        )

        bucket = s3.Bucket(
            self,
            "TranscriptBucket",
            bucket_name=BUCKET_NAME,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            enforce_ssl=True,
            versioned=False,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            auto_delete_objects=False,
        )
        bucket.apply_removal_policy(cdk.RemovalPolicy.RETAIN)

        note_queue = sqs.Queue(
            self,
            "AiNoteQueue",
            queue_name=AI_NOTE_QUEUE_NAME,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            retention_period=cdk.Duration.days(4),
            visibility_timeout=cdk.Duration.seconds(
                settings.ai_note_timeout_seconds * 6
            ),
        )
        summary_queue = sqs.Queue(
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
            "TranscriptDispatcher",
            DISPATCHER_NAME,
            memory=settings.dispatcher_memory_mb,
            timeout=settings.dispatcher_timeout_seconds,
            environment={
                "VIDWIZ_ENDPOINT": str(settings.vidwiz_endpoint),
                "VIDWIZ_TOKEN": vidwiz_token.value_as_string,
                "SQS_QUEUE_URL": note_queue.queue_url,
                "SQS_SUMMARY_QUEUE_URL": summary_queue.queue_url,
            },
        )
        note_worker = self._function(
            "AiNoteWorker",
            AI_NOTE_WORKER_NAME,
            memory=settings.ai_note_memory_mb,
            timeout=settings.ai_note_timeout_seconds,
            environment={
                **self._worker_environment(
                    vidwiz_token.value_as_string,
                    openrouter_api_key.value_as_string,
                    BUCKET_NAME,
                ),
                "TRANSCRIPT_BUFFER_SECONDS": str(settings.transcript_buffer_seconds),
                "CONTEXT_SEGMENTS": str(settings.context_segments),
                "MIN_NOTE_LENGTH": str(settings.min_note_length),
                "MAX_NOTE_LENGTH": str(settings.max_note_length),
            },
        )
        summary_worker = self._function(
            "AiSummaryWorker",
            AI_SUMMARY_WORKER_NAME,
            memory=settings.ai_summary_memory_mb,
            timeout=settings.ai_summary_timeout_seconds,
            environment={
                **self._worker_environment(
                    vidwiz_token.value_as_string,
                    openrouter_api_key.value_as_string,
                    BUCKET_NAME,
                ),
                "MIN_SUMMARY_LENGTH": str(settings.min_summary_length),
                "MAX_SUMMARY_LENGTH": str(settings.max_summary_length),
            },
        )

        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sqs:SendMessage"],
                resources=[note_queue.queue_arn, summary_queue.queue_arn],
            )
        )
        transcript_objects = f"arn:{cdk.Aws.PARTITION}:s3:::{BUCKET_NAME}/transcripts/*"
        for worker in (note_worker, summary_worker):
            worker.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["s3:GetObject"],
                    resources=[transcript_objects],
                )
            )

        note_worker.add_event_source(
            event_sources.SqsEventSource(
                note_queue,
                batch_size=1,
                max_concurrency=2,
                report_batch_item_failures=False,
            )
        )
        summary_worker.add_event_source(
            event_sources.SqsEventSource(
                summary_queue,
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
            source_arn=f"arn:{cdk.Aws.PARTITION}:s3:::{BUCKET_NAME}",
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
            bucket, note_queue, summary_queue, dispatcher, note_worker, summary_worker
        )

    def _worker_environment(
        self, vidwiz_token: str, api_key: str, bucket_name: str
    ) -> dict[str, str]:
        settings = self._settings
        return {
            "S3_BUCKET_NAME": bucket_name,
            "VIDWIZ_ENDPOINT": str(settings.vidwiz_endpoint),
            "VIDWIZ_TOKEN": vidwiz_token,
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
        construct_id: str,
        function_name: str,
        *,
        memory: int,
        timeout: int,
        environment: Mapping[str, str],
    ) -> lambda_.Function:
        package = next(item for item in PACKAGES if item.name in function_name)
        archive = package_path(package)
        if not archive.is_file():
            raise ValueError(
                f"Missing {archive}; run `uv run python scripts/build_lambdas.py`"
            )

        log_group = logs.LogGroup(
            self,
            f"{construct_id}LogGroup",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        role = iam.Role(
            self,
            f"{construct_id}Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"{log_group.log_group_arn}:*"],
            )
        )
        function = lambda_.Function(
            self,
            construct_id,
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.X86_64,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                str(archive),
                asset_hash=asset_hash(package),
                asset_hash_type=cdk.AssetHashType.CUSTOM,
            ),
            memory_size=memory,
            timeout=cdk.Duration.seconds(timeout),
            role=role,
            environment=dict(environment),
            tracing=lambda_.Tracing.DISABLED,
            log_group=log_group,
        )
        function.node.add_dependency(log_group)
        return function

    def _outputs(
        self,
        bucket: s3.Bucket,
        note_queue: sqs.Queue,
        summary_queue: sqs.Queue,
        dispatcher: lambda_.Function,
        note_worker: lambda_.Function,
        summary_worker: lambda_.Function,
    ) -> None:
        outputs = {
            "TranscriptBucketName": bucket.bucket_name,
            "AiNoteQueueUrl": note_queue.queue_url,
            "AiNoteQueueArn": note_queue.queue_arn,
            "AiSummaryQueueUrl": summary_queue.queue_url,
            "AiSummaryQueueArn": summary_queue.queue_arn,
            "DispatcherFunctionName": dispatcher.function_name,
            "AiNoteWorkerFunctionName": note_worker.function_name,
            "AiSummaryWorkerFunctionName": summary_worker.function_name,
        }
        for construct_id, value in outputs.items():
            cdk.CfnOutput(self, construct_id, value=value)
