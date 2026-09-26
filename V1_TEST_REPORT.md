# PANINI v1.0 test report

Date: 2026-09-26
Compiler: 1.0.0

## Command

```
python3 -m unittest discover -s python/tests -p 'test_*.py'
```

## Result

164 passed, 0 failed, 0 skipped.

## Suites

| Suite | Role |
|---|---|
| test_vertical.py | v0.1–v0.3 slice |
| test_simulator_debugger.py | simulator / debugger |
| test_conformance.py | IR conformance |
| test_v04.py | geometry / two-axis |
| test_architecture.py | Core / domain split |
| test_genotype_compiler.py | sequence compiler |
| test_v07_resolution.py | resolution + knowledge growth |
| test_v08_core.py | dual path / providers |
| test_v09_engines.py | engines |
| test_v10_platform.py | v1.0 cases A–G |

Unavailable capabilities (reported, not failed): GPU kernel.
Scientifically unresolved capabilities (reported, not failed): two-tail genotype.
