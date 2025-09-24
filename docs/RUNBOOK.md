# MinuteOne Runbook

## Environment
- Python 3.10+
- Optional: PyQt5 for desktop shell (`pip install pyqt5`)

## Setup
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## API Server
```bash
uvicorn m1.api.main:app --reload --port 8000
```

### Health Check
```bash
curl http://localhost:8000/health
```

### Ingest Transcript
```bash
http --json POST :8000/ingest patient_id=demo transcript@demo/transcript.txt
```

### Fetch Evidence
```bash
http :8000/evidence/demo
```

## Demo Data Ingest
```bash
python -m m1.scripts.ingest demo/patient_bundle.json
```

## Desktop Client
```bash
python -m m1.ui.app
```

## Testing
```bash
pytest -q
```
### Configuration precedence
1. Package defaults (`m1/defaults/config.yaml`)
2. System config (`/etc/m1/config.yaml` or `%PROGRAMDATA%\m1\config.yaml`)
3. User config (`~/.config/m1/config.yaml` or `%APPDATA%\m1\config.yaml`)
4. Project config (`./config.yaml`)
5. Overrides via `M1_CONFIG`
6. Environment variables prefixed with `M1_`

Example: `set M1_CACHE_DB=D:\\data\\cache.db` to point the cache at a different location for a single session.
