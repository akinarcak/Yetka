from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.views import APIView

from common.permissions import OnlySuperUser
from common.security_updates import (
    get_maintenance_status,
    plan_pending,
    queue_plan,
    queue_update,
    read_plan_result,
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
            # Planning is read-only, so it is offered whenever a newer release
            # exists -- including when applying is unavailable and the operator
            # only wants to see what the update would do.
            update['can_plan'] = update['can_apply']
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


class MaintenancePlanApi(APIView):
    """Run the read-only host planner from the GUI.

    POST queues a plan for the audited latest release; GET returns the last
    plan the host produced. The planner touches nothing -- it verifies the
    signed checksum and runs the target installer in dry-run mode -- which is
    why this is exposed separately from applying rather than behind the same
    confirmation.
    """

    permission_classes = (OnlySuperUser,)

    def get(self, request):
        return Response({
            'available': update_queue_available(),
            'pending': plan_pending(),
            'result': read_plan_result(),
        })

    def post(self, request):
        maintenance = get_maintenance_status()
        update = maintenance.get('update') or {}
        version = request.data.get('version', '')
        latest = update.get('latest_version')
        if not latest or version != latest:
            return Response(
                {'detail': 'Yalnızca denetlenmiş en son Yetka sürümü planlanabilir.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        try:
            queue_plan(version)
        except FileExistsError:
            return Response(
                {'detail': 'Başka bir plan isteği zaten bekliyor.'},
                status=http_status.HTTP_409_CONFLICT,
            )
        except (RuntimeError, ValueError) as exc:
            return Response(
                {'detail': str(exc)},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                'detail': 'Plan sıraya alındı. Sunucu hiçbir değişiklik yapmadan '
                          'hedef sürümü doğrulayıp sonucu buraya yazacak.',
                'version': version,
            },
            status=http_status.HTTP_202_ACCEPTED,
        )
