from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import OnlySuperUser
from common.security_updates import get_maintenance_status


class MaintenanceStatusApi(APIView):
    permission_classes = (OnlySuperUser,)

    def get(self, request):
        return Response(get_maintenance_status())
