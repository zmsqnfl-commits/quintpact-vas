# 템플릿 버전 마이그레이션 가이드

이 문서는 **에이전트 팀 템플릿**의 버전 업그레이드 시 기존 프로젝트에 변경 사항을 적용하는 방법을 안내합니다.

---

## 마이그레이션 원칙

1. **CONTEXT.md, INSTRUCTIONS.md** — 프로젝트별 내용이 포함되므로 **수동 머지** 필요
2. **SKILL.md (6개)** — YAML 프론트매터 변경 시 **주의하여 갱신** (프로젝트별 커스터마이즈 영역 보존)
3. **워크플로우 (.md)** — 프로젝트 독립적이므로 **직접 교체** 가능
4. **스크립트 (.sh/.ps1)** — 프로젝트별 커스터마이즈가 있으면 **수동 머지**, 없으면 교체
5. **access-control.md, advisor-strategy.md** — 프로젝트별 정책이 있으면 수동 머지

---

## 버전별 마이그레이션 절차

### v2.0 → v2.1

| 파일 | 액션 | 설명 |
|------|------|------|
| 5개 SKILL.md | YAML 수정 | `read_file` → 삭제, ABAC 자가 진단 섹션 추가 |
| dev-cycle.md | 교체 | 경량 모드, 반려 포맷, 롤백 절차 추가 |
| hotfix.md | 교체 | 반려 포맷 추가 |
| setup-from-application.md | 교체 | Step 4.5 스캐폴딩, Step 6 검증 추가 |
| CONTEXT.md | 수동 머지 | "현재 진행 상태" + "충돌 규칙" 섹션 추가 |
| INSTRUCTIONS.md | 수동 머지 | 섹션 5.1/5.2/7/8 추가 |
| .ps1 스크립트 4개 | 신규 복사 | Windows 호환 스크립트 |
| src/README.md, tests/README.md | 신규 복사 | 스캐폴딩 |
| .gitignore | 신규 복사 | |

### v2.1 → v2.2

| 파일 | 액션 | 설명 |
|------|------|------|
| dev-cycle.md | 교체 | 각 Step에 진입 조건 + LESSONS 기록 안내 추가 |
| hotfix.md | 교체 | 진입 조건 + LESSONS 기록 안내 추가 |
| ultra-plan.md | 교체 | GEMINI 시작/종료 + LESSONS 기록 안내 추가 |
| setup-from-application.md | 교체 | GEMINI 종료 + LESSONS 스캐폴딩 + 참조 문서 갱신 |
| dep-update.md | 신규 복사 | 의존성 업데이트 워크플로우 |
| CUSTOM_GUIDE.md | 신규 복사 | 커스텀 워크플로우 작성 가이드 |
| LESSONS.md | 신규 복사 | 교훈 축적 시스템 |
| MIGRATION.md | 신규 복사 | 이 파일 (마이그레이션 가이드) |
| INSTRUCTIONS.md | 수동 머지 | 섹션 9(코드 소유권), 10(GEMINI 최적화), 11(멀티프로젝트) |
| CONTEXT.md | 수동 머지 | 참조 문서에 LESSONS/MIGRATION 추가, RBAC에 LESSONS 추가 |
| access-control.md | 수동 머지 | Security RBAC에 LESSONS.md 쓰기 추가 |
| Security SKILL.md | YAML 수정 | `allowed_write_paths`에 LESSONS.md 추가 |
| .agents/hooks/ | 신규 복사 | Git 훅 템플릿 |
| .agents/ci/ | 신규 복사 | CI/CD 템플릿 |

### v2.2 → v2.3

