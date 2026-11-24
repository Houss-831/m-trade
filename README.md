# ⚡ M-TRADE by Mahjoub Agency

Bot de trading autonome en argent fictif, sur les vrais cours du marché.

Le bot surveille en continu actions, crypto, or et pétrole avec les **vrais cours du marché**
(Yahoo Finance) et **l'actu mondiale** (Reuters, CNBC, MarketWatch, CoinDesk, Les Echos, Boursorama).
Il **achète et vend tout seul** avec un portefeuille **fictif** de 10 000 €, et t'envoie un message
Telegram **à chaque ordre** : ce qu'il a fait, pourquoi, comment il a dimensionné, et l'actu liée.
Il t'envoie aussi un bilan chaque soir à 21h.

## 🚀 Premier lancement sur les vrais cours (sans ordinateur)
Une fois le dépôt créé et les secrets ajoutés (voir « Installation » plus bas) :
1. Va dans l'onglet **Actions**, puis **M-TRADE - bot autonome**, puis **Run workflow**.
2. Remplis les deux cases :
   - **rejouer** : `120`. Le bot rejoue 120 jours sur les vrais cours, pour démarrer avec un historique.
   - **backtest** : `oui`, pour mesurer la stratégie sur 5 ans de vrais cours.
3. Lance. Au bout de quelques minutes, le résumé du job affiche le backtest. L'interface
   (`docs/`) contient alors les vraies données, et le laboratoire rend son premier verdict.
4. Les lancements suivants se font tout seuls, toutes les 2 heures.

## 👤 Tes réglages (onglet « Réglages » de l'appli)
Tu programmes le bot selon ta situation :
- **Ton argent** : capital de départ, montant maximum investi, **perte maximale par jour** et
  perte totale maximale, en euros.
- **Ton profil de risque** : Prudent, Équilibré, Offensif, ou Sur mesure avec 6 curseurs.
- **Tes marchés** (Actions, Crypto, Matières) et les actifs autorisés un par un.
- **Les stratégies du conseil** à garder, le **poids de l'IA** et les **notifications**.

L'appli calcule en direct l'impact de tes choix, par exemple la pire journée probable, puis
**« Appliquer au bot »** te donne le fichier `data/settings.json` à coller sur GitHub.

**Comment la perte maximale par jour est respectée :**
1. Avant d'acheter, le bot estime la pire journée probable de son portefeuille (VaR 95 %).
   Si elle dépasse ton budget restant pour la journée, il réduit toutes ses positions en proportion.
2. Si la perte du jour atteint ta limite, il vend tout et ne reprend que le lendemain. Une alerte
   Telegram 🛑 te prévient.
3. Si la perte totale atteint ta limite, il s'arrête jusqu'à ce que tu modifies ce réglage.

*Limite honnête :* le bot vérifie ses limites à chaque passage, toutes les 2 heures. Un krach brutal
entre deux passages peut faire dépasser un peu la limite.

**Profil et code d'accès :** dans l'aperçu Claude, ton identité vient de ton compte Claude, et tes
réglages y sont synchronisés. Le code d'accès verrouille l'écran sur ton appareil. C'est une
protection contre les regards indiscrets, pas une sécurité de serveur. Une page GitHub Pages
publique reste visible par quiconque a son adresse.

## 📈 Salle de marché « Live »
- **Graphique en bougies animé** : moyennes EMA 20/50, Bollinger, volumes, et en dessous RSI 14 et MACD.
  Tu peux zoomer (molette ou loupes), remonter le temps en glissant, et un réticule affiche les cours
  ouverture, plus haut, plus bas et clôture.
- **Unités de temps** : 1 min, 5 min, 15 min, 1 h, 4 h et 1 jour.
- **Signaux calculés en direct sur les bougies** : croisements des EMA, sorties des zones RSI (▲ / ▼),
  avec une notification à l'écran. Une jauge animée donne le signal du moment, à côté de l'avis
  officiel du bot.
