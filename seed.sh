#!/usr/bin/env bash
# Canonical reproducibility command for PANINI v1.0.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "PANINI genetic compiler v1.0 — staging $ROOT"
python3 -m compileall -q python/panini
python3 -m unittest discover -s python/tests -p 'test_*.py'
echo "OK"
