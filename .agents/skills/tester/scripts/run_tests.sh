#!/bin/bash
# 테스트 러너 스크립트 (Tester 에이전트용)
# /setup-from-application 실행 시 프로젝트에 맞게 커스터마이징됩니다.

# 사용법: 이 스크립트는 Tester 에이전트가 테스트 실행 시 참조합니다.

echo "[Test Runner] 테스트 실행 시작..."

# TODO: 프로젝트에 맞는 테스트 실행 명령 설정
# Python 프로젝트:
# python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Node.js 프로젝트:
# npm test -- --coverage

echo "[Test Runner] 테스트 완료."