- **Vrai direct** (sur GitHub Pages) : Bitcoin, Ethereum, Solana et l'or (via le jeton PAXG), grâce aux
  données publiques de Binance. Les indices et le pétrole n'ont pas de flux en direct gratuit : ils
  sont affichés en bougies journalières, mises à jour à chaque passage du bot.
- **Dans l'aperçu Claude** (sans Internet), une simulation accélérée part des vrais derniers cours.
  Elle est clairement signalée à l'écran.
- **Ordres manuels** sur un portefeuille fictif à toi (capital pris dans tes Réglages), avec une
  confirmation en deux temps, 0,1 % de frais, et un **stop** et un **objectif** automatiques en %.
  Ces derniers ne sont surveillés que lorsque l'onglet Live est ouvert. Tes ordres s'affichent sur le
  graphique (A / V), et la carte **« Toi contre M-TRADE »** compare tes résultats à ceux du bot.
  C'est de l'argent fictif : aucun ordre n'est envoyé à un courtier.

## ⚡ Scalper automatique (onglet « Scalping »)
En plus du bot long terme (GitHub, toutes les 2 heures), l'appli contient un **scalper** qui trade
lui-même sur des bougies d'une minute : Bitcoin, Ethereum, Solana et l'or (PAXG).
- **Entrée** : tendance EMA 9/21, puis rebond sur l'EMA 9 ou cassure du plus haut ou du plus bas sur
  15 minutes, confirmés par le RSI 7, le MACD et le volume. Le scalper n'entre qu'à partir d'un score
  de 0,70. Il prend des positions à l'achat et à la vente à découvert (désactivable).
- **Taille** : un risque de 0,5 % du porte-monnaie par opération (réglable), au plus 25 % par position
  et 3 positions en même temps.
- **Sortie** : objectif à 1,6 ATR, stop à 1 ATR, stop remonté au prix d'entrée après +1 ATR puis stop
  suiveur. Le scalper sort aussi si la tendance s'inverse ou après 30 bougies.
- **Sécurité** : il s'arrête de lui-même si la séance perd 3 % (réglable).
- **Tout se voit en direct** : le porte-monnaie qui compte à chaque variation, la courbe de valeur, les
  statistiques (taux de réussite, facteur de profit, frais payés, pire baisse), chaque position sur un
  rail stop → entrée → objectif, 4 mini-graphiques avec les entrées et les sorties, un fil des
  opérations et la force du setup pour chaque actif. Une pastille dans l'en-tête affiche le résultat
  du scalper depuis n'importe quel onglet.

