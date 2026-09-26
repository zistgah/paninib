# PANINI Tasks 2–5: Complete Specification
## Living Biological Knowledge Spine, Genetic CISC/RISC Semantics, Sequence IR, Reference Backend, and Designed Genotype Compiler MVP

**Version:** 0.1  
**Date:** 2026-09-25  
**Status:** Reference specification + executable MVP  
**Purpose:** Provide Grok/implementers with a precise, generic PANINI spine and a small reference implementation that proves the computational path from PANINI source to deterministic ATGC output without pretending to solve unsupported biological inverse problems.

---

## 1. Scope and design principle

PANINI is a generic biological intention/compiler platform. It is **not** a mouse genome compiler and it is not an exhaustive biological database.

The architecture must separate:

1. **PANINI Core** — language, IRs, compiler contracts, verification, provenance, registry.
2. **Domain plugins** — organism/domain-specific models and knowledge.
3. **Living knowledge providers** — extensible sources of reference sequences, annotations, evidence, pathways, phenotypes, etc.
4. **Reference backends** — versioned sequence/annotation retrieval.
5. **Compiler backends** — deterministic transformation of validated sequence operations.
6. **Simulation/execution models** — separate from genotype realization.
7. **Authorization/realization** — separate from design compilation.

The MVP target is:

`PANINI source`
→ `semantic IR`
→ `Genetic CISC`
→ `Genetic RISC`
→ `GenotypeDesign`
→ `Sequence IR`
→ `Reference backend`
→ `deterministic sequence transformation`
→ `ATGC FASTA`
→ `verification`
→ `provenance`

A successful MVP demonstrates a real compiler path. It does **not** imply that PANINI can infer an experimentally validated genotype for an arbitrary phenotype.

---

# 2. Architectural layers

## 2.1 Core

The core owns:

- parser and source representation
- semantic IR
- CISC ontology
- RISC ontology
- lowering machinery
- genotype-design schema
- Sequence IR
- compiler pipeline
- reference-provider interfaces
- verification
- provenance
- artifact graph
- model/provider registries
- diagnostics
- deterministic build manifests

The core must not import mouse-specific knowledge.

## 2.2 Domain plugins

A domain plugin may own:

- organism identity
- assemblies
- organism-specific causal models
- developmental models
- phenotype models
- organism-specific sequence catalogs
- organism-specific execution models
- organism-specific evidence mappings

Example:

`panini/domains/mus_musculus/`

must not become a dependency of generic core compilation.

## 2.3 Living knowledge providers

The knowledge layer is deliberately open-ended.

Providers can be:

- local databases
- versioned files
- HTTP/API adapters
- external standards
- human-curated records
- AI-generated candidate records
- institutional repositories

Provider records must carry provenance and evidence status.

---

# 3. Knowledge object model

All canonical knowledge records SHOULD expose:

```yaml
canonical_id:
namespace:
name:
version:
source:
source_id:
provenance:
evidence_status:
validity_domain:
created:
updated:
```

Core object families:

- Organism
- Assembly
- Genome
- Sequence
- Gene
- Transcript
- Protein
- RegulatoryElement
- Variant
- StructuralVariant
- Pathway
- GeneRegulatoryRelation
- CellType
- Phenotype
- BiologicalProcess
- MolecularFunction
- Evidence
- Publication

### Evidence status

Allowed values:

- `authoritative_reference`
- `curated`
- `computational_prediction`
- `model_assumption`
- `unverified_candidate`

Evidence status must never be silently upgraded.

---

# 4. Provider interfaces

Conceptual provider contract:

```python
class KnowledgeProvider(Protocol):
    def resolve(self, canonical_id: str) -> Record: ...
    def search(self, query: str, limit: int = 20) -> list[Record]: ...
    def capabilities(self) -> set[str]: ...
    def provenance(self) -> dict: ...
    def version(self) -> str: ...
```

Specialized providers:

```text
SequenceProvider
GenomeProvider
AnnotationProvider
VariantProvider
EvidenceProvider
PhenotypeProvider
PathwayProvider
```

A provider may return `UNAVAILABLE` rather than fabricate information.

---

# 5. Genetic CISC specification

The existing PANINI CISC vocabulary is retained as a 77-operation working ontology.

It is a **comprehensive working instruction vocabulary**, not a mathematical proof of completeness.

The semantic schema for each opcode is:

```yaml
opcode_id:
name:
category:
description:
operand_types:
preconditions:
transition:
postconditions:
state_effects:
affected_domains:
mechanism_class:
risc_lowering:
microcode_class:
evidence_requirements:
implementation_status:
```

Implementation status:

- `SPECIFIED`
- `LOWERABLE`
- `EXECUTABLE`
- `MODEL_DEPENDENT`
- `UNIMPLEMENTED`
- `UNKNOWN`

## 5.1 Genetic execution state

The canonical abstract state contains:

