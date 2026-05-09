# iMessage Bulk Sender

Sends personalized iMessage/SMS messages to 50+ contacts weekly from a Mac, via a single Claude Code skill invocation. No Terminal knowledge required after initial setup.

---

## Onboarding & Installation

Follow these steps on a fresh machine. You only do this once.

### Step 1 — Clone the repo

```bash
git clone https://github.com/rafael-alvarez-001/iMessage-bulk-sender.git
cd iMessage-bulk-sender
```

> Get the URL from whoever shared this repo with you.

### Step 2 — Run the setup script

```bash
bash bin/setup.sh
```

This will:
- Install Homebrew and Python 3.11+ if missing
- Create a Python virtual environment at `~/messages/.venv`
- Install pip dependencies (`click`, `phonenumbers`)
- Copy scripts to `~/bin/`
- Install the `/imessage-blast` Claude Code skill to `~/.claude/skills/`
- Create `~/messages/` directory structure with starter files
- Walk you through the two required macOS permissions:
  - **Full Disk Access** — reads your Messages delivery history from `chat.db`
  - **Automation → Messages** — sends messages through Messages.app

Both permissions require a one-time manual click in System Settings. The script opens the correct pane and tells you exactly what to toggle.

### Step 4 — Add your contacts

Open `~/messages/contacts.csv` in Numbers or Excel and fill in your contacts:

```
first_name,last_name,phone,service_type,custom_greeting,active
Jane,Smith,+15551234567,,Hi Jane! Hope you're well —,yes
Bob,Jones,bob@example.com,,Hey Bob! Quick update —,yes
```

Leave `service_type` blank — it will be auto-detected in the next step.

> **Phone or email?** For contacts whose iMessage is linked to their Apple ID email rather than their phone number, use their email address in the `phone` column. The scripts handle both formats automatically.

### Step 5 — Auto-detect service types

```bash
~/messages/.venv/bin/python3 ~/bin/detect_service.py
```

This fills in the `service_type` column (imessage / sms / rcs) for each contact by checking your Messages.app history. Re-run this whenever you add contacts or someone switches from iPhone to Android (or vice versa).

> **Requires an existing thread:** auto-detection only works for contacts you've already messaged. If a contact has no prior thread, open Messages.app, send them a message manually, then re-run.

### Step 6 — Write your first message

Edit `~/messages/message_template.txt`:

```
{greeting}

This week's update: [your message here]
```

`{greeting}` is replaced per contact with their `custom_greeting` from the CSV. The rest of the body is the same for everyone.

### Step 7 — Test the installation

See the **Efficacy Tests** section below.

---

## Efficacy Tests

Run these after installation to confirm everything is working before sending to real contacts.

### Test 1 — Pre-flight check

```bash
~/messages/.venv/bin/python3 ~/bin/send_messages.py --dry-run
```

**Expected output:**
```
Pre-flight OK — N contacts verified
DRY RUN — messages that would be sent:
  To: ...
  Message: ...
```

**Pass condition:** exit 0, `Pre-flight OK` in output, one preview per active contact with correct name and greeting.

### Test 2 — Pre-flight catches missing threads

