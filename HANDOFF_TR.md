# Görev: Yetka için Türkçe (tr) çeviri

Yetka (JumpServer GPLv3 fork'u) arayüzü şu an yalnızca **English + Türkçe** dil seçeneği
sunuyor, ancak **Türkçe çeviri dosyaları henüz yok** — Türkçe seçilince metinler
İngilizce'ye düşüyor. Bu görev, Türkçe çeviri dosyalarını üretip derlemektir.

Dil `tr` kod tarafında zaten kayıtlı (`apps/common/const/choices.py` → `Language.tr`,
ve `LANGUAGES_SUPPORTED='en,tr'`). **Kod değişikliği gerekmiyor**, yalnızca çeviri
dosyaları eklenip derlenecek.

## 1) Backend çevirileri (gettext `.po` → `.mo`)

Kaynak (İngilizce) → Üretilecek (Türkçe):

| Kaynak (oku) | Hedef (oluştur) |
|---|---|
| `apps/i18n/core/en/LC_MESSAGES/django.po` (~2680 dizge) | `apps/i18n/core/tr/LC_MESSAGES/django.po` |
| `apps/i18n/core/en/LC_MESSAGES/djangojs.po` | `apps/i18n/core/tr/LC_MESSAGES/djangojs.po` |

Kurallar:
- `msgid` satırlarını **AYNEN** koru; yalnızca `msgstr ""` içini Türkçe doldur.
- Placeholder'ları koru: `%s`, `%(name)s`, `{}`, `{name}`, `%d`, HTML etiketleri (`<b>` vb.).
- `.po` başlığındaki (header) `Language: tr\n`, `Plural-Forms: nplurals=2; plural=(n != 1);\n`
  alanlarını ayarla. Türkçe çoğul kuralı: `nplurals=2; plural=(n != 1);`.
- En kolay yol: `en/.../django.po` dosyasını `tr/.../django.po`'ya kopyala, sonra her
  `msgstr` alanını çevir.

Derleme (çeviriden sonra, repo kökünde):
```
cd apps
python manage.py compilemessages -l tr
```
Bu, her `.po` yanında `.mo` üretir. `.mo` dosyaları da commit edilmeli.

## 2) Frontend çevirileri (JSON)

Her bileşen için `en.json` → `tr.json` (aynı dizinde):

| Kaynak (oku) | Hedef (oluştur) |
|---|---|
| `apps/i18n/lina/en.json` (~92 KB, web UI) | `apps/i18n/lina/tr.json` |
| `apps/i18n/luna/en.json` (web terminal) | `apps/i18n/luna/tr.json` |
| `apps/i18n/koko/en.json` (SSH connector) | `apps/i18n/koko/tr.json` |
| `apps/i18n/lion/en.json` (RDP/VNC connector) | `apps/i18n/lion/tr.json` |
| `apps/i18n/chen/en.json` (DB client) | `apps/i18n/chen/tr.json` |

Kurallar:
- JSON **anahtarlarını (key) AYNEN** koru; yalnızca değerleri (value) Türkçe'ye çevir.
- Placeholder'ları koru: `{name}`, `{0}`, `%{count}`, `{{var}}` vb.
- Geçerli JSON olarak kaydet (UTF-8, aynı yapı). Referans için mevcut `zh.json`/`ja.json`
  dosyalarına bakılabilir (aynı anahtar seti).

## 3) Marka notu
Çevirilerde ürün adı **"Yetka"** olmalı; "JumpServer" geçen kullanıcıya görünür dizeleri
"Yetka" yap (lisans/atıf metinleri hariç — onlar İngilizce/olduğu gibi kalabilir).

## 4) Doğrulama
1. `compilemessages -l tr` hatasız çalışmalı; `tr/LC_MESSAGES/*.mo` üretilmeli.
2. `tr.json` dosyaları geçerli JSON olmalı (ör. `python -m json.tool apps/i18n/lina/tr.json`).
3. Çalışan container'da (veya yeniden derlenmiş imajda) arayüzü Türkçe'ye alıp
   login sayfası + panelde metinlerin Türkçe geldiğini gör.

## 5) İmaja yansıtma (Yetka dağıtımı için)
Bu proje `jms_all` imajı üzerine ince overlay ile paketleniyor. Çeviri dosyaları
eklendikten sonra Dockerfile'a şu COPY'ler eklenmeli (build context göreli yolları):
```
COPY apps/i18n/core/tr /opt/jumpserver/apps/i18n/core/tr
COPY apps/i18n/lina/tr.json /opt/jumpserver/apps/i18n/lina/tr.json
COPY apps/i18n/luna/tr.json /opt/jumpserver/apps/i18n/luna/tr.json
COPY apps/i18n/koko/tr.json /opt/jumpserver/apps/i18n/koko/tr.json
COPY apps/i18n/lion/tr.json /opt/jumpserver/apps/i18n/lion/tr.json
COPY apps/i18n/chen/tr.json /opt/jumpserver/apps/i18n/chen/tr.json
```
(`.mo` dosyaları `core/tr` içinde COPY ile gelir; container başlangıcında ayrıca
`compilemessages` gerekmez ama emin olmak için çalıştırılabilir.)

## Öncelik
En görünür etki: `core/django.po` + `lina/en.json` (asıl web arayüzü). Önce bu ikisi
yapılırsa arayüzün büyük kısmı Türkçe olur; koko/lion/chen/luna ikincil.
