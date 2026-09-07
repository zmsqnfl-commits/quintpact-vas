/** Open the current composition and confirmed tokens in a read-only sample tab. */
(function () {
  'use strict';
  function refresh() {
    const link = document.getElementById('openDesignSample');
    if (!link) return;
    const state = VASThemeState.get();
    link.href = 'design-sample.html?preset=' + encodeURIComponent(state.basePreset) +
      '#vas=' + VASThemeState.encodeNavigationState(state);
  }
  window.addEventListener('vas-theme-state', refresh);
  refresh();
})();
