/* =========================================
   client-export.js
   내보내기 로직: JSON 저장
   (localStorage 미사용 — 폼에서 직접 수집)
   ========================================= */

function exportJson() {
    const form = document.getElementById('projectForm');
    const data = {};
    form.querySelectorAll('input, textarea').forEach(el => {
        if (el.type === 'checkbox' || el.type === 'radio') {
            if (el.checked) data[el.name] = (data[el.name] || []).concat(el.value);
        } else if (el.value.trim()) {
            data[el.name] = el.value;
        }
    });

    const now = new Date();
    const stamp = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}-${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}`;
    const filename = `vas-client-${stamp}.json`;

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}
