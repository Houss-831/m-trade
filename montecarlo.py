"""Analyse avant chaque investissement : 10 000 scénarios simulés.

Principe (« que s'est-il passé, les fois où la situation ressemblait à celle-ci ? ») :
1. On cherche dans l'historique accumulé toutes les fois où le même signal est apparu
   (même sens, même niveau de conviction) : ce sont les « analogues ».
2. On prend ce que le prix a fait dans les heures ou les jours qui ont suivi chacun d'eux,
   exprimé en multiples d'ATR (donc comparable quelle que soit la volatilité du moment).
3. On recompose 10 000 trajectoires possibles en mélangeant des morceaux de ces suites
   (bootstrap par blocs), ce qui garde le comportement réel du marché sans recopier un seul passé.
4. Sur chaque trajectoire on applique exactement les règles du trade (stop, objectif, durée maximale)
   et les frais. On n'investit que si l'espérance après frais est positive et la probabilité
   de gain suffisante. Sinon le trade est refusé, avec les chiffres.
Les scénarios viennent du passé : ils mesurent un avantage passé, pas une certitude future.
"""
import numpy as np

N_SCEN = 10_000


def analog_paths(close, high, low, atr, idx, horizon):
    """Trajectoires après chaque analogue, en ATR depuis le prix d'entrée : (C, H, L) de forme (A, horizon)."""
    C, Hh, Ll = [], [], []
    n = len(close)
    for i in idx:
        if i + horizon >= n or not atr[i] or atr[i] <= 0:
            continue
        a, c0 = atr[i], close[i]
        seg = slice(i + 1, i + 1 + horizon)
        C.append((close[seg] - c0) / a)
        Hh.append((high[seg] - c0) / a)
        Ll.append((low[seg] - c0) / a)
    if not C:
        return None
    return np.array(C), np.array(Hh), np.array(Ll)


def simulate(paths, direction, tp, sl, n=N_SCEN, block=3, seed=None):
    """Applique stop/objectif sur n trajectoires recomposées. Résultats en multiples d'ATR (R)."""
    C, Hh, Ll = paths
    A, H = C.shape
    rng = np.random.default_rng(seed)
    inc = np.diff(np.concatenate([np.zeros((A, 1)), C], axis=1), axis=1)   # variations bougie par bougie
    hx, lx = Hh - C, Ll - C                                                # mèches au-dessus / au-dessous
    nb = -(-H // block)
    a = rng.integers(0, A, size=(n, nb))
    s = rng.integers(0, max(1, H - block + 1), size=(n, nb))
    k = (s[:, :, None] + np.arange(block)).clip(max=H - 1)
    aa = np.repeat(a[:, :, None], block, axis=2)
    k, aa = k.reshape(n, -1)[:, :H], aa.reshape(n, -1)[:, :H]
    path = np.cumsum(inc[aa, k], axis=1)
    hi, lo = path + hx[aa, k], path + lx[aa, k]
    if direction > 0:
        hit_tp, hit_sl = (hi >= tp) if tp else np.zeros_like(hi, bool), lo <= -sl
    else:
        hit_tp, hit_sl = (lo <= -tp) if tp else np.zeros_like(lo, bool), hi >= sl
    big = H + 1
    t_tp = np.where(hit_tp.any(1), hit_tp.argmax(1), big)
    t_sl = np.where(hit_sl.any(1), hit_sl.argmax(1), big)
    end = direction * path[:, -1]
    R = np.where(t_sl <= t_tp, np.where(t_sl < big, -sl, end), tp if tp else end)   # stop prioritaire si même bougie
    R = np.where((t_sl == big) & (t_tp == big), end, R)
    return {"n": n, "analogs": A, "p_win": float((R > 0).mean()), "ev_R": float(R.mean()),
            "p_tp": float((t_tp < t_sl).mean()), "p_sl": float(((t_sl <= t_tp) & (t_sl < big)).mean()),
            "q05_R": float(np.quantile(R, 0.05)), "q95_R": float(np.quantile(R, 0.95))}


def verdict(res, atr_pct, cost_pct, min_analogs=12, min_pwin=0.45):
    """Décision : (ok, texte). Espérance convertie en % du prix, frais déduits."""
    if res is None or res["analogs"] < min_analogs:
        k = 0 if res is None else res["analogs"]
        return False, f"10 000 scénarios impossibles : seulement {k} situations comparables dans l'historique (minimum {min_analogs})", None
    ev = res["ev_R"] * atr_pct - cost_pct
    res = dict(res, ev_pct=ev)
    txt = (f"10 000 scénarios sur {res['analogs']} situations comparables : {res['p_win']:.0%} gagnants, "
           f"espérance {ev:+.2%} après frais, pire 5 % {res['q05_R'] * atr_pct:+.2%}")
    ok = ev > 0 and res["p_win"] >= min_pwin
    return ok, ("✅ " if ok else "⛔ refusé : ") + txt, res
