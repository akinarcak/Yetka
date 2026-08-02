from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import Http404
from django.test import SimpleTestCase

from terminal.api.session.session import SessionReplayViewSet


class SessionReplayTenantScopeTests(SimpleTestCase):
    @patch('terminal.api.session.session.Session.objects')
    @patch('terminal.api.session.session.TenantOrganization.objects')
    def test_replay_lookup_is_scoped_to_verified_tenant_organizations(self, organizations, sessions):
        organization_ids = organizations.filter.return_value.values_list.return_value
        sessions.filter.return_value.first.return_value = SimpleNamespace(id='session-a')
        request = SimpleNamespace(customer_tenant=SimpleNamespace(id='tenant-a'))

        result = SessionReplayViewSet()._get_tenant_session(request, 'session-a')

        self.assertEqual(result.id, 'session-a')
        organizations.filter.assert_called_once_with(tenant=request.customer_tenant)
        sessions.filter.assert_called_once_with(
            id='session-a', org_id__in=organization_ids
        )

    @patch('terminal.api.session.session.Session.objects')
    @patch('terminal.api.session.session.TenantOrganization.objects')
    def test_replay_lookup_hides_cross_tenant_or_missing_session(self, organizations, sessions):
        organizations.filter.return_value.values_list.return_value = ['org-a']
        sessions.filter.return_value.first.return_value = None
        request = SimpleNamespace(customer_tenant=SimpleNamespace(id='tenant-a'))

        with self.assertRaises(Http404):
            SessionReplayViewSet()._get_tenant_session(request, 'session-attacker')

    def test_replay_lookup_requires_verified_tenant_context(self):
        with self.assertRaises(Http404):
            SessionReplayViewSet()._get_tenant_session(SimpleNamespace(), 'session-a')
