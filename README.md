<div align="center">
  <a name="readme-top"></a>

# Yetka

> Docker'sız Linux, harici veritabanı, PostgreSQL HA ve uygulama active-active/active-standby kurulumları için [kurulum rehberine](deploy/README.md) bakın.

**Yetkili Erişim ve Terminal Kayıt Altyapısı**

_An open-source Privileged Access Management (PAM) platform_

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

</div>
<br/>

## Yetka nedir?

Yetka, DevOps ve IT ekiplerine SSH, RDP, Kubernetes, veritabanı ve uzak uygulama uç noktalarına web tarayıcısı üzerinden güvenli ve denetlenebilir erişim sağlayan, açık kaynak bir **Ayrıcalıklı Erişim Yönetimi (PAM)** platformudur.

Adı "yetki" kelimesinden türetilmiştir ve açılımı: **Y**etkili **E**rişim ve **T**erminal **K**ayıt **A**ltyapısı.

Temel yetenekler:

- **Ayrıcalıklı erişim**: SSH / RDP / VNC / veritabanı / Kubernetes uç noktalarına tarayıcıdan tek noktadan erişim.
- **Oturum kaydı ve denetim**: Tüm oturumların kaydı, komut filtreleme, dosya transfer loglama.
- **Kimlik ve yetkilendirme**: LDAP/AD, MFA, OIDC/SAML2/OAuth2 SSO, ACL ve RBAC tabanlı erişim politikaları.
- **Hesap yönetimi**: Otomatik keşif ve hesap otomasyonu.

## JumpServer ile ilişkisi

> Yetka, [JumpServer](https://github.com/jumpserver/jumpserver)'ın (GPLv3 lisanslı) açık kaynak bir fork'udur.
>
> JumpServer, Fit2Cloud tarafından geliştirilen bir açık kaynak PAM platformudur. Yetka bu güçlü temeli alır, tamamen açık kaynak olarak geliştirmeyi sürdürür ve bazı özellikleri topluluk sürümünde serbestleştirir. "JumpServer" adı ve logosu Fit2Cloud'a ait ticari markalardır; Yetka bu markaları kullanmaz ve Fit2Cloud ile resmi bir bağı yoktur.
>
> Orijinal telif bildirimleri ve GPLv3 lisansı korunmaktadır. Kaynağa ve tüm katkıcılara teşekkürler.

## Kolay kurulum

Temiz bir Linux sunucusu hazırlayın (64-bit, en az 4 CPU / 8 GB RAM önerilir) ve Docker'ın kurulu olduğundan emin olun.

```sh
git clone https://github.com/akinarcak/Yetka.git
cd Yetka

docker build -t yetka:latest .
docker volume create yetka_data
docker run -d --name yetka \
  --restart unless-stopped \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e BOOTSTRAP_TOKEN="$(openssl rand -hex 24)" \
  -v yetka_data:/opt/data \
  -p 8080:8080 \
  yetka:latest
```

Tarayıcıdan `http://sunucu-ip:8080/` adresine gidin.

Yeni ve boş bir `yetka_data` volume'u ile ilk kurulumda varsayılan giriş bilgileri:

- Kullanıcı adı: `admin`
- Parola: `ChangeMe`

Bu bilgiler yalnızca yeni veri volume'u için geçerlidir. Daha önce çalıştırılmış
bir volume kullanıyorsanız admin parolası volume içinde saklanan mevcut değerdir;
bu README'deki parola onu sıfırlamaz. İlk girişten sonra varsayılan parolayı
mutlaka değiştirin.

## Geliştirme için çalıştırma

Deneme/geliştirme için ayrı bir container adı ve volume kullanmak isterseniz:

```sh
docker build -t yetka:dev .
docker run -d --name yetka-dev \
  --restart unless-stopped \
  -v yetka_dev_data:/opt/data \
  -p 8080:8080 \
  yetka:dev
```

Bu modda arayüze `http://sunucu-ip:8080/` adresinden erişebilirsiniz.

## Lisans

Bu proje **GNU General Public License v3.0 (GPLv3)** ile lisanslanmıştır — bkz. [LICENSE](LICENSE). Türev bir çalışma olarak, JumpServer'ın GPLv3 lisansı ve şartları geçerlidir.
