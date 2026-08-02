import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('cloud_sync', '0002_customer_tenant_ownership')]

    operations = [
        migrations.CreateModel(
            name='CloudSyncQuarantine',
            fields=[
                ('created_by', models.CharField(blank=True, max_length=128, null=True, verbose_name='Created by')),
                ('updated_by', models.CharField(blank=True, max_length=128, null=True, verbose_name='Updated by')),
                ('date_created', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Date created')),
                ('date_updated', models.DateTimeField(auto_now=True, verbose_name='Date updated')),
                ('comment', models.TextField(blank=True, default='', verbose_name='Comment')),
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('org_id', models.CharField(blank=True, db_index=True, default='', max_length=36, verbose_name='Organization')),
                ('provider_object_id', models.CharField(max_length=256)),
                ('reason_code', models.CharField(max_length=64)),
                ('reason_detail', models.CharField(blank=True, default='', max_length=512)),
                ('observed', models.JSONField(blank=True, default=dict)),
                ('resolved', models.BooleanField(db_index=True, default=False)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quarantined_objects', to='cloud_sync.cloudsyncaccount')),
                ('execution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quarantined_objects', to='cloud_sync.cloudsyncexecution')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='cloud_sync_quarantine', to='tenants.customertenant')),
            ],
            options={'ordering': ('-date_updated',)},
        ),
        migrations.AddConstraint(
            model_name='cloudsyncquarantine',
            constraint=models.UniqueConstraint(fields=('account', 'provider_object_id'), name='uniq_cloud_quarantine_account_object'),
        ),
    ]
