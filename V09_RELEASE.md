# PANINI v0.9 release report

Compiler 0.9.0. Date 2026-09-26.

1. v0.8 baseline tests: 110 passed (re-run as part of 145).
2. v0.9 final tests: 145 passed, 0 failed.
3. Tests added: 35 (`python/tests/test_v09_engines.py`).
4. Engines implemented (execute against at least one deterministic fixture):
   MultiscaleStateEngine, TransitionEngine, BiochemicalEngine,
   CPUReferenceBackend, SpatialFieldEngine, ReactionDiffusionEngine,
   CellularEngine, DevelopmentalEngine, PhenotypeEngine, PhysiologicalEngine,
   PointCloudEngine, VoxelEngine, ParametricGeometryEngine, MeshEngine,
   AnimationEngine, RealizationPlanningEngine, ReferenceGenomeEngine,
   SequenceEngine, GenerativeSequenceEngine, InverseResolutionEngine,
   ConstraintSolver, Coverage (metric engine), VerificationEngine,
   ArtifactDebugger.
5. Engines still scaffolded: SSA/stochastic kinetics; full causal inversion;
   implicit_surface / skeleton geometry; calibrated physiology models.
6. Backends implemented: SimulatorDigitalBackend (adapter), LocalMockRealizationBackend
   (adapter), DeterministicGeometryBackend (fixture), DeterministicAnimationBackend
   (fixture), CPUReferenceBackend, realization planner.
7. Backends still unavailable: GPUBackend (CUDA not present), laboratory vendor
   adapters, NCBI/Refget HTTP, generative foundation model.
8. Fixtures vs scientific models:
   Fixtures: A→B→C kinetics, RD source/decay, cell line, tank physiology,
   schematic geometry, mock generative provider, inverse fixture strategy,
   two-axis axial computational model.
   Models (reduced-order, not validated biology): existing 1-D / two-axis
   axial simulator.
   Not models: GPU, SSA, two-tail genomic realization.
9. CPU/GPU status: CPU reference oracle implemented and reproducible.
   GPU contract present; capability detection reports UNAVAILABLE; no GPU
   execution claimed. Equivalence protocol runs CPU self-repeat within 1e-9.
10. Biochemical engine: ODE Euler mass-action; A→B→C fixture; SSA reserved.
11. Spatial-field: Grid/Scalar/Vector/Voxel + ops + RD engine.
12. Cellular/developmental: cell substrate + combined fixture + maturation frames.
13. Physiological: generic tank fixture + plug-in slots; not a complete physiology model.
14. Geometry: point cloud + voxels + parametric axes + triangle-tube mesh.
15. Animation: JSON frames from developmental/maturation trajectories; glTF-min adapter; no renderer.
16. Physical realization: planning/packaging/verification engine; LocalMock retained; labs are adapters.
17. Generative provider: engine pipeline over contract; default unavailable; mock is non-biological.
18. Inverse engine: strategy engine + synthetic licensed fixture; association stays NOT_LICENSED.
19. Constraint solver: ResolutionPlan over ConstraintGraph; not quantitative genetics.
20. Verification/debugger: cross-artifact checks + artifact-level traces (not causal inversion).
21. Vertical-slice commands actually executed (via tests):
    `python3 -m unittest discover -s python/tests -p 'test_*.py'`
    digital_vertical_slice() and physical_vertical_slice() both pass.
22. Remaining scientific limitations: no causal genotype for two tails; no
    validated mammalian networks; no wet-lab; no calibrated twin; no GPU;
    no SSA; retrieved loci are snapshots not a full assembly.
23. Exact next feature set: see AVAILABLE NOW / SCIENTIFICALLY UNRESOLVED / NEXT BUILD below.

## AVAILABLE NOW

- All v0.8 compiler / resolution / dual-path capabilities
- Biochemical ODE engine + inspectable trajectories
- Spatial fields + reaction-diffusion
- Cellular + developmental + maturation fixtures
- Parametric / point-cloud / voxel / mesh geometry
- Animation frames + glTF-min
- Realization planning engine
- Reference + sequence engines
- Generative candidate pipeline (provider-pluggable)
- Inverse strategy machinery (synthetic)
- Constraint solver + class-separated coverage
- Cross-artifact verification + artifact traces
- Structured digital-twin maturity profiles
- CPU execution protocol; GPU boundary with honest UNAVAILABLE

## SCIENTIFICALLY UNRESOLVED

- Causal genomic realization of "two tails"
- Licensed inverse-causal biology beyond fixtures
- Mammalian biochemical / physiological / morphogenetic models
- Experimental validation of any designed sequence
- GPU-accelerated equivalent kernels
- Stochastic SSA kinetics
- Whole-organism digital twin

## NEXT BUILD

1. Bind a real reference/annotation provider without compiler changes.
2. Optional CUDA kernel for the biochemical + RD fixtures with CPU≈GPU tests.
3. SSA backend implementing the reserved stochastic contract.
4. Domain plugin that maps axial model parameters onto the new state engine.
5. Richer mesh/implicit geometry if a dependency-free path remains viable.
6. Observation-driven knowledge update loop using the maturity profile.
7. Keep DESIGN_UNRESOLVED for unjustified genotypes.
