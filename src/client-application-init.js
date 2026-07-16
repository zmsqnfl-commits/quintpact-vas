/** 디자인 스튜디오 테마를 신청서에 적용합니다. */
(function () {
  'use strict';

  const state = VASThemeState.init();
  const v = state.tokens;
  const root = document.documentElement;
  root.style.setProperty('--bg-color', v.colors.background);
  root.style.setProperty('--text-main', v.colors.text);
  root.style.setProperty('--text-muted', v.colors.text);
  root.style.setProperty('--accent', v.colors.primary);
  root.style.setProperty('--card-bg', v.colors.surface);
  root.style.setProperty('--border', v.colors.border);
  root.style.setProperty('--border-dark', v.colors.text);

  root.style.setProperty('--form-motion', v.speed + 's');
  root.style.setProperty('--selection-radius', v.radius + 'px');
  const style = document.createElement('style');
  style.textContent = [
    'body{font-family:' + v.fontFamily + ';font-size:' + v.fontSize + 'px;letter-spacing:' + v.letterSpacing + 'em}',
    '.hero-section{background:var(--text-main);color:var(--bg-color)}',
    '.hero-meta,.back-link,.hero-title p,.progress-indicator{color:var(--bg-color)}',
    '.drag-drop-zone{background:var(--bg-color);border-color:var(--border)}'
  ].join('\n');
  document.head.appendChild(style);

  const themeName = document.getElementById('themeNameSpan');
  if (themeName) themeName.textContent = state.preset.charAt(0).toUpperCase() + state.preset.slice(1);
  if (document.body.dataset.mode === 'standalone') {
    const backLink = document.getElementById('hubBackLink');
    if (backLink) backLink.hidden = true;
  }
  VASThemeState.decorateLinks(document);
})();
