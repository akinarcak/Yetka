# Yetka güvenlik ve sürüm bakım politikası

Yetka üretim kurulumu web sürecinin root komutu çalıştırmasına izin vermez. Sistem altı saatte bir kontrol yapar ve sonucu yöneticilere popup olarak gösterir. Bare-metal kurulumda sistem yöneticisi “Güncellemeleri al” düğmesiyle yalnızca denetlenmiş en son Yetka sürümünü root-owned systemd kuyruğuna iletebilir. Container ve HA kurulumlarında doğrulanmış `yetka-update` komutu gösterilir; rollout host/CI tarafından yapılır.

## Neler kontrol edilir?

- Kurulu Yetka sürümü yalnız `akinarcak/Yetka` release kanalıyla karşılaştırılır. Popup’taki bu sürüm doğrudan kurulabilir.
- JumpServer upstream sürümü Yetka’nın taban aldığı upstream sürümle ayrıca karşılaştırılır. Bu yalnız ürün ekibine inceleme kaydı açar; upstream etiketi Yetka sunucusuna otomatik kurulmaz.
- Çalışan Python ortamındaki gerçek paket adları ve sürümleri OSV kayıtlarıyla karşılaştırılır.
- GitHub üzerinde haftalık bağımlılık güncelleme PR’ları, `pip-audit` ve Trivy kaynak taraması çalışır.
- Koko, Lina, Luna, Lion ve Chen sürümleri çekirdek release’iyle birlikte değerlendirilir. Bu binary bileşenler Python paket taramasının parçası değildir; sürüm matrisi release kabul testinde ayrıca doğrulanır.
- Kontrol kaynaklarından biri erişilemezse bu durum da bakım bulgusu sayılır; sessizce “güvenli” sonucu üretilmez.

Tarama sırasında OSV’ye yalnız kurulu PyPI paket adı ve sürümü gönderilir. Yetka kullanıcıları, varlıkları, adresleri, anahtarları ve oturum bilgileri gönderilmez.

## Müdahale süreleri

| Bulgu | İlk değerlendirme | Hedef düzeltme |
|---|---:|---:|
| Aktif istismar veya kritik yetki aşımı | 4 saat | 24 saat |
| Yüksek önem dereceli açık | 1 iş günü | 7 gün |
| Orta/düşük açık | 5 iş günü | Sonraki planlı bakım |
| Normal upstream sürümü | 5 iş günü | Aylık bakım penceresi |

Bir kayıt Yetka’nın kullandığı kod yolunu etkilemiyorsa gerekçesi ve kanıtı release notuna yazılır; popup yalnız yeni fingerprint oluştuğunda yeniden açılır ve aynı bulgu en fazla 24 saat ertelenebilir.

## Bare-metal güncelleme komutları

Kurucu `/usr/local/sbin/yetka-update` aracını ve kullanılan env dosyasının yolunu kurar. Araç aynı anda yalnız bir güncellemeye izin verir; GitHub release arşivi ile SHA-256 dosyasını indirir, checksum’u doğrular ve hedef kurucuyu önce dry-run olarak çalıştırır.

Bare-metal kurucu ayrıca `yetka-update-request.path` birimini ve root-owned `/run/yetka-update-requests` kuyruğunu kurar. Web süreci yalnızca sürüm etiketini yetkisiz komut içermeyen sabit bir istek dosyasına atomik olarak yazar. Root-owned runner etiketi tekrar doğrular ve aynı checksum, yedek, rollback ve sağlık kontrolü akışını çalıştırır. API yalnız sistem yöneticilerine açıktır ve CSRF korumalı POST isteği kabul eder.

```bash
yetka-update check
sudo yetka-update plan --version v2.1.0
sudo yetka-update apply --version v2.1.0
```

Etkileşimsiz onay yalnız kontrollü bakım otomasyonunda verilmelidir:

```bash
sudo yetka-update apply --version v2.1.0 --yes
```

