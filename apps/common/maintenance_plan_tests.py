"""The GUI plan control and the privilege boundary it hands work across.

Applying an update from the GUI already works: the web process writes a
release tag into a root-owned queue and a root runner re-validates it. These
tests cover the read-only planner added alongside it, and in particular the
property that makes the boundary safe -- the queue file carries a validated
version string and can never become a command channel.
"""
import json
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from common.security_updates import (
    PLAN_REQUEST_NAME,
    PLAN_RESULT_NAME,
    plan_pending,
    queue_plan,
    read_plan_result,
)
from jumpserver.api.maintenance import MaintenancePlanApi

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


class QueuePlanTestCase(SimpleTestCase):
    def test_plan_request_is_written_once(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            queue_plan(LATEST)
            with open(os.path.join(queue, PLAN_REQUEST_NAME), encoding='ascii') as fp:
                self.assertEqual(fp.read(), f'{LATEST}\n')
            self.assertTrue(plan_pending())
            with self.assertRaises(FileExistsError):
                queue_plan(LATEST)

    def test_plan_request_rejects_shell_input(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            for tag in ('yetka-1.0.1; rm -rf /', '--version=x', '$(id)', ''):
                with self.subTest(tag=tag):
                    with self.assertRaises(ValueError):
                        queue_plan(tag)
            self.assertFalse(os.path.exists(os.path.join(queue, PLAN_REQUEST_NAME)))

    def test_plan_and_apply_use_separate_queue_files(self):
        from common.security_updates import UPDATE_REQUEST_NAME, queue_update

        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            queue_plan(LATEST)
            # A pending plan must not block, or be mistaken for, an apply.
            queue_update(LATEST)
            self.assertTrue(os.path.exists(os.path.join(queue, PLAN_REQUEST_NAME)))
            self.assertTrue(os.path.exists(os.path.join(queue, UPDATE_REQUEST_NAME)))


class ReadPlanResultTestCase(SimpleTestCase):
    def _write(self, queue, payload):
        with open(os.path.join(queue, PLAN_RESULT_NAME), 'w', encoding='utf-8') as fp:
            json.dump(payload, fp)

    def test_result_is_returned(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self._write(queue, {
                'version': LATEST,
                'started_at': '2026-08-06T18:00:00Z',
                'finished_at': '2026-08-06T18:02:00Z',
                'exit_code': 0,
                'truncated': False,
                'output': 'Plan complete; no host changes were made',
            })
            result = read_plan_result()
            self.assertEqual(result['version'], LATEST)
            self.assertTrue(result['succeeded'])
            self.assertIn('no host changes', result['output'])

    def test_failed_plan_is_reported_as_not_succeeded(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self._write(queue, {'version': LATEST, 'exit_code': 3, 'output': 'boom'})
            self.assertFalse(read_plan_result()['succeeded'])

    def test_missing_or_corrupt_result_is_dropped(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self.assertIsNone(read_plan_result())
            with open(os.path.join(queue, PLAN_RESULT_NAME), 'w', encoding='utf-8') as fp:
                fp.write('not json')
            self.assertIsNone(read_plan_result())
            self._write(queue, {'version': 'x; rm -rf /', 'output': 'x'})
            self.assertIsNone(read_plan_result())
            self._write(queue, ['not', 'a', 'mapping'])
            self.assertIsNone(read_plan_result())

    def test_non_string_output_does_not_reach_the_gui(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            self._write(queue, {'version': LATEST, 'exit_code': 0, 'output': {'a': 1}})
            self.assertEqual(read_plan_result()['output'], '')


class MaintenancePlanApiTestCase(SimpleTestCase):
    def _post(self, version):
        request = APIRequestFactory().post('/api/v1/maintenance/plan/', {'version': version})
        force_authenticate(request, user=_Superuser())
        return MaintenancePlanApi.as_view()(request)

    def _get(self):
        request = APIRequestFactory().get('/api/v1/maintenance/plan/')
        force_authenticate(request, user=_Superuser())
        return MaintenancePlanApi.as_view()(request)

    def test_only_the_audited_latest_release_can_be_planned(self):
        status = {'update': {'available': True, 'latest_version': LATEST}}
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ), patch('jumpserver.api.maintenance.get_maintenance_status', return_value=status):
            self.assertEqual(self._post('yetka-9.9.9').status_code, 400)
            self.assertFalse(os.path.exists(os.path.join(queue, PLAN_REQUEST_NAME)))
            self.assertEqual(self._post(LATEST).status_code, 202)
            self.assertTrue(os.path.exists(os.path.join(queue, PLAN_REQUEST_NAME)))

    def test_second_request_conflicts_instead_of_overwriting(self):
        status = {'update': {'available': True, 'latest_version': LATEST}}
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ), patch('jumpserver.api.maintenance.get_maintenance_status', return_value=status):
            self.assertEqual(self._post(LATEST).status_code, 202)
            self.assertEqual(self._post(LATEST).status_code, 409)

    def test_unavailable_queue_reports_service_unavailable(self):
        status = {'update': {'available': True, 'latest_version': LATEST}}
        with patch('common.security_updates.UPDATE_REQUEST_DIR', ''), patch(
            'jumpserver.api.maintenance.get_maintenance_status', return_value=status
        ):
            self.assertEqual(self._post(LATEST).status_code, 503)

    def test_get_reports_pending_and_result(self):
        with TemporaryDirectory() as queue, patch(
            'common.security_updates.UPDATE_REQUEST_DIR', queue
        ):
            response = self._get()
            self.assertTrue(response.data['available'])
            self.assertFalse(response.data['pending'])
            self.assertIsNone(response.data['result'])

            queue_plan(LATEST)
            self.assertTrue(self._get().data['pending'])

    def test_anonymous_access_is_refused(self):
        request = APIRequestFactory().get('/api/v1/maintenance/plan/')
        self.assertIn(MaintenancePlanApi.as_view()(request).status_code, (401, 403))
