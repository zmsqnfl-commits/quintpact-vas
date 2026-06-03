#!/bin/bash
# pre-commit 훅 — 커밋 전 자동 검증
# 이 파일을 .git/hooks/pre-commit 으로 복사하세요.
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
SENSITIVE=$(git diff --cached --name-only | xargs grep -l -E "(password|secret|api_key|private_key)\s*=" 2>/dev/null)
if [ -n "$SENSITIVE" ]; then
    echo "[WARNING] 민감 데이터 패턴 발견:"
    echo "$SENSITIVE"
    echo "계속하려면 SKIP_SENSITIVE=1 git commit 사용"
    if [ "$SKIP_SENSITIVE" != "1" ]; then
        exit 1
    fi
fi

echo "[Pre-Commit] 검증 통과 ✓"
exit 0
