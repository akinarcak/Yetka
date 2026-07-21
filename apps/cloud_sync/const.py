from django.db import models
from django.utils.translation import gettext_lazy as _


class CloudProvider(models.TextChoices):
    aws = 'aws', _('Amazon Web Services')
    azure = 'azure', _('Microsoft Azure')


class SyncStatus(models.TextChoices):
    pending = 'pending', _('Pending')
    running = 'running', _('Running')
    success = 'success', _('Success')
    partial = 'partial', _('Partial')
    failed = 'failed', _('Failed')


class HostnameStrategy(models.TextChoices):
    instance_name = 'instance_name', _('Instance name')
    instance_id = 'instance_id', _('Instance ID')
