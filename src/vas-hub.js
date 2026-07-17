(function () {
  'use strict';

  VASThemeState.init();
  const root = document.documentElement;
  root.dataset.shellPreset = 'awwwards';
  VASThemeState.decorateLinks(document);

  const hero = document.querySelector('[data-reveal]');
  const reduced = globalThis.matchMedia && globalThis.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (hero) {
    if (!reduced) root.classList.add('motion-ready');
    requestAnimationFrame(function () { hero.classList.add('is-visible'); });
  }
})();
