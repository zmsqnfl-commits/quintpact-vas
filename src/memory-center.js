(function () {
  'use strict';
  const state = VASThemeState.init();
  const root = document.documentElement;
  root.style.setProperty('--bg', state.tokens.colors.background);
  root.style.setProperty('--surface', state.tokens.colors.surface);
  root.style.setProperty('--text', state.tokens.colors.text);
  root.style.setProperty('--border', state.tokens.colors.border);
  root.style.setProperty('--font', state.tokens.fontFamily);
  VASThemeState.decorateLinks(document);

  const listRoot = document.getElementById('memoryList');
  const filter = document.getElementById('typeFilter');
  let paused = false;
  let consent = null;

  function download(name, content) {
    const blob = new Blob([content], { type: 'application/json' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = name; link.click(); URL.revokeObjectURL(link.href);
  }

  function payloadText(payload) {
    const text = JSON.stringify(payload, null, 2);
    return text.length > 700 ? text.slice(0, 700) + '\n…' : text;
  }

  async function removeEvent(id) {
    if (!confirm('이 기록을 삭제하시겠습니까? 삭제 후 추천에서도 제거됩니다.')) return;
    await VASPersonalization.delete(id); await refresh();
  }

  function render(events) {
    listRoot.innerHTML = '';
    document.getElementById('eventCount').textContent = String(events.length);
    if (!events.length) { const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = '저장된 사용 기록이 없습니다.'; listRoot.append(empty); return; }
    events.forEach(function (event) {
      const row = document.createElement('article'); row.className = 'memory-row';
      const time = document.createElement('time'); time.dateTime = event.timestamp; time.textContent = new Date(event.timestamp).toLocaleString();
      const content = document.createElement('div'); const title = document.createElement('h3'); const detail = document.createElement('pre');
      title.textContent = event.type + ' · ' + event.source; detail.textContent = payloadText(event.payload); content.append(title, detail);
      const button = document.createElement('button'); button.textContent = '삭제'; button.addEventListener('click', function () { removeEvent(event.id); });
      row.append(time, content, button); listRoot.append(row);
    });
  }

  async function refresh() {
    await VASPersonalization.init();
    paused = await VASPersonalization.pause();
    consent = await VASPersonalization.consent();
    const events = await VASPersonalization.list({ type: filter.value || undefined });
    render(events);
    document.getElementById('memoryState').textContent = !consent ? '개인화 꺼짐' : paused ? '기록 일시정지' : '기록 중';
    document.getElementById('togglePause').textContent = paused ? '기록 다시 시작' : '기록 일시정지';
    document.getElementById('togglePause').disabled = consent !== true;
    document.getElementById('toggleConsent').textContent = consent === true ? '개인화 끄기' : '개인화 켜기';
    document.getElementById('storageLocation').textContent = VASRuntime.isAvailable() ? 'Windows 사용자 로컬' : '현재 브라우저';
  }

  VASPersonalization.eventTypes.forEach(function (type) { const option = document.createElement('option'); option.value = type; option.textContent = type; filter.append(option); });
  filter.addEventListener('change', refresh);
  document.getElementById('toggleConsent').addEventListener('click', async function () {
    if (consent === true && !confirm('새 기록을 중지하시겠습니까? 기존 기록은 직접 삭제할 때까지 남습니다.')) return;
    await VASPersonalization.consent(consent !== true); await refresh();
  });
  document.getElementById('togglePause').addEventListener('click', async function () { await VASPersonalization.pause(!paused); await refresh(); });
  document.getElementById('deleteAll').addEventListener('click', async function () { if (confirm('모든 개인화 기록과 파생 선호도를 완전히 삭제하시겠습니까?')) { await VASPersonalization.clear(); await refresh(); } });
  document.getElementById('exportMemory').addEventListener('click', async function () { download('vas-personalization-memory.json', await VASPersonalization.export()); });
  document.getElementById('importMemory').addEventListener('change', async function (event) { const file = event.target.files[0]; if (!file) return; const count = await VASPersonalization.import(await file.text()); alert(count + '건을 가져왔습니다.'); await refresh(); });
  refresh();
})();
