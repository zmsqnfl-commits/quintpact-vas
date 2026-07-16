(function () {
  'use strict';

  const themeState = VASThemeState.init();
  const root = document.documentElement;

  function alphaColor(hex, alpha) {
    const match = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
    if (!match) return hex;
    return 'rgb(' + [match[1], match[2], match[3]].map(function (part) {
      return parseInt(part, 16);
    }).join(' ') + ' / ' + alpha + ')';
  }

  root.style.setProperty('--bg', themeState.tokens.colors.background);
  root.style.setProperty('--surface', themeState.tokens.colors.surface);
  root.style.setProperty('--text', themeState.tokens.colors.text);
  root.style.setProperty('--border', themeState.tokens.colors.border);
  root.style.setProperty('--primary', themeState.tokens.colors.primary);
  root.style.setProperty('--line', alphaColor(themeState.tokens.colors.border, '28%'));
  root.style.setProperty('--editorial-accent', themeState.preset === 'awwwards' ? '#9b6808' : themeState.tokens.colors.primary);
  root.style.setProperty('--font-sans', themeState.tokens.fontFamily);
  root.style.setProperty('--font-size', themeState.tokens.fontSize + 'px');
  root.style.setProperty('--tracking', themeState.tokens.letterSpacing + 'em');
  root.style.setProperty('--space', themeState.tokens.padding + 'px');
  root.style.setProperty('--rule-width', themeState.tokens.borderWidth + 'px');
  root.style.setProperty('--shadow-size', themeState.tokens.shadow + 'px');
  root.style.setProperty('--shadow-offset', (themeState.tokens.shadow / 3) + 'px');
  root.style.setProperty('--motion', Math.max(0.1, themeState.tokens.speed) + 's');
  root.style.setProperty('--radius', themeState.tokens.radius + 'px');
  const typeScale = themeState.tokens.fontSize / 16;
  [
    ['--type-brand', 18, 16, 22], ['--type-brand-mobile', 17, 15, 20],
    ['--type-status', 12, 11, 16], ['--type-ui', 13, 12, 18],
    ['--type-hero', 70, 52, 70], ['--type-hero-tablet', 56, 48, 60], ['--type-hero-mobile', 44, 40, 46],
    ['--type-copy', 17, 14, 20], ['--type-copy-mobile', 15, 14, 18], ['--type-micro', 11, 10, 14],
    ['--type-index', 20, 17, 26], ['--type-index-mobile', 18, 16, 22],
    ['--type-action', 22, 18, 28], ['--type-action-mobile', 18, 17, 22], ['--type-action-narrow', 17, 16, 20],
    ['--type-small', 12, 11, 15], ['--type-section', 18, 16, 22], ['--type-tool', 14, 13, 18],
    ['--type-project', 15, 13, 20], ['--type-dialog', 25, 22, 36], ['--type-dialog-mobile', 22, 20, 30]
  ].forEach(function (entry) {
    root.style.setProperty(entry[0], Math.min(entry[3], Math.max(entry[2], entry[1] * typeScale)) + 'px');
  });
  root.dataset.preset = themeState.preset;
  VASThemeState.decorateLinks(document);
  VASProjectContext.init();
  VASProjectContext.decorateLinks(document);

  function initReveals() {
    const items = Array.from(document.querySelectorAll('[data-reveal]'));
    const reducedMotion = globalThis.matchMedia && globalThis.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion || !('IntersectionObserver' in window)) {
      items.forEach(function (item) { item.classList.add('is-visible'); });
      return;
    }
    root.classList.add('motion-ready');
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -8% 0px' });
    items.forEach(function (item) { observer.observe(item); });
  }

  initReveals();

  const runtimeStatus = document.getElementById('runtimeStatus');
  const runtimeConnected = VASRuntime.isAvailable();
  runtimeStatus.dataset.connected = String(runtimeConnected);
  runtimeStatus.textContent = runtimeConnected ? '연결됨' : '웹 분석 모드';

  const onboarding = document.getElementById('onboarding');
  onboarding.hidden = VASStorage.readText('vasOnboardingDone', '') === '1';
  document.getElementById('dismissOnboarding').addEventListener('click', function () {
    VASStorage.writeText('vasOnboardingDone', '1');
    onboarding.hidden = true;
  });

  async function initPersonalization() {
    if (!window.VASPersonalization) return;
    await window.VASPersonalization.init();
    let consent = window.VASPersonalization.getConsent
      ? await window.VASPersonalization.getConsent()
      : VASStorage.readText('vasPersonalizationConsent', 'unset');
    const stored = VASStorage.readText('vasPersonalizationConsent', 'unset');
    if (consent === null && (stored === 'accepted' || stored === 'declined')) {
      consent = stored === 'accepted';
      await window.VASPersonalization.consent(consent);
    }
    if (consent === true) await loadRecommendation();
    document.getElementById('privacyRail').hidden = !(consent === 'unset' || consent === null);
  }

  async function loadRecommendation() {
    const recommendation = await window.VASPersonalization.recommend('다음 작업 추천', { limit: 3 });
    const terms = (recommendation.preferences || []).join(' ');
    if (!terms) return;
    let target = { href: 'knowledge-search.html', label: '내부 지식 검색', reason: '최근 검색 흐름을 이어서 확인해 보세요.' };
    if (/(이관|마이그|가져|import|legacy)/i.test(terms)) {
      target = { href: 'project-import.html', label: '기존 프로그램 가져오기', reason: '최근 가져오기 흐름을 이어서 진행해 보세요.' };
    } else if (/(디자인|design|theme|preset|스타일)/i.test(terms)) {
      target = { href: 'design-controller.html', label: '디자인 스튜디오', reason: '최근 디자인 선택을 바탕으로 다음 설정을 이어갈 수 있습니다.' };
    } else if (/(신청|의뢰|brief|form|project|프로젝트)/i.test(terms)) {
      target = { href: 'client-application.html', label: '새 프로젝트 신청서', reason: '최근 프로젝트 흐름을 바탕으로 요구사항 작성을 이어가세요.' };
    }
    const section = document.getElementById('nextRecommendation');
    const link = document.getElementById('recommendationLink');
    document.getElementById('recommendationTitle').textContent = target.label;
    document.getElementById('recommendationCopy').textContent = target.reason + ' 추천은 이 기기의 사용 기록만 사용합니다.';
    link.href = target.href;
    link.addEventListener('click', function () {
      window.VASPersonalization.record({ type: 'recommendation_used', source: 'hub', payload: { target: target.href } });
    }, { once: true });
    VASThemeState.decorateLinks(section);
    if (window.VASRuntime && window.VASRuntime.preserveTokenInLinks) window.VASRuntime.preserveTokenInLinks();
    section.hidden = false;
  }

  async function setConsent(value) {
    VASStorage.writeText('vasPersonalizationConsent', value ? 'accepted' : 'declined');
    document.getElementById('privacyRail').hidden = true;
    if (window.VASPersonalization && window.VASPersonalization.consent) {
      await window.VASPersonalization.consent(value);
      if (value) await loadRecommendation();
    }
  }

  document.getElementById('acceptPersonalization').addEventListener('click', function () { setConsent(true); });
  document.getElementById('declinePersonalization').addEventListener('click', function () { setConsent(false); });
  document.querySelectorAll('[data-track]').forEach(function (link) {
    link.addEventListener('click', function () {
      if (window.VASPersonalization) {
        window.VASPersonalization.record({ type: 'navigation', source: 'hub', payload: { target: link.dataset.track } });
      }
    });
  });

  async function loadProjects() {
    const list = document.getElementById('projectList');
    if (!VASRuntime.isAvailable()) return;
    try {
      const data = await VASRuntime.request('/api/projects');
      const projects = data && Array.isArray(data.projects) ? data.projects : [];
      if (!projects.length) return;
      list.innerHTML = '';
      projects.forEach(function (project) {
        const row = document.createElement('article');
        row.className = 'project-row';
        const copy = document.createElement('div');
        const title = document.createElement('h3');
        const meta = document.createElement('p');
        const goalLabels = { manage: '관리', improve: '기능 개선', redesign: '리디자인', upgrade: 'VAS 업그레이드' };
        title.textContent = project.name;
        meta.textContent = [project.sourceType === 'imported' ? '가져온 프로젝트' : '새 프로젝트', goalLabels[project.goal], project.status]
          .filter(Boolean).join(' · ');
        copy.append(title, meta);
        const actions = document.createElement('div');
        actions.className = 'project-actions';
        const continueLink = document.createElement('a');
        continueLink.href = VASProjectContext.nextHref(project);
        continueLink.dataset.vasLink = '';
        continueLink.textContent = '계속 작업';
        continueLink.addEventListener('click', function () {
          VASProjectContext.set(project);
        });
        const open = document.createElement('button');
        open.type = 'button';
        open.textContent = '폴더 열기';
        open.addEventListener('click', async function () {
          open.disabled = true;
          try {
            await VASRuntime.request('/api/projects/open', {
              method: 'POST', body: { projectId: project.projectId }
            });
            if (window.VASPersonalization) {
              window.VASPersonalization.record({
                type: 'project_opened', source: 'hub',
                payload: { sourceType: project.sourceType || 'unknown' }
              });
            }
          } catch (error) {
            meta.textContent = '폴더를 열지 못했습니다. 다시 시도해 주세요.';
          } finally {
            open.disabled = false;
          }
        });
        const exportButton = document.createElement('button');
        exportButton.type = 'button';
        exportButton.textContent = '안전 ZIP';
        exportButton.addEventListener('click', async function () {
          exportButton.disabled = true;
          try {
            const blob = await VASRuntime.download('/api/projects/export', {
              method: 'POST', body: { projectId: project.projectId }
            });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'VAS-2.6.1-handoff.zip';
            link.click();
            URL.revokeObjectURL(link.href);
          } catch (error) {
            meta.textContent = '안전 ZIP을 만들지 못했습니다. 다시 시도해 주세요.';
          } finally { exportButton.disabled = false; }
        });
        actions.append(continueLink, open, exportButton);
        row.append(copy, actions);
        VASThemeState.decorateLinks(row);
        if (window.VASRuntime && VASRuntime.preserveTokenInLinks) VASRuntime.preserveTokenInLinks();
        const continueUrl = new URL(continueLink.href, window.location.href);
        const fragments = new URLSearchParams(continueUrl.hash.replace(/^#/, ''));
        fragments.set('vasProject', project.projectId);
        continueUrl.hash = fragments.toString();
        continueLink.href = continueUrl.href;
        list.append(row);
      });
    } catch (error) {
      list.innerHTML = '<p class="empty-state"><strong>프로젝트 목록을 불러오지 못했습니다.</strong><span>잠시 후 새로고침해 주세요.</span></p>';
    }
  }

  document.getElementById('refreshProjects').addEventListener('click', loadProjects);
  initPersonalization();
  loadProjects();
})();
