#!/bin/bash
# AfterTool Hook — 도구 실행 후 로깅 및 검증
# /setup-from-application 실행 시 프로젝트에 맞게 커스터마이징됩니다.

echo "[AfterTool] 실행 완료: $TOOL_NAME on $TARGET_PATH (결과: $EXIT_CODE)"

# TODO: 프로젝트별 로깅/검증 로직 추가
# 예시:
# if [[ "$TOOL_NAME" == "write_to_file" ]]; then
#   FILE_LINES=$(wc -l < "$TARGET_PATH")
#   if [[ $FILE_LINES -gt 500 ]]; then
#     echo "[WARNING] $TARGET_PATH 가 ${FILE_LINES}줄로 500줄 제한을 초과합니다."
#   fi
# fi

exit 0
