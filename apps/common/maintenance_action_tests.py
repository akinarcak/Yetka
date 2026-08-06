"""The GUI maintenance controls and the privilege boundary behind them.

The web process never runs a maintenance command. It writes a validated
release tag into a root-owned queue file, and a systemd unit decides which
command that file triggers -- so the boundary carries data, and the choice of
apply versus plan lives in the unit rather than in anything the web process
can write. These tests pin that property and the reporting built on top of it.
"""
import json
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from common.security_updates import (
    REQUEST_NAMES,
    RESULT_NAME,
    pending_action,
    queue_action,
    read_last_result,
)
from jumpserver.api.maintenance import MaintenanceStatusApi

LATEST = 'yetka-1.0.6-final-ws23'


class _Superuser:
    # OnlySuperUser derives from the project's IsValidUser, which checks
    # is_valid on top of the usual authentication attributes.
    is_authenticated = True
    is_valid = True
    is_superuser = True
    is_active = True
    is_staff = True
    id = 1
    pk = 1

    def has_perm(self, *args, **kwargs):
        return True


class QueueActionTestCase(SimpleTestCase):
    def test_each_action_has_its_own_queue_file(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            queue_action('plan', LATEST)
            queue_action('apply', LATEST)
            for action, name in REQUEST_NAMES.items():
                with self.subTest(action=action):
                    with open(os.path.join(queue, name), encoding='ascii') as fp:
                        self.assertEqual(fp.read(), f'{LATEST}\n')

    def test_second_request_for_the_same_action_is_refused(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            queue_action('plan', LATEST)
            with self.assertRaises(FileExistsError):
                queue_action('plan', LATEST)

    def test_queue_file_never_carries_anything_but_a_release_tag(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            for tag in ('yetka-1.0.1; rm -rf /', '--version=x', '$(id)', ''):
                with self.subTest(tag=tag):
                    with self.assertRaises(ValueError):
                        queue_action('plan', tag)
            self.assertEqual(os.listdir(queue), [])

    def test_unknown_action_is_refused(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            with self.assertRaises(ValueError):
                queue_action('rm', LATEST)
            self.assertEqual(os.listdir(queue), [])

    def test_pending_action_reports_what_is_queued(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self.assertIsNone(pending_action())
            queue_action('plan', LATEST)
            self.assertEqual(pending_action(), 'plan')


class ReadLastResultTestCase(SimpleTestCase):
    def _write(self, queue, payload):
        with open(os.path.join(queue, RESULT_NAME), 'w', encoding='utf-8') as fp:
            json.dump(payload, fp)

    def test_result_is_returned(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self._write(queue, {
                'action': 'plan',
                'version': LATEST,
                'started_at': '2026-08-06T18:00:00Z',
                'finished_at': '2026-08-06T18:02:00Z',
                'exit_code': 0,
                'truncated': False,
                'output': 'Plan complete; no host changes were made',
            })
            result = read_last_result()
            self.assertEqual(result['action'], 'plan')
            self.assertTrue(result['succeeded'])
            self.assertIn('no host changes', result['output'])

    def test_failed_run_is_reported_as_not_succeeded(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self._write(queue, {'action': 'apply', 'version': LATEST, 'exit_code': 3,
                                'output': 'boom'})
            self.assertFalse(read_last_result()['succeeded'])

    def test_missing_or_corrupt_result_is_dropped(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self.assertIsNone(read_last_result())
            with open(os.path.join(queue, RESULT_NAME), 'w', encoding='utf-8') as fp:
                fp.write('not json')
            self.assertIsNone(read_last_result())
            self._write(queue, {'action': 'plan', 'version': 'x; rm -rf /'})
            self.assertIsNone(read_last_result())
            self._write(queue, {'action': 'rm', 'version': LATEST})
            self.assertIsNone(read_last_result())
            self._write(queue, ['not', 'a', 'mapping'])
            self.assertIsNone(read_last_result())

    def test_non_string_output_does_not_reach_the_gui(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self._write(queue, {'action': 'plan', 'version': LATEST, 'exit_code': 0,
                                'output': {'a': 1}})
            self.assertEqual(read_last_result()['output'], '')


class MaintenanceStatusApiTestCase(SimpleTestCase):
    status = {'update': {'available': True, 'latest_version': LATEST}}

    def _post(self, **payload):
        request = APIRequestFactory().post('/api/v1/maintenance/status/', payload)
        force_authenticate(request, user=_Superuser())
        return MaintenanceStatusApi.as_view()(request)

    def _get(self):
        request = APIRequestFactory().get('/api/v1/maintenance/status/')
        force_authenticate(request, user=_Superuser())
        return MaintenanceStatusApi.as_view()(request)

    def test_plan_and_apply_go_to_their_own_queue_files(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ), patch('jumpserver.api.maintenance.get_maintenance_status', return_value=self.status):
            self.assertEqual(self._post(version=LATEST, action='plan').status_code, 202)
            self.assertEqual(self._post(version=LATEST, action='apply').status_code, 202)
            self.assertEqual(sorted(os.listdir(queue)), sorted(REQUEST_NAMES.values()))

    def test_apply_is_the_default_action(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ), patch('jumpserver.api.maintenance.get_maintenance_status', return_value=self.status):
            self.assertEqual(self._post(version=LATEST).status_code, 202)
            self.assertEqual(os.listdir(queue), [REQUEST_NAMES['apply']])

    def test_unknown_action_and_unaudited_version_are_refused(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ), patch('jumpserver.api.maintenance.get_maintenance_status', return_value=self.status):
            self.assertEqual(self._post(version=LATEST, action='rm').status_code, 400)
            self.assertEqual(self._post(version='yetka-9.9.9', action='plan').status_code, 400)
            self.assertEqual(os.listdir(queue), [])

    def test_second_request_conflicts_instead_of_overwriting(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ), patch('jumpserver.api.maintenance.get_maintenance_status', return_value=self.status):
            self.assertEqual(self._post(version=LATEST, action='plan').status_code, 202)
            self.assertEqual(self._post(version=LATEST, action='plan').status_code, 409)

    def test_unavailable_queue_reports_service_unavailable(self):
        with patch('common.security_updates.UPDATE_REQUEST_DIR', ''), patch(
            'jumpserver.api.maintenance.get_maintenance_status', return_value=self.status
        ):
            self.assertEqual(self._post(version=LATEST, action='plan').status_code, 503)

    def test_status_carries_everything_the_card_needs(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ), patch('jumpserver.api.maintenance.get_maintenance_status', return_value=self.status):
            body = self._get().data
            self.assertTrue(body['update']['can_plan'])
            self.assertIsNone(body['pending_action'])
            self.assertIsNone(body['last_result'])

            queue_action('plan', LATEST)
            self.assertEqual(self._get().data['pending_action'], 'plan')

    def test_anonymous_access_is_refused(self):
        request = APIRequestFactory().get('/api/v1/maintenance/status/')
        self.assertIn(MaintenanceStatusApi.as_view()(request).status_code, (401, 403))
