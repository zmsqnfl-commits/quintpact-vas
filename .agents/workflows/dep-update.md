---
description: 보안 패치나 버전 범프 등 의존성만 변경할 때 사용하는 경량 워크플로우
---

# 워크플로우: 의존성 업데이트 (/dep-update)

기존 코드 수정 없이 **라이브러리 의존성만** 업데이트하는 경우 사용합니다.
`/dev-cycle`보다 경량이며, 설계(Architect)·디자인(Designer)·구현(Implementer) 단계를 단순화합니다.

## 실행 조건
- 보안 취약점 패치 (예: `safety check` 결과 대응)
- 라이브러리 메이저/마이너 버전 업그레이드
- 사용자가 `/dep-update` 슬래시 커맨드를 입력했을 때

> ⚠️ 의존성 변경으로 인해 **소스 코드 수정이 필요한 경우** → `/dev-cycle`로 전환합니다.

---

## Step 1. 변경 범위 파악

**담당:** Implementer

> **진입 조건:** 업데이트 대상 패키지명과 목표 버전이 명확함

1. 현재 의존성 파일(`requirements.txt` / `package.json`) 확인
2. 업데이트 대상 패키지와 목표 버전 확인
3. **사용자에게 변경 사항 확인** (핵심 규칙: 새 라이브러리 설치 전 반드시 확인)
4. 변경 이력(CHANGELOG) 확인하여 breaking changes 여부 판단
5. breaking changes 있으면 → `/dev-cycle`로 전환 (사용자 알림)
6. `GEMINI.md`의 "현재 진행 상태"를 업데이트한다: `활성 워크플로우: /dep-update Step 1`

---

## Step 2. 의존성 업데이트 실행

**담당:** Implementer
**RBAC:** `src/` 쓰기 (의존성 파일은 src/ 또는 루트)

> **진입 조건:** Step 1에서 breaking changes 없음 확인 + 사용자 승인

1. 의존성 파일에서 버전을 업데이트한다
2. 로컬에서 설치/빌드 테스트를 실행한다
3. import 에러나 호환성 문제가 없는지 확인한다

```
[인계] Implementer → Tester
- 완료: [패키지명] v[이전] → v[이후] 업데이트
- 변경 파일: [의존성 파일명]
- breaking changes: 없음
- 특이사항: [deprecated API 경고 등 / 없으면 '없음']
```

---

## Step 3. 테스트 검증

**담당:** Tester (context: fork)

> **진입 조건:** 의존성 업데이트 완료 + 빌드 성공

1. 기존 테스트 스위트를 **전체 실행**한다 (회귀 테스트)
2. 실패 시 → Implementer에게 반려, `/dev-cycle`로 전환 판단
   - ⚠️ **반복 제한:** 최대 **1회**. 재실패 시 사용자 에스컬레이션.
3. 통과 시 아래 형식으로 Security에게 인계

```
[인계] Tester → Security
- 완료: 회귀 테스트 통과
- 테스트 결과: [통과/실패 케이스 수]
- 특이사항: [deprecated 경고 등 / 없으면 '없음']
```

---

## Step 4. 보안 검토 + final/ 배포

**담당:** Security (context: fork)

> **진입 조건:** 모든 기존 테스트 통과

1. 업데이트된 패키지의 알려진 취약점 확인 (`safety check` / `npm audit`)
2. 통과 시 의존성 파일을 `final/`에 복사
3. `docs/log.md`에 업데이트 이력 기록

```markdown
## [날짜] [DEP-UPDATE] [패키지명]
- 변경 내용: [패키지명] v[이전] → v[이후]
- 사유: [보안 패치 / 기능 개선 / 호환성]
- 테스트: 전체 회귀 테스트 통과
- 최종 파일: final/[의존성 파일명]
```

4. `GEMINI.md`의 "현재 진행 상태"를 업데이트하여 워크플로우 종료를 기록한다.
5. 호환성 이슈 등 교훈이 있으면 `docs/log.md`에 함께 기록한다.
