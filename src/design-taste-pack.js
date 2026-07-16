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
      'Use the system sans stack for Korean UI and the system mono stack for numeric or code-heavy details.',
      'Avoid generic centered heroes, repeated 3-card rows, card spam, default emojis, and template-like SaaS layouts.',
      'Prefer deliberate asymmetry, clear hierarchy, calibrated negative space, and strong scan paths.',
      'Use one controlled accent color; avoid generic AI purple/blue gradients unless the preset explicitly needs a muted reference.',
      'Use only standalone HTML, Vanilla CSS, and Vanilla JS; translate heavy motion ideas into CSS transitions or small JS.'
    ]
  };

  const TASTE_PROFILES = {
    premiumFrontend: {
      label: 'Premium Frontend',
      source: 'taste-skill / design-taste-frontend',
      rules: [
        'Make the interface feel product-grade, not like a generic mockup.',
        'Use precise spacing, calm surfaces, clean borders, and intentional type scale.',
        'Keep buttons, panels, controls, and states practical enough to implement directly.',
        'Favor restrained motion with tactile hover/active feedback.',
        'Avoid decorative gradients, random blobs, oversized cards, and filler copy.'
      ]
    },
    editorialMotion: {
      label: 'Editorial Motion',
      source: 'gpt-taste / Awwwards editorial',
      rules: [
        'Use asymmetric composition, editorial contrast, and memorable section rhythm.',
        'Vary scale between headline, supporting copy, and interface details.',
        'Use motion as pacing: reveal, stagger, slide, or scrub effects translated to Vanilla CSS/JS.',
        'Keep the design readable and usable even when the layout is expressive.',
        'Avoid center-stacked sameness and overly safe dashboard grids.'
      ]
    },
    softPremium: {
      label: 'Soft Premium Interface',
      source: 'soft-skill / high-end-visual-design',
      rules: [
        'Build a refined, expensive feel through material, depth, and spacing.',
        'Use soft surfaces, subtle shadow logic, fine borders, and quiet typography.',
        'Keep color controlled and avoid loud neon unless softened by context.',
        'Treat glass effects as material with border, highlight, and inner depth.',
        'Avoid cheap blur overlays, heavy gradients, and floating decoration.'
      ]
    },
    minimalistUtility: {
      label: 'Minimalist Utility',
      source: 'minimalist-skill',
      rules: [
        'Prioritize utility, reading comfort, and document-like clarity.',
        'Use line, whitespace, hierarchy, and compact controls instead of many cards.',
        'Keep the palette mostly neutral with one quiet accent.',
        'Make repeated workflows fast to scan and easy to operate.',
        'Avoid ornamental UI and unnecessary visual weight.'
      ]
    },
    industrialBrutalist: {
      label: 'Industrial Brutalist',
      source: 'brutalist-skill',
      rules: [
        'Use strong structure, hard edges, visible grids, and mechanical contrast.',
        'Make type scale decisive and utilitarian, with clear labels and dense metadata.',
        'Use borders, black/white contrast, and functional color rather than soft decoration.',
        'Keep interactions physical, snappy, and legible.',
        'Avoid playful gradients, rounded softness, and generic startup polish.'
      ]
    },
    dataTool: {
      label: 'Dense Data Tool',
      source: 'stitch-skill / design-taste-frontend',
      rules: [
        'Optimize for repeated work, comparison, filtering, and fast scanning.',
        'Use compact panels, stable dimensions, clear affordances, and predictable navigation.',
        'Prefer tables, lists, segments, and status marks over marketing-style sections.',
        'Keep typography tight but readable, with strong alignment and numeric clarity.',
        'Avoid oversized hero layouts, decorative cards, and vague product storytelling.'
      ]
    },
    redesignGuard: {
      label: 'Redesign Guard',
      source: 'redesign-skill',
      rules: [
        'Preserve working behavior while upgrading visual quality.',
        'Identify generic AI patterns and replace them with purposeful layout decisions.',
        'Improve hierarchy, spacing, state feedback, and responsive stability.',
        'Keep changes scoped, testable, and compatible with existing code.',
        'Avoid redesigning unrelated areas just for novelty.'
      ]
    }
  };

  const PRESET_TASTE_PROFILE_MAP = {
    vercel: 'premiumFrontend',
    linear: 'premiumFrontend',
    stripe: 'softPremium',
    shadcn: 'minimalistUtility',
    untitled: 'premiumFrontend',
    carbon: 'dataTool',
    apple: 'softPremium',
    google: 'softPremium',
    spotify: 'premiumFrontend',
    discord: 'premiumFrontend',
    airbnb: 'softPremium',
    notion: 'minimalistUtility',
    github: 'dataTool',
    figma: 'dataTool',
    ant: 'dataTool',
    neobrutal: 'industrialBrutalist',
    awwwards: 'editorialMotion',
    glow: 'softPremium'
  };

  const CONFLICT_POLICY = [
    'Priority: security/lightweight/Vanilla constraints > VAS baseline > selected taste profile > preset direction.',
    'Preserve the preset mood while using the offline-safe system sans or system mono stack.',
    'If a preset uses loud purple/blue, preserve the intent with a calmer single accent unless the brief explicitly demands it.',
    'If a preset implies heavy libraries or complex animation frameworks, translate the idea into Vanilla CSS/JS.',
    'Treat brand clone wording as visual reference, not literal copying.'
  ];

  const OUTPUT_CONTRACT = [
    'Return practical design guidance that can become standalone HTML/CSS/JS.',
    'Name concrete layout, typography, color, spacing, motion, and component-state decisions.',
    'Avoid vague moodboard language, filler copy, and generic AI UI defaults.',
    'Keep the result light, local-file friendly, and suitable for VAS workspace/projects output.'
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

  function composeAgentPrompt(presetKey, preset, overrideProfileKey) {
    const selectedPreset = preset || {};
    const manualProfileKey = overrideProfileKey || (
      window.getManualTasteProfileKey ? window.getManualTasteProfileKey() : null
    );
    const profileKey = getTasteProfileKey(presetKey, selectedPreset, manualProfileKey);
    const profile = TASTE_PROFILES[profileKey] || TASTE_PROFILES[DEFAULT_TASTE_PROFILE];
    const presetPrompt = selectedPreset.prompt || '';

    return [
      '[VAS DESIGN STUDIO PROMPT]\nPreset: ' + presetKey + '\nTaste Profile: ' + profile.label + '\nTaste Source: ' + profile.source,
      formatRuleList('BASELINE RULES', TASTE_BASELINE.rules),
      formatRuleList('TASTE PROFILE RULES', profile.rules),
      '[PRESET DIRECTION]\n' + presetPrompt,
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
