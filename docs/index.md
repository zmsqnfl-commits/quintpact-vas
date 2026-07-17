# VAS 2.6.4 시스템 지도

## 사용자 흐름

```text
Run-VAS-System.bat
  -> 시작 화면
     -> 새 프로젝트 -> 요구사항 -> 디자인 -> 프롬프트 복사
     -> 기존 프로그램 -> 폴더 위치 -> 작업 작성 -> 디자인 -> 프롬프트 복사
  -> 코딩 도구에서 RBG 확인 후 실제 작업
```

VAS 웹 화면은 프롬프트와 선택 JSON을 만들 때만 사용합니다. 프로젝트 대시보드나 계속 작업 목록은 제공하지 않습니다.

## 구성

| 영역 | 역할 | 기준 파일 |
|---|---|---|
| 시작 | 두 가지 시작 방식 선택 | `src/vas-hub.html` |
| 새 프로젝트 | 요구사항·디자인·프롬프트와 선택 JSON | `src/client-application.html` |
| 기존 프로그램 | 폴더 위치·작업·디자인 프롬프트와 선택 JSON | `src/project-import.html` |
| 공통 도움말·설정 | 작업 순서와 작업 기억 제어 | `src/setup-tools.js` |
| 디자인 | 프리셋·토큰·에이전트 디자인 지침 | `src/design-controller.html` |
| 인계 계약 | 인계 v3 생성과 호환용 결과 v1 검증 | `src/agent-contract.js`, `src/handoff-workflow.js`, `scripts/vas_ai_contract.py` |
| 호환 모듈 | 결과 JSON 검증·RAG 검토(기본 UI 미노출) | `src/ai-result-import.js`, `src/handoff-context-review.js` |
| 런타임 | 로컬 웹 실행과 호환 API | `scripts/Start-VAS.ps1` |
| 배포 | Windows·독립 폼·Pages 생성 | `scripts/build_release.py` |

## 저장·호환

- 작업 기억: Windows 사용자 로컬 또는 브라우저 IndexedDB
- 디자인 설정: 브라우저 저장소와 URL 상태
- 체크포인트: `.vas_backups/` 최신 10개
- 배포물: `dist/`
- 기존 `workspace/` 프로젝트와 복사·등록 모듈은 삭제하지 않지만 기본 UI에는 노출하지 않습니다.

## 운영 원칙

- 모든 기능은 외부 CDN 없이 동작합니다.
- 저장소가 차단되거나 손상돼도 기본값으로 실행합니다.
- 작업 기억은 동의 없이 자동 활성화하지 않습니다.
- 최종 JSON에는 요구사항·디자인·안전 규칙·AI 안내만 포함하며 구조·기술 스택은 추정하지 않습니다.
- 기존 프로그램의 절대 경로는 복사 프롬프트에만 넣고 JSON·작업 기억에는 저장하지 않습니다.
- 기본 저장·복사는 인계 영수증을 만들지 않습니다.
- 호환용 반복 계약을 직접 사용할 때만 ID·해시·sourceType 일치를 필수로 검사합니다.
- 파일은 500줄 이하로 유지합니다.
