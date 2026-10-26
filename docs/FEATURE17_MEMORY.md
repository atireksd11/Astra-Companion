# Feature 17 — Memory and context (Phase 3 v2)

Each speaker (`speaker_id`) has their own durable facts in SQLite (`memory_items`) with optional FastEmbed vectors and FTS. Set `memory.use_mem0` to true to use Mem0 with on-disk Qdrant instead.

Pipeline: `context_retrieve` (before LLM) loads profile card, memories, and optional turn excerpts. `memory_persist` (after `safety_out`) stores `remember` facts or handles `forget`.

Retrieved text is injected as untrusted `<memory>` blocks in the system prompt. Web snippets use `<web>`.
