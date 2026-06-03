# tests/ — 테스트 코드 폴더

이 폴더는 **Tester 에이전트가 테스트 코드를 작성하는 공간**입니다.

## 규칙
- Tester만 이 폴더에서 파일을 생성/수정합니다.
- `src/`의 디렉터리 구조를 **미러링**합니다.
- 테스트 실패 시 소스 코드를 직접 수정하지 않고 Implementer에게 인계합니다.

## 구조 미러링 규칙

| 소스 파일 | 테스트 파일 |
|-----------|-----------|
| `src/core/engine.py` | `tests/core/test_engine.py` |
| `src/ui/sidebar.py` | `tests/ui/test_sidebar.py` |
| `src/utils/helpers.py` | `tests/utils/test_helpers.py` |

### 명명 규칙
- Python: `test_` 접두사 (`test_모듈명.py`)
- JavaScript: `.test.` 접미사 (`모듈명.test.js`)

## 커버리지 목표
- 기본: **80% 이상**
- `/setup-from-application` 실행 시 프로젝트 규모에 맞게 조정됩니다.

## 주요 실행 명령
- `npm run test:design-preview` — 디자인 스튜디오 preset token preview 회귀 테스트
- `npm run test:browser` — 브라우저 스모크 전체 실행
