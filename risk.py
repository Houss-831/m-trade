"""Gestion du risque de M-TRADE : ce qui protège le capital quand les signaux se trompent.

- Stop suiveur ATR (« chandelier exit », Chuck LeBeau ; stops en ATR des Turtles, 1983) :
  on sort si le prix recule de plus de N fois l'amplitude moyenne journalière depuis son plus haut.
- Pause après un stop : pas de rachat immédiat du même actif.
- Disjoncteur de portefeuille : si le portefeuille chute trop depuis son sommet,
  l'exposition est réduite automatiquement (principe de survie de tout gérant).
"""
from datetime import datetime, timedelta

import numpy as np

DEFAULTS = {"atr_mult": 3.0, "cooldown_days": 5, "dd_reduce": 0.12, "dd_cut": 0.20,
            "take_profit": True, "tp1_atr": 3.0, "tp1_sell": 0.33, "tp2_atr": 6.0, "tp2_sell": 0.5}


def corr_adjust(targets, prices, names, signals, lookback=60, min_factor=0.5):
    """Réduit les positions qui forment un même pari (Markowitz, 1952).

    Pour chaque actif acheté : facteur = 1 / √(somme des corrélations positives avec les autres
    actifs achetés, lui compris). Trois actifs parfaitement corrélés pèsent alors comme un seul
    pari et demi, au lieu de trois.
    """
    held = [s for s, w in targets.items() if w > 0 and s in prices]
    events = []
    if len(held) < 2:
        return targets, events
    c = prices[held].pct_change().iloc[-lookback:].corr().fillna(0).clip(lower=0)
    for s in held:
        f = max(min_factor, 1 / (c[s].sum() ** 0.5))
        if f < 0.9:
            mates = [names.get(o, o) for o in held if o != s and c.loc[s, o] > 0.5]
            targets[s] *= f
            txt = (f"taille réduite de {1 - f:.0%} : pari corrélé"
                   + (f" avec {', '.join(mates)}" if mates else " avec le reste du portefeuille"))
            events.append({"type": "corr", "symbol": s, "text": txt})
            if s in signals:
                signals[s]["reasons"].append(txt)
    return targets, events


def portfolio_drawdown(state, value):
    peak = max([h["value"] for h in state.get("history", [])] + [value, state["start_value"]])
    return value / peak - 1


