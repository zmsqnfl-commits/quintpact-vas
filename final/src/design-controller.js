let currentFormat = 'json';

// 즐겨찾기 상태 (localStorage 기반)
let favorites = JSON.parse(localStorage.getItem('vasFavorites')) || [];

function toggleFavorite(presetKey, event) {
  event.stopPropagation();
  const idx = favorites.indexOf(presetKey);
  if (idx > -1) {
    favorites.splice(idx, 1);
  } else {
    favorites.push(presetKey);
  }
  localStorage.setItem('vasFavorites', JSON.stringify(favorites));
  renderPresets();
}

function renderPresets() {
  const container = document.getElementById('preset-container');
  container.innerHTML = ''; // Clear

  // 1. 즐겨찾기 그룹 렌더링 (옵션)
  if (favorites.length > 0) {
    let html = `<h3>⭐ 즐겨찾기</h3><div class="preset-grid" style="margin-bottom: 20px;">`;
    favorites.forEach(key => {
      if(PRESETS[key]) {
        // 첫 글자 대문자화 (간단히 표시용)
        let nameDisplay = key.charAt(0).toUpperCase() + key.slice(1);
        html += `<button class="btn-preset" data-preset="${key}" onclick="applyPreset('${key}', this)">
                   ${nameDisplay}
                   <span class="fav-icon active" onclick="toggleFavorite('${key}', event)">★</span>
                 </button>`;
      }
    });
    html += `</div>`;
    container.innerHTML += html;
  }

  // 2. 카테고리별 렌더링
  Object.keys(PRESET_CATEGORIES).forEach(catKey => {
    const cat = PRESET_CATEGORIES[catKey];
    let html = `<h3>${cat.label}</h3><div class="preset-grid" style="margin-bottom: 20px;">`;
    
    cat.presets.forEach(key => {
      let isFav = favorites.includes(key);
      let nameDisplay = key.charAt(0).toUpperCase() + key.slice(1);
      html += `<button class="btn-preset" data-preset="${key}" onclick="applyPreset('${key}', this)">
                 ${nameDisplay}
                 <span class="fav-icon ${isFav ? 'active' : ''}" onclick="toggleFavorite('${key}', event)">
                   ${isFav ? '★' : '☆'}
                 </span>
               </button>`;
    });
    
    html += `</div>`;
    container.innerHTML += html;
  });
}

function applyPreset(name, element) {
  document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
  
  let targetElement = element;
  if (!targetElement && typeof event !== 'undefined' && event && event.target) {
    targetElement = event.target;
  }
  
  if (targetElement) {
    targetElement.classList.add('active');
  } else {
    document.querySelectorAll('.btn-preset').forEach(b => {
      if (b.getAttribute('onclick') && b.getAttribute('onclick').includes(`'${name}'`)) {
        b.classList.add('active');
      }
    });
  }
  
  const p = PRESETS[name];
  document.getElementById('colorBg').value = p.bg;
  document.getElementById('colorSurface').value = p.surface;
  document.getElementById('colorText').value = p.text;
  document.getElementById('colorPrimary').value = p.primary;
  document.getElementById('colorBorder').value = p.border;
  document.getElementById('radius').value = p.rad;
  document.getElementById('padding').value = p.pad;
  document.getElementById('borderWidth').value = p.bw;
  document.getElementById('shadow').value = p.shadow;
  document.getElementById('speed').value = p.speed;
  document.getElementById('letterSpacing').value = p.ls;
  document.getElementById('fontFamily').value = p.font;
  
  // Set the AI System Prompt
  const agentPrompt = window.composeAgentPrompt ? window.composeAgentPrompt(name, p) : p.prompt;
  document.getElementById('aiPrompt').value = agentPrompt;
  
  // 현재 프리셋 이름 저장 (#7 연동)
  localStorage.setItem('vasCurrentPreset', name);
  
  update(false); // history 기록
}

