
from unittest.mock import patch, MagicMock
from vidwiz.shared.models import Message, Video, db
from datetime import datetime, timezone
import os


def test_wiz_chat_guest_quota(client, app):
    """Test guest quota limits (5 messages/day)"""
    guest_id = "guest_123"
    headers = {"X-Guest-Session-ID": guest_id}
    video_id = "a1b2c3d4e5f"
    
    # Ensure video exists
    with app.app_context():
        if not Video.query.filter_by(video_id=video_id).first():
            video = Video(video_id=video_id, title="Test", transcript_available=True)
            db.session.add(video)
            db.session.commit()
    
    # Mock transcript retrieval and GEMINI_API_KEY
    with patch("vidwiz.services.wiz_service.get_transcript_from_s3") as mock_get_transcript, \
         patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
         patch("vidwiz.services.wiz_service.genai.Client") as mock_genai_client:
        
        mock_get_transcript.return_value = [{"offset": 0, "text": "Hello world"}]
        
        # Mock GenAI Client
        mock_chat = MagicMock()
        mock_genai_client.return_value.chats.create.return_value = mock_chat
        
        # Mock streaming response
        mock_chunk = MagicMock()
        mock_chunk.text = "AI Response"
        mock_chat.send_message_stream.return_value = [mock_chunk]

        # Send 5 messages (allowed)
        for i in range(5):
            response = client.post(
                "/api/wiz/chat",
                json={"video_id": video_id, "message": f"msg {i}"},
                headers=headers
            )
            assert response.status_code == 200

        # Send 6th message (blocked)
        response = client.post(
            "/api/wiz/chat",
            json={"video_id": video_id, "message": "msg 6"},
            headers=headers
        )
        assert response.status_code == 429
        assert "limit reached" in response.json["error"]["message"]



def test_wiz_chat_user_quota(client, app):
    """Test authenticated user quota limits (20 messages/day)"""
    video_id = "a1b2c3d4e5f"
    
    # Generate token locally to ensure validity
    import jwt
    from datetime import timedelta
    with app.app_context():
        token = jwt.encode(
            {
                "user_id": 1,
                "email": "test@example.com", 
                "name": "Test",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1)
            },
            app.config["SECRET_KEY"],
            algorithm="HS256"
        )
        auth_headers = {"Authorization": f"Bearer {token}"}

        if not Video.query.filter_by(video_id=video_id).first():
            video = Video(video_id=video_id, title="Test", transcript_available=True)
            db.session.add(video)
            db.session.commit()

    # Mock transcript retrieval and GEMINI_API_KEY
    with patch("vidwiz.services.wiz_service.get_transcript_from_s3") as mock_get_transcript, \
         patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
         patch("vidwiz.services.wiz_service.genai.Client") as mock_genai_client:
        
        mock_get_transcript.return_value = [{"offset": 0, "text": "Hello world"}]
        
        # Mock GenAI Client
        mock_chat = MagicMock()
        mock_genai_client.return_value.chats.create.return_value = mock_chat
        
        # Mock streaming response
        mock_chunk = MagicMock()
        mock_chunk.text = "AI Response"
        mock_chat.send_message_stream.return_value = [mock_chunk]

        # Send 20 messages (allowed)
        for i in range(20):
            response = client.post(
                "/api/wiz/chat",
                json={"video_id": video_id, "message": f"msg {i}"},
                headers=auth_headers
            )
            assert response.status_code == 200

        # Send 21st message (blocked)
        response = client.post(
            "/api/wiz/chat",
            json={"video_id": video_id, "message": "msg 21"},
            headers=auth_headers
        )
        assert response.status_code == 429
        assert "limit reached" in response.json["error"]["message"]


def test_wiz_chat_transcript_missing(client, app):
    """Test behavior when transcript is missing"""
    video_id = "m1n2b3v4c5x"
    
    # Create video with no transcript
    with app.app_context():
        video = Video(video_id=video_id, title="Test Missing", transcript_available=False)
        db.session.add(video)
        db.session.commit()

    headers = {"X-Guest-Session-ID": "guest_test"}
    
    response = client.post(
        "/api/wiz/chat",
        json={"video_id": video_id, "message": "hello"},
        headers=headers
    )
    
    # Should be 400 or 202 depending on active task status
    # Since no task is active in this test setup, it returns 400 with "init session first" message
    assert response.status_code == 400
    assert "Transcript unavailable" in response.json["error"]["message"]


def test_wiz_conversation_create_and_chat_roundtrip(client, app):
    """Create a conversation and reuse it for chat."""
    video_id = "z9y8x7w6v5u"
    guest_id = "guest_convo"
    headers = {"X-Guest-Session-ID": guest_id}

    with app.app_context():
        if not Video.query.filter_by(video_id=video_id).first():
            video = Video(video_id=video_id, title="Test", transcript_available=True)
            db.session.add(video)
            db.session.commit()

    convo_response = client.post(
        "/api/wiz/conversation",
        json={"video_id": video_id},
        headers=headers,
    )
    assert convo_response.status_code == 200
    conversation_id = convo_response.json["conversation_id"]

    with patch("vidwiz.services.wiz_service.get_transcript_from_s3") as mock_get_transcript, \
         patch("vidwiz.services.wiz_service.genai.Client") as mock_genai_client:
        mock_get_transcript.return_value = [{"offset": 0, "text": "Hello world"}]

        mock_chat = MagicMock()
        mock_genai_client.return_value.chats.create.return_value = mock_chat

        mock_chunk = MagicMock()
        mock_chunk.text = "AI Response"
        mock_chat.send_message_stream.return_value = [mock_chunk]

        response = client.post(
            "/api/wiz/chat",
            json={
                "video_id": video_id,
                "message": "msg 1",
                "conversation_id": conversation_id,
            },
            headers=headers,
        )
        assert response.status_code == 200

    with app.app_context():
        message = Message.query.filter_by(conversation_id=conversation_id).first()
        assert message is not None
        assert message.role == "user"


def test_wiz_chat_conversation_scoped_to_guest(client, app):
    """Reject conversation access from a different guest session."""
    video_id = "p0o9i8u7y6t"
    guest_a = {"X-Guest-Session-ID": "guest_a"}
    guest_b = {"X-Guest-Session-ID": "guest_b"}

    with app.app_context():
        if not Video.query.filter_by(video_id=video_id).first():
            video = Video(video_id=video_id, title="Test", transcript_available=True)
            db.session.add(video)
            db.session.commit()

    convo_response = client.post(
        "/api/wiz/conversation",
        json={"video_id": video_id},
        headers=guest_a,
    )
    assert convo_response.status_code == 200
    conversation_id = convo_response.json["conversation_id"]

    with patch("vidwiz.services.wiz_service.get_transcript_from_s3") as mock_get_transcript:
        mock_get_transcript.return_value = [{"offset": 0, "text": "Hello world"}]

        response = client.post(
            "/api/wiz/chat",
            json={
                "video_id": video_id,
                "message": "msg 1",
                "conversation_id": conversation_id,
            },
            headers=guest_b,
        )
        assert response.status_code == 404
