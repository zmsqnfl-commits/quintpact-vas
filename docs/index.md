# VAS 2.6.3 시스템 지도

## 사용자 흐름

```text
Run-VAS-System.bat
  -> 시작 화면
     -> 새 프로젝트 -> 요구사항 -> 디자인 -> VAS-AI-HANDOFF.json
     -> 기존 프로그램 -> 읽기 전용 분석 -> 디자인 -> VAS-AI-HANDOFF.json
  -> 코딩 도구에서 작업 폴더 + JSON + 복사한 프롬프트 사용
```

VAS 웹 화면은 JSON을 만들 때만 사용합니다. 프로젝트 대시보드나 계속 작업 목록은 제공하지 않습니다.

## 구성

| 영역 | 역할 | 기준 파일 |
|---|---|---|
| 시작 | 두 가지 시작 방식 선택 | `src/vas-hub.html` |
| 새 프로젝트 | 요구사항·디자인·통합 JSON | `src/client-application.html` |
| 기존 프로그램 | 폴더 분석·통합 JSON | `src/project-import.html` |
| 공통 도움말·설정 | 작업 순서와 작업 기억 제어 | `src/setup-tools.js` |
| 디자인 | 프리셋·토큰·에이전트 디자인 지침 | `src/design-controller.html` |
| JSON 계약 | 신규·기존 공통 문서 생성 | `src/agent-handoff-web.js`, `scripts/vas_agent_handoff.py` |
| 런타임 | 로컬 폴더 선택과 안전 분석 | `scripts/Start-VAS.ps1` |
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
- 최종 JSON에는 요구사항·디자인·프로젝트 구조·안전 규칙·AI 안내만 포함합니다.
- 파일은 500줄 이하로 유지합니다.
