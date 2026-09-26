# PANINI v1.0 release report

Compiler 1.0.0. Date 2026-09-26.

## A. Preserved from v0.9

All v0.9 engines and the 145-test baseline: MultiscaleStateEngine,
TransitionEngine, BiochemicalEngine, CPUReferenceBackend, SpatialFieldEngine,
ReactionDiffusionEngine, CellularEngine, DevelopmentalEngine, PhenotypeEngine,
PhysiologicalEngine, PointCloudEngine, VoxelEngine, ParametricGeometryEngine,
MeshEngine, AnimationEngine, RealizationPlanningEngine, ReferenceGenomeEngine,
SequenceEngine, GenerativeSequenceEngine, InverseResolutionEngine,
ConstraintSolver, Coverage, VerificationEngine, ArtifactDebugger,
digital and physical vertical slices, mouse axial models, knowledge registry,
CISC 77-op catalogue, genotype compiler, dual-path backends.

## B. Newly implemented

- `python/panini/engines/ssa.py` — CPU Gillespie fixture
- `python/panini/engines/cisc_coverage.py` — machine-readable coverage
- `python/panini/engines/verification_matrix.py`
- `python/panini/engines/composition.py`
- `python/panini/domains/mus_musculus/bridge.py` — generic-state lift
- biochemical conservation / numerical diagnostics
- phenotype residuals + validated kind
- DigitalExecutionBackend.trace / verify
- CLI `simulate`, `coverage`, `feedback`
- `python/tests/test_v10_platform.py` cases A–G
- docs/v1.0-spec.md, v1.0-completion.md, v1.0-limitations.md
- CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, ROADMAP, RESEARCH,
  REPRODUCIBILITY, docs/COLLABORATION.md

## C. Not implemented

Genuine CUDA kernels. Implicit-surface / skeleton geometry. Live NCBI/Refget
HTTP. Wet-lab vendor adapters. Nested block syntax. GFF3 live resolution.

## D. Scientifically unresolved

Causal genomic realization of two tails. Licensed inverse-causal biology
beyond fixtures. Mammalian biochemical / physiological / morphogenetic
validity. Experimental validation of designed sequences. Quantitative
genetics. Whole-organism twin.

## E. Tests

Command: `python3 -m unittest discover -s python/tests -p 'test_*.py'`

Result: 164 passed, 0 failed.

## F. Vertical slices

Executed inside the suite: `digital_vertical_slice()`,
`physical_vertical_slice()`, mouse axial 1-D / 2-axis through the domain
bridge. Two-axis simulation may satisfy tail_count==2; genotype remains
DESIGN_UNRESOLVED.

## G. CISC coverage

77 specified. EXECUTABLE 4. LOWERABLE 15. SPECIFIED 57. MODEL_DEPENDENT 1.
Sequence-realizable recorded: DELETE, EDIT, INSERT, REPLACE.
Executable sequence ops: DELETE, INSERT, REPLACE, SUBSTITUTE.
Unavailable lowerings: 58 (honest, not invented).

## H–L

See V1_IMPLEMENTATION_MATRIX.md and ROADMAP.md.
