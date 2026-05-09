#!/Users/rafael/messages/.venv/bin/python3
import csv
import sqlite3
import sys
from pathlib import Path

import phonenumbers

CHAT_DB = Path.home() / "Library/Messages/chat.db"
DEFAULT_CSV = Path.home() / "messages/contacts.csv"


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


def detect_service(phone_e164: str, db: sqlite3.Connection) -> str | None:
    cur = db.cursor()
    cur.execute(
        "SELECT service FROM handle WHERE id = ? ORDER BY ROWID DESC LIMIT 1",
        (phone_e164,),
    )
    row = cur.fetchone()
    return row[0].lower() if row else None


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Auto-populate service_type in contacts.csv from chat.db")
    parser.add_argument("--csv", dest="csv_path", default=str(DEFAULT_CSV))
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        sys.exit(1)

    if not CHAT_DB.exists():
        print("Error: chat.db not found — grant Terminal Full Disk Access in System Settings", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("contacts.csv is empty.")
        return

    db = sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True)

    updated = 0
    no_thread = []
    bad_phone = []

    for row in rows:
        if row.get("active", "yes").lower() != "yes":
            continue

        identifier = normalize_identifier(row["phone"])
        if not identifier:
            bad_phone.append(f"  {row['first_name']} {row['last_name']}: cannot normalize '{row['phone']}'")
            continue

        row["phone"] = identifier
        service = detect_service(identifier, db)
        if service:
            row["service_type"] = service
            updated += 1
        else:
            no_thread.append(f"  {row['first_name']} {row['last_name']} ({e164})")

    db.close()

    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated: {updated} contacts")
    if bad_phone:
        print("Could not normalize phone (fix manually):")
        for line in bad_phone:
            print(line)
    if no_thread:
        print("No existing thread found (pre-flight will catch these):")
        for line in no_thread:
            print(line)
    if not no_thread and not bad_phone:
        print("All active contacts detected successfully.")


if __name__ == "__main__":
    main()
