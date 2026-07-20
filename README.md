<div align="center">
  <a name="readme-top"></a>

# Yetka

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

## Hızlı başlangıç

Temiz bir Linux sunucusu hazırlayın (64-bit, >= 4c8g) ve Docker'ı kurun.

```sh
# Geliştirme/deneme için all-in-one imajı üzerine Yetka katmanı
docker build -t yetka:dev .
docker run -d --name yetka \
  -v yetka_data:/opt/data \
  -v yetka_pg:/var/lib/postgresql \
  -p 80:80 yetka:dev
```

Tarayıcıdan `http://sunucu-ip/` adresine gidin. Varsayılan giriş: `admin` / `ChangeMe` (ilk girişte değiştirmeniz istenir).

## Lisans

Bu proje **GNU General Public License v3.0 (GPLv3)** ile lisanslanmıştır — bkz. [LICENSE](LICENSE). Türev bir çalışma olarak, JumpServer'ın GPLv3 lisansı ve şartları geçerlidir.
