from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .security_updates import _version, refresh_maintenance_status
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

    @override_settings(VERSION='v4.10.1')
    @patch('common.security_updates.cache.set')
    @patch('common.security_updates._installed_python_packages')
    def test_refresh_reports_release_and_osv_findings(self, packages, cache_set):
        packages.return_value = [
            {'name': 'example-package', 'version': '1.0.0'},
        ]
        release_response = Mock()
        release_response.json.return_value = {
            'tag_name': 'v4.10.2',
            'published_at': '2026-07-20T00:00:00Z',
            'html_url': 'https://example.test/releases/v4.10.2',
        }
        osv_response = Mock()
        osv_response.json.return_value = {
            'results': [{'vulns': [{'id': 'GHSA-test-0000'}]}],
        }
        session = Mock()
        session.get.return_value = release_response
        session.post.return_value = osv_response

        with patch('common.security_updates.cache.get', return_value=None):
            status = refresh_maintenance_status(session=session)

        self.assertTrue(status['attention_required'])
        self.assertTrue(status['update']['available'])
        self.assertEqual(status['vulnerabilities']['total'], 1)
        self.assertEqual(status['vulnerabilities']['items'][0]['package'], 'example-package')
        self.assertEqual(len(status['fingerprint']), 20)
        cache_set.assert_called_once()

    @override_settings(VERSION='dev')
    @patch('common.security_updates.cache.set')
    @patch('common.security_updates._installed_python_packages', return_value=[])
    def test_unknown_build_version_requires_review(self, packages, cache_set):
        release_response = Mock()
        release_response.json.return_value = {
            'tag_name': 'v4.10.2', 'published_at': None, 'html_url': None,
        }
        session = Mock()
        session.get.return_value = release_response

        with patch('common.security_updates.cache.get', return_value=None):
            status = refresh_maintenance_status(session=session)

        self.assertTrue(status['update']['available'])
        self.assertFalse(status['update']['comparison_available'])
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
