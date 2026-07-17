(function () {
  'use strict';

  const state = VASThemeState.init();
  const root = document.documentElement;
  root.dataset.preset = state.preset;
  root.style.setProperty('--bg', state.tokens.colors.background);
  root.style.setProperty('--surface', state.tokens.colors.surface);
  root.style.setProperty('--text', state.tokens.colors.text);
  root.style.setProperty('--primary', state.tokens.colors.primary);
  root.style.setProperty('--space', state.tokens.padding + 'px');
  root.style.setProperty('--radius', state.tokens.radius + 'px');
  root.style.setProperty('--shadow-size', state.tokens.shadow + 'px');
  root.style.setProperty('--line', 'color-mix(in srgb, ' + state.tokens.colors.border + ' 24%, transparent)');
  root.style.setProperty('--editorial-accent', state.preset === 'awwwards' ? '#9b6808' : state.tokens.colors.primary);
  root.style.setProperty('--font-sans', state.tokens.fontFamily);
  root.style.setProperty('--font-size', state.tokens.fontSize + 'px');
  root.style.setProperty('--motion', Math.max(.1, state.tokens.speed) + 's');
  VASThemeState.decorateLinks(document);

  const hero = document.querySelector('[data-reveal]');
  const reduced = globalThis.matchMedia && globalThis.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (hero) {
    if (!reduced) root.classList.add('motion-ready');
    requestAnimationFrame(function () { hero.classList.add('is-visible'); });
  }

  document.querySelectorAll('[data-track]').forEach(function (link) {
    link.addEventListener('click', function () {
      if (window.VASPersonalization) {
        VASPersonalization.record({ type: 'navigation', source: 'start', payload: { target: link.dataset.track } });
      }
    });
  });
})();
