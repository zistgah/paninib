# PANINI architecture — Core / domain boundary

v0.8 completes backend contracts around the v0.7 Biological Resolution layer.
See `docs/v0.8-core-completion.md` and `docs/v0.7-biological-resolution.md`.

Copyright © 1993–2026 Abhishek Choudhary. All rights reserved. · AyeAI

v0.5 task 1 establishes a stable split:

```
PANINI Core
        │
        ├── ISA                 (implemented: CISC catalog + candidate RISC)
        ├── compiler            (implemented: parse → IR → CISC → RISC → microcode)
        ├── IR                  (implemented)
        ├── model resolver      (implemented: capability / organism-default registry)
        ├── execution contracts (implemented: ExecutionContract + ExecutionModel protocol)
        ├── provenance          (implemented: core / domain / model / data / evidence)
        ├── verification        (implemented: L0–L13 compile-time checks)
        └── plugin interfaces   (implemented as contracts; domain packages register)
                 │
                 ├── Mus musculus          (implemented plugin)
                 │      ├── genome data    (GRCm39 snapshots — DATA, not Core)
                 │      ├── developmental models   (mouse_axial_1d, mouse_axial_2axis)
                 │      └── phenotype models
                 │
                 ├── conformance TestOrganismA / TestOrganismB
                 │      (TEST / NON-BIOLOGICAL / CONFORMANCE MODEL)
                 │
                 ├── Drosophila            (not implemented — interface only)
                 │
                 ├── other organisms       (not implemented — interface only)
                 │
                 └── future domains        (not implemented)
```

## Distinctions

| Layer | Status in v0.5 task 1 | Owns |
|---|---|---|
| CORE | implemented | parser, ISA, IR, lowering algebra, resolver, engine loop, provenance schema, verification harness |
| MODEL | implemented for mouse + two conformance fixtures | field equations, stage logic, compile-time preview |
| DATA | implemented as domain snapshots | GRCm39 FASTA under `data/retrieved/` owned by the Mus musculus plugin |
| EVIDENCE | scaffolded records | MGI/NCBI citations live on the domain EvidenceModel |
| SIMULATOR | implemented engine; models are plugins | event loop is Core; ODEs are MODEL |
| REALIZATION | implemented specification path | reference-locus pack; authorization remains false |

Interfaces that exist but are **not** filled by a scientific implementation in this task:

- Drosophila / other organism plugins
- 3-D morphogenesis (`mouse_axial_3d` is REGISTERED only)
- GPU execution, SSA, population simulation
- wet-lab realization, synthesis orders, DT-5 closed loop

The two-tail mouse program is an acceptance test of the platform. It is not the architecture.