### 🧠 Scalper intelligent (v13)
Diagnostic de la version précédente : sur des bougies d'une minute, l'objectif (1,6 × le mouvement
moyen d'une bougie, soit environ 0,13 %) était **plus petit que les frais** d'un aller-retour (0,2 %).
Même une opération gagnante perdait de l'argent. Sur 3 000 bougies simulées, cette version perdait 37 %,
dont 5 500 € de frais.

Ce qui a changé :
- **Bougies de 5 minutes** par défaut (1 min et 15 min restent disponibles), objectif à 2,5 ATR et
  stop à 1,2 ATR.
- **Filtre de frais** : une opération est refusée si son objectif ne couvre pas au moins 3 fois les frais.
- **Filtre de direction** : une opération est refusée si l'efficacité de tendance (Kaufman) est sous 0,30.
- **Tendance de fond** : l'EMA 50 doit aller dans le même sens que l'opération.
- **Apprentissage** : après des pertes d'affilée, le scalper devient plus exigeant. Il met aussi en pause
  un actif ou un sens qui perd sur ses dernières opérations.
- **Auto-validation** : pour chaque actif, 12 réglages sont testés sur 70 % des 3 000 dernières bougies,
  puis le meilleur est vérifié sur les 30 % restants, jamais vus. L'actif n'est tradé que si le réglage
  reste rentable, frais compris. La validation est refaite toutes les heures.
- **Labo du scalper** : il compare l'ancienne et la nouvelle version sur le même historique.

Résultat sur données simulées, qui sont du hasard pur : la perte passe de −37 % à −1 % avec les filtres.
Avec l'auto-validation, le scalper reconnaît qu'il n'y a pas d'avantage à exploiter et ne trade pas
(0 € de perte). Sur les vrais cours, il ne tradera que les actifs où un avantage résiste au test sur des
données jamais vues.

**Limites honnêtes :**
- Le scalper ne tourne que **tant que l'appli est ouverte**. Pour un fonctionnement 24 h/24, il faudrait
  un petit serveur.
- Sur GitHub Pages, il trade les vrais cours Binance. Dans l'aperçu Claude, le marché est simulé en
  accéléré (une bougie d'une minute toutes les 15 secondes).
- En scalping, les frais (0,1 % par sens) pèsent très lourd : beaucoup de stratégies de scalping
  perdent une fois les frais déduits. Les statistiques sont là pour le vérifier.

## 🎨 Apparence (Réglages > Apparence)
- **5 thèmes** : Néon, Océan, Aurore, Solaire et Minuit.
- **5 fonds** : constellation animée, étoiles scintillantes, aurores, grille holographique ou uni.
- **Effet verre** sur la barre du bas et l'en-tête, avec un réglage du flou et de la transparence.
- Taille du texte, et animations désactivables pour économiser la batterie.

## 🟣 Simulation ou 🟢 direct ?
L'indicateur en haut de l'écran le dit en permanence. Dans l'aperçu Claude, l'appli n'a pas accès à
Internet : tout ce qui bouge y est **simulé**. Sur GitHub Pages, les cryptos et l'or sont **en direct**.
Les porte-monnaie du scalper sont **séparés** (simulation d'un côté, direct de l'autre), pour que les
résultats simulés ne se mélangent jamais aux vrais.

## 🎓 Une IA qui apprend de ses erreurs
- **Mémoire des prédictions** (`data/ai_memory.json`) : chaque avis de l'IA sur chaque actif est
  enregistré avec le prix du moment, puis **noté 5 séances plus tard** (bonne ou mauvaise direction).
- **Bulletin** : taux de bons appels, corrélation entre prévision et réalité, fiabilité par actif et plus
  grosses erreurs. Ce bulletin est **renvoyé à l'IA dans chaque analyse** : elle sait où elle se trompe
  et en tire une « leçon du jour ».
- **Influence méritée** : après 30 appels notés, le poids de l'IA dans les décisions monte si elle voit
  juste (jusqu'à 1,6 fois sa base) et baisse jusqu'à 5 % si elle se trompe, ou si sa corrélation est
  négative.
- **Base de connaissances** : régimes de marché, intermarché, positionnement, liquidité, calendrier des
  banques centrales, crypto, or, et distinction entre le bruit et le signal.
- **Risque d'événement** : si l'IA détecte un événement majeur dans les 48 heures (Fed, BCE, inflation,
  emploi, élection, conflit) avec un niveau d'au moins 0,6, le bot réduit ses positions jusqu'à 40 %.
- **Régimes de marché** : chaque jour est classé haussier, baissier, indécis ou en crise. Le conseil
  retient quelles méthodes réussissent dans chaque régime. Cette **mémoire des régimes** n'est gardée
  que si le labo prouve qu'elle améliore le Sharpe sur l'historique.

## 🧠 Cockpit IA
Choisis un actif et touche **« Rejouer la réflexion »**. Le bot déroule alors ses 11 étapes, des cours
lus jusqu'à l'ordre passé, en surlignant à chaque étape la fonction exacte de son code source,
consultable dans l'appli. L'assistant « Demande à M-TRADE » affiche aussi son raisonnement avant
sa réponse.

## 🏛️ Le conseil des stratégies
M-TRADE ne mise pas sur une seule méthode. Sept grandes méthodes de l'histoire du trading
votent chaque jour pour chaque actif :

| Stratégie | Origine | Famille |
|---|---|---|
| Tendance de fond (50/200 jours) | Charles Dow, vers 1900 | Suivi de tendance |
| Momentum temporel 12 mois | Moskowitz, Ooi et Pedersen, 2012 | Momentum |
| Momentum relatif 6 mois | Jegadeesh et Titman, 1993 | Momentum |
| Cassure de canal 55 jours | Donchian (années 1960), les Turtles (1983) | Suivi de tendance |
| MACD 12/26/9 | Gerald Appel, fin des années 1970 | Momentum |
| Retour à la moyenne (Bollinger + filtre ADX) | John Bollinger, années 1980 | Retour à la moyenne |
| RSI 2 jours dans la tendance | Wilder (1978), Connors (années 2000) | Retour à la moyenne |

**Pondération adaptative :** chaque méthode est notée sur son ratio de Sharpe des 60 derniers jours
(son rendement rapporté à son risque), sans jamais regarder le futur. Les méthodes qui marchent en ce
moment gagnent du poids, celles qui échouent en perdent. Chacune garde tout de même au moins 4 % des voix.

## 🛡️ Le bouclier (gestion du risque)
- **Stop suiveur** : le bot sort d'une position si le prix tombe sous son plus haut moins
  3 ATR (l'amplitude moyenne d'une journée). C'est le « chandelier exit » de Chuck LeBeau,
  inspiré des stops des Turtles.
- **Pause** de 5 jours après un stop, sans rachat du même actif.
- **Disjoncteur** : si le portefeuille est à −12 % de son sommet, l'exposition est divisée par 2.
  À −20 %, elle est divisée par 4.
- **Taille des positions** selon la volatilité (15 % par an visés), avec un plafond de 20 % par actif.

- **Ajustement aux corrélations** (Markowitz, 1952) : quand plusieurs positions forment
  un même pari (par exemple Bitcoin, Ethereum et Solana), leur taille est réduite. Elles pèsent
  alors comme un pari et demi, au lieu de trois.

Tout se règle dans `config.py` (`RISK` et `STRATEGY`).

## 🎯 Entrées, sorties et prises de profit
- **Hystérésis** : le bot achète quand le score dépasse 0,25, mais ne revend que s'il retombe sous 0,10.
  Entre les deux, il **conserve** sa position. Il ne paie donc plus de frais pour du bruit.
- **Bande de non-transaction** : les réajustements de moins de 3 % du capital sont ignorés. Le backtest
  reproduit désormais exactement ce comportement réel.
- **Prises de profit échelonnées (TP)** : à +6 ATR depuis l'achat, le bot encaisse 25 % de sa position
  et remonte son stop au prix d'achat, ce qui rend la position « gratuite ». À +12 ATR, il encaisse
  encore 25 %. Les seuils varient selon le profil (4, 6 ou 8 ATR) et se désactivent dans les Réglages.
  *Mesure honnête sur données simulées :* les prises de profit font passer les ventes gagnantes de
  48 % à 51-59 %, mais réduisent le rendement, car elles coupent une partie des grosses tendances.
  Les réglages larges retenus par défaut limitent ce coût. Seuls les vrais cours diront s'il vaut
  mieux les garder.
- **Filtre de crise** : si la volatilité du marché sur 20 jours dépasse 1,5 fois sa moyenne sur un an,
  l'exposition globale est réduite (jusqu'à 40 %).

## 📡 Fil de signaux et santé des données
À chaque passage, le bot compare son analyse à la précédente et publie des événements : changements
de décision, RSI extrêmes, entrées en tendance, stops proches, prises de profit, changement de
méthode dominante, filtre de crise. Ils sont visibles dans l'onglet **Signaux**, et les plus
importants sont envoyés sur Telegram 📡.
Avant chaque décision, les cours sont vérifiés (trois tentatives de téléchargement, puis contrôle des
données absentes, trop courtes ou figées). Un actif douteux est écarté du passage plutôt que de
fausser les décisions.

## 🧪 Le laboratoire (une fois par jour)
Le laboratoire répond à la seule question qui compte : le bot a-t-il un **vrai avantage**, ou de la
chance ? Il utilise jusqu'à 5 ans de vrais cours, frais inclus.
- **Test de chance** : la t-statistique du rendement en excès du marché donne une probabilité
  d'avantage réel. En dessous de 95 %, rien n'est prouvé.
- **Trimestre par trimestre** : le bot bat-il le marché régulièrement ?
- **Robustesse** : 20 réglages du conseil sont testés. Si seul le réglage actuel marche,
  c'est du sur-ajustement, pas un avantage.

Les résultats sont sauvegardés dans `data/lab.json`, s'affichent dans l'interface et sont
résumés dans le bilan Telegram du soir.

**À savoir honnêtement :** combiner des méthodes reconnues rend le bot plus robuste, pas infaillible.
Plusieurs d'entre elles perdent pendant des années entières selon le régime de marché. C'est pour ça
que le conseil les pondère, et que le journal en conditions réelles reste le seul vrai juge.

## Ce que le bot fait, toutes les 2 heures
1. Il télécharge les vrais cours et les convertit en € avec les vrais taux de change.
2. Il lit les actus des dernières 36h, les relie à chaque actif et mesure leur ton (positif ou négatif).
3. Il calcule un score par actif :
   - **tendance** (moyennes 50j et 200j)
   - **momentum** sur 60j, ajusté de la volatilité
   - **RSI** (suracheté ou survendu)
   - **sentiment de l'actu** (15 % du score)
4. Il décide : achat, renforcement, allègement ou vente totale.
5. Il dimensionne : plus un actif est risqué, plus la position est petite (max 20 % par actif).
6. Il passe les ordres fictifs, frais inclus, et calcule les gains ou pertes réalisés.
7. Il t'envoie une alerte par ordre et enregistre tout dans `data/journal.csv`.

## Installation (une quinzaine de minutes, une seule fois)

### 1. Crée ton bot Telegram
1. Dans Telegram, ouvre **@BotFather**, tape `/newbot` et suis les étapes.
2. Il te donne un **token**. Garde-le pour toi, c'est la clé de ton bot.
3. Envoie un message quelconque à ton nouveau bot.
4. Ouvre `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` dans un navigateur.
   Le nombre affiché après `"chat":{"id":` est ton **chat_id**.

### 2. Mets le bot sur GitHub (gratuit, il tournera même PC éteint)
1. Crée un compte sur github.com, puis un **nouveau dépôt privé** (par exemple `oracle-bot`).
2. Envoie tous les fichiers de ce dossier dans le dépôt, y compris le dossier `.github`.
   Le plus simple : utilise « Add file → Upload files ».
3. Va dans **Settings → Secrets and variables → Actions → New repository secret**.
   Crée ces deux secrets :
   - `TELEGRAM_TOKEN` : ton token
   - `TELEGRAM_CHAT_ID` : ton chat_id
   - `ANTHROPIC_API_KEY` : ta clé d'API Claude (optionnel, mais c'est ce qui rend le bot
     intelligent, voir plus bas)
4. Va dans l'onglet **Actions**, active les workflows, puis sur
   « M-TRADE - bot autonome », clique sur **Run workflow** pour le premier lancement.

C'est fait. Il tournera ensuite tout seul toutes les 2 heures.

### Sur ton ordinateur (optionnel, pour tester)
```bash
pip install -r requirements.txt
python main.py backtest        # teste la stratégie sur 5 ans de vrais cours
python main.py run --full      # un passage complet, avec tous les signaux
python main.py status          # état du portefeuille
python main.py run --demo      # test hors ligne avec des données simulées
```

## 🖥️ L'interface (tableau de bord)
Après chaque passage, le bot met à jour `docs/index.html`. On y trouve la courbe de valeur face au
marché, les scores (M-TRADE, Performance, Intelligence, Risque), la lecture de l'IA, tous les cours avec
leurs mini-graphiques et leurs signaux, les positions, le journal complet des ordres, le détail du risque
et les actus analysées.

**Pour l'ouvrir sur ton téléphone :** active GitHub Pages (**Settings → Pages → Branch : main,
dossier /docs**). Ton interface sera alors en ligne à l'adresse `https://<ton-pseudo>.github.io/<ton-depot>/`.
- Avec un compte GitHub gratuit, GitHub Pages exige un dépôt **public**. Tout le monde peut alors voir
  le code et le portefeuille fictif, mais jamais tes secrets (clés API, Telegram), qui restent cachés.
  Si tu préfères un dépôt privé, ouvre `docs/data.json` depuis GitHub et charge-le dans l'aperçu avec
  le bouton « Charger mes données ».
