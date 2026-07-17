/** 새 작업과 기존 작업이 같은 디자인 설정을 최종 JSON에 담도록 연결합니다. */
(function (global) {
  'use strict';

  const mounts = [];

  function title(key) { return key.charAt(0).toUpperCase() + key.slice(1); }

  function presetTokens(preset) {
    const fontSize = 16;
    return VASStorage.normalizeTheme({
      fontFamily: preset.font,
      fontSize: fontSize,
      letterSpacing: preset.ls,
      padding: preset.pad,
      radius: preset.rad,
      borderWidth: preset.bw,
      shadow: preset.shadow,
      speed: preset.speed,
      colors: {
        primary: preset.primary,
        background: preset.bg,
        surface: preset.surface,
        text: preset.text,
        border: preset.border,
        success: '#10b981'
      }
    });
  }

  function context() {
    const state = VASThemeState.get();
    const preset = typeof PRESETS !== 'undefined' ? PRESETS[state.preset] : null;
    const fallback = { prompt: '[Custom Token Direction]\n' + JSON.stringify(state.tokens, null, 2) };
    const direction = global.composeAgentPrompt
      ? global.composeAgentPrompt(state.preset, preset || fallback, state.tasteProfileMode === 'auto' ? null : state.tasteProfileMode)
      : (preset ? preset.prompt : fallback.prompt);
    return {
      included: true,
      preset: state.preset,
      tasteProfileMode: state.tasteProfileMode,
      tokens: state.tokens,
      direction: direction
    };
  }

  function refreshMount(item) {
    const state = VASThemeState.get();
    if (item.select) {
      const known = typeof PRESETS !== 'undefined' && PRESETS[state.preset];
      item.select.value = known ? state.preset : 'custom';
    }
    if (item.summary) item.summary.textContent = title(state.preset) + ' · ' + state.tokens.colors.background + ' · ' + state.tokens.colors.text;
  }

  function apply(key) {
    if (key === 'custom' || typeof PRESETS === 'undefined' || !PRESETS[key]) return;
    VASThemeState.commit({ preset: key, tokens: presetTokens(PRESETS[key]) });
    mounts.forEach(refreshMount);
  }

  function mount(selectId, summaryId) {
    const select = document.getElementById(selectId);
    const summary = document.getElementById(summaryId);
    if (!select) return;
    select.innerHTML = '';
    Object.keys(PRESETS).forEach(function (key) {
      const option = document.createElement('option');
      option.value = key;
      option.textContent = title(key);
      select.append(option);
    });
    const custom = document.createElement('option');
    custom.value = 'custom';
    custom.textContent = 'Custom';
    select.append(custom);
    const item = { select: select, summary: summary };
    mounts.push(item);
    select.addEventListener('change', function () { apply(select.value); });
    refreshMount(item);
  }

  global.addEventListener('focus', function () { mounts.forEach(refreshMount); });
  global.VASSetupDesign = Object.freeze({ mount: mount, apply: apply, context: context, refresh: function () { mounts.forEach(refreshMount); } });
})(window);
