"""Fil de signaux de M-TRADE : tout ce qui change d'un passage à l'autre.

Le bot compare son analyse à celle du passage précédent et produit des événements
(nouvelle décision, RSI extrême, stop proche, filtre de crise, changement de méthode dominante...).
L'appli les affiche dans l'onglet Signaux, et les plus importants partent sur Telegram.
"""
from datetime import datetime

LEVELS = {"info": 0, "attention": 1, "important": 2}


def _ev(now, kind, level, title, text, symbol=None):
    return {"date": now.isoformat(timespec="minutes"), "kind": kind, "level": level,
            "title": title, "text": text, "symbol": symbol}


def build_feed(state, signals, events, stops, ctx, names, now=None, keep=200):
    now = now or datetime.now()
    prev = state.get("last_signals", {})
    feed = []
    for sym, s in signals.items():
        p = prev.get(sym)
        if p and p.get("action") != s["action"]:
            lvl = "important" if s["action"] in ("ACHAT", "ÉVITER / SORTIR", "VENTE À DÉCOUVERT") else "attention"
            feed.append(_ev(now, "decision", lvl, f"{s['name']} : {p['action'].lower()} → {s['action'].lower()}",
                            f"score {p['score']:+.2f} → {s['score']:+.2f}. " + (s["reasons"][0] if s["reasons"] else ""), sym))
        elif p and abs(s["score"] - p["score"]) >= 0.25:
            sens = "renforce" if abs(s["score"]) > abs(p["score"]) else "s'affaiblit"
            feed.append(_ev(now, "momentum", "info", f"{s['name']} : la conviction {sens}",
                            f"score {p['score']:+.2f} → {s['score']:+.2f}", sym))
        rsi, prsi = s.get("rsi"), (p or {}).get("rsi")
        if rsi is not None and rsi > 75 and (prsi is None or prsi <= 75):
            feed.append(_ev(now, "rsi", "attention", f"{s['name']} suracheté", f"RSI {rsi:.0f} : risque de repli à court terme", sym))
        if rsi is not None and rsi < 25 and (prsi is None or prsi >= 25):
            feed.append(_ev(now, "rsi", "attention", f"{s['name']} survendu", f"RSI {rsi:.0f} : rebond technique possible", sym))
        adx, padx = s.get("adx"), (p or {}).get("adx")
        if adx is not None and padx is not None and adx > 25 >= padx:
            feed.append(_ev(now, "trend", "info", f"{s['name']} entre en tendance", f"ADX {adx:.0f} : les méthodes de tendance gagnent en fiabilité", sym))
    alerted = set(state.get("stop_alerted", []))
    for sym in list(alerted):
        st = (stops or {}).get(sym)
        if not st or (st.get("distance") or 0) > 0.06:      # réarmé seulement quand le prix s'est éloigné
            alerted.discard(sym)
    for sym, st in (stops or {}).items():
        d = st.get("distance")
        if d is not None and d < 0.03 and sym not in alerted:
            alerted.add(sym)
            feed.append(_ev(now, "stop", "attention", f"{names.get(sym, sym)} proche de son stop",
                            f"à {d:.1%} du niveau de sortie automatique", sym))
    for e in events:
        if e["type"] in ("corr", "budget", "cooldown"):     # récurrents : visibles dans le Bouclier, pas dans le fil
            continue
        lvl = "important" if e["type"] in ("stop", "halt", "breaker", "event") else "info"
        feed.append(_ev(now, "risk:" + e["type"], lvl, "Bouclier : " + {"stop": "stop déclenché", "halt": "garde-fou activé",
                        "breaker": "disjoncteur", "corr": "taille ajustée", "budget": "budget respecté",
                        "cooldown": "rachat bloqué", "event": "événement à risque", "tp": "prise de profit"}.get(e["type"], e["type"]), e["text"], e.get("symbol")))
    if ctx is not None:
        w = ctx["weights"].iloc[-1]
        lead = str(w.idxmax())
        if state.get("last_leader") and state["last_leader"] != lead:
            from strategies import NAMES
            feed.append(_ev(now, "council", "attention", "Le conseil change de méthode dominante",
                            f"{NAMES.get(state['last_leader'])} → {NAMES.get(lead)} ({w[lead]:.0%} des voix) : le marché change de régime"))
        state["last_leader"] = lead
        sf = float(ctx["stress"].iloc[-1])
        was = state.get("last_stress", 1.0)
        if sf < 0.99 and was >= 0.99:
            feed.append(_ev(now, "stress", "important", "Filtre de crise activé",
                            f"la volatilité du marché explose : exposition globale × {sf:.2f}"))
        elif sf >= 0.99 and was < 0.99:
            feed.append(_ev(now, "stress", "attention", "Filtre de crise levé", "le marché se calme, exposition normale"))
        state["last_stress"] = sf
        th = ctx.get("thermo") if isinstance(ctx, dict) else None
        if th:
            sc, prev = th["score"], state.get("thermo_last", 0)
            for lvl_, name_, imp in ((75, "crise", "important"), (55, "stress", "attention")):
                if sc >= lvl_ > prev:
                    feed.append(_ev(now, "thermo", imp, f"Thermomètre de crise : {name_} ({sc:.0f}/100)",
                                    f"profil proche de {th['analogue']} — {th['lesson']}"))
                    break
            else:
                if prev >= 55 > sc:
                    feed.append(_ev(now, "thermo", "info", f"Thermomètre de crise redescendu ({sc:.0f}/100)",
                                    "les symptômes de crise s'estompent, exposition normale"))
            state["thermo_last"] = sc
    for sym, sg in signals.items():
        for pt in sg.get("patterns", []):
            if pt["ago"] == 0 and pt["dir"] != 0:
                feed.append(_ev(now, "pattern", "info", f"{names.get(sym, sym)} : {pt['name']}",
                                f"{pt['text']} {'Signal haussier' if pt['dir'] > 0 else 'Signal baissier'} pris en compte par le conseil.", sym))
    state["last_signals"] = {s: {"action": v["action"], "score": v["score"], "rsi": v.get("rsi"), "adx": v.get("adx")}
                             for s, v in signals.items()}
    state["stop_alerted"] = sorted(alerted)
    hist = state.setdefault("feed", [])
    hist.extend(feed)
    del hist[:-keep]
    return feed


def data_health(raw, tradable, now=None):
    """Contrôle qualité des données : actifs absents, trop courts ou figés."""
    import pandas as pd
    now = pd.Timestamp(now or datetime.now()).normalize()
    out = []
    for s in tradable:
        if s not in raw:
            out.append({"symbol": s, "ok": False, "why": "aucune donnée"})
            continue
        col = raw[s].dropna()
        if len(col) < 260:
            out.append({"symbol": s, "ok": False, "why": f"historique trop court ({len(col)} jours)"})
            continue
        age = (now - col.index[-1].normalize()).days
        lim = 3 if "-USD" in s else 5                    # crypto cote 7j/7, le reste ferme le week-end
        flat = (col.iloc[-5:].nunique() == 1)
        ok = age <= lim and not flat
        why = "" if ok else (f"dernier cours vieux de {age} jours" if age > lim else "cours figé sur 5 jours")
        out.append({"symbol": s, "ok": ok, "why": why, "last": col.index[-1].strftime("%Y-%m-%d"), "age": int(age)})
    return out