- Pour démarrer avec un historique, lance une fois `python main.py replay --days 120` sur ton ordinateur.
  La stratégie y est rejouée sur les vrais cours des 120 derniers jours, sans l'actu. Envoie ensuite
  les dossiers `data/` et `docs/` sur GitHub.

### Comment les scores sont calculés
- **Performance** : le rendement du bot comparé à « tout acheter à parts égales et garder », et son
  Sharpe (le rendement obtenu par unité de risque).
- **Intelligence** : 5 jours après chaque ordre, le prix est-il allé dans le sens prévu ? On compte aussi
  la part de ventes gagnantes. 50 correspond au hasard. Tant qu'il y a moins de 20 mesures, le score
  reste proche de 50 et affiche « en calibrage ».
- **Risque** : la volatilité réelle du portefeuille, la taille de la plus grosse position, la part de
  crypto et la baisse en cours depuis le dernier sommet.
- **Score M-TRADE** : 40 % performance, 40 % intelligence et 20 % maîtrise du risque.

### Installer M-TRADE comme une appli sur ton téléphone
Ouvre ton adresse GitHub Pages dans Safari (iPhone) ou Chrome (Android).
- **iPhone** : bouton Partager, puis « Sur l'écran d'accueil ».
- **Android** : menu ⋮, puis « Installer l'application ».

