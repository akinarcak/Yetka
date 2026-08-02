from unittest import TestCase
from unittest.mock import Mock, patch

from common.storage.replay import SessionPartReplayStorageHandler

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

    @patch('terminal.tasks.server_replay_storage')
    @patch('terminal.tasks.default_storage')
    def test_external_failure_retains_local_replay(self, storage, external):
        storage.exists.return_value = True
        storage.path.return_value = '/tmp/session.replay.gz'
        external.upload.return_value = (False, 'unavailable')

        with self.assertRaises(ReplayUploadError):
            upload_session_replay_file_to_external_storage(
                'session', 'replay/session.replay.gz', 'session.replay.gz'
            )

        storage.delete.assert_not_called()

    @patch('terminal.tasks.server_replay_storage')
    @patch('terminal.tasks.default_storage')
    def test_successful_external_upload_removes_local_copy(self, storage, external):
        storage.exists.return_value = True
        storage.path.return_value = '/tmp/session.replay.gz'
        external.upload.return_value = (True, None)

        upload_session_replay_file_to_external_storage(
            'session', 'replay/session.replay.gz', 'session.replay.gz'
        )

        storage.delete.assert_called_once_with('replay/session.replay.gz')

    def test_missing_replay_metadata_fails_closed(self):
        session = Mock(id='session')
        handler = SessionPartReplayStorageHandler(session)
        with patch.object(handler, 'get_part_file_path_url', return_value=(None, 'missing')):
            with self.assertRaises(FileNotFoundError):
                handler.prepare_offline_tar_file()
