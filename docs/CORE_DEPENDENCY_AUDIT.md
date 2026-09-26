# v0.4 → v0.5 task 1 dependency audit

Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.

Inspected: every Python module under `python/panini`, tests, examples,
`docs/`, `data/retrieved/`, the Rust sketch under `src/`, and workstation
assets. Imports, call sites, data paths and execution branches were traced
(not filenames alone).

## PANINI CORE (after refactor)

Domain-neutral: parser, types, CISC/RISC ontology, IR, generic lowering
algebra, capability intersection, model registry/resolver, execution
engine loop, debugger, phenotype constraint evaluator, provenance schema,
CLI.

## MUS MUSCULUS DOMAIN

Moved behind `python/panini/domains/mus_musculus/`:

- loci Wnt3a, Fgf8, Cdx2, Hoxd13, Aldh1a2 and GRCm39 retrieval
- `mouse_axial_1d` / `mouse_axial_2axis` numerics
- murine Wnt/FGF/RA/Cdx/Hox causal prior
- two-basin geometry
- mouse stdlib catalogue

`data/retrieved/*.fa` remains at repo root as domain data, not Core.

## Still outside this task

Whole-genome compilation, sequence-level causal editing, biochemical /
physiological digital twins, 3-D morphogenesis, GPU, SSA, population
simulation, experimental calibration, DT-5, wet-lab protocols, synthesis
orders. The Rust tree is an unchanged sketch.
