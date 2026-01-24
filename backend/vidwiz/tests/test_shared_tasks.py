from unittest.mock import patch
from vidwiz.shared.tasks import create_transcript_task, create_metadata_task
from vidwiz.shared.config import FETCH_TRANSCRIPT_TASK_TYPE, FETCH_METADATA_TASK_TYPE

class TestSharedTasks:
    """Test shared task creation functions"""

    def test_create_transcript_task_success(self):
        with patch("vidwiz.shared.models.Task") as MockTask, \
             patch("vidwiz.shared.models.db.session") as mock_session:

            create_transcript_task("vid123")

            MockTask.assert_called_with(
                task_type=FETCH_TRANSCRIPT_TASK_TYPE,
                task_details={"video_id": "vid123"}
            )
            mock_session.add.assert_called()
            mock_session.commit.assert_called()

    def test_create_transcript_task_failure(self):
        with patch("vidwiz.shared.models.Task"), \
             patch("vidwiz.shared.models.db.session") as mock_session:

            mock_session.commit.side_effect = Exception("DB Error")

            # Should not raise exception
            create_transcript_task("vid123")

            mock_session.rollback.assert_called()

    def test_create_metadata_task_success(self):
        with patch("vidwiz.shared.models.Task") as MockTask, \
             patch("vidwiz.shared.models.db.session") as mock_session:

            create_metadata_task("vid123")

            MockTask.assert_called_with(
                task_type=FETCH_METADATA_TASK_TYPE,
                task_details={"video_id": "vid123"}
            )
            mock_session.add.assert_called()
            mock_session.commit.assert_called()

    def test_create_metadata_task_custom_type(self):
        with patch("vidwiz.shared.models.Task") as MockTask, \
             patch("vidwiz.shared.models.db.session"):

            create_metadata_task("vid123", task_type="custom_type")

            MockTask.assert_called_with(
                task_type="custom_type",
                task_details={"video_id": "vid123"}
            )
