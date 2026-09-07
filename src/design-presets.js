/**
 * VAS 디자인 스튜디오 — 프리셋 데이터
 * design-controller.html에서 분리된 프리셋 정의 파일
 * 공개 목록은 14개로 선별합니다. 이전 프리셋 데이터는 저장된 설정 호환용입니다.
 */

const PRESET_CATEGORIES = {
  collection: { label: '새 디자인 컬렉션 · 10가지', presets: ['bento','aurora','clay','noir','botanical','retro','swiss','cyber','kinetic','collage'] },
  core: { label: '추천 샘플 사이트 · 4가지', presets: ['awwwards','linear','stripe','notion'] }
};
const VAS_PRESET_KEYS = Object.freeze(Object.values(PRESET_CATEGORIES).flatMap(category => category.presets));

const SYSTEM_SANS = VASStorage.SYSTEM_SANS;
const SYSTEM_MONO = VASStorage.SYSTEM_MONO;
const DISPLAY_SANS = "'Bricolage Grotesque', " + SYSTEM_SANS;
const DISPLAY_SERIF = "'DM Serif Display', Georgia, 'Batang', serif";
const DISPLAY_SPACE = "'Space Grotesk', " + SYSTEM_SANS;

const PRESET_DESCRIPTIONS = Object.freeze({
  bento: '라벤더·라임 모듈과 그래픽을 조합한 크리에이티브 벤토',
  aurora: '오로라 빛과 반투명 유리 패널의 몰입형 워크스페이스',
  clay: '복숭아색 배경과 폭신한 3D 오브젝트의 클레이 디자인',
  noir: '블랙·샴페인 골드와 세리프를 쓰는 럭셔리 에디션',
  botanical: '보태니컬 사진과 올리브·아이보리의 자연스러운 브랜드',
  retro: '버터크림·버건디와 레코드 그래픽의 레트로 포스터',
  swiss: '코발트·버밀리언과 초대형 활자의 전시 포스터',
  cyber: '애시드 라임과 와이어프레임·터미널의 사이버 인터페이스',
  kinetic: '퍼플·옐로 대비와 움직이는 대형 타이포그래피',
  collage: '핑크 종이와 겹친 사진·테이프를 쓰는 콜라주 저널',
  vercel: '흑백 대비가 선명한 개발 도구형 디자인',
  linear: 'ORBIT · 칸반 보드와 작업 상세를 갖춘 프로젝트 관리 앱',
  stripe: 'RELAY · 매출 화면과 요금제 선택을 갖춘 구독 서비스',
  apple: '큰 글자와 넓은 여백을 쓰는 부드러운 프리미엄 디자인',
  neobrutal: '굵은 선과 강한 색으로 시선을 끄는 각진 디자인',
  awwwards: 'FORM / FIELD · 잡지처럼 큰 사진과 활자를 쓰는 건축 스튜디오',
  untitled: '읽기 쉽고 정돈된 기업용 서비스 디자인',
  shadcn: '군더더기 없이 단정한 개발자 도구형 디자인',
  glow: '어두운 배경에 은은한 빛을 쓰는 미래형 디자인',
  google: '둥근 모양과 부드러운 색을 쓰는 친근한 디자인',
  ant: '표와 정보가 많은 업무 화면에 맞는 디자인',
  carbon: '격자와 직선을 강조한 산업·기술 도구형 디자인',
  spotify: '콘텐츠가 돋보이는 선명한 어두운 디자인',
  discord: '정보가 많아도 편안하게 읽히는 커뮤니티형 디자인',
  airbnb: '따뜻한 여백과 사진 중심의 친근한 서비스 디자인',
  notion: 'FIELDNOTES · 문서 검색과 체크리스트를 갖춘 팀 위키',
  github: '코드와 변경 내역을 읽기 좋은 개발 도구형 디자인',
  figma: '도구와 작업 영역을 촘촘하게 배치한 편집기형 디자인'
});

