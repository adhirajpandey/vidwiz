from vidwiz_infra.manual_policies import (
    application_user_policy,
    github_deploy_role_policy,
    github_deploy_role_trust,
)

ACCOUNT = "123456789012"
REGION = "ap-south-1"


def test_github_trust_is_limited_to_main_branch() -> None:
    trust = github_deploy_role_trust(ACCOUNT)
    assert len(trust["Statement"]) == 1
    statement = trust["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Principal"]["Federated"] == (
        f"arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"
    )
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert statement["Condition"] == {
        "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": (
                "repo:adhirajpandey/vidwiz:ref:refs/heads/main"
            ),
        }
    }


def test_github_can_assume_only_required_bootstrap_roles() -> None:
    policy = github_deploy_role_policy(ACCOUNT, REGION)
    assert len(policy["Statement"]) == 1
    resources = policy["Statement"][0]["Resource"]

    assert policy["Statement"][0]["Effect"] == "Allow"
    assert resources == [
        f"arn:aws:iam::{ACCOUNT}:role/cdk-hnb659fds-deploy-role-{ACCOUNT}-{REGION}",
        f"arn:aws:iam::{ACCOUNT}:role/cdk-hnb659fds-file-publishing-role-{ACCOUNT}-{REGION}",
        f"arn:aws:iam::{ACCOUNT}:role/cdk-hnb659fds-lookup-role-{ACCOUNT}-{REGION}",
    ]
    assert policy["Statement"][0]["Action"] == "sts:AssumeRole"


def test_application_user_policy_is_exactly_scoped() -> None:
    policy = application_user_policy(ACCOUNT, REGION)

    assert policy["Statement"] == [
        {
            "Sid": "TranscriptObjects",
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject"],
            "Resource": "arn:aws:s3:::vidwiz-prod/transcripts/*",
        },
        {
            "Sid": "SubmitAiNoteJobs",
            "Effect": "Allow",
            "Action": "sqs:SendMessage",
            "Resource": (f"arn:aws:sqs:{REGION}:{ACCOUNT}:vidwiz-prod-ai-note-jobs"),
        },
    ]