function getValues() {
  const fs = +document.getElementById('fontSize').value;
  return {
    fontFamily: document.getElementById('fontFamily').value,
    fontSize: fs,
    fsHero: (fs * 3.5) + 'px',
    fsH2: (fs * 2.2) + 'px',
    fsH3: (fs * 1.5) + 'px',
    fsBody: fs + 'px',
    fsSm: (fs * 0.8) + 'px',
    letterSpacing: +document.getElementById('letterSpacing').value,
    padding: +document.getElementById('padding').value,
    radius: +document.getElementById('radius').value,
    borderWidth: +document.getElementById('borderWidth').value,
    shadow: +document.getElementById('shadow').value,
    speed: +document.getElementById('speed').value,
    colors: {
      primary: document.getElementById('colorPrimary').value,
      background: document.getElementById('colorBg').value,
      surface: document.getElementById('colorSurface').value,
      text: document.getElementById('colorText').value,
      border: document.getElementById('colorBorder').value,
      success: document.getElementById('colorSuccess').value,
    }
  };
}

function update(skipHistory = false) {
  const v = getValues();
  const f = document.getElementById('advPreview');
  
  document.getElementById('fsVal').textContent = v.fontSize + 'px';
  document.getElementById('lsVal').textContent = v.letterSpacing.toFixed(2) + 'em';
  document.getElementById('padVal').textContent = v.padding + 'px';
  document.getElementById('radVal').textContent = v.radius + 'px';
  document.getElementById('borderVal').textContent = v.borderWidth + 'px';
  document.getElementById('shadowVal').textContent = v.shadow + 'px';
  document.getElementById('speedVal').textContent = v.speed.toFixed(2) + 's';
  
  // Set CSS Vars for Preview Component
  f.style.setProperty('--p-font', v.fontFamily);
  f.style.setProperty('--p-fs-hero', v.fsHero);
  f.style.setProperty('--p-fs-h2', v.fsH2);
  f.style.setProperty('--p-fs-h3', v.fsH3);
  f.style.setProperty('--p-fs-body', v.fsBody);
  f.style.setProperty('--p-fs-sm', v.fsSm);
  f.style.setProperty('--p-ls', v.letterSpacing + 'em');
  f.style.setProperty('--p-pad', v.padding + 'px');
  f.style.setProperty('--p-radius', v.radius + 'px');
  f.style.setProperty('--p-border-width', v.borderWidth + 'px');
  
  // Custom shadow logic for NeoBrutalism
  if(v.colors.border === '#000000' && v.borderWidth >= 3 && v.shadow === 0 && v.radius === 0) {
     f.style.setProperty('--p-shadow', '6px 6px 0px #000');
  } else {
     f.style.setProperty('--p-shadow', v.shadow > 0 ? `0 ${v.shadow/2}px ${v.shadow}px rgba(0,0,0,0.15)` : 'none');
  }

  f.style.setProperty('--p-speed', v.speed + 's');
  f.style.setProperty('--p-primary', v.colors.primary);
  f.style.setProperty('--p-bg', v.colors.background);
  f.style.setProperty('--p-surface', v.colors.surface);
  f.style.setProperty('--p-text', v.colors.text);
  f.style.setProperty('--p-border-color', v.colors.border);
  f.style.setProperty('--p-success', v.colors.success);
  
  document.querySelector('.preview').style.background = v.colors.background;
  
  // Save globally for other HTML layers
  localStorage.setItem('vasThemeTokens', JSON.stringify(v));
  localStorage.setItem('vasThemeTokensVersion', '2.5.2');
  
  if(!skipHistory) saveHistory(v);
  
  if(document.getElementById('tokenOutput').classList.contains('show')) {
    renderOutput();
  }
}

// ========================
// Undo History Logic (#9)
// ========================
let tokenHistory = JSON.parse(localStorage.getItem('vasThemeHistory')) || [];

function saveHistory(v) {
  if(tokenHistory.length > 0) {
    const last = tokenHistory[tokenHistory.length - 1];
    if(JSON.stringify(last) === JSON.stringify(v)) return;
  }
  tokenHistory.push(v);
  if(tokenHistory.length > 6) tokenHistory.shift(); // 5 + 1
  localStorage.setItem('vasThemeHistory', JSON.stringify(tokenHistory));
}

