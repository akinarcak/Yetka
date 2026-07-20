# Yetka güvenlik ve sürüm bakım politikası

Yetka üretim kurulumu otomatik olarak yeni kodu devreye almaz. Otomatik yükseltme; veritabanı migrasyonu, connector uyumu ve HA düğümlerinde aynı anda kesinti riski doğurur. Sistem bunun yerine altı saatte bir kontrol yapar, sonucu yöneticilere popup olarak gösterir ve aşağıdaki kontrollü süreci başlatır.

## Neler kontrol edilir?

- Kurulu çekirdek sürümü ile en son upstream çekirdek release’i karşılaştırılır.
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

## Güvenli güncelleme akışı

1. Upstream release notlarını, güvenlik danışma kimliklerini ve değişen migrasyonları inceleyin.
2. Yetka değişikliklerinin üzerine tüm upstream dalını körlemesine birleştirmeyin. İlgili güvenlik düzeltmesini ayrı dalda merge/cherry-pick edin ve marka/lisans değişikliklerini koruyun.
3. Kilit dosyasını güncelleyin; `pip-audit`, backend testleri, görünür tab fonksiyon testleri ve connector oturum testlerini çalıştırın.
4. Veritabanı ve `/var/lib/yetka` yedeği alın; geri dönüşün gerçekten açılabildiğini doğrulayın.
5. HA kurulumunda önce trafiksiz standby düğümünü yükseltin. Sağlık, login, CRUD, SSH/RDP/WebDB ve kayıt oynatma testleri geçince trafiği taşıyın.
6. Veritabanı migrasyonunu yalnız bir düğüm çalıştırsın. Yeni şema eski sürümle uyumlu değilse rollback, uygulama downgrade’i değil DB geri dönüşü gerektirir.
7. İkinci uygulama düğümlerini ve aynı sürüm matrisindeki connector’ları yükseltin. Son olarak scheduler liderini güncelleyin.
8. Release etiketi oluşturun; GitHub workflow’u kurulum paketini ve SHA-256 dosyasını release’e ekler.

Bare-metal düğümde kontrollü yükseltme:

```bash
sudo cp /etc/yetka-install.env /etc/yetka-install.env.backup
sudo editor /etc/yetka-install.env
sudo ./deploy/install-baremetal.sh --env /etc/yetka-install.env --dry-run
sudo ./deploy/install-baremetal.sh --env /etc/yetka-install.env --yes
sudo ./deploy/check-install.sh http://127.0.0.1
```

`YETKA_GIT_REF` değeri yalnız kabul testinden geçen etikete veya commit’e sabitlenmelidir.

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
