# stock_monitor

Moniteur de stock multi-pages avec notification email.

## Fichiers de configuration

- `smtp.env` (sensible, ignore par git): credentials SMTP uniquement.
- `monitor.env` (local): configuration non sensible (logs + chemins de config).
- `monitor_targets.json` (local, ignore par git): cibles a surveiller.
- `monitor_targets.example.json`: exemple versionnable pour creer votre config.

## Structure de `monitor_targets.json`

Chaque entree de `targets` represente une page a surveiller:

- `url`: URL a telecharger.
- `in_stock_terms` (optionnel) **ou** `out_of_stock_terms` (optionnel) : ne pas remplir les deux en meme temps.
  - **Detection negative (produits / billets indisponibles)** : ne renseigner que `out_of_stock_terms` (ex. "Rupture de stock", "Out of stock"). L'etat est *hors stock* si l'un des termes est present dans la page, sinon *en stock*.
  - **Detection positive (annonce, ville, etc.)** : ne renseigner que `in_stock_terms` (ex. "Paris" pour un concert). L'etat est *en stock* si l'un des termes est present, sinon *hors stock* (en attente).
- `schedule`: frequence de surveillance:
  - `{"mode": "hourly", "interval_seconds": 3600}`
  - `{"mode": "daily", "time": "09:30"}`
- `emails_on_out_of_stock`: destinataires quand l'etat est *hors stock* (dans chaque mode).
- `emails_on_in_stock`: destinataires quand l'etat est *en stock*.
- `notify_on_same_state`:
  - `false` = notifie seulement au changement d'etat.
  - `true` = notifie a chaque verification planifiee.
- `enabled` (optionnel) : `false` pour desactiver temporairement une cible.

## Execution

Le script principal:

- `python3 monitor_stock.py` -> mode planifie (respecte les schedules).
- `python3 monitor_stock.py --once` -> force la verification de toutes les pages.

Le service systemd est declenche chaque minute via timer. Le script decide ensuite quelles pages sont dues selon leur `schedule`.

Par defaut, les chemins de `monitor.env` peuvent rester relatifs (`monitor.log`, `monitor_targets.json`, `monitor_state.json`) et sont resolus depuis le dossier du script.

## Activation systemd

Depuis le dossier du projet, option rapide:

```bash
bash install_systemd.sh
```

Ou manuellement:

```bash
PROJECT_DIR="$(pwd)"
sudo ln -sfn "$PROJECT_DIR/stock-monitor.service" /etc/systemd/system/stock-monitor.service
sudo ln -sfn "$PROJECT_DIR/stock-monitor.timer" /etc/systemd/system/stock-monitor.timer
sudo systemctl daemon-reload
sudo systemctl enable --now stock-monitor.timer
```

`ln -sfn` remplace proprement une ancienne copie ou un ancien lien, ce qui permet de garder les unites systemd synchronisees avec les fichiers du projet.

Verification:

```bash
systemctl status stock-monitor.timer
systemctl status stock-monitor.service
```

Note: le service pointe vers `/home/mick111/Documents/stock_monitor`.
Si vous renommez le dossier projet, mettez aussi a jour `stock-monitor.service`, puis relancez la commande `ln -sfn` pour recreer les liens.
