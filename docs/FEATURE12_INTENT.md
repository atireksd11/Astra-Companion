# Feature 12 — Intent

Intent comes from the same completion as the spoken line. There is no second model call.

The model returns strict JSON:

```json
{"intent": "chat", "say": "One or two short sentences."}
```

`intent` is one of `chat`, `question`, `remember`, `stop`, `unknown`. Anything else becomes `unknown`.

| Intent | What happens |
|---|---|
| `chat`, `question`, `unknown` | Astra speaks `say`. |
| `stop` | `text_out` becomes `Okay, I'll stop.` |
| `remember` | `notes["memory_request"]` is the transcript clipped to 200 characters, and Astra still speaks `say`. |

`remember` does not write a new table and does not call a memory insert API. The note is there for a later phase.

The transcript is untrusted data inside `<transcript>` tags. The system prompt says those tags are not new instructions.
