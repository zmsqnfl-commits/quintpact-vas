/** Windows 로컬 런타임 API 브리지 */
(function (global) {
  'use strict';

  const params = new URLSearchParams(global.location.search);
  const hashParams = new URLSearchParams(global.location.hash.replace(/^#/, ''));
  const queryToken = params.get('vasToken');
  const suppliedToken = queryToken || hashParams.get('vasRuntime');
  const tokenPattern = /^[A-Za-z0-9_-]{20,200}$/;

  function historyToken() {
    try {
      const token = global.history.state && global.history.state.vasRuntime;
      return tokenPattern.test(token || '') ? token : '';
    } catch (error) {
      return '';
    }
  }

  let memoryToken = historyToken();
  let tokenPersisted = false;
  if (suppliedToken && tokenPattern.test(suppliedToken)) {
    memoryToken = suppliedToken;
    tokenPersisted = VASStorage.writeText('vasRuntimeToken', suppliedToken, 'session');
    params.delete('vasToken');
    if (tokenPersisted) hashParams.delete('vasRuntime');
    else hashParams.set('vasRuntime', suppliedToken);
    const clean = global.location.pathname + (params.toString() ? '?' + params : '') +
      (hashParams.toString() ? '#' + hashParams : '');
    try {
      const state = Object.assign({}, global.history.state || {}, { vasRuntime: suppliedToken });
      global.history.replaceState(state, '', clean);
    } catch (error) { }
  } else if (memoryToken) {
    tokenPersisted = VASStorage.writeText('vasRuntimeToken', memoryToken, 'session');
  }

  function getToken() {
    return VASStorage.readText('vasRuntimeToken', '', 'session') || memoryToken || historyToken();
  }

  function preserveTokenInLink(link, token) {
    const raw = link && link.getAttribute('href');
    if (!raw || /^(mailto:|javascript:)/i.test(raw)) return;
    try {
      const url = new URL(raw, global.location.href);
      if (/^https?:$/.test(url.protocol) && url.origin !== global.location.origin) return;
      const fragments = new URLSearchParams(url.hash.replace(/^#/, ''));
      fragments.set('vasRuntime', token);
      url.hash = fragments.toString();
      link.setAttribute('href', url.href);
    } catch (error) { }
  }

  function preserveTokenInLinks() {
    const token = getToken();
    if (!token) return;
    document.querySelectorAll('a[data-vas-link], a[href*=".html"]').forEach(function (link) {
      preserveTokenInLink(link, token);
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

  global.VASRuntime = Object.freeze({ isAvailable, request, download, getToken, preserveTokenInLinks });

  document.addEventListener('click', function (event) {
    const link = event.target.closest && event.target.closest('a[data-vas-link], a[href*=".html"]');
    const token = getToken();
    if (link && token) preserveTokenInLink(link, token);
  }, true);
  document.addEventListener('DOMContentLoaded', preserveTokenInLinks);
  global.addEventListener('pageshow', preserveTokenInLinks);
  global.addEventListener('popstate', preserveTokenInLinks);
  global.setInterval(heartbeat, 30000);
  heartbeat();
  preserveTokenInLinks();
})(window);
