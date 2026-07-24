import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .security_updates import (
    _fetch_release,
    _current_yetka_version,
    _version,
    queue_update,
    refresh_maintenance_status,
)
from jumpserver.api.maintenance import MaintenanceStatusApi

# Create your tests here.

from .utils import random_string, signer


def test_signer_len():
    results = {}
    for i in range(1, 4096):
        s = random_string(i)
        encs = signer.sign(s)
        results[i] = (len(encs)/len(s))
    results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    print(results)


class MaintenanceStatusTestCase(SimpleTestCase):
    def test_version_normalization(self):
        self.assertEqual(_version('v4.10.17-lts'), (4, 10, 17))
        self.assertIsNone(_version('dev'))

    def test_release_tag_rejects_shell_input(self):
        response = Mock()
        response.json.return_value = {'tag_name': 'v2.1.0;touch /tmp/unsafe'}
        session = Mock()
        session.get.return_value = response

        with self.assertRaisesRegex(ValueError, 'valid version tag'):
            _fetch_release(session, 'https://example.test/releases/latest')

    def test_release_tag_accepts_yetka_prefix(self):
        response = Mock()
        response.json.return_value = {'tag_name': 'yetka-1.0.1'}
        session = Mock()
        session.get.return_value = response

        self.assertEqual(
            _fetch_release(session, 'https://example.test/releases/latest')['tag_name'],
            'yetka-1.0.1',
        )

    def test_update_queue_creates_exclusive_request(self):
        with TemporaryDirectory() as request_dir, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', request_dir
        ):
            queue_update('yetka-1.0.1')
            with open(os.path.join(request_dir, 'request'), encoding='ascii') as stream:
                self.assertEqual(stream.read(), 'yetka-1.0.1\n')
            with self.assertRaises(FileExistsError):
                queue_update('yetka-1.0.1')

    def test_current_version_prefers_installed_yetka_release_file(self):
        with TemporaryDirectory() as directory:
            version_file = os.path.join(directory, 'release-version')
            with open(version_file, 'w', encoding='ascii') as stream:
                stream.write('yetka-1.0.1\n')
            with patch(
                'common.security_updates.YETKA_RELEASE_VERSION_FILE', version_file
            ):
                self.assertEqual(_current_yetka_version(), 'yetka-1.0.1')

    def test_slack_renderer_supports_current_mistune(self):
        from common.sdk.im.slack import Slack

        blocks = Slack().convert_to_markdown(
            '**Kritik** [bakım rehberi](https://example.test/guide)'
        )['blocks']
        self.assertEqual(len(blocks), 1)
        self.assertIn('*Kritik*', blocks[0]['text']['text'])
        self.assertIn(
            '<https://example.test/guide|bakım rehberi>',
            blocks[0]['text']['text'],
        )

    @override_settings(VERSION='2.0.1')
    @patch('common.security_updates.cache.set')
    @patch('common.security_updates._installed_python_packages')
    def test_refresh_reports_release_and_osv_findings(self, packages, cache_set):
        packages.return_value = [
            {'name': 'example-package', 'version': '1.0.0'},
        ]
        yetka_response = Mock()
        yetka_response.json.return_value = {
            'tag_name': 'v2.1.0',
            'published_at': '2026-07-20T00:00:00Z',
            'html_url': 'https://example.test/releases/v2.1.0',
        }
        upstream_response = Mock()
        upstream_response.json.return_value = {
            'tag_name': 'v4.10.17',
            'published_at': '2026-07-19T00:00:00Z',
            'html_url': 'https://example.test/releases/v4.10.17',
        }
        osv_response = Mock()
        osv_response.json.return_value = {
            'results': [{'vulns': [{'id': 'GHSA-test-0000'}]}],
        }
        session = Mock()
        session.get.side_effect = [yetka_response, upstream_response]
        session.post.return_value = osv_response

        with patch('common.security_updates.cache.get', return_value=None):
            status = refresh_maintenance_status(session=session)

        self.assertTrue(status['attention_required'])
        self.assertTrue(status['update']['available'])
        self.assertEqual(
            status['update']['command'],
            'sudo yetka-update apply --version v2.1.0',
        )
        self.assertFalse(status['upstream']['review_required'])
        self.assertEqual(status['vulnerabilities']['total'], 1)
        self.assertEqual(status['vulnerabilities']['items'][0]['package'], 'example-package')
        self.assertEqual(len(status['fingerprint']), 20)
        cache_set.assert_called_once()

    @override_settings(VERSION='dev')
    @patch('common.security_updates.cache.set')
    @patch('common.security_updates._installed_python_packages', return_value=[])
    def test_unknown_build_version_requires_review(self, packages, cache_set):
        yetka_response = Mock()
        yetka_response.json.return_value = {
            'tag_name': 'v2.1.0', 'published_at': None, 'html_url': None,
        }
        upstream_response = Mock()
        upstream_response.json.return_value = {
            'tag_name': 'v4.10.17', 'published_at': None, 'html_url': None,
        }
        session = Mock()
        session.get.side_effect = [yetka_response, upstream_response]

        with patch('common.security_updates.cache.get', return_value=None):
            status = refresh_maintenance_status(session=session)

        self.assertTrue(status['update']['available'])
        self.assertFalse(status['update']['comparison_available'])
        self.assertTrue(status['attention_required'])

    @override_settings(VERSION='2.1.0')
    @patch('common.security_updates.cache.set')
    @patch('common.security_updates._installed_python_packages', return_value=[])
    @patch('common.security_updates.UPSTREAM_BASE_VERSION', 'v4.10.16')
    def test_upstream_release_is_review_only(self, packages, cache_set):
        yetka_response = Mock()
        yetka_response.json.return_value = {
            'tag_name': 'v2.1.0', 'published_at': None, 'html_url': None,
        }
        upstream_response = Mock()
        upstream_response.json.return_value = {
            'tag_name': 'v4.10.17', 'published_at': None, 'html_url': None,
        }
        session = Mock()
        session.get.side_effect = [yetka_response, upstream_response]

        with patch('common.security_updates.cache.get', return_value=None):
            status = refresh_maintenance_status(session=session)

        self.assertFalse(status['update']['available'])
        self.assertTrue(status['upstream']['review_required'])
        self.assertTrue(status['attention_required'])

    @patch('jumpserver.api.maintenance.get_maintenance_status')
    def test_status_api_is_restricted_to_system_admins(self, get_status):
        get_status.return_value = {'attention_required': False}
        factory = APIRequestFactory()
        view = MaintenanceStatusApi.as_view()

        denied_request = factory.get('/api/v1/maintenance/status/')
        force_authenticate(denied_request, user=SimpleNamespace(
            pk='regular-user', is_authenticated=True, is_valid=True,
            is_superuser=False,
        ))
        self.assertEqual(view(denied_request).status_code, 403)

        allowed_request = factory.get('/api/v1/maintenance/status/')
        force_authenticate(allowed_request, user=SimpleNamespace(
            pk='system-admin', is_authenticated=True, is_valid=True,
            is_superuser=True,
        ))
        self.assertEqual(view(allowed_request).status_code, 200)

    @patch('jumpserver.api.maintenance.queue_update')
    @patch('jumpserver.api.maintenance.get_maintenance_status')
    def test_system_admin_can_queue_only_latest_reviewed_update(
        self, get_status, queue
    ):
        get_status.return_value = {
            'update': {'available': True, 'latest_version': 'yetka-1.0.1'}
        }
        factory = APIRequestFactory()
        request = factory.post(
            '/api/v1/maintenance/status/',
            {'version': 'yetka-1.0.1'},
            format='json',
        )
        force_authenticate(request, user=SimpleNamespace(
            pk='system-admin', is_authenticated=True, is_valid=True,
            is_superuser=True,
        ))

        response = MaintenanceStatusApi.as_view()(request)

        self.assertEqual(response.status_code, 202)
        queue.assert_called_once_with('yetka-1.0.1')
