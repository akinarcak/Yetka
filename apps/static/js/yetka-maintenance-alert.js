(function () {
  'use strict';

  var API_URL = '/api/v1/maintenance/status/';
  var DISMISS_KEY = 'yetka-maintenance-dismissed-v2';
  var DISMISS_MS = 24 * 60 * 60 * 1000;

  function isRecentlyDismissed(fingerprint) {
    try {
      var saved = JSON.parse(window.localStorage.getItem(DISMISS_KEY) || '{}');
      return saved.fingerprint === fingerprint && Date.now() - saved.at < DISMISS_MS;
    } catch (_) {
      return false;
    }
  }

  function dismiss(fingerprint) {
    window.localStorage.setItem(DISMISS_KEY, JSON.stringify({fingerprint: fingerprint, at: Date.now()}));
  }

  function addLine(container, text) {
    var line = document.createElement('li');
    line.textContent = text;
    container.appendChild(line);
  }

  function showAlert(status) {
    if (!status.attention_required || !status.fingerprint || isRecentlyDismissed(status.fingerprint)) return;

    var overlay = document.createElement('div');
    overlay.id = 'yetka-maintenance-alert';
    overlay.innerHTML = '<div class="yetka-maintenance-card" role="dialog" aria-modal="true" aria-labelledby="yetka-maintenance-title">' +
      '<div class="yetka-maintenance-icon">!</div>' +
      '<div class="yetka-maintenance-content"><h2 id="yetka-maintenance-title">Güvenlik ve güncelleme kontrolü</h2>' +
      '<p>Yetka yöneticisinin incelemesi gereken yeni bakım bulguları var.</p>' +
      '<ul class="yetka-maintenance-findings"></ul>' +
      '<div class="yetka-update-command" hidden><span>Sunucuda çalıştırılacak doğrulanmış komut:</span><code></code><button type="button" class="yetka-copy-command">Komutu kopyala</button></div>' +
      '<div class="yetka-maintenance-actions"><a target="_blank" rel="noopener noreferrer">Bakım rehberi</a>' +
      '<button type="button" class="yetka-dismiss">24 saat ertele</button></div></div></div>';

    var findings = overlay.querySelector('.yetka-maintenance-findings');
    if (status.update && status.update.available) {
      addLine(findings, 'Yeni Yetka sürümü: ' + status.update.latest_version + ' (kurulu: ' + status.update.current_version + ')');
      if (status.update.command) {
        var commandBox = overlay.querySelector('.yetka-update-command');
        commandBox.hidden = false;
        commandBox.querySelector('code').textContent = status.update.command;
        commandBox.querySelector('.yetka-copy-command').addEventListener('click', function (event) {
          if (!window.navigator.clipboard) return;
          window.navigator.clipboard.writeText(status.update.command).then(function () {
            event.target.textContent = 'Kopyalandı';
          }).catch(function () { /* The command remains selectable in the dialog. */ });
        });
      }
    }
    if (status.upstream && status.upstream.review_required) {
      addLine(findings, 'Yeni JumpServer upstream sürümü inceleme bekliyor: ' + status.upstream.latest_version + ' (Yetka tabanı: ' + status.upstream.base_version + '). Otomatik uygulanmaz.');
    }
    if (status.vulnerabilities && status.vulnerabilities.total) {
      addLine(findings, status.vulnerabilities.total + ' güvenlik kaydı, ' + status.vulnerabilities.affected_packages + ' kurulu paketi etkiliyor.');
      status.vulnerabilities.items.slice(0, 4).forEach(function (item) {
        addLine(findings, item.package + ' ' + item.version + ': ' + item.ids.slice(0, 3).join(', '));
      });
    }
    if (status.errors && status.errors.length) {
      addLine(findings, 'Bakım taramasının bazı kaynaklarına ulaşılamadı; ağ ve scheduler loglarını kontrol edin.');
    }

    var guide = overlay.querySelector('a');
    guide.href = status.guide_url;
    overlay.querySelector('.yetka-dismiss').addEventListener('click', function () {
      dismiss(status.fingerprint);
      overlay.remove();
    });
    document.body.appendChild(overlay);
  }

  function installStyles() {
    var style = document.createElement('style');
    style.textContent = '#yetka-maintenance-alert{position:fixed;inset:0;z-index:2147483000;background:rgba(15,23,42,.58);display:flex;align-items:flex-start;justify-content:center;padding:8vh 20px;font-family:Arial,sans-serif}' +
      '.yetka-maintenance-card{max-width:680px;width:100%;display:flex;gap:18px;background:#fff;border-radius:12px;box-shadow:0 24px 70px rgba(0,0,0,.3);padding:24px;color:#172033}' +
      '.yetka-maintenance-icon{flex:0 0 42px;height:42px;border-radius:50%;display:grid;place-items:center;background:#fff3cd;color:#8a5b00;font-size:26px;font-weight:700}' +
      '.yetka-maintenance-content{min-width:0;flex:1}.yetka-maintenance-content h2{margin:2px 0 8px;font-size:21px}.yetka-maintenance-content p{margin:0 0 12px;color:#475569}' +
      '.yetka-maintenance-findings{margin:0 0 18px;padding-left:20px;max-height:260px;overflow:auto}.yetka-maintenance-findings li{margin:7px 0;overflow-wrap:anywhere}' +
      '.yetka-update-command{margin:0 0 18px;padding:12px;border:1px solid #bbf7d0;border-radius:8px;background:#f0fdf4}.yetka-update-command span{display:block;margin-bottom:7px;color:#475569;font-size:13px}.yetka-update-command code{display:block;padding:9px;background:#172033;color:#f8fafc;border-radius:6px;overflow:auto}.yetka-update-command .yetka-copy-command{margin-top:8px}' +
      '.yetka-maintenance-actions{display:flex;gap:10px;justify-content:flex-end;align-items:center;flex-wrap:wrap}.yetka-maintenance-actions a,.yetka-maintenance-actions button{border-radius:7px;padding:9px 14px;font-size:14px}' +
      '.yetka-maintenance-actions a{background:#166534;color:#fff;text-decoration:none}.yetka-maintenance-actions button{border:1px solid #cbd5e1;background:#fff;color:#334155;cursor:pointer}';
    document.head.appendChild(style);
  }

  function check() {
    window.fetch(API_URL, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (status) { if (status) { installStyles(); showAlert(status); } })
      .catch(function () { /* Login and network failures must not block the console. */ });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', check);
  else check();
}());