def apply_risk(state, targets, last_px, last_atr, signals, now=None, cfg=None, rets=None):
    """Ajuste les poids cibles. Retourne (targets, événements, niveaux de stop)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    now = now or datetime.now()
    peaks = state.setdefault("peaks", {})
    cool = state.setdefault("cooldown", {})
    events, stops = [], {}

    tp = state.setdefault("tp", {})
    basis = state.get("cost_basis", {})
    value0 = state["cash"] + sum(q * last_px.get(s, 0) for s, q in state["positions"].items())
    for sym, qty in list(state["positions"].items()):
        px = last_px.get(sym)
        if not px or qty <= 0:
            continue
        peaks[sym] = max(peaks.get(sym, px), px)
        a = last_atr.get(sym) or 0
        stop = peaks[sym] - cfg["atr_mult"] * a
        # ---- Prises de profit échelonnées (take profit) ----
        entry = basis.get(sym, 0) / qty if qty else 0
        t = tp.get(sym, {"level": 0})
        if cfg.get("take_profit") and a and entry and value0:
            cur_w = qty * px / value0
            for lvl, mult, part in ((1, cfg["tp1_atr"], cfg["tp1_sell"]), (2, cfg["tp2_atr"], cfg["tp2_sell"])):
                if t["level"] < lvl and px >= entry + mult * a:
                    t = {"level": lvl, "cap": cur_w * (1 - part), "entry": entry}
                    msg = (f"prise de profit n°{lvl} : +{px / entry - 1:.1%} depuis l'achat "
                           f"(objectif {mult:.0f} ATR atteint), {part:.0%} de la position encaissée"
                           + (", stop remonté au prix d'achat" if lvl == 1 else ""))
                    events.append({"type": "tp", "symbol": sym, "text": msg})
                    if sym in signals:
                        signals[sym]["reasons"] = [msg] + signals[sym]["reasons"]
            if t["level"] >= 1:
                stop = max(stop, t.get("entry", entry))          # position « gratuite » : stop au prix d'achat
                if sym in targets:
                    targets[sym] = min(targets[sym], t["cap"])   # on ne rachète pas ce qui a été encaissé
        tp[sym] = t
        nxt = None
        if cfg.get("take_profit") and a and entry:
            lv = tp.get(sym, {}).get("level", 0)
            nxt = entry + (cfg["tp1_atr"] if lv == 0 else cfg["tp2_atr"]) * a if lv < 2 else None
        stops[sym] = {"stop": stop, "peak": peaks[sym], "distance": px / stop - 1 if stop > 0 else None,
                      "tp_next": nxt, "tp_level": tp.get(sym, {}).get("level", 0), "entry": entry}
        if a and px < stop:
            targets[sym] = 0.0
            cool[sym] = (now + timedelta(days=cfg["cooldown_days"])).isoformat()
            msg = (f"stop suiveur touché : prix {px:,.2f} sous le stop {stop:,.2f} "
                   f"(plus haut {peaks[sym]:,.2f} moins {cfg['atr_mult']:.0f} ATR)")
            events.append({"type": "stop", "symbol": sym, "text": msg})
            if sym in signals:
                signals[sym]["reasons"] = [msg] + signals[sym]["reasons"]

    # ---- Stops des paris à la baisse (positions courtes) : plus bas + k ATR ----
    troughs = state.setdefault("troughs", {})
    for sym, qty in list(state["positions"].items()):
        px = last_px.get(sym)
        if not px or qty >= 0:
            continue
        troughs[sym] = min(troughs.get(sym, px), px)
        a = last_atr.get(sym) or 0
        stop = troughs[sym] + cfg["atr_mult"] * a
        entry = basis.get(sym, 0) / qty if qty else 0
        stops[sym] = {"stop": stop, "peak": troughs[sym], "distance": stop / px - 1 if px else None,
                      "tp_next": None, "tp_level": 0, "entry": entry, "short": True}
        if a and px > stop:
            targets[sym] = 0.0
            cool[sym] = (now + timedelta(days=cfg["cooldown_days"])).isoformat()
            msg = (f"stop du pari à la baisse touché : prix {px:,.2f} au-dessus du stop {stop:,.2f} "
                   f"(plus bas {troughs[sym]:,.2f} plus {cfg['atr_mult']:.0f} ATR)")
            events.append({"type": "stop", "symbol": sym, "text": msg})
            if sym in signals:
                signals[sym]["reasons"] = [msg] + signals[sym]["reasons"]
    for sym in list(troughs):
        if sym not in state["positions"] or state["positions"][sym] >= 0:
            troughs.pop(sym, None)

    for sym in list(peaks):
        if sym not in state["positions"]:
            peaks.pop(sym, None)
    for sym in list(tp):
        if sym not in state["positions"]:
            tp.pop(sym, None)

    for sym, until in list(cool.items()):
        if datetime.fromisoformat(until) <= now:
            cool.pop(sym)
        elif targets.get(sym, 0) != 0 and sym not in state["positions"]:
            targets[sym] = 0.0
            events.append({"type": "cooldown", "symbol": sym,
                           "text": f"pause après stop jusqu'au {until[:10]}"})

    value = state["cash"] + sum(q * last_px.get(s, 0) for s, q in state["positions"].items())
    dd = portfolio_drawdown(state, value)
    factor = 1.0
    if dd <= -cfg["dd_cut"]:
        factor = 0.25
    elif dd <= -cfg["dd_reduce"]:
        factor = 0.5
    if factor < 1:
        for s in targets:
            targets[s] *= factor
        events.append({"type": "breaker", "symbol": None,
                       "text": f"disjoncteur : portefeuille à {dd:.1%} de son sommet, exposition × {factor}"})
    state["breaker"] = {"drawdown": dd, "factor": factor}

    # ---------- Limites fixées par l'utilisateur (en euros) ----------
    today = now.date().isoformat()
    day = state.get("day") or {}
    if day.get("date") != today:
        day = {"date": today, "start": value, "halted": False}
    day_pnl = value - day["start"]
    max_day = cfg.get("max_loss_day")
    max_total = cfg.get("max_loss_total")
    invest_max = cfg.get("invest_max")

    # 1) Montant maximum investi
    gross = sum(abs(w) for w in targets.values())
    if invest_max and value > 0 and gross * value > invest_max:
        f = invest_max / (gross * value)
        for s in targets:
            targets[s] *= f
        events.append({"type": "budget", "symbol": None,
                       "text": f"montant investi plafonné à {invest_max:,.0f} € (ton réglage)"})

    # 2) Budget de risque du jour : la perte probable d'une mauvaise journée (VaR 95 %)
    #    ne doit pas dépasser ce qu'il reste de ta perte maximale du jour
    var95 = None
    if rets is not None and len(rets) > 20:
        syms = [s for s in targets if s in rets and targets[s] != 0]
        if syms:
            w = np.array([targets[s] for s in syms])
            cov = rets[syms].iloc[-60:].cov().values
            var95 = float(1.65 * np.sqrt(max(w @ cov @ w, 0)) * value)
    budget = None
    if max_day:
        budget = max(0.0, max_day + min(0.0, day_pnl))
        if var95 and var95 > budget:
            f = budget / var95 if var95 else 0
            for s in targets:
                targets[s] *= f
            events.append({"type": "budget", "symbol": None,
                           "text": f"positions réduites de {1 - f:.0%} : une mauvaise journée pourrait coûter "
                                   f"{var95:,.0f} €, ton budget restant aujourd'hui est de {budget:,.0f} €"})
            var95 = var95 * f

    # 3) Perte maximale du jour atteinte : on coupe tout jusqu'à demain
    if max_day and (day.get("halted") or day_pnl <= -max_day):
        if not day.get("halted"):
            events.append({"type": "halt", "symbol": None,
                           "text": f"perte du jour de {-day_pnl:,.0f} € : ta limite de {max_day:,.0f} € est atteinte, "
                                   f"le bot vend tout et ne reprend que demain"})
        day["halted"] = True
        for s in targets:
            targets[s] = 0.0

    # 4) Perte totale maximale : le bot s'arrête jusqu'à ce que tu changes ce réglage
    if max_total:
        lost = state["start_value"] - value
        halted = state.get("halted_total")
        if halted and halted.get("limit") != max_total and lost < max_total:
            state.pop("halted_total", None)
            halted = None
        if halted or lost >= max_total:
            if not halted:
                state["halted_total"] = {"limit": max_total, "date": today}
                events.append({"type": "halt", "symbol": None,
                               "text": f"perte totale de {lost:,.0f} € : ta limite de {max_total:,.0f} € est atteinte, "
                                       f"le bot est arrêté jusqu'à ce que tu modifies ce réglage"})
            for s in targets:
                targets[s] = 0.0
    else:
        state.pop("halted_total", None)

    state["day"] = day
    state["risk_budget"] = {"day_pnl": day_pnl, "max_loss_day": max_day, "budget_left": budget,
                            "var95": var95, "max_loss_total": max_total, "invest_max": invest_max,
                            "halted_day": bool(day.get("halted")), "halted_total": bool(state.get("halted_total"))}
    return targets, events, stops
