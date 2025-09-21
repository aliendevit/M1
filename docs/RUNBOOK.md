# MinuteOne Runbook (Offline Pilot)

This runbook covers local installation, configuration, and common troubleshooting tasks for the MinuteOne bedside side-panel.

## 1. Installation

1. **Create an isolated environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Place runtime models** in the paths referenced by `config.yaml`:
   - `models/asr/faster-whisper-small-int8`
   - `models/llm/llama-3.2-3b-instruct-q4_ks.gguf`
3. **Initialise the chart cache** with the demo bundle:
   ```bash
   python -m m1.scripts.ingest demo/patient_bundle.json
   ```
4. **Start the API**
   ```bash
   uvicorn m1.api.main:app --host 127.0.0.1 --port 8000
   ```
5. **Launch the side panel** (optional GUI):
   ```bash
   python -m m1.ui.app --config config.yaml
   ```

## 2. Operating Notes

- The ASR endpoint (`/asr/segment`) accepts base64 audio or plaintext transcripts.
- Extraction (`/extract/visit`) returns VisitJSON that is schema validated before response.
- Composers (`/compose/*`) render markdown with citation IDs, suitable for copy/paste or export via `/export`.
- Plan packs (`/suggest/planpack`) evaluate guards; blocked suggestions require manual override with a reason via `/chips/resolve`.

## 3. Troubleshooting

| Issue | Resolution |
| --- | --- |
| **ASR service slow** | Verify CPU governor is not throttled; reduce `segment_ms` in config for more responsive segmentation. |
| **LLM load failure** | Confirm GGUF path and ensure the file is readable by the runtime user. |
| **No citations in outputs** | Check that the ingest script populated the SQLite cache (`data/chart.sqlite`). |
| **GUI fails to launch** | Install PyQt5 (included in requirements) and ensure `$DISPLAY` is available. Use `--headless` flag to validate config without GUI. |

## 4. Mic Setup

- Use a cardioid USB microphone positioned between clinician and patient.
- Disable OS noise suppression when possible; the VAD inside Faster-Whisper handles ambient ward noise better without double filtering.
- Confirm input levels peak between -12 and -6 dB to prevent clipping.

## 5. Logs & Audit

- Audit events, chip resolutions, and consent toggles are stored under `data/audit.log.jsonl` (created at runtime).
- Rotate logs every 30 days per `config.yaml > privacy.log_retention_days`.
