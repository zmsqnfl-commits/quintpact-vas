/** 인계 연결 영수증과 현재 반복 작업의 최소 상태를 관리합니다. */
(function (global) {
  'use strict';

  const RECEIPT_KEY = 'vasHandoffReceipts.v1';
  const MAX_RECEIPTS = 20;
  let continuationState = null;

  function readReceipts() {
    if (!global.VASStorage) return [];
    return VASStorage.readJson(RECEIPT_KEY, [], function (value) { return Array.isArray(value); }) || [];
  }

  function writeReceipts(receipts) {
    if (!global.VASStorage) return false;
    return VASStorage.writeJson(RECEIPT_KEY, receipts.slice(0, MAX_RECEIPTS));
  }

  function receipt(document) {
    if (!document || !document.workflow || !/^h_[a-f0-9]{32}$/i.test(document.workflow.handoffId || '')) return null;
    if (!document.integrity || !/^[a-f0-9]{64}$/i.test(document.integrity.payloadSha256 || '')) return null;
    return {
      handoffId: document.workflow.handoffId,
      payloadSha256: document.integrity.payloadSha256,
      iteration: Number(document.workflow.iteration) || 1,
      sourceType: document.project && document.project.sourceType || 'existing',
      resultIds: []
    };
  }

  function remember(document) {
    const next = receipt(document);
    if (!next) return false;
    const current = readReceipts();
    const previous = current.find(function (item) { return item && item.handoffId === next.handoffId; });
    if (previous && Array.isArray(previous.resultIds)) next.resultIds = previous.resultIds.slice(0, 20);
    return writeReceipts([next].concat(current.filter(function (item) { return item && item.handoffId !== next.handoffId; })));
  }

  function verifyResult(result) {
    const current = readReceipts();
    const found = current.find(function (item) { return item && item.handoffId === result.handoffId; });
    if (!found) return { status: 'unverified', message: '이 기기의 인계 기록을 찾지 못했습니다. 원본 인계가 맞는지 직접 확인해 주세요.' };
    if (found.sourceType !== result.sourceType && !(found.sourceType === 'existing' && result.sourceType === 'registered')) {
      return { status: 'mismatch', message: '인계 작업 종류와 결과의 작업 종류가 다릅니다.' };
    }
    if (Number(found.iteration) !== Number(result.iteration)) return { status: 'mismatch', message: '인계 반복 번호와 결과 반복 번호가 다릅니다.' };
    if (!/^[a-f0-9]{64}$/i.test(result.handoffPayloadSha256 || '') || found.payloadSha256 !== result.handoffPayloadSha256) {
      return { status: 'mismatch', message: '인계 JSON 해시와 결과의 해시가 다릅니다.' };
    }
    if (Array.isArray(found.resultIds) && found.resultIds.includes(result.resultId)) return { status: 'duplicate', message: '이미 다음 작업에 반영한 결과입니다.' };
    return { status: 'verified', message: '이 기기에서 만든 인계와 일치합니다.', receipt: found };
  }

  function markResult(result) {
    const receipts = readReceipts();
    const found = receipts.find(function (item) { return item && item.handoffId === result.handoffId; });
    if (!found) return false;
    found.resultIds = Array.from(new Set((found.resultIds || []).concat(result.resultId))).slice(-20);
    return writeReceipts(receipts);
  }

  function acceptResult(result, verdict, note) {
    continuationState = {
      context: VASAgentContract.continuation(result, verdict, note),
      workflow: { iteration: Number(result.iteration) + 1, parentResultId: result.resultId, status: 'ready' },
      sourceType: result.sourceType
    };
    markResult(result);
    return continuationState;
  }

  function current() { return continuationState ? JSON.parse(JSON.stringify(continuationState)) : null; }
  function clearCurrent() { continuationState = null; }
  function clearReceipts() { return global.VASStorage ? VASStorage.remove(RECEIPT_KEY) : false; }

  function writeImportDraft(value) {
    try {
      const state = Object.assign({}, global.history.state || {}, { vasImportDraft: value || null });
      global.history.replaceState(state, document.title, global.location.href);
      return true;
    } catch (error) { return false; }
  }

  function readImportDraft() {
    try { return global.history.state && global.history.state.vasImportDraft || null; } catch (error) { return null; }
  }

  global.VASHandoffWorkflow = Object.freeze({
    remember: remember, verifyResult: verifyResult, acceptResult: acceptResult,
    current: current, clearCurrent: clearCurrent, clearReceipts: clearReceipts,
    writeImportDraft: writeImportDraft, readImportDraft: readImportDraft
  });
})(window);
