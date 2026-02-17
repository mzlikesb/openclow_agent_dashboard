#!/usr/bin/env python3
import json
import time
from pathlib import Path

SRC = Path('/home/ubuntu/.openclaw/agents/main/sessions/sessions.json')
OUT = Path(__file__).resolve().parent.parent / 'app' / 'sessions.json'
OUT.parent.mkdir(parents=True, exist_ok=True)

ACTIVE_MIN = 20
IDLE_MIN = 180


def classify_type(key: str) -> str:
    if ':cron:' in key:
        return 'CRON'
    if ':subagent:' in key:
        return 'SUBAGENT'
    if key.endswith(':main'):
        return 'MAIN'
    return 'OTHER'


def classify_state(updated_ms: int, aborted: bool) -> str:
    now_ms = int(time.time() * 1000)
    age_min = (now_ms - int(updated_ms)) / 60000
    if age_min <= ACTIVE_MIN:
        return 'ACTIVE'
    if aborted or age_min > IDLE_MIN:
        return 'STALE'
    return 'IDLE'


def bar(percent: float, width=20):
    fill = int(round((percent / 100) * width))
    fill = max(0, min(width, fill))
    return '█' * fill + '░' * (width - fill)


try:
    raw = json.loads(SRC.read_text())
except Exception:
    raw = {}

now_ms = int(time.time() * 1000)
items = []

for key, v in raw.items():
    total = int(v.get('totalTokens') or 0)
    ctx = int(v.get('contextWindow') or v.get('contextTokens') or 0)
    percent = round((total / ctx) * 100, 2) if ctx else 0.0
    updated = int(v.get('updatedAt') or 0)
    age_min = round((now_ms - updated) / 60000, 1) if updated else None
    aborted = bool(v.get('abortedLastRun'))

    s_type = classify_type(key)
    s_state = classify_state(updated, aborted) if updated else 'UNKNOWN'

    items.append({
        'key': key,
        'label': v.get('label'),
        'model': v.get('model'),
        'channel': v.get('lastChannel') or v.get('channel'),
        'updatedAt': updated,
        'ageMin': age_min,
        'totalTokens': total,
        'contextTokens': ctx,
        'percent': percent,
        'bar': bar(percent),
        'state': s_state,
        'type': s_type,
        'abortedLastRun': aborted,
    })

items.sort(key=lambda x: x.get('updatedAt', 0), reverse=True)

by_type = {}
for it in items:
    by_type.setdefault(it['type'], []).append(it)

summary = {
    'total': len(items),
    'active': len([x for x in items if x['state'] == 'ACTIVE']),
    'idle': len([x for x in items if x['state'] == 'IDLE']),
    'stale': len([x for x in items if x['state'] == 'STALE']),
    'byType': {k: len(v) for k, v in by_type.items()}
}

out = {
    'generatedAt': int(time.time()),
    'generatedAtIso': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
    'activeThresholdMin': ACTIVE_MIN,
    'idleThresholdMin': IDLE_MIN,
    'summary': summary,
    'items': items,
    'groups': by_type,
}

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(f'wrote {OUT} ({len(items)} sessions)')
