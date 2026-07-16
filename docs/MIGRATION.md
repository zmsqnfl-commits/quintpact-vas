# 마이그레이션 정책

VAS 2.6.0은 기존 프로그램을 `workspace/projects/`에 안전하게 흡수하고, 원본은 기본적으로 보존합니다.

## 단계

1. **선택**: 사용자가 원본 프로젝트 폴더를 직접 선택합니다.
2. **분석**: 읽기 전용으로 기술 스택, Git, 용량, 파일 수, 의존성, 의심 파일을 확인합니다.
3. **승인**: 대상 이름, 제외 항목, Git 보존, RAG 색인 여부와 가져온 뒤 할 일을 사용자가 확인합니다.
4. **체크포인트**: 파일 목록·SHA-256과 복구 자료를 생성합니다.
5. **복제**: 임시 staging으로 복사하고 검증한 뒤 대상 폴더로 원자적으로 승격합니다.
6. **등록**: 프로젝트 목록과 선택한 지식 색인에 연결하고 관리·개선·리디자인·업그레이드 목적에 맞는 다음 화면을 엽니다.
7. **검증**: 원본 불변, 대상 해시, 진입점, 의존성 안내를 확인합니다.

## 안전 경계

- 분석 중 프로젝트 파일을 실행하지 않습니다.
- `.git`, 의존성 폴더, 비밀 후보는 보고서에 별도 표시합니다.
- 심볼릭 링크와 대상 폴더 밖으로 나가는 경로는 차단합니다.
- 같은 이름의 대상이 있으면 덮어쓰지 않습니다.
- 원본 삭제는 기본 흐름에 없고 별도 확인 문구가 필요합니다.

## CLI

```powershell
python scripts/vas-project-import.py analyze "C:\path\old-project"
python scripts/vas-project-import.py import "C:\path\old-project" --name my-project
python scripts/vas-project-import.py rollback <job-id>
```

정확한 옵션은 `python scripts/vas-project-import.py --help`로 확인합니다. 일반 사용자는 허브의 **기존 프로젝트 가져오기**를 사용합니다.
