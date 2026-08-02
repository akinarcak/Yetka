from unittest import TestCase
from unittest.mock import patch

from .tasks import ReplayUploadError, upload_session_replay_file_to_external_storage, upload_session_replay_to_external_storage


class RecordingFailClosedTests(TestCase):
    @patch('terminal.tasks.Session.objects')
    def test_missing_session_is_failure_not_success(self, objects):
        objects.filter.return_value.first.return_value = None
        with self.assertRaises(ReplayUploadError):
            upload_session_replay_to_external_storage('missing')

    @patch('terminal.tasks.default_storage')
    def test_missing_part_is_not_deleted_or_reported_successfully(self, storage):
        storage.exists.return_value = False
        with self.assertRaises(ReplayUploadError):
            upload_session_replay_file_to_external_storage('session', 'missing', 'remote')
        storage.delete.assert_not_called()
