# cloud_sync — Bulut Varlık Senkronu

AWS (EC2) ve Azure (VM) envanterini Yetka'ya **Host asset** olarak senkronlar.
JumpServer'ın kapalı `xpack.plugins.cloud` modülünün açık kaynak muadilidir.

## Kavramlar
- **CloudSyncAccount**: bir bulut hesabı (provider + şifreli credential + bölgeler + hedef node).
- **CloudSyncedAsset**: `instance_id → asset` eşlemesi; tekrar senkronda duplicate olmaz (idempotent).
- **CloudSyncExecution**: her senkron çalışmasının özeti (total/created/updated/failed).

## Sağlayıcılar
- **aws**: `boto3` ile tüm (veya seçili) bölgelerde EC2 instance'ları listeler.
  credentials: `{"access_key_id": "...", "secret_access_key": "..."}`
- **azure**: `azure-identity` + `azure-mgmt-compute/network` ile VM'leri listeler.
  credentials: `{"tenant_id","client_id","client_secret","subscription_id"}`

Linux → ssh/22, Windows → rdp/3389 protokolüyle asset oluşturulur; OS otomatik tespit edilir.
`use_public_ip` true ise public IP, değilse private IP adres olarak kullanılır.

## REST API
- `GET/POST /api/v1/cloud-sync/accounts/` — hesap CRUD (credentials write-only)
- `POST /api/v1/cloud-sync/accounts/{id}/test/` — credential doğrula
- `POST /api/v1/cloud-sync/accounts/{id}/sync/` — senkronu tetikle
- `GET  /api/v1/cloud-sync/executions/` — çalışma geçmişi

## CLI
```
python manage.py cloud_sync <hesap-adi-veya-id>
```

## Zamanlanmış senkron
`cloud_sync.tasks.sync_all_cloud_accounts` Celery task'ı aktif hesapları senkronlar
(periyodik zamanlama için django-celery-beat'e eklenebilir).