`apply` başlamadan `/var/backups/yetka` altında env/yapılandırma, veritabanı ve varsayılan olarak `/var/lib/yetka` arşivi oluşturur. Dış/shared depolamanın bağımsız, geri dönüşü test edilmiş snapshot politikası varsa `YETKA_UPDATE_BACKUP_DATA=false` kullanılabilir. Script yeni kodu kurar, migrasyonları tek düğümde çalıştırır, yapılandırılmış servisleri yeniden başlatır ve HTTP/servis sağlığını denetler. Kurulum veya sağlık kontrolü başarısızsa önceki uygulama commit’ine dönmeyi dener; veritabanı migrasyonlarını otomatik geri almaz ve alınan DB yedeğinin yolunu bildirir.

## Güvenli release hazırlama akışı

1. Upstream release notlarını, güvenlik danışma kimliklerini ve değişen migrasyonları inceleyin.
2. Yetka değişikliklerinin üzerine tüm upstream dalını körlemesine birleştirmeyin. İlgili güvenlik düzeltmesini ayrı dalda merge/cherry-pick edin ve marka/lisans değişikliklerini koruyun.
3. Kilit dosyasını güncelleyin; `pip-audit`, backend testleri, görünür tab fonksiyon testleri ve connector oturum testlerini çalıştırın.
4. Veritabanı ve `/var/lib/yetka` yedeği alın; geri dönüşün gerçekten açılabildiğini doğrulayın.
5. HA kurulumunda önce trafiksiz standby düğümünü yükseltin. Sağlık, login, CRUD, SSH/RDP/WebDB ve kayıt oynatma testleri geçince trafiği taşıyın.
6. Veritabanı migrasyonunu yalnız bir düğüm çalıştırsın. Yeni şema eski sürümle uyumlu değilse rollback, uygulama downgrade’i değil DB geri dönüşü gerektirir.
7. İkinci uygulama düğümlerini ve aynı sürüm matrisindeki connector’ları yükseltin. Son olarak scheduler liderini güncelleyin.
8. Release etiketi oluşturun; GitHub workflow’u kurulum paketini ve SHA-256 dosyasını release’e ekler.

`YETKA_GIT_REF` yalnız kabul testinden geçen Yetka etiketine veya commit’e sabitlenmelidir. Popup’ın gösterdiği upstream JumpServer etiketi bu alana yazılmamalıdır.

## HA ve container güncellemesi

Active-active/active-standby kurulumunda yük dengeleyiciden çıkarılmış standby düğümde `plan` ve `apply` çalıştırın. Login, CRUD ve connector kabul testlerinden sonra trafiği bu düğüme alın; kalan uygulama düğümlerini tek tek güncelleyin. Scheduler yalnız bir düğümde etkin kalmalı ve scheduler lideri en son güncellenmelidir. Ortak şemada migrasyon yalnız ilk güncellenen düğümde oluşur; DB yedeği olmadan eski sürüme trafik döndürülmemelidir.

Container kurulumu kendi çalışan container’ı içinden güncellenmez. Host/CI, aynı Yetka release etiketine ait yeni image’ı digest ile sabitleyip veritabanı ve volume snapshot’ını aldıktan sonra standby container’da migrasyon ve sağlık kontrolü yapar; başarılı olunca load balancer/Compose/Kubernetes rollout’u ilerletir. `yetka-update` yalnız bu repodaki systemd bare-metal kurulumu içindir.

## İşletim ve hata ayıklama

```bash
systemctl status yetka-web yetka-worker yetka-scheduler
journalctl -u yetka-scheduler --since '24 hours ago' | grep -i maintenance
```

Kontrolü kapatmak yalnız kapalı ağ ve eşdeğer merkezi tarama bulunan ortamlarda kabul edilir:

```dotenv
YETKA_MAINTENANCE_CHECK_ENABLED=false
```

Kapalı ağda kurum içi CI, SBOM, zafiyet veritabanı aynası ve güvenlik duyurusu takibi ayrıca tanımlanmadan kontrol kapatılmamalıdır.
