# Yetka kurulum ve yüksek erişilebilirlik rehberi

> Sürekli güvenlik taraması, popup davranışı ve kontrollü yükseltme süreci için [bakım politikasına](MAINTENANCE.md) bakın.

Bu dizin Docker kullanmadan çalışan bare-metal kurucuyu ve üretim HA örneklerini içerir. Kurucu Yetka çekirdeğini kaynak koddan kurar, Python 3.14 ortamını `uv` ile izole eder, systemd servislerini ve nginx ters vekilini oluşturur. Debian/Ubuntu, RHEL/Rocky/Alma/Fedora ve openSUSE/SLES paket aileleri desteklenir. Hedef sistem systemd, `amd64` veya `arm64` olmalıdır; “her Linux” ifadesi bu açık koşullar içinde desteklenir.

## Güvenlik ve ilk parola

Temiz veritabanında ilk kullanıcı `admin`, ilk parola `ChangeMe` değeridir. Bu değer [kullanıcı migrasyonunda](../apps/users/migrations/0001_initial.py) oluşturulur ve ana README ile uyumludur. Var olan bir veritabanı bağlanırsa migrasyon mevcut admin parolasını değiştirmez. İlk girişten hemen sonra parola değiştirilmelidir.

`SECRET_KEY`, `BOOTSTRAP_TOKEN`, veritabanı ve Redis parolaları repoya yazılmaz. İlk kurulum boş bırakılan iki küme sırrını `/etc/yetka/cluster-secrets.env` içinde `0600` izinle üretir. HA düğümlerinin tümüne bu dosya güvenli bir kanal üzerinden aynen kopyalanmalıdır. Sırlar farklı olursa oturumlar ve connector kaydı bozulur.

## 1. Tek sunucu bare-metal

```bash
git clone https://github.com/akinarcak/Yetka.git
cd Yetka
sudo install -m 600 deploy/yetka.env.example /etc/yetka-install.env
sudo editor /etc/yetka-install.env
```

Dosyada `YETKA_DATA_MODE=standalone`, doğru `YETKA_DOMAIN` ve web/worker/scheduler seçeneklerini `true` yapın. Önce planı görün, sonra kurun:

```bash
sudo ./deploy/install-baremetal.sh --env /etc/yetka-install.env --dry-run
sudo ./deploy/install-baremetal.sh --env /etc/yetka-install.env --yes
sudo ./deploy/check-install.sh http://127.0.0.1
```

Kurucu yerel PostgreSQL ve Redis için rastgele parola üretir. Uygulama yapılandırması `/opt/yetka/app/config.yml`, küme sırları `/etc/yetka/cluster-secrets.env`, kalıcı veri `/var/lib/yetka` altındadır.

Scheduler düğümü Yetka release, JumpServer upstream inceleme ve OSV bağımlılık kontrolünü altı saatte bir çalıştırır. Kurulabilir Yetka sürümü, upstream inceleme kaydı, güvenlik kaydı veya tarama hatası yalnız sistem yöneticilerine popup olarak gösterilir. Yetka ile upstream sürüm numaraları birbirine kıyaslanmaz.

## 2. Harici PostgreSQL, MySQL ve Redis

Yetka PostgreSQL veya MySQL’in yönetilen/harici bir örneğine kurulabilir. Uygulama kullanıcısı boş bir veritabanının sahibi olmalı ve şema oluşturabilmelidir.

```dotenv
YETKA_DATA_MODE=external
DB_ENGINE=postgresql                 # veya mysql
DB_HOST=db-writer.internal           # primary/VIP/proxy uç noktası
DB_PORT=5432                         # MySQL için 3306
DB_NAME=yetka
DB_USER=yetka
DB_PASSWORD=yerel-gizli-deger
DB_USE_SSL=true
REDIS_HOST=redis.internal
REDIS_PORT=6379
REDIS_PASSWORD=yerel-gizli-deger
```

