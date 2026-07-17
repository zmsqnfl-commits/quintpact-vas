/** 새 작업과 기존 작업이 같은 디자인 설정을 최종 JSON에 담도록 연결합니다. */
(function (global) {
  'use strict';

  const mounts = [];

  function title(key) { return key.charAt(0).toUpperCase() + key.slice(1); }
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
    if (item.summary) item.summary.textContent = title(state.preset) + ' — ' + description(state.preset);
    if (item.referenceLabel) item.referenceLabel.textContent = title(state.preset) + ' 디자인 예시·설정 보기';
  }

  function recommendedPreset(result) {
    const values = [];
    if (result && Array.isArray(result.preferences)) values.push.apply(values, result.preferences);
    if (result && Array.isArray(result.results)) result.results.forEach(function (entry) {
      if (entry && entry.kind === 'memory') values.push(entry.text || '');
    });
    const combined = values.join(' ').toLowerCase();
    return Object.keys(PRESETS).find(function (key) {
      return new RegExp('(^|[^a-z0-9])' + key.toLowerCase() + '([^a-z0-9]|$)').test(combined);
    }) || null;
  }

  async function refreshRecommendation(item) {
    const button = item.recommendation;
    if (!button) return;
    button.hidden = true;
    button.disabled = false;
    if (!global.VASPersonalization || !global.VASRagLite) return;
    try {
      const status = await VASPersonalization.status();
      if (status.consent !== true || status.paused) return;
      const keys = Object.keys(PRESETS);
      const result = await VASPersonalization.recommend('디자인 프리셋 ' + keys.join(' '), { limit: 12 });
      const key = recommendedPreset(result);
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
    VASThemeState.commit({ preset: key, tokens: presetTokens(PRESETS[key]) });
    mounts.forEach(function (item) { refreshMount(item); refreshRecommendation(item); });
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
    recommendation.addEventListener('click', function () {
      const key = recommendation.dataset.preset;
      if (!key) return;
      apply(key);
      if (global.VASPersonalization) VASPersonalization.record({
        type: 'recommendation_used', source: 'setup-design', payload: { preset: key }
      });
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
  global.addEventListener('vas-theme-state', function () {
    mounts.forEach(refreshMount);
  });
  global.VASSetupDesign = Object.freeze({ mount: mount, apply: apply, context: context, refresh: refresh });
})(window);