```text
sequence_state
chemical_state
topological_state
structural_state
occupancy_state
copy_number_state
localization_state
expression_state
epigenetic_state
temporal_state
context_state
```

An instruction denotes a state transition:

`S --instruction--> S'`

subject to:

- preconditions
- transition relation
- postconditions
- evidence/model constraints.

## 5.2 CISC → RISC

The RISC layer is a candidate primitive basis.

**No minimality claim is made.**

A lowering record has the conceptual form:

```yaml
cisc_opcode:
lowering_status:
risc_sequence:
side_conditions:
required_capabilities:
model_dependencies:
evidence_requirements:
```

If no defensible lowering exists:

`lowering_status = UNAVAILABLE`

The compiler must not invent a lowering.

---

# 6. Sequence IR

ATGC is a backend representation, not the semantic source language.

Sequence IR must retain enough structure to explain how a sequence was derived.

## 6.1 Core types

```text
ReferenceSequence
SequenceSegment
Feature
Variant
Edit
Construct
Allele
Orientation
Coordinate
Assembly
SequenceConstraint
DerivedSequence
```

## 6.2 Coordinate

```yaml
assembly:
sequence_id:
start:
end:
coordinate_system:
orientation:
```

The MVP uses 0-based half-open intervals:

`[start, end)`

## 6.3 SequenceEdit

```yaml
edit_id:
reference_sequence:
location:
operation:
source:
replacement:
orientation:
provenance:
validation:
```

Operations:

- `COPY`
- `INSERT`
- `DELETE`
- `REPLACE`
- `DUPLICATE`
- `INVERT`
- `MOVE`
- `SUBSTITUTE`

For the MVP, `REPLACE`, `INSERT`, `DELETE`, and `SUBSTITUTE` are executable.

Unsupported operations must be represented explicitly rather than approximated.

## 6.4 Deterministic transform

Given:

`ReferenceSequence + SequenceEdit[]`

produce:

`DerivedSequence`

The transformation must be deterministic and reproducible.

---

# 7. Reference backend contract

The backend abstraction must support:

```text
resolve_assembly()
resolve_sequence()
retrieve_interval()
resolve_feature()
verify_digest()
retrieve_metadata()
```

Every retrieved sequence must be identified by:

- provider
- accession/identifier
- version
- digest
- retrieval timestamp
- provenance

The implementation should support standards/providers such as:

- NCBI Datasets
- GA4GH Refget
- GA4GH Sequence Collections
- GA4GH Variation Representation
- FASTA
- GFF3/GTF/GenBank where applicable

The MVP may use an in-memory reference backend.

The production architecture should use adapters rather than embedding an entire database.

---

# 8. GenotypeDesign

A GenotypeDesign is an intermediate artifact between biological semantics and literal sequence operations.

Conceptual schema:

```yaml
design_id:
organism:
assembly:
reference:
edits:
constraints:
evidence:
status:
provenance:
```

The design is not automatically an experimental construct.

---

# 9. Compiler semantics

## 9.1 Pipeline

```text
Source
  ↓
Parser
  ↓
Semantic IR
  ↓
CISC
  ↓
RISC
  ↓
GenotypeDesign
  ↓
Sequence IR
  ↓
Reference resolution
  ↓
Validated deterministic transformation
  ↓
DerivedSequence
  ↓
FASTA
  ↓
Verification
  ↓
Provenance / artifact graph
```

Every stage must emit an inspectable artifact.

## 9.2 Scientific honesty rule

Two cases must be distinguished.

### Case A — explicit/evidence-backed sequence transformation

A deterministic sequence edit is specified and the reference is available.

PANINI may compile it to ATGC.

### Case B — phenotype with no validated causal sequence mapping

Example:

```text
make a mouse with two tails
```

If PANINI has only a developmental simulation model and no experimentally defensible genotype mapping, the compiler must return:

`DESIGN_UNRESOLVED`

It must not fabricate nucleotide sequence.

This distinction is mandatory.

---

# 10. Status model

Allowed high-level statuses:

- `COMPILED`
- `COMPILED_WITH_WARNINGS`
- `DESIGN_UNRESOLVED`
- `REFERENCE_UNAVAILABLE`
- `INVALID_PROGRAM`
- `INVALID_EDIT`
- `REFERENCE_MISMATCH`
- `INSUFFICIENT_EVIDENCE`
- `UNSUPPORTED_OPERATION`

Simulation status and genotype-design status are independent.

Example:

```text
simulation: TARGET_SATISFIED
genotype_design: DESIGN_UNRESOLVED
```

is valid.

---

# 11. Provenance model

Every artifact should identify its source class:

- `REFERENCE_DATA`
- `EVIDENCE`
- `MODEL`
- `INFERENCE`
- `DESIGN`
- `SIMULATION`
- `OBSERVATION`

A derived artifact should point to parent artifact digests.

Minimum build manifest:

