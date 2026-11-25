"""Configuration du bot. Modifie librement."""

# Univers suivi : symbole Yahoo Finance -> nom lisible
UNIVERSE = {
    # Indices / ETF actions
    "^FCHI": "CAC 40",
    "^GDAXI": "DAX",
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq",
    "^N225": "Nikkei 225",
    # Crypto
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
    # Forex
    "EURUSD=X": "EUR/USD",
    "USDJPY=X": "USD/JPY",
    # Matières premières
    "GC=F": "Or",
    "CL=F": "Pétrole WTI",
    # Taux (rendement US 10 ans)
    "^TNX": "Taux US 10 ans",
    # Univers élargi (v16) : secteurs, grandes actions, obligations, argent métal
    "XLK": "Secteur technologie US",
    "XLV": "Secteur santé US",
    "XLE": "Secteur énergie US",
    "XLF": "Secteur finance US",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "TLT": "Obligations US 20 ans",
    "IEF": "Obligations US 7-10 ans",
    "SI=F": "Argent métal",
}

# Actifs sur lesquels le bot peut prendre des positions fictives
CORE_TRADABLE = ["^FCHI", "^GDAXI", "^GSPC", "^IXIC", "^N225",
                 "BTC-USD", "ETH-USD", "SOL-USD", "GC=F", "CL=F"]
EXTRA_TRADABLE = ["XLK", "XLV", "XLE", "XLF", "AAPL", "MSFT", "NVDA", "TLT", "IEF", "SI=F"]
TRADABLE = CORE_TRADABLE + EXTRA_TRADABLE

ALL_TRADABLE = list(TRADABLE)   # tout ce que le bot sait trader (TRADABLE = la sélection du profil)

# Devise de cotation de chaque actif (tout est converti en € dans le portefeuille)
CURRENCY = {"^FCHI": "EUR", "^GDAXI": "EUR", "^N225": "JPY"}   # le reste : USD

# Mots-clés pour relier une actu à un actif
KEYWORDS = {
    "^FCHI": ["cac", "france", "paris", "bce", "ecb", "europe", "lvmh", "totalenergies"],
    "^GDAXI": ["dax", "allemagne", "germany", "bce", "ecb", "europe"],
    "^GSPC": ["s&p", "wall street", "fed", "powell", "us economy", "inflation", "jobs"],
    "^IXIC": ["nasdaq", "tech", "nvidia", "apple", "microsoft", "ai ", "semiconductor"],
    "^N225": ["nikkei", "japan", "japon", "boj", "yen"],
    "BTC-USD": ["bitcoin", "btc", "crypto", "etf bitcoin", "sec"],
    "ETH-USD": ["ethereum", "eth", "crypto"],
    "SOL-USD": ["solana", "sol", "crypto"],
    "GC=F": ["gold", "or ", "safe haven", "valeur refuge"],
    "CL=F": ["oil", "pétrole", "opec", "opep", "brent", "crude"],
    "EURUSD=X": ["euro", "dollar", "ecb", "bce", "fed"],
    "XLK": ["tech", "software", "semiconductor", "ai "],
    "XLV": ["health", "pharma", "biotech", "santé"],
    "XLE": ["energy", "oil", "exxon", "chevron", "pétrole"],
    "XLF": ["bank", "banque", "jpmorgan", "financials", "fed"],
    "AAPL": ["apple", "iphone", "tim cook"],
    "MSFT": ["microsoft", "azure", "openai"],
    "NVDA": ["nvidia", "gpu", "jensen huang", "ai chip"],
    "TLT": ["treasury", "bond", "yields", "obligations", "fed"],
    "IEF": ["treasury", "bond", "yields", "obligations"],
    "SI=F": ["silver", "argent métal"],
}

# Flux RSS d'actualité (gratuits)
NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=stock+market+OR+fed+OR+inflation+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=bourse+OR+BCE+OR+CAC+40+when:1d&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=bitcoin+OR+crypto+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=oil+OR+gold+OR+geopolitics+markets+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://finance.yahoo.com/news/rssindex",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.lesechos.fr/rss/rss_finance-marches.xml",
    "https://www.boursorama.com/rss/actualites/economie.xml",
]

# Paramètres de stratégie
STRATEGY = {
    "sma_fast": 50,
    "sma_slow": 200,
    "momentum_days": 60,
    "rsi_days": 14,
    "vol_days": 20,
    "target_vol": 0.15,          # volatilité annuelle visée par position
    "max_weight": 0.20,          # poids max par actif
    "news_weight": 0.15,         # influence du sentiment actu sur le score
    "entry_threshold": 0.25,     # score minimum pour ouvrir une position
    "exit_threshold": 0.10,      # on ne revend que si le score retombe sous ce seuil (hystérésis)
    "stress_level": 1.5,         # filtre de crise : volatilité 20 j > 1,5 × celle d'un an → on réduit
    "allow_short": True,         # le bot peut aussi parier à la baisse (vente à découvert fictive)
}

