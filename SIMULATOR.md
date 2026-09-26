# Genetic Execution Simulator + Biological Debugger

Implementation map against the v0.2 specification. This is an execution
subsystem of the compiler, not a visualization helper.

```
PANINI → Bio-IR → CISC → RISC → microcode → compiled genotype
                                              │
                                       EXECUTION ENGINE
                                              │
                         molecular → cellular → developmental → organism
                                              │
                                       phenotype Φ = H(S)
                                              │
                                    VERIFICATION V0–V11
                                              │
                                          DEBUGGER
```

## What is actually executed

The engine loads the *semantic* compiled genotype (stable gene IDs, loci,
roles, library refs, CISC/RISC/μcode ancestry). It does not treat `ATGC…`
as the program.

Canonical step:

```
S_{t+Δt} = F(S_t, G, E_t, U_t, θ, ξ_t)
Φ_t      = H(S_t)
```

`U_t` is the debugger intervention channel.

## Package map

| Spec | Code |
|---|---|
| 3 runtime / scheduler / event queue / state / checkpoints | `simulator/engine.py`, `events.py`, `state.py`, `checkpoint.py` |
| 5 canonical state S | `simulator/state.py` `BiologicalState` |
| 6 semantic genotype | `simulator/genotype.py` |
| 7–8 execution events | `simulator/events.py`, `engine.py` |
| 9 hybrid time | discrete ticks + event queue (TRANSCRIBE/TRANSLATE/REACT/SIGNAL/DIFFERENTIATE/DEVELOP/OBSERVE) |
| 10 spatial backends | 1-D axis bins shipped; other backends named in state.spatial |
| 11–12 phenotype / observation | `simulator/phenotype.py`, `observation.py` |
| 14 ensemble / seed | `SimulationManifest.random_seed`, identical seeds replay |
| 15–24 debugger | `debugger/session.py`, `predicates.py`, `causal.py` |
| 26–27 assertions + V0–V11 | `simulator/assertions.py`, `verify_runtime.py` |
| 31–32 API / CLI | `simulator/api.py`, `cli.py` |
| 33–34 storage / manifest | `simulator/run.py` |
| 35 maturity | mouse axial slice is **DT-3** |

## CLI

```
panini compile organism.panini
panini genotype build build.json
panini sim run build.json
panini sim inspect run_…
panini sim checkpoint run_…
panini debug build.json
```

## Honesty bounds

- The executable model is a reduced-order murine axial twin, not a whole-organism
  finite-element embryo.
- PathwayModel substitution slots exist (`deterministic_ODE`, `hybrid`, …);
  only hybrid/ODE is implemented.
- GPU / CUDA is specified as an accelerator, not shipped.
- DT-5 closed-loop wet-lab update is the target, not this milestone.
- `COMPILED = TRUE` ≠ `BIOLOGICALLY VALIDATED = TRUE`.
