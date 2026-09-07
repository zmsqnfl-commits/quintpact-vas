#!/usr/bin/env bash
set -euo pipefail
vas_check_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
exec python "$vas_check_root/scripts/agent_checks.py" after "$@"
