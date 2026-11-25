"""Service M-TRADE 24 h/24 (lancé par GitHub Actions, environ 5 h 45 par session, sessions enchaînées).

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


def export_scalp(S):
    """Fichier léger lu par l'appli toutes les minutes."""
    os.makedirs("docs", exist_ok=True)
    out = {k: S.get(k) for k in ("start", "cash", "pos", "equity", "updated", "source", "fees", "prices", "signals", "created")}
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


def main_run():
    sh(sys.executable, "main.py", "tune", check=True)
    if not os.path.exists("data/portfolio.json"):
        sh(sys.executable, "main.py", "replay", "--days", "120", check=True)
    r = sh(sys.executable, "main.py", "run", check=True)
    print(r.stdout[-1500:])
    mark_run()


def main():
    t_end = time.time() + MINUTES * 60
    last_save = 0
    S = ss.load()
    while time.time() < t_end:
        t0 = time.time()
        try:
            S = ss.step(S)
            ss.save(S)
            export_scalp(S)
            print(datetime.now(timezone.utc).strftime("%H:%M"), "scalper", ss.summary(S))
        except Exception as e:                       # une erreur réseau ne doit jamais arrêter le service
            print("scalper :", e)
        if time.time() - last_run() >= RUN_EVERY:
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
