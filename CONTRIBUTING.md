# Contributing to PANINI

Copyright © 1993–2026 Abhishek Choudhary. All rights reserved. · AyeAI

PANINI Core is organism-independent. Prefer adding:

- a knowledge record or provider
- an organism / model / geometry / biochemistry plugin under `python/panini/domains/`
- a backend that implements an existing contract
- tests and fixtures that are labelled as fixtures

Do not add species switches to Core. Do not invent causal biology to make a test pass.
Unresolved is a valid compiler result.

Run `./seed.sh` before opening a change.
