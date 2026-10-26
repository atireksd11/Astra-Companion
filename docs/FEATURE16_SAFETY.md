# Feature 16 — Safety filter

`safety_in` runs after speech-to-text and before the language model. `safety_out` runs on `text_out` before TTS.

The phrase list lives in `server/core/safety_list.py`, not in config. Matching is case-insensitive. Punctuation becomes spaces. Phrases match on word boundaries.

Categories: violent-crime how-to, explosives and weapons how-to, child sexual content, scams and credential theft, bio and chem weapons, and self-harm methods. A feelings statement is not a method request. "I feel like hurting myself" is not blocked. "How do I hurt myself" is.

On a hit, Astra says `I can't help with that.` `notes["safety"]` is `{blocked, stage, source: "blocklist", category}` and `notes["intent"]` is `unknown`. `turn.error` stays unset so TTS can speak the refusal. The matched phrase is not copied into `text_out`. The language model is not called.

`safety_out` uses the same list. A hit replaces `text_out` with the refusal before TTS. The canned offline line, the daily-cap line, the stop line, and the refusal itself do not trip the list.

Optional OpenAI moderation runs only when `safety.moderation` is `openai` and `OPENAI_API_KEY` is set. Timeout is 2.5 seconds. Any error skips moderation (fail open). A flag for `sexual/minors`, `self-harm/instructions`, or `illicit/violent` uses the same refusal. A blocklist child-sexual hit is not sent to that API.

API keys are environment variables only. They are not stored in config.
