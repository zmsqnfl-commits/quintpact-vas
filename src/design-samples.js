/** Four curated, interactive sample sites. Sample state stays in the preview only. */
(function (global) {
  'use strict';
  const profiles = { curatedEditorial: 'awwwards', curatedProduct: 'linear', curatedSaas: 'stripe', curatedKnowledge: 'notion' };
  const button = (text, target) => '<button type="button" class="p-btn" data-jump="' + target + '">' + text + ' <span aria-hidden="true">↗</span></button>';
  const photo = (file, alt, cls) => '<img class="' + cls + '" src="assets/designs/' + file + '.png" alt="' + alt + '" decoding="async">';
  function editorial() {
    return '<header class="ds-mast"><strong>FORM / FIELD</strong><nav aria-label="스튜디오 메뉴"><a href="#previewProjects">Projects</a><a href="#sampleStudio">Studio</a><a href="#sampleContact">Contact</a></nav></header>' +
      '<section class="ds-editorial-hero" id="sampleStudio"><h2>Spaces for<br>slower living.</h2><div><p>Architecture shaped by light, landscape, and everyday life.</p>' + button('Explore projects', 'previewProjects') + '</div></section>' +
      '<figure class="ds-architecture">' + photo('courtyard', '올리브 나무와 바다가 보이는 콘크리트 주택의 햇살 든 중정', 'ds-architecture-photo') + '<figcaption><span>01 / Courtyard House</span><span>Jeju, Korea · 2026</span></figcaption></figure>' +
      '<section class="ds-projects" id="previewProjects" tabindex="-1" aria-label="Selected projects">' +
      [['Courtyard House','Residence','2026','바다를 향한 열린 중정과 빛의 흐름을 따라 설계한 주거 공간.'],['Still Library','Cultural','2025','소리와 시선을 낮추고 읽는 일에 집중하도록 만든 동네 도서관.'],['Stone & Light','Retreat','2025','돌의 질감과 긴 그림자가 느린 하루를 만드는 작은 휴식처.']].map(row => '<details><summary><strong>' + row[0] + '</strong><span>' + row[1] + '</span><span>' + row[2] + ' ↗</span></summary><p>' + row[3] + '</p></details>').join('') + '</section>' +
      '<section class="ds-contact" id="sampleContact"><h3>Start a conversation.</h3><form><label for="sampleInquiry">Tell us about your project</label><input class="p-input" id="sampleInquiry" aria-label="미리보기 입력창" placeholder="어떤 공간을 생각하고 있나요?" required maxlength="500"><button class="p-btn" type="submit">Preview inquiry ↗</button><p class="ds-feedback" role="status"></p></form></section>';
  }
  const initialTasks = [
    { id: 101, title: 'Map the first visit', tag: 'Design', owner: 'AL', date: 'Sep 12', status: 'Backlog', note: '첫 방문자가 탐색부터 문의까지 이어지는 경로를 정리합니다.' },
    { id: 102, title: 'Write the product story', tag: 'Content', owner: 'SR', date: 'Sep 14', status: 'Backlog', note: '소개 문구와 핵심 메시지의 흐름을 작성합니다.' },
    { id: 103, title: 'Build the component library', tag: 'Engineering', owner: 'KM', date: 'Sep 10', status: 'In progress', note: '여러 화면과 테마에서 일관되게 쓰는 컴포넌트를 만듭니다.' },
    { id: 104, title: 'Polish the mobile navigation', tag: 'Design', owner: 'AL', date: 'Sep 13', status: 'In progress', note: '작은 화면에서 메뉴 이동과 키보드 탐색을 확인합니다.' },
    { id: 105, title: 'Define our visual language', tag: 'Design', owner: 'SR', date: 'Sep 06', status: 'Done', note: '색상, 글꼴과 간격을 하나의 언어로 정리했습니다.' },
    { id: 106, title: 'Prototype the onboarding', tag: 'Design', owner: 'KM', date: 'Sep 08', status: 'Done', note: '처음 시작하는 흐름을 프로토타입으로 확인했습니다.' }
  ];
  function product() {
    return '<div class="ds-workspace"><aside class="ds-sidebar"><strong class="ds-orbit-brand">◯ ORBIT</strong><label class="ds-search">작업 검색<input type="search" data-task-search placeholder="Search tasks" aria-label="작업 검색"></label><small>WORKSPACE</small><button type="button" data-owner="all" aria-pressed="true">▦ All projects</button><button type="button" data-owner="AL" aria-pressed="false">◉ My tasks</button><div class="ds-team"><small>TEAM</small><p><b>AL</b> Alex Lee</p><p><b>KM</b> Kai Morgan</p><p><b>SR</b> Sam Rivera</p></div></aside>' +
      '<section class="ds-work-main"><div class="ds-crumb">Workspace <span>/</span> Website launch</div><header class="ds-project-heading"><div><h2>Website launch</h2><p>A considered home for our next chapter.</p></div><button type="button" class="p-btn" data-new-task>＋ New task</button></header><div class="ds-progress"><span data-progress-label></span><progress max="6" value="2" aria-label="완료 작업 비율"></progress><span>AL · KM · SR</span></div>' +
      '<div class="ds-filters" role="group" aria-label="작업 분류">' + ['All tasks','Design','Engineering'].map((label,i) => '<button type="button" data-filter="' + (i ? label : 'all') + '" aria-pressed="' + !i + '">' + label + '</button>').join('') + '</div><div class="ds-board" aria-live="polite"></div>' +
      '<form class="ds-new-task" hidden><label>작업 이름<input class="p-input" name="taskTitle" required maxlength="100" placeholder="새 작업을 입력하세요"></label><button type="submit" class="p-btn">Add task</button><button type="button" data-cancel-task>Cancel</button></form>' +
      '<section class="ds-task-detail" tabindex="-1" aria-label="작업 상세"><div><small data-task-id></small><h3 data-task-title></h3><p data-task-note></p></div><label>Status<select data-task-status aria-label="작업 상태"><option>Backlog</option><option>In progress</option><option>Done</option></select></label></section><footer class="ds-work-footer"><span>Next milestone</span><strong>Design handoff</strong><span>Sep 18 · Sample workspace</span></footer></section></div>';
  }
  function saas() {
    return '<header class="ds-mast ds-relay-mast"><strong>relay.</strong><nav aria-label="서비스 메뉴"><a href="#sampleProduct">Product</a><a href="#samplePricing">Pricing</a><a href="#samplePricing">See plans ↗</a></nav></header><section class="ds-saas-hero" id="sampleProduct"><div class="ds-saas-copy"><h2>Make room<br>for growth.</h2><p>Subscriptions, invoices, and a clear view of your business. All in one calm workspace.</p>' + button('Find your plan', 'samplePricing') + '</div>' +
      '<section class="ds-billing" aria-label="구독 관리 화면 예시"><aside><strong>relay.</strong><span>▦ Overview</span><span>↻ Subscriptions</span><span>▤ Invoices</span></aside><div class="ds-billing-main"><h3>Business overview</h3><div class="ds-chart-head"><span>Monthly recurring revenue</span><small>Sample data</small></div><strong class="ds-revenue">$24,680</strong><div class="ds-chart" role="img" aria-label="샘플 월 반복 매출: 1월 8천, 2월 1만2천, 3월 1만6천, 4월 1만8천, 5월 2만1천, 6월 2만4680 달러">' + [32,48,64,72,84,98].map((height,i)=>'<div><i style="height:' + height + '%"></i><span>' + ['Jan','Feb','Mar','Apr','May','Jun'][i] + '</span></div>').join('') + '</div><div class="ds-subscriptions"><div><span>Subscription</span><span>MRR</span><span>Status</span></div>' + [['Acme Studio','$1,200'],['Northlight Co.','$640'],['Fieldwork','$320']].map(row=>'<div><strong>' + row[0] + '</strong><span>' + row[1] + '</span><span class="ds-active">Active</span></div>').join('') + '</div></div></section></section>' +
      '<section class="ds-pricing" id="samplePricing" tabindex="-1"><h3>Simple plans. More possibility.</h3><div class="ds-billing-toggle" role="group" aria-label="결제 주기"><button type="button" data-period="monthly" aria-pressed="true">Monthly</button><button type="button" data-period="yearly" aria-pressed="false">Yearly · Save 20%</button></div><div class="ds-plans">' + [['Starter',24,'Everything you need to get started.','Up to 3 users','Basic reports'],['Studio',64,'More room for your next chapter.','Up to 10 users','Advanced reports']].map(row=>'<article><div><h4>' + row[0] + '</h4><p>' + row[2] + '</p></div><div class="ds-price"><strong data-price="' + row[1] + '">$' + row[1] + '</strong><span>/mo</span></div><ul><li>' + row[3] + '</li><li>Unlimited subscriptions</li><li>' + row[4] + '</li></ul><button type="button" class="p-btn" data-plan="' + row[0] + '">Choose ' + row[0] + ' ↗</button></article>').join('') + '</div><p data-billing-note>월 결제 기준 · 샘플 요금제</p><p class="ds-feedback" role="status"></p></section><footer class="ds-relay-footer"><strong>relay.</strong><span>Built for independent teams.</span></footer>';
  }
  function knowledge() {
    return '<div class="ds-wiki"><aside class="ds-sidebar ds-wiki-sidebar"><strong>fieldnotes</strong><label class="ds-search">문서 검색<input type="search" data-doc-search placeholder="Search documents" aria-label="문서 검색"></label><nav aria-label="팀 문서">' + ['Team home','Brand guide','Product principles','Meeting notes'].map((title,i)=>'<button type="button" data-doc="' + i + '" aria-pressed="' + (i === 1) + '">' + title + '</button>').join('') + '</nav><p class="ds-no-docs" hidden>검색 결과가 없습니다.</p><small class="ds-wiki-space">Studio workspace</small></aside><section class="ds-wiki-main"><header class="ds-wiki-bar"><span>Studio / <b data-doc-name>Brand guide</b></span><span>Reading view</span></header>' + photo('fieldnotes-cover', '햇살과 나뭇가지 그림자가 드리운 아이보리 벽', 'ds-wiki-cover') +
      '<article class="ds-document"><h2 data-doc-title>A little clarity.<br>A lot of possibility.</h2><p class="ds-doc-meta">Brand guide · Updated Sep 07 · 3 contributors</p><p class="ds-doc-intro">The shared language behind everything we make.</p><aside class="ds-callout"><small>Our north star</small><strong>Make the useful feel considered.</strong></aside><div class="ds-doc-columns"><section id="sampleBeliefs" tabindex="-1"><h3>01 / What we believe</h3><p data-doc-body>좋은 디자인은 복잡한 것을 명확하게 만듭니다. 우리의 언어와 화면은 사람들의 실제 필요에서 시작합니다. 작은 선택에도 같은 기준을 담습니다.</p></section><nav aria-label="문서 목차"><small>ON THIS PAGE</small><a href="#sampleBeliefs">What we believe</a><a href="#sampleChecklist">Before we publish</a></nav></div><section id="sampleChecklist" tabindex="-1"><h3>02 / Before we publish</h3>' + ['Start with a real user need','Keep the language human','Make the next step clear'].map((text,i)=>'<label class="ds-check"><input type="checkbox"' + (!i ? ' checked' : '') + '><span>' + text + '</span></label>').join('') + '<div class="ds-check-footer"><span data-check-count>1 / 3 complete</span><button type="button" class="p-btn" data-check-all>Complete checklist ↗</button></div></section><footer class="ds-related"><button type="button" data-doc="2">Product principles ↗</button><button type="button" data-doc="3">Meeting notes ↗</button></footer></article></section></div>';
  }
  function bindProduct(root) {
    const tasks = initialTasks.map(task => ({ ...task }));
    let filter = 'all', owner = 'all', query = '', selected = 103;
    const board = root.querySelector('.ds-board');
    function draw() {
      board.replaceChildren();
      ['Backlog','In progress','Done'].forEach(status => {
        const column = document.createElement('section');
        const visible = tasks.filter(t => t.status === status && (filter === 'all' || t.tag === filter) && (owner === 'all' || t.owner === owner) && t.title.toLowerCase().includes(query));
        const heading = document.createElement('h3'); heading.textContent = status + ' (' + visible.length + ')'; column.append(heading);
        visible.forEach(task => {
          const card = document.createElement('button'); card.type = 'button'; card.className = 'ds-task'; card.dataset.task = task.id;
          card.setAttribute('aria-pressed', String(selected === task.id));
          [['small','WL-' + task.id],['strong',task.title],['em',task.tag],['span',task.owner + ' · ' + task.date]].forEach(([tag,text]) => { const el = document.createElement(tag); el.textContent = text; card.append(el); });
          card.addEventListener('click', () => { selected = task.id; draw(); root.querySelector('.ds-task-detail').focus({ preventScroll: true }); }); column.append(card);
        });
        if (!visible.length) { const empty = document.createElement('p'); empty.textContent = '표시할 작업이 없습니다.'; column.append(empty); }
        board.append(column);
      });
      const task = tasks.find(t => t.id === selected);
      root.querySelector('[data-task-id]').textContent = 'WL-' + task.id;
      root.querySelector('[data-task-title]').textContent = task.title;
      root.querySelector('[data-task-note]').textContent = task.note;
      root.querySelector('[data-task-status]').value = task.status;
      const done = tasks.filter(t => t.status === 'Done').length;
      root.querySelector('progress').max = tasks.length; root.querySelector('progress').value = done;
      root.querySelector('[data-progress-label]').textContent = Math.round(done / tasks.length * 100) + '% complete';
    }
    root.querySelectorAll('[data-filter]').forEach(el => el.addEventListener('click', () => { filter = el.dataset.filter; root.querySelectorAll('[data-filter]').forEach(b => b.setAttribute('aria-pressed', String(b === el))); draw(); }));
    root.querySelectorAll('[data-owner]').forEach(el => el.addEventListener('click', () => { owner = el.dataset.owner; root.querySelectorAll('[data-owner]').forEach(b => b.setAttribute('aria-pressed', String(b === el))); draw(); }));
    root.querySelector('[data-task-search]').addEventListener('input', e => { query = e.target.value.trim().toLowerCase(); draw(); });
    root.querySelector('[data-task-status]').addEventListener('change', e => { tasks.find(t => t.id === selected).status = e.target.value; draw(); });
    const form = root.querySelector('.ds-new-task');
    root.querySelector('[data-new-task]').addEventListener('click', () => { form.hidden = false; form.elements.taskTitle.focus(); });
    root.querySelector('[data-cancel-task]').addEventListener('click', () => { form.hidden = true; root.querySelector('[data-new-task]').focus(); });
    form.addEventListener('submit', e => { e.preventDefault(); const title = form.elements.taskTitle.value.trim(); if (!title) return; selected = 101 + tasks.length; tasks.push({ id: selected, title, tag: 'Design', owner: 'AL', date: 'Just now', status: 'Backlog', note: '샘플에서 추가한 작업입니다.' }); form.reset(); form.hidden = true; filter = 'all'; query = ''; root.querySelector('[data-task-search]').value = ''; root.querySelector('[data-filter="all"]').click(); draw(); root.querySelector('.ds-task-detail').focus(); });
    draw();
  }
  function bindKnowledge(root) {
    const docs = [
      ['Team home','A shared place.<br>A clear direction.','우리 팀의 방향과 지금 진행하는 작업을 모읍니다. 문서 한 장에서 다음 할 일까지 자연스럽게 이어집니다.'],
      ['Brand guide','A little clarity.<br>A lot of possibility.','좋은 디자인은 복잡한 것을 명확하게 만듭니다. 우리의 언어와 화면은 사람들의 실제 필요에서 시작합니다. 작은 선택에도 같은 기준을 담습니다.'],
      ['Product principles','Less noise.<br>More meaning.','사용자가 하려는 일부터 이해합니다. 필요한 정보는 가까이 두고, 결정에 도움이 되지 않는 장식은 덜어냅니다.'],
      ['Meeting notes','Good conversations.<br>Clear next steps.','월요일 디자인 리뷰: 모바일 메뉴를 단순하게 정리하고 첫 화면의 메시지를 확인했습니다. 다음 단계는 실제 사용자 흐름 검증입니다.']
    ];
    root.querySelectorAll('[data-doc]').forEach(button => button.addEventListener('click', () => {
      const doc = docs[Number(button.dataset.doc)]; root.querySelector('[data-doc-name]').textContent = doc[0]; root.querySelector('[data-doc-title]').innerHTML = doc[1]; root.querySelector('[data-doc-body]').textContent = doc[2];
      root.querySelector('.ds-doc-meta').textContent = doc[0] + ' · Updated Sep 07 · 3 contributors';
      root.querySelectorAll('.ds-sidebar [data-doc]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.doc === button.dataset.doc)));
    }));
    root.querySelector('[data-doc-search]').addEventListener('input', e => {
      let count = 0; root.querySelectorAll('.ds-sidebar [data-doc]').forEach(b => { b.hidden = !b.textContent.toLowerCase().includes(e.target.value.trim().toLowerCase()); if (!b.hidden) count++; }); root.querySelector('.ds-no-docs').hidden = count > 0;
    });
    const checks = Array.from(root.querySelectorAll('.ds-check input'));
    function count() { root.querySelector('[data-check-count]').textContent = checks.filter(c => c.checked).length + ' / 3 complete'; }
    checks.forEach(c => c.addEventListener('change', count));
    root.querySelector('[data-check-all]').addEventListener('click', () => { checks.forEach(c => { c.checked = true; }); count(); });
  }
  function render(root, profile) {
    const key = profiles[profile]; root.dataset.sample = key;
    root.innerHTML = { awwwards: editorial, linear: product, stripe: saas, notion: knowledge }[key]();
    function jump(id) { const target = root.querySelector('#' + id); if (target) { target.scrollIntoView({ block: 'nearest' }); if (!target.hasAttribute('tabindex')) target.tabIndex = -1; target.focus({ preventScroll: true }); } }
    root.querySelectorAll('[data-jump]').forEach(el => el.addEventListener('click', () => jump(el.dataset.jump)));
    root.querySelectorAll('a[href^="#"]').forEach(el => el.addEventListener('click', e => { e.preventDefault(); jump(el.getAttribute('href').slice(1)); }));
    if (key === 'linear') bindProduct(root);
    if (key === 'notion') bindKnowledge(root);
    if (key === 'awwwards') root.querySelector('form').addEventListener('submit', e => { e.preventDefault(); root.querySelector('.ds-feedback').textContent = '문의 내용 미리보기가 준비되었습니다. 샘플이므로 실제 전송하지 않습니다.'; });
    if (key === 'stripe') {
      let yearly = false, selectedPlan = '';
      function feedback() { root.querySelector('.ds-feedback').textContent = selectedPlan ? selectedPlan + ' · ' + (yearly ? '연 결제' : '월 결제') + '를 선택했습니다. 샘플이므로 결제되지 않습니다.' : ''; }
      root.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', () => {
        yearly = button.dataset.period === 'yearly'; root.querySelectorAll('[data-period]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
        root.querySelectorAll('[data-price]').forEach(el => { el.textContent = '$' + (Number(el.dataset.price) * (yearly ? .8 : 1)).toLocaleString('en-US', { maximumFractionDigits: 2 }); });
        root.querySelector('[data-billing-note]').textContent = yearly ? '연 결제 시 월 환산 금액 · Starter $230.40 / Studio $614.40 연간 · 샘플 요금제' : '월 결제 기준 · 샘플 요금제'; feedback();
      }));
      root.querySelectorAll('[data-plan]').forEach(button => button.addEventListener('click', () => { selectedPlan = button.dataset.plan; root.querySelectorAll('[data-plan]').forEach(b => b.setAttribute('aria-pressed', String(b === button))); feedback(); }));
    }
  }
  global.VASDesignSamples = Object.freeze({ has: key => Object.hasOwn(profiles, key), render });
})(window);