```yaml
compiler_version:
isa_version:
semantic_version:
lowering_version:
organism:
assembly:
reference_identifier:
reference_digest:
input_program_digest:
semantic_ir_digest:
cisc_digest:
risc_digest:
genotype_design_digest:
sequence_ir_digest:
output_sequence_digest:
edits:
evidence:
warnings:
status:
```

---

# 12. Verification

## 12.1 Reference verification

Verify:

- assembly identity
- sequence identity
- digest
- coordinate system
- alphabet

## 12.2 Edit verification

Verify:

- bounds
- orientation
- nucleotide alphabet
- non-overlap where required
- deterministic edit order
- operation support

## 12.3 Output verification

Verify:

- FASTA alphabet
- expected length
- digest
- deterministic reproducibility

## 12.4 Unsupported biology

Unsupported biological inference is not a verification failure.

It is an explicit unresolved design state.

---

# 13. Example PANINI source

The reference implementation uses a deliberately explicit operation:

```text
organism synthetic
assembly demo-v1
reference chrDemo
replace 4 8 TTTT
```

This means:

- reference sequence is supplied by the reference backend
- replace `[4,8)` with `TTTT`
- produce the derived sequence

This example proves the compiler path without claiming biological causality.

---

# 14. Example

Reference:

```text
AACCGGTTAACC
```

Coordinates:

```text
0 1 2 3 4 5 6 7 8 9 10 11
A A C C G G T T A A C  C
```

Program:

```text
organism synthetic
assembly demo-v1
reference chrDemo
replace 4 8 TTTT
```

Derived sequence:

```text
AACCTTTTAACC
```

The transformation is deterministic.

---

# 15. CLI contract

Reference implementation:

```bash
python -m panini_ref compile examples/replace.panini --out output
python -m panini_ref inspect output
python -m panini_ref verify output
python -m unittest discover -s tests -v
```

The implementation is intentionally small and dependency-free.

---

# 16. Acceptance criteria

A compliant implementation passes all of the following.

### A1 — generic architecture

Core code contains no mouse-specific biological dependency.

### A2 — living provider model

Provider interfaces can be implemented by external sources without modifying compiler semantics.

### A3 — CISC schema

CISC operations have machine-readable semantic metadata.

### A4 — explicit lowering

CISC→RISC is represented explicitly. Unsupported lowering is not fabricated.

### A5 — Sequence IR

Sequence edits are structured objects, not string concatenation.

### A6 — reference backend

Reference data is retrieved through an abstraction.

### A7 — deterministic compilation

The same source + same reference + same compiler version produces the same derived sequence digest.

### A8 — provenance

The output identifies its source/reference/compiler and parent artifact digests.

### A9 — validation

Invalid coordinates, symbols, reference IDs, and digests are rejected.

### A10 — unresolved biology

A phenotype with no defensible sequence mapping returns `DESIGN_UNRESOLVED`, never invented ATGC.

### A11 — artifact inspectability

Semantic IR, CISC, RISC, GenotypeDesign, Sequence IR and final FASTA are inspectable.

### A12 — non-mouse conformance

The same core compiler can operate on the synthetic reference backend.

---

# 17. Scientific reference anchors

The production implementation should align with established standards and repositories rather than inventing incompatible identifiers.

### GA4GH Refget

Refget defines retrieval of reference sequences using content-derived identifiers/digests and supports reproducible sequence retrieval.

### GA4GH Sequence Collections

Sequence Collections provide standardized collections of sequences with identifiers/digests and retrieval/comparison semantics.

### GA4GH Variation Representation

Useful for representing sequence variation independently of a single textual edit syntax.

### NCBI Datasets

Provides programmatic access to genome-related packages, including sequences, annotations and metadata.

### NCBI GRCm39

A concrete mouse assembly/reference example; useful as a domain-provider fixture, not as a PANINI core dependency.

Production implementations should pin versions/accessions/digests and retain retrieval provenance.

---

# 18. Explicit non-goals for this MVP

Do not block Task 5 on:

- complete genomes for every organism
- exhaustive annotations
- all pathways
- all 77 CISC lowerings
- proof of RISC minimality
- complete molecular microcode execution
- biochemical simulation
- cellular simulation
- 3-D morphogenesis
- GPU/SSA execution
- physiology
- population simulation
- automatic causal-model discovery
- experimental validation
- wet-lab protocols
- synthesis ordering
- clinical use

These belong to later stages.

---

# 19. Future compatibility

The schemas must remain extensible.

Recommended versioning:

```text
isa_version
semantic_version
lowering_version
sequence_ir_version
reference_contract_version
compiler_version
```

Breaking schema changes require explicit version increments.

---

# 20. Design invariant

The most important invariant is:

> PANINI may compile what it can justify. It must represent what it cannot justify as unresolved rather than silently converting hypothesis into sequence.

This permits the platform to grow from a deterministic compiler MVP into a living biological computation system without conflating simulation, inference, design, and experimental fact.
