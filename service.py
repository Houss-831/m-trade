"""Service M-TRADE 24 h/24 (Telegram inclus) (lancé par GitHub Actions, environ 5 h 45 par session, sessions enchaînées).

- toutes les 5 minutes : scalper serveur sur les bougies 5 min qui viennent de clôturer ;
- toutes les 2 heures : passage complet du bot (actus, conseil, décisions, appli) ;
- toutes les 10 minutes : sauvegarde dans le dépôt, ce qui met à jour l'appli en ligne.
S'arrête proprement si le code du bot a changé, pour que la session suivante prenne la nouvelle version.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import scalper_server as ss

MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 340
RUN_EVERY = 2 * 3600
SAVE_EVERY = 10 * 60
STATE = "data/service.json"


def sh(*cmd, check=False):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode and check:
        print(r.stdout, r.stderr)
    return r


def last_run():
    try:
        with open(STATE) as f:
            return json.load(f).get("last_run", 0)
    except (OSError, ValueError):
        return 0


def mark_run():
    os.makedirs("data", exist_ok=True)
    with open(STATE, "w") as f:
        json.dump({"last_run": time.time(), "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, f)


def live_portfolio():
    """Valeur du portefeuille principal au prix du moment (toutes les 5 min), pour voir l'argent bouger dans l'appli.
    Actions et indices : Yahoo Finance (quelques minutes de décalage, seulement pendant les heures de bourse) ;
    crypto et or : Binance."""
    try:
        with open("data/portfolio.json") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return
    pos = st.get("positions", {})
    import config
    out = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cash": st.get("cash", 0),
           "start": st.get("start_value", 10000), "positions": []}
    prices, fx = {}, {"USD": None, "JPY": None}
    try:
        import yfinance as yf
        tick = [s for s in pos if s not in ss.SYMS] + ["EURUSD=X", "USDJPY=X"]
        df = yf.download(tick, period="1d", interval="1m", progress=False, auto_adjust=False, threads=False)
        cl = df["Close"] if "Close" in df else df
        for s in tick:
            if s in cl and cl[s].dropna().size:
                prices[s] = float(cl[s].dropna().iloc[-1])
    except Exception as e:
        print("prix en direct :", e)
    for s in pos:
        if s in ss.SYMS:
            try:
                prices[s] = float(ss._get(f"{ss.HOSTS[0]}/api/v3/ticker/price?symbol={ss.SYMS[s]}")["price"])
            except Exception:
                pass
    eurusd = prices.get("EURUSD=X")
    usdjpy = prices.get("USDJPY=X")
    hist = st.get("history") or []
    last_pos = {}
    try:
        with open("docs/data.json") as f:
            last_pos = {p_["symbol"]: p_ for p_ in json.load(f)["portfolio"]["positions"]}
    except (OSError, ValueError, KeyError):
        pass
    value = st.get("cash", 0)
    basis = st.get("cost_basis", {})
    for s, q in pos.items():
        p = prices.get(s)
        cur = config.CURRENCY.get(s, "USD")
        if p and eurusd and (cur != "JPY" or usdjpy):
            v = q * (p / eurusd if cur == "USD" else (p / (usdjpy * eurusd) if cur == "JPY" else p))
        else:
            v = float((last_pos.get(s) or {}).get("value") or basis.get(s, 0))
        value += v
        out["positions"].append({"symbol": s, "name": config.UNIVERSE.get(s, s), "price": p, "value": round(v, 2),
                                 "pnl": round(v - basis.get(s, v), 2)})
    out["value"] = round(value, 2)
    out["live"] = bool(prices)
    os.makedirs("docs", exist_ok=True)
    with open("docs/live.json", "w") as f:
        json.dump(out, f, ensure_ascii=False)


def export_scalp(S):
    """Fichier léger lu par l'appli toutes les minutes."""
    os.makedirs("docs", exist_ok=True)
    out = {k: S.get(k) for k in ("start", "cash", "pos", "equity", "updated", "source", "fees", "prices", "signals", "created", "tf")}
    out["trades"] = S["trades"][-60:]
    out["log"] = S["log"][-60:]
    out["eq"] = S["eq"][-600:]
    out["summary"] = ss.summary(S)
    with open("docs/scalp.json", "w") as f:
        json.dump(out, f, ensure_ascii=False)


def code_head():
    r = sh("git", "log", "-1", "--format=%H", "--", "*.py", "dashboard_template.html", ".github", "requirements.txt")
    return r.stdout.strip()


def push(msg):
    sh("git", "add", "data", "docs")
    if not sh("git", "diff", "--cached", "--quiet").returncode:
        return False
    sh("git", "commit", "-q", "-m", msg)
    before = code_head()
    for _ in range(4):
        sh("git", "pull", "-q", "--rebase", "-X", "theirs", "origin", "main")
        if sh("git", "push", "-q", "origin", "HEAD:main").returncode == 0:
            break
        time.sleep(5)
    return code_head() != before          # True : du nouveau code est arrivé


