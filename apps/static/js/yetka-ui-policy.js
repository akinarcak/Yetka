(function () {
  'use strict';

  var LICENSE_ROUTE = /^#\/settings\/license(?:[/?]|$)/;
  var LICENSE_LINK_SELECTOR = 'a[href="#/settings/license"],a[href$="/settings/license"]';
  var observer;
  var cleanupScheduled = false;

  function redirectLicenseRoute() {
    if (!LICENSE_ROUTE.test(window.location.hash)) return false;
    window.location.replace(
      window.location.pathname + window.location.search + '#/settings/basic'
    );
    return true;
  }

  function removeLicenseLinks() {
    document.querySelectorAll(LICENSE_LINK_SELECTOR).forEach(function (link) {
      var menuItem = link.closest('li');
      (menuItem || link).remove();
    });
  }

  function scheduleCleanup() {
    if (cleanupScheduled) return;
    cleanupScheduled = true;
    window.requestAnimationFrame(function () {
      cleanupScheduled = false;
      removeLicenseLinks();
    });
  }

  function installPolicy() {
    if (redirectLicenseRoute()) return;
    removeLicenseLinks();
    observer = new MutationObserver(scheduleCleanup);
    observer.observe(document.body, {childList: true, subtree: true});
  }

  var style = document.createElement('style');
  style.id = 'yetka-ui-policy-style';
  style.textContent = LICENSE_LINK_SELECTOR + '{display:none!important}';
  document.head.appendChild(style);

  window.addEventListener('hashchange', redirectLicenseRoute);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installPolicy, {once: true});
  } else {
    installPolicy();
  }
}());
