/** Purpose-built offline examples. Preview copy is illustrative, never project input. */
(function (global) {
  'use strict';
  const scenes = {
    editorialMotion: {
      brand: 'FORM & FIELD', section: '독립 디자인 스튜디오', title: '좋은 생각을,<br>선명한 형태로.',
      copy: '브랜드의 본질을 발견하고, 오래 기억되는 경험을 만듭니다.',
      action: '작업 목록 보기', label: 'SELECTED WORK / 2026', type: 'editorial',
      stats: [['함께 만든 브랜드', '24', '깊이 있는 협업'], ['이어온 시간', '08', '2018 — 2026'], ['다음 이야기', '03', '새로운 프로젝트']],
      rows: [['01', '여백의 미학', '브랜드 · 패키지'], ['02', '일상의 새로운 결', '공간 · 아트 디렉션'], ['03', '생각이 자라는 곳', '디지털 경험']]
    },
    premiumFrontend: {
      brand: 'orbit', section: '워크스페이스 / 프로젝트', title: '아이디어에서<br>다음 단계로.',
      copy: '팀의 흐름을 한눈에. 오늘 중요한 일에 집중하세요.',
      action: '프로젝트 살펴보기', label: '진행 중인 프로젝트', type: 'workspace',
      stats: [['진행 중', '12', '프로젝트'], ['이번 주 완료', '28', '지난주보다 6개 더'], ['팀 목표 달성', '86%', '순조롭게 진행 중']],
      rows: [['WEB', '브랜드 웹사이트', '디자인 검토'], ['APP', '고객 앱 리뉴얼', '개발 중'], ['SYS', '디자인 시스템', '문서 정리']]
    },
    dataTool: {
      brand: 'CONTROL', section: '운영 / 작업 현황', title: '운영 현황',
      copy: '오늘의 처리 상태와 확인이 필요한 작업을 살펴보세요.',
      action: '작업 내역 보기', label: '최근 작업', type: 'data',
      stats: [['처리 완료', '1,284', '오늘 누적'], ['확인 필요', '06', '담당자 배정 대기'], ['정상 처리율', '99.2%', '최근 24시간']],
      rows: [['OP-048', '출고 요청 확인', '처리 완료'], ['OP-049', '입고 수량 검수', '진행 중'], ['OP-050', '재고 현황 집계', '검토 대기']]
    },
    minimalistUtility: {
      brand: 'folio', section: '팀 문서 / 기획', title: '생각을 모아,<br>함께 앞으로.',
      copy: '흩어진 기록이 하나의 방향이 되는 공간. 이번 프로젝트의 시작을 정리합니다.',
      action: '문서 목차 보기', label: '프로젝트 노트', type: 'document',
      stats: [['함께 쓰는 문서', '16', '공유된 지식'], ['열린 논의', '04', '의견을 기다려요'], ['참여한 동료', '08', '함께 만드는 기록']],
      rows: [['01', '우리가 해결하려는 문제', '기획 노트'], ['02', '사용자의 하루 이해하기', '리서치'], ['03', '다음 실험과 확인할 것', '실행 계획']]
    },
    softPremium: {
      brand: 'still.', section: '오롯이 나를 위한 시간', title: '잠시 멈추면,<br>새로운 일상이.',
      copy: '빛과 여백, 편안한 감각으로 채운 작은 공간을 만나보세요.',
      action: '공간 살펴보기', label: '당신을 위한 공간', type: 'retreat',
      stats: [['머물고 싶은 공간', '12', '직접 고른 장소'], ['한 공간의 정원', '02', '조용한 휴식'], ['고객의 기록', '4.9', '편안했던 순간들']],
      rows: [['01', '빛이 머무는 서재', '읽고 사색하는 시간'], ['02', '작은 정원이 있는 방', '초록을 바라보는 오후'], ['03', '차 한 잔의 여유', '일상을 비우는 순간']]
    },
    industrialBrutalist: {
      brand: 'WORK / SHOP', section: '제작과 실험의 기록', title: '생각은 크게.<br>실행은 정확히.',
      copy: '정해진 틀을 넘어, 손에 잡히는 결과를 만듭니다.',
      action: '제작 목록 보기', label: 'PRODUCTION INDEX', type: 'industrial',
      stats: [['현재 제작', '08', 'IN PROGRESS'], ['완료한 실험', '32', 'COMPLETED'], ['다음 공개', '09.24', 'NEXT RELEASE']],
      rows: [['A—01', '새로운 시각 언어', '설계'], ['B—02', '사용성을 위한 실험', '제작'], ['C—03', '다음 단계의 도구', '테스트']]
    },
    redesignGuard: {
      brand: 'workspace', section: '프로젝트 / 개선 사항', title: '익숙한 흐름,<br>더 명확한 화면.',
      copy: '매일 하는 일을 편하게. 필요한 정보와 다음 행동이 자연스럽게 이어집니다.',
      action: '개선 목록 보기', label: '이번 업데이트', type: 'document',
      stats: [['확인한 화면', '12', '기존 흐름 유지'], ['개선한 요소', '08', '읽기와 조작'], ['검토 항목', '03', '마지막 확인']],
      rows: [['01', '메뉴와 이동 경로', '유지'], ['02', '정보의 우선순위', '개선'], ['03', '입력과 상태 안내', '검토']]
    }
  };

  function artwork(type) {
    return '<div class="p-art p-art-' + type + '" aria-hidden="true">' +
      '<span class="p-art-orbit"></span><span class="p-art-column"></span>' +
      '<span class="p-art-disc"></span><small>FORM STUDY<br>NO. 024</small></div>';
  }

  function stats(scene) {
    return '<div class="p-grid">' + scene.stats.map(function (item) {
      return '<article class="p-stat-card"><span class="label">' + item[0] +
        '</span><strong class="value">' + item[1] + '</strong><span class="trend">' + item[2] + '</span></article>';
    }).join('') + '</div>';
  }

  function content(scene) {
    const rows = scene.rows.map(function (row, index) {
      return '<div class="p-project-row"><span class="p-index">' + row[0] + '</span><strong>' + row[1] +
        '</strong><span class="p-status">' + row[2] + '</span><span class="p-row-end" aria-hidden="true">' +
        (scene.type === 'data' ? '14:' + (20 + index * 12) : '↗') + '</span></div>';
    }).join('');
    return '<section class="p-content" id="previewProjects" tabindex="-1"><div class="p-section-title"><h3>' +
      scene.label + '</h3><span>01 — 03</span></div>' + rows + '</section>';
  }

  function render(profileKey, presetKey, colors) {
    const root = document.getElementById('advPreview');
    if (!root) return;
    root.style.setProperty('--p-on-primary', foreground(colors.primary));
    root.style.setProperty('--p-muted', readableMuted(colors.text, colors.background));
    const scene = scenes[profileKey] || scenes.premiumFrontend;
    const signature = profileKey + ':' + presetKey;
    if (root.dataset.sceneKey === signature) return;
    root.dataset.sceneKey = signature;
    root.dataset.scene = scene.type;
    const visual = ['editorial', 'retreat', 'industrial'].includes(scene.type);
    const navigation = visual ? ['작업', '소개', '문의'] : ['개요', '프로젝트', '문서'];
    const noteTitle = visual ? '다음 이야기를 시작해 보세요.' : '다음 할 일을 기록하세요.';
    const placeholder = visual ? '어떤 프로젝트를 생각하고 있나요?' : '새 작업의 이름이나 목표를 입력하세요';
    root.innerHTML = '<header class="p-masthead"><strong class="p-brand">' + scene.brand +
      '</strong><div class="p-navigation" aria-label="예시 메뉴">' + navigation.map(function (item, index) {
        return '<span' + (index === 0 ? ' class="is-current"' : '') + '>' + item + '</span>';
      }).join('') + '</div><span class="p-edition">' + (visual ? 'SEOUL, KR' : 'TEAM SPACE') + '</span></header>' +
      '<div class="p-hero"><div class="p-hero-copy"><span class="p-kicker">' + scene.section + '</span><h2>' +
      scene.title.replace(/<br>/g, '<br> ') + '</h2><p>' + scene.copy + '</p><button type="button" class="p-btn">' + scene.action +
      '<span aria-hidden="true">↗</span></button></div>' + (visual ? artwork(scene.type) : '') + '</div>' +
      (scene.type === 'editorial' || scene.type === 'document' ? content(scene) + stats(scene) : stats(scene) + content(scene)) +
      '<div class="p-profile"><div class="p-avatar" aria-hidden="true">↗</div><div class="p-profile-info">' +
      '<h3>' + noteTitle + '</h3><p>입력 필드의 색상과 글자도 직접 확인할 수 있습니다.</p>' +
      '<input type="text" class="p-input" placeholder="' + placeholder + '" aria-label="미리보기 입력창"></div></div>' +
      '<footer class="p-colophon"><span>' + scene.brand + '</span><span>DESIGNED WITH INTENTION.</span></footer>';
    root.querySelector('.p-btn').addEventListener('click', function () {
      const target = root.querySelector('.p-content');
      target.scrollIntoView({ block: 'nearest' });
      target.focus({ preventScroll: true });
    });
  }

  function luminance(hex) {
    const rgb = hex.match(/[a-f0-9]{2}/gi).map(function (part) {
      const v = parseInt(part, 16) / 255;
      return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
  }
  function foreground(color) { return luminance(color) > .179 ? '#000000' : '#ffffff'; }
  function readableMuted(text, background) {
    // Full text color keeps custom low-contrast themes from becoming even fainter.
    return (Math.max(luminance(text), luminance(background)) + .05) /
      (Math.min(luminance(text), luminance(background)) + .05) < 7 ? text :
      'color-mix(in srgb, ' + text + ' 68%, ' + background + ')';
  }
  function palette(preset) {
    const strip = document.createElement('div');
    strip.className = 'preset-palette';
    strip.setAttribute('aria-hidden', 'true');
    [preset.bg, preset.surface, preset.primary, preset.text].forEach(function (color) {
      const chip = document.createElement('i');
      chip.style.background = color;
      strip.append(chip);
    });
    return strip;
  }
  global.VASDesignPreview = Object.freeze({ render: render, foreground: foreground, palette: palette });
})(window);