def scalp_tf_stale():
    try:
        with open(ss.TF_PATH) as f:
            return "brain" not in json.load(f)            # test fait avant le nouveau cerveau : on le refait
    except (OSError, ValueError):
        return True


def allocation_stale():
    try:
        with open("data/allocation.json") as f:
            return "kept" not in json.load(f)            # ancienne version : refaire la comparaison tout de suite
    except (OSError, ValueError):
        return True


def main_run():
    if ss.tf_due() or scalp_tf_stale():
        r = ss.choose_tf()
        if r:
            ss.CFG["tf"], ss.CFG["brain"], ss.CFG["active"] = r["tf"], r.get("brain", "rules"), r.get("active", True)
            print("⏱", r["summary"])
    sh(sys.executable, "main.py", "allocate", *(["--force"] if allocation_stale() else []), check=True)
    sh(sys.executable, "main.py", "tune", check=True)
    if not os.path.exists("data/portfolio.json"):
        sh(sys.executable, "main.py", "replay", "--days", "120", check=True)
    r = sh(sys.executable, "main.py", "run", check=True)
    print(r.stdout[-1500:])
    mark_run()


def apply_reset():
    """Remise à zéro demandée (data/reset_request.json) : archive l'historique et repart de 10 000 €."""
    if not os.path.exists("data/reset_request.json"):
        return
    import shutil
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    arch = os.path.join("data", "archive", stamp)
    os.makedirs(arch, exist_ok=True)
    for f in ("portfolio.json", "journal.csv", "scalp_server.json"):
        p = os.path.join("data", f)
        if os.path.exists(p):
            shutil.move(p, os.path.join(arch, f))
    now = datetime.now().isoformat(timespec="seconds")
    with open("data/portfolio.json", "w") as f:      # portefeuille neuf, sans rejeu du passé
        json.dump({"cash": 10000.0, "positions": {}, "start_value": 10000.0, "created": now, "history": [],
                   "reset_from": arch}, f, indent=2)
    os.remove("data/reset_request.json")
    with open(STATE, "w") as f:                      # passage complet du bot tout de suite
        json.dump({"last_run": 0, "at": now}, f)
    print("🔄 portefeuilles remis à 10 000 €, ancien historique archivé dans", arch)


def main():
    t_end = time.time() + MINUTES * 60
    last_save = 0
    apply_reset()
    sh(sys.executable, "main.py", "render", check=True)      # l'appli prend tout de suite le nouveau modèle
    if os.getenv("TELEGRAM_TOKEN") and not os.path.exists("data/telegram_chat.txt"):
        try:                                                    # connexion Telegram : message de bienvenue tout de suite
            from report import send_telegram
            with open("data/portfolio.json") as f:
                st = json.load(f)
            pos = len(st.get("positions", {}))
            ok = send_telegram(f"📊 Portefeuille fictif : {len(st.get('history', [])) and st['history'][-1]['value'] or st['cash']:,.0f} € · "
                               f"{pos} position(s) ouverte(s). Prochain passage du bot dans moins de 2 heures.".replace(",", " "))
            print("Telegram :", "connecté" if ok else "aucune conversation trouvée (écris « bonjour » à ton bot)")
        except Exception as e:
            print("Telegram :", e)
    S = ss.load()
    while time.time() < t_end:
        t0 = time.time()
        try:
            n_log = len(S.get("log", []))
            S = ss.step(S)
            ss.manual_closes(S)
            if os.getenv("TELEGRAM_TOKEN"):
                from report import send_telegram
                for t, txt in S["log"][n_log:]:
                    if txt[:1] in ("🟢", "🔴", "✅", "❌", "⛔", "⏱"):
                        try:
                            send_telegram("⚡ Scalper M-TRADE\n" + txt)
                        except Exception:
                            pass
            ss.save(S)
            export_scalp(S)
            live_portfolio()
            print(datetime.now(timezone.utc).strftime("%H:%M"), "scalper", ss.summary(S))
        except Exception as e:                       # une erreur réseau ne doit jamais arrêter le service
            print("scalper :", e)
        if time.time() - last_run() >= RUN_EVERY or ss.tf_due() or scalp_tf_stale() or allocation_stale():
            try:
                main_run()
            except Exception as e:
                print("bot :", e)
        if time.time() - last_save >= SAVE_EVERY:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H:%M")
            if push(f"Bot: mise à jour {stamp}"):
                print("nouveau code reçu : fin de session, la suivante prendra la nouvelle version")
                return
            last_save = time.time()
            S = ss.load()
        # prochaine bougie 5 min clôturée (+20 s de marge)
        nxt = (int(time.time() // 300) + 1) * 300 + 20
        time.sleep(max(15, min(nxt - time.time(), t_end - time.time())))
    push("Bot: fin de session " + datetime.now(timezone.utc).strftime("%Y-%m-%d_%H:%M"))


if __name__ == "__main__":
    main()
