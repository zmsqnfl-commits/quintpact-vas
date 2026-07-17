"""VAS 2.6.2 명시적 릴리즈용 10회 무결성 스트레스 검사."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tests" / "test_integrity.py"
results: list[tuple[int, int, float]] = []

print("VAS 2.6.2 - 10회 무결성 스트레스 검사")
for round_number in range(1, 11):
    started = time.monotonic()
    process = subprocess.run([sys.executable, str(TEST)], cwd=ROOT, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    results.append((round_number, process.returncode, elapsed))
    print(f"Round {round_number:02d}/10: {'PASS' if process.returncode == 0 else 'FAIL'} ({elapsed:.2f}s)")
    if process.returncode:
        print(process.stdout)
        print(process.stderr, file=sys.stderr)

failures = [item for item in results if item[1]]
print(f"TOTAL: 10 | PASS: {10 - len(failures)} | FAIL: {len(failures)}")
raise SystemExit(1 if failures else 0)
