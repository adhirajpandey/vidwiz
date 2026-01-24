
import pytest
from unittest.mock import patch, MagicMock
from vidwiz.shared.models import Conversation, Message, Video, db
from datetime import datetime, timezone
import os
from google.genai import types


def test_wiz_chat_guest_quota(client, app):
    """Test guest quota limits (5 messages/day)"""
    guest_id = "guest_123"
    headers = {"X-Guest-Session-ID": guest_id}
    video_id = "test_video_123"
    
    # Ensure video exists
    with app.app_context():
        if not Video.query.filter_by(video_id=video_id).first():
            video = Video(video_id=video_id, title="Test", transcript_available=True)
            db.session.add(video)
            db.session.commit()
    
    # Mock transcript retrieval and GEMINI_API_KEY
    with patch("vidwiz.routes.wiz_routes.get_transcript_from_s3") as mock_get_transcript, \
         patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
         patch("vidwiz.routes.wiz_routes.genai.Client") as mock_genai_client:
        
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
    video_id = "test_video_123"
    
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
    with patch("vidwiz.routes.wiz_routes.get_transcript_from_s3") as mock_get_transcript, \
         patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
         patch("vidwiz.routes.wiz_routes.genai.Client") as mock_genai_client:
        
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
    video_id = "test_video_missing_transcript"
    
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
