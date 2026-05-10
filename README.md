# iMessage Bulk Sender

Sends personalized iMessage/SMS messages to 50+ contacts weekly from a Mac, via a single Claude Code skill invocation. No Terminal knowledge required after initial setup.

**Repo:** https://github.com/rafael-alvarez-001/iMessage-bulk-sender

---

## Requirements

- macOS Tahoe (16) or later
- Claude Code installed
- Terminal granted **Full Disk Access** and **Automation → Messages** (setup script handles this)

---

## Onboarding & Installation

Follow these steps on a fresh machine. You only do this once.

### Step 1 — Clone the repo

```bash
git clone https://github.com/rafael-alvarez-001/iMessage-bulk-sender.git
cd iMessage-bulk-sender
```

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

### Step 3 — Add your contacts

Open `~/messages/contacts.csv` in Numbers or Excel and fill in your contacts:

```
first_name,last_name,phone,service_type,custom_greeting,active
Jane,Smith,+15551234567,,Hi Jane! Hope you're well —,yes
Bob,Jones,bob@example.com,,Hey Bob! Quick update —,yes
```

Leave `service_type` blank — it will be auto-detected in the next step.

> **Phone or email?** Some iMessage contacts are linked to their Apple ID email rather than their phone number. Use the email address in the `phone` column for those contacts — the scripts detect the `@` and handle it automatically.

### Step 4 — Auto-detect service types

```bash
~/messages/.venv/bin/python3 ~/bin/detect_service.py
```

This fills in the `service_type` column (`imessage` / `sms` / `rcs`) for each contact by checking your Messages.app history. Re-run whenever you add contacts or someone switches between iPhone and Android.

> **Requires an existing thread:** detection only works for contacts you've already messaged. If a contact has no prior thread, open Messages.app, send them a message manually to start one, then re-run.

### Step 5 — Write your first message

Edit `~/messages/message_template.txt`:

```
{greeting}

This week's update: [your message here]
```

`{greeting}` is replaced per contact with their `custom_greeting` value from the CSV. Everything else is the same for everyone.

### Step 6 — Test the installation

See the **Efficacy Tests** section below before sending to real contacts.

---

## Efficacy Tests

Run these after installation to confirm everything is working.

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

After a multi-contact send, verify the 10-second delay between sends:

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
| `phone` | Phone number (any US format) or email address for Apple ID iMessage contacts |
| `service_type` | `imessage`, `sms`, or `rcs` — auto-detected by `detect_service.py` |
| `custom_greeting` | Per-contact greeting used as `{greeting}` in template |
| `active` | `yes` to include in sends, `no` to skip without deleting the row |

---

## message_template.txt Format

```
{greeting}

This week's update: [your message here]
```

Available placeholders: `{greeting}`, `{first_name}`, `{last_name}`. Everything else is sent as-is to every contact. Edit this file before each weekly run.

---

## Scripts

### detect_service.py

Auto-populates `service_type` in `contacts.csv` by querying `chat.db`. Run once after adding contacts, and again when contacts switch devices.

```bash
~/messages/.venv/bin/python3 ~/bin/detect_service.py

# Custom CSV path
~/messages/.venv/bin/python3 ~/bin/detect_service.py --csv ~/messages/contacts.csv
```

### send_messages.py

Sends personalized messages to all active contacts. Runs a pre-flight check first to confirm every contact has an existing Messages.app thread.

```bash
# Preview without sending
~/messages/.venv/bin/python3 ~/bin/send_messages.py --dry-run

# Send
~/messages/.venv/bin/python3 ~/bin/send_messages.py

# Retry failed contacts from a previous run
~/messages/.venv/bin/python3 ~/bin/send_messages.py --csv ~/messages/logs/retry_YYYY-MM-DD.csv

# Options
--csv PATH          contacts CSV (default: ~/messages/contacts.csv)
--template PATH     message template (default: ~/messages/message_template.txt)
--dry-run           preview only, no sends
--delay INT         seconds between sends (default: 10)
```

**Pre-flight:** verifies every active contact has an existing Messages.app thread before any send. Halts if any are missing.

**Retry behavior:** failed sends are automatically retried once after a 15-second pause. If the retry also fails, the contact is written to `retry_YYYY-MM-DD.csv` and the batch continues. A consolidated failure list is printed at the end.

### delivery_report.py

Queries `chat.db` for delivery status. Run ~60 seconds after sending to allow delivery signals to propagate.

```bash
~/messages/.venv/bin/python3 ~/bin/delivery_report.py

# Against a specific send log
~/messages/.venv/bin/python3 ~/bin/delivery_report.py --send-log ~/messages/logs/send_YYYY-MM-DD.csv
```

Writes `~/messages/logs/delivery_YYYY-MM-DD.csv` with `is_delivered` and `is_read` per contact.

---

## Weekly Workflow

Type `/imessage-blast` in Claude Code. The skill guides you through:

1. Contacts check — flags missing service types, offers to run auto-detection
2. Template review — shows current template, stops if you want to edit it
3. Dry-run preview — shows exactly what will be sent, requires confirmation
4. Send — sends to all active contacts with 10-second delays between each
5. Delivery report — runs automatically 60 seconds after send completes
6. Retry — if any failed, retries once and reports final status

---

## Notes

- **Rate limiting:** 10-second delay between sends (~8 minutes for 50 contacts). The custom greeting per contact keeps message content unique, satisfying Apple's anti-spam requirements.
- **Delivery confirmation:** `is_delivered = 1` means the message reached the device. `is_read` is only available for iMessage contacts who have "Send Read Receipts" enabled — SMS contacts never show `is_read`.
- **URLs in messages:** links appear with a generic card preview, not a rich thumbnail. Rich previews only generate when a human types and sends a URL manually in Messages.app. This is a Messages.app limitation, not a script bug.
- **RCS:** contacts detected as RCS are routed via the SMS service; Messages.app handles the protocol upgrade automatically.
- **Email vs phone:** some iMessage contacts are stored in Messages.app by Apple ID email rather than phone number. Use the email in the `phone` column — the `@` triggers automatic detection and skips phone normalization.
- **Existing thread required:** `osascript` sends only work reliably with contacts you've previously messaged. The pre-flight check enforces this before any messages are sent.
- **Python environment:** scripts use a dedicated virtual environment at `~/messages/.venv` to avoid conflicts with macOS's system-managed Python. Do not run scripts with `python3` directly — use `~/messages/.venv/bin/python3`.
