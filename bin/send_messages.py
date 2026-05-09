#!/Users/rafael/messages/.venv/bin/python3
import csv
import logging
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import click
import phonenumbers

CHAT_DB = Path.home() / "Library/Messages/chat.db"
DEFAULT_CSV = Path.home() / "messages/contacts.csv"
DEFAULT_TEMPLATE = Path.home() / "messages/message_template.txt"
LOGS_DIR = Path.home() / "messages/logs"

logging.basicConfig(format="%(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# Maps CSV service_type values to AppleScript service type constants
SERVICE_MAP = {
    "imessage": "iMessage",
    "sms": "SMS",
    "rcs": "SMS",  # RCS contacts addressed by phone; Messages.app handles upgrade automatically
}


@dataclass
class Contact:
    first_name: str
    last_name: str
    phone: str
    service_type: str
    custom_greeting: str


def normalize_identifier(raw: str) -> str | None:
    raw = raw.strip()
    if "@" in raw:
        return raw  # email-based iMessage handle — pass through as-is
    try:
        parsed = phonenumbers.parse(raw, "US")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None


def load_contacts(csv_path: Path) -> list[Contact]:
    contacts = []
    bad = []
    with open(csv_path, newline="") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            if row.get("active", "yes").lower() != "yes":
                continue
            identifier = normalize_identifier(row["phone"])
            if not identifier:
                bad.append(f"  Row {i}: {row['first_name']} {row['last_name']} — cannot normalize '{row['phone']}'")
                continue
            contacts.append(Contact(
                first_name=row["first_name"],
                last_name=row["last_name"],
                phone=identifier,
                service_type=row.get("service_type", "imessage").lower().strip(),
                custom_greeting=row["custom_greeting"],
            ))
    if bad:
        log.error("Phone normalization failed — fix these rows before sending:")
        for b in bad:
            log.error(b)
        sys.exit(1)
    return contacts


def preflight(contacts: list[Contact]) -> list[Contact]:
    db = sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True)
    missing = []
    for c in contacts:
        cur = db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM handle h "
            "JOIN chat_handle_join chj ON h.ROWID = chj.handle_id "
            "WHERE h.id = ?",
            (c.phone,),
        )
        if cur.fetchone()[0] == 0:
            missing.append(c)
    db.close()
    return missing


def build_message(template: str, contact: Contact) -> str:
    return template.format(
        first_name=contact.first_name,
        last_name=contact.last_name,
        greeting=contact.custom_greeting,
    )


def escape_for_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def send(contact: Contact, message: str) -> str | None:
    service = SERVICE_MAP.get(contact.service_type, "iMessage")
    safe_msg = escape_for_applescript(message)
    safe_phone = escape_for_applescript(contact.phone)
    script = f'''
tell application "Messages"
    set targetService to 1st service whose service type = {service}
    set targetBuddy to buddy "{safe_phone}" of targetService
    send "{safe_msg}" to targetBuddy
end tell
'''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return result.stderr.strip() or f"osascript exit {result.returncode}"
    return None


def append_send_log(path: Path, contact: Contact, status: str, error: str = "") -> None:
    fieldnames = ["timestamp", "first_name", "last_name", "phone", "service_type", "status", "error"]
    exists = path.exists()
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "phone": contact.phone,
            "service_type": contact.service_type,
            "status": status,
            "error": error,
        })


def append_retry_log(path: Path, contact: Contact, error: str) -> None:
    fieldnames = ["first_name", "last_name", "phone", "service_type", "custom_greeting", "active", "error"]
    exists = path.exists()
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "phone": contact.phone,
            "service_type": contact.service_type,
            "custom_greeting": contact.custom_greeting,
            "active": "yes",
            "error": error,
        })


@click.command()
@click.option("--csv", "csv_path", default=str(DEFAULT_CSV), help="Path to contacts CSV")
@click.option("--template", "template_path", default=str(DEFAULT_TEMPLATE), help="Path to message template file")
@click.option("--dry-run", is_flag=True, help="Preview messages without sending")
@click.option("--delay", default=10, show_default=True, help="Seconds between sends")
@click.option("--skip-preflight", is_flag=True, hidden=True)
def main(csv_path: str, template_path: str, dry_run: bool, delay: int, skip_preflight: bool) -> None:
    csv_path = Path(csv_path)
    template_path = Path(template_path)
    today = date.today().strftime("%Y-%m-%d")
    send_log_path = LOGS_DIR / f"send_{today}.csv"
    retry_log_path = LOGS_DIR / f"retry_{today}.csv"

    if not template_path.exists():
        log.error(f"Template not found: {template_path}")
        sys.exit(1)
    template = template_path.read_text()

    if not csv_path.exists():
        log.error(f"Contacts file not found: {csv_path}")
        sys.exit(1)

    contacts = load_contacts(csv_path)
    if not contacts:
        log.info("No active contacts found.")
        return
    log.info(f"Loaded {len(contacts)} active contacts")

    if not skip_preflight:
        if not CHAT_DB.exists():
            log.error("chat.db not found — grant Terminal Full Disk Access in System Settings")
            sys.exit(1)
        log.info("Running pre-flight check...")
        missing = preflight(contacts)
        if missing:
            log.error("PRE-FLIGHT FAILED — no existing thread for:")
            for c in missing:
                log.error(f"  {c.first_name} {c.last_name} ({c.phone})")
            log.error("Open Messages.app and start a conversation with each contact above, then re-run.")
            sys.exit(1)
        log.info(f"Pre-flight OK — {len(contacts)} contacts verified")

    if dry_run:
        log.info("\nDRY RUN — messages that would be sent:\n")
        for c in contacts:
            msg = build_message(template, c)
            print(f"  To:      {c.first_name} {c.last_name} ({c.phone}) [{c.service_type}]")
            print(f"  Message: {msg}")
            print()
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    sent = 0
    failures: list[tuple[Contact, str]] = []

    for i, contact in enumerate(contacts):
        msg = build_message(template, contact)
        log.info(f"[{i+1}/{len(contacts)}] {contact.first_name} {contact.last_name} ({contact.phone})")

        err = send(contact, msg)

        if err is None:
            append_send_log(send_log_path, contact, "sent")
            sent += 1
            log.info("  ✓ sent")
        else:
            log.warning(f"  ✗ failed: {err}")
            log.warning("  Retrying in 15s...")
            time.sleep(15)
            err2 = send(contact, msg)
            if err2 is None:
                append_send_log(send_log_path, contact, "sent_after_retry")
                sent += 1
                log.info("  ✓ sent (after retry)")
            else:
                append_send_log(send_log_path, contact, "failed", err2)
                append_retry_log(retry_log_path, contact, err2)
                failures.append((contact, err2))
                log.warning(f"  ✗ failed after retry: {err2}")

        if i < len(contacts) - 1:
            time.sleep(delay)

    log.info(f"\nSent: {sent}  Failed after retry: {len(failures)}")
    if failures:
        log.warning("\nFailed contacts:")
        for c, err in failures:
            log.warning(f"  {c.first_name} {c.last_name} ({c.phone}): {err}")
        log.warning(f"\nRetry log: {retry_log_path}")
        log.warning(f"To retry:  python3 ~/bin/send_messages.py --csv {retry_log_path}")
    log.info(f"Send log:  {send_log_path}")


if __name__ == "__main__":
    main()
