# CI/CD 파이프라인 템플릿

이 디렉터리는 프로젝트의 CI/CD 파이프라인 템플릿을 저장합니다.
`/setup-from-application` 실행 시 프로젝트에 맞는 파이프라인이 자동 생성됩니다.

---

## GitHub Actions 예시

`프로젝트루트/.github/workflows/ci.yml`로 복사하여 사용합니다.

```yaml
name: CI Pipeline

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Python 프로젝트
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Lint (500줄 체크 포함)
        run: |
          # 500줄 초과 파일 체크
          find src/ -name "*.py" | while read f; do
            lines=$(wc -l < "$f")
            if [ "$lines" -gt 500 ]; then
              echo "ERROR: $f exceeds 500 lines ($lines)"
              exit 1
            fi
          done

      - name: Test
        run: python -m pytest tests/ -v --cov=src --cov-report=term-missing

      - name: Security scan
        run: |
          pip install bandit safety
          bandit -r src/ -f json -o security_report.json || true
          safety check --json > dependency_report.json || true
```

---

## Docker 배포 예시 (Synology NAS)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY final/src/ ./src/
COPY final/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "src.main"]
```

---

## 적용 방법
1. 프로젝트에 맞는 템플릿을 선택하여 복사
2. 환경 변수와 경로를 프로젝트에 맞게 수정
3. `final/`의 파일만 배포 대상에 포함

> CI/CD 파이프라인에서도 에이전트 팀의 **500줄 제한**과 **민감 데이터 체크**를 자동화합니다.
