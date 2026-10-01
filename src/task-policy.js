/** Explicit scope and completion conditions for newly generated handoffs. */
(function (global) {
  'use strict';
  const methods = { automatic: '자동 검사', manual: '수동 확인', static: '정적 검토' };
  const modes = { preserve: '기존 디자인 유지', partial: '부분 디자인 수정', redesign: '전체 리디자인', new: '새 프로젝트 디자인' };
  function text(value, maximum, label, changes) {
    if (typeof value !== 'string') throw new Error(label + '은 텍스트로 입력하세요.');
    if (value.length > maximum) throw new Error(label + '은 ' + maximum + '자 이하여야 합니다. 내용을 줄여 다시 확인하세요.');
    const normalized = VASAgentContract.clean(value, maximum);
    if (normalized !== value.trim()) changes.push(label);
    return normalized;
  }
  function criteria(value, changes) {
    if (value === undefined) return [];
    if (!Array.isArray(value) || value.length > 20) throw new Error('완료조건은 최대 20개까지 입력하세요.');
    return value.map(function (item, index) {
      if (!item || typeof item !== 'object' || Array.isArray(item) || typeof item.method !== 'string' || !Object.hasOwn(methods, item.method) || typeof item.required !== 'boolean') throw new Error('완료조건의 확인 방법과 필수 여부를 확인하세요.');
      const description = text(item.description, 500, '완료조건 ' + (index + 1), changes);
      if (!description) throw new Error('빈 완료조건을 삭제하거나 내용을 입력하세요.');
      return { id: 'C' + (index + 1), description: description, method: item.method, required: item.required };
    });
  }
  function scope(value, sourceType, changes) {
    const selected = value === undefined ? { mode: sourceType === 'new' ? 'new' : 'preserve', scope: '' } : value;
    if (!selected || typeof selected !== 'object' || Array.isArray(selected) || typeof selected.mode !== 'string' || !Object.hasOwn(modes, selected.mode) || (sourceType === 'new') !== (selected.mode === 'new')) throw new Error('디자인 변경 범위를 다시 선택하세요.');
    const details = text(selected.scope === undefined ? '' : selected.scope, 1000, '디자인 변경 범위', changes);
    if (selected.mode === 'partial' && !details) throw new Error('부분 수정할 화면·요소·속성을 입력하세요.');
    return { mode: selected.mode, scope: selected.mode === 'preserve' ? '' : details };
  }
  function direction(value) {
    if (!value || !modes[value.mode]) return '이전 인계에 디자인 변경 범위가 없습니다. 변경 권한을 추정하지 말고 기존 요청을 확인하세요.';
    const common = '디자인 선택은 데이터 삭제나 요청 밖 기능 변경 권한을 포함하지 않습니다.';
    if (value.mode === 'preserve') return '기존 디자인 유지: 기존 컴포넌트·색상·글꼴·배치를 유지하세요. 요청 기능에 필요한 최소 UI 추가와 키보드 조작·레이블 보완만 기존 규칙으로 적용하세요. 관련 없는 화면의 디자인 변경은 허용하지 않습니다. 기존 모습과 필수 접근성 조건이 충돌하면 보고하세요. ' + common;
    if (value.mode === 'partial') return '부분 디자인 수정: ' + value.scope + '\n지정한 화면·요소·속성에만 디자인 지침을 적용하고 나머지 기존 디자인은 유지하세요. ' + common;
    return modes[value.mode] + ': ' + (value.scope || '요청에서 정한 UI 범위') + '. ' + common;
  }
  function guidance(value) {
    return ['요청한 기능과 제약사항을 실제 산출물로 확인하고 실행한 검사·미실행 항목과 결과를 보고하세요.',
      value.mode === 'preserve' ? 'UI 변경은 기존 화면과 비교하세요. 요청에 필요한 최소 변경 외에 색상·글꼴·레이아웃을 유지했는지 확인하세요.' : '허용한 UI 범위에서 선택한 디자인 지침과 참고 화면을 비교하고 모바일·데스크톱 차이를 확인하세요.'];
  }
  function apply(document, options, changes) {
    const settings = options || {};
    const changed = changes || [];
    const selectedScope = scope(settings.designScope, document.project.sourceType, changed);
    const selectedCriteria = criteria(settings.completionCriteria, changed);
    document.task.designScope = selectedScope;
    document.task.completionCriteria = selectedCriteria;
    document.task.validationGuidance = guidance(selectedScope);
    document.task.acceptanceCriteria = selectedCriteria.map(function (item) {
      return '[' + item.id + ' · ' + (item.required ? '필수' : '선택') + ' · ' + methods[item.method] + '] ' + item.description;
    });
    document.task.constraints = (document.task.constraints || []).concat([direction(selectedScope)]);
    if (selectedScope.mode === 'preserve') document.context.design = { included: false };
    document.inputReview = { required: changed.length > 0, fields: Array.from(new Set(changed)), acknowledged: false };
    return document;
  }
  function quality() {
    return { requirementsConfirmed: false, designConfirmed: false, sourceHandlingConfirmed: false, privacyChecked: false,
      ragReviewed: false, continuationReviewed: false,
      automaticRedaction: { applied: true, scope: 'known-sensitive-patterns', guaranteesAbsence: false },
      userConfirmation: { status: 'not-performed', scope: [] }, independentSecurityVerification: { status: 'not-performed' } };
  }
  global.VASTaskPolicy = Object.freeze({ apply: apply, text: text, criteria: criteria, scope: scope, direction: direction, quality: quality });
})(window);
