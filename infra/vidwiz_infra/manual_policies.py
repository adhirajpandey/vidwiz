from typing import Any

PolicyDocument = dict[str, Any]


def github_deploy_role_trust(account_id: str) -> PolicyDocument:
    """Return the trust policy for the manually created GitHub OIDC role."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": (
                        f"arn:aws:iam::{account_id}:oidc-provider/"
                        "token.actions.githubusercontent.com"
                    )
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": (
                            "sts.amazonaws.com"
                        ),
                        "token.actions.githubusercontent.com:sub": (
                            "repo:adhirajpandey/vidwiz:ref:refs/heads/main"
                        ),
                    }
                },
            }
        ],
    }


def github_deploy_role_policy(account_id: str, region: str) -> PolicyDocument:
    """Return the least-privilege bootstrap-role policy for GitHub."""
    role_prefix = f"arn:aws:iam::{account_id}:role/cdk-hnb659fds"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeProductionCdkRoles",
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": [
                    f"{role_prefix}-deploy-role-{account_id}-{region}",
                    f"{role_prefix}-file-publishing-role-{account_id}-{region}",
                    f"{role_prefix}-lookup-role-{account_id}-{region}",
                ],
            }
        ],
    }


def application_user_policy(account_id: str, region: str) -> PolicyDocument:
    """Return the policy for the manually managed Docker application user."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "TranscriptObjects",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": ("arn:aws:s3:::vidwiz-prod-transcripts/transcripts/*"),
            },
            {
                "Sid": "SubmitAiNoteJobs",
                "Effect": "Allow",
                "Action": "sqs:SendMessage",
                "Resource": (
                    f"arn:aws:sqs:{region}:{account_id}:vidwiz-prod-ai-note-jobs"
                ),
            },
        ],
    }
