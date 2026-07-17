# 마이그레이션 호환 정책

VAS 2.6.3의 기본 마이그레이션은 원본 폴더를 코딩 도구에서 열고 `VAS-AI-HANDOFF.json`을 전달하는 방식입니다. VAS가 원본을 복사하거나 등록하지 않습니다.

이전 버전에서 만든 `workspace/projects/`와 백업·복제·검증·롤백 모듈은 데이터 호환을 위해 삭제하지 않습니다. 기본 UI에서는 노출하지 않으며 유지보수용 CLI에서만 사용할 수 있습니다.

```powershell
python scripts/vas-project-import.py --help
```

CLI 사용 시에도 원본 실행 금지, 링크 차단, 비밀값 제외, 백업 후 해시 검증 규칙을 유지합니다.
