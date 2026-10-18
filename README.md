# PANINI Genetic Compiler

© 1993–2026 Abhishek Choudhary. All rights reserved.  ·  AyeAI

**v1.0 — Research platform. Computational architecture complete enough to publish. Biology remains open.**

```
Desired Phenotype ≠ Predicted Phenotype ≠ Observed Phenotype ≠ Validated Phenotype
Compilation Success ≠ Execution Success ≠ Target Satisfaction ≠ Biological Validation
```

## 1. What PANINI is

A compiler platform that lowers declarative biological intent through typed
IR (semantic → resolution → CISC → RISC → Sequence IR) and emits two coupled
artifacts: a physical realization *plan* and a digital execution *run*.
IR contracts are the product. The laboratory is an external adapter.

## 2. What v1.0 implements

The executable spine from source to sequence, simulation, phenotype, geometry,
animation, verification, debug traces, observation, and knowledge update.
See `docs/v1.0-spec.md` and `V1_IMPLEMENTATION_MATRIX.md`.

## 3. What it does not claim

It does not design arbitrary genomes. It does not possess a causal genomic
realization of “two tails”. Fixtures are fixtures. GPU execution is
UNAVAILABLE. SSA is a synthetic Gillespie fixture. No wet-lab is executed.

## 4. Install / run

Python 3.10+. No extra packages required for the reference engines.

```bash
./seed.sh
python3 panini compile examples/replace.panini -o /tmp/replace-out
python3 panini inspect /tmp/replace-out --stage sequence-ir
python3 panini verify /tmp/replace-out
python3 panini isa --opcode REPLACE
python3 panini coverage
```

## 5. Reproduce the tests

```bash
./seed.sh
# equivalent:
python3 -m unittest discover -s python/tests -p 'test_*.py'
```

## 6. Flagship demonstrations

- Case A: `examples/replace.panini` → Sequence IR → `AACCTTTTAACC`
- Case B: knowledge record closes E0001 without compiler edits
- Case C: digital vertical slice (biochem → field/dev → phenotype → geometry → animation)
- Case D: two-tail mouse remains DESIGN_UNRESOLVED + E0001
- Case E: user-asserted edit is NOT_VALIDATED
- Case F: observation → residual → knowledge update → recompile
- Case G: forward and reverse artifact traces

## 7. Architecture

Core is organism-independent. Mouse lives in `python/panini/domains/mus_musculus`.
Providers and backends are capability-selected. See `docs/ARCHITECTURE.md`
and `docs/v1.0-spec.md`.

## 8. Scientific limitations

`docs/v1.0-limitations.md`. Two-tail genomic realization is unresolved on
purpose.

## 9. Contribute

`CONTRIBUTING.md`, `docs/COLLABORATION.md`. Add providers and domain plugins;
do not put species switches in Core.

## 10. Cite

See `CITATION.cff`. No DOI is minted in this tree.

## Layout

```
examples/                 programs and golden artifacts
python/panini/            working compiler
python/panini/engines/    generic engines
python/panini/domains/    organism / conformance plugins
python/tests/             conformance
schemas/                  versioned JSON schemas
docs/                     specifications
seed.sh                   canonical reproducibility command
```

<!-- trademarks:begin -->
---
AyeAI®, AyeCNSe® and AyeAM® are registered trademarks of Abhishek Choudhary in India, used and claimed worldwide since
2019. The names of his products and projects are his trademarks; see [legal/TRADEMARKS.md](legal/TRADEMARKS.md). Code
licences in this repository grant copyright permissions only and no right in any mark.
© 1993–2026 Abhishek Choudhary. All rights reserved. AyeAI.
<!-- trademarks:end -->
