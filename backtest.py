"""Backtest : la stratégie technique appliquée au passé, frais inclus.

Important : le sentiment actu n'est PAS backtesté (pas d'historique d'actus).
Un bon backtest ne garantit rien pour l'avenir.
"""
import numpy as np
import pandas as pd

from strategy import compute_scores, weights_from_scores


def metrics(equity):
    rets = equity.pct_change().dropna()
    years = len(rets) / 252
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
    dd = (equity / equity.cummax() - 1).min()
    return {"rendement_total": equity.iloc[-1] / equity.iloc[0] - 1,
            "rendement_annuel": cagr, "sharpe": sharpe, "pire_baisse": dd,
            "jours_gagnants": (rets > 0).mean()}


def run_backtest(prices, p, fee_rate=0.001, tradable=None):
    prices = prices[tradable] if tradable else prices
    from strategy import stress_factor
    score, vol, *_ = compute_scores(prices, p)
    from strategy import apply_band
    w = weights_from_scores(score, vol, p, stress=stress_factor(prices, p))
    w = apply_band(w, p.get("min_trade_pct", 0.03)).shift(1).fillna(0.0)   # pas de triche : signal d'hier
    rets = prices.pct_change().fillna(0.0)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    port = (w * rets).sum(axis=1) - turnover * fee_rate
    start = p["sma_slow"] + 1
    equity = (1 + port.iloc[start:]).cumprod()
    bench = (1 + rets.iloc[start:].mean(axis=1)).cumprod()        # tout acheter à parts égales
    return {"strategie": metrics(equity), "achat_conserve": metrics(bench),
            "equity": equity, "benchmark": bench,
            "exposition_moyenne": float(w.iloc[start:].abs().sum(axis=1).mean()),
            "rotation_annuelle": float(turnover.iloc[start:].mean() * 252),
            "frais_totaux": float((turnover.iloc[start:] * fee_rate).sum())}


def format_report(res):
    lines = ["📈 BACKTEST (stratégie technique, frais inclus)", ""]
    labels = {"rendement_total": "Rendement total", "rendement_annuel": "Rendement annuel",
              "sharpe": "Ratio de Sharpe", "pire_baisse": "Pire baisse",
              "jours_gagnants": "Jours gagnants"}
    lines.append(f"{'':20}{'Bot':>12}{'Achat-conserve':>16}")
    for k, lab in labels.items():
        a, b = res["strategie"][k], res["achat_conserve"][k]
        fmt = (lambda x: f"{x:.2f}") if k == "sharpe" else (lambda x: f"{x:+.1%}")
        lines.append(f"{lab:20}{fmt(a):>12}{fmt(b):>16}")
    lines.append(f"\nExposition moyenne : {res['exposition_moyenne']:.0%} du capital")
    lines.append(f"Rotation : {res['rotation_annuelle']:.1f}× le capital par an · frais cumulés {res['frais_totaux']:.1%}")
    lines.append("⚠️ Les performances passées ne préjugent pas des performances futures.")
    return "\n".join(lines)