L'icône M-TRADE apparaît alors sur ton écran d'accueil, et l'appli s'ouvre en plein écran.

### Fonctions de l'interface
- **Fiche complète par actif** : touche un actif dans le bandeau, la matrice ou le tableau des marchés.
  Tu y vois sa courbe sur environ un an avec les moyennes 20 et 50 jours, son score détaillé,
  la lecture de l'IA et ses ordres.
- **Assistant « Demande à M-TRADE »** : pose tes questions sur les décisions du bot. Il ne fonctionne
  que dans l'aperçu ouvert dans l'appli Claude. Sur ta version GitHub Pages, charge ton `data.json`
  dans cet aperçu pour l'utiliser avec tes vraies données.
- **Direct crypto** (Bitcoin, Ethereum, Solana) via Binance, sur la version GitHub Pages.

## 💶 Options gratuites et payantes

Tout fonctionne gratuitement : vrais cours, direct crypto et or, actus, bot autonome, conseil des 8 stratégies, thermomètre de crise, laboratoire, encyclopédie, alertes Telegram et assistant (dans l'appli Claude).
La seule option payante est **l'analyse IA de l'actualité par Claude**, avec son bulletin et sa mémoire. Elle est **désactivée** (`AI["enabled"] = False` dans `config.py`) mais reste visible dans Réglages › Options. Pour l'activer, passe-la à `True` et ajoute le secret `ANTHROPIC_API_KEY`.

## 📚 La culture de trader (v14)

- **Encyclopédie M-TRADE** (`knowledge.py`) : 66 fiches, de la naissance de la Bourse d'Amsterdam (1602) à aujourd'hui. Elle couvre l'analyse technique, la macro, l'intermarché, le risque, la psychologie, les découvertes académiques, la crypto, les matières premières et l'exécution. Chaque fiche se termine par une **règle**. Ces règles et les leçons des grandes crises sont envoyées à Claude à chaque analyse. L'IA doit dire quelle règle elle applique (`principle`) et à quel épisode la situation ressemble (`analogue`). On consulte tout ça dans l'onglet Savoir (recherche et chapitres).
- **Chandeliers japonais** : 8e stratégie du conseil (Homma au XVIIIe siècle, Nison en 1991). Le bot détecte, sur les vraies bougies, le marteau, l'étoile filante, l'avalement, les étoiles du matin et du soir, les trois soldats et les trois corbeaux. Une figure ne compte qu'après une vraie tendance, et son effet s'estompe en environ 5 jours. Comme les autres stratégies, elle ne gagne du poids que si elle marche.
- **Thermomètre de crise** (`crisis.py`) : un score de 0 à 100 qui combine les corrélations, la volatilité, la baisse depuis le plus haut, la vitesse de chute et la part des actifs sous leur moyenne. Il compare le profil du marché à 1987/2020, 2000, 2008 et 2022. À partir de 55, l'exposition passe à ×0,85 ; à partir de 70, à ×0,6. Le fil de signaux prévient quand le thermomètre franchit ces seuils.

Honnêtement : sur les données de démo (aléatoires), les chandeliers n'apportent pas d'avantage, ce qui est attendu. Leur vrai poids sera fixé par le conseil sur les vrais cours.

## 🧠 Le cerveau IA (Claude)
Avec une clé d'API, Claude lit toutes les actus à chaque passage. Il comprend les mécanismes, y compris
les effets indirects (par exemple : pétrole en hausse → inflation → Fed → Nasdaq). Il donne pour chaque
actif un impact entre -1 et +1, un niveau de confiance et une explication en français. Cette analyse
pèse 30 % de la décision. Sa lecture du contexte mondial apparaît dans chaque alerte.

- Pour obtenir une clé : crée un compte sur **console.anthropic.com**, ajoute un peu de crédit,
  puis va dans **API Keys → Create Key**. Garde-la secrète.
- Le modèle utilisé par défaut est `claude-haiku-5-5`, rapide et économique. Pour une analyse plus
  fine, mets `claude-sonnet-5-5` dans `config.py`. Vérifie les tarifs sur la console. Tu peux aussi
  y fixer une limite de dépense mensuelle.
- Sans clé, ou si l'API ne répond pas, le bot continue avec l'analyse par mots-clés.
- Pour tester l'affichage sans clé : `python main.py run --demo --mock-ai`

## Personnaliser
Tout se règle dans `config.py` : les actifs suivis, les flux d'actu, le capital de départ, les frais,
le poids de l'actu dans le score, la vente à découvert (`allow_short`) et l'heure du bilan.

## À savoir, honnêtement
- **Lance `python main.py backtest` en premier.** Il compare le bot à une stratégie « tout acheter
  et garder ». Si le bot ne fait pas mieux sur les vrais cours, c'est qu'il faut améliorer la stratégie.
- Le sentiment de l'actu n'est pas backtesté, faute d'historique d'actus gratuit. Seul le journal
  en direct dira si l'actu améliore les décisions.
- Les données gratuites de Yahoo peuvent avoir quelques minutes de retard, ou des trous ponctuels.
- **Laisse-le tourner au moins 3 mois** en fictif avant de tirer des conclusions. Une bonne semaine
  ne prouve rien.
- Aucun bot ne prévoit le marché à coup sûr. C'est un outil d'apprentissage et d'expérimentation,
  pas un conseil financier.
