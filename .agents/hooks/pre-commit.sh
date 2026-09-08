#!/bin/bash
# pre-commit 훅 — 커밋 전 자동 검증
# 이 파일을 .git/hooks/pre-commit으로, check-staged.py를 같은 폴더로 복사하세요.
# /setup-from-application 실행 시 프로젝트에 맞게 커스터마이징됩니다.

echo "[Pre-Commit] 커밋 전 검증 시작..."

# 1. 500줄 제한 체크
OVER_LIMIT=$(find src/ -name "*.py" -o -name "*.js" -o -name "*.ts" | while read f; do
    lines=$(wc -l < "$f")
    if [ "$lines" -gt 500 ]; then
        echo "$f: ${lines}줄"
    fi
done)

if [ -n "$OVER_LIMIT" ]; then
    echo "[BLOCKED] 500줄 초과 파일 발견:"
    echo "$OVER_LIMIT"
    exit 1
fi

# 2. 민감 데이터 패턴 체크 (ABAC sensitive_data_guard)
HOOK_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd) || exit 2
if command -v python3 >/dev/null 2>&1; then PYTHON=python3; else PYTHON=python; fi
"$PYTHON" "$HOOK_DIR/check-staged.py" || exit $?

echo "[Pre-Commit] 검증 통과 ✓"
exit 0
