"""Laboratoire de M-TRADE : le bot a-t-il un vrai avantage, ou de la chance ?

Trois tests classiques de la gestion quantitative :
1. Test de chance : t-statistique du rendement en excès du marché (Sharpe × √années).
   On en déduit la probabilité que l'avantage observé soit réel et pas dû au hasard.
2. Validation trimestre par trimestre : un bot solide bat le marché régulièrement,
   pas seulement sur un coup de chance.
3. Robustesse des réglages : on fait varier les paramètres du conseil. Si les bons résultats
   n'existent que pour un réglage précis, c'est du sur-ajustement (« overfitting »).

Limites : backtest vectorisé, frais inclus, mais sans les stops ni l'ajustement aux corrélations
(qui ne s'appliquent qu'en conditions réelles et dans le rejeu).
"""
import json
import math
import os
from datetime import date

import numpy as np
import pandas as pd

from strategies import council
from strategy import weights_from_scores


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _sim(px, p, fee, window=60, temperature=4.0, regime=None):
    rg = p.get("regime_memory", True) if regime is None else regime
    score, *_ = council(px, window=window, temperature=temperature, keys=p.get("strategies"), regime=rg)
    vol = px.pct_change().rolling(p["vol_days"]).std() * np.sqrt(252)
    from strategy import stress_factor
    from strategy import apply_band
    w = weights_from_scores(score, vol, p, stress=stress_factor(px, p))
    w = apply_band(w, p.get("min_trade_pct", 0.03)).shift(1).fillna(0.0)
    rets = px.pct_change().fillna(0.0)
    port = (w * rets).sum(axis=1) - w.diff().abs().sum(axis=1).fillna(0.0) * fee
    bench = rets.mean(axis=1)
    start = 252                                      # échauffement des indicateurs
    return port.iloc[start:], bench.iloc[start:]


def _sharpe(r):
    return float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0


def run_lab(prices, tradable, p, fee):
    px = prices[tradable].ffill().dropna(how="all")
    port, bench = _sim(px, p, fee)
    if len(port) < 60:
        return None
    excess = port - bench
    years = len(excess) / 252
    t = _sharpe(excess) * math.sqrt(years)
    prob = _norm_cdf(t)

    q = pd.DataFrame({"bot": port, "marche": bench})
    q = (1 + q).groupby(q.index.to_period("Q")).prod() - 1
    quarters = [{"q": f"T{per.quarter} {per.year}", "bot": round(float(r.bot), 4),
                 "market": round(float(r.marche), 4)} for per, r in q.iterrows()]
    wins = sum(1 for x in quarters if x["bot"] > x["market"])

    windows, temps = [20, 40, 60, 90, 120], [1.0, 2.0, 4.0, 8.0]
    grid = []
    for wdw in windows:
        row = []
        for tp in temps:
            pr, _ = _sim(px, p, fee, window=wdw, temperature=tp)
            row.append(round(_sharpe(pr), 2))
        grid.append(row)
    flat = [v for r in grid for v in r]
    good = sum(1 for v in flat if v > _sharpe(bench))

    with_r, _ = _sim(px, p, fee, regime=True)
    without_r, _ = _sim(px, p, fee, regime=False)
    regime_test = {"with": round(_sharpe(with_r), 2), "without": round(_sharpe(without_r), 2)}
    regime_test["use"] = regime_test["with"] > regime_test["without"]

    verdict = ("Avantage probable" if prob > 0.95 else "Indices encourageants" if prob > 0.8
               else "Pas de preuve d'avantage" if prob > 0.4 else "Plutôt en retard sur le marché")
    return {
        "date": date.today().isoformat(), "years": round(years, 2),
        "bot_return": round(float((1 + port).prod() - 1), 4),
        "market_return": round(float((1 + bench).prod() - 1), 4),
        "bot_sharpe": round(_sharpe(port), 2), "market_sharpe": round(_sharpe(bench), 2),
        "tstat": round(t, 2), "prob_edge": round(prob, 3), "verdict": verdict,
        "quarters": quarters, "quarters_won": wins, "regime_test": regime_test,
        "grid": {"windows": windows, "temperatures": temps, "sharpe": grid,
                 "current": [windows.index(60), temps.index(4.0)],
                 "beat_market": good, "total": len(flat)},
    }


def lab_cached(prices, tradable, p, fee, path="data/lab.json", force=False):
    """Le laboratoire est recalculé une fois par jour seulement (il est plus lourd)."""
    if not force and os.path.exists(path):
        try:
            with open(path) as f:
                old = json.load(f)
            if old.get("date") == date.today().isoformat():
                return old
        except Exception:
            pass
    res = run_lab(prices, tradable, p, fee)
    if res:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(res, f)
    return res
