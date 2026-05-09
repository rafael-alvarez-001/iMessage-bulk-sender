#!/Users/rafael/messages/.venv/bin/python3
import csv
import datetime
import sqlite3
import sys
from pathlib import Path

CHAT_DB = Path.home() / "Library/Messages/chat.db"
LOGS_DIR = Path.home() / "messages/logs"

EPOCH = datetime.datetime(2001, 1, 1)


def chat_db_ts(raw) -> str:
    if not raw:
        return ""
    try:
        return (EPOCH + datetime.timedelta(seconds=raw / 1e9)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(raw)


def latest_send_log() -> Path | None:
    logs = sorted(LOGS_DIR.glob("send_*.csv"), reverse=True)
    return logs[0] if logs else None


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Query chat.db for delivery status after a send run")
    parser.add_argument("--send-log", help="Path to send log CSV (default: most recent in ~/messages/logs/)")
    args = parser.parse_args()

    log_path = Path(args.send_log) if args.send_log else latest_send_log()
    if not log_path or not log_path.exists():
        print("No send log found. Run send_messages.py first.", file=sys.stderr)
        sys.exit(1)

    if not CHAT_DB.exists():
        print("chat.db not found — grant Terminal Full Disk Access in System Settings", file=sys.stderr)
        sys.exit(1)

    with open(log_path, newline="") as f:
        sent_rows = [r for r in csv.DictReader(f) if r["status"] in ("sent", "sent_after_retry")]

    if not sent_rows:
        print("No successfully sent contacts in send log.")
        sys.exit(0)

    db = sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True)

    results = []
    for row in sent_rows:
        phone = row["phone"]
        cur = db.cursor()
        cur.execute(
            "SELECT m.is_delivered, m.is_read, m.date_delivered "
            "FROM message m "
            "JOIN handle h ON m.handle_id = h.ROWID "
            "WHERE h.id = ? AND m.is_from_me = 1 "
            "ORDER BY m.date DESC LIMIT 1",
            (phone,),
        )
        r = cur.fetchone()
        results.append({
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "phone": phone,
            "service_type": row["service_type"],
            "is_delivered": r[0] if r else "",
            "is_read": r[1] if r else "",
            "delivered_at": chat_db_ts(r[2]) if r else "",
        })

    db.close()

    today = datetime.date.today().strftime("%Y-%m-%d")
    out_path = LOGS_DIR / f"delivery_{today}.csv"
    fieldnames = ["first_name", "last_name", "phone", "service_type", "is_delivered", "is_read", "delivered_at"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    delivered = sum(1 for r in results if r["is_delivered"] == 1)
    print(f"Delivery report: {out_path}")
    print(f"Delivered: {delivered}/{len(results)}")

    undelivered = [r for r in results if r["is_delivered"] != 1]
    if undelivered:
        print("Not yet delivered:")
        for r in undelivered:
            print(f"  {r['first_name']} {r['last_name']} ({r['phone']})")


if __name__ == "__main__":
    main()
