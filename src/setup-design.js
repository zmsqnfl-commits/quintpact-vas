/** 새 작업과 기존 작업이 같은 디자인 설정을 최종 JSON에 담도록 연결합니다. */
(function (global) {
  'use strict';

  const mounts = [];
  let lastConfirmation = '';

  function title(key) { return PRESETS[key]?.label || key.charAt(0).toUpperCase() + key.slice(1); }
  function description(key) {
    if (typeof PRESET_DESCRIPTIONS !== 'undefined' && PRESET_DESCRIPTIONS[key]) return PRESET_DESCRIPTIONS[key];
    return '색상과 간격을 직접 정한 사용자 디자인';
  }

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
    const preset = typeof PRESETS !== 'undefined' ? PRESETS[state.basePreset || state.preset] : null;
    const fallback = { prompt: '[Custom Token Direction]\n' + JSON.stringify(state.tokens, null, 2) };
    const direction = global.composeAgentPrompt
      ? global.composeAgentPrompt(state.basePreset || state.preset, preset || fallback, state.tasteProfileMode === 'auto' ? null : state.tasteProfileMode, state.tokens)
      : (preset ? preset.prompt : fallback.prompt);
    return {
      included: true,
      preset: state.preset,
      basePreset: state.basePreset,
      tasteProfileMode: state.tasteProfileMode,
      tokens: state.tokens,
      direction: direction
    };
  }

  function refreshMount(item) {
    const state = VASThemeState.get();
    if (item.select) {
      const known = typeof PRESETS !== 'undefined' && PRESETS[state.preset];
      item.select.querySelectorAll('[data-legacy]').forEach(option => option.remove());
      if (known && !VAS_PRESET_KEYS.includes(state.preset)) {
        const legacy = new Option(title(state.preset) + ' · 저장된 이전 스타일', state.preset);
        legacy.dataset.legacy = '';
        item.select.append(legacy);
      }
      item.select.value = known ? state.preset : 'custom';
    }
    if (item.summary) item.summary.textContent = title(state.basePreset || state.preset) + (state.preset === 'custom' ? ' · 세부 값 수정' : '') + ' — ' + description(state.basePreset || state.preset);
    if (item.referenceLabel) item.referenceLabel.textContent = title(state.preset) + ' 디자인 예시·설정 보기';
  }

  async function refreshRecommendation(item) {
    const request = item.request = (item.request || 0) + 1;
    const button = item.recommendation;
    if (!button) return;
    button.hidden = true;
    button.disabled = false;
    if (!global.VASPersonalization) return;
    try {
      const status = await VASPersonalization.status();
      if (status.consent !== true || status.paused) return;
      const keys = VAS_PRESET_KEYS;
      const events = await VASPersonalization.list({ type: 'theme_selected' });
      const confirmed = events.find(function (event) { return event.payload && event.payload.confirmed === true && keys.includes(event.payload.preset); });
      const key = confirmed && confirmed.payload.preset;
      if (item.request !== request) return;
      if (!key) return;
      const current = VASThemeState.get().preset;
      button.dataset.preset = key;
      button.textContent = current === key
        ? '작업 기억 추천 적용됨: ' + title(key)
        : '작업 기억 추천: ' + title(key) + ' 적용';
      button.disabled = current === key;
      button.hidden = false;
    } catch (error) {
      button.hidden = true;
    }
  }

  function apply(key) {
    if (key === 'custom' || typeof PRESETS === 'undefined' || !PRESETS[key]) return;
    VASThemeState.commit({ preset: key, basePreset: key, tokens: presetTokens(PRESETS[key]) });
    mounts.forEach(function (item) { refreshMount(item); refreshRecommendation(item); });
  }

  function mount(selectId, summaryId) {
    const select = document.getElementById(selectId);
    const summary = document.getElementById(summaryId);
    if (!select) return;
    select.innerHTML = '';
    VAS_PRESET_KEYS.forEach(function (key) {
      const option = document.createElement('option');
      option.value = key;
      option.textContent = title(key);
      select.append(option);
    });
    const custom = document.createElement('option');
    custom.value = 'custom';
    custom.textContent = 'Custom';
    select.append(custom);
    const parent = select.closest('.handoff-design, .design-choice');
    const referenceLabel = parent && parent.querySelector('[data-design-reference-label]');
    const recommendation = document.createElement('button');
    recommendation.type = 'button';
    recommendation.className = 'design-memory-suggestion';
    recommendation.setAttribute('data-design-memory-suggestion', '');
    recommendation.hidden = true;
    if (summary) summary.insertAdjacentElement('afterend', recommendation);
    const item = { select: select, summary: summary, referenceLabel: referenceLabel, recommendation: recommendation };
    mounts.push(item);
    select.addEventListener('change', function () { apply(select.value); });
    recommendation.addEventListener('click', async function () {
      const key = recommendation.dataset.preset;
      if (!key) return;
      const state = await VASPersonalization.status().catch(function () { return {}; });
      if (state.consent !== true || state.paused || recommendation.hidden) return;
      apply(key);
    });
    refreshMount(item);
    refreshRecommendation(item);
  }

  function refresh() {
    VASThemeState.sync();
    mounts.forEach(refreshMount);
    return Promise.all(mounts.map(refreshRecommendation));
  }

  global.addEventListener('focus', refresh);
  global.addEventListener('pageshow', refresh);
  global.addEventListener('vas-memory-change', function (event) {
    if (['clear', 'delete', 'consent'].includes(event.detail.action)) lastConfirmation = '';
    mounts.forEach(refreshRecommendation);
  });
  global.addEventListener('vas-theme-state', function () {
    mounts.forEach(refreshMount);
  });
  async function confirm() {
    if (!global.VASPersonalization) return;
    const state = VASThemeState.get();
    const key = state.basePreset || state.preset;
    if (!VAS_PRESET_KEYS.includes(key)) return;
    const identity = JSON.stringify([key, state.tasteProfileMode, state.tokens]);
    if (identity === lastConfirmation) return;
    const recorded = await VASPersonalization.record({ type: 'theme_selected', source: 'setup-design', payload: { preset: key, confirmed: true } });
    if (recorded) lastConfirmation = identity;
  }
  global.VASSetupDesign = Object.freeze({ mount: mount, apply: apply, context: context, refresh: refresh, confirm: confirm });
})(window);
