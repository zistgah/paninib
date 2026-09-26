# Reproducibility

Canonical command:

```bash
./seed.sh
```

This command:

1. byte-compiles `python/panini`
2. runs `python3 -m unittest discover -s python/tests -p 'test_*.py'`

Requirements: Python 3.10+. No extra scientific Python stack is required
for the v1.0 reference engines.

Vertical slices are executed inside the test suite
(`digital_vertical_slice`, `physical_vertical_slice`, cases A–G).
