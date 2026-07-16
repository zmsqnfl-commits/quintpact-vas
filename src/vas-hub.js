(function () {
  'use strict';

  VASThemeState.init();
  VASThemeState.decorateLinks(document);

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
    if (consent === 'unset' || consent === null) document.getElementById('privacyDialog').showModal();
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
        row.append(copy, open);
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
