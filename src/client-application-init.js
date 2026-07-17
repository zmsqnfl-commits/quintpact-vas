/** 프로젝트 디자인 선택은 유지하되 VAS 설정 화면은 읽기 쉬운 공통 셸로 고정합니다. */
(function () {
  'use strict';

  const themeName = document.getElementById('themeNameSpan');
  function refreshThemeName() {
    const state = VASThemeState.get();
    if (themeName) themeName.textContent = state.preset.charAt(0).toUpperCase() + state.preset.slice(1);
  }

  VASThemeState.init();
  refreshThemeName();
  window.addEventListener('vas-theme-state', refreshThemeName);
  window.addEventListener('focus', refreshThemeName);
  window.addEventListener('pageshow', refreshThemeName);
  if (document.body.dataset.mode === 'standalone') {
    const backLink = document.getElementById('hubBackLink');
    if (backLink) backLink.hidden = true;
    document.querySelectorAll('[data-setup-settings]').forEach(function (button) { button.hidden = true; });
  }
  VASThemeState.decorateLinks(document);
})();
