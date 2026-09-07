/**
 * VAS Design Taste Pack
 * Lightweight prompt bridge for expert taste-skill principles.
 */
(function () {
  'use strict';

  const DEFAULT_TASTE_PROFILE = 'premiumFrontend';

  const TASTE_BASELINE = {
    label: 'VAS Taste Baseline',
    source: '.agents/skills/designer/TASTE-RULES.md',
    rules: [
      'Use the confirmed typography tokens and existing font assets; preserve Korean legibility.',
      'Choose layout and component patterns for the actual content and workflow; avoid repetitive filler.',
      'Use clear hierarchy, calibrated space and strong scan paths; use asymmetry only when the selected direction calls for it.',
      'Preserve confirmed brand colors and tokens; check contrast and readable states.',
      'Derive a readable on-primary foreground for filled buttons; do not reuse the surface color as button text. Keep normal text contrast at least 4.5:1 and explain conflicts with confirmed tokens.',
      'Use the target project stack and available components. VAS runtime constraints apply only to VAS itself.'
    ]
  };

  const TASTE_PROFILES = window.VASAgentResources.profiles;

  const PRESET_TASTE_PROFILE_MAP = {
    vercel: 'premiumFrontend',
    linear: 'curatedProduct',
    stripe: 'curatedSaas',
    shadcn: 'minimalistUtility',
    untitled: 'premiumFrontend',
    carbon: 'dataTool',
    apple: 'softPremium',
    google: 'softPremium',
    spotify: 'premiumFrontend',
    discord: 'premiumFrontend',
    airbnb: 'softPremium',
    notion: 'curatedKnowledge',
    github: 'dataTool',
    figma: 'dataTool',
    ant: 'dataTool',
    neobrutal: 'industrialBrutalist',
    awwwards: 'curatedEditorial',
    glow: 'softPremium'
  };

  const CONFLICT_POLICY = [
    'Priority: user requirements and target project rules > confirmed tokens and references > selected profile > preset defaults.',
    'Token values override conflicting preset prose. Report accessibility conflicts instead of silently changing the brand.',
    'Preserve the target framework, installed component system and font assets; choose new dependencies only when the task needs them.'
  ];
  const OUTPUT_CONTRACT = [
    'Treat preset brand names as style references, not a request to copy a brand. The studio demo content, geometric studies and sample counts are illustrative and must not become production data.',
    'Before implementation, name the actual screen task, the chosen composition, type ratios, spacing rhythm and focal point. Adapt editorial or consumer layouts to the requested product instead of forcing every screen into a hero plus three metric cards.',
    'Implement the requested result with concrete layout, typography, spacing, color and component states.',
    'Use actual reference files and screenshots. Name missing inputs instead of inventing their contents.',
    'Render and compare the result at mobile and desktop sizes. Correct differences and report verification evidence.'
  ];

  function formatRuleList(title, rules) {
    return '[' + title + ']\n' + rules.map(function (rule) {
      return '- ' + rule;
    }).join('\n');
  }

  function getTasteProfileKey(presetKey, preset, overrideProfileKey) {
    if (overrideProfileKey && TASTE_PROFILES[overrideProfileKey]) {
      return overrideProfileKey;
    }
    if (preset && preset.tasteProfile && TASTE_PROFILES[preset.tasteProfile]) {
      return preset.tasteProfile;
    }
    return PRESET_TASTE_PROFILE_MAP[presetKey] || DEFAULT_TASTE_PROFILE;
  }

  function composeAgentPrompt(presetKey, preset, overrideProfileKey, tokens) {
    const selectedPreset = preset || {};
    const manualProfileKey = overrideProfileKey || (
      window.getManualTasteProfileKey ? window.getManualTasteProfileKey() : null
    );
    const profileKey = getTasteProfileKey(presetKey, selectedPreset, manualProfileKey);
    const profile = TASTE_PROFILES[profileKey] || TASTE_PROFILES[DEFAULT_TASTE_PROFILE];
    const presetPrompt = selectedPreset.prompt || '';

    return [
      '[VAS DESIGN STUDIO PROMPT]\nPreset: ' + presetKey + '\nTaste Profile: ' + profile.label + '\nTaste Source: ' + profile.source,
      '[DESIGN SKILL]\n' + window.VASAgentResources.designer,
      formatRuleList('BASELINE RULES', TASTE_BASELINE.rules),
      formatRuleList('TASTE PROFILE RULES', profile.rules),
      '[PRESET DIRECTION]\n' + presetPrompt,
      tokens ? '[DESIGN TOKENS]\n' + JSON.stringify(tokens, null, 2) : '',
      formatRuleList('CONFLICT POLICY', CONFLICT_POLICY),
      formatRuleList('OUTPUT CONTRACT', OUTPUT_CONTRACT)
    ].join('\n\n');
  }

  window.VAS_TASTE_BASELINE = TASTE_BASELINE;
  window.VAS_TASTE_PROFILES = TASTE_PROFILES;
  window.VAS_PRESET_TASTE_PROFILE_MAP = PRESET_TASTE_PROFILE_MAP;
  window.getTasteProfileKey = getTasteProfileKey;
  window.composeAgentPrompt = composeAgentPrompt;
})();
