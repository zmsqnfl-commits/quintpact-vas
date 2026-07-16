/** 모든 VAS 화면에 같은 오프라인 Editorial 토큰을 적용합니다. */
(function (global) {
  'use strict';

  function alpha(hex, amount) {
    const match = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
    if (!match) return hex;
    return 'rgb(' + [match[1], match[2], match[3]].map(function (part) {
      return parseInt(part, 16);
    }).join(' ') + ' / ' + amount + ')';
  }

  function apply(state) {
    const theme = state || VASThemeState.init();
    const tokens = theme.tokens;
    const root = document.documentElement;
    const accent = theme.preset === 'awwwards' ? '#9b6808' : tokens.colors.primary;
    const values = {
      '--vas-bg': tokens.colors.background,
      '--vas-surface': tokens.colors.surface,
      '--vas-text': tokens.colors.text,
      '--vas-border': tokens.colors.border,
      '--vas-line': alpha(tokens.colors.border, '28%'),
      '--vas-accent': accent,
      '--vas-font-sans': tokens.fontFamily,
      '--vas-font-mono': VASStorage.SYSTEM_MONO,
      '--vas-font-size': tokens.fontSize + 'px',
      '--vas-tracking': tokens.letterSpacing + 'em',
      '--vas-space': tokens.padding + 'px',
      '--vas-radius': tokens.radius + 'px',
      '--vas-rule': Math.max(1, tokens.borderWidth) + 'px',
      '--vas-motion': Math.max(0.1, tokens.speed) + 's'
    };
    Object.keys(values).forEach(function (key) { root.style.setProperty(key, values[key]); });
    root.dataset.preset = theme.preset;
    return theme;
  }

  function init() {
    const state = apply(VASThemeState.init());
    global.addEventListener('vas-theme-state', function (event) { apply(event.detail); });
    return state;
  }

  global.VASEditorialTheme = Object.freeze({ init, apply });
  if (global.VASThemeState && global.VASStorage) init();
})(window);
