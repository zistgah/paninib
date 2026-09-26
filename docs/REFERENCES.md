# References

Copyright © 1993–2026 Abhishek Choudhary. All rights reserved. · AyeAI

## Assemblies and identifiers

- Mouse reference assembly GRCm39, GCF_000001635.27  
  https://www.ncbi.nlm.nih.gov/assembly/GCF_000001635.27
- NCBI E-utilities efetch  
  https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi
- Mouse Genome Informatics  
  https://www.informatics.jax.org/

## Loci in the seed library

| Symbol | MGI | NCBI Gene | GRCm39 | URL |
|---|---|---|---|---|
| Wnt3a | [MGI:98956](https://www.informatics.jax.org/marker/MGI:98956) | 22416 | chr11:59138859–59181578 − | https://www.informatics.jax.org/sequence/ENSMUSG00000009900 |
| Fgf8 | [MGI:99604](https://www.informatics.jax.org/marker/MGI:99604) | 14179 | chr19:45725237–45731354 − | https://www.informatics.jax.org/marker/MGI:99604 |
| Cdx2 | [MGI:88361](https://www.ncbi.nlm.nih.gov/gene/12591) | 12591 | chr5:147237710–147244059 − | https://www.ncbi.nlm.nih.gov/gene/12591 |
| Hoxd13 | [MGI:96205](https://www.informatics.jax.org/marker/MGI:96205) | 15433 | chr2:74498569–74501947 + | https://www.ncbi.nlm.nih.gov/gene/15433 |
| Aldh1a2 (Raldh2) | [MGI:107928](https://www.informatics.jax.org/marker/MGI:107928) | 19378 | chr9:71123071–71203525 + | https://ensembl.org/Mus_musculus/Gene/Summary?g=ENSMUSG00000013584 |

## Model assumptions (not laws)

The axial prior (Wnt/FGF posteriorising, RA anteriorising, Cdx/Hox posterior identity) is a reduced-order planning model transferred from the mouse axial literature. It is labelled MODEL_ASSUMPTION. It is not a quantitative prediction of a living embryo and is not experimental validation.

## Invariants

MODEL PREDICTION ≠ EXPERIMENTAL OBSERVATION ≠ BIOLOGICAL VALIDATION

## Sequence and genome standards

- GA4GH refget / sequence collections: https://www.ga4gh.org/
- FASTA sequence representation (NCBI)
- Synthetic Biology Open Language (SBOL) — adapter emits a minimal subset only

## Simulation methods (engines, not claims)

- Gillespie DT (1977). Exact stochastic simulation of coupled chemical reactions. *J. Phys. Chem.*
- Forward-Euler mass-action ODE integration as implemented in BiochemicalEngine (numerical fixture)
- Turing-style reaction–diffusion as a generic field primitive (fixture)

## Provenance / knowledge

- W3C PROV concepts inform artifact provenance fields; PANINI does not claim PROV-O completeness.
