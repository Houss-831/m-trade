"""Portefeuille fictif (paper trading) + journal de chaque décision."""
import csv
import json
import os
from datetime import datetime


def load_state(path, starting_cash):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"cash": starting_cash, "positions": {}, "start_value": starting_cash,
            "created": datetime.now().isoformat(timespec="seconds"), "history": []}


def save_state(state, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, default=str)


def portfolio_value(state, prices):
    return state["cash"] + sum(q * prices.get(s, 0) for s, q in state["positions"].items())


def rebalance(state, signals, target_weights, prices, fee_rate, min_trade_pct=0.03, now=None):
    """Ajuste les positions fictives vers les poids cibles. Retourne les ordres simulés."""
    value = portfolio_value(state, prices)
    ts = (now or datetime.now()).isoformat(timespec="seconds")
    orders = []
    # Ventes d'abord (libèrent du cash), puis achats
    items = sorted(target_weights.items(),
                   key=lambda kv: kv[1] * value / prices[kv[0]] - state["positions"].get(kv[0], 0.0)
                   if prices.get(kv[0]) else 0)
    for sym, w in items:
        px = prices.get(sym)
        if not px:
            continue
        cur_qty = state["positions"].get(sym, 0.0)
        target_qty = value * w / px
        delta = target_qty - cur_qty
        closing = w == 0 and cur_qty != 0
        if abs(delta * px) < value * min_trade_pct and not closing:
            continue
        if delta > 0:                            # jamais plus que le cash disponible
            delta = min(delta, max(state["cash"], 0) / (px * (1 + fee_rate)))
            target_qty = cur_qty + delta
            if delta * px < value * 0.005:
                continue
        cost = delta * px
        fee = abs(cost) * fee_rate
        state["cash"] -= cost + fee
        basis = state.setdefault("cost_basis", {})
        pnl = None
        if delta > 0:
            basis[sym] = basis.get(sym, 0.0) + cost + fee
        elif cur_qty > 0:                         # vente : gain/perte réalisé
            part = basis.get(sym, 0.0) * (-delta / cur_qty)
            pnl = -cost - fee - part
            basis[sym] = basis.get(sym, 0.0) - part
            state["realized_pnl"] = state.get("realized_pnl", 0.0) + pnl
        state["positions"][sym] = target_qty
        if abs(state["positions"][sym]) < 1e-9 or closing:
            state["positions"].pop(sym, None)
            basis.pop(sym, None)
        sig = signals.get(sym, {})
        side = "ACHAT" if delta > 0 else ("VENTE TOTALE" if closing else "ALLÈGEMENT")
        if delta > 0 and cur_qty > 0:
            side = "RENFORCEMENT"
        orders.append({"date": ts,
                       "symbol": sym, "name": sig.get("name", sym), "side": side,
                       "weight_before": round(cur_qty * px / value, 4),
                       "weight_after": round(target_qty * px / value, 4),
                       "qty": round(delta, 6), "price": round(px, 4),
                       "amount": round(abs(cost), 2), "fee": round(fee, 2),
                       "pnl": None if pnl is None else round(pnl, 2),
                       "score": round(sig.get("score", 0), 3),
                       "confidence": sig.get("confidence", ""),
                       "reasons": " | ".join(sig.get("reasons", [])),
                       "news": " | ".join(h["title"] for h in sig.get("headlines", [])[:3])})
    new_value = portfolio_value(state, prices)
    state["history"].append({"date": ts,
                             "value": round(new_value, 2)})
    return orders, new_value


def append_journal(orders, path):
    if not orders:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(orders[0].keys()))
        if new:
            w.writeheader()
        w.writerows(orders)
