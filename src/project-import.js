(function () {
  'use strict';

  let step = 1;
  let selection = null;
  let report = null;
  let jobId = null;
  const localMode = VASRuntime.isAvailable();
  let importReady = localMode;
  const modeLabel = document.getElementById('modeLabel');
  modeLabel.textContent = localMode ? 'LOCAL / 확인 중' : 'WEB / ANALYZE';

  async function checkLocalCapabilities() {
    if (!localMode) return;
    const button = document.getElementById('selectFolder');
    const notice = document.getElementById('runtimeNotice');
    button.disabled = true;
    try {
      const status = await VASRuntime.request('/api/status');
      const capability = status && status.capabilities && status.capabilities.projectImport;
      importReady = !capability || capability.available === true;
      modeLabel.textContent = importReady ? 'LOCAL / FULL' : 'LOCAL / 제한 모드';
      button.disabled = !importReady;
      if (!importReady) {
        notice.textContent = capability.reason === 'python-unavailable' || capability.reason === 'python-version-unsupported'
          ? '기존 프로그램 가져오기에 Python 3.10 이상이 필요합니다. Python 설치 후 VAS를 다시 실행해 주세요.'
          : '가져오기 모듈을 사용할 수 없습니다. 배포 ZIP을 전체 압축 해제했는지 확인해 주세요.';
        notice.hidden = false;
      }
    } catch (error) {
      importReady = false;
      modeLabel.textContent = 'LOCAL / 연결 확인 필요';
      button.disabled = true;
      notice.textContent = '로컬 기능 상태를 확인하지 못했습니다. VAS를 다시 실행해 주세요.';
      notice.hidden = false;
    }
  }

  const theme = VASThemeState.init();
  document.documentElement.style.setProperty('--bg', theme.tokens.colors.background);
  document.documentElement.style.setProperty('--surface', theme.tokens.colors.surface);
  document.documentElement.style.setProperty('--text', theme.tokens.colors.text);
  document.documentElement.style.setProperty('--border', theme.tokens.colors.border);
  document.documentElement.style.setProperty('--font', theme.tokens.fontFamily);
  VASThemeState.decorateLinks(document);

  function go(next) {
    step = next;
    document.querySelectorAll('[data-step]').forEach(function (panel) {
      panel.classList.toggle('active', Number(panel.dataset.step) === step);
    });
    document.querySelectorAll('[data-nav-step]').forEach(function (item) {
      item.classList.toggle('active', Number(item.dataset.navStep) <= step);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
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
  }

  async function selectLocalFolder() {
    const value = await VASRuntime.request('/api/folder/select', { method: 'POST' });
    if (value && !value.cancelled && value.selection) displaySelection(value.selection);
  }

  async function selectWebFolder() {
    if (window.showDirectoryPicker) {
      const handle = await window.showDirectoryPicker({ mode: 'read' });
      displaySelection({ name: handle.name, path: handle.name, handle: handle });
      return;
    }
    document.getElementById('folderFallback').click();
  }

  async function walkDirectory(handle, prefix, result) {
    for await (const entry of handle.values()) {
      const relative = prefix ? prefix + '/' + entry.name : entry.name;
      if (entry.kind === 'directory') {
        if (['node_modules', '.git', '.venv', '__pycache__'].includes(entry.name)) {
          result.excluded.push(relative);
        } else {
          await walkDirectory(entry, relative, result);
        }
      } else {
        const file = await entry.getFile();
        result.files.push({ path: relative, size: file.size });
        result.totalSize += file.size;
      }
      if (result.files.length > 20000) throw new Error('웹 분석 한도(20,000개 파일)를 초과했습니다. Windows판을 이용해 주세요.');
    }
  }

  function reportFromFiles(name, files, totalSize) {
    const paths = files.map(function (item) { return item.path.toLowerCase(); });
    const stacks = [];
    if (paths.includes('package.json')) stacks.push('JavaScript/TypeScript');
    if (paths.some(function (path) { return /(^|\/)(pyproject\.toml|requirements.*\.txt|setup\.py)$/.test(path); })) stacks.push('Python');
    if (paths.some(function (path) { return /\.csproj$/.test(path); })) stacks.push('.NET');
    if (paths.includes('cargo.toml')) stacks.push('Rust');
    if (paths.includes('go.mod')) stacks.push('Go');
    if (paths.some(function (path) { return /\.html?$/.test(path); })) stacks.push('HTML');
    const secretPaths = paths.filter(function (path) { return /(^|\/)(\.env|.*\.(pem|key)|.*secret.*)$/.test(path); });
    return {
      name: name,
      fileCount: files.length,
      totalSize: totalSize,
      stack: stacks.length ? stacks.join(', ') : '자동 감지 안 됨',
      git: paths.some(function (path) { return path.startsWith('.git/'); }),
      secrets: secretPaths.length,
      largeFiles: files.filter(function (file) { return file.size > 100 * 1024 * 1024; }).length,
      reparsePoints: 0,
      risks: secretPaths.length ? ['시크릿 후보 ' + secretPaths.length + '개는 RAG와 보고서에서 제외됩니다.'] : [],
      mode: 'web-analysis'
    };
  }

  async function analyzeWeb() {
    if (selection.handle) {
      const result = { files: [], totalSize: 0, excluded: [] };
      await walkDirectory(selection.handle, '', result);
      return reportFromFiles(selection.name, result.files, result.totalSize);
    }
    const files = Array.from(document.getElementById('folderFallback').files).map(function (file) {
      return { path: file.webkitRelativePath.replace(/^[^/]+\//, ''), size: file.size };
    });
    return reportFromFiles(selection.name, files, files.reduce(function (sum, file) { return sum + file.size; }, 0));
  }

  async function analyze() {
    clearError();
    try {
      report = localMode
        ? await VASRuntime.request('/api/migrations/analyze', { method: 'POST', body: { selectionId: selection.selectionId } })
        : await analyzeWeb();
      renderReport();
      go(2);
      if (window.VASPersonalization) window.VASPersonalization.record({ type: 'navigation', source: 'project-import', payload: { action: 'analyzed', stack: report.stack, fileCount: report.fileCount } });
    } catch (error) { showError(error); }
  }

  function metric(label, value) {
    const item = document.createElement('div');
    item.className = 'metric';
    const caption = document.createElement('span');
    const strong = document.createElement('strong');
    caption.textContent = label;
    strong.textContent = value;
    item.append(caption, strong);
    return item;
  }

  function renderReport() {
    const stack = report.stack || (Array.isArray(report.stacks) ? report.stacks.join(', ') : '알 수 없음');
    const gitPresent = typeof report.git === 'object' ? Boolean(report.git.present) : Boolean(report.git);
    const secretCount = Array.isArray(report.secretFiles) ? report.secretFiles.length : Number(report.secrets || 0);
    const largeCount = Array.isArray(report.largeFiles) ? report.largeFiles.length : Number(report.largeFiles || 0);
    const skippedCount = Array.isArray(report.skipped) ? report.skipped.length : 0;
    const grid = document.getElementById('analysisGrid');
    grid.innerHTML = '';
    grid.append(
      metric('기술 스택', stack),
      metric('파일', String(report.fileCount || 0) + '개'),
      metric('크기', ((report.totalSize || 0) / 1048576).toFixed(1) + ' MB'),
      metric('Git', gitPresent ? '이력 보존' : '없음'),
      metric('시크릿 후보', String(secretCount) + '개'),
      metric('대용량 파일', String(largeCount) + '개')
    );
    const risks = [].concat(report.risks || []);
    if (secretCount) risks.push('시크릿 후보 ' + secretCount + '개는 보고서에서만 표시하고 색인하지 않습니다.');
    if (largeCount) risks.push('대용량 파일 ' + largeCount + '개를 가져오기 전에 확인하세요.');
    if (skippedCount) risks.push('안전 규칙에 따라 ' + skippedCount + '개 경로를 건너뜁니다.');
    if (report.reparsePoints) risks.push('링크/리파스 포인트 ' + report.reparsePoints + '개는 자동으로 따라가지 않습니다.');
    if (!risks.length) risks.push('즉시 차단할 위험을 찾지 못했습니다.');
    const list = document.getElementById('riskList');
    list.innerHTML = '';
    risks.forEach(function (risk) { const li = document.createElement('li'); li.textContent = risk; list.append(li); });
    document.getElementById('webNote').hidden = localMode;
    document.getElementById('configureButton').disabled = !importReady;
    document.getElementById('projectName').value = report.projectName || report.name || selection.name || 'imported-project';
  }

  function downloadReport() {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'vas-migration-analysis.json';
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function configure() {
    document.getElementById('importSummary').textContent = '백업을 만든 뒤 workspace/projects/' + document.getElementById('projectName').value + '에 검증된 복사본을 등록합니다. 원본은 유지됩니다.';
    go(3);
  }

  function configureNextAction() {
    const goal = document.getElementById('migrationGoal').value;
    const actions = {
      manage: { href: 'vas-hub.html', label: '허브에서 프로젝트 관리' },
      improve: { href: 'knowledge-search.html?q=' + encodeURIComponent('프로젝트 기능 개선 계획'), label: '개선 계획 찾기' },
      redesign: { href: 'design-controller.html', label: '디자인 스튜디오 열기' },
      upgrade: { href: 'knowledge-search.html?q=' + encodeURIComponent('기존 프로젝트 VAS 업그레이드 계획'), label: '업그레이드 계획 찾기' }
    };
    const action = actions[goal] || actions.manage;
    const link = document.getElementById('nextActionLink');
    link.href = action.href;
    link.textContent = action.label + ' →';
    VASThemeState.decorateLinks(link.parentNode);
    if (window.VASRuntime && VASRuntime.preserveTokenInLinks) VASRuntime.preserveTokenInLinks();
  }

  async function startImport() {
    clearError();
    document.getElementById('retryActions').hidden = true;
    document.getElementById('result').hidden = true;
    go(4);
    renderProgress(['백업 준비', '스테이징 복원', 'SHA-256 검증', '프로젝트 등록'], 1);
    try {
      const response = await VASRuntime.request('/api/migrations/import', {
        method: 'POST',
        body: {
          selectionId: selection.selectionId,
          projectName: document.getElementById('projectName').value.trim(),
          goal: document.getElementById('migrationGoal').value,
          createIndex: document.getElementById('createIndex').checked,
          preserveGit: true
        }
      });
      jobId = response.jobId;
      renderProgress(['백업 완료', '스테이징 완료', '무결성 통과', '프로젝트 등록 완료'], 4);
      document.getElementById('resultTitle').textContent = '가져오기가 완료됐습니다.';
      const completed = response.message || '프로젝트가 안전하게 등록되었습니다.';
      document.getElementById('resultMessage').textContent = response.warning
        ? completed + ' 안내: ' + response.warning : completed;
      configureNextAction();
      document.getElementById('result').hidden = false;
      if (window.VASPersonalization && document.getElementById('createIndex').checked) {
        const stack = report.stack || (Array.isArray(report.stacks) ? report.stacks.join(', ') : 'unknown');
        window.VASPersonalization.record({
          type: 'project_imported', source: 'project-import',
          payload: {
            stack: stack,
            goal: document.getElementById('migrationGoal').value,
            fileCount: Number(report.fileCount || 0)
          }
        });
      }
    } catch (error) {
      document.getElementById('resultTitle').textContent = '가져오기를 완료하지 못했습니다.';
      document.getElementById('retryActions').hidden = false;
      showError(error);
    }
  }

  function renderProgress(items, completed) {
    const list = document.getElementById('progressList');
    list.innerHTML = '';
    items.forEach(function (label, index) { const li = document.createElement('li'); li.textContent = (index < completed ? '완료 — ' : '대기 — ') + label; list.append(li); });
    document.getElementById('progressBar').style.width = (completed / items.length * 100) + '%';
  }

  async function rollback() {
    if (!jobId || !confirm('가져온 복사본을 롤백하시겠습니까? 원본은 영향을 받지 않습니다.')) return;
    try {
      await VASRuntime.request('/api/migrations/rollback', { method: 'POST', body: { jobId: jobId } });
      document.getElementById('resultMessage').textContent = '가져온 복사본을 롤백했습니다.';
      document.getElementById('rollbackButton').disabled = true;
    } catch (error) { showError(error); }
  }

  document.getElementById('selectFolder').addEventListener('click', function () { (localMode ? selectLocalFolder() : selectWebFolder()).catch(showError); });
  document.getElementById('folderFallback').addEventListener('change', function (event) {
    if (event.target.files.length) displaySelection({ name: event.target.files[0].webkitRelativePath.split('/')[0], path: event.target.files[0].webkitRelativePath.split('/')[0] });
  });
  document.getElementById('analyzeButton').addEventListener('click', analyze);
  document.getElementById('downloadReport').addEventListener('click', downloadReport);
  document.getElementById('configureButton').addEventListener('click', configure);
  document.getElementById('confirmCopy').addEventListener('change', function (event) { document.getElementById('importButton').disabled = !event.target.checked; });
  document.getElementById('importButton').addEventListener('click', startImport);
  document.getElementById('rollbackButton').addEventListener('click', rollback);
  document.getElementById('retryImportButton').addEventListener('click', function () { clearError(); go(3); });
  checkLocalCapabilities();
})();
