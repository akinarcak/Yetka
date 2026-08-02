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
        request.user = SimpleNamespace(
            is_authenticated=True, is_active=True, is_valid=True
        )
        response = SupportedComponentsApi.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'components': manifest})
