# Feature 8 — Pronunciation & accent tracking

Astra remembers **how you say custom words** and, with the CTC aligner, refines phone sequences from your speech after each turn.

## Enable

In `server/config.json`:

```json
"steps": ["denoise", "focus", "stt", "cadence", "pronunciation", "echo"],
"pronunciation": {
  "enabled": true,
  "aligner": "ctc",
  "model": "charsiu/en_w2v2_ctc_libris_and_cv",
  "tokenizer": "charsiu/tokenizer_en_cmu",
  "min_word_confidence": 0.85,
  "promote_count": 5,
  "aligner_timeout_s": 8.0,
  "min_phone_confidence": 0.5
}
```

First run with `"aligner": "ctc"` downloads the charsiu model (~755 MB). Use `"aligner": "none"` for lexicon-only mode.

Restart `python bridge.py`.

## Teach a word (manual)

Send on `start` meta:

```json
"teach": { "word": "tomato", "phones": ["T", "AH", "M", "EY", "T", "OW"] }
```

The word is stored with `source: "user"` / `status: "taught"` and is not overwritten by automatic learning.

## Background learning (CTC)

After **`done`**, when STT ran with word timestamps:

1. **g2p-en** seeds new lexicon entries.
2. **Charsiu CTC** runs on high-confidence word slices (`min_word_confidence`).
3. **Promote** after **3** consistent isolated-word hearings or **5** in-sentence (`promote_count`).
4. Bridge may send `{"type":"learn", "lines": [...], ...}` (laptop prints learn lines).

Learning runs **async** after echo; profile writes **merge** pronunciation into the latest DB row so cadence/embedding updates are not clobbered.

Skipped: barged turns, low-confidence words, tokens shorter than 3 letters (e.g. “hr”).

## Profile storage

- Local: `server/astra.db` table `speaker_profiles` (survives restarts).
- Optional sync: set `profile.sync_url` and env `ASTRA_PROFILE_SYNC_TOKEN` for `PUT …/v1/profiles/{speaker_id}` (JSON only, **no audio**).

## Limits

- **`aligner: "none"`**: lexicon + manual teach only; no background learning.
- Accent “learning” is **not** the focus ECAPA match — that is for who is talking (Feature 5).
- The **laptop bridge must be running** to learn; a cloud DB is memory, not ears on the robot.

See also [FEATURE9_CADENCE.md](FEATURE9_CADENCE.md).
