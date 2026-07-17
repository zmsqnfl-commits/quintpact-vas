# VAS 2.6.3

VAS는 `설정 → VAS-AI-HANDOFF.json 생성 → 코딩 AI 전달`을 위한 로컬 도구입니다.

## 사용 방법

1. ZIP을 새 폴더에 전부 압축 해제합니다.
2. `Run-VAS-System.bat`를 더블클릭합니다.
3. **새 프로젝트 만들기** 또는 **기존 프로그램 AI로 연결**을 고릅니다.
4. 화면 질문에 답하고 `VAS-AI-HANDOFF.json`을 저장합니다.
5. Codex·Claude·Antigravity에서 작업할 폴더를 열고 JSON을 첨부한 뒤 복사한 프롬프트를 붙여넣습니다.

JSON을 만든 뒤에는 VAS를 닫아도 됩니다. 화면 위의 **사용 방법**과 **설정**은 어느 단계에서든 다시 열 수 있습니다.

기존 프로그램 분석은 원본을 실행·수정·삭제하지 않습니다. 절대 경로, 비밀값, 연락처, 작업 기억 원본은 JSON에서 제외합니다. `작업 기억`은 선택 기능이며 설정에서 언제든 끄거나 삭제할 수 있습니다.

자세한 설명은 [`00-처음-사용하기.txt`](00-처음-사용하기.txt), 시스템 구조는 [docs/index.md](docs/index.md)를 확인하세요.

## 검증·배포

```powershell
npm.cmd run knowledge:index
npm.cmd run test:python
npm.cmd run test:browser
npm.cmd run test:package
```

10회 스트레스 검사는 명시적으로 필요할 때만 `npm.cmd run test:release`로 실행합니다.
