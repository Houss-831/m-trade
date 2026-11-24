"""M-TRADE by Mahjoub Agency. Génère l'interface web du bot (docs/index.html + docs/data.json) et calcule ses scores.

Scores (0 à 100), calculés uniquement à partir de résultats mesurés :
- Performance  : rendement du bot face à « tout acheter et garder », et Sharpe.
- Intelligence : justesse des signaux (le prix est-il allé dans le sens prévu 5 jours après ?)
                 et part de ventes gagnantes. Ramené vers 50 tant que l'échantillon est petit.
- Risque       : volatilité réelle du portefeuille, concentration, part crypto, baisse en cours.
- Score M-TRADE : synthèse des trois.
"""
import csv
import json
import math
import os
from datetime import datetime

import numpy as np
import pandas as pd

ASSET_CLASS = {"^FCHI": "Actions", "^GDAXI": "Actions", "^GSPC": "Actions", "^IXIC": "Actions",
               "^N225": "Actions", "BTC-USD": "Crypto", "ETH-USD": "Crypto", "SOL-USD": "Crypto",
               "GC=F": "Matières", "CL=F": "Matières", "EURUSD=X": "Forex", "USDJPY=X": "Forex",
               "^TNX": "Taux"}
TEMPLATE = os.path.join(os.path.dirname(__file__), "dashboard_template.html")


def _clip(x, lo=0.0, hi=100.0):
    return float(max(lo, min(hi, x)))


def _f(x, nd=4):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else round(x, nd)
    except (TypeError, ValueError):
        return None