const PRESETS = {
  bento: {
    label: 'Bento Studio', tasteProfile: 'bentoStudio',
    bg: '#e9dff5', surface: '#f8f4fc', text: '#17121f', primary: '#c8ed47', border: '#cfc2df',
    rad: 24, pad: 24, bw: 0, shadow: 0, font: DISPLAY_SANS, speed: .2, ls: -.03,
    prompt: '[Bento Studio]\nUse an irregular modular portfolio: one oversized typography tile, one original graphic, one usable checklist, a project strip and a compact contact tile. Lavender, lime, coral and black form deliberate contrasting islands. Preserve varied spans and avoid three identical summary cards.'
  },
  aurora: {
    label: 'Aurora Glass', tasteProfile: 'auroraGlass',
    bg: '#060e28', surface: '#142445', text: '#f4f7ff', primary: '#8dedff', border: '#51608b',
    rad: 24, pad: 32, bw: 1, shadow: 24, font: DISPLAY_SPACE, speed: .4, ls: -.03,
    prompt: '[Aurora Glass]\nUse a full-bleed midnight aurora image behind a left-aligned statement and an offset translucent workspace. Layer cyan-violet light with frosted borders, legible glass panels and a bottom dock. Keep the material visible between panels; use an opaque fallback when backdrop-filter is unavailable.'
  },
  clay: {
    label: 'Clay Pop', tasteProfile: 'clayPop',
    bg: '#ffcea5', surface: '#fff0dc', text: '#38132f', primary: '#913968', border: '#d79266',
    rad: 32, pad: 24, bw: 0, shadow: 24, font: DISPLAY_SANS, speed: .3, ls: -.03,
    prompt: '[Clay Pop]\nBuild a tactile creative learning screen with a lilac clay sculpture, peach backdrop, heavy rounded display type, inflated controls and softly inset course tiles. Use matched product artwork and real local interactions. Depth comes from consistent lighting, not arbitrary blur.'
  },
  noir: {
    label: 'Noir Luxe', tasteProfile: 'noirLuxe',
    bg: '#11100e', surface: '#201c17', text: '#f1e8d8', primary: '#ddc395', border: '#736044',
    rad: 0, pad: 40, bw: 1, shadow: 0, font: "'Cormorant Garamond', Georgia, 'Batang', serif", speed: .5, ls: -.02,
    prompt: '[Noir Luxe]\nCreate a luxury editorial product page: champagne serif masthead, large light serif headline, dark photographic still life, hairline rules and an open collection index. Keep the black field spacious; no generic dashboard, glass cards or gold gradients.'
  },
  botanical: {
    label: 'Botanical Atelier', tasteProfile: 'botanicalAtelier',
    bg: '#f3f0e5', surface: '#e8ecd9', text: '#273f2c', primary: '#435c32', border: '#a7b29a',
    rad: 16, pad: 32, bw: 1, shadow: 0, font: DISPLAY_SERIF, speed: .3, ls: -.02,
    prompt: '[Botanical Atelier]\nBuild an organic luxury brand composition around a tall arch of real botanical photography, olive/ivory materials and expressive serif type. Offset the image against calm copy, follow with a horizontal ritual/product band. Use actual foliage imagery rather than generic leaf icons.'
  },
  retro: {
    label: 'Retro Sunset', tasteProfile: 'retroSunset',
    bg: '#fff0c9', surface: '#f3dca9', text: '#66251f', primary: '#8f2e24', border: '#bc5b38',
    rad: 24, pad: 24, bw: 2, shadow: 0, font: "'Caprasimo', Georgia, 'Batang', serif", speed: .2, ls: -.04,
    prompt: '[Retro Sunset]\nDesign a warm music/cafe poster with chunky rounded serif type, sunset arches, vinyl record geometry and a full-width orange ticker. Below the poster use a dated event lineup. Buttercream, terracotta and burgundy create the identity; avoid a modern SaaS hero.'
  },
  swiss: {
    label: 'Swiss Poster', tasteProfile: 'swissPoster',
    bg: '#1847e8', surface: '#123bc8', text: '#fff8e8', primary: '#fff8e8', border: '#a2b6ff',
    rad: 0, pad: 32, bw: 1, shadow: 0, font: "'Anton', " + SYSTEM_SANS, speed: .2, ls: -.05,
    prompt: '[Swiss Poster]\nUse a cobalt exhibition poster with monumental compact sans type, strict asymmetric grid, vertical date, large vermilion circle and programme rows. Typography and geometry are the focal image. Preserve clear reading order when the poster collapses to mobile.'
  },
  cyber: {
    label: 'Cyber Deck', tasteProfile: 'cyberDeck',
    bg: '#080e0a', surface: '#101d15', text: '#e2f6d8', primary: '#c8ff4a', border: '#466334',
    rad: 0, pad: 24, bw: 1, shadow: 0, font: SYSTEM_MONO, speed: .2, ls: 0,
    prompt: '[Cyber Deck]\nBuild a sci-fi creative console with acid-lime line work, chamfered panels, an animated wireframe globe, local terminal interaction and horizontal signal instruments. Text labels remain legible; motion has a stop control and respects reduced motion. Never fabricate live security or financial telemetry.'
  },
  kinetic: {
    label: 'Kinetic Type', tasteProfile: 'kineticType',
    bg: '#5b24e8', surface: '#4818be', text: '#fffdf7', primary: '#e5ff55', border: '#b6a0ef',
    rad: 0, pad: 32, bw: 0, shadow: 0, font: "'Anton', " + SYSTEM_SANS, speed: .3, ls: -.05,
    prompt: '[Kinetic Type]\nMake typography the entire creative direction: giant italic headline, electric purple field, acid-yellow action, a contrasting moving type band and a sparse project index. Use actual transform animation with a pause control, no essential information dependent on animation.'
  },
  collage: {
    label: 'Paper Collage', tasteProfile: 'paperCollage',
    bg: '#f2dcd7', surface: '#fff8ed', text: '#4c302d', primary: '#704236', border: '#ba9990',
    rad: 2, pad: 24, bw: 1, shadow: 16, font: DISPLAY_SERIF, speed: .3, ls: -.02,
    prompt: '[Paper Collage]\nCreate a tactile journal with overlapping photographic prints, cream paper mattes, tape corners, modest rotation and editorial serif headlines. Follow the collage with a two-column article index. Keep text outside photos selectable and stack the prints on mobile without clipping.'
  },
  vercel: {
    bg: '#ffffff', surface: '#ffffff', text: '#000000', primary: '#000000', border: '#eaeaea',
    rad: 6, pad: 24, bw: 1, shadow: 10, font: SYSTEM_MONO, speed: 0.15, ls: -0.04,
    prompt: "[Vercel Design System Reference]\n- Goal: Create a high-contrast, ultra-snappy monochrome interface inspired by precise developer tooling.\n- Font: Use the operating-system monospace stack for numeric/code details and the system sans stack for UI text.\n- Border-radius: Exact 6px, no circles.\n- Borders: 1px solid #eaeaea for clean separation, not card spam.\n- Shadows: Extremely subtle drop-shadows; hover may lift the surface -2px with restraint.\n- Primary Button: Near-black with white text, no decorative rounding.\n- Focus: Speed, minimal padding, stark contrast, and practical scanability."
  },
  linear: {
    tasteProfile: 'curatedProduct', sample: 'linear',
    bg: '#0b0c0f', surface: '#111318', text: '#f1f1f3', primary: '#6f7db8', border: '#242833',
    rad: 8, pad: 24, bw: 1, shadow: 20, font: SYSTEM_SANS, speed: 0.2, ls: 0,
    prompt: "[Linear Design System Reference]\n- Goal: Create a premium, dark-mode-first productivity tool aesthetic.\n- Font: Use the system sans stack with medium/semibold hierarchy; use system mono only for technical data.\n- Colors: Off-black background, dark neutral surfaces, and one muted blue-lavender accent.\n- Borders: 1px solid neutral dark borders. Use inner shadow hints instead of glow-heavy styling.\n- Radii: 8px for cards, 4px for buttons.\n- Micro-interactions: Very subtle opacity transitions (0.2s), restrained border response on hover.\n- Focus: Deep contrast, calm accents, supreme tidiness."
  },
  stripe: {
    tasteProfile: 'curatedSaas', sample: 'stripe',
    bg: '#f6f9fc', surface: '#ffffff', text: '#32325d', primary: '#5f6fa8', border: '#e6ebf1',
    rad: 8, pad: 32, bw: 0, shadow: 40, font: DISPLAY_SERIF, speed: 0.3, ls: 0,
    prompt: "[Stripe Design System Reference]\n- Goal: Create a trustworthy, high-tech fintech dashboard.\n- Font: Use the system sans stack with a clean, highly legible hierarchy.\n- Colors: Light cool grey background, white surfaces, and a muted blue accent instead of loud blue-purple.\n- Borders: Minimal visible borders. Use soft, diffuse shadows only where they clarify elevation.\n- Radii: 8px across the board.\n- Transitions: Smooth 0.3s cubic-bezier with modest lift.\n- Focus: Trust, cleanliness, whitespace, and soft depth."
  },
  apple: {
    bg: '#f5f5f7', surface: '#ffffff', text: '#1d1d1f', primary: '#0066cc', border: '#d2d2d7',
    rad: 18, pad: 32, bw: 1, shadow: 30, font: SYSTEM_SANS, speed: 0.4, ls: -0.01,
    prompt: "[Apple Glass Design System Reference]\n- Goal: Premium hardware-like interface with translucent layers.\n- Font: Use the Korean-capable system sans stack with thin, elegant tracking.\n- Colors: Light silver background, white surfaces, and deep charcoal text.\n- Borders: Extremely faint 1px border, paired with careful translucent material only where useful.\n- Radii: Large, continuous rounded corners (18px+).\n- Shadows: Broad, soft, very transparent drop shadows.\n- Focus: Hardware-like elegance, large typography hierarchy, and restrained glass material."
  },
  neobrutal: {
    bg: '#f0f0f0', surface: '#ffcc00', text: '#000000', primary: '#000000', border: '#000000',
    rad: 0, pad: 24, bw: 2, shadow: 0, font: SYSTEM_SANS, speed: 0.1, ls: -0.05,
    prompt: "[Neo-Brutalism Design System Reference]\n- Goal: High-impact, mechanical, unpolished interface with disciplined contrast.\n- Font: Use heavy system sans, with system mono for labels and numeric details.\n- Colors: Light grey base with one strong accent surface, not a rainbow palette.\n- Borders: Solid near-black borders, default 2px for clean contrast.\n- Shadows: Hard near-black drop shadows where they improve physical feedback. No blur.\n- Radii: 0px. Sharp edges only.\n- Hover: Button physically translates down/right to press into the hard shadow. Speed: Snappy (0.1s)."
  },
  awwwards: {
    tasteProfile: 'curatedEditorial', sample: 'awwwards',
    bg: '#e8e8e5', surface: '#e8e8e5', text: '#111111', primary: '#111111', border: '#111111',
    rad: 0, pad: 40, bw: 1, shadow: 0, font: SYSTEM_SANS, speed: 0.5, ls: -0.04,
    prompt: "[Awwwards Editorial Design Reference]\n- Goal: High-end editorial gallery feel with expressive but usable composition.\n- Typography: Large scale contrast with controlled tracking. Avoid oversized type that breaks workflow readability.\n- Colors: Warm gray background, near-black text, mostly monochrome.\n- Layout: Split screens and asymmetrical grids. Avoid generic centered hero and repeated card rows.\n- Interactions: Smooth, slow reveals (0.5s+ cubic-bezier). Hover states may shift type or cursor with restraint."
  },
  untitled: {
    bg: '#f9fafb', surface: '#ffffff', text: '#101828', primary: '#58627a', border: '#eaecf0',
    rad: 8, pad: 24, bw: 1, shadow: 15, font: SYSTEM_SANS, speed: 0.2, ls: 0,
    prompt: "[Untitled UI Design System Reference]\n- Goal: A reliable B2B SaaS interface without generic template habits.\n- Font: Use the system sans stack with a highly legible, neutral hierarchy.\n- Colors: Off-white background, white surfaces, dark slate text, and a muted slate accent.\n- Borders: Clean 1px borders for structure, but avoid boxing every item into a card.\n- Radii: 8px border-radius for controls and panels.\n- Shadows: Very soft, realistic shadows only where depth is needed.\n- Focus: Clarity, alignment, trustworthy enterprise feel, and efficient scanning."
  },
  shadcn: {
    bg: '#ffffff', surface: '#ffffff', text: '#09090b', primary: '#18181b', border: '#e4e4e7',
    rad: 6, pad: 20, bw: 1, shadow: 5, font: SYSTEM_SANS, speed: 0.15, ls: -0.02,
    prompt: "[shadcn/ui Design System Reference]\n- Goal: Developer-centric, hyper-minimalist UI components.\n- Font: Use the system sans stack with tight, code-first hierarchy.\n- Colors: White background, zinc/slate accents, and near-black primary.\n- Borders: 1px solid #e4e4e7. Use crisp borders for separation instead of heavy shadows.\n- Radii: Sharp 6px radius.\n- Focus: Code-first precision, stripped-down utility, and sleek developer workflow."
  },
  glow: {
    bg: '#07090b', surface: '#111418', text: '#ededed', primary: '#4fb7c5', border: '#222a30',
    rad: 12, pad: 32, bw: 1, shadow: 60, font: SYSTEM_SANS, speed: 0.3, ls: 0,
    prompt: "[Glow UI Design System Reference]\n- Goal: Futuristic dark interface with controlled luminous accents.\n- Font: Use the system sans stack with a modern hierarchy.\n- Colors: Off-black background, dark charcoal surfaces, and one muted cyan accent.\n- Borders: 1px solid dark neutral borders. Use inner border hints for material depth.\n- Shadows: Use transparent accent glows sparingly; avoid neon-heavy decoration.\n- Focus: Futuristic contrast, calm accents, and readable interface depth."
  },
  google: {
    bg: '#fffbff', surface: '#f3edf7', text: '#1c1b1f', primary: '#6f6f8f', border: '#cac4d0',
    rad: 16, pad: 24, bw: 0, shadow: 25, font: SYSTEM_SANS, speed: 0.25, ls: 0,
    prompt: "[Google Material 3 Design Reference]\n- Goal: Create an Android-like Material You interface.\n- Colors: Soft pastel backgrounds, layered surface containers, and a muted adaptive accent instead of vivid purple.\n- Borders: No heavy borders. Rely on surface elevation and color fills.\n- Radii: Large, pill-like rounded corners (16px to full pill 999px for buttons).\n- Shadows: Soft elevation shadows used sparingly.\n- Focus: Accessibility, friendly rounded shapes, and distinct layer elevations."
  },
  ant: {
    bg: '#f0f2f5', surface: '#ffffff', text: '#000000', primary: '#3d6f9f', border: '#d9d9d9',
    rad: 8, pad: 24, bw: 1, shadow: 10, font: SYSTEM_SANS, speed: 0.2, ls: 0,
    prompt: "[Ant Design System Reference]\n- Goal: Create a highly reliable, data-heavy enterprise dashboard.\n- Colors: Light grey background, white surfaces, and a muted functional blue accent.\n- Borders: 1px solid #d9d9d9. Use subtle, functional borders.\n- Radii: Sensible 8px default radius.\n- Shadows: Gentle hover shadows only where they clarify interactivity.\n- Focus: Information density, alignment, and enterprise reliability."
  },
  carbon: {
    bg: '#f4f4f4', surface: '#ffffff', text: '#161616', primary: '#2f5f9a', border: '#e0e0e0',
    rad: 0, pad: 32, bw: 1, shadow: 0, font: SYSTEM_MONO, speed: 0.15, ls: 0,
    prompt: "[IBM Carbon Design System Reference]\n- Goal: High-density, industrial, engineering-focused interface.\n- Font: Use system mono for structured numeric details and system sans for general UI.\n- Colors: Strict grayscale with one muted functional blue accent.\n- Borders: 1px solid #e0e0e0. Rely on hard lines and grid structures.\n- Radii: 0px. No rounded corners unless usability requires it.\n- Shadows: No drop shadows. Use contrast and borders for depth.\n- Focus: Serious enterprise tools, data visualization, and industrial grid alignment."
  },
  spotify: {
    bg: '#121212', surface: '#181818', text: '#ffffff', primary: '#1ed760', border: '#4d4d4d',
    rad: 8, pad: 24, bw: 1, shadow: 20, font: SYSTEM_SANS, speed: 0.2, ls: 0,
    prompt: "[Spotify Design System Reference]\n- Goal: Create a near-black immersive dark theme focused on content.\n- Colors: Deep charcoal background, dark surfaces, and pure white text.\n- Primary: Green accent used only for active states and CTAs.\n- Radii: 8px for panels, pill-shapes for buttons/navigation.\n- Focus: High contrast, content-first dark UI, and controlled vibrant accents."
  },
  discord: {
    bg: '#313338', surface: '#2b2d31', text: '#f2f3f5', primary: '#6974b8', border: '#1e1f22',
    rad: 8, pad: 16, bw: 0, shadow: 15, font: SYSTEM_SANS, speed: 0.15, ls: 0,
    prompt: "[Discord Design System Reference]\n- Goal: Cozy, community-driven dark UI.\n- Colors: Soft gray-blue darks with a muted indigo accent.\n- Borders: Mostly borderless, relying on subtle background shifts for elevation.\n- Radii: 8px default, rounded elements for avatars/icons.\n- Focus: Friendly, legible dense information and community workflow."
  },
  airbnb: {
    bg: '#ffffff', surface: '#ffffff', text: '#222222', primary: '#ff385c', border: '#dddddd',
    rad: 12, pad: 24, bw: 1, shadow: 15, font: SYSTEM_SANS, speed: 0.25, ls: -0.02,
    prompt: "[Airbnb Design System Reference]\n- Goal: Trustworthy, highly legible, welcoming consumer UI.\n- Colors: White background, warm red accent, and near-black text.\n- Borders: Very light gray; use soft shadows only where elevation is meaningful.\n- Radii: Friendly 12px corners.\n- Focus: Large readable typography, warm whitespace, and inviting consumer flow."
  },
  notion: {
    tasteProfile: 'curatedKnowledge', sample: 'notion',
    bg: '#ffffff', surface: '#f7f7f5', text: '#37352f', primary: '#2383e2', border: '#e9e9e7',
    rad: 4, pad: 16, bw: 1, shadow: 5, font: SYSTEM_SANS, speed: 0.15, ls: 0,
    prompt: "[Notion Design System Reference]\n- Goal: Minimalist, document-driven productivity workspace.\n- Colors: White/off-white backgrounds and soft black text.\n- Borders: Extremely subtle borders.\n- Radii: Small, tight 4px corners.\n- Focus: Document-like canvas, high utility, and quiet information hierarchy."
  },
  github: {
    bg: '#0d1117', surface: '#161b22', text: '#c9d1d9', primary: '#238636', border: '#30363d',
    rad: 6, pad: 16, bw: 1, shadow: 0, font: SYSTEM_SANS, speed: 0.15, ls: 0,
    prompt: "[GitHub Design System Reference]\n- Goal: Developer-centric dark mode.\n- Colors: Very dark blue-gray, success green accent, and clear text contrast.\n- Borders: Distinct 1px borders to separate dense information.\n- Radii: Classic 6px.\n- Focus: Information density, Git logic, and functional developer workflow."
  },
  figma: {
    bg: '#1e1e1e', surface: '#2c2c2c', text: '#ffffff', primary: '#3e8fb8', border: '#444444',
    rad: 2, pad: 12, bw: 1, shadow: 5, font: SYSTEM_SANS, speed: 0.1, ls: 0,
    prompt: "[Figma Design System Reference]\n- Goal: A compact design tool UI interface.\n- Colors: Neutral dark grays with a muted tool-blue accent.\n- Borders: Strict 1px panel borders.\n- Radii: Tiny 2px corners to maximize workspace area.\n- Focus: UI that gets out of the way of content, with compact toolbars and clear panels."
  }
};
