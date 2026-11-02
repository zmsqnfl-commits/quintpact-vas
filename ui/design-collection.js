/** Ten original compositions; all controls and typography remain native HTML. */
(function (global) {
  'use strict';
  const image = (name, alt, cls = '') => `<img class="nc-image ${cls}" src="assets/designs/${name}.png" alt="${alt}" decoding="async">`;
  const header = (brand, note) => `<header class="nc-header"><strong>${brand}</strong><span>${note}</span></header>`;
  const action = (label) => `<button type="button" class="p-btn nc-action" data-reveal aria-expanded="false" aria-controls="ncDetail">${label}<span aria-hidden="true">↗</span></button>`;
  const detail = (title, body) => `<section class="nc-detail" id="ncDetail" tabindex="-1" hidden><h3>${title}</h3><p>${body}</p></section>`;
  const rows = (items) => items.map((item, i) => `<div class="nc-row"><span>0${i + 1}</span><strong>${item[0]}</strong><small>${item[1]}</small><b aria-hidden="true">↗</b></div>`).join('');
  const pause = '<button type="button" class="nc-pause" data-pause aria-pressed="false">모션 일시정지</button>';
  const templates = {
    bentoStudio: () => header('moyo®', 'Independent minds. Shared ideas.') + `
      <div class="nc-bento-grid">
        <section class="nc-bento-title"><small>DESIGN THAT FEELS DIFFERENT</small><h2>Make<br>things<br><em>matter.</em></h2>${action('Explore our work')}</section>
        <figure class="nc-bento-art">${image('bento', '분홍 원과 검은 물결, 크림색 줄무늬의 추상 그래픽')}<figcaption>PLAY IS A PRACTICE. ↗</figcaption></figure>
        <section class="nc-checklist"><small>A LITTLE MOMENTUM</small><h3>Good things<br>in the making.</h3><label><input type="checkbox" checked> Find the spark</label><label><input type="checkbox"> Make a little mess</label><label><input type="checkbox"> Bring it to life</label></section>
        <div class="nc-bento-flower" aria-hidden="true">✳<small>Stay curious.</small></div>
        <section class="nc-bento-projects"><small>RECENT EXPLORATIONS</small>${rows([['Bloom','Identity / 2026'],['Common ground','Digital / 2026']])}</section>
        <div class="nc-bento-hello">Have a wild idea?<strong>Say<br>hello. ↗</strong></div>
      </div>${detail('Selected work — Bloom', '꽃의 생장 리듬을 그래픽과 패키지에 담은 브랜드 프로젝트. 라임색 액션, 넓은 제목 모듈, 작은 작업 목록이 서로 다른 크기로 연결됩니다.')}`,
    auroraGlass: () => header('aura', 'YOUR SPACE TO THINK BEYOND') + `
      <div class="nc-aurora-layout"><section class="nc-aurora-copy"><small>A CLEARER KIND OF WORKSPACE</small><h2>Ideas, in<br>a new light.</h2><p>Room for your thoughts.<br>Space for what comes next.</p>${action('Enter your space')}</section>
        <section class="nc-glass"><div class="nc-glass-top"><span>✧ Your workspace</span><small>PERSONAL</small></div><h3>A little clarity.</h3><p>Everything you are creating, together.</p>${rows([['Brand explorations','Canvas'],['A place to begin','Note'],['September collection','Files'],['The next chapter','Canvas']])}<div class="nc-glass-foot"><span>4 spaces</span><span>All yours.</span></div></section></div>
      <div class="nc-dock"><span>▧<small>Canvas</small></span><span>≋<small>Notes</small></span><span>▱<small>Files</small></span></div>${detail('Your canvas', '아이디어를 시각화할 공간입니다. 유리 표면 뒤로 빛을 남기고, 문서와 프로젝트 이름은 충분히 진한 패널 위에서 읽도록 구성했습니다.')}`,
    clayPop: () => header('plūm', 'A playground for your imagination') + `
      <div class="nc-clay-hero"><section><small>MAKE ROOM FOR PLAY</small><h2>Small steps.<br>Big ideas.</h2><p>A little curiosity goes a long way.<br>Learn something lovely today.</p>${action('Find your first class')}</section>${image('clay', '복숭아빛 공간에 놓인 보라색 점토 헤드폰 조형')}</div>
      <div class="nc-clay-courses"><article><span class="nc-clay-symbol" aria-hidden="true"></span><small>01 / GET HANDS-ON</small><h3>Shape your world</h3><p>재료를 만지고 형태를 발견해요.</p></article><article><span class="nc-clay-symbol" aria-hidden="true"></span><small>02 / MIX IT UP</small><h3>A little colour</h3><p>좋아하는 색으로 시작해요.</p></article><article><span class="nc-clay-symbol" aria-hidden="true"></span><small>03 / FOLLOW THE FUN</small><h3>Just press play</h3><p>정답 없이 자유롭게 실험해요.</p></article></div>${detail('Shape your world', '첫 수업에서는 점토를 굴리고 구부려 작은 오브젝트를 만듭니다. 준비물: 부드러운 점토, 작업 매트, 호기심. 세 단계의 활동을 천천히 따라가세요.')}`,
    noirLuxe: () => header('MAISON NUIT', 'PARIS · COLLECTION 01') + `
      <div class="nc-noir-hero"><section><small>AN EXERCISE IN SENSATION</small><h2>The art of<br><em>after dark.</em></h2><p>A quiet presence.<br>An unforgettable impression.</p>${action('Discover the collection')}<span class="nc-noir-caption">EAU DE PARFUM / 50 ML</span></section><figure>${image('noir', '어두운 돌 위에서 금빛 조명을 받는 앰버 향수병')}<figcaption>01 — AMBRE NOCTURNE</figcaption></figure></div>
      <div class="nc-scent-notes"><span>THE COMPOSITION</span><div><small>01 / WOODY</small><strong>Santal</strong></div><div><small>02 / WARM</small><strong>Ambre</strong></div><div><small>03 / FLORAL</small><strong>Iris</strong></div></div>${detail('Ambre Nocturne', '따뜻한 앰버와 부드러운 샌들우드, 마지막에 남는 아이리스. 향의 세 층을 넓은 여백과 얇은 선으로 표현한 컬렉션입니다.')}`,
    botanicalAtelier: () => header('VERDANT', 'BOTANICAL CARE · SLOWER LIVING') + `
      <div class="nc-botanical-hero"><section><small>LESS, BUT MORE MEANINGFUL.</small><h2>Rooted<br>in <em>nature.</em></h2><p>Thoughtfully made rituals.<br>For skin, and a softer everyday.</p>${action('Explore the rituals')}<div class="nc-botanical-seal" aria-hidden="true">✳<span>GROWN WITH CARE</span></div></section><figure>${image('botanical', '햇빛과 꽃 사이에 놓인 초록색 보태니컬 케어 제품')}<figcaption>A LITTLE CLOSER TO NATURE.</figcaption></figure></div>
      <div class="nc-botanical-notes"><span>01<br><strong>Botanical oils</strong></span><span>02<br><strong>Daily rituals</strong></span><span>03<br><strong>Slow essentials</strong></span></div>${detail('The morning ritual', '세안 후 오일 한 방울을 손바닥에서 데워 천천히 펴 바르는 일상. 식물 사진은 여백 있는 아치 안에 두고, 사용 순서는 간결한 문장으로 보여줍니다.')}`,
    retroSunset: () => header('GOOD DAYS', 'MUSIC / FOOD / GOOD COMPANY') + `
      <div class="nc-retro-hero"><section><small>AN ALL-DAY KIND OF FEELING</small><h2>TAKE<br>IT SLOW.</h2><p>More sunshine. More good records.<br>A little less hurry.</p>${action('See the lineup')}</section><div class="nc-retro-art" aria-hidden="true"><div class="nc-sunset"></div><div class="nc-vinyl"><span>GOOD<br>DAYS</span></div><b>EST. 1978<br>REIMAGINED, 2026</b></div></div>
      <div class="nc-retro-band">SUNSHINE ✳ GOOD RECORDS ✳ BETTER COMPANY</div><section class="nc-retro-lineup"><h3>All day. Your way.</h3>${rows([['12:00 / Slow mornings','Soul & coffee'],['16:00 / Golden hour','Live sessions'],['20:00 / One more record','Vinyl selections']])}</section>${detail('Golden hour — Live sessions', '해가 기울 무렵 시작하는 어쿠스틱 세션. 오렌지 아치와 레코드 원형을 반복하고 시간표는 평평한 종이 위에 정렬했습니다.')}`,
    swissPoster: () => header('FORM / 26', 'INTERNATIONAL POSTER EXHIBITION') + `
      <div class="nc-swiss-poster"><span class="nc-swiss-date">24—28<br>OCT</span><h2><span>NEW</span><span>PERSPECTIVES</span></h2><div class="nc-swiss-disc" aria-hidden="true"></div><p>TYPE. CULTURE.<br>NEW WAYS OF SEEING.</p>${action('View programme')}</div>
      <section class="nc-swiss-programme">${rows([['24 / Exhibition opening','10:00 / Main hall'],['25 / Design talks','11:00 / Lecture room'],['26 / Poster workshops','14:00 / Studio'],['28 / Closing forum','16:00 / Main hall']])}</section>${detail('Poster workshops · 26 October', '타이포그래피와 단순한 기하 도형으로 포스터를 구성하는 워크숍. 제목의 크기, 정렬 축, 한 가지 강조색으로 시각적 우선순위를 만듭니다.')}`,
    cyberDeck: () => header('⌖ NEXUS', 'SIMULATION / SYSTEM ONLINE') + `
      <div class="nc-cyber-grid"><section class="nc-system"><small>SYSTEM STATUS</small><h2>SYSTEM<br>ONLINE_</h2><dl><dt>NODE ID</dt><dd>NX-7A3F</dd><dt>ENVIRONMENT</dt><dd>CYBER DECK</dd><dt>LINK STATUS</dt><dd>SIMULATED</dd></dl>${action('Open console')}</section><div class="nc-radar" aria-hidden="true">${image('globe', '', 'nc-earth')}<div class="nc-globe"><i></i><i></i><i></i><i></i><i></i></div><div class="nc-radar-orbit"></div><small>37.77° N / 122.41° W<br>LOCAL VISUAL SIMULATION</small></div><section class="nc-terminal"><small>TERMINAL</small><pre>&gt; workspace ready
&gt; loading visual modules
[ OK ] core systems
[ OK ] signal routing
[ OK ] interface layer

&gt; awaiting input_</pre><label>Preview signal <meter min="0" max="100" value="72">72%</meter></label>${pause}</section></div>
      <div class="nc-signal"><span>SIG_01 / ALPHA STREAM</span><div aria-hidden="true">⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁</div><span>72% / SIMULATED</span></div>${detail('Local console', '프리뷰 전용 콘솔입니다. 실제 기기나 네트워크에 연결하지 않습니다. 아래 버튼으로 예시 진단 결과를 확인하세요.')}<button class="nc-diagnostic" type="button" hidden>예시 진단 실행</button><p class="nc-console-output" role="status"></p>`,
    kineticType: () => header('OFFBEAT', 'INDEPENDENT CREATIVE STUDIO') + `
      <section class="nc-kinetic-hero"><h2><span>LESS</span><span>ORDINARY.</span><span>MORE YOU.</span></h2><div class="nc-kinetic-seal" aria-hidden="true">✳</div>${action('See the work')}</section>
      <div class="nc-marquee" aria-hidden="true"><div>WE MAKE CULTURE MOVE. ✳ WE MAKE CULTURE MOVE. ✳ WE MAKE CULTURE MOVE. ✳</div></div><div class="nc-motion-control">${pause}</div>
      <section class="nc-kinetic-projects">${rows([['SYNK','Identity / Sound'],['HYPERLAND','Digital / Play'],['CLUB PARALLAX','Culture / Experience'],['TYPEFUTURE','Motion / Type']])}</section>${detail('SYNK — Identity in motion', '새로운 사운드 플랫폼을 위한 굵은 글자와 빠른 리듬의 아이덴티티. 움직임을 멈춰도 프로젝트 제목과 탐색 기능은 그대로 유지됩니다.')}`,
    paperCollage: () => header('DAYBOOK', 'A JOURNAL OF QUIET DISCOVERIES') + `
      <div class="nc-collage-hero"><section><small>NOTICING THE LITTLE THINGS</small><h2>Collected<br>moments.</h2><p>A journal of quiet discoveries,<br>and the beauty found<br>in our everyday.</p>${action('Open the journal')}</section>${image('collage', '들꽃과 오래된 건물, 바다 사진을 종이테이프로 겹쳐 붙인 콜라주')}</div>
      <div class="nc-journal-index"><article><small>ISSUE 27</small><h3>Sunlit & softly spoken</h3><p>Longer days, open windows,<br>and the gentle return of light.</p></article><article><small>ISSUE 26</small><h3>Edges of summer</h3><p>Salt air, sun-warmed mornings,<br>and quiet horizons.</p></article></div>${detail('Sunlit & softly spoken', '평범한 날의 작은 장면을 모은 기록. 창가에 닿은 빛, 산책길의 들꽃, 오래된 건물의 그림자를 사진과 짧은 글로 엮었습니다.')}`
  };
  function render(root, key) {
    root.dataset.collection = key;
    root.dataset.paused = 'false';
    root.innerHTML = templates[key]();
    root.querySelector('[data-reveal]').addEventListener('click', function () {
      const panel = root.querySelector('.nc-detail');
      panel.hidden = !panel.hidden;
      this.setAttribute('aria-expanded', String(!panel.hidden));
      const diagnostic = root.querySelector('.nc-diagnostic');
      if (diagnostic) diagnostic.hidden = panel.hidden;
      if (!panel.hidden) { panel.scrollIntoView({ block: 'nearest' }); panel.focus({ preventScroll: true }); }
    });
    root.querySelector('[data-pause]')?.addEventListener('click', function () {
      const paused = root.dataset.paused !== 'true';
      root.dataset.paused = String(paused);
      this.setAttribute('aria-pressed', String(paused));
      this.textContent = paused ? '모션 재생' : '모션 일시정지';
    });
    root.querySelector('.nc-diagnostic')?.addEventListener('click', function () {
      root.querySelector('.nc-console-output').textContent = '[예시 결과] 화면 모듈 3개 준비 완료 · 외부 연결 없음';
    });
  }
  global.VASDesignCollection = Object.freeze({ has: key => Object.hasOwn(templates, key), render });
})(window);
