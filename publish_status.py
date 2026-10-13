#!/usr/bin/env python3
"""Build public status.json (NO dollar amounts) and push if changed."""
import json, os, re, subprocess, datetime as dt
from zoneinfo import ZoneInfo
CT = ZoneInfo("America/Chicago"); B = "/workspace/project-million"; HERE = os.path.dirname(os.path.abspath(__file__))
def load(p):
    try: return json.load(open(p)), os.path.getmtime(p)
    except Exception: return {}, None
def clean(s):  # strip $amounts, wallet/contract addresses, account numbers
    s = str(s or "")
    s = re.sub(r"((?i:liquidity)[^$]{0,15})\$\s?(\d[\d,.]*\s?[KMB])", r"\1\2", s)  # public pool liquidity ok
    s = re.sub(r"\$\s?\d[\d,.]*\s?[KkMmBb]?", "", s)
    s = re.sub(r"[1-9A-HJ-NP-Za-km-z]{6,}…|[1-9A-HJ-NP-Za-km-z]{30,}", "", s)
    s = re.sub(r"[•\u2022]+\d+", "", s)
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;:")
    return s if len(s) <= 110 else s[:107].rstrip() + "…"
def mc(v):
    try: v = float(v)
    except Exception: return None
    return f"{v/1e6:.2f}M MC" if v >= 1e6 else f"{v/1e3:.0f}K MC"
def ts(t):
    if not t: return None
    try: d = dt.datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=CT)
    return d.astimezone(CT)
def ct(d): return d.strftime("%-I:%M %p CT") if d else None
def mt(m): return dt.datetime.fromtimestamp(m, CT) if m else None

led, lm = load(f"{B}/ledger.json"); risk, rm = load(f"{B}/risk.json")
sc, sm = load(f"{B}/scout.json"); pre, pm = load("/workspace/prelaunch-seen.json")
ev = []
def add(d, agent, kind, text, to=None):
    if d: ev.append({"t": d.isoformat(), "time": ct(d), "agent": agent, "kind": kind, "text": clean(text), "to": to})

# player
trades = sorted(led.get("trades", []), key=lambda x: x.get("time", ""))
for t in trades:
    verb = {"sell": "sold", "buy": "bought"}.get(t.get("side"), t.get("side", "traded"))
    m = mc(t.get("mc") or t.get("exit_mc"))
    add(ts(t.get("time")), "player", "trade", f"{verb} {t.get('coin')}" + (f" at {m}" if m else ""), "advisor")
bags = []
rp = {p.get("coin"): p for p in risk.get("positions", [])}
for o in led.get("open", []):
    c = o.get("coin"); cb, mv = o.get("cost_basis"), o.get("mark_value")
    r = rp.get(c, {})
    if cb and mv is not None: d = "up" if mv > cb else "down" if mv < cb else "flat"
    elif r.get("pnl_pct") is not None: d = "up" if r["pnl_pct"] > 0 else "down"
    else: d = "flat"
    bags.append({"coin": c, "type": o.get("type"), "pnl_direction": d, "mc": mc(o.get("mark_mc") or r.get("mcap_usd"))})
for c, r in rp.items():
    if c not in [b["coin"] for b in bags]:
        p = r.get("pnl_pct"); bags.append({"coin": c, "type": r.get("status"), "pnl_direction": "flat" if p is None else ("up" if p > 0 else "down"), "mc": mc(r.get("mcap_usd"))})
last_trade = ts(trades[-1]["time"]) if trades else None
# advisor
flags = [p.get("flag", "green") for p in risk.get("positions", [])]
hit = any(f == "red" and ("stop" in str(p.get("note","")).lower() and "hit" in str(p.get("note","")).lower()) for f, p in zip(flags, risk.get("positions", []))) or bool(risk.get("alert"))
risk_level = "red" if hit or any(str(x.get("rugcheck","")).lower() == "fail" for x in risk.get("positions", [])) else ("yellow" if any(f in ("yellow","red") for f in flags) else "green")
for p in risk.get("passed", []): add(ts(risk.get("updated")), "advisor", "pass", f"passed {p.get('coin')}: {p.get('reason')}", "bro")
# scout
flagged = [{"coin": clean(f.get("name")), "result": clean(f.get("result")), "time": f.get("time")} for f in sc.get("flagged", [])]
dumpster = [{"coin": clean(s.get("name")), "reason": clean(s.get("reason"))} for s in sc.get("skipped", [])]
su = ts(sc.get("updated")) or mt(sm); now = dt.datetime.now(CT)
scanning = bool(su and (now - su).total_seconds() < 15*60)
for f in sc.get("flagged", []): add(su, "trench dig", "flag", f"flagged {clean(f.get('name'))} to advisor", "advisor")
add(su, "trench dig", "scan", f"dug {len(dumpster)+len(flagged)} tokens, {len(dumpster)} dumped, {len(flagged)} flagged", "bro")
# bro
for k, s in (pre.get("stories") or {}).items():
    add(ts(s.get("first_seen")), "bro", "alert", f"pre-launch watch: {k.split('-')[0]} ({s.get('status')})", "trench dig")
lr = ts(pre.get("last_run"))
add(lr, "bro", "check", "ran pre-launch sweep", "trench dig")
ev.sort(key=lambda e: e["t"], reverse=True); ev = ev[:15]
def latest(a): return next((e for e in ev if e["agent"] == a), None)
w = sc.get("watching", [])
agents = {
 "bro": {"role": "Overseer", "where": "rooftop watchtower", "activity": f"watching {', '.join(clean(x.get('name')) for x in w[:2]) or 'the city'}; next: market brief 8:22 AM CT", "updated": ct(lr or mt(pm))},
 "trench dig": {"role": "Scout", "where": "alleys & docks", "activity": ("digging the trenches" if scanning else "resting between scans") + f" — {len(dumpster)} in the dumpster", "updated": ct(su)},
 "advisor": {"role": "Risk", "where": "clocktower", "activity": f"risk {risk_level.upper()}: " + ", ".join(f"{p.get('coin')} {p.get('flag')}" for p in risk.get("positions", [])), "updated": ct(ts(risk.get("updated")) or mt(rm))},
 "player": {"role": "Trader", "where": "the vault", "activity": f"holding {', '.join(b['coin'] for b in bags)}; last move: " + (latest("player")["text"] if latest("player") else "none"), "updated": ct(ts(led.get("updated")) or mt(lm))},
}
out = {"risk_level": risk_level, "bags": bags, "last_trade_ts": last_trade.isoformat() if last_trade else None,
       "scanning": scanning, "flagged": flagged, "dumpster": dumpster, "agents": agents, "events": ev}
blob = json.dumps(out, indent=1, ensure_ascii=False)
assert not re.search(r"\$\s?\d", blob), "dollar amount leaked"
p = os.path.join(HERE, "status.json")
old = open(p).read() if os.path.exists(p) else None
if old != blob: open(p, "w").write(blob)
g = lambda *a: subprocess.run(["git", "-C", HERE, *a], check=True)
g("add", "status.json", "city", "index.html", "publish_status.py")
if subprocess.run(["git", "-C", HERE, "diff", "--cached", "--quiet"]).returncode:
    g("commit", "-qm", f"status {now:%H:%M} CT"); g("push", "-q"); print("pushed")
else: print("unchanged")
