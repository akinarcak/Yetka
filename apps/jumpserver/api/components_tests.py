from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from .components import SupportedComponentsApi


# Throttling runs before the view and reads through the Django cache, which is
# configured for Redis. There is no Redis in the test container, so the request
# died with a ConnectionError instead of reaching the endpoint. Local memory
# keeps the throttle path exercised without the dependency.
@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
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
