from src.conversations.config import ConversationsSettings


def test_transcript_bucket_uses_domain_specific_name(monkeypatch):
    monkeypatch.setenv("S3_TRANSCRIPT_BUCKET_NAME", "transcript-bucket")

    configured = ConversationsSettings(_env_file=None)

    assert configured.s3_transcript_bucket_name == "transcript-bucket"
