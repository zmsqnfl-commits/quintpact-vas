(function () {
  'use strict';

  VASThemeState.init();
  const root = document.documentElement;
  root.dataset.shellPreset = 'awwwards';
  VASThemeState.decorateLinks(document);
  if (globalThis.VASRuntime && VASRuntime.isAvailable()) {
    VASRuntime.request('/api/status').then(function (status) {
      if (status.layout !== 'project') return;
      document.querySelector('.hero-copy p').textContent = '지금 연 폴더가 프로젝트입니다. 앱은 최상위 src/에 만들고, VAS 설정은 여기서 관리하세요.';
      VASProjectPrompt.mount();
    }).catch(function () { /* The form and its original help also work offline. */ });
  }

  const hero = document.querySelector('[data-reveal]');
  const reduced = globalThis.matchMedia && globalThis.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (hero) {
    if (!reduced) root.classList.add('motion-ready');
    requestAnimationFrame(function () { hero.classList.add('is-visible'); });
  }
})();
