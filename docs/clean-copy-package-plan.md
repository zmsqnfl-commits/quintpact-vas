# 배포 패키지 기준

`python scripts/build_release.py`가 `dist/`에 아래 결과를 만듭니다.

- `VAS-2.6.4-windows.zip`: 로컬 서버·프롬프트 생성·선택형 작업 기억 포함 전체 실행본
- `VAS-Client-Form-2.6.4.zip`: 외부 공유용 독립 설정 폼
- `pages/`: GitHub Pages용 정적 허브
- `release-manifest.json`, `SHA256SUMS.txt`: 파일 목록과 검증 해시

`.git`, `workspace`, `dist`, 백업, 캐시, 테스트 결과, 환경 변수, 키 파일은 제외됩니다. 실행 시 필요한 `workspace/`는 로컬 런타임이 새로 만듭니다.
