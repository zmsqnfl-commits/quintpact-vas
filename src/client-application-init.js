/** 프로젝트 디자인 선택은 유지하되 VAS 설정 화면은 읽기 쉬운 공통 셸로 고정합니다. */
(function () {
  'use strict';

  const state = VASThemeState.init();

  const themeName = document.getElementById('themeNameSpan');
  if (themeName) themeName.textContent = state.preset.charAt(0).toUpperCase() + state.preset.slice(1);
  if (document.body.dataset.mode === 'standalone') {
    const backLink = document.getElementById('hubBackLink');
    if (backLink) backLink.hidden = true;
  }
  VASThemeState.decorateLinks(document);
})();
