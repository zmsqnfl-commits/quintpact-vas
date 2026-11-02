/** 인계 연결 영수증과 현재 반복 작업의 최소 상태를 관리합니다. */
(function (global) {
  'use strict';

  const RECEIPT_KEY = 'vasHandoffReceipts.v1';
  const REVIEW_KEY = 'vasResultReviews.v1';
  const MAX_RECEIPTS = 20;
  let continuationState = null;
  const acceptedResults = new Set();
  const invalidatedReviews = new Set();
  function resultKey(result) { return result.handoffId + ":" + result.resultId; }
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function binding(result) {
    const value = clone(result);
    delete value.__redactions;
    return VASAgentContract.stable(value);
  }
  function readReviews() {
    return global.VASStorage ? VASStorage.readJson(REVIEW_KEY, [], Array.isArray) || [] : [];
  }
  function reviewEntry(result) {
    const semantic = binding(result);
    const records = readReviews();
    const stale = records.some(function (item) { return item && item.key === resultKey(result) && item.semantic !== semantic; });
    // Importing a changed payload invalidates the older confirmation, even if a later file reuses its IDs.
    if (stale) {
      invalidatedReviews.add(resultKey(result));
      if (global.VASStorage) VASStorage.writeJson(REVIEW_KEY, records.filter(function (item) { return item && item.key !== resultKey(result); }));
    }
    if (invalidatedReviews.has(resultKey(result))) return null;
    return records.find(function (item) {
      return item && item.key === resultKey(result) && item.semantic === semantic;
    }) || null;
  }

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
      completionCriteria: clone(document.task && document.task.completionCriteria || []),
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
    if (acceptedResults.has(resultKey(result))) return { status: 'duplicate', message: '이미 다음 작업에 반영한 결과입니다.' };
    if (!found) return { status: 'unverified', message: '이 기기의 인계 기록을 찾지 못했습니다. 원본 인계가 맞는지 직접 확인해 주세요.' };
    if (found.sourceType !== result.sourceType && !(found.sourceType === 'existing' && result.sourceType === 'registered')) {
      return { status: 'mismatch', message: '인계 작업 종류와 결과의 작업 종류가 다릅니다.' };
    }
    if (Number(found.iteration) !== Number(result.iteration)) return { status: 'mismatch', message: '인계 반복 번호와 결과 반복 번호가 다릅니다.' };
    if (!/^[a-f0-9]{64}$/i.test(result.handoffPayloadSha256 || '') || found.payloadSha256 !== result.handoffPayloadSha256) {
      return { status: 'mismatch', message: '인계 JSON 해시와 결과의 해시가 다릅니다.' };
    }
    if (Array.isArray(found.resultIds) && found.resultIds.includes(result.resultId)) return { status: 'duplicate', message: '이미 다음 작업에 반영한 결과입니다.' };
    return { status: 'verified', message: '인계 연결 확인: 이 기기에서 만든 인계와 일치합니다. 작업 완료나 실행을 검증한 것은 아닙니다.', receipt: found };
  }

  function review(result) {
    const linked = verifyResult(result);
    const entry = reviewEntry(result);
    const criteria = linked.receipt && linked.receipt.completionCriteria || [];
    const observations = entry && Array.isArray(entry.observations) ? entry.observations : [];
    const assessment = global.VASResultAssessment
      ? VASResultAssessment.evaluate(result, { linkStatus: linked.status, criteria: criteria, observations: observations })
      : { status: 'needs-verification', reasons: ['assessment-unavailable'], conditions: [] };
    return clone({ assessment: assessment, criteria: criteria, observations: observations,
      userAcceptance: entry && entry.userAcceptance || { status: 'not-reviewed' } });
  }

  function saveReview(result, update) {
    if (!global.VASStorage) return false;
    const records = readReviews();
    const previous = reviewEntry(result) || { key: resultKey(result), semantic: binding(result), observations: [] };
    Object.assign(previous, update);
    const saved = VASStorage.writeJson(REVIEW_KEY, [previous].concat(records.filter(function (item) {
      return item && item.key !== resultKey(result);
    })).slice(0, 10));
    if (saved) invalidatedReviews.delete(resultKey(result));
    return saved;
  }

  function recordObservation(result, input) {
    const state = review(result);
    if (!input || typeof input !== 'object' || state.assessment.status === 'invalid') return { ok: false, message: '결과와 확인 입력 형식을 다시 확인해 주세요.' };
    if (verifyResult(result).status !== 'verified' || !global.VASResultAssessment || !VASResultAssessment.criteriaValid(state.criteria)) return { ok: false, message: '원본 인계의 완료조건을 먼저 확인해야 합니다.' };
    const criterion = state.criteria.find(function (item) { return item.id === input.criterionId; });
    if (!criterion || !result.artifactVersion || input.artifactVersion !== result.artifactVersion) return { ok: false, message: '직접 확인한 산출물 버전이 결과의 버전과 일치해야 합니다.' };
    if (!['manual', 'static'].includes(input.method) || !['passed', 'failed', 'skipped', 'not-applicable'].includes(input.outcome)) return { ok: false, message: '확인 방법과 결과를 선택해 주세요.' };
    if (input.method !== criterion.method && input.alternativeApproved !== true) return { ok: false, message: '원래 확인 방법을 대신하는 확인임을 명시적으로 승인해 주세요.' };
    const summary = VASAgentContract.clean(input.summary, 1000);
    if (!summary || summary !== String(input.summary || '').trim()) return { ok: false, message: '관찰 내용을 1,000자 이내로 적고 비밀값·연락처·절대 경로를 제거해 주세요.' };
    const observation = { criterionId: criterion.id, artifactVersion: result.artifactVersion,
      method: input.method, outcome: input.outcome, summary: summary, source: 'user-direct',
      observedAt: new Date().toISOString(), alternativeApproved: input.alternativeApproved === true };
    const observations = state.observations.filter(function (item) { return item.criterionId !== criterion.id; }).concat(observation);
    if (!saveReview(result, { observations: observations })) return { ok: false, message: '직접 확인 기록을 저장하지 못했습니다. 평가를 완료로 바꾸지 않았습니다.' };
    return { ok: true, review: review(result) };
  }

  function markResult(result) {
    const receipts = readReceipts();
    const found = receipts.find(function (item) { return item && item.handoffId === result.handoffId; });
    if (!found) return false;
    found.resultIds = Array.from(new Set((found.resultIds || []).concat(result.resultId))).slice(-20);
    return writeReceipts(receipts);
  }

  function acceptResult(result, verdict, note, userAccepted) {
    if (result.iteration >= 9999) return null;
    if (['duplicate', 'mismatch'].includes(verifyResult(result).status)) return null;
    const evaluated = review(result);
    if (evaluated.assessment.status === 'invalid') return null;
    const userAcceptance = { status: verdict === 'needs-revision' ? 'needs-revision' : userAccepted === true ? 'accepted' : 'not-reviewed',
      recordedAt: new Date().toISOString(), completionOverride: false };
    saveReview(result, { userAcceptance: userAcceptance });
    const context = VASAgentContract.continuation(result, verdict, note);
    context.reportedStatus = result.reportedStatus || result.status;
    context.assessment = evaluated.assessment;
    context.userAcceptance = userAcceptance;
    context.reviewHistory = { source: 'previous-local-user-review', trustedOnImport: false,
      artifactVersion: result.artifactVersion || '', observations: evaluated.observations };
    continuationState = {
      context: context,
      workflow: { iteration: Number(result.iteration) + 1, parentResultId: result.resultId, status: 'ready' },
      sourceType: result.sourceType
    };
    acceptedResults.add(resultKey(result));
    markResult(result);
    return continuationState;
  }

  function current() { return continuationState ? JSON.parse(JSON.stringify(continuationState)) : null; }
  function clearCurrent() { continuationState = null; }
  function clearReceipts() {
    if (!global.VASStorage) return false;
    const reviewsRemoved = VASStorage.remove(REVIEW_KEY);
    return VASStorage.remove(RECEIPT_KEY) && reviewsRemoved;
  }

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
    review: review, recordObservation: recordObservation,
    current: current, clearCurrent: clearCurrent, clearReceipts: clearReceipts,
    writeImportDraft: writeImportDraft, readImportDraft: readImportDraft
  });
})(window);
