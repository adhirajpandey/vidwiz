from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk import aws_lambda as lambda_
from aws_cdk.assertions import Match, Template

from vidwiz_infra.settings import ProductionDeploymentConfig
from vidwiz_infra.stack import VidwizStack

FIXTURE_ENV = Path(__file__).parent / "fixtures" / "production.env"


def _test_python_function(
    scope: cdk.Stack,
    construct_id: str,
    *,
    entry: str,
    index: str,
    handler: str,
    **kwargs: object,
) -> lambda_.Function:
    del entry
    return lambda_.Function(
        scope,
        construct_id,
        code=lambda_.Code.from_inline(
            "def lambda_handler(event, context): return None"
        ),
        handler=f"{index.removesuffix('.py')}.{handler}",
        **kwargs,
    )


@pytest.fixture(scope="module")
def template() -> Template:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "vidwiz_infra.stack.lambda_python.PythonFunction",
        _test_python_function,
    )
    settings = ProductionDeploymentConfig.from_env_file(FIXTURE_ENV)
    try:
        app = cdk.App()
        stack = VidwizStack(
            app,
            "vidwiz-stack",
            settings=settings,
            env=cdk.Environment(
                account=settings.aws_account_id,
                region=settings.aws_region,
            ),
        )
        return Template.from_stack(stack)
    finally:
        monkeypatch.undo()


def test_exact_resource_names_and_security(template: Template) -> None:
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketName": "vidwiz-prod",
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            },
            "OwnershipControls": {
                "Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
            "NotificationConfiguration": {
                "LambdaConfigurations": [
                    {
                        "Event": "s3:ObjectCreated:*",
                        "Filter": {
                            "S3Key": {
                                "Rules": [
                                    {"Name": "prefix", "Value": "transcripts/"},
                                    {"Name": "suffix", "Value": ".json"},
                                ]
                            }
                        },
                    }
                ]
            },
        },
    )
    template.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Effect": "Deny",
                                "Action": "s3:*",
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            }
                        )
                    ]
                )
            }
        },
    )


def test_queues_and_event_sources(template: Template) -> None:
    for name, visibility in (
        ("vidwiz-prod-ai-note-jobs", 720),
        ("vidwiz-prod-ai-summary-jobs", 720),
    ):
        template.has_resource_properties(
            "AWS::SQS::Queue",
            {
                "QueueName": name,
                "SqsManagedSseEnabled": True,
                "MessageRetentionPeriod": 345600,
                "VisibilityTimeout": visibility,
            },
        )
    template.resource_count_is("AWS::Lambda::EventSourceMapping", 2)
    template.has_resource_properties(
        "AWS::Lambda::EventSourceMapping",
        {
            "BatchSize": 1,
            "ScalingConfig": {"MaximumConcurrency": 2},
        },
    )


def test_lambda_runtime_sizing_logs_and_configuration_values(
    template: Template,
) -> None:
    expected = {
        "vidwiz-prod-transcript-dispatcher": (128, 30),
        "vidwiz-prod-ai-note-worker": (512, 120),
        "vidwiz-prod-ai-summary-worker": (512, 120),
    }
    for name, (memory, timeout) in expected.items():
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": name,
                "Runtime": "python3.13",
                "Architectures": ["x86_64"],
                "Handler": "handler.lambda_handler",
                "MemorySize": memory,
                "Timeout": timeout,
            },
        )
        template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {
                "LogGroupName": f"/aws/lambda/{name}",
                "RetentionInDays": 7,
            },
        )
    rendered = template.to_json()
    text = str(rendered)
    assert "VidwizInternalApiAdminToken" not in rendered.get("Parameters", {})
    assert "OpenrouterApiKey" not in rendered.get("Parameters", {})
    assert "fixture-admin-token" in text
    assert "fixture-openrouter-key" in text


def test_lambda_environments_use_domain_specific_contracts(
    template: Template,
) -> None:
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "vidwiz-prod-transcript-dispatcher",
            "Environment": {
                "Variables": Match.object_like(
                    {
                        "VIDWIZ_INTERNAL_API_BASE_URL": ("https://example.invalid"),
                        "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": "fixture-admin-token",
                        "SQS_AI_NOTE_QUEUE_URL": Match.any_value(),
                        "SQS_AI_SUMMARY_QUEUE_URL": Match.any_value(),
                    }
                )
            },
        },
    )
    for function_name in (
        "vidwiz-prod-ai-note-worker",
        "vidwiz-prod-ai-summary-worker",
    ):
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": function_name,
                "Environment": {
                    "Variables": Match.object_like(
                        {
                            "S3_TRANSCRIPT_BUCKET_NAME": Match.any_value(),
                            "VIDWIZ_INTERNAL_API_BASE_URL": ("https://example.invalid"),
                            "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": "fixture-admin-token",
                            "OPENROUTER_API_KEY": "fixture-openrouter-key",
                        }
                    )
                },
            },
        )
    retired_names = {
        "SQS_QUEUE_URL",
        "SQS_SUMMARY_QUEUE_URL",
        "S3_BUCKET_NAME",
        "VIDWIZ_ENDPOINT",
        "VIDWIZ_TOKEN",
    }
    functions = template.find_resources("AWS::Lambda::Function")
    for function in functions.values():
        variables = function["Properties"]["Environment"]["Variables"]
        assert retired_names.isdisjoint(variables)


def test_s3_invoke_permission_is_source_restricted(template: Template) -> None:
    template.has_resource_properties(
        "AWS::Lambda::Permission",
        {
            "Action": "lambda:InvokeFunction",
            "Principal": "s3.amazonaws.com",
            "SourceAccount": "123456789012",
            "SourceArn": Match.any_value(),
        },
    )
    permissions = template.find_resources("AWS::Lambda::Permission")
    assert "vidwiz-prod" in str(permissions)


def test_excluded_cost_resources_are_absent(template: Template) -> None:
    for resource_type in (
        "AWS::SQS::QueuePolicy",
        "AWS::SNS::Topic",
        "AWS::CloudWatch::Alarm",
        "AWS::CloudWatch::Dashboard",
        "AWS::EC2::VPC",
        "AWS::Lambda::LayerVersion",
        "AWS::Lambda::Version",
        "AWS::CodeDeploy::DeploymentGroup",
        "AWS::KMS::Key",
    ):
        template.resource_count_is(resource_type, 0)


def test_runtime_roles_are_separate_and_lambda_only(template: Template) -> None:
    roles = template.find_resources("AWS::IAM::Role")

    assert len(roles) == 3
    for role in roles.values():
        assert role["Properties"]["AssumeRolePolicyDocument"]["Statement"] == [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
            }
        ]

    policies = template.find_resources("AWS::IAM::Policy")
    assert len(policies) == 3
    policy_text = str(policies)
    assert "AWSLambdaSQSQueueExecutionRole" not in policy_text
    assert "'Resource': '*'" not in policy_text
    assert "s3:ListBucket" not in policy_text


def test_outputs_are_complete_and_stable(template: Template) -> None:
    outputs = template.to_json()["Outputs"]

    assert set(outputs) == {
        "TranscriptBucketName",
        "AiNoteQueueUrl",
        "AiNoteQueueArn",
        "AiSummaryQueueUrl",
        "AiSummaryQueueArn",
        "DispatcherFunctionName",
        "AiNoteWorkerFunctionName",
        "AiSummaryWorkerFunctionName",
    }
