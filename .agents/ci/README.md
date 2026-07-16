# CI

GitHub Actions는 Python 검증, Playwright 검증, 재현 가능한 패키지 검증을 수행합니다. Pages와 Release는 `scripts/build_release.py`가 만든 산출물만 배포하며 `workspace/`, 백업, 캐시, 환경 변수는 포함하지 않습니다.
