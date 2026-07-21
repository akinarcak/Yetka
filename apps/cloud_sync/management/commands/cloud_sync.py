from django.core.management.base import BaseCommand, CommandError

from orgs.utils import set_current_org
from orgs.models import Organization
from cloud_sync.models import CloudSyncAccount
from cloud_sync.sync import run_sync


class Command(BaseCommand):
    help = 'Bir bulut hesabinin envanterini Yetka asset olarak senkronlar'

    def add_arguments(self, parser):
        parser.add_argument('account', help='CloudSyncAccount adi veya id')

    def handle(self, *args, **options):
        ident = options['account']
        for org in Organization.objects.all():
            set_current_org(org)
            acc = CloudSyncAccount.objects.filter(name=ident).first() \
                or CloudSyncAccount.objects.filter(id=ident).first()
            if acc:
                break
        else:
            raise CommandError(f'CloudSyncAccount bulunamadi: {ident}')

        ex = run_sync(acc)
        self.stdout.write(
            f'status={ex.status} total={ex.total} created={ex.created} '
            f'updated={ex.updated} failed={ex.failed}'
        )
        if ex.error:
            self.stdout.write(f'error: {ex.error}')
