from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('cloud_sync', '0001_initial'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cloudsyncaccount',
            name='tenant',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='cloud_sync_accounts', to='tenants.customertenant',
            ),
        ),
        migrations.AddField(
            model_name='cloudsyncedasset',
            name='tenant',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='cloud_synced_assets', to='tenants.customertenant',
            ),
        ),
        migrations.AddField(
            model_name='cloudsyncexecution',
            name='tenant',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='cloud_sync_executions', to='tenants.customertenant',
            ),
        ),
        migrations.AddField(
            model_name='cloudsyncexecution',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='cloudsyncaccount',
            unique_together={('tenant', 'name')},
        ),
        migrations.AddConstraint(
            model_name='cloudsyncexecution',
            constraint=models.UniqueConstraint(
                fields=('account', 'idempotency_key'),
                name='uniq_cloud_sync_account_idempotency',
            ),
        ),
    ]
