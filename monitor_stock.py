#!/usr/bin/env python3
import json
import logging
import os
import smtplib
import sys
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent


def resolve_project_path(env_var_name: str, default_relative_path: str) -> Path:
    raw_value = (os.environ.get(env_var_name) or default_relative_path).strip()
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path


LOG_FILE = resolve_project_path("LOG_FILE", "monitor.log")
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "5"))

MONITOR_CONFIG_FILE = resolve_project_path("MONITOR_CONFIG_FILE", "monitor_targets.json")
MONITOR_STATE_FILE = resolve_project_path("MONITOR_STATE_FILE", "monitor_state.json")
HTTP_TIMEOUT_SECONDS = int(os.environ.get("HTTP_TIMEOUT_SECONDS", "30"))

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "") or SMTP_USER
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") not in {"0", "false", "False"}

logger = logging.getLogger("stock_monitor")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)


def log(message: str) -> None:
    logger.info(message)


def parse_string_list(raw_value: Any, field_name: str, target_name: str) -> list[str]:
    if raw_value is None:
        return []

    values: list[str] = []
    if isinstance(raw_value, str):
        values = [item.strip() for item in raw_value.split(",")]
    elif isinstance(raw_value, list):
        for item in raw_value:
            if not isinstance(item, str):
                raise ValueError(
                    f"Target '{target_name}': '{field_name}' doit contenir uniquement des chaines."
                )
            values.append(item.strip())
    else:
        raise ValueError(
            f"Target '{target_name}': '{field_name}' doit etre une liste ou une chaine."
        )

    return [item for item in values if item]


def parse_schedule(raw_schedule: Any, target_name: str) -> dict[str, Any]:
    if raw_schedule is None:
        raw_schedule = {"mode": "hourly"}
    if not isinstance(raw_schedule, dict):
        raise ValueError(f"Target '{target_name}': 'schedule' doit etre un objet.")

    mode = str(raw_schedule.get("mode", "hourly")).strip().lower()
    if mode == "hourly":
        interval_seconds = int(raw_schedule.get("interval_seconds", 3600))
        if interval_seconds <= 0:
            raise ValueError(
                f"Target '{target_name}': 'interval_seconds' doit etre > 0."
            )
        return {
            "mode": "hourly",
            "interval_seconds": interval_seconds,
        }

    if mode == "daily":
        time_value = str(raw_schedule.get("time", "")).strip()
        if len(time_value) != 5 or time_value[2] != ":":
            raise ValueError(
                f"Target '{target_name}': horaire daily invalide, attendu HH:MM."
            )
        hour = int(time_value[:2])
        minute = int(time_value[3:])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError(
                f"Target '{target_name}': horaire daily invalide, attendu HH:MM."
            )
        return {
            "mode": "daily",
            "time": f"{hour:02d}:{minute:02d}",
            "minute_of_day": (hour * 60) + minute,
        }

    raise ValueError(
        f"Target '{target_name}': mode schedule inconnu '{mode}', attendu 'hourly' ou 'daily'."
    )


def load_monitor_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier de configuration introuvable: {path}. Creez-le a partir du .example."
        )

    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    if not isinstance(raw, dict):
        raise ValueError("La configuration doit etre un objet JSON.")

    raw_targets = raw.get("targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise ValueError("La configuration doit contenir 'targets' (liste non vide).")

    targets: list[dict[str, Any]] = []
    for index, target in enumerate(raw_targets, start=1):
        if not isinstance(target, dict):
            raise ValueError(f"Target #{index}: format invalide.")

        target_name = str(target.get("name", "")).strip() or f"target_{index}"
        target_id = str(target.get("id", "")).strip() or f"target_{index}"
        url = str(target.get("url", "")).strip()
        if not url:
            raise ValueError(f"Target '{target_name}': 'url' est obligatoire.")

        out_of_stock_terms = parse_string_list(
            target.get("out_of_stock_terms"),
            "out_of_stock_terms",
            target_name,
        )
        if not out_of_stock_terms:
            raise ValueError(
                f"Target '{target_name}': 'out_of_stock_terms' doit contenir au moins une valeur."
            )

        schedule = parse_schedule(target.get("schedule"), target_name)
        emails_on_out_of_stock = parse_string_list(
            target.get("emails_on_out_of_stock"),
            "emails_on_out_of_stock",
            target_name,
        )
        emails_on_in_stock = parse_string_list(
            target.get("emails_on_in_stock"),
            "emails_on_in_stock",
            target_name,
        )
        notify_on_same_state = bool(target.get("notify_on_same_state", False))

        targets.append(
            {
                "id": target_id,
                "name": target_name,
                "url": url,
                "out_of_stock_terms": out_of_stock_terms,
                "schedule": schedule,
                "emails_on_out_of_stock": emails_on_out_of_stock,
                "emails_on_in_stock": emails_on_in_stock,
                "notify_on_same_state": notify_on_same_state,
            }
        )

    return {"targets": targets}


def parse_iso_datetime(raw_value: Any) -> datetime | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"targets": {}}

    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except Exception as exc:  # pragma: no cover
        log(f"STATE: lecture impossible ({exc}), recreation de l'etat.")
        return {"targets": {}}

    if not isinstance(state, dict):
        return {"targets": {}}
    if not isinstance(state.get("targets"), dict):
        state["targets"] = {}
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)