| 파일 | 액션 | 설명 |
|------|------|------|
| `.agents/skills/designer/SKILL.md` | **신규 복사** | Designer 에이전트 스킬 (Claude Design 기반) |
| `.agents/skills/designer/references/README.md` | **신규 복사** | Claude Design 활용 가이드, Figma 연동 패턴 |
| `src/assets/README.md` | **신규 복사** | Designer 작업 공간 안내 |
| `access-control.md` | **수동 머지** | RBAC 테이블에 Designer 행, ABAC target에 designer 추가 |
| `dev-cycle.md` | **교체** | Step 1.5 Designer 삽입, 디자인 반려 포맷, 유기적 상호 검증 |
| `hotfix.md` | **수동 머지** | Designer 생략 명시 |
| `setup-from-application.md` | **교체** | 3-10 Designer 스킬 생성, Step 4 리소스 테이블, 파일 수 10개 |
| `CONTEXT.md` | **수동 머지** | RBAC 요약 테이블에 Designer 행 추가 |
| `INSTRUCTIONS.md` | **수동 머지** | 코드 소유권, 폴더 구조, 라이프사이클, 커밋 메시지에 Designer 반영 |
| `README.md` | **교체** | 전체 시스템 가이드로 재작성 (에이전트 역할, 워크플로우, 접근 제어 등) |
| Architect SKILL.md | **수동 머지** | 인계 대상을 Designer(UI 변경 시) 또는 Implementer로 변경 |
| Implementer SKILL.md | **수동 머지** | 작업 완료 기준에 디자인 명세 준수 체크 추가 |
| Reviewer SKILL.md | **수동 머지** | 디자인 명세 일치 검토 항목 추가 |
| `reviewer/references/checklist.md` | **수동 머지** | 디자인 명세 검토 섹션 추가 |
| `advisor-strategy.md` | **수동 머지** | Designer Advisor 시나리오 추가 |
| `mcp_config_template.json` | **수동 머지** | Figma MCP 서버 설정 예시 추가 |
| `src/README.md` | **수동 머지** | Designer `src/assets/` 쓰기 권한, 구조에 assets/ 추가 |
| `LESSONS.md` | **수동 머지** | `#디자인` 태그 추가 |
| `HISTORY.md` | **이력 추가** | v2.3 변경 이력 + 후속 보완 이력 |
| `MIGRATION.md` | **이력 추가** | 이 섹션 (v2.2→v2.3 절차) |

### v2.3 → v2.4