TLS kullanan veritabanının CA sertifikasını `/var/lib/yetka/core/certs/db_ca.pem` olarak koyun. MySQL HA kullanılıyorsa `DB_HOST`, tek bir backend adına değil yazılabilir-primary sağlayan ProxySQL/HAProxy/VIP uç noktasına verilmelidir.

Redis Sentinel örneği:

```dotenv
REDIS_HOST=
REDIS_SENTINEL_HOSTS=10.20.1.11:26379:mymaster,10.20.1.12:26379:mymaster,10.20.1.13:26379:mymaster
REDIS_SENTINEL_PASSWORD=sentinel-gizli-deger
REDIS_PASSWORD=redis-primary-gizli-deger
```

## 3. PostgreSQL HA (Patroni)

Üretimde üç PostgreSQL/Patroni düğümü, bağımsız üç veya beş üyeli etcd quorum’u ve en az iki HAProxy/VIP düğümü önerilir. Aynı üç makinede etcd çalıştırmak mümkündür fakat PostgreSQL arızasıyla quorum arızasını aynı hata alanına taşır. etcd düğümlerine özel CA imzalı, IP/DNS SAN içeren mTLS sertifikalarını hazırladıktan sonra her quorum üyesini kurun:

```bash
sudo install -m 600 deploy/ha/postgresql/etcd.env.example /etc/yetka-etcd.env
sudo editor /etc/yetka-etcd.env
sudo ./deploy/ha/postgresql/install-etcd-node.sh --env /etc/yetka-etcd.env --dry-run
sudo ./deploy/ha/postgresql/install-etcd-node.sh --env /etc/yetka-etcd.env
```

Üç ilk üyenin `ETCD_INITIAL_CLUSTER` ve token değeri aynı, `NODE_NAME`, `NODE_IP` ve düğüm sertifikası farklı olmalıdır. Script indirdiği etcd arşivini sabit SHA-256 ile doğrular; sürüm değiştirilirse yeni resmi checksum `ETCD_SHA256_OVERRIDE` ile açıkça verilmelidir.

Her DB düğümünde:

```bash
sudo install -m 600 deploy/ha/postgresql/patroni.env.example /etc/yetka-patroni.env
sudo editor /etc/yetka-patroni.env
sudo ./deploy/ha/postgresql/install-patroni-node.sh --env /etc/yetka-patroni.env --dry-run
sudo ./deploy/ha/postgresql/install-patroni-node.sh --env /etc/yetka-patroni.env
```

`NODE_NAME` ve `NODE_IP` düğüme özel, diğer parola ve küme alanları bütün düğümlerde aynı olmalıdır. HAProxy düğümlerinde [haproxy-postgresql.cfg.example](ha/postgresql/haproxy-postgresql.cfg.example) adreslerini düzenleyin. Yetka `DB_HOST`, iki HAProxy’nin Keepalived VIP’si veya DNS adı olmalıdır. Patroni REST `/primary` kontrolü yalnız yazılabilir lideri seçer.

İlk lider oluştuktan sonra uygulama veritabanını bir kere oluşturun. Failover tatbikatında aktif lideri `patronictl switchover` ile değiştirin; sağlık, oturum açma ve yeni kayıt oluşturma testlerini tekrar çalıştırın. Yedekleme Patroni yerine ayrıca pgBackRest/WAL arşivleme ile kurulmalı ve geri dönüş testi yapılmalıdır.

## 4. Uygulama HA (active-active)

En az iki uygulama düğümünde aynı harici DB/Redis ve aynı `/etc/yetka/cluster-secrets.env` kullanılır. Web ve worker her düğümde, scheduler yalnız bir yönetim düğümünde etkinleştirilir:

```dotenv
YETKA_ENABLE_WEB=true
YETKA_ENABLE_WORKER=true
YETKA_ENABLE_SCHEDULER=false
```

Scheduler düğümü kaybedilirse standby üzerinde `sudo systemctl enable --now yetka-scheduler` çalıştırın. Öndeki iki yük dengeleyicide [haproxy.cfg.example](ha/application/haproxy.cfg.example), VIP için [keepalived.conf.example](ha/application/keepalived.conf.example) kullanın.