function undoTheme() {
  if(tokenHistory.length > 1) {
    tokenHistory.pop(); // Remove current
    const prev = tokenHistory[tokenHistory.length - 1];
    localStorage.setItem('vasThemeHistory', JSON.stringify(tokenHistory));
    
    if (!prev || !prev.colors) {
      showToast('히스토리 데이터가 호환되지 않습니다. 초기화합니다.');
      tokenHistory = [];
      localStorage.setItem('vasThemeHistory', '[]');
      return;
    }
    
    try {
      // Restore inputs
      document.getElementById('colorBg').value = prev.colors.background || '#ffffff';
      document.getElementById('colorSurface').value = prev.colors.surface || '#ffffff';
      document.getElementById('colorText').value = prev.colors.text || '#000000';
      document.getElementById('colorPrimary').value = prev.colors.primary || '#000000';
      document.getElementById('colorBorder').value = prev.colors.border || '#000000';
      if(document.getElementById('colorSuccess') && prev.colors.success) {
        document.getElementById('colorSuccess').value = prev.colors.success;
      }
      
      document.getElementById('radius').value = prev.radius || 0;
      document.getElementById('padding').value = prev.padding || 0;
      document.getElementById('borderWidth').value = prev.borderWidth || 0;
      document.getElementById('shadow').value = prev.shadow || 0;
      document.getElementById('speed').value = prev.speed || 0;
      document.getElementById('letterSpacing').value = prev.letterSpacing || 0;
      if(prev.fontFamily) document.getElementById('fontFamily').value = prev.fontFamily;
      if(prev.fontSize) document.getElementById('fontSize').value = prev.fontSize;
      
      document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
      
      update(true); // UI 업데이트 (history 기록 제외)
      showToast('이전 디자인으로 되돌렸습니다.');
    } catch(e) {
      showToast('Undo 적용 중 오류가 발생했습니다.');
      console.error(e);
    }
  } else {
    showToast('더 이상 되돌릴 수 없습니다.');
  }
}

function getJSON() {
  const v = getValues();
  return JSON.stringify(v, null, 2);
}

function getCSS() {
  const v = getValues();
  return `:root {\n  --font-family: ${v.fontFamily};\n  --font-size-base: ${v.fontSize}px;\n  --letter-spacing: ${v.letterSpacing}em;\n  --color-primary: ${v.colors.primary};\n  --color-bg: ${v.colors.background};\n  --color-surface: ${v.colors.surface};\n  --color-text: ${v.colors.text};\n  --color-border: ${v.colors.border};\n  --border-radius: ${v.radius}px;\n  --border-width: ${v.borderWidth}px;\n  --padding-base: ${v.padding}px;\n  --transition-speed: ${v.speed}s;\n}`;
}

function getTailwind() {
  const v = getValues();
  return `module.exports = {\n  theme: {\n    extend: {\n      colors: {\n        primary: '${v.colors.primary}',\n        background: '${v.colors.background}',\n        surface: '${v.colors.surface}',\n        border: '${v.colors.border}',\n      },\n      borderRadius: {\n        DEFAULT: '${v.radius}px',\n      },\n      borderWidth: {\n        DEFAULT: '${v.borderWidth}px',\n      },\n      transitionDuration: {\n        DEFAULT: '${v.speed * 1000}ms',\n      }\n    }\n  }\n}`;
}

function renderOutput() {
  let txt = '';
  if(currentFormat === 'json') txt = getJSON();
  else if(currentFormat === 'css') txt = getCSS();
  else if(currentFormat === 'tailwind') txt = getTailwind();
  document.getElementById('tokenPre').textContent = txt;
}

function showExport(fmt) {
  document.getElementById('tokenOutput').classList.add('show');
  renderOutput();
}

function switchFormat(fmt, btn) {
  currentFormat = fmt;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderOutput();
}

