"""
VAS 2.4 - 드라이런 10-시나리오 연속 10회 스트레스 테스트
"""
import subprocess, sys, io, time, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(BASE, 'tests', 'test_dryrun_10scenarios.py')
results = []

print('=' * 60)
print('  VAS 2.4 -- 드라이런 10-시나리오 x 10회 스트레스 테스트')
print('=' * 60)
print()

for i in range(1, 11):
    start = time.time()
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    elapsed = time.time() - start
    total_line = [l for l in proc.stdout.splitlines() if 'TOTAL:' in l]
    info = total_line[0].strip() if total_line else 'PARSE ERROR'
    passed = proc.returncode == 0
    status = 'PASS' if passed else 'FAIL'
    results.append((i, status, elapsed, info))
    icon = '[O]' if passed else '[X]'
    print(f'  Round {i:2d}/10: {icon} {elapsed:.2f}s | {info}')

print()
print('=' * 60)
print('  최종 집계')
print('=' * 60)

pass_count = sum(1 for r in results if r[1] == 'PASS')
fail_count = sum(1 for r in results if r[1] == 'FAIL')
avg_time = sum(r[2] for r in results) / len(results)

print(f'  총 라운드: 10 | PASS: {pass_count} | FAIL: {fail_count}')
print(f'  총 검증 항목: {pass_count * 149} (149 x {pass_count})')
print(f'  평균 실행 시간: {avg_time:.2f}s')

if fail_count > 0:
    print()
    print('  실패 라운드:')
    for r in results:
        if r[1] == 'FAIL':
            print(f'    Round {r[0]}: {r[3]}')

print()
if pass_count == 10:
    print('  *** 10/10 드라이런 풀 파이프라인 연속 무결점 통과 ***')
else:
    print(f'  !!! {fail_count}회 실패 -- 불안정 요소 존재')
print('=' * 60)

sys.exit(0 if fail_count == 0 else 1)
