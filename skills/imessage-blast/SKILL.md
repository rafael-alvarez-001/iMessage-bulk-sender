---
name: imessage-blast
description: "Weekly iMessage/SMS bulk sender for teachers. Guides through the full workflow: service detection → CSV check → dry-run preview → confirm → send → delivery report. Use when the user says '/imessage-blast' or 'send my weekly messages'."
allowed-tools: Bash, Read, Edit
---

# iMessage Blast — Weekly Send Workflow

Orchestrates the full weekly messaging workflow for the teacher. Each step must complete before the next begins. Never skip steps or send without dry-run confirmation.

## Constants

```
VENV_PYTHON  = ~/messages/.venv/bin/python3
CONTACTS_CSV = ~/messages/contacts.csv
TEMPLATE     = ~/messages/message_template.txt
LOGS_DIR     = ~/messages/logs
SEND_PY      = ~/bin/send_messages.py
DETECT_PY    = ~/bin/detect_service.py
REPORT_PY    = ~/bin/delivery_report.py
```

---

## Step 1 — Check contacts.csv

Read `~/messages/contacts.csv` and report:
- Total active contacts (active = yes)
- Total inactive contacts (active = no)
- Any rows missing `service_type` (empty or blank)

If any active contacts are missing `service_type`, ask:
> "Some contacts are missing a service type. Run auto-detection now? (yes/no)"

If yes → run Step 2. If no → warn that sends may fail for those contacts and proceed to Step 3.

---

## Step 2 — Auto-detect service types (if needed)

Run:
```bash
~/messages/.venv/bin/python3 ~/bin/detect_service.py
```

Show the output. If any contacts show "No existing thread found", halt and tell the user:
> "These contacts have no existing Messages.app thread. Open Messages.app, send them a message manually to start a thread, then re-run /imessage-blast."

List the affected contacts. Do not proceed until resolved.

---

## Step 3 — Review message template

Read `~/messages/message_template.txt` and display its current contents to the user.

Ask:
> "Is this the message you want to send this week? (yes / no — I'll open the file for editing)"

If no → tell the user to edit `~/messages/message_template.txt`, then re-run `/imessage-blast` when ready. Stop here.

If yes → proceed to Step 4.

---

## Step 4 — Dry-run preview

Run:
```bash
~/messages/.venv/bin/python3 ~/bin/send_messages.py --dry-run
```

Show the full output including pre-flight result and all message previews.

If pre-flight fails → halt and tell the user which contacts are missing threads (same guidance as Step 2).

If pre-flight passes → ask:
> "Everything look correct? Ready to send to N contacts? (yes/no)"

If no → stop. Tell the user to edit contacts.csv or message_template.txt and re-run.

---

## Step 5 — Send

Run:
```bash
~/messages/.venv/bin/python3 ~/bin/send_messages.py
```

Stream and display the output in real time. Do not interrupt the process.

When complete, show the summary line (`Sent: N  Failed after retry: M`).

If M > 0 → show the full failure list from the output. Tell the user:
> "N messages sent. M failed after retry and have been saved to the retry log. We'll check delivery in 60 seconds — failed contacts can be re-sent after that."

---

## Step 6 — Delivery report

Wait 60 seconds after the send completes, then run:
```bash
~/messages/.venv/bin/python3 ~/bin/delivery_report.py
```

Show the output. Report delivered vs total.

If any contacts show `is_delivered = 0`:
> "These contacts haven't confirmed delivery yet. This can happen with SMS or if the device is offline. Check again in a few minutes by running: python3 ~/bin/delivery_report.py"

---

## Step 7 — Retry (if failures exist)

If the send produced a retry log (`~/messages/logs/retry_YYYY-MM-DD.csv`), ask:
> "Would you like to retry the failed contacts now? (yes/no)"

If yes → run:
```bash
~/messages/.venv/bin/python3 ~/bin/send_messages.py --csv ~/messages/logs/retry_$(date +%Y-%m-%d).csv
```

Show output. Then re-run the delivery report after 60 seconds.

If no → tell the user they can retry later by running:
```
python3 ~/bin/send_messages.py --csv ~/messages/logs/retry_YYYY-MM-DD.csv
```

---

## Done

Report the final summary:
- Messages sent successfully
- Delivery confirmation status
- Location of logs: `~/messages/logs/`

Tell the user they're done for the week.
