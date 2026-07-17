(function () {
  'use strict';

  let step = 1;
  let selection = null;
  let preview = null;
  let webFiles = [];
  let migrationReport = null;
  let jobId = null;
  let previewKind = 'json';
  const localMode = VASRuntime.isAvailable();
  const initialProjectId = new URLSearchParams(location.search).get('projectId');
  const modeLabel = document.getElementById('modeLabel');

  VASProjectContext.init();
  VASThemeState.init();
  VASThemeState.decorateLinks(document);
  modeLabel.textContent = localMode ? 'WINDOWS / JSON + ZIP' : 'WEB / JSON';

  function go(next) {
    step = next;
    document.querySelectorAll('[data-step]').forEach(function (panel) { panel.classList.toggle('active', Number(panel.dataset.step) === step); });
    document.querySelectorAll('[data-nav-step]').forEach(function (item) {
      const number = Number(item.dataset.navStep);
      item.classList.toggle('active', number <= step);
      if (number === step) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
    });
    document.querySelector('.workspace').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function showError(error) {
    const box = document.getElementById('errorBox');
    box.textContent = error && error.message ? error.message : String(error);
    box.hidden = false;
  }

  function clearError() { document.getElementById('errorBox').hidden = true; }

  function displaySelection(value) {
    selection = value;
    document.getElementById('selectedPath').textContent = value.path || value.name;
    document.getElementById('selection').hidden = false;
    document.getElementById('analyzeButton').disabled = false;
    document.getElementById('projectName').value = value.name || 'existing-project';
  }

  async function checkLocalCapabilities() {
    if (!localMode) {
      document.getElementById('configureButton').disabled = true;
      document.getElementById('sourceModeLabel').hidden = true;
      return;
    }
    const button = document.getElementById('selectFolder');
    const notice = document.getElementById('runtimeNotice');
    try {
      const status = await VASRuntime.request('/api/status');
      const capability = status && status.capabilities && status.capabilities.projectImport;
      if (capability && capability.available === false) {
        button.disabled = true;
        notice.textContent = 'AI 전달팩에는 Python 3.10 이상이 필요합니다. Python 설치 후 VAS를 다시 실행해 주세요.';
        notice.hidden = false;
      }
    } catch (error) {
      button.disabled = true;
      notice.textContent = '로컬 기능에 연결하지 못했습니다. VAS를 다시 실행해 주세요.';
      notice.hidden = false;
    }
  }

  async function loadRegisteredProject() {
    if (!initialProjectId || !localMode) return;
    try {
      const data = await VASRuntime.request('/api/projects');
      const project = (data.projects || []).find(function (item) { return item.projectId === initialProjectId; });
      if (!project) return;
      displaySelection({ projectId: project.projectId, name: project.name, path: 'VAS 프로젝트 / ' + project.name });
      document.getElementById('selectFolder').hidden = true;
      document.getElementById('configureButton').disabled = true;
    } catch (error) { showError(error); }
  }

  async function selectLocalFolder() {
    const value = await VASRuntime.request('/api/folder/select', { method: 'POST' });
    if (value && !value.cancelled && value.selection) displaySelection(value.selection);
  }

  async function walkDirectory(handle, prefix, result) {
    const excluded = new Set(['.git', '.hg', '.svn', '.cache', '.venv', '__pycache__', 'build', 'coverage', 'dist', 'node_modules', 'target', 'test-results']);
    for await (const entry of handle.values()) {
      const relative = prefix ? prefix + '/' + entry.name : entry.name;
      if (entry.kind === 'directory') {
        if (!excluded.has(entry.name.toLowerCase())) await walkDirectory(entry, relative, result);
      } else {
        const file = await entry.getFile();
        result.push({ path: relative, size: file.size });
      }
      if (result.length > 20000) throw new Error('웹 분석 한도(20,000개 파일)를 초과했습니다. Windows판을 이용해 주세요.');
    }
  }

  async function selectWebFolder() {
    if (window.showDirectoryPicker) {
      const handle = await window.showDirectoryPicker({ mode: 'read' });
      webFiles = [];
      await walkDirectory(handle, '', webFiles);
      displaySelection({ name: handle.name, path: handle.name });
      return;
    }
    document.getElementById('folderFallback').click();
  }

  function requestBody(extra) {
    const identity = selection.projectId ? { projectId: selection.projectId } : { selectionId: selection.selectionId };
    return Object.assign(identity, {
      projectName: document.getElementById('projectName').value.trim() || selection.name,
      task: { request: document.getElementById('taskRequest').value.trim(), constraints: [], acceptanceCriteria: [] }
    }, extra || {});
  }

  async function analyze() {
    clearError();
    document.getElementById('analyzeButton').disabled = true;
    document.getElementById('analyzeButton').textContent = '분석 중…';
    try {
      preview = localMode
        ? await VASRuntime.request('/api/handoffs/preview', { method: 'POST', body: requestBody() })
        : await VASAgentHandoffWeb.build(selection.name, webFiles, document.getElementById('taskRequest').value);
      renderAnalysis();
      renderCandidates();
      renderPreview();
      go(2);
      if (window.VASPersonalization) VASPersonalization.record({ type: 'navigation', source: 'project-import', payload: { action: 'handoff_analyzed', fileCount: preview.document.analysis.stats.fileCount } });
    } catch (error) { showError(error); }
    finally {
      document.getElementById('analyzeButton').disabled = false;
      document.getElementById('analyzeButton').textContent = '안전하게 분석하기 →';
    }
  }

  function metric(label, value) {
    const item = document.createElement('div'); item.className = 'metric';
    const caption = document.createElement('span'); caption.textContent = label;
    const strong = document.createElement('strong'); strong.textContent = value;
    item.append(caption, strong); return item;
  }

  function renderAnalysis() {
    const data = preview.document;
    const stats = data.analysis.stats;
    const grid = document.getElementById('analysisGrid'); grid.innerHTML = '';
    grid.append(
      metric('기술 스택', data.analysis.stacks.join(', ') || '자동 감지 안 됨'),
      metric('파일', stats.fileCount.toLocaleString('ko-KR') + '개'),
      metric('전체 크기', (stats.totalBytes / 1048576).toFixed(1) + ' MB'),
      metric('Git', data.analysis.git.present ? '있음 / 내용 제외' : '없음'),
      metric('비밀값 후보', data.security.secretCandidates + '개 / 제외'),
      metric('전달 방식', localMode ? 'JSON 또는 검토 ZIP' : '내용 없는 JSON')
    );
    const risks = [];
    if (data.security.secretCandidates) risks.push('비밀값 후보 ' + data.security.secretCandidates + '개는 전달 목록에서 제외했습니다.');
    (data.inventory.excluded || []).forEach(function (item) { if (item.reason !== 'secret') risks.push(item.reason + ' 항목 ' + item.count + '개를 안전 규칙에 따라 건너뛰었습니다.'); });
    (data.security.warnings || []).forEach(function (warning) { risks.push(warning); });
    if (!risks.length) risks.push('차단할 위험을 찾지 못했습니다. 원본 파일은 실행하거나 변경하지 않았습니다.');
    const list = document.getElementById('riskList'); list.innerHTML = '';
    risks.forEach(function (risk) { const li = document.createElement('li'); li.textContent = risk; list.append(li); });
    document.getElementById('webNote').hidden = localMode;
  }

  function renderCandidates() {
    const list = document.getElementById('candidateFiles'); list.innerHTML = '';
    (preview.candidateFiles || []).forEach(function (file) {
      const label = document.createElement('label');
      const input = document.createElement('input'); input.type = 'checkbox'; input.value = file.path; input.name = 'approvedFile';
      const name = document.createElement('span'); name.textContent = file.path;
      const size = document.createElement('small'); size.textContent = Math.max(1, Math.ceil(file.sizeBytes / 1024)) + ' KB';
      label.append(input, name, size); list.append(label);
    });
  }

  function currentPrompt() { return VASAgentHandoffWeb.prompt(preview.document, document.getElementById('provider').value); }

  function renderPreview() {
    const content = previewKind === 'prompt' ? currentPrompt() : JSON.stringify(preview.document, null, 2);
    document.getElementById('previewContent').textContent = content;
    document.getElementById('previewStatus').textContent = preview.document.analysis.stats.fileCount + '개 파일 분석됨';
    document.querySelectorAll('[data-preview]').forEach(function (button) { button.classList.toggle('active', button.dataset.preview === previewKind); });
  }

  function selectedFiles() {
    return Array.from(document.querySelectorAll('input[name="approvedFile"]:checked')).map(function (input) { return input.value; });
  }

  function saveBlob(blob, name) {
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = name; link.click(); URL.revokeObjectURL(link.href);
  }

  async function downloadPackage(format) {
    clearError();
    try {
      if (!localMode) {
        VASAgentHandoffWeb.save(preview.document, 'VAS-AI-HANDOFF.json');
      } else {
        const mode = format === 'reviewed-zip' ? 'reviewed-source' : 'metadata';
        const files = mode === 'reviewed-source' ? selectedFiles() : [];
        if (mode === 'reviewed-source' && !files.length) throw new Error('함께 보낼 파일을 1개 이상 직접 선택해 주세요.');
        const blob = await VASRuntime.download('/api/handoffs/export', { method: 'POST', body: requestBody({ mode: mode, format: format, snapshotId: preview.snapshotId, approvedFiles: files }) });
        saveBlob(blob, format === 'reviewed-zip' ? 'VAS-AI-SOURCE.zip' : 'VAS-AI-HANDOFF.json');
      }
      let copyNote = ' 프롬프트도 복사했습니다.';
      try { await copyPrompt(false); } catch (copyError) { copyNote = ' 자동 복사를 사용할 수 없어 오른쪽 PROMPT에서 직접 복사해 주세요.'; }
      document.getElementById('resultMessage').textContent = (format === 'reviewed-zip' ? '검토한 소스 발췌와 JSON을 ZIP으로 저장했습니다.' : 'AI가 읽을 분석 JSON을 저장했습니다.') + copyNote;
      go(4);
    } catch (error) { showError(error); }
  }

  async function copyPrompt(showFeedback) {
    await VASAgentHandoffWeb.copy(currentPrompt());
    if (showFeedback !== false) {
      const button = document.getElementById('copyPrompt'); const old = button.textContent;
      button.textContent = '복사됨 ✓'; setTimeout(function () { button.textContent = old; }, 1400);
    }
  }

  async function configureMigration() {
    if (!localMode || !selection.selectionId) return;
    clearError();
    try {
      migrationReport = await VASRuntime.request('/api/migrations/analyze', { method: 'POST', body: { selectionId: selection.selectionId } });
      document.getElementById('importSummary').textContent = '백업 후 workspace/projects/' + document.getElementById('projectName').value + '에 검증된 복사본을 등록합니다.';
      go(3); document.getElementById('advancedMigration').open = true;
    } catch (error) { showError(error); }
  }

  function renderProgress(items, completed) {
    document.getElementById('migrationProgress').hidden = false;
    const list = document.getElementById('progressList'); list.innerHTML = '';
    items.forEach(function (label, index) { const li = document.createElement('li'); li.textContent = (index < completed ? '완료 — ' : '대기 — ') + label; list.append(li); });
    document.getElementById('progressBar').style.width = (completed / items.length * 100) + '%';
  }

  async function startImport() {
    clearError(); go(4); renderProgress(['백업 준비', '안전 복사', 'SHA-256 검증', '프로젝트 등록'], 1);
    try {
      const goal = document.getElementById('migrationGoal').value;
      const response = await VASRuntime.request('/api/migrations/import', { method: 'POST', body: { selectionId: selection.selectionId, projectName: document.getElementById('projectName').value.trim(), goal: goal, createIndex: document.getElementById('createIndex').checked, preserveGit: true } });
      jobId = response.jobId; renderProgress(['백업 완료', '안전 복사 완료', '무결성 통과', '프로젝트 등록 완료'], 4);
      document.getElementById('resultTitle').textContent = '프로젝트 복사·등록이 끝났습니다.';
      document.getElementById('resultMessage').textContent = response.message || '원본은 그대로 유지되었습니다.';
      document.getElementById('rollbackButton').hidden = false;
      const project = response.project || { projectId: response.jobId, sourceType: 'imported', goal: goal, stage: 'ready' };
      VASProjectContext.set(project);
      const link = document.getElementById('nextActionLink'); link.hidden = false; link.href = 'project-import.html?projectId=' + encodeURIComponent(project.projectId); link.textContent = '등록 프로젝트 전달팩 만들기';
      VASThemeState.decorateLinks(link.parentNode);
    } catch (error) { document.getElementById('resultTitle').textContent = '복사·등록을 완료하지 못했습니다.'; document.getElementById('retryImportButton').hidden = false; showError(error); }
  }

  async function rollback() {
    if (!jobId || !confirm('가져온 복사본을 롤백하시겠습니까? 원본은 영향을 받지 않습니다.')) return;
    try { await VASRuntime.request('/api/migrations/rollback', { method: 'POST', body: { jobId: jobId } }); document.getElementById('resultMessage').textContent = '가져온 복사본을 롤백했습니다.'; document.getElementById('rollbackButton').disabled = true; }
    catch (error) { showError(error); }
  }

  document.getElementById('selectFolder').addEventListener('click', function () { (localMode ? selectLocalFolder() : selectWebFolder()).catch(showError); });
  document.getElementById('changeFolder').addEventListener('click', function () { (localMode ? selectLocalFolder() : selectWebFolder()).catch(showError); });
  document.getElementById('folderFallback').addEventListener('change', function (event) {
    const files = Array.from(event.target.files); if (!files.length) return;
    webFiles = files.map(function (file) { return { path: file.webkitRelativePath.replace(/^[^/]+\//, ''), size: file.size }; });
    const name = files[0].webkitRelativePath.split('/')[0]; displaySelection({ name: name, path: name });
  });
  document.getElementById('analyzeButton').addEventListener('click', analyze);
  document.getElementById('continueReview').addEventListener('click', function () { go(3); });
  document.getElementById('configureButton').addEventListener('click', configureMigration);
  document.getElementById('downloadJson').addEventListener('click', function () { downloadPackage('json'); });
  document.getElementById('exportHandoff').addEventListener('click', function () { downloadPackage(document.querySelector('input[name="handoffMode"]:checked').value === 'reviewed-source' ? 'reviewed-zip' : 'json'); });
  document.getElementById('copyPrompt').addEventListener('click', function () { copyPrompt(true).catch(showError); });
  document.getElementById('provider').addEventListener('change', renderPreview);
  document.querySelectorAll('[data-preview]').forEach(function (button) { button.addEventListener('click', function () { previewKind = button.dataset.preview; renderPreview(); }); });
  document.querySelectorAll('input[name="handoffMode"]').forEach(function (input) { input.addEventListener('change', function () { document.getElementById('sourceReview').hidden = input.value !== 'reviewed-source' || !input.checked; }); });
  document.getElementById('clearFiles').addEventListener('click', function () { document.querySelectorAll('input[name="approvedFile"]').forEach(function (input) { input.checked = false; }); });
  document.getElementById('confirmCopy').addEventListener('change', function (event) { document.getElementById('importButton').disabled = !event.target.checked; });
  document.getElementById('importButton').addEventListener('click', startImport);
  document.getElementById('rollbackButton').addEventListener('click', rollback);
  document.getElementById('retryImportButton').addEventListener('click', function () { go(3); document.getElementById('advancedMigration').open = true; });
  document.getElementById('startAgain').addEventListener('click', function () { location.reload(); });
  checkLocalCapabilities(); loadRegisteredProject();
})();
