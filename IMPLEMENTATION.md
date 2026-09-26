# PANINI v1.0 implementation report

Build: v1.0.0 on top of v0.9.0
See docs/v1.0-spec.md, docs/v1.0-completion.md, V1_RELEASE.md.

# PANINI v0.9 implementation report

Build: v0.9.0 on top of v0.8.0
See docs/v0.9-engines.md.

# PANINI v0.8 implementation report

Build: v0.8.0 on top of v0.7.0
See docs/v0.8-core-completion.md.

---

# PANINI v0.7 implementation report

Build: v0.7.0 on top of v0.6.0
See docs/v0.7-biological-resolution.md.

---

# PANINI Tasks 2-5 implementation report

Build: v0.6.0 on top of v0.5 task-1 Core / domain split
Date: 2026-09-25
Acceptance: end-to-end compiler feasibility, not universal biological capability

This report answers the sixteen required items. It does not claim that
PANINI can currently design arbitrary biological genomes.

## 1. Exact files added / changed

Added:

- python/panini/knowledge.py — living knowledge record schema + provider registry + MVP records
- python/panini/isa_spec.py — machine-readable CISC semantics, execution-state model, CISC to RISC lowering contract
- python/panini/sequence_ir.py — Sequence IR types + deterministic edit engine
- python/panini/reference_backend.py — reference-backend protocol, in-memory MVP, standards notes
- python/panini/genotype_compiler.py — designed-genotype compiler, artifact writer, verify/inspect
- python/tests/test_genotype_compiler.py — acceptance tests 1-10 plus spine/ISA/honesty tests
- examples/replace.panini — explicit REPLACE demo
- examples/invert.panini — unsupported operation yields DESIGN_UNRESOLVED
- examples/replace-out/ — generated inspectable artifact graph
- docs/PANINI_SPEC.md — Tasks 2-5 specification
- docs/v0.6-tasks2-5.md — short architecture note
- IMPLEMENTATION.md — this report

Changed:

- python/panini/version.py — compiler 0.6.0; Core remains 0.5.0; new ISA / Sequence IR / compiler versions
- python/panini/pipeline.py — intent programs emit genotype_design + genotype_realization as DESIGN_UNRESOLVED
- python/panini/cli.py — auto-detect sequence programs on compile; add inspect, verify, isa
- README.md — v0.6 banner and CLI examples

Existing mouse domain, simulator, debugger, CISC catalogue (77 ops),
candidate RISC (16 ops), and v0.5 architecture tests are unchanged in
behaviour.

## 2. Exact new interfaces

KnowledgeProvider: resolve, search, capabilities, provenance, version.

Specialized capability interfaces: SequenceProvider, GenomeProvider,
AnnotationProvider, VariantProvider, EvidenceProvider, PhenotypeProvider,
PathwayProvider.

ProviderRegistry: register(name, provider), resolve/search across providers.

ReferenceBackend: resolve_assembly, resolve_sequence, retrieve_interval,
resolve_feature, verify_digest, retrieve_metadata.

Genotype compiler: detect_source_kind, parse_sequence_program,
compile_sequence_program, compile_unresolved_phenotype, compile_any,
write_bundle, verify_bundle, inspect_stage.

A provider may return absence rather than fabricate a record.
Evidence status is never silently upgraded.

## 3. Exact Sequence IR schema

SequenceIR: type, version, organism, assembly, reference,
coordinate_system="0-based-half-open", edits[], constraints[].

SequenceEdit: edit_id, operation (COPY|INSERT|DELETE|REPLACE|DUPLICATE|INVERT|MOVE|SUBSTITUTE),
start, end, replacement, source, orientation, reference_sequence, provenance, validation.

Coordinate: assembly, sequence_id, start, end, coordinate_system, orientation.

ReferenceSequence: sequence_id, assembly, sequence, provider, version, accession, provenance, digest=sha256(sequence).

DerivedSequence: sequence_id, assembly, sequence, parent_digest, digest, edits, provenance, alphabet.

Also typed: SequenceSegment, Feature, SequenceConstraint.

MVP-executable operations: REPLACE, INSERT, DELETE, SUBSTITUTE.
INVERT / DUPLICATE / MOVE / COPY are represented and rejected as
UNSUPPORTED_OPERATION or DESIGN_UNRESOLVED rather than approximated.

## 4. Exact GenotypeDesign schema

