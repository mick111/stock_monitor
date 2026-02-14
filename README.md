# stock_monitor

Moniteur de stock multi-pages avec notification email.

## Fichiers de configuration

- `smtp.env` (sensible, ignore par git): credentials SMTP uniquement.
- `monitor.env` (local): configuration non sensible (logs + chemins de config).
- `monitor_targets.json` (local, ignore par git): cibles a surveiller.
- `monitor_targets.example.json`: exemple versionnable pour creer votre config.

## Structure de `monitor_targets.json`

Chaque entree de `targets` represente une page a surveiller:

- `url`: URL du produit.
- `out_of_stock_terms`: liste des termes qui signifient "hors stock".
- `schedule`: frequence de surveillance:
  - `{"mode": "hourly", "interval_seconds": 3600}`
  - `{"mode": "daily", "time": "09:30"}`
- `emails_on_out_of_stock`: liste des emails a prevenir quand la page est hors stock.
- `emails_on_in_stock`: liste des emails a prevenir quand la page est en stock.
- `notify_on_same_state`:
  - `false` = notifie seulement au changement d'etat.
  - `true` = notifie a chaque verification planifiee.

Le script considere:

- `out_of_stock` si au moins un terme de `out_of_stock_terms` est detecte.
- sinon `in_stock`.

## Execution

Le script principal:

- `python3 monitor_stock.py` -> mode planifie (respecte les schedules).
- `python3 monitor_stock.py --once` -> force la verification de toutes les pages.

Le service systemd est declenche chaque minute via timer. Le script decide ensuite quelles pages sont dues selon leur `schedule`.

Par defaut, les chemins de `monitor.env` peuvent rester relatifs (`monitor.log`, `monitor_targets.json`, `monitor_state.json`) et sont resolus depuis le dossier du script.

## Activation systemd

Depuis le dossier du projet:

```bash
sudo cp stock-monitor.service /etc/systemd/system/
sudo cp stock-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stock-monitor.timer
```

Verification:

```bash
systemctl status stock-monitor.timer
systemctl status stock-monitor.service
```

Note: le service pointe vers `/home/pi/Projects/stock_monitor`.
Si vous renommez le dossier projet, mettez aussi a jour `stock-monitor.service`.