# Analyste IA (Claude). Clé dans la variable d'environnement ANTHROPIC_API_KEY.
# OPTION PAYANTE, désactivée pour l'instant : passer à True ET ajouter le secret ANTHROPIC_API_KEY.
# Désactivée, le bot lit l'actualité par mots-clés (gratuit) ; tout le reste fonctionne.
AI = {
    "enabled": False,
    "model": "claude-haiku-5-5",      # rapide et économique ; "claude-sonnet-5-5" = plus fin
    "api_version": "2026-10-21",
    "news_weight": 0.30,              # poids de l'IA dans le score (remplace news_weight)
}

# Gestion du risque
RISK = {
    "atr_mult": 3.0,        # stop suiveur : plus haut moins 3 ATR
    "cooldown_days": 5,     # pas de rachat pendant 5 jours après un stop
    "dd_reduce": 0.12,      # portefeuille -12 % depuis son sommet : exposition divisée par 2
    "dd_cut": 0.20,         # portefeuille -20 % : exposition divisée par 4
    "corr_adjust": True,
    "take_profit": True,    # prises de profit échelonnées
    "tp1_atr": 6.0,         # objectif 1 : +6 ATR depuis l'achat → encaisse 25 %, stop au prix d'achat
    "tp1_sell": 0.25,
    "tp2_atr": 12.0,        # objectif 2 : +12 ATR → encaisse encore 25 % du reste
    "tp2_sell": 0.25,    # réduit les positions qui forment un même pari (ex : BTC + ETH + SOL)
}

# Paper trading
PAPER = {
    "starting_cash": 10_000.0,   # capital fictif en €
    "fee_rate": 0.001,           # 0,1 % de frais par transaction
    "min_trade_pct": 0.03,       # ignore les ajustements < 3 % du portefeuille (évite le bruit)
    "daily_summary_hour": 21,    # heure (Paris) d'un bilan quotidien ; None pour désactiver
    "state_file": "data/portfolio.json",
    "journal_file": "data/journal.csv",
}


# Catalogue des options (affiché dans Réglages > Options). paid=True : option payante.
OPTIONS = [
    {"key": "prices", "name": "Vrais cours des marchés", "desc": "Indices, crypto, or, pétrole, devises (Yahoo Finance, quotidien).", "paid": False},
    {"key": "live", "name": "Direct crypto et or", "desc": "Bougies et prix en temps réel (Binance), scalping en direct.", "paid": False},
    {"key": "news", "name": "Actualités mondiales", "desc": "Flux d'actus lus à chaque passage, analysés par mots-clés.", "paid": False},
    {"key": "bot", "name": "Bot autonome toutes les 2 h", "desc": "Achats, ventes, stops et prises de profit sur le portefeuille fictif (GitHub Actions).", "paid": False},
    {"key": "council", "name": "Conseil des 8 stratégies", "desc": "Dont les chandeliers japonais, pondérées selon leurs résultats.", "paid": False},
    {"key": "thermo", "name": "Thermomètre de crise", "desc": "Compare le marché aux grandes crises et réduit le risque.", "paid": False},
    {"key": "lab", "name": "Laboratoire", "desc": "Test de chance, walk-forward, robustesse, chaque jour.", "paid": False},
    {"key": "knowledge", "name": "Encyclopédie M-TRADE", "desc": "66 fiches et 400 ans d'histoire des marchés.", "paid": False},
    {"key": "telegram", "name": "Alertes Telegram", "desc": "Gratuit : il suffit d'ajouter TELEGRAM_TOKEN et TELEGRAM_CHAT_ID dans GitHub.", "paid": False},
    {"key": "assistant", "name": "Assistant M-TRADE", "desc": "Discussion avec l'IA, incluse quand l'appli est ouverte dans Claude.", "paid": False},
    {"key": "ai_claude", "name": "Analyse IA de l'actualité (Claude)", "desc": "Claude lit et comprend chaque actu, applique l'encyclopédie, compare aux crises passées, et se fait noter. Nécessite une clé API Anthropic (facturée à l'usage, quelques euros par mois).", "paid": True},
    {"key": "ai_memory", "name": "Bulletin et mémoire de l'IA", "desc": "Notes des prédictions de l'IA et ajustement automatique de son poids. Dépend de l'analyse IA.", "paid": True},
]
