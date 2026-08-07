from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.views import APIView

from common.permissions import OnlySuperUser
from common.security_updates import (
    get_maintenance_status,
    pending_action,
    queue_action,
    read_last_result,
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
            # Planning is read-only, so it is offered wherever applying is.
            update['can_plan'] = update['can_apply']
        # The GUI renders the whole maintenance card from this one response:
        # what is available, whether the host is busy, and how the last run went.
        status['pending_action'] = pending_action()
        status['last_result'] = read_last_result()
        return Response(status)

    def post(self, request):
        maintenance = get_maintenance_status()
        update = maintenance.get('update') or {}
        version = request.data.get('version', '')
        # Applying stays the default so a client that predates planning keeps
        # working unchanged.
        action = request.data.get('action', 'apply')
        if action not in ('apply', 'plan'):
            return Response(
                {'detail': 'Geçersiz bakım eylemi.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if not update.get('available') or version != update.get('latest_version'):
            return Response(
                {'detail': 'Yalnızca denetlenmiş en son Yetka sürümü uygulanabilir.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        try:
            queue_action(action, version)
        except FileExistsError as exc:
            return Response(
                {'detail': str(exc)},
                status=http_status.HTTP_409_CONFLICT,
            )
        except (RuntimeError, ValueError) as exc:
            return Response(
                {'detail': str(exc)},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        detail = (
            'Plan sıraya alındı. Sunucu hiçbir değişiklik yapmadan hedef '
            'sürümü doğrulayacak ve sonucu buraya yazacak.'
            if action == 'plan' else
            'Güncelleme sıraya alındı. Sunucu yedek alıp doğrulanmış paketi uygulayacak.'
        )
        return Response(
            {'detail': detail, 'action': action, 'version': version},
            status=http_status.HTTP_202_ACCEPTED,
        )

