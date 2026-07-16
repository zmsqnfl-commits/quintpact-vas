"""이전 명령과의 호환성을 위한 단일 무결성 검사 래퍼입니다."""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(BASE, 'tests', 'test_integrity.py')

print('[NOTICE] test_integrity_10loop.py는 호환 래퍼입니다. test_integrity.py를 실행합니다.')
result = subprocess.run([sys.executable, SCRIPT], cwd=BASE)
sys.exit(result.returncode)
