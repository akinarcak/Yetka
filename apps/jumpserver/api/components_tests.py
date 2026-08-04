from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .components import SupportedComponentsApi


class SupportedComponentsApiTests(SimpleTestCase):
    @patch('jumpserver.api.components.load_supported_components')
    def test_manifest_is_exposed_without_mutation(self, loader):
        manifest = {'koko': {'status': 'supported'}, 'lion': {'status': 'unavailable'}}
        loader.return_value = manifest
        request = APIRequestFactory().get('/api/v1/components/')
        # DRF throttling builds its cache key from request.user.pk before the
        # view runs, so the stand-in user needs one. Without it the request
        # never reached the view and this test raised AttributeError instead of
        # asserting anything -- unnoticed, because the gate step it runs in
        # discarded the exit code.
        request.user = SimpleNamespace(
            pk=1, is_authenticated=True, is_active=True, is_valid=True
        )
        response = SupportedComponentsApi.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'components': manifest})
