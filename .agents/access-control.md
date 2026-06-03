# 🔐 접근 제어 정책 — RBAC + ABAC 하이브리드

이 문서는 에이전트 팀의 **접근 제어 정책**을 정의합니다.
`/setup-from-application` 실행 시 프로젝트 특성에 맞게 자동 커스터마이징됩니다.

---

## 1. 접근 제어 모델 선택 기준

| 프로젝트 특성 | 적용 모델 | 이유 |
|-------------|----------|------|
| 단순 스크립트/유틸리티 (1~3명) | **RBAC only** | 역할 고정, 컨텍스트 변화 없음 |
| 멀티 환경 (dev/staging/prod) | **ABAC 추가** | 환경별 권한 차등 필요 |
| 민감 데이터 처리 (의료/금융) | **ABAC 강화** | 데이터 분류 등급별 접근 제한 |
| 다수 에이전트 + 복합 워크플로우 | **하이브리드** | 기본 RBAC + 조건부 ABAC 오버라이드 |
| 대부분의 일반 SW 프로젝트 | **하이브리드 (기본)** | RBAC + 핵심 ABAC 정책 3~5개 |

> **현재 프로젝트 적용 모델:** [하이브리드 (기본)] ← `/setup-from-application` 시 자동 결정

---

## 2. RBAC 레이어 — 역할 기반 정적 권한

에이전트의 **역할(Role)**에 따라 도구·경로 접근을 정의합니다.

### 역할별 권한 매트릭스

| 에이전트 | 파일 읽기 | 파일 쓰기 | 터미널 실행 | 브라우저 | `final/` 쓰기 | 자동 승인 |
|----------|:---------:|:---------:|:-----------:|:--------:|:-------------:|:---------:|
| **Architect** | ✅ 전체 | ❌ | ❌ | ✅ (리서치) | ❌ | ❌ |
| **Designer** | ✅ 전체 | ✅ `src/assets/`, `.temp data/` | ❌ | ✅ (리서치/Figma) | ❌ | ❌ |
| **Implementer** | ✅ 전체 | ✅ `src/`, `.temp data/` | ✅ (빌드/실행) | ❌ | ❌ | ❌ |
| **Reviewer** | ✅ 전체 | ❌ (코멘트만) | ✅ (린트/분석) | ❌ | ❌ | ❌ |
| **Tester** | ✅ 전체 | ✅ `tests/`, `.temp data/` | ✅ (테스트) | ❌ | ❌ | ❌ |
| **Security** | ✅ 전체 | ✅ `final/`, `HISTORY.md`, `LESSONS.md` | ✅ (보안 스캔) | ❌ | ✅ | ❌ |

### RBAC → SKILL.md 매핑

각 에이전트의 SKILL.md YAML에 아래와 같이 반영됩니다:

```yaml
# 예시: Designer
allowed_tools: [view_file, write_to_file, replace_file_content, multi_replace_file_content, grep_search, list_dir, search_web, browser_subagent, generate_image]
denied_tools: [run_command]
allowed_write_paths: ["src/assets/*", ".temp data/*"]
denied_write_paths: ["src/core/*", "src/ui/*", "src/utils/*", "final/*", "tests/*", ".agents/*", "INSTRUCTIONS.md", "GEMINI.md"]

# 예시: Implementer
allowed_tools: [view_file, write_to_file, replace_file_content, multi_replace_file_content, run_command, grep_search, list_dir]
denied_tools: [search_web, browser_subagent]
allowed_write_paths: ["src/*", ".temp data/*"]
denied_write_paths: ["final/*", "tests/*", ".agents/*", "INSTRUCTIONS.md", "GEMINI.md"]
```

---

## 3. ABAC 레이어 — 속성 기반 동적 정책

RBAC 위에 **속성(Attribute)**을 기반으로 동적으로 권한을 조정합니다.

### 속성 카테고리

| 속성 카테고리 | 속성 예시 | 설명 |
|-------------|----------|------|
| **워크플로우** | `workflow`, `workflow_step`, `severity` | 현재 진행 중인 워크플로우와 단계 |
| **데이터** | `file_pattern`, `data_classification` | 파일 경로 패턴, 데이터 민감도 등급 |
| **리소스** | `file_lines`, `file_type` | 파일 크기, 파일 유형 |
| **환경** | `environment`, `deploy_target` | 개발/스테이징/프로덕션 환경 |
| **시간** | `expiry`, `session_duration` | 권한 만료 시점, 세션 지속 시간 |

### ABAC 정책 목록

```yaml
abac_policies:

  # 정책 1: 긴급 수정 시 권한 상승
  - name: "hotfix_escalation"
    description: "긴급 수정(P0) 시 Implementer에게 임시 확장 권한 부여"
    condition:
      workflow: hotfix
      severity: P0
    effect: allow
    override:
      implementer:
        allowed_write_paths: ["src/*", "final/*"]
        auto_approve: true
    expiry: "workflow_end"

  # 정책 2: 민감 데이터 보호
  - name: "sensitive_data_guard"
    description: "민감 데이터 포함 파일에 대한 추가 제한"
    condition:
      file_pattern: ["**/credentials*", "**/secrets*", "**/.env*", "**/config/prod*"]
    effect: deny
    target: [designer, implementer, tester]
    action: [write_to_file, replace_file_content, run_command]

  # 정책 3: 리뷰 전 final/ 차단
  - name: "review_before_final"
    description: "Reviewer·Tester 통과 전 final/ 쓰기 차단"
    condition:
      workflow_step: "< step_5_security"
    effect: deny
    target: [all]
    action: [write_to_file]
    path: ["final/*"]

  # 정책 4: 대형 파일 수정 시 승인 필요
  - name: "large_file_alert"
    description: "400줄 초과 파일 수정 시 Reviewer 승인 필요"
    condition:
      file_lines: "> 400"
    effect: require_approval
    target: [implementer]
    approver: reviewer

  # 정책 5: 프로덕션 설정 파일 잠금
  - name: "prod_config_lock"
    description: "프로덕션 설정 파일은 Security만 수정 가능"
    condition:
      file_pattern: ["**/config/prod*", "**/deploy/prod*"]
    effect: deny
    target: [architect, designer, implementer, reviewer, tester]
    action: [write_to_file, replace_file_content]
```

---

## 4. 정책 평가 순서

```
요청 → RBAC 기본 권한 확인 → ABAC 정책 평가 → 최종 판정

1. RBAC에서 허용? → No → 즉시 차단 (ABAC 평가 안 함)
2. RBAC에서 허용? → Yes → ABAC 정책 중 deny가 있는가?
   2a. deny 있음 → 차단 + 사용자 보고
   2b. deny 없음 → ABAC에 require_approval이 있는가?
       2b-i.  있음 → 승인 대기
       2b-ii. 없음 → ABAC에 allow 오버라이드가 있는가?
              있음 → 확장 권한으로 허용
              없음 → RBAC 기본 권한으로 허용
```

---

## 5. 위반 시 처리 규칙

1. 에이전트가 권한 밖 작업을 시도하면 → **즉시 중단** 후 사용자에게 보고
2. `/hotfix` 워크플로우에서는 ABAC `hotfix_escalation` 정책으로 **임시 권한 상승** 가능
3. 모든 권한 변경/위반 이력은 `HISTORY.md`에 기록
4. 임시 권한은 워크플로우 종료 시 자동 만료