| 파일 | 액션 | 설명 |
|------|------|------|
| `CONTEXT.md` | **수동 머지** | Auto-Orchestrator Protocol 추가, 자연어 워크플로우 매핑 규칙 추가, Final-Centric 라이프사이클 언급, 참조 문서에 `docs/index.md` · `docs/HANDOFF.md` 추가 |
| `INSTRUCTIONS.md` | **수동 머지** | Andrej Karpathy 4대 코딩 원칙 통합, Taste-Skill 디자인 가이드 추가 |
| `docs/HANDOFF.md` | **신규 복사** | 에이전트 인계 전용 문서 (다음 세션 시작 시 최우선 읽기) |
| `docs/index.md` | **신규 복사** | Wiki SSoT (프로젝트 현황, 아키텍처, 위키 링크) |
| `docs/log.md` | **신규 복사** | 통합 연대기 (기존 `HISTORY.md` + `LESSONS.md` 합본) |
| `docs/design-system.md` | **신규 복사** | 디자인 시스템 명세 |
| `HISTORY.md` | **삭제** | `docs/log.md`로 통합됨 |
| `LESSONS.md` | **삭제** | `docs/log.md`로 통합됨 |
| `dev-cycle.md` | **교체** | Step 0 마이크로 백업 추가, Step 6 Wiki 업데이트 + 로그 압축(Log Condensation) 추가, Auto-Orchestrator 주의사항, Tester Bypass 경량 룰 |
| `migration-cycle.md` | **교체** | Step 0 프로젝트 인식 추가, VAS 인프라 보존 목록 명시, Auto-Orchestrator 연동 |
| `hotfix.md` | **수동 머지** | Auto-Orchestrator 주의사항 추가 |
| `setup-from-application.md` | **교체** | Auto-Orchestrator 템플릿 주입, Tester Bypass 룰 포함 |
| `index.html` | **교체** | 허브 페이지 전체 리뉴얼 (Neo-Brutalism 카드 레이아웃) |
| `design-controller.html` | **교체** | AI 에이전트 시스템 프롬프트 생성기 통합, 12개 프리셋 prompt 필드 추가 |
| `design-controller.css` | **신규 복사** | 디자인 컨트롤러 전용 스타일 (HTML에서 분리) |
| `client-application.html` | **교체** | 의뢰서 폼 전체 리뉴얼 (인라인 스크립트 제거) |
| `client-application-init.js` | **신규 복사** | 테마 토큰 초기화 + Pretendard 폴백 JS |
| `client-form.js` | **신규 복사** | 폼 네비게이션 + 드래그앤드롭 로직 |
| `client-export.js` | **신규 복사** | JSON 내보내기 로직 |
| `client-i18n.js` | **신규 복사** | 한/영 다국어 번역 데이터 |
| `client-style.css` | **교체** | 의뢰서 폼 메인 스타일 (@import 체인) |
| `client-components.css` | **신규 복사** | 드래그존/파일칩/버튼 컴포넌트 |
| `client-print.css` | **신규 복사** | 인쇄 모드 스타일 |
| `Run-VAS-System.bat` | **교체** | Python HTTP 서버 → 브라우저 자동 실행으로 변경 |
| `Run-VAS-Backup.bat` | **신규 복사** | 마이크로 백업 런처 |
| `vas-backup.py` | **신규 복사** | ZIP 체크포인트 백업 스크립트 (UTF-8 stdout) |
| `tests/test_integrity_10loop.py` | **신규 복사** | 98건 10-Loop 무결성 검증 |
| `tests/test_dryrun_10scenarios.py` | **신규 복사** | 149건 드라이런 파이프라인 검증 |

---

## 기존 프로그램 흡수 (Migration-Cycle 퀵 가이드)

VAS 2.4를 **템플릿/인프라로 유지**하면서 기존 프로그램을 관리하고 싶을 때:

```
1. 채팅창에 "/migration-cycle" + 원본 프로젝트 경로 입력
2. AI가 원본 → .temp data/프로젝트명_backup.zip 아카이빙 → final/ 배치 자동 수행
3. 원본 폴더 삭제 확인 (선택 — y/N 프롬프트)
4. AI가 Step 0~6을 자동으로 완주 → 끝
```

> **수동 방식도 가능:** 기존처럼 파일을 `final/`에 직접 넣고 `/migration-cycle` 호출하면 Step -1을 건너뛰고 Step 0부터 시작합니다.

> 상세 절차: `.agents/workflows/migration-cycle.md` 참조

---

## 마이그레이션 체크리스트

프로젝트에 새 템플릿 버전을 적용할 때 아래를 순서대로 확인합니다:

- [ ] 새 버전의 MIGRATION.md에서 해당 버전 섹션 확인
- [ ] "교체" 파일은 새 템플릿에서 직접 복사
- [ ] "수동 머지" 파일은 diff 비교 후 프로젝트 고유 내용 보존하며 새 섹션 추가
- [ ] "신규 복사" 파일은 새 템플릿에서 복사 후 프로젝트에 맞게 커스터마이즈
- [ ] "삭제" 파일은 백업 후 제거 (내용이 다른 파일로 통합되었는지 확인)
- [ ] `docs/log.md`에 마이그레이션 이력 기록
- [ ] 전체 워크플로우 참조 경로가 정상인지 확인
- [ ] `tests/test_integrity_10loop.py` 실행하여 무결성 검증

---

## 향후 버전 추가 시

이 파일의 "버전별 마이그레이션 절차" 섹션에 새 항목을 추가합니다.
형식: `### vX.Y → vX.Z` + 파일별 액션 테이블

