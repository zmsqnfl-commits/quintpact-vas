/* =========================================
   client-form.js
   폼 네비게이션, 드래그앤드롭, 완료 화면, 다국어 전환 로직
   초안 저장은 client-draft.js가 담당합니다.
   ========================================= */

var currentLang = 'ko';
var cur = 1;
const total = 5;

/* 언어 전환 */
function setLang(lang) {
    currentLang = lang;
    const koButton = document.getElementById('btn-ko');
    const enButton = document.getElementById('btn-en');
    if (koButton) koButton.classList.toggle('active', lang === 'ko');
    if (enButton) enButton.classList.toggle('active', lang === 'en');

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (i18n[lang][key]) el.innerHTML = i18n[lang][key];
    });

    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
        const key = el.getAttribute('data-i18n-ph');
        if (i18n[lang][key]) el.setAttribute('placeholder', i18n[lang][key]);
    });

    updateUI();
    if (window.VASClientDraft) window.VASClientDraft.renderPolicy();
    if (window.VASClientDraft) window.VASClientDraft.save();
}

/* 진행 상태 UI 갱신 */
function updateUI() {
    document.getElementById('progressText').innerHTML = `0${cur}<span>/0${total}</span>`;

    const prevBtn = document.getElementById('prevBtn');
    prevBtn.style.opacity = cur === 1 ? '0' : '1';
    prevBtn.style.pointerEvents = cur === 1 ? 'none' : 'auto';

    const nextBtn = document.getElementById('nextBtn');
    if (cur === total) {
        nextBtn.innerHTML = i18n[currentLang]['btnSubmit'];
        nextBtn.classList.add('finish');
    } else {
        nextBtn.innerHTML = i18n[currentLang]['btnNext'];
        nextBtn.classList.remove('finish');
    }
}

/* 숨은 라디오 검증 안내 */
function clearStepValidation(stepEl) {
    stepEl.querySelectorAll('[data-validation-message]').forEach(el => el.remove());
    stepEl.querySelectorAll('[data-validation-target]').forEach(el => {
        el.removeAttribute('data-validation-target');
        el.style.outline = '';
        el.style.outlineOffset = '';
    });
}

