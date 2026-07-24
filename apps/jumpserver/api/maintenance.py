from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.views import APIView

from common.permissions import OnlySuperUser
from common.security_updates import (
    get_maintenance_status,
    queue_update,
    update_queue_available,
)


class MaintenanceStatusApi(APIView):
    permission_classes = (OnlySuperUser,)

    def get(self, request):
        status = dict(get_maintenance_status())
        update = status.get('update')
        if update:
            update = dict(update)
            status['update'] = update
            update['can_apply'] = bool(
                update.get('available') and update_queue_available()
            )
        return Response(status)

    def post(self, request):
        maintenance = get_maintenance_status()
        update = maintenance.get('update') or {}
        version = request.data.get('version', '')
        if not update.get('available') or version != update.get('latest_version'):
            return Response(
                {'detail': 'Yalnızca denetlenmiş en son Yetka sürümü uygulanabilir.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        try:
            queue_update(version)
        except FileExistsError:
            return Response(
                {'detail': 'Başka bir güncelleme isteği zaten bekliyor.'},
                status=http_status.HTTP_409_CONFLICT,
            )
        except (RuntimeError, ValueError) as exc:
            return Response(
                {'detail': str(exc)},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                'detail': 'Güncelleme sıraya alındı. Sunucu yedek alıp doğrulanmış paketi uygulayacak.',
                'version': version,
            },
            status=http_status.HTTP_202_ACCEPTED,
        )