def read_journal(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _chg(s, n):
    s = s.dropna()
    return _f(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


def history_frame(state):
    h = pd.DataFrame(state.get("history", []))
    if h.empty:
        return pd.Series(dtype=float)
    h["date"] = pd.to_datetime(h["date"])
    return h.set_index("date")["value"].astype(float)


def compute_scores(state, journal, prices, tradable, weights, vols):
    equity = history_frame(state)
    daily = equity.resample("D").last().dropna() if not equity.empty else equity
    out = {"samples": int(len(daily))}

    # ---------- Performance ----------
    ret = daily.iloc[-1] / state["start_value"] - 1 if len(daily) else 0.0
    bench_ret = 0.0
    bench_curve = []
    if len(daily) > 1:
        px = prices[tradable].ffill()
        px = px[px.index >= daily.index[0].normalize()]
        if len(px) > 1:
            b = (1 + px.pct_change().fillna(0).mean(axis=1)).cumprod() * state["start_value"]
            bench_ret = float(b.iloc[-1] / state["start_value"] - 1)
            bench_curve = [[d.strftime("%Y-%m-%d"), round(v, 2)] for d, v in b.items()]
    r = daily.pct_change().dropna()
    sharpe = float(r.mean() / r.std() * np.sqrt(252)) if len(r) > 5 and r.std() > 0 else 0.0
    dd_series = daily / daily.cummax() - 1 if len(daily) else daily
    max_dd = float(dd_series.min()) if len(daily) else 0.0
    cur_dd = float(dd_series.iloc[-1]) if len(daily) else 0.0
    perf = _clip(50 + (ret - bench_ret) * 250 + (sharpe - 0.8) * 12)
    out["performance"] = {"score": round(perf), "return": _f(ret), "bench_return": _f(bench_ret),
                          "alpha": _f(ret - bench_ret), "sharpe": _f(sharpe, 2),
                          "max_dd": _f(max_dd), "current_dd": _f(cur_dd)}

    # ---------- Intelligence ----------
    correct = total = 0
    for row in journal:
        sym = row.get("symbol")
        if sym not in prices:
            continue
        d = pd.Timestamp(row["date"][:10])
        s = prices[sym].dropna()
        after = s[s.index > d]
        before = s[s.index <= d]
        if len(after) < 5 or before.empty:
            continue
        move = after.iloc[4] / before.iloc[-1] - 1
        buy = row["side"] in ("ACHAT", "RENFORCEMENT")
        total += 1
        correct += int((move > 0) == buy)
    closed = [float(r["pnl"]) for r in journal if r.get("pnl") not in (None, "", "None")]
    wins = sum(1 for p in closed if p > 0)
    acc = correct / total if total else 0.5
    winrate = wins / len(closed) if closed else 0.5
    raw = 100 * (0.6 * acc + 0.4 * winrate)
    n = total + len(closed)
    intel = 50 + (raw - 50) * n / (n + 20)              # prudence si peu de données
    out["intelligence"] = {"score": round(_clip(intel)), "accuracy": _f(acc), "signals_checked": total,
                           "win_rate": _f(winrate), "closed_trades": len(closed),
                           "calibrating": n < 20}

    # ---------- Risque ----------
    w = pd.Series(weights, dtype=float).reindex(tradable).fillna(0.0)
    rets = prices[tradable].pct_change().iloc[-60:].fillna(0)
    port_vol = float(np.sqrt(max(w.values @ rets.cov().values @ w.values, 0) * 252))
    max_w = float(w.abs().max()) if len(w) else 0.0
    crypto = float(w[[s for s in tradable if ASSET_CLASS.get(s) == "Crypto"]].sum())
    exposure = float(w.abs().sum())
    risk = _clip(0.55 * _clip(port_vol / 0.30 * 100) + 0.15 * _clip(max_w / 0.25 * 100)
                 + 0.15 * _clip(crypto / 0.5 * 100) + 0.15 * _clip(-cur_dd / 0.2 * 100))
    level = "Faible" if risk < 35 else "Modéré" if risk < 65 else "Élevé"
    out["risk"] = {"score": round(risk), "level": level, "port_vol": _f(port_vol),
                   "max_weight": _f(max_w), "crypto_share": _f(crypto), "exposure": _f(exposure)}

    out["oracle"] = round(0.4 * perf + 0.4 * _clip(intel) + 0.2 * (100 - risk))
    curve = [[d.strftime("%Y-%m-%d"), round(v, 2)] for d, v in daily.items()]
    return out, curve, bench_curve


def market_regime(prices, tradable, p):
    """Indice maison d'appétit pour le risque (0 = peur extrême, 100 = euphorie)."""
    px = prices[tradable].ffill()
    sma_f = px.rolling(p["sma_fast"]).mean().iloc[-1]
    sma_s = px.rolling(p["sma_slow"]).mean().iloc[-1]
    breadth = float((sma_f > sma_s).mean())
    rets = px.pct_change()
    vol20 = rets.iloc[-20:].std()
    vol1y = rets.iloc[-252:].std()
    mom = px.iloc[-1] / px.iloc[-61] - 1
    mz = (mom / (vol1y * np.sqrt(60))).clip(-2, 2).mean() / 2
    vr = float((vol20 / vol1y).mean())
    idx = _clip(50 * breadth + 30 * (mz + 1) / 2 + 20 * (1 - _clip(vr - 0.5, 0, 1)))
    label = ("Peur extrême" if idx < 20 else "Peur" if idx < 40 else "Neutre" if idx < 60
             else "Appétit" if idx < 80 else "Euphorie")
    from strategies import adx
    a = float(adx(px).iloc[-1].mean())
    return {"index": round(idx), "label": label, "breadth": _f(breadth), "momentum": _f(mz),
            "vol_ratio": _f(vr, 2), "adx": _f(a, 1),
            "mode": "Marché en tendance" if a > 25 else "Marché sans tendance nette"}


def correlations(prices, tradable, names):
    c = prices[tradable].pct_change().iloc[-60:].corr().round(2)
    return {"labels": [names.get(s, s) for s in tradable],
            "matrix": [[_f(v, 2) for v in row] for row in c.values.tolist()]}


def projection(curve_values, days=30, n=2000, seed=7):
    """Projection par ré-échantillonnage des rendements passés du bot (pas une prévision)."""
    v = pd.Series(curve_values, dtype=float)
    r = np.log(v).diff().dropna().iloc[-120:].values
    if len(r) < 15:
        return None
    rng = np.random.default_rng(seed)
    paths = v.iloc[-1] * np.exp(np.cumsum(rng.choice(r, size=(n, days)), axis=1))
    q = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
    return {"days": days, "p5": q[0].round(0).tolist(), "p25": q[1].round(0).tolist(),
            "p50": q[2].round(0).tolist(), "p75": q[3].round(0).tolist(),
            "p95": q[4].round(0).tolist(),
            "prob_gain": _f(float((paths[:, -1] > v.iloc[-1]).mean()), 3)}


def profile(scores, curve_values, weights, journal, start_value):
    """Six dimensions du bot, de 0 à 100, pour le radar."""
    v = pd.Series(curve_values, dtype=float)
    r = v.pct_change().dropna()
    pos_days = float((r > 0).mean()) if len(r) else 0.5
    w = np.array([abs(x) for x in weights.values()] or [0.0])
    eff_n = (w.sum() ** 2 / (w ** 2).sum()) if (w ** 2).sum() > 0 else 0
    fees = sum(float(o.get("fee") or 0) for o in journal)
    return [
        ["Performance", scores["performance"]["score"]],
        ["Intelligence", scores["intelligence"]["score"]],
        ["Sécurité", 100 - scores["risk"]["score"]],
        ["Régularité", round(_clip((pos_days - 0.4) / 0.2 * 100))],
        ["Diversification", round(_clip(eff_n / 6 * 100))],
        ["Discipline", round(_clip(100 - fees / start_value * 2000))],
    ]


def score_snapshot(state, journal_path, prices, cfg, when):
    tradable = [s for s in cfg.TRADABLE if s in prices]
    last = prices.iloc[-1]
    value = state["cash"] + sum(q * float(last.get(s, 0)) for s, q in state["positions"].items())
    weights = {s: q * float(last.get(s, 0)) / value for s, q in state["positions"].items()} if value else {}
    sc, _, _ = compute_scores(state, read_journal(journal_path), prices, tradable, weights, {})
    snap = {"date": when.strftime("%Y-%m-%d %H:%M"), "oracle": sc["oracle"],
            "performance": sc["performance"]["score"], "intelligence": sc["intelligence"]["score"],
            "risk": sc["risk"]["score"]}
    hist = state.setdefault("score_history", [])
    if hist and hist[-1]["date"][:13] == snap["date"][:13]:
        hist[-1] = snap
    else:
        hist.append(snap)
    del hist[:-400]
    return snap


def council_payload(prices, tradable, ctx, cfg):
    from strategies import LIBRARY, standalone
    if ctx is None:
        return None
    w, skill, V = ctx["weights"], ctx["skill"], ctx["votes"]
    perf = standalone(prices[tradable], cfg.PAPER["fee_rate"])
    hist = w.iloc[-120::2]
    out = {"strategies": [], "weights_history": {
        "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
        "series": {s["key"]: [_f(x, 3) for x in hist[s["key"]].tolist()] for s in LIBRARY if s["key"] in V}}}
    for s in LIBRARY:
        k = s["key"]
        if k not in V:
            continue
        out["strategies"].append({**s, "weight": _f(w[k].iloc[-1], 3), "skill": _f(skill[k].iloc[-1], 2),
                                  "standalone": {kk: _f(vv, 3) for kk, vv in perf[k].items()},
                                  "votes": {sym: _f(V[k][sym].iloc[-1], 2) for sym in tradable}})
    return out


def convictions(signals, stops):
    s = sorted(signals.values(), key=lambda x: -x["score"])
    pick = lambda x, why: {"symbol": x["symbol"], "name": x["name"], "score": _f(x["score"], 3),
                           "action": x["action"], "confidence": x["confidence"], "why": why,
                           "agree": x.get("agree")}
    out = []
    if s:
        top = s[0]
        out.append({**pick(top, top["reasons"][0] if top["reasons"] else ""), "kind": "Plus forte conviction"})
        low = s[-1]
        out.append({**pick(low, low["reasons"][0] if low["reasons"] else ""), "kind": "Plus forte méfiance"})
    near = [(v["distance"], k) for k, v in stops.items() if v.get("distance") is not None]
    if near:
        dist, k = min(near)
        if k in signals:
            out.append({**pick(signals[k], f"à {dist:.1%} de son stop suiveur"), "kind": "Position à surveiller"})
    return out


def build_payload(prices, signals, state, journal_path, news, macro, cfg, now=None, ctx=None, events=None, stops=None):
    now = now or datetime.now()
    raw = prices.attrs.get("raw", prices)
    tradable = [s for s in cfg.TRADABLE if s in prices]
    last = prices.iloc[-1]
    value = state["cash"] + sum(q * float(last.get(s, 0)) for s, q in state["positions"].items())
    weights = {s: q * float(last.get(s, 0)) / value for s, q in state["positions"].items()} if value else {}
    vols = {s: sig.get("volatility") for s, sig in signals.items()}
    journal = read_journal(journal_path)
    scores, curve, bench = compute_scores(state, journal, prices, tradable, weights, vols)

    assets = []
    for sym, name in cfg.UNIVERSE.items():
        if sym not in raw:
            continue
        s = raw[sym].dropna()
        if s.empty:
            continue
        sig = signals.get(sym, {})
        assets.append({
            "symbol": sym, "name": name, "class": ASSET_CLASS.get(sym, "Autre"),
            "currency": "%" if sym == "^TNX" else cfg.CURRENCY.get(sym, "USD"),
            "price": _f(s.iloc[-1]), "d1": _chg(s, 1), "d5": _chg(s, 5), "m1": _chg(s, 21),
            "y1": _chg(s, 252), "spark": [_f(v, 4) for v in s.iloc[-250:].tolist()],
            "tradable": sym in tradable, "action": sig.get("action"),
            "score": _f(sig.get("score"), 3), "tech": _f(sig.get("tech_score"), 3),
            "news": _f(sig.get("news_score"), 3), "confidence": sig.get("confidence"),
            "vol": _f(sig.get("volatility")), "reasons": sig.get("reasons", []),
            "components": {k: _f(v, 3) for k, v in sig.get("components", {}).items()},
            "patterns": sig.get("patterns", []),
            "rsi": _f(sig.get("rsi"), 1),
            "ai": next((r for r in sig.get("reasons", []) if r.startswith("IA")), None),
            "adx": _f(sig.get("adx"), 1), "atr_pct": _f(sig.get("atr_pct")), "agree": sig.get("agree"),
            "stop": _f((stops or {}).get(sym, {}).get("stop", float("nan")) * float(s.iloc[-1]) / float(prices[sym].iloc[-1]), 4)
                    if sym in (stops or {}) and sym in prices else None,
            "stop_dist": _f((stops or {}).get(sym, {}).get("distance")),
            "pipe": {k: _f(v) for k, v in sig.get("pipe", {}).items()} or None,
            "tech": _f(sig.get("tech_score"), 3), "n_strat": sig.get("n_strat"),
            "weight": _f(weights.get(sym, 0.0)),
        })

    basis = state.get("cost_basis", {})
    positions = []
    for sym, q in state["positions"].items():
        v = q * float(last.get(sym, 0))
        positions.append({"symbol": sym, "name": cfg.UNIVERSE.get(sym, sym), "value": _f(v, 2),
                          "weight": _f(v / value if value else 0),
                          "pnl": _f(v - basis.get(sym, v), 2),
                          "pnl_pct": _f(v / basis[sym] - 1 if basis.get(sym) else 0)})
    positions.sort(key=lambda p: -p["value"])

    orders = list(reversed(journal))[:150]
    for o in orders:
        for k in ("amount", "price", "fee", "score", "weight_before", "weight_after"):
            o[k] = _f(o.get(k))
        o["pnl"] = _f(o.get("pnl")) if o.get("pnl") not in ("", "None", None) else None

    news_out = [{"title": n["title"], "source": n["source"], "link": n.get("link", ""),
                 "date": n["date"].isoformat() if hasattr(n.get("date"), "isoformat") else None}
                for n in news[:20]]

    return {
        "generated": now.isoformat(timespec="seconds"),
        "macro": macro,
        "ai_enabled": bool(macro),
        "portfolio": {"value": _f(value, 2), "start": state["start_value"], "cash": _f(state["cash"], 2),
                      "realized": _f(state.get("realized_pnl", 0), 2), "created": state.get("created"),
                      "positions": positions, "curve": curve, "bench": bench},
        "scores": scores, "assets": assets, "orders": orders, "news": news_out,
        "regime": market_regime(prices, tradable, cfg.STRATEGY),
        "ohlc": {s: [[d.strftime("%Y-%m-%d"), _f(r.Open, 4), _f(r.High, 4), _f(r.Low, 4), _f(r.Close, 4), _f(r.Volume, 0)]
                     for d, r in o.iloc[-200:].iterrows()]
                 for s, o in (getattr(cfg, "OHLC", None) or {}).items() if s in cfg.UNIVERSE},
        "fx": {"EURUSD": _f(raw["EURUSD=X"].iloc[-1], 5) if "EURUSD=X" in raw else None,
               "USDJPY": _f(raw["USDJPY=X"].iloc[-1], 3) if "USDJPY=X" in raw else None},
        "correlations": correlations(prices, tradable, cfg.UNIVERSE),
        "projection": projection([c[1] for c in curve]),
        "profile": profile(scores, [c[1] for c in curve], weights, journal, state["start_value"]),
        "score_history": state.get("score_history", []),
        "council": council_payload(prices, tradable, ctx, cfg),
        "risk_mgmt": {"events": events or [], "breaker": state.get("breaker", {}),
                      "settings": getattr(cfg, "RISK", {}),
                      "stops": [{"symbol": s, "name": cfg.UNIVERSE.get(s, s), "stop": _f(v["stop"], 4),
                                 "peak": _f(v["peak"], 4), "distance": _f(v["distance"]),
                                 "tp_next": _f(v.get("tp_next"), 4), "tp_level": v.get("tp_level", 0),
                                 "entry": _f(v.get("entry"), 4)}
                                for s, v in (stops or {}).items()]},
        "convictions": convictions(signals, stops or {}),
        "user_profile": getattr(cfg, "PROFILE", None),
        "risk_budget": {k: (_f(v, 2) if isinstance(v, float) else v) for k, v in state.get("risk_budget", {}).items()},
        "universe": [{"symbol": s, "name": n, "class": ASSET_CLASS.get(s, "Autre")} for s, n in cfg.UNIVERSE.items()
                     if s in getattr(cfg, "ALL_TRADABLE", cfg.TRADABLE)],
        "library": __import__("strategies").LIBRARY,
        "effective": {"strategy": cfg.STRATEGY, "risk": {k: v for k, v in cfg.RISK.items()}},
        "settings": {"strategy": cfg.STRATEGY, "fee_rate": cfg.PAPER["fee_rate"],
                     "ai_model": cfg.AI["model"] if bool(macro) else None,
                     "ai_weight": cfg.AI["news_weight"]},
    }


SOURCE_FILES = ["main.py", "strategies.py", "strategy.py", "risk.py", "settings.py", "ai_analyst.py",
                "paper.py", "lab.py", "dashboard.py", "data.py", "report.py", "config.py"]


def read_sources():
    base = os.path.dirname(os.path.abspath(__file__))
    out = {}
    for f in SOURCE_FILES:
        try:
            with open(os.path.join(base, f), encoding="utf-8") as fh:
                out[f] = fh.read()
        except OSError:
            pass
    return out


def write_dashboard(payload, out_dir="docs"):
    os.makedirs(out_dir, exist_ok=True)
    payload.setdefault("source", read_sources())
    data = json.dumps(payload, ensure_ascii=False, default=str)
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as f:
        f.write(data)
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__ORACLE_DATA__", data.replace("</", "<\\/"))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.join(out_dir, "index.html")
