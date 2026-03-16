#!/usr/bin/env python3
"""Multi-backend notification sender for multi-agent-shogun.

Usage:
    python3 scripts/notify.py "message" [--title TITLE] [--tags TAGS] [--priority N]

Backends: ntfy | discord | slack | mqtt
Config: config/settings.yaml (notify section)
Auth: config/notify_auth.env
"""

import argparse
import base64
import json
import os
import shutil
import sys
import threading
import urllib.request
import urllib.error
from pathlib import Path

# Resolve project root (parent of scripts/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_config():
    """Load notify config from config/settings.yaml. Returns None if disabled."""
    settings_path = _PROJECT_ROOT / "config" / "settings.yaml"
    if not settings_path.exists():
        return None

    # Minimal YAML parser (no PyYAML dependency)
    notify = _parse_notify_section(settings_path)
    if not notify:
        return None

    if not notify.get("enable", False):
        return None

    return notify


def _parse_notify_section(path):
    """Extract notify section from settings.yaml without PyYAML."""
    lines = path.read_text().splitlines()
    result = {}
    in_notify = False
    current_subsection = None
    indent_base = 0

    for line in lines:
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            continue

        # Detect notify: section start
        if stripped == "notify:" or stripped.startswith("notify:"):
            in_notify = True
            indent_base = len(line) - len(line.lstrip())
            continue

        if not in_notify:
            continue

        # Check indentation — if we've dedented back to base level, we left notify
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= indent_base and not line[indent_base:indent_base+1].isspace():
            break

        # Parse key: value
        if ":" not in stripped:
            continue

        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()

        # Remove inline comments
        if val and "#" in val:
            # Handle quoted strings with # inside
            if val.startswith('"') or val.startswith("'"):
                quote = val[0]
                end = val.find(quote, 1)
                if end > 0:
                    val = val[1:end]
                else:
                    val = val.strip("\"'")
            else:
                val = val[:val.index("#")].strip()
        else:
            val = val.strip("\"'")

        # Detect subsection (ntfy:, discord:, etc.)
        if val == "" and key in ("ntfy", "discord", "slack", "mqtt"):
            current_subsection = key
            result[key] = {}
            continue

        # Top-level notify keys
        if current_indent <= indent_base + 2 + 1 and current_subsection is None:
            result[key] = _coerce_value(val)
            current_subsection = None
        elif current_subsection:
            result[current_subsection][key] = _coerce_value(val)
        else:
            # Could be a new top-level key after subsection ended
            # Check indent to decide
            if current_indent <= indent_base + 2:
                current_subsection = None
                result[key] = _coerce_value(val)


    return result if result else None


def _coerce_value(val):
    """Convert string value to appropriate Python type."""
    if val == "":
        return ""
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    try:
        return int(val)
    except ValueError:
        pass
    return val


def _load_auth():
    """Load auth from config/notify_auth.env. Returns dict."""
    auth = {}
    auth_path = _PROJECT_ROOT / "config" / "notify_auth.env"
    if not auth_path.exists():
        return auth

    for line in auth_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        auth[key.strip()] = val.strip()

    return auth


def _send_ntfy(message, title, tags, priority, config, auth):
    """Send via ntfy."""
    ntfy_conf = config.get("ntfy", {})
    topic = ntfy_conf.get("topic", "")
    if not topic:
        return

    server = ntfy_conf.get("server", "https://ntfy.sh").rstrip("/")
    url = f"{server}/{topic}"

    headers = {}
    if title:
        headers["Title"] = title
    if tags:
        headers["Tags"] = tags

    prio = priority or ntfy_conf.get("priority", 3)
    if prio and prio != 3:
        headers["Priority"] = str(prio)

    # Auth
    token = auth.get("NTFY_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        user = auth.get("NTFY_USER", "")
        passwd = auth.get("NTFY_PASS", "")
        if user and passwd:
            cred = base64.b64encode(f"{user}:{passwd}".encode()).decode()
            headers["Authorization"] = f"Basic {cred}"

    req = urllib.request.Request(url, data=message.encode("utf-8"), headers=headers)
    urllib.request.urlopen(req, timeout=10)


def _send_discord(message, title, tags, config, auth):
    """Send via Discord webhook."""
    discord_conf = config.get("discord", {})
    webhook_url = discord_conf.get("webhook_url", "")
    if not webhook_url:
        return

    embed = {"description": message}
    if title:
        embed["title"] = title
    if tags:
        embed["footer"] = {"text": tags}

    payload = json.dumps({"embeds": [embed]}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)


def _send_slack(message, title, tags, config, auth):
    """Send via Slack incoming webhook."""
    slack_conf = config.get("slack", {})
    webhook_url = slack_conf.get("webhook_url", "")
    if not webhook_url:
        return

    blocks = []
    if title:
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": title}})
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": message}})
    if tags:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"_{tags}_"}]})

    text = f"{title}: {message}" if title else message
    payload = json.dumps({"text": text, "blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)


def _send_mqtt(message, title, tags, config, auth):
    """Send via mosquitto_pub."""
    import subprocess

    if not shutil.which("mosquitto_pub"):
        print("Warning: mosquitto_pub not found, skipping MQTT notification", file=sys.stderr)
        return

    mqtt_conf = config.get("mqtt", {})
    host = mqtt_conf.get("host", "localhost")
    port = str(mqtt_conf.get("port", 1883))
    prefix = mqtt_conf.get("topic_prefix", "shogun")
    topic = f"{prefix}/notify"

    payload = json.dumps({"message": message, "title": title, "tags": tags})

    cmd = ["mosquitto_pub", "-h", host, "-p", port, "-t", topic, "-m", payload]

    mqtt_user = auth.get("MQTT_USER", "")
    mqtt_pass = auth.get("MQTT_PASS", "")
    if mqtt_user:
        cmd.extend(["-u", mqtt_user])
    if mqtt_pass:
        cmd.extend(["-P", mqtt_pass])

    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


_BACKENDS = {
    "ntfy": _send_ntfy,
    "discord": _send_discord,
    "slack": _send_slack,
    "mqtt": _send_mqtt,
}


def _do_send(message, title, tags, priority):
    """Actual send logic (runs in thread)."""
    try:
        config = _load_config()
        if not config:
            return

        auth = _load_auth()
        backend = config.get("backend", "ntfy")

        fn = _BACKENDS.get(backend)
        if not fn:
            return

        # ntfy takes priority arg, others don't
        if backend == "ntfy":
            fn(message, title, tags, priority, config, auth)
        else:
            fn(message, title, tags, config, auth)
    except Exception:
        pass  # Silent failure — never block the caller


def send(message, *, title="", tags="", priority=0):
    """Send notification. Non-blocking. No-op if disabled."""
    t = threading.Thread(target=_do_send, args=(message, title, tags, priority), daemon=True)
    t.start()


def main():
    parser = argparse.ArgumentParser(description="Send notification via configured backend")
    parser.add_argument("message", help="Notification message")
    parser.add_argument("--title", default="", help="Notification title")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--priority", type=int, default=0, help="Priority (1-5, ntfy only)")
    parser.add_argument("--sync", action="store_true", help="Send synchronously (for debugging)")
    args = parser.parse_args()

    if args.sync:
        _do_send(args.message, args.title, args.tags, args.priority)
    else:
        send(args.message, title=args.title, tags=args.tags, priority=args.priority)
        # Give daemon thread time to complete
        import time
        time.sleep(2)


if __name__ == "__main__":
    main()