function showFieldValidation(input) {
    const q = input.closest('.q') || input.parentElement;
    const target = input.closest('.v-blocks, .blocks') || input;
    const message = currentLang === 'ko'
        ? '필수 항목을 입력하거나 선택해 주세요.'
        : 'Please complete the required field.';

    target.setAttribute('data-validation-target', 'true');
    target.style.outline = '3px solid #ffcc00';
    target.style.outlineOffset = '8px';

    if (!q.querySelector('[data-validation-message]')) {
        const notice = document.createElement('div');
        notice.setAttribute('data-validation-message', 'true');
        notice.style.marginTop = '16px';
        notice.style.fontWeight = '800';
        notice.style.color = '#b45309';
        notice.textContent = message;
        q.appendChild(notice);
    }

    target.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

function validateCurrentStep(stepEl) {
    clearStepValidation(stepEl);
    const inputs = stepEl.querySelectorAll('input[required], textarea[required]');
    const checkedNames = new Set();

    for (let input of inputs) {
        if (input.type === 'radio') {
            if (checkedNames.has(input.name)) continue;
            checkedNames.add(input.name);
            const selected = stepEl.querySelector(`input[name="${input.name}"]:checked`);
            if (!selected) {
                showFieldValidation(input);
                return false;
            }
            continue;
        }

        if (!input.checkValidity()) {
            input.reportValidity();
            showFieldValidation(input);
            return false;
        }
    }

    return true;
}

/* 스텝 이동 */
function changeStep(dir) {
    const steps = document.querySelectorAll('.step');

    if (dir === 1) {
        const currentStepEl = document.querySelector(`[data-step="${cur}"]`);
        if (!validateCurrentStep(currentStepEl)) return;
    }

    cur += dir;
    if (cur < 1) cur = 1;
    if (cur > total) { showDone(); return; }

    steps.forEach(s => {
        s.style.opacity = '0';
        s.style.transform = 'translateY(40px)';
        setTimeout(() => s.classList.remove('active'), 300);
    });

    setTimeout(() => {
        const nextStep = document.querySelector(`[data-step="${cur}"]`);
        nextStep.classList.add('active');
        void nextStep.offsetWidth;
        nextStep.style.opacity = '1';
        nextStep.style.transform = 'translateY(0)';
        const firstInput = nextStep.querySelector('input, textarea');
        if (firstInput) firstInput.focus();
    }, 350);

    updateUI();
    if (window.VASClientDraft) window.VASClientDraft.save();
}

/* 완료 화면 진입 */
function showDone() {
    const activeStep = document.querySelector('.step.active');
    if (activeStep) {
        activeStep.style.opacity = '0';
        activeStep.style.transform = 'translateY(40px)';
        setTimeout(() => activeStep.classList.remove('active'), 300);
    }
    document.getElementById('navWrap').style.display = 'none';
    const ds = document.getElementById('doneScreen');
    ds.classList.add('active');
    if (window.VASPersonalization) {
        const selected = name => Array.from(document.querySelectorAll(`[name="${name}"]:checked`)).map(input => input.value || 'selected');
        const capabilities = ['vision', 'audio', 'text', 'auto'].filter(name => document.querySelector(`[name="sense_${name}"]`).checked);
        const environments = ['web', 'mobile', 'windows', 'edge'].filter(name => document.querySelector(`[name="env_${name}"]`).checked);
        window.VASPersonalization.record({
            type: 'form_completed',
            source: 'client-application',
            payload: {
                language: currentLang, schema: 1, capabilities: capabilities,
                environments: environments, dataStatus: selected('data_status'), budget: selected('budget')
            }
        });
    }
}

/* 완료 화면 → 폼으로 복귀 */
function goBackFromDone() {
    document.getElementById('doneScreen').classList.remove('active');
    document.getElementById('navWrap').style.display = 'flex';
    cur = total;
    const lastStep = document.querySelector(`.step[data-step="${total}"]`);
    lastStep.classList.add('active');
    setTimeout(() => {
        lastStep.style.opacity = '1';
        lastStep.style.transform = 'translateY(0)';
        updateUI();
    }, 50);
}

/* 새로 작성하기 — 페이지 리로드로 초기화 */
function clearForm() {
    const msg = currentLang === 'ko'
        ? '작성 중인 내용을 모두 지우고 처음부터 다시 시작하시겠습니까?'
        : 'Clear all and start over?';
    if (confirm(msg)) {
        if (window.VASClientDraft) window.VASClientDraft.clear();
        document.getElementById('projectForm').reset();
        location.reload();
    }
}

/* 드래그 앤 드롭 로직 */
const dropZone = document.getElementById('dropZone');
const fileChips = document.getElementById('fileChips');
let uploadedFiles = [];

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});

function handleFiles(files) {
    for (let f of files) uploadedFiles.push(f.name);
    renderFiles();
}
function removeFile(index, event) {
    event.stopPropagation();
    uploadedFiles.splice(index, 1);
    renderFiles();
}
function renderFiles() {
    fileChips.innerHTML = '';
    uploadedFiles.forEach((name, i) => {
        const chip = document.createElement('div');
        chip.className = 'file-chip';
        chip.appendChild(document.createTextNode(`File: ${name} `));

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.textContent = 'x';
        removeButton.addEventListener('click', (event) => removeFile(i, event));
        chip.appendChild(removeButton);
        fileChips.appendChild(chip);
    });
    let hidden = document.getElementById('hiddenFiles');
    if (!hidden) {
        hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = 'attached_files';
        hidden.id = 'hiddenFiles';
        document.getElementById('projectForm').appendChild(hidden);
    }
    hidden.value = JSON.stringify(uploadedFiles);
}

/* 초기 렌더링 */
setTimeout(() => {
    const firstStep = document.querySelector('.step.active');
    if (firstStep) {
        firstStep.style.opacity = '1';
        firstStep.style.transform = 'translateY(0)';
    }
}, 100);
updateUI();
setLang(currentLang);

document.getElementById('projectForm').addEventListener('change', (event) => {
    const stepEl = event.target.closest('.step');
    if (stepEl) clearStepValidation(stepEl);
});