def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def send_email(subject: str, body: str, recipients: list[str]) -> bool:
    missing = []
    if not SMTP_HOST:
        missing.append("SMTP_HOST")
    if not SMTP_PORT:
        missing.append("SMTP_PORT")
    if not SMTP_USER:
        missing.append("SMTP_USER")
    if not SMTP_PASS:
        missing.append("SMTP_PASS")
    if not EMAIL_FROM:
        missing.append("EMAIL_FROM")
    if missing:
        log("EMAIL: configuration SMTP incomplete: " + ", ".join(missing))
        return False

    if not recipients:
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        log("EMAIL: notification envoyee a " + ", ".join(recipients))
        return True
    except Exception as exc:
        log(f"EMAIL: echec d'envoi: {exc}")
        return False


def detect_stock_state(html: str, out_of_stock_terms: list[str]) -> tuple[str, str]:
    lower_html = html.lower()
    for marker in out_of_stock_terms:
        if marker.lower() in lower_html:
            return "out_of_stock", marker
    return "in_stock", ""


def is_target_due(target: dict[str, Any], target_state: dict[str, Any], now: datetime) -> bool:
    schedule = target["schedule"]
    last_check = parse_iso_datetime(target_state.get("last_check_at"))

    if schedule["mode"] == "hourly":
        if last_check is None:
            return True
        elapsed_seconds = (now - last_check).total_seconds()
        return elapsed_seconds >= schedule["interval_seconds"]

    minute_of_day = (now.hour * 60) + now.minute
    if minute_of_day < schedule["minute_of_day"]:
        return False
    if last_check is None:
        return True
    return last_check.date() < now.date()


def evaluate_target(
    target: dict[str, Any],
    target_state: dict[str, Any],
    now: datetime,
) -> bool:
    target_name = target["name"]
    url = target["url"]
    previous_state = target_state.get("last_state")

    log(f"[{target_name}] verification de {url}")
    try:
        html = fetch_html(url)
    except Exception as exc:
        log(f"[{target_name}] ERREUR HTTP: {exc}")
        target_state["last_state"] = "unknown"
        target_state["last_check_at"] = now.isoformat(timespec="seconds")
        return False

    current_state, marker = detect_stock_state(html, target["out_of_stock_terms"])
    if current_state == "out_of_stock":
        log(f"[{target_name}] HORS STOCK - terme detecte: {marker}")
        recipients = target["emails_on_out_of_stock"]
    else:
        log(f"[{target_name}] EN STOCK - aucun terme out_of_stock detecte")
        recipients = target["emails_on_in_stock"]

    should_notify = target["notify_on_same_state"] or previous_state != current_state
    if should_notify:
        if recipients:
            subject_state = "EN STOCK" if current_state == "in_stock" else "HORS STOCK"
            marker_line = marker if marker else "aucun"
            body = (
                f"Cible: {target_name}\n"
                f"URL: {url}\n"
                f"Etat: {subject_state}\n"
                f"Terme detecte: {marker_line}\n"
                f"Date: {now.isoformat(timespec='seconds')}\n"
            )
            send_email(
                f"[Stock Monitor] {subject_state} - {target_name}",
                body,
                recipients,
            )
        else:
            log(f"[{target_name}] Aucun destinataire configure pour l'etat {current_state}.")
    else:
        log(f"[{target_name}] Etat inchange ({current_state}), pas de notification.")

    target_state["last_state"] = current_state
    target_state["last_marker"] = marker
    target_state["last_check_at"] = now.isoformat(timespec="seconds")
    return True


def run_cycle(force_run: bool) -> int:
    config_path = MONITOR_CONFIG_FILE
    state_path = MONITOR_STATE_FILE

    try:
        config = load_monitor_config(config_path)
    except Exception as exc:
        log(f"CONFIG: echec de chargement de {config_path}: {exc}")
        return 2

    state = load_state(state_path)
    targets_state = state.setdefault("targets", {})
    now = datetime.now()

    checked_count = 0
    for target in config["targets"]:
        target_id = target["id"]
        target_state = targets_state.setdefault(target_id, {})
        if not force_run and not is_target_due(target, target_state, now):
            continue
        checked_count += 1
        evaluate_target(target, target_state, now)

    state["updated_at"] = now.isoformat(timespec="seconds")
    save_state(state_path, state)

    if checked_count:
        log(f"Cycle termine: {checked_count} page(s) verifiee(s).")
    return 0


def main() -> None:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(
            "Usage:\n"
            "  monitor_stock.py           # run planifie (respecte schedule)\n"
            "  monitor_stock.py --once    # force la verification de toutes les pages\n"
        )
        sys.exit(0)

    force_run = "--once" in sys.argv or "-1" in sys.argv
    sys.exit(run_cycle(force_run))


if __name__ == "__main__":
    main()