`/var/lib/yetka/core` birden fazla düğümde ortaktır. Kurucu bu yolu `/opt/yetka/app/data` üzerine bind-mount eder ve `/etc/fstab` kaydı ekler. Üretimde kaynak yolu NFS/CephFS ile bağlayın veya Yetka’nın nesne depolama seçeneklerini yapılandırın. Düğüm-local medya ile active-active kurulursa yüklenen dosyalar düğümler arasında kaybolmuş görünür.

## 5. Active-standby

İki uygulama düğümünü aynı şekilde kurun ancak HAProxy backend’inde standby satırına `backup` ekleyin:

```haproxy
server app1 10.30.0.11:80 check
server app2 10.30.0.12:80 check backup
```

Her iki düğümde web servisi hazır kalabilir; kullanıcı trafiğini yalnız aktif düğüm alır. Worker’ların yalnız aktifte çalışması istenirse standby’da worker ve scheduler kapatılır. Otomatik servis rolü değişimi, ağ bölünmesinde çift scheduler riski nedeniyle yalnız bir quorum/fencing sistemiyle yapılmalıdır.

## 6. Lina, Luna ve connector paketleri

Çekirdek repo web UI ve protokol connector binary’lerini içermez. Yetka release
workflow'u [Yetka-Lina](https://github.com/akinarcak/Yetka-Lina),
[Yetka-Luna](https://github.com/akinarcak/Yetka-Luna) ve
[Yetka-Koko](https://github.com/akinarcak/Yetka-Koko) forklarını aynı sürüm
matrisiyle derler. Oluşan arşivler Yetka release'ine yüklenir ve SHA-256 ile
sabitlenmelidir:

```dotenv
YETKA_LINA_URL=https://github.com/akinarcak/Yetka/releases/download/yetka-1.0.0/lina-yetka-1.0.0.tar.gz
YETKA_LINA_SHA256=...
YETKA_LUNA_URL=https://github.com/akinarcak/Yetka/releases/download/yetka-1.0.0/luna-yetka-1.0.0.tar.gz
YETKA_LUNA_SHA256=...
YETKA_KOKO_URL=https://github.com/akinarcak/Yetka/releases/download/yetka-1.0.0/koko-yetka-1.0.0-linux-amd64.tar.gz
YETKA_KOKO_SHA256=...
```

URL verilip checksum verilmezse kurulum durur. Lina URL’si yoksa API kurulur fakat nginx UI için kasıtlı olarak `503` döndürür; eksik arayüz başarılı kurulum gibi gösterilmez. Koko sürümü core ile aynı olmalıdır. Lion/Chen gibi grafik ve WebDB connector’ları kendi desteklenen paketlerinde ayrı düğümlere kurulup aynı `CORE_HOST` ve `BOOTSTRAP_TOKEN` ile kaydedilmelidir.

## 7. Yükseltme ve işletim

İlk kurulumdan sonra kurulan host updater’ını kullanın. Araç release checksum’unu doğrular, dry-run yapar, DB/yapılandırma/veri yedeği alır, servisleri kontrollü yeniden başlatır ve sağlık kontrolü çalıştırır:

```bash
yetka-update check
sudo yetka-update plan --version v2.1.0
sudo yetka-update apply --version v2.1.0
```

HA ortamında önce trafiksiz standby/ikinci uygulama düğümünü güncelleyin. Sağlık ve kullanıcı akışları geçtikten sonra trafiği yeni düğüme taşıyın ve düğümleri tek tek ilerletin. Scheduler liderini en son güncelleyin. Şema migrasyonu uygulandıktan sonra eski uygulama sürümüne dönmek her zaman güvenli değildir; DB geri dönüş planı olmadan downgrade yapılmamalıdır. Ayrıntılar [bakım politikasındadır](MAINTENANCE.md).

```bash
systemctl status yetka-web yetka-worker yetka-scheduler nginx
journalctl -u yetka-web -u yetka-worker -f
sudo -u yetka /opt/yetka/venv/bin/python /opt/yetka/app/jms upgrade_db
```
