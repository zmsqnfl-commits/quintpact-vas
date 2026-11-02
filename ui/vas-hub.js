(function () {
  'use strict';

  VASThemeState.init();
  const root = document.documentElement;
  root.dataset.shellPreset = 'awwwards';
  VASThemeState.decorateLinks(document);
  function mountProjectProgress() {
    const element = suffix => document.getElementById('projectProgress' + suffix);
    const panel = element('Panel'), body = element('Body'), checks = element('Checks');
    const labels = { passed: '통과', failed: '실패', 'not-run': '미실행', skipped: '건너뜀' };
    const phases = { planning: '계획', implementing: '구현', testing: '검사', reviewing: '검토',
      paused: '일시 중단', blocked: '진행 막힘', 'awaiting-request': '다음 요청 대기' };
    let generation = 0;
    function showDetails(note) {
      const details = element('Details');
      details.replaceChildren();
      function add(label, value) {
        if (!value) return;
        const title = document.createElement('dt'), text = document.createElement('dd');
        title.textContent = label;
        text.textContent = value;
        details.append(title, text);
      }
      function list(items) {
        if (items == null) return '';
        if (!Array.isArray(items) || !items.every(item => typeof item === 'string')) throw new Error('invalid progress');
        return items.join('\n');
      }
      if (note.scope != null) {
        if (typeof note.scope.objective !== 'string') throw new Error('invalid progress');
        add('합의한 목표', note.scope.objective);
        add('완료조건', list(note.scope.criteria));
      }
      add('결정 사항', list(note.decisions));
      add('남은 일', list(note.remaining));
      if (note.markdownPath != null) {
        const path = 'vas-state/progress/' + String(note.revision).padStart(6, '0') + '.md';
        if (note.markdownPath !== path) throw new Error('invalid progress');
        add('읽을 수 있는 파일', path);
      }
      details.hidden = !details.childElementCount;
    }
    async function load() {
      const request = ++generation;
      body.hidden = true;
      element('Status').textContent = '프로젝트 진행 요약을 읽고 있습니다.';
      try {
        const data = await VASRuntime.request('/api/project-progress');
        if (request !== generation) return;
        const note = data.progress;
        if (note === null) {
          element('Status').textContent = '이 프로젝트에 저장한 진행 요약이 없습니다.';
          return;
        }
        if (!note || !Number.isSafeInteger(note.revision) || note.revision < 1 ||
            !Object.hasOwn(phases, note.phase) || typeof note.summary !== 'string' || typeof note.nextStep !== 'string' ||
            !Array.isArray(note.checks) || !note.checks.every(check => check && typeof check.name === 'string' &&
              Object.hasOwn(labels, check.status))) throw new Error('invalid progress');
        element('Summary').textContent = note.summary;
        element('Next').textContent = note.nextStep;
        showDetails(note);
        checks.replaceChildren();
        for (const check of note.checks) {
          const item = document.createElement('li');
          item.textContent = check.name + ' · ' + labels[check.status];
          checks.appendChild(item);
        }
        if (!note.checks.length) {
          const item = document.createElement('li');
          item.textContent = '기록한 검사 없음';
          checks.appendChild(item);
        }
        element('Status').textContent = phases[note.phase] + ' · 프로젝트에 저장된 판본 ' + note.revision +
          '입니다. 검사 결과는 당시 작업자의 기록입니다.';
        body.hidden = false;
      } catch (_) {
        if (request === generation) element('Status').textContent =
          '진행 요약을 읽지 못했습니다. 파일과 접근 상태를 확인한 후 다시 읽어주세요.';
      }
    }
    panel.hidden = false;
    element('Reload').addEventListener('click', load);
    window.addEventListener('focus', load);
    load();
  }
  if (globalThis.VASRuntime && VASRuntime.isAvailable()) {
    VASRuntime.request('/api/status').then(function (status) {
      if (status.layout !== 'project') return;
      document.querySelector('.hero-copy p').textContent = '지금 연 폴더가 프로젝트입니다. 앱은 최상위 src/에 만들고, VAS 설정은 여기서 관리하세요.';
      VASProjectPrompt.mount();
      mountProjectProgress();
    }).catch(function () { /* The form and its original help also work offline. */ });
  }

  const hero = document.querySelector('[data-reveal]');
  const reduced = globalThis.matchMedia && globalThis.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (hero) {
    if (!reduced) root.classList.add('motion-ready');
    requestAnimationFrame(function () { hero.classList.add('is-visible'); });
  }
})();
