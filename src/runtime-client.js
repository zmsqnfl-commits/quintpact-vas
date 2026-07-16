/** Windows 로컬 런타임 API 브리지 */
(function (global) {
  'use strict';

  const params = new URLSearchParams(global.location.search);
  const hashParams = new URLSearchParams(global.location.hash.replace(/^#/, ''));
  const queryToken = params.get('vasToken');
  const suppliedToken = queryToken || hashParams.get('vasRuntime');
  let memoryToken = '';
  let tokenPersisted = false;
  if (suppliedToken && /^[A-Za-z0-9_-]{20,200}$/.test(suppliedToken)) {
    memoryToken = suppliedToken;
    tokenPersisted = VASStorage.writeText('vasRuntimeToken', suppliedToken, 'session');
    params.delete('vasToken');
    if (tokenPersisted) hashParams.delete('vasRuntime');
    else hashParams.set('vasRuntime', suppliedToken);
    const clean = global.location.pathname + (params.toString() ? '?' + params : '') +
      (hashParams.toString() ? '#' + hashParams : '');
    global.history.replaceState(null, '', clean);
  }

  function getToken() {
    return VASStorage.readText('vasRuntimeToken', '', 'session') || memoryToken;
  }

  function preserveTokenInLinks() {
    if (tokenPersisted || !memoryToken) return;
    document.querySelectorAll('a[data-vas-link], a[href$=".html"]').forEach(function (link) {
      const raw = link.getAttribute('href');
      if (!raw || /^(https?:|mailto:|javascript:)/i.test(raw)) return;
      try {
        const url = new URL(raw, global.location.href);
        const fragments = new URLSearchParams(url.hash.replace(/^#/, ''));
        fragments.set('vasRuntime', memoryToken);
        url.hash = fragments.toString();
        link.setAttribute('href', url.href);
      } catch (error) { }
    });
  }

  function isAvailable() {
    return /^https?:$/.test(global.location.protocol) && Boolean(getToken());
  }

  async function request(path, options) {
    if (!isAvailable()) throw new Error('VAS 로컬 런타임에 연결되지 않았습니다.');
    const init = Object.assign({}, options || {});
    init.headers = Object.assign({}, init.headers || {}, { 'X-VAS-Token': getToken() });
    if (init.body && typeof init.body !== 'string') {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(init.body);
    }
    const response = await global.fetch(path, init);
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (error) { data = { message: text }; }
    if (!response.ok) throw new Error((data && (data.error || data.message)) || '요청 실패: ' + response.status);
    return data;
  }

  async function download(path, options) {
    if (!isAvailable()) throw new Error('VAS 로컬 런타임에 연결되지 않았습니다.');
    const init = Object.assign({}, options || {});
    init.headers = Object.assign({}, init.headers || {}, { 'X-VAS-Token': getToken() });
    if (init.body && typeof init.body !== 'string') {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(init.body);
    }
    const response = await global.fetch(path, init);
    if (!response.ok) {
      const text = await response.text();
      let message = text;
      try { const data = JSON.parse(text); message = data.error || data.message || text; } catch (error) { }
      throw new Error(message || '다운로드 실패: ' + response.status);
    }
    return response.blob();
  }

  function heartbeat() {
    if (!isAvailable()) return;
    request('/api/heartbeat', { method: 'POST' }).catch(function () {});
  }

  global.setInterval(heartbeat, 30000);
  heartbeat();
  preserveTokenInLinks();

  global.VASRuntime = Object.freeze({ isAvailable, request, download, getToken, preserveTokenInLinks });
})(window);