Add a row to `contacts.csv` with a phone number that has no Messages.app thread (e.g. a number you've never texted), then run `--dry-run`.

**Expected output:**
```
PRE-FLIGHT FAILED — no existing thread for:
  [name] ([phone])
```

**Pass condition:** exit non-zero, no message previews shown. Remove the test row when done.

### Test 3 — Live send to one test contact

Set all contacts to `active = no` except one test contact, then run:

```bash
~/messages/.venv/bin/python3 ~/bin/send_messages.py
```

**Expected output:**
```
Pre-flight OK — 1 contacts verified
[1/1] [name] ([identifier])
  ✓ sent
Sent: 1  Failed after retry: 0
```

**Pass condition:** exit 0, message appears in Messages.app, `send_YYYY-MM-DD.csv` created in `~/messages/logs/`.

### Test 4 — Delivery confirmation

60 seconds after Test 3, run:

```bash
~/messages/.venv/bin/python3 ~/bin/delivery_report.py
```

**Expected output:**
```
Delivered: 1/1
```

**Pass condition:** exit 0, `is_delivered = 1` for the test contact in `delivery_YYYY-MM-DD.csv`.

### Test 5 — Rate limiting

After a multi-contact send, check that the 10-second delay between sends is respected:

```bash
awk -F',' 'NR>1 {print $1}' ~/messages/logs/send_$(date +%Y-%m-%d).csv
```

**Pass condition:** timestamps show 10+ seconds between consecutive entries.

### Test 6 — Skill end-to-end

In Claude Code, type:

```
/imessage-blast
```

**Pass condition:** skill walks through all steps (CSV check → template review → dry-run preview → confirm → send → delivery report) without errors.

---

## Requirements

- macOS Tahoe (16) or later
- Claude Code installed
- Terminal granted **Full Disk Access** and **Automation → Messages** (setup script handles this)

---

## File Structure

```
~/bin/
  setup.sh              # one-time onboarding
  send_messages.py      # main send CLI
  detect_service.py     # auto-detects iMessage vs SMS per contact
  delivery_report.py    # queries delivery status from chat.db

~/messages/
  .venv/                # Python virtual environment (created by setup.sh)
  contacts.csv          # contact list (you maintain this)
  message_template.txt  # weekly message body (edit before each run)
  logs/
    send_YYYY-MM-DD.csv      # per-run send log
    retry_YYYY-MM-DD.csv     # contacts that failed after retry
    delivery_YYYY-MM-DD.csv  # delivery confirmation report

~/.claude/skills/imessage-blast/
  SKILL.md              # Claude Code skill
```

---

## contacts.csv Schema

```
first_name,last_name,phone,service_type,custom_greeting,active
Jane,Smith,+15551234567,imessage,"Hi Jane! Hope you're well —",yes
Bob,Jones,bob@example.com,imessage,"Hey Bob! Quick update —",yes
```

| Column | Description |
|---|---|
| `first_name` | Used in message personalization via `{first_name}` |
| `last_name` | Available as `{last_name}` in template |
| `phone` | Phone (any US format) or email for Apple ID iMessage contacts |
| `service_type` | `imessage`, `sms`, or `rcs` — auto-detected by `detect_service.py` |
| `custom_greeting` | Per-contact greeting used as `{greeting}` in template |
| `active` | `yes` to include in sends, `no` to skip without deleting |

---

## message_template.txt Format

```
{greeting}

This week's update: [your message here]
```

`{greeting}`, `{first_name}`, and `{last_name}` are replaced per contact. Everything else is the same for everyone. Edit this file before each weekly run.

---

## Scripts

### detect_service.py

Auto-populates `service_type` in `contacts.csv` from Messages.app history. Run once after adding contacts, and again when contacts switch devices.

```bash
~/messages/.venv/bin/python3 ~/bin/detect_service.py
```

### send_messages.py

Sends personalized messages to all active contacts. Runs a pre-flight check first.

```bash
# Preview without sending
~/messages/.venv/bin/python3 ~/bin/send_messages.py --dry-run

# Send
~/messages/.venv/bin/python3 ~/bin/send_messages.py

# Retry failed contacts from a previous run
~/messages/.venv/bin/python3 ~/bin/send_messages.py --csv ~/messages/logs/retry_2026-05-09.csv

# Options
--csv PATH          contacts CSV (default: ~/messages/contacts.csv)
--template PATH     message template (default: ~/messages/message_template.txt)
--dry-run           preview only, no sends
--delay INT         seconds between sends (default: 10)
```

**Retry behavior:** failed sends are automatically retried once after a 15-second pause. If retry also fails, the contact is written to `retry_YYYY-MM-DD.csv` and the batch continues.

**Pre-flight:** verifies every active contact has an existing Messages.app thread before any send. Halts if any are missing.

### delivery_report.py

Queries `chat.db` for delivery status ~60 seconds after a send run.

```bash
~/messages/.venv/bin/python3 ~/bin/delivery_report.py
```

Writes `~/messages/logs/delivery_YYYY-MM-DD.csv` with `is_delivered` and `is_read` per contact.

---

## Weekly Workflow

Type `/imessage-blast` in Claude Code. The skill guides you through:

1. Contacts check (flags missing service types)
2. Template review (confirm or stop to edit)
3. Dry-run preview
4. Confirmation and send
5. Delivery report after 60 seconds
6. Retry prompt if any failures

---

## Notes

- **Rate limiting:** 10-second delay between sends (~8 minutes for 50 contacts). The custom greeting on every message keeps content unique, which satisfies Apple's anti-spam requirements.
- **Delivery confirmation:** `is_delivered = 1` means the message reached the device. `is_read` is only available for iMessage contacts with "Send Read Receipts" enabled.
- **URLs in messages:** links appear as a generic card — rich link previews only generate when a human types and sends a URL manually in Messages.app. This is a Messages.app limitation, not a script bug.
- **RCS:** contacts detected as RCS are routed via the SMS service; Messages.app handles the protocol upgrade automatically.
- **Email vs phone:** some iMessage contacts are linked to their Apple ID email. Use the email in the `phone` column — the scripts detect the `@` and skip phone normalization.
- **Existing thread required:** `osascript` sends only work with contacts you've previously messaged. The pre-flight check enforces this.
