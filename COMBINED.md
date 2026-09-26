# Combined repository

© 1993–2026 Abhishek Choudhary. All rights reserved.  ·  AyeAI

| Path | Role |
|---|---|
| `python/panini` | Canonical compiler, simulator, debugger |
| `examples/` | Golden programs — one copy |
| `workstation/` | GitHub Pages demonstrator |
| `src/` | Rust contract sketch |
| `docs/v0.3.md` | Milestone notes |
| `NAME.md` | Naming decision still required |
| `python/tests/` | Vertical + simulator + conformance |
| `seed.sh` | Stage and verify by execution |

```bash
./seed.sh
python3 panini compile examples/mouse_axial.panini -o /tmp/mouse.compile.json
```

Expected for the golden two-tail program:

- compilation PASS
- simulation PASS
- target UNSATISFIED (`tail_count` declared 2, predicted 1)
- overall UNSATISFIED
