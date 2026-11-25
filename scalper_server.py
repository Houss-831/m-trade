"""Scalper M-TRADE côté serveur : tourne 24 h/24 sur GitHub, même téléphone éteint.

Bougies réelles de 5 minutes (Binance, repli Yahoo Finance) pour Bitcoin, Ethereum, Solana et l'or (PAXG).
Argent fictif. Même logique que le scalper de l'appli : tendance courte (EMA 9/21), cassure ou rebond,
RSI, MACD, volume, tendance de fond (EMA 50), efficacité du mouvement, filtre de frais.
Chaque position a un stop et un objectif en multiples d'ATR, et une durée maximale.
Les décisions ne regardent que les bougies déjà clôturées.
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

PATH = "data/scalp_server.json"
SYMS = {"BTC-USD": "BTCUSDT", "ETH-USD": "ETHUSDT", "SOL-USD": "SOLUSDT", "GC=F": "PAXGUSDT"}
NAMES = {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana", "GC=F": "Or"}
HOSTS = ["https://data-api.binance.vision", "https://api.binance.com"]
CFG = {"tf": "5m", "risk": 0.005, "tp_atr": 2.5, "sl_atr": 1.2, "max_pos": 3, "time_stop": 24,
       "min_score": 0.7, "fee": 0.001, "fee_mult": 2.0, "min_er": 0.25, "short": True,
       "max_loss_day": 0.03, "start": 10000.0, "mc": True, "mc_min_pwin": 0.35,
       "brain": "knn", "k": 150, "history": 3000, "knn_min_pwin": 0.45, "knn_min_ev": 0.0005}


# ---------------------------------------------------------------- données
def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "m-trade-bot"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def candles(sym, limit=1000):
    """Bougies clôturées : [(t_ms, o, h, l, c, v)]. Au-delà de 1000, plusieurs pages (historique plus long)."""
    now = time.time() * 1000
    for host in HOSTS:
        try:
            k, end = [], None
            while len(k) < limit:
                n = min(1000, limit - len(k))
                url = f"{host}/api/v3/klines?symbol={SYMS[sym]}&interval={CFG['tf']}&limit={n}" + (f"&endTime={end}" if end else "")
                page = _get(url)
                if not page:
                    break
                k = page + k
                end = int(page[0][0]) - 1
                if len(page) < n:
                    break
            rows = [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in k
                    if int(x[6]) < now]                         # seulement les bougies clôturées
            if len(rows) > 80:
                return rows, "Binance"
        except Exception:
            continue
    try:                                                       # repli : Yahoo Finance
        import yfinance as yf
        ysym = "PAXG-USD" if sym == "GC=F" else sym
        df = yf.download(ysym, period="5d", interval="5m", progress=False, auto_adjust=False)
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna().iloc[:-1]
        rows = [(int(ts.timestamp() * 1000), float(r.Open), float(r.High), float(r.Low), float(r.Close), float(r.Volume))
                for ts, r in df.tail(limit).iterrows()]
        if len(rows) > 80:
            return rows, "Yahoo"
    except Exception:
        pass
    return [], None


# ---------------------------------------------------------------- indicateurs
def _ema(x, n):
    k, out, e = 2 / (n + 1), [], None
    for v in x:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def indicators(L):
    c = [x[4] for x in L]
    n = len(c)
    e9, e21, e50 = _ema(c, 9), _ema(c, 21), _ema(c, 50)
    md = [a - b for a, b in zip(_ema(c, 12), _ema(c, 26))]
    sg = _ema(md, 9)
    hist = [a - b for a, b in zip(md, sg)]
    rsi, ag, al, atr, a0, vav, er = [50.0], 0.0, 0.0, [], None, [], []
    for i in range(n):
        if i:
            d = c[i] - c[i - 1]
            ag = (ag * 6 + max(d, 0)) / 7
            al = (al * 6 + max(-d, 0)) / 7
            rsi.append(100 - 100 / (1 + ag / (al or 1e-12)))
        h, l = L[i][2], L[i][3]
        tr = max(h - l, abs(h - c[i - 1]), abs(l - c[i - 1])) if i else h - l
        a0 = tr if a0 is None else (a0 * 13 + tr) / 14
        atr.append(a0)
        vav.append(sum(x[5] for x in L[max(0, i - 20):i]) / min(i, 20) if i else 0)
        if i < 20:
            er.append(0.0)
        else:
            vo = sum(abs(c[j] - c[j - 1]) for j in range(i - 19, i + 1))
            er.append(abs(c[i] - c[i - 20]) / vo if vo else 0.0)
    return {"c": c, "e9": e9, "e21": e21, "e50": e50, "hist": hist, "rsi": rsi, "atr": atr, "vav": vav, "er": er}


def decide(L, I, n):
    """Meilleur setup à la clôture de la bougie n : dict(dir, score, why, block)."""
    if n < 60:
        return None
    cl, atr = I["c"][n], I["atr"][n]
    hi15 = max(x[2] for x in L[n - 15:n])
    lo15 = min(x[3] for x in L[n - 15:n])
    r, r1, h, h1 = I["rsi"][n], I["rsi"][n - 1], I["hist"][n], I["hist"][n - 1]
    volr = L[n][5] / (I["vav"][n] or 1)
    best = None
    for d in (1, -1):
        if d == -1 and not CFG["short"]:
            continue
        sc, why, block = 0.0, [], None
        trend = (I["e9"][n] > I["e21"][n] and I["e21"][n] > I["e21"][n - 3]) if d > 0 else \
                (I["e9"][n] < I["e21"][n] and I["e21"][n] < I["e21"][n - 3])
        if trend:
            sc += 0.3; why.append("EMA 9 > EMA 21" if d > 0 else "EMA 9 < EMA 21")
        bounce = (cl > I["e9"][n] and I["c"][n - 1] <= I["e9"][n - 1] * 1.0008) if d > 0 else \
                 (cl < I["e9"][n] and I["c"][n - 1] >= I["e9"][n - 1] * 0.9992)
        brk = cl > hi15 if d > 0 else cl < lo15
        if bounce or brk:
            sc += 0.25; why.append(("cassure du plus haut" if d > 0 else "cassure du plus bas") if brk else "rebond sur l'EMA 9")
        if (50 < r < 78 and r > r1) if d > 0 else (22 < r < 50 and r < r1):
            sc += 0.2; why.append(f"RSI {r:.0f}")
        if (h > 0 and h > h1) if d > 0 else (h < 0 and h < h1):
            sc += 0.15; why.append("MACD accélère")
        if volr > 1.2:
            sc += 0.1; why.append(f"volume ×{volr:.1f}")
        htf = (cl > I["e50"][n] and I["e50"][n] > I["e50"][n - 5]) if d > 0 else \
              (cl < I["e50"][n] and I["e50"][n] < I["e50"][n - 5])
        if htf:
            sc += 0.1; why.append("tendance de fond alignée")
        tp_pct, cost = CFG["tp_atr"] * atr / cl, 2 * CFG["fee"] + 0.0003
        if tp_pct < CFG["fee_mult"] * cost:
            block = f"objectif {tp_pct:.2%} trop petit face aux frais ({cost:.2%})"
        elif I["er"][n] < CFG["min_er"]:
            block = f"marché sans direction (efficacité {I['er'][n]:.2f})"
        elif not htf:
            block = "tendance de fond contraire (EMA 50)"
        o = {"dir": d, "score": round(sc, 2), "why": why, "block": block, "atr": atr}
        if best is None or o["score"] > best["score"] or (o["score"] == best["score"] and not o["block"]):
            best = o
    return best


# ---------------------------------------------------------------- état
def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"start": CFG["start"], "cash": CFG["start"], "pos": {}, "trades": [], "eq": [], "log": [],
                "last": {}, "fees": 0.0, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "day": {}, "source": None}


def save(S):
    S["trades"] = S["trades"][-400:]
    S["log"] = S["log"][-200:]
    S["eq"] = S["eq"][-2000:]
    os.makedirs("data", exist_ok=True)
    with open(PATH, "w") as f:
        json.dump(S, f, ensure_ascii=False)


def _iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="seconds")


def _log(S, ms, txt):
    S["log"].append([_iso(ms), txt])


def equity(S, px):
    v = S["cash"]
    for s, p in S["pos"].items():
        v += p["notional"] + p["dir"] * p["qty"] * (px.get(s, p["entry"]) - p["entry"])
    return v


def _close(S, sym, price, ms, why):
    p = S["pos"].pop(sym)
    gross = p["dir"] * p["qty"] * (price - p["entry"])
    fee = abs(p["qty"] * price) * CFG["fee"]
    S["cash"] += p["notional"] + gross - fee
    S["fees"] += fee
    pnl = gross - fee - p["fee_in"]
    S["trades"].append({"t": _iso(ms), "sym": sym, "name": NAMES[sym], "kind": "close", "dir": p["dir"],
                        "entry": p["entry"], "exit": price, "pnl": round(pnl, 2), "why": why, "bars": p["bars"]})
    _log(S, ms, f"{'✅' if pnl > 0 else '❌'} {NAMES[sym]} : {'achat' if p['dir'] > 0 else 'vente à découvert'} fermé ({why}), "
               f"{'+' if pnl > 0 else ''}{pnl:.2f} €")


def _open(S, sym, st, price, ms, px):
    E = equity(S, px)
    stop_d = CFG["sl_atr"] * st["atr"]
    qty = E * CFG["risk"] / stop_d
    notional = min(qty * price, E * 0.33, max(S["cash"], 0) * 0.98)
    if notional < 50:
        return
    qty = notional / price
    fee = notional * CFG["fee"]
    S["cash"] -= notional + fee
    S["fees"] += fee
    d = st["dir"]
    S["pos"][sym] = {"dir": d, "qty": qty, "entry": price, "notional": notional, "fee_in": fee, "bars": 0,
                     "sl": price - d * stop_d, "tp": price + d * CFG["tp_atr"] * st["atr"], "t": _iso(ms),
                     "why": st["why"], "score": st["score"]}
    S["trades"].append({"t": _iso(ms), "sym": sym, "name": NAMES[sym], "kind": "open", "dir": d, "entry": price,
                        "score": st["score"], "why": ", ".join(st["why"])})
    _log(S, ms, f"{'🟢 achat' if d > 0 else '🔴 vente à découvert'} {NAMES[sym]} à {price:,.2f} $ (score {st['score']:.2f} : "
               f"{', '.join(st['why'])}) · stop {S['pos'][sym]['sl']:,.2f} · objectif {S['pos'][sym]['tp']:,.2f}"
               + (f" · {st['mc']}" if st.get("mc") else ""))


# ---------------------------------------------------------------- cerveau « mémoire des situations » (k plus proches voisins)
FEATS = ["écart à l'EMA 21", "pente courte", "écart à l'EMA 50", "RSI", "MACD", "efficacité", "volatilité relative",
         "élan 6 bougies", "volume"]


def features(L, I):
    """Empreinte de chaque bougie : 9 mesures sans unité (en ATR ou en ratio), comparables d'un actif à l'autre."""
    import numpy as np
    c = np.array(I["c"]); atr = np.array(I["atr"]) + 1e-12
    vol = np.array([x[5] for x in L]); vav = np.array(I["vav"]) + 1e-12
    ap = atr / c
    med = np.array([np.median(ap[max(0, i - 200):i + 1]) for i in range(len(c))]) + 1e-12
    mom = np.r_[np.zeros(6), (c[6:] - c[:-6])] / atr
    F = np.c_[(c - np.array(I["e21"])) / atr, (np.array(I["e9"]) - np.array(I["e21"])) / atr,
              (c - np.array(I["e50"])) / atr, np.array(I["rsi"]) / 100, np.array(I["hist"]) / atr,
              np.array(I["er"]), ap / med, mom, np.log((vol + 1) / vav)]
    F[:60] = np.nan
    return F


def build_library(data, inds):
    """Pour chaque bougie passée de chaque actif : empreinte, ce qui s'est passé ensuite (en ATR), et l'heure de fin."""
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view as sw
    H = CFG["time_stop"]
    lib = {"F": [], "C": [], "Hh": [], "Ll": [], "end": [], "sym": []}
    for sym, L in data.items():
        I = inds[sym]
        N = len(L)
        if N < 80 + H:
            continue
        c = np.array([x[4] for x in L]); h = np.array([x[2] for x in L]); l = np.array([x[3] for x in L])
        t = np.array([x[0] for x in L]); atr = np.array(I["atr"]) + 1e-12
        F = features(L, I)
        idx = np.arange(60, N - H)
        win = lambda a: sw(a[1:], H)[idx - 0]       # fenêtre des H bougies qui suivent i
        lib["F"].append(F[idx]); lib["end"].append(t[idx + H]); lib["sym"] += [sym] * len(idx)
        lib["C"].append((win(c) - c[idx, None]) / atr[idx, None])
        lib["Hh"].append((win(h) - c[idx, None]) / atr[idx, None])
        lib["Ll"].append((win(l) - c[idx, None]) / atr[idx, None])
    if not lib["F"]:
        return None
    out = {k: np.concatenate(v) if k != "sym" else np.array(v) for k, v in lib.items()}
    ok = ~np.isnan(out["F"]).any(1)
    out = {k: v[ok] for k, v in out.items()}
    out["mu"], out["sd"] = out["F"].mean(0), out["F"].std(0) + 1e-9
    out["Z"] = (out["F"] - out["mu"]) / out["sd"]
    # résultat réel de chaque situation passée, à la hausse et à la baisse (stop, objectif, durée)
    tp, sl = CFG["tp_atr"], CFG["sl_atr"]
    for d, key in ((1, "R_long"), (-1, "R_short")):
        hi, lo, C = out["Hh"], out["Ll"], out["C"]
        hit_tp = (hi >= tp) if d > 0 else (lo <= -tp)
        hit_sl = (lo <= -sl) if d > 0 else (hi >= sl)
        big = C.shape[1] + 1
        t_tp = np.where(hit_tp.any(1), hit_tp.argmax(1), big)
        t_sl = np.where(hit_sl.any(1), hit_sl.argmax(1), big)
        out[key] = np.where(t_sl <= t_tp, np.where(t_sl < big, -sl, d * C[:, -1]), tp)
    return out


def knn_decide(lib, f, t_now, atr_pct):
    """Retrouve les K situations passées les plus ressemblantes (déjà terminées), puis 10 000 scénarios sur leurs suites."""
    import numpy as np
    import montecarlo as mc
    if lib is None or np.isnan(f).any():
        return None
    ok = lib["end"] < t_now
    if ok.sum() < 300:
        return None
    z = (f - lib["mu"]) / lib["sd"]
    dist = np.sqrt(((lib["Z"][ok] - z) ** 2).sum(1))
    k = min(CFG["k"], len(dist))
    nn = np.argpartition(dist, k - 1)[:k]
    sel = np.flatnonzero(ok)[nn]
    cost = 2 * CFG["fee"] + 0.0003
    best = None
    for d, key in ((1, "R_long"), (-1, "R_short")):
        if d < 0 and not CFG["short"]:
            continue
        R = lib[key][sel]
        quick = {"dir": d, "p_win": float((R > 0).mean()), "ev_pct": float(R.mean() * atr_pct - cost)}
        if best is None or quick["ev_pct"] > best["ev_pct"]:
            best = quick
    best["k"] = k
    best["sim"] = float(np.median(dist[nn]))
    if best["ev_pct"] > CFG["knn_min_ev"] and best["p_win"] >= CFG["knn_min_pwin"] - 0.05:
        res = mc.simulate((lib["C"][sel], lib["Hh"][sel], lib["Ll"][sel]), best["dir"], CFG["tp_atr"], CFG["sl_atr"],
                          seed=int(t_now // 1000) % 2**31)
        okv, txt, res = mc.verdict(res, atr_pct, cost, min_analogs=50, min_pwin=CFG["knn_min_pwin"])
        best.update({"ok": okv and res["ev_pct"] > CFG["knn_min_ev"], "txt": txt, "mc": res})
    else:
        best.update({"ok": False, "txt": f"⛔ refusé : les {k} situations passées les plus ressemblantes donnent "
                                         f"{best['p_win']:.0%} de gagnants et {best['ev_pct']:+.2%} d'espérance après frais"})
    return best


def scan_setups(L, I):
    """Toutes les bougies passées où un signal valide est apparu : {1: [n...], -1: [n...]}."""
    out = {1: [], -1: []}
    for n in range(60, len(L)):
        st = decide(L, I, n)
        if st and st["score"] >= CFG["min_score"] and not st["block"]:
            out[st["dir"]].append(n)
    return out


def mc_check(sym, n, st, data, inds, setups):
    """10 000 scénarios avant d'ouvrir : analogues de tous les actifs (en ATR), sans regarder le futur."""
    import numpy as np
    import montecarlo as mc
    H = CFG["time_stop"]
    t_now = data[sym][n][0]
    pools = []
    for s2, L2 in data.items():
        I2 = inds[s2]
        idx = [i for i in setups[s2][st["dir"]] if i + H < len(L2) and L2[i + H][0] < t_now]
        arr = lambda k: np.array([x[k] for x in L2])
        p = mc.analog_paths(arr(4), arr(2), arr(3), np.array(I2["atr"]), idx, H)
        if p is not None:
            pools.append(p)
    if not pools:
        return mc.verdict(None, 0, 0)
    paths = tuple(np.concatenate([p[k] for p in pools]) for k in range(3))
    res = mc.simulate(paths, st["dir"], CFG["tp_atr"], CFG["sl_atr"], seed=int(t_now // 1000) % 2**31)
    atr_pct = st["atr"] / data[sym][n][4]
    return mc.verdict(res, atr_pct, 2 * CFG["fee"] + 0.0003, min_analogs=20, min_pwin=CFG["mc_min_pwin"])


def step(S=None, data=None):
    """Traite toutes les bougies clôturées depuis le dernier passage (rattrapage inclus)."""
    S = S or load()
    if S.get("tf") and S["tf"] != CFG["tf"]:                      # changement d'unité de temps : on repart proprement
        for s2 in list(S["pos"]):
            _close(S, s2, (S.get("prices") or {}).get(s2, S["pos"][s2]["entry"]), time.time() * 1000, "changement d'unité de temps")
        S["last"] = {}
        _log(S, time.time() * 1000, f"⏱ le scalper passe en bougies {CFG['tf']} (meilleure unité de temps sur les vraies bougies)")
    S["tf"] = CFG["tf"]
    if data is None:
        data = {}
        for sym in SYMS:
            L, src = candles(sym, CFG.get("history", 1000))
            if L:
                data[sym] = L
                S["source"] = src
    if not data:
        _log(S, time.time() * 1000, "⚠️ données indisponibles, nouvel essai au prochain passage")
        return S
    # chronologie commune de toutes les bougies non encore traitées
    events = []
    inds = {sym: indicators(L) for sym, L in data.items()}
    knn = CFG.get("brain") == "knn"
    setups = {} if knn else {sym: scan_setups(L, inds[sym]) for sym, L in data.items()}
    lib = build_library(data, inds) if knn else None
    feats = {sym: features(L, inds[sym]) for sym, L in data.items()} if knn else {}
    if not S["last"] and not S["trades"]:
        _log(S, time.time() * 1000, "▶ scalper serveur démarré : il tourne 24 h/24 sur GitHub (bougies 5 min, argent fictif). "
                                    "Premier passage : les 6 dernières heures sont jouées pour amorcer.")
    for sym, L in data.items():
        I = inds[sym]
        last = S["last"].get(sym) or L[max(60, len(L) - 73)][0]
        for n in range(60, len(L)):
            if L[n][0] > last:
                events.append((L[n][0], sym, n, L, I))
    events.sort(key=lambda e: e[0])
    px = {s: L[-1][4] for s, L in data.items()}
    cur = {}
    for ms, sym, n, L, I in events:
        bar = L[n]
        cur[sym] = bar[4]
        day = _iso(ms)[:10]
        if S["day"].get("date") != day:
            S["day"] = {"date": day, "start": equity(S, {**px, **cur}), "halted": False}
        p = S["pos"].get(sym)
        if p:                                                  # gestion de la position
            p["bars"] += 1
            hit_sl = bar[3] <= p["sl"] if p["dir"] > 0 else bar[2] >= p["sl"]
            hit_tp = bar[2] >= p["tp"] if p["dir"] > 0 else bar[3] <= p["tp"]
            if hit_sl:
                _close(S, sym, p["sl"], ms, "stop touché")
            elif hit_tp:
                _close(S, sym, p["tp"], ms, "objectif atteint")
            elif p["bars"] >= CFG["time_stop"]:
                _close(S, sym, bar[4], ms, f"durée maximale ({CFG['time_stop']} bougies)")
            elif p["bars"] >= 6 and (bar[4] - p["entry"]) * p["dir"] > CFG["sl_atr"] * I["atr"][n]:
                p["sl"] = max(p["sl"], p["entry"]) if p["dir"] > 0 else min(p["sl"], p["entry"])   # stop au prix d'entrée
        elif not CFG.get("active", True):
            pass                                                   # mode observation : aucune nouvelle position
        elif knn and not S["day"].get("halted") and len(S["pos"]) < CFG["max_pos"]:
            kd = knn_decide(lib, feats[sym][n], ms, I["atr"][n] / bar[4])
            S.setdefault("mc_stats", {"ok": 0, "no": 0})
            if kd and kd["ok"]:
                S["mc_stats"]["ok"] += 1
                st = {"dir": kd["dir"], "score": round(kd["p_win"], 2), "atr": I["atr"][n], "mc": kd["txt"],
                      "why": [f"{kd['k']} situations passées ressemblantes", f"{kd['p_win']:.0%} gagnantes"]}
                _open(S, sym, st, bar[4], ms, {**px, **cur})
            elif kd:
                S["mc_stats"]["no"] += 1
                if kd["ev_pct"] > -0.001 and ms - S.setdefault("mc_log", {}).get(sym, 0) >= 4 * 3600000:
                    S["mc_log"][sym] = ms
                    _log(S, ms, f"🧪 {NAMES[sym]} : {kd['txt']}")
        elif not S["day"].get("halted") and len(S["pos"]) < CFG["max_pos"]:
            st = decide(L, I, n)
            if st and st["score"] >= CFG["min_score"] and not st["block"]:
                ok, txt, res = mc_check(sym, n, st, data, inds, setups) if CFG["mc"] else (True, "", None)
                S.setdefault("mc_stats", {"ok": 0, "no": 0})["ok" if ok else "no"] += 1
                if ok:
                    st["mc"] = txt
                    _open(S, sym, st, bar[4], ms, {**px, **cur})
                elif ms - S.setdefault("mc_log", {}).get(sym, 0) >= 30 * 60000:
                    S["mc_log"][sym] = ms
                    _log(S, ms, f"🧪 {NAMES[sym]} : signal {'hausse' if st['dir'] > 0 else 'baisse'} {st['score']:.2f} · {txt}")
        S["last"][sym] = ms
        v = equity(S, {**px, **cur})
        if not S["day"].get("halted") and v - S["day"]["start"] <= -CFG["max_loss_day"] * S["start"]:
            for s2 in list(S["pos"]):
                _close(S, s2, cur.get(s2, px[s2]), ms, "limite de perte du jour")
            S["day"]["halted"] = True
            _log(S, ms, f"⛔ limite de perte du jour atteinte ({CFG['max_loss_day']:.0%}) : pause jusqu'à demain")
        if not S["eq"] or ms - S["eq"][-1][0] >= 15 * 60000:
            S["eq"].append([ms, round(v, 2)])
    S["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    S["equity"] = round(equity(S, px), 2)
    S["prices"] = px
    S["signals"] = {}
    for sym, L in data.items():                                # état du signal courant, pour l'appli
        st = decide(L, inds[sym], len(L) - 1)
        if st:
            S["signals"][sym] = {"dir": st["dir"], "score": st["score"], "why": st["why"], "block": st["block"]}
    return S


def summary(S):
    """Résumé du porte-monnaie."""
    cl = [t for t in S["trades"] if t["kind"] == "close"]
    wins = [t for t in cl if t["pnl"] > 0]
    return {"equity": S.get("equity", S["cash"]), "start": S["start"], "trades": len(cl),
            "win_rate": round(len(wins) / len(cl), 3) if cl else None,
            "pnl": round(S.get("equity", S["cash"]) - S["start"], 2), "fees": round(S["fees"], 2),
            "open": len(S["pos"]), "updated": S.get("updated"), "source": S.get("source"),
            "mc_ok": S.get("mc_stats", {}).get("ok", 0), "mc_no": S.get("mc_stats", {}).get("no", 0)}


if __name__ == "__main__":
    S = step()
    save(S)
    print("⚡ scalper serveur :", summary(S))


# ---------------------------------------------------------------- choix de l'unité de temps
TF_PATH = "data/scalp_tf.json"
TF_TXT = {"5m": "5 minutes", "1h": "1 heure", "4h": "4 heures"}


def evaluate_tf(tf, warmup=400, brain="rules"):
    """Rejoue le scalper (avec ses 10 000 scénarios) sur les dernières bougies réelles de cette durée."""
    old, old_b = CFG["tf"], CFG.get("brain")
    CFG["tf"], CFG["brain"] = tf, brain
    try:
        data = {}
        for sym in SYMS:
            L, _ = candles(sym, CFG.get("history", 1000))
            if len(L) > warmup + 50:
                data[sym] = L
        if not data:
            return None
        S = {"start": CFG["start"], "cash": CFG["start"], "pos": {}, "trades": [], "eq": [], "log": [], "fees": 0.0,
             "last": {s2: L[warmup][0] for s2, L in data.items()}, "day": {}, "tf": tf}
        S = step(S, data)
        sm = summary(S)
        span = (max(L[-1][0] for L in data.values()) - max(L[warmup][0] for L in data.values())) / 86400000
        pn = [t["pnl"] for t in S["trades"] if t["kind"] == "close"]
        import statistics as _st
        tstat = (_st.mean(pn) / _st.stdev(pn) * len(pn) ** 0.5) if len(pn) >= 5 and _st.stdev(pn) > 0 else 0.0
        return {"tf": tf, "brain": brain, "days": round(span, 1), "tstat": round(tstat, 2),
                **{k: sm[k] for k in ("pnl", "trades", "win_rate", "fees", "mc_ok", "mc_no")}}
    finally:
        CFG["tf"], CFG["brain"] = old, old_b


def choose_tf():
    res = [r for r in (evaluate_tf(tf, brain=b) for tf in ("5m", "1h", "4h") for b in ("rules", "knn")) if r]
    if not res:
        return None
    best = max(res, key=lambda r: (r["tstat"] if r["trades"] >= 8 else -9))   # la plus fiable, avec assez de trades
    active = best["pnl"] > 0 and best["tstat"] > 0.5
    BR = {"rules": "règles fixes", "knn": "mémoire des situations"}
    out = {"date": datetime.now(timezone.utc).date().isoformat(), "tf": best["tf"], "brain": best["brain"], "results": res,
           "active": active,
           "summary": f"Retenu : bougies de {TF_TXT[best['tf']]}, cerveau « {BR[best['brain']]} ». Rejeu sur vraies bougies, "
                      "10 000 scénarios avant chaque trade : "
                      + " ; ".join(f"{TF_TXT[r['tf']]}/{BR[r['brain']]} {r['pnl']:+.0f} € en {r['days']:.0f} j ({r['trades']} trades, "
                                   f"{(r['win_rate'] or 0):.0%} gagnants, fiabilité {r['tstat']:+.1f})" for r in res) + "."
                      + ("" if active else " Aucune combinaison n'est gagnante de façon fiable : le scalper reste en observation "
                                           "(il analyse mais n'ouvre pas de trade) jusqu'au prochain test.")}
    os.makedirs("data", exist_ok=True)
    with open(TF_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    return out


def tf_due(days=7):
    try:
        with open(TF_PATH) as f:
            d = json.load(f)
        return (datetime.now(timezone.utc).date() - datetime.fromisoformat(d["date"]).date()).days >= days
    except (OSError, ValueError, KeyError):
        return True


try:                                                            # unité de temps choisie sur les vraies bougies
    with open(TF_PATH) as _f:
        _d = json.load(_f)
        CFG["tf"] = _d.get("tf", CFG["tf"])
        CFG["brain"] = _d.get("brain", "rules")
        CFG["active"] = _d.get("active", True)
except (OSError, ValueError):
    pass


# ---------------------------------------------------------------- clôtures manuelles (demandées depuis l'appli)
def manual_closes(S):
    """Lit les demandes « FERMER <actif> » ouvertes sur le dépôt GitHub. Seules celles du propriétaire du dépôt
    sont prises en compte (dépôt public : n'importe qui pourrait en créer). Ferme le trade, puis la demande."""
    tok, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    owner = (os.getenv("GITHUB_REPOSITORY_OWNER") or "").lower()
    if not tok or not repo:
        return 0
    hdr = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json", "User-Agent": "m-trade-bot"}
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues?state=open&per_page=50", headers=hdr)
        with urllib.request.urlopen(req, timeout=15) as r:
            issues = json.loads(r.read().decode())
    except Exception:
        return 0
    done = 0
    for it in issues:
        title = (it.get("title") or "").strip()
        if not title.upper().startswith("FERMER") or "pull_request" in it:
            continue
        if (it.get("user") or {}).get("login", "").lower() != owner:
            continue
        sym = title.split(None, 1)[1].strip() if len(title.split(None, 1)) > 1 else ""
        msg = "Aucun trade ouvert sur cet actif : rien à fermer."
        if sym in S["pos"]:
            price = (S.get("prices") or {}).get(sym, S["pos"][sym]["entry"])
            _close(S, sym, price, time.time() * 1000, "clôture manuelle demandée depuis l'appli")
            msg = f"✅ Trade {NAMES.get(sym, sym)} fermé au prix de {price:,.2f} $. " + S["log"][-1][1]
            done += 1
        try:
            body = json.dumps({"body": msg}).encode()
            urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/{repo}/issues/{it['number']}/comments",
                                                          data=body, headers=hdr, method="POST"), timeout=15)
            urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/{repo}/issues/{it['number']}",
                                                          data=json.dumps({"state": "closed"}).encode(), headers=hdr, method="PATCH"), timeout=15)
        except Exception:
            pass
    if done:
        S["equity"] = round(equity(S, S.get("prices") or {}), 2)
    return done
