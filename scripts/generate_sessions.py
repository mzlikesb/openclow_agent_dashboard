#!/usr/bin/env python3
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

AGENTS_DIR = Path('/home/ubuntu/.openclaw/agents')
OUT = Path(__file__).resolve().parent.parent / 'app' / 'sessions.json'
OUT.parent.mkdir(parents=True, exist_ok=True)
AUTH_FILE = Path('/home/ubuntu/.openclaw/agents/main/agent/auth.json')

ACTIVE_MIN = 20
IDLE_MIN = 180

def fmt_reset_remaining(reset_ts_sec: float) -> str:
    """남은 리셋 시간을 사람이 읽기 쉬운 형태로 반환"""
    now = time.time()
    diff = reset_ts_sec - now
    if diff <= 0:
        return "now"
    mins = int(diff / 60)
    if mins < 60:
        return f"{mins}분"
    hours = mins // 60
    rem_mins = mins % 60
    if hours < 24:
        return f"{hours}h {rem_mins}m" if rem_mins else f"{hours}h"
    days = hours // 24
    return f"{days}일 {hours % 24}h"

def fetch_quota_resets() -> dict:
    """Gemini / Codex 리셋 타임 가져오기"""
    result = {}
    if not AUTH_FILE.exists():
        return result
    try:
        auth = json.loads(AUTH_FILE.read_text())
    except Exception:
        return result

    # --- Gemini ---
    try:
        token = auth.get('google-gemini-cli', {}).get('access', '')
        req = urllib.request.Request(
            'https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota',
            data=b'{}', method='POST',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        pro_reset = flash_reset = None
        for bucket in data.get('buckets', []):
            m = (bucket.get('modelId') or '').lower()
            rt = bucket.get('resetTime')
            if not rt:
                continue
            ts = time.mktime(time.strptime(rt, '%Y-%m-%dT%H:%M:%SZ')) - time.timezone
            if 'pro' in m and pro_reset is None:
                pro_reset = ts
            if 'flash' in m and flash_reset is None:
                flash_reset = ts
        if pro_reset:
            result['gemini_pro'] = {
                'label': 'Gemini Pro',
                'resetTs': pro_reset,
                'remaining': fmt_reset_remaining(pro_reset),
            }
        if flash_reset:
            result['gemini_flash'] = {
                'label': 'Gemini Flash',
                'resetTs': flash_reset,
                'remaining': fmt_reset_remaining(flash_reset),
            }
    except Exception:
        pass

    # --- Codex ---
    try:
        token = auth.get('openai-codex', {}).get('access', '')
        req = urllib.request.Request(
            'https://chatgpt.com/backend-api/wham/usage',
            headers={'Authorization': f'Bearer {token}', 'User-Agent': 'CodexBar', 'Accept': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        rl = data.get('rate_limit', {})
        pw = rl.get('primary_window') or {}
        sw = rl.get('secondary_window') or {}
        if pw.get('reset_at'):
            ts = float(pw['reset_at'])
            wh = round((pw.get('limit_window_seconds') or 10800) / 3600)
            result['codex_primary'] = {
                'label': f'Codex {wh}h',
                'resetTs': ts,
                'remaining': fmt_reset_remaining(ts),
            }
        if sw.get('reset_at'):
            ts = float(sw['reset_at'])
            wh = round((sw.get('limit_window_seconds') or 86400) / 3600)
            label = 'Codex Day' if wh >= 24 else f'Codex {wh}h'
            result['codex_secondary'] = {
                'label': label,
                'resetTs': ts,
                'remaining': fmt_reset_remaining(ts),
            }
    except Exception:
        pass

    return result

def classify_type(key: str) -> str:
    if ':cron:' in key:
        return 'CRON'
    if ':subagent:' in key:
        return 'SUBAGENT'
    if key.startswith('agent:reviewer:'):
        return 'REVIEWER'
    if key.startswith('agent:worker:'):
        return 'WORKER'
    if key.startswith('agent:main:') or key.endswith(':main'):
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

def detect_model_family(model_name: str) -> str:
    if not model_name:
        return 'Unknown'
    m = model_name.lower()
    if 'gemini' in m or 'google' in m:
        if 'flash' in m:
            return 'Gemini Flash'
        return 'Gemini Pro'
    if 'claude' in m or 'anthropic' in m:
        return 'Claude'
    if 'gpt' in m or 'codex' in m or 'openai' in m:
        return 'Codex'
    return 'Other'

# Collect sessions from all agents
all_sessions = {}
agent_dirs = [d for d in AGENTS_DIR.iterdir() if d.is_dir()]

for agent_dir in agent_dirs:
    session_file = agent_dir / 'sessions' / 'sessions.json'
    if session_file.exists():
        try:
            agent_sessions = json.loads(session_file.read_text())
            all_sessions.update(agent_sessions)
        except Exception:
            pass

items = []
now_ms = int(time.time() * 1000)

model_stats = {
    'Gemini Pro':   {'count': 0, 'tokens': 0, 'active': 0},
    'Gemini Flash': {'count': 0, 'tokens': 0, 'active': 0},
    'Claude':       {'count': 0, 'tokens': 0, 'active': 0},
    'Codex':        {'count': 0, 'tokens': 0, 'active': 0},
    'Other':        {'count': 0, 'tokens': 0, 'active': 0},
}

for key, v in all_sessions.items():
    total = int(v.get('totalTokens') or 0)
    ctx = int(v.get('contextWindow') or v.get('contextTokens') or 0)
    percent = round((total / ctx) * 100, 2) if ctx else 0.0
    updated = int(v.get('updatedAt') or 0)
    age_min = round((now_ms - updated) / 60000, 1) if updated else None
    aborted = bool(v.get('abortedLastRun'))

    s_type = classify_type(key)
    s_state = classify_state(updated, aborted) if updated else 'UNKNOWN'
    model_name = v.get('model', '')
    family = detect_model_family(model_name)

    if family in model_stats:
        model_stats[family]['count'] += 1
        model_stats[family]['tokens'] += total
        if s_state == 'ACTIVE':
            model_stats[family]['active'] += 1

    items.append({
        'key': key,
        'label': v.get('label'),
        'model': model_name,
        'family': family,
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

quota_resets = fetch_quota_resets()

summary = {
    'total': len(items),
    'active': len([x for x in items if x['state'] == 'ACTIVE']),
    'idle': len([x for x in items if x['state'] == 'IDLE']),
    'stale': len([x for x in items if x['state'] == 'STALE']),
    'byType': {k: len(v) for k, v in by_type.items()},
    'modelUsage': model_stats,
    'quotaResets': quota_resets,
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
print(f'wrote {OUT} ({len(items)} sessions from {len(agent_dirs)} agents)')
