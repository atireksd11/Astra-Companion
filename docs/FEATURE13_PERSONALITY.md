# Feature 13 — Personality

Personality is the system prompt inside `build_context`. It is not a pipeline step.

Astra is warm, brief, and one or two sentences. She is not a doctor and does not diagnose.

When `notes["mood"]["label"]` is `happy`, `sad`, `angry`, or `surprised`, the prompt adds one short tone line. It does not tell the model to name the user's emotion. `neutral` and a missing label add nothing.

When cadence `pause_ms_median` is at least 400, or `peaks_per_s` is at least 3.5, the prompt adds one line: use short sentences.

Context is that system prompt, at most two previous `text_in` / `text_out` pairs (each clipped to 200 characters), and the current transcript. No embeddings.
