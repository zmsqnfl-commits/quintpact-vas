#!/usr/bin/env node
// Builds docs/STYLES.md from ui/design-presets.js so chat lists and ui/style-preview.html share one numbering.
// Usage: node scripts/build-style-list.cjs        (write)
//        node scripts/build-style-list.cjs --check (exit 1 when docs/STYLES.md is stale)
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const SOURCE = path.join(ROOT, 'ui', 'design-presets.js');
const TARGET = path.join(ROOT, 'docs', 'STYLES.md');
const FONT_FILES = {
  'Bricolage Grotesque': 'BricolageGrotesque.ttf',
  'DM Serif Display': 'DMSerifDisplay.ttf',
  'Space Grotesk': 'SpaceGrotesk.ttf',
  Anton: 'Anton-Regular.ttf',
  Caprasimo: 'Caprasimo-Regular.ttf',
  'Cormorant Garamond': 'CormorantGaramond.ttf'
};

function loadPresets() {
  const context = { VASStorage: { SYSTEM_SANS: 'system-ui, sans-serif', SYSTEM_MONO: 'ui-monospace, monospace' } };
  vm.createContext(context);
  const code = fs.readFileSync(SOURCE, 'utf8') +
    '\n;this.out = { PRESETS, PRESET_DESCRIPTIONS, VAS_PRESET_KEYS, VAS_STYLE_ORDER };';
  vm.runInContext(code, context, { filename: SOURCE });
  return context.out;
}

function displayName(key, preset) {
  if (preset.label) return preset.label;
  const match = String(preset.prompt || '').match(/^\[([^\]]+)\]/);
  return match ? match[1].replace(/ Design( System)? Reference$/i, '') : key;
}

function firstFont(stack) {
  const first = String(stack || '').split(',')[0].trim().replace(/^['"]|['"]$/g, '');
  return FONT_FILES[first] ? first : '';
}

function render() {
  const { PRESETS, PRESET_DESCRIPTIONS, VAS_PRESET_KEYS, VAS_STYLE_ORDER } = loadPresets();
  const rows = VAS_STYLE_ORDER.map((key, index) => {
    const preset = PRESETS[key];
    const font = firstFont(preset.font);
    const fontCell = font ? `${font} (\`ui/assets/fonts/${FONT_FILES[font]}\`)` : 'PC 글꼴';
    const group = VAS_PRESET_KEYS.includes(key) ? '공개' : '호환';
    const description = String(PRESET_DESCRIPTIONS[key] || '').replace(/\|/g, '/');
    return `| ${index + 1} | \`${key}\` | ${displayName(key, preset)} | ${description} | ${fontCell} | ${group} |`;
  });
  return [
    '# 스타일 목록',
    '',
    '<!-- scripts/build-style-list.cjs가 ui/design-presets.js에서 만든 파일입니다. 직접 고치지 말고 다시 만드세요. -->',
    '',
    '디자인이 정해지지 않은 새 화면에서 사용자에게 고를 거리를 보여 줄 때 이 번호를 씁니다. 같은 번호가 `ui/style-preview.html`(서버 없이 여는 바둑판 미리보기)의 타일에도 붙어 있습니다.',
    '',
    '- 채팅에는 앱 종류에 맞는 6~8개만 번호·이름·한 줄 설명으로 보여 주고, 전체는 미리보기 페이지에서 보라고 안내합니다.',
    '- 사용자가 고르면 `src/DESIGN.md`에는 번호가 아니라 **키**를 적습니다. 번호는 스타일이 늘면 뒤에 붙지만 키가 더 확실합니다.',
    '- 글꼴이 적힌 스타일은 그 글꼴 파일과 같은 이름의 `-OFL.txt` 라이선스 파일을 함께 앱의 `src/` 안으로 복사해 씁니다. 영문 글꼴이라 한글은 PC 글꼴로 보입니다.',
    '',
    '| 번호 | 키 | 이름 | 한 줄 설명 | 제목 글꼴 | 묶음 |',
    '|---:|---|---|---|---|---|',
    ...rows,
    ''
  ].join('\n');
}

const text = render();
if (process.argv.includes('--check')) {
  const current = fs.existsSync(TARGET) ? fs.readFileSync(TARGET, 'utf8').replace(/\r\n/g, '\n') : '';
  if (current !== text) {
    console.error('docs/STYLES.md is stale: run node scripts/build-style-list.cjs');
    process.exit(1);
  }
  console.log('Style list verified');
} else {
  fs.writeFileSync(TARGET, text, 'utf8');
  console.log('Wrote docs/STYLES.md');
}
