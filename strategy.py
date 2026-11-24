"""Moteur de décision de M-TRADE.

Le score technique vient du conseil des 8 stratégies (voir strategies.py), pondéré selon
leur réussite récente. Il est ensuite combiné à l'actu (IA ou mots-clés), puis la taille des
positions est fixée par la volatilité. Chaque signal est accompagné de ses raisons en français.
"""
import numpy as np
import pandas as pd

from strategies import council, LIBRARY, NAMES, atr as atr_fn, adx as adx_fn


def rsi(series, n=14):
    delta = series.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def build_context(prices, p):
    """Calcule une fois tout ce dont le bot a besoin sur l'ensemble des actifs tradés."""
    score, weights, votes, skill = council(prices, window=p.get("council_window", 60), temperature=p.get("council_temp", 4.0),
                                          keys=p.get("strategies"), regime=p.get("regime_memory", True))
    vol = prices.pct_change().rolling(p["vol_days"]).std() * np.sqrt(252)
    return {"score": score, "weights": weights, "votes": votes, "skill": skill, "vol": vol,
            "rsi": rsi(prices, p["rsi_days"]), "sma_f": prices.rolling(p["sma_fast"]).mean(),
            "sma_s": prices.rolling(p["sma_slow"]).mean(),
            "mom": prices.pct_change(p["momentum_days"]), "atr": atr_fn(prices),
            "adx": adx_fn(prices), "stress": stress_factor(prices, p)}


def compute_scores(prices, p):
    """Compatibilité : (score, vol, rsi, sma_f, sma_s, mom) calculés par le conseil."""
    c = build_context(prices, p)
    return c["score"], c["vol"], c["rsi"], c["sma_f"], c["sma_s"], c["mom"]


def gate_scores(score, p, held=None):
    """Hystérésis : on entre au-dessus du seuil d'entrée, on ne sort que sous le seuil de sortie.

    Évite d'acheter et de revendre à chaque petite oscillation du score autour du seuil,
    ce qui coûte des frais sans rien rapporter. `held` : {symbole: +1/-1} positions déjà ouvertes.
    """
    entry = p["entry_threshold"]
    ext = p.get("exit_threshold", 0.4 * entry)
    short = bool(p.get("allow_short"))
    vals = score.fillna(0.0).values
    h = np.array([(held or {}).get(c, 0) for c in score.columns], dtype=int)
    out = np.zeros_like(vals)
    for i, r in enumerate(vals):
        keep_l = (h == 1) & (r >= ext)
        keep_s = (h == -1) & (r <= -ext) & short
        new_l = r >= entry
        new_s = (r <= -entry) & short
        h = np.where(keep_l | new_l, 1, np.where(keep_s | new_s, -1, 0))
        out[i] = np.where(h != 0, r, 0.0)
    return pd.DataFrame(out, index=score.index, columns=score.columns)


def apply_band(w, band=0.03):
    """Comme en réel : on ne réajuste une position que si l'écart dépasse `band` du capital
    (ou pour la fermer). Évite de payer des frais sur des micro-ajustements."""
    vals = w.fillna(0.0).values
    out = np.zeros_like(vals)
    cur = np.zeros(vals.shape[1])
    for i, t in enumerate(vals):
        move = (np.abs(t - cur) >= band) | ((t == 0) & (cur != 0))
        cur = np.where(move, t, cur)
        out[i] = cur
    return pd.DataFrame(out, index=w.index, columns=w.columns)


def stress_factor(px, p):
    """Filtre de crise : si la volatilité récente du marché explose par rapport à l'année,
    l'exposition globale est réduite (jusqu'à 40 % minimum)."""
    r = px.pct_change()
    ratio = (r.rolling(20).std() / r.rolling(252, min_periods=60).std()).median(axis=1)
    lvl = p.get("stress_level", 1.5)
    return (lvl / ratio).clip(lower=0.4, upper=1.0).fillna(1.0)


