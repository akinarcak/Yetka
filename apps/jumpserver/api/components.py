from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.component_manifest import load_supported_components


class SupportedComponentsApi(APIView):
    """Expose the signed source-level support boundary to product surfaces."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response({'components': load_supported_components()})
