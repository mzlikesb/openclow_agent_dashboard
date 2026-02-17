# openclow_agent_dashboard

Luca Session Garden dashboard (2D + 3D) for OpenClaw sessions.

## Includes
- `app/index.html` — 2D dashboard (filters + theme toggle)
- `app/three.html` — 3D dashboard (character-based session view)
- `scripts/generate_sessions.py` — converts OpenClaw `sessions.json` to web-facing `sessions.json`
- `scripts/fetch_kenney_assets.sh` — fetches Kenney assets for 3D scene

## Quick start

```bash
# 1) fetch Kenney assets
./scripts/fetch_kenney_assets.sh

# 2) generate sessions snapshot
python3 ./scripts/generate_sessions.py

# 3) serve app directory
python3 -m http.server 8890 --directory ./app
```

Open:
- `http://localhost:8890/` (2D)
- `http://localhost:8890/three.html` (3D)

## Notes
- 3D view hides `STALE` sessions by default.
- Session data source path in `generate_sessions.py` currently targets:
  `/home/ubuntu/.openclaw/agents/main/sessions/sessions.json`
  Adjust for your environment if needed.
