# Collaboration model

Collaborators extend PANINI without modifying Core by contributing at
these extension points:

- knowledge providers
- organism plugins (`python/panini/domains/<taxon>/`)
- biochemical models (ReactionSystem records)
- developmental models (ExecutionModel protocol)
- physiology models
- generative providers
- reference providers (ReferenceBackend)
- GPU engines (only with a real kernel)
- SSA engines (already a CPU fixture; richer models welcome)
- geometry engines
- validation datasets
- observation providers

Register capabilities. Do not hard-code species names into Core.