function downloadJSON() {
  const blob = new Blob([getJSON()], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'design-tokens.json';
  a.click();
  showToast('디자인 토큰 다운로드 완료!');
}

function triggerFileInput() {
  document.getElementById('fileInput').click();
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) importJSON(file);
}

function importJSON(file) {
  if (!file.name.endsWith('.json')) {
    showToast('JSON 형식의 파일만 지원합니다.');
    return;
  }
  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      const v = JSON.parse(e.target.result);
      if (!v.colors || !v.fontSize || v.radius === undefined) {
        showToast('유효하지 않은 디자인 토큰 파일입니다.');
        return;
      }
      
      // 값 반영
      document.getElementById('colorBg').value = v.colors.background;
      document.getElementById('colorSurface').value = v.colors.surface;
      document.getElementById('colorText').value = v.colors.text;
      document.getElementById('colorPrimary').value = v.colors.primary;
      document.getElementById('colorBorder').value = v.colors.border;
      document.getElementById('colorSuccess').value = v.colors.success || '#10b981';
      document.getElementById('radius').value = v.radius;
      document.getElementById('padding').value = v.padding;
      document.getElementById('borderWidth').value = v.borderWidth;
      document.getElementById('shadow').value = v.shadow;
      document.getElementById('speed').value = v.speed;
      document.getElementById('letterSpacing').value = v.letterSpacing;
      document.getElementById('fontFamily').value = v.fontFamily;
      document.getElementById('fontSize').value = v.fontSize;
      
      // 프리셋 선택 해제
      document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
      
      update();
      showToast('디자인 토큰 성공적으로 복원됨!');
    } catch (err) {
      showToast('파일 읽기 오류 또는 손상된 JSON입니다.');
    }
  };
  reader.readAsText(file);
}

// 드래그 앤 드롭 이벤트 리스너 바인딩
window.addEventListener('DOMContentLoaded', () => {
  renderPresets(); // 동적 프리셋 렌더링 호출
  
  // 최초 로드 시 현재 상태를 히스토리에 기록하기 위해 호출
  setTimeout(() => update(false), 100);

  const dz = document.getElementById('dragZone');
  if (dz) {
    dz.addEventListener('dragover', (e) => {
      e.preventDefault();
      dz.classList.add('dragover');
    });
    dz.addEventListener('dragleave', () => {
      dz.classList.remove('dragover');
    });
    dz.addEventListener('drop', (e) => {
      e.preventDefault();
      dz.classList.remove('dragover');
      const file = e.dataTransfer.files[0];
      if (file) importJSON(file);
    });
  }
});

function copyOutput() {
  navigator.clipboard.writeText(document.getElementById('tokenPre').textContent).then(() => showToast(currentFormat.toUpperCase() + ' 코드 복사 완료!'));
}

function copyAgentPrompt() {
  const p = document.getElementById('aiPrompt').value;
  navigator.clipboard.writeText(p).then(() => showToast('에이전트용 프롬프트 복사 완료!'));
}

function showToast(msg) {
  const t = document.getElementById('dc-toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// Init with Neo-Brutalism as the signature system theme default
applyPreset('neobrutal');

// --- 스플리터 (Resizer) 드래그 로직 ---
const resizer = document.getElementById('resizer');
const controlsPanel = document.getElementById('controlsPanel');
let isDragging = false;

resizer.addEventListener('mousedown', function(e) {
  isDragging = true;
  resizer.classList.add('dragging');
  document.body.style.cursor = 'col-resize';
  // 드래그 중 텍스트 선택 방지
  document.body.style.userSelect = 'none';
});

window.addEventListener('mousemove', function(e) {
  if (!isDragging) return;
  let newWidth = e.clientX;
  if (newWidth < 300) newWidth = 300;
  if (newWidth > 800) newWidth = 800;
  controlsPanel.style.width = newWidth + 'px';
});

window.addEventListener('mouseup', function(e) {
  if (isDragging) {
    isDragging = false;
    resizer.classList.remove('dragging');
    document.body.style.cursor = 'default';
    document.body.style.userSelect = '';
  }
});

