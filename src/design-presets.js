/**
 * VAS 디자인 스튜디오 — 프리셋 데이터
 * design-controller.html에서 분리된 프리셋 정의 파일
 * 카테고리: CORE(기본 스타일), BRAND(브랜드 레퍼런스), CONCEPT(콘셉트 스타일)
 */

const PRESET_CATEGORIES = {
  core: { label: '기본 스타일 (Core)', presets: ['vercel','linear','stripe','shadcn','untitled','carbon'] },
  brand: { label: '브랜드 레퍼런스 (Brand)', presets: ['apple','google','spotify','discord','airbnb','notion','github','figma','ant'] },
  concept: { label: '콘셉트 (Concept)', presets: ['neobrutal','awwwards','glow'] }
};

const PRESETS = {
  vercel: {
    bg: '#ffffff', surface: '#ffffff', text: '#000000', primary: '#000000', border: '#eaeaea',
    rad: 6, pad: 24, bw: 1, shadow: 10, font: "'Geist Mono', 'Pretendard', monospace", speed: 0.15, ls: -0.04,
    prompt: "[Vercel Design System Reference]\n- Goal: Create a high-contrast, ultra-snappy monochrome interface inspired by precise developer tooling.\n- Font: Geist Mono or JetBrains Mono for numeric/code details, with Pretendard as the primary UI fallback.\n- Border-radius: Exact 6px, no circles.\n- Borders: 1px solid #eaeaea for clean separation, not card spam.\n- Shadows: Extremely subtle drop-shadows; hover may lift the surface -2px with restraint.\n- Primary Button: Near-black with white text, no decorative rounding.\n- Focus: Speed, minimal padding, stark contrast, and practical scanability."
  },
  linear: {
    bg: '#0b0c0f', surface: '#111318', text: '#f1f1f3', primary: '#6f7db8', border: '#242833',
    rad: 8, pad: 24, bw: 1, shadow: 20, font: "'Pretendard', 'Geist', sans-serif", speed: 0.2, ls: 0,
    prompt: "[Linear Design System Reference]\n- Goal: Create a premium, dark-mode-first productivity tool aesthetic.\n- Font: Pretendard with medium/semibold hierarchy; use mono only for technical data.\n- Colors: Off-black background, dark neutral surfaces, and one muted blue-lavender accent.\n- Borders: 1px solid neutral dark borders. Use inner shadow hints instead of glow-heavy styling.\n- Radii: 8px for cards, 4px for buttons.\n- Micro-interactions: Very subtle opacity transitions (0.2s), restrained border response on hover.\n- Focus: Deep contrast, calm accents, supreme tidiness."
  },
  stripe: {
    bg: '#f6f9fc', surface: '#ffffff', text: '#32325d', primary: '#5f6fa8', border: '#e6ebf1',
    rad: 8, pad: 32, bw: 0, shadow: 40, font: "'Pretendard', sans-serif", speed: 0.3, ls: 0,
    prompt: "[Stripe Design System Reference]\n- Goal: Create a trustworthy, high-tech fintech dashboard.\n- Font: Pretendard with clean, highly legible hierarchy.\n- Colors: Light cool grey background, white surfaces, and a muted blue accent instead of loud blue-purple.\n- Borders: Minimal visible borders. Use soft, diffuse shadows only where they clarify elevation.\n- Radii: 8px across the board.\n- Transitions: Smooth 0.3s cubic-bezier with modest lift.\n- Focus: Trust, cleanliness, whitespace, and soft depth."
  },
  apple: {
    bg: '#f5f5f7', surface: '#ffffff', text: '#1d1d1f', primary: '#0066cc', border: '#d2d2d7',
    rad: 18, pad: 32, bw: 1, shadow: 30, font: "'Pretendard', sans-serif", speed: 0.4, ls: -0.01,
    prompt: "[Apple Glass Design System Reference]\n- Goal: Premium hardware-like interface with translucent layers.\n- Font: Pretendard with thin, elegant tracking for Korean-first UI.\n- Colors: Light silver background, white surfaces, and deep charcoal text.\n- Borders: Extremely faint 1px border, paired with careful translucent material only where useful.\n- Radii: Large, continuous rounded corners (18px+).\n- Shadows: Broad, soft, very transparent drop shadows.\n- Focus: Hardware-like elegance, large typography hierarchy, and restrained glass material."
  },
  neobrutal: {
    bg: '#f0f0f0', surface: '#ffcc00', text: '#000000', primary: '#000000', border: '#000000',
    rad: 0, pad: 24, bw: 2, shadow: 0, font: "'Pretendard', sans-serif", speed: 0.1, ls: -0.05,
    prompt: "[Neo-Brutalism Design System Reference]\n- Goal: High-impact, mechanical, unpolished interface with disciplined contrast.\n- Font: Pretendard with heavy weight, or Geist Mono for labels and numeric details.\n- Colors: Light grey base with one strong accent surface, not a rainbow palette.\n- Borders: Solid near-black borders, default 2px for clean contrast.\n- Shadows: Hard near-black drop shadows where they improve physical feedback. No blur.\n- Radii: 0px. Sharp edges only.\n- Hover: Button physically translates down/right to press into the hard shadow. Speed: Snappy (0.1s)."
  },
  awwwards: {
    bg: '#e8e8e5', surface: '#e8e8e5', text: '#111111', primary: '#111111', border: '#111111',
    rad: 0, pad: 40, bw: 1, shadow: 0, font: "'Pretendard', sans-serif", speed: 0.5, ls: -0.04,
    prompt: "[Awwwards Editorial Design Reference]\n- Goal: High-end editorial gallery feel with expressive but usable composition.\n- Typography: Large scale contrast with controlled tracking. Avoid oversized type that breaks workflow readability.\n- Colors: Warm gray background, near-black text, mostly monochrome.\n- Layout: Split screens and asymmetrical grids. Avoid generic centered hero and repeated card rows.\n- Interactions: Smooth, slow reveals (0.5s+ cubic-bezier). Hover states may shift type or cursor with restraint."
  },
  untitled: {
    bg: '#f9fafb', surface: '#ffffff', text: '#101828', primary: '#58627a', border: '#eaecf0',
    rad: 8, pad: 24, bw: 1, shadow: 15, font: "'Pretendard', sans-serif", speed: 0.2, ls: 0,
    prompt: "[Untitled UI Design System Reference]\n- Goal: A reliable B2B SaaS interface without generic template habits.\n- Font: Pretendard with highly legible, neutral hierarchy.\n- Colors: Off-white background, white surfaces, dark slate text, and a muted slate accent.\n- Borders: Clean 1px borders for structure, but avoid boxing every item into a card.\n- Radii: 8px border-radius for controls and panels.\n- Shadows: Very soft, realistic shadows only where depth is needed.\n- Focus: Clarity, alignment, trustworthy enterprise feel, and efficient scanning."
  },
  shadcn: {
    bg: '#ffffff', surface: '#ffffff', text: '#09090b', primary: '#18181b', border: '#e4e4e7',
    rad: 6, pad: 20, bw: 1, shadow: 5, font: "'Pretendard', sans-serif", speed: 0.15, ls: -0.02,
    prompt: "[shadcn/ui Design System Reference]\n- Goal: Developer-centric, hyper-minimalist UI components.\n- Font: Pretendard with tight, code-first hierarchy.\n- Colors: White background, zinc/slate accents, and near-black primary.\n- Borders: 1px solid #e4e4e7. Use crisp borders for separation instead of heavy shadows.\n- Radii: Sharp 6px radius.\n- Focus: Code-first precision, stripped-down utility, and sleek developer workflow."
  },
  glow: {
    bg: '#07090b', surface: '#111418', text: '#ededed', primary: '#4fb7c5', border: '#222a30',
    rad: 12, pad: 32, bw: 1, shadow: 60, font: "'Pretendard', sans-serif", speed: 0.3, ls: 0,
    prompt: "[Glow UI Design System Reference]\n- Goal: Futuristic dark interface with controlled luminous accents.\n- Font: Pretendard with modern sans-serif hierarchy.\n- Colors: Off-black background, dark charcoal surfaces, and one muted cyan accent.\n- Borders: 1px solid dark neutral borders. Use inner border hints for material depth.\n- Shadows: Use transparent accent glows sparingly; avoid neon-heavy decoration.\n- Focus: Futuristic contrast, calm accents, and readable interface depth."
  },
  google: {
    bg: '#fffbff', surface: '#f3edf7', text: '#1c1b1f', primary: '#6f6f8f', border: '#cac4d0',
    rad: 16, pad: 24, bw: 0, shadow: 25, font: "'Pretendard', sans-serif", speed: 0.25, ls: 0,
    prompt: "[Google Material 3 Design Reference]\n- Goal: Create an Android-like Material You interface.\n- Colors: Soft pastel backgrounds, layered surface containers, and a muted adaptive accent instead of vivid purple.\n- Borders: No heavy borders. Rely on surface elevation and color fills.\n- Radii: Large, pill-like rounded corners (16px to full pill 999px for buttons).\n- Shadows: Soft elevation shadows used sparingly.\n- Focus: Accessibility, friendly rounded shapes, and distinct layer elevations."
  },
  ant: {
    bg: '#f0f2f5', surface: '#ffffff', text: '#000000', primary: '#3d6f9f', border: '#d9d9d9',
    rad: 8, pad: 24, bw: 1, shadow: 10, font: "'Pretendard', sans-serif", speed: 0.2, ls: 0,
    prompt: "[Ant Design System Reference]\n- Goal: Create a highly reliable, data-heavy enterprise dashboard.\n- Colors: Light grey background, white surfaces, and a muted functional blue accent.\n- Borders: 1px solid #d9d9d9. Use subtle, functional borders.\n- Radii: Sensible 8px default radius.\n- Shadows: Gentle hover shadows only where they clarify interactivity.\n- Focus: Information density, alignment, and enterprise reliability."
  },
  carbon: {
    bg: '#f4f4f4', surface: '#ffffff', text: '#161616', primary: '#2f5f9a', border: '#e0e0e0',
    rad: 0, pad: 32, bw: 1, shadow: 0, font: "'Geist Mono', 'Pretendard', monospace", speed: 0.15, ls: 0,
    prompt: "[IBM Carbon Design System Reference]\n- Goal: High-density, industrial, engineering-focused interface.\n- Font: Geist Mono for structured numeric/details, with Pretendard for general UI.\n- Colors: Strict grayscale with one muted functional blue accent.\n- Borders: 1px solid #e0e0e0. Rely on hard lines and grid structures.\n- Radii: 0px. No rounded corners unless usability requires it.\n- Shadows: No drop shadows. Use contrast and borders for depth.\n- Focus: Serious enterprise tools, data visualization, and industrial grid alignment."
  },
  spotify: {
    bg: '#121212', surface: '#181818', text: '#ffffff', primary: '#1ed760', border: '#4d4d4d',
    rad: 8, pad: 24, bw: 1, shadow: 20, font: "'Pretendard', sans-serif", speed: 0.2, ls: 0,
    prompt: "[Spotify Design System Reference]\n- Goal: Create a near-black immersive dark theme focused on content.\n- Colors: Deep charcoal background, dark surfaces, and pure white text.\n- Primary: Green accent used only for active states and CTAs.\n- Radii: 8px for panels, pill-shapes for buttons/navigation.\n- Focus: High contrast, content-first dark UI, and controlled vibrant accents."
  },
  discord: {
    bg: '#313338', surface: '#2b2d31', text: '#f2f3f5', primary: '#6974b8', border: '#1e1f22',
    rad: 8, pad: 16, bw: 0, shadow: 15, font: "'Pretendard', sans-serif", speed: 0.15, ls: 0,
    prompt: "[Discord Design System Reference]\n- Goal: Cozy, community-driven dark UI.\n- Colors: Soft gray-blue darks with a muted indigo accent.\n- Borders: Mostly borderless, relying on subtle background shifts for elevation.\n- Radii: 8px default, rounded elements for avatars/icons.\n- Focus: Friendly, legible dense information and community workflow."
  },
  airbnb: {
    bg: '#ffffff', surface: '#ffffff', text: '#222222', primary: '#ff385c', border: '#dddddd',
    rad: 12, pad: 24, bw: 1, shadow: 15, font: "'Pretendard', sans-serif", speed: 0.25, ls: -0.02,
    prompt: "[Airbnb Design System Reference]\n- Goal: Trustworthy, highly legible, welcoming consumer UI.\n- Colors: White background, warm red accent, and near-black text.\n- Borders: Very light gray; use soft shadows only where elevation is meaningful.\n- Radii: Friendly 12px corners.\n- Focus: Large readable typography, warm whitespace, and inviting consumer flow."
  },
  notion: {
    bg: '#ffffff', surface: '#f7f7f5', text: '#37352f', primary: '#2383e2', border: '#e9e9e7',
    rad: 4, pad: 16, bw: 1, shadow: 5, font: "'Pretendard', sans-serif", speed: 0.15, ls: 0,
    prompt: "[Notion Design System Reference]\n- Goal: Minimalist, document-driven productivity workspace.\n- Colors: White/off-white backgrounds and soft black text.\n- Borders: Extremely subtle borders.\n- Radii: Small, tight 4px corners.\n- Focus: Document-like canvas, high utility, and quiet information hierarchy."
  },
  github: {
    bg: '#0d1117', surface: '#161b22', text: '#c9d1d9', primary: '#238636', border: '#30363d',
    rad: 6, pad: 16, bw: 1, shadow: 0, font: "'Pretendard', 'Geist Mono', sans-serif", speed: 0.15, ls: 0,
    prompt: "[GitHub Design System Reference]\n- Goal: Developer-centric dark mode.\n- Colors: Very dark blue-gray, success green accent, and clear text contrast.\n- Borders: Distinct 1px borders to separate dense information.\n- Radii: Classic 6px.\n- Focus: Information density, Git logic, and functional developer workflow."
  },
  figma: {
    bg: '#1e1e1e', surface: '#2c2c2c', text: '#ffffff', primary: '#3e8fb8', border: '#444444',
    rad: 2, pad: 12, bw: 1, shadow: 5, font: "'Pretendard', sans-serif", speed: 0.1, ls: 0,
    prompt: "[Figma Design System Reference]\n- Goal: A compact design tool UI interface.\n- Colors: Neutral dark grays with a muted tool-blue accent.\n- Borders: Strict 1px panel borders.\n- Radii: Tiny 2px corners to maximize workspace area.\n- Focus: UI that gets out of the way of content, with compact toolbars and clear panels."
  }
};