def weights_from_scores(score, vol, p, held=None, stress=None):
    """Transforme les scores en poids de portefeuille (volatilité cible, plafond par actif)."""
    s = gate_scores(score, p, held)
    if not p["allow_short"]:
        s = s.clip(lower=0)
    size = (p["target_vol"] / vol.replace(0, np.nan)).clip(upper=1.0)
    w = (s * size).clip(-p["max_weight"], p["max_weight"]).fillna(0.0)
    gross = w.abs().sum(axis=1)
    scale = (0.98 / gross).where(gross > 0.98, 1.0)   # garde ~2 % de cash pour les frais
    w = w.mul(scale, axis=0)
    if stress is not None:
        w = w.mul(stress.reindex(w.index).fillna(1.0), axis=0)
    return w


def explain(sym, name, prices, p, news_info=None, news_weight=None, ctx=None, held=False):
    """Signal du jour pour un actif, avec raisons lisibles."""
    if ctx is None:
        ctx = build_context(prices, p)
    if sym not in ctx["score"] or ctx["score"][sym].dropna().empty:
        return None
    last = ctx["score"].index[-1]
    tech = float(ctx["score"][sym].iloc[-1])
    sent = news_info["sentiment"] if news_info else 0.0
    nw = p["news_weight"] if news_weight is None else news_weight
    final = float(np.clip((1 - nw) * tech + nw * sent, -1, 1))

    w_now = ctx["weights"].iloc[-1]
    active = list(ctx["votes"].keys())
    votes = {k: float(ctx["votes"][k][sym].iloc[-1]) for k in active}
    contrib = sorted(((w_now[k] * votes[k], k) for k in active), key=lambda x: -abs(x[0]))

    reasons = []
    for c, k in contrib[:3]:
        if abs(votes[k]) < 0.05:
            continue
        sens = "achat" if votes[k] > 0 else "vente"
        reasons.append(f"{NAMES[k]} vote {sens} ({votes[k]:+.2f}, poids {w_now[k]:.0%})")
    agree = sum(1 for k in active if np.sign(votes[k]) == np.sign(tech) and abs(votes[k]) > 0.05)
    reasons.append(f"{agree} stratégie(s) sur {len(active)} vont dans le sens du score")
    rv = float(ctx["rsi"][sym].iloc[-1])
    if rv > 75:
        reasons.append(f"RSI {rv:.0f} : suracheté, risque de repli")
    elif rv < 25:
        reasons.append(f"RSI {rv:.0f} : survendu, rebond possible")
    av = float(ctx["adx"][sym].iloc[-1])
    reasons.append(f"ADX {av:.0f} : {'tendance forte' if av > 25 else 'marché sans tendance nette'}")
    if news_info and news_info.get("ai_explanation"):
        reasons.append(f"IA ({news_info['confidence']:.0%} de confiance) : {news_info['ai_explanation']}")
    elif news_info and news_info["count"]:
        tone = "positif" if sent > 0.15 else "négatif" if sent < -0.15 else "mitigé"
        reasons.append(f"actu : {news_info['count']} article(s), ton {tone} ({sent:+.2f})")

    thr = p["entry_threshold"]
    ext = p.get("exit_threshold", 0.4 * thr)
    if held and ext <= final < thr:
        action = "CONSERVER"
        reasons.append(f"score sous le seuil d'achat ({thr:.2f}) mais au-dessus du seuil de sortie ({ext:.2f}) : position conservée")
    elif final >= thr:
        action = "ACHAT"
    elif final <= -thr and p["allow_short"]:
        action = "VENTE À DÉCOUVERT"
    elif final <= -thr:
        action = "ÉVITER / SORTIR"
    else:
        action = "NEUTRE"
    conf = "élevée" if abs(final) > 0.6 else "moyenne" if abs(final) > 0.35 else "faible"
    components = {s["short"]: votes[s["key"]] for s in LIBRARY if s["key"] in votes}
    components["Actu / IA"] = float(sent)
    px_now = float(prices[sym].iloc[-1])
    return {"symbol": sym, "name": name, "date": last, "price": px_now,
            "components": components, "rsi": rv, "adx": av,
            "momentum": float(ctx["mom"][sym].iloc[-1]),
            "atr_pct": float(ctx["atr"][sym].iloc[-1] / px_now) if px_now else None,
            "agree": agree, "n_strat": len(active), "tech_score": tech, "news_score": sent, "score": final,
            "action": action, "confidence": conf, "volatility": float(ctx["vol"][sym].iloc[-1]),
            "reasons": reasons, "headlines": news_info["top"] if news_info else []}