design_id, organism, assembly, reference, edits[], constraints[],
evidence[], status, provenance=DESIGN, phenotype_target,
genomic_realization=resolved|unresolved, reason.

A GenotypeDesign is not an experimental construct and is not a simulated
phenotype.

## 5. Exact reference-backend contract

Every retrieved sequence is identified by provider, accession/identifier,
version, digest (SHA-256 stand-in for GA4GH Refget content id),
retrieval timestamp, and provenance.

MVP implementation: MemoryReferenceBackend with
demo-v1/chrDemo = AACCGGTTAACC and demo-v2/chrDemo = TTTTGGTTAACC
(alternate fixture for Test 3).

Documented adapter slots, not connected in this MVP:
NCBI Datasets, GA4GH Refget, GA4GH Sequence Collections, GA4GH VR,
FASTA (emitted), GFF3/GTF/GenBank (resolve_feature stubbed).

No encyclopedia is copied into the repository. Mouse GRCm39 FASTA
snapshots remain domain data under data/retrieved/, owned by
panini.domains.mus_musculus.

## 6. Exact CISC semantic schema

Every opcode in the working 77-op catalogue has:
opcode_id, name, category, description, operand_types, preconditions,
transition (S --OP(operands)--> S'), postconditions, state_effects,
affected_domains, mechanism_class, risc_lowering, microcode_class,
evidence_requirements, implementation_status, isa_version,
semantic_version, lowering_version, compatibility_version.

implementation_status: SPECIFIED | LOWERABLE | EXECUTABLE | MODEL_DEPENDENT | UNIMPLEMENTED | UNKNOWN.

risc_lowering: cisc_opcode, lowering_status (AVAILABLE|UNAVAILABLE|MODEL_DEPENDENT),
risc_sequence, rule, side_conditions, required_capabilities,
model_dependencies, evidence_requirements, sequence_realizable.

Dump: python3 panini isa   and   python3 panini isa --opcode REPLACE

Execution-state domains: sequence_state, chemical_state, topological_state,
structural_state, occupancy_state, copy_number_state, localization_state,
expression_state, epigenetic_state, temporal_state, context_state.

## 7. Exact lowering representation

Example, REPLACE:
  lowering_status: AVAILABLE
  risc_sequence: [CLEAVE, WRITE_STATE, POLYMERIZE, LIGATE, COMMIT]
  rule: REPLACE → CLEAVE; WRITE_STATE; POLYMERIZE; LIGATE; COMMIT
  sequence_realizable: true

Ops that already had a compiler rewrite (SENSE, REGULATE, DEVELOP, ...)
are AVAILABLE / LOWERABLE. Sequence-realizable CISC (REPLACE, INSERT,
DELETE, EDIT, MUTATE) are EXECUTABLE when operands are literal edits.

If no defensible lowering exists (example INVERT):
  lowering_status: UNAVAILABLE
  risc_sequence: []
  rule: no scientifically defensible RISC lowering recorded

The compiler does not invent a lowering. The 16-op RISC remains a
candidate basis; risc_minimality_claim is false.

## 8. Example source program

examples/replace.panini:

    organism synthetic
    assembly demo-v1
    reference chrDemo
    replace 4 8 TTTT

Reference AACCGGTTAACC, 0-based half-open [4, 8) = GGTT,
replacement TTTT → AACCTTTTAACC.

This is an explicit sequence transformation. It does not claim a phenotype.

## 9. Generated intermediate artifacts

Emitted under the output directory (see examples/replace-out/):

    01-source.json
    02-semantic-ir.json
    03-cisc.json
    04-risc.json
    05-genotype-design.json
    06-sequence-ir.json
    07-derived-sequence.fasta
    08-provenance.json
    manifest.json
    verification.json
    sequence.json

CLI:

    python3 panini compile examples/replace.panini -o out
    python3 panini inspect out --stage semantic-ir
    python3 panini inspect out --stage cisc
    python3 panini inspect out --stage risc
    python3 panini inspect out --stage genotype
    python3 panini inspect out --stage sequence-ir
    python3 panini verify out

## 10. Generated ATGC artifact

    >chrDemo|demo-v1|derived
    AACCTTTTAACC

output_sequence_digest (sha256 of AACCTTTTAACC):
6a97eae150bddc75fee5ccb63082032d9645afea9f9fec2eda18fff43fd1380f

reference_digest:
b1bb15af215d1fdff848b7c7a3aaf151fd0444f5bae123cdc92f70c08d96f7d2

## 11. Verification results

panini verify checks required stage artifacts, FASTA alphabet ACGT,
output digest vs manifest, and presence of reference/source digests.

Intent programs never emit a derived FASTA from an unresolved design.

Invalid coordinates → INVALID_EDIT.
Invalid symbols (e.g. N) → INVALID_EDIT.
Pinned digest mismatch → REFERENCE_MISMATCH.
Missing assembly → REFERENCE_UNAVAILABLE.

Full unit suite: 64 tests, OK.

## 12. Provenance chain

source → semantic_ir → cisc → risc → genotype_design → sequence_ir
→ reference → derived_sequence → verification

Each stage is hashed. Manifest records parent digests plus compiler_version,
isa_version, semantic_version, lowering_version, organism, assembly,
reference_identifier, reference_digest, input_program_digest,
semantic_ir_digest, cisc_digest, risc_digest, genotype_design_digest,
sequence_ir_digest, output_sequence_digest, edits, evidence, warnings, status.

Source classes: REFERENCE_DATA, EVIDENCE, MODEL, INFERENCE, DESIGN,
SIMULATION, OBSERVATION.

A derived sequence is DESIGN. A demo chromosome is REFERENCE_DATA.
A two-axis developmental run is SIMULATION. Those labels are not interchangeable.

## 13. Tests and their results

python/tests/test_genotype_compiler.py

1 explicit REPLACE → deterministic ATGC AACCTTTTAACC — PASS
2 same source → same digest — PASS
3 change reference demo-v1 to demo-v2 changes digest and sequence — PASS
4 invalid coordinates fail — PASS
5 invalid nucleotide symbols fail — PASS
6 reference digest mismatch fails — PASS
7 unsupported CISC-to-sequence (INVERT) → DESIGN_UNRESOLVED, no ATGC — PASS
8 two-tail mouse: 2-axis simulation SATISFIED; genotype DESIGN_UNRESOLVED — PASS
9 synthetic / conformance programs reach Sequence IR or unresolved without Core edits — PASS
10 complete inspectable artifact graph — PASS

Plus knowledge-spine, ISA-spec, standards-note, and honesty-boundary tests.

Existing v0.5 architecture / vertical / conformance / debugger / v0.4
suites still PASS. Core still has no mouse-specific tokens or imports.

## 14. What is genuinely implemented

- Provider / record spine with evidence-status vocabulary
- In-memory MVP knowledge for synthetic + conformance organisms, demo assembly, demo sequence
- Versioned CISC semantic specs for the full working catalogue
- Explicit CISC to RISC lowering records, including UNAVAILABLE
- Sequence IR objects (not string concatenation)
- Deterministic REPLACE / INSERT / DELETE / SUBSTITUTE engine
- In-memory reference backend with digest verification
- Genotype compiler pipeline with inspectable artifacts
- Status model including DESIGN_UNRESOLVED
- CLI compile / inspect / verify / isa
- Intent-program compile payload now carries an honest unresolved genotype design
- Two-tail mouse developmental behaviour preserved

## 15. What remains scaffolded

- NCBI Datasets / Refget / Sequence Collections / VR HTTP adapters
- GFF3 feature resolution
- Per-opcode biochemical microcode execution
- Most of the 77 CISC ops as sequence realizations
- Mouse-domain knowledge exposed through the new provider API (the domain
  plugin and GRCm39 snapshots already exist; they are not re-imported into Core)
- INSERT/DELETE exercised by the engine but the golden example is REPLACE
- Version history store for previous ISA revisions (fields exist; no archive yet)
- Nested program { } block syntax (line-oriented form is what the MVP compiles)

## 16. What remains scientifically unresolved

- Any evidence-backed genomic realization of "two tails"
- Inverse design from arbitrary phenotype to genotype
- Causal completeness of the CISC catalogue
- Minimality of the 16-op RISC
- Biological validity of any designed sequence
- Wet-lab realization, authorization, synthesis ordering
- Whole-genome compilation, 3-D morphogenesis, physiology, population models

The two-tail mouse remains:

    developmental simulation:
        default 1-D model → target UNSATISFIED (one axis)
        explicit mouse_axial_2axis → target SATISFIED (tail_count == 2)

    genotype realization:
        DESIGN_UNRESOLVED

That split is a successful compiler result: the inverse-design problem
is identified, not papered over with invented ATGC.

## Design invariant

PANINI may compile what it can justify. It must represent what it
cannot justify as unresolved rather than silently converting
hypothesis into sequence.
