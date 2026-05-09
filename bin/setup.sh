#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

step()   { echo -e "\n${YELLOW}${BOLD}▶ $1${NC}"; }
ok()     { echo -e "${GREEN}✓ $1${NC}"; }
warn()   { echo -e "${YELLOW}⚠ $1${NC}"; }
fail()   { echo -e "${RED}✗ $1${NC}"; exit 1; }
pause()  { read -r -p "$1"; }

echo ""
echo -e "${BOLD}======================================"
echo   "  iMessage Bulk Sender — Setup"
echo -e "======================================${NC}"

# ── 1. macOS version ──────────────────────────────────────────────────────────
step "Checking macOS..."
OS_VERSION=$(sw_vers -productVersion)
echo "macOS $OS_VERSION"
ok "macOS detected"

# ── 2. Homebrew ───────────────────────────────────────────────────────────────
step "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    warn "Homebrew not found. Installing (this may take a few minutes)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || fail "Homebrew installation failed"
    # Add to PATH for Apple Silicon
    [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
    [[ -f /usr/local/bin/brew   ]] && eval "$(/usr/local/bin/brew shellenv)"
    ok "Homebrew installed"
else
    ok "Homebrew already installed ($(brew --version | head -1))"
fi

# ── 3. Python 3.11+ ───────────────────────────────────────────────────────────
step "Checking Python 3.11+..."
PYTHON_CMD=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 11 ]]; then
            PYTHON_CMD="$cmd"
            ok "Found $cmd ($VER)"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    warn "Python 3.11+ not found. Installing via Homebrew..."
    brew install python@3.11 || fail "Python installation failed"
    PYTHON_CMD=python3.11
    ok "Python 3.11 installed"
fi

# ── 4. Virtual environment + pip dependencies ─────────────────────────────────
step "Setting up Python virtual environment..."
mkdir -p ~/messages
"$PYTHON_CMD" -m venv ~/messages/.venv || fail "venv creation failed"
~/messages/.venv/bin/pip install --quiet --upgrade pip
~/messages/.venv/bin/pip install --quiet click phonenumbers || fail "pip install failed"
ok "venv created at ~/messages/.venv with click and phonenumbers"

# ── 5. Install scripts ────────────────────────────────────────────────────────
step "Installing scripts to ~/bin/..."
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p ~/bin
cp "$REPO_DIR/bin/send_messages.py" ~/bin/
cp "$REPO_DIR/bin/detect_service.py" ~/bin/
cp "$REPO_DIR/bin/delivery_report.py" ~/bin/
chmod +x ~/bin/send_messages.py ~/bin/detect_service.py ~/bin/delivery_report.py
ok "Scripts installed to ~/bin/"

step "Installing Claude Code skill..."
mkdir -p ~/.claude/skills/imessage-blast
cp "$REPO_DIR/skills/imessage-blast/SKILL.md" ~/.claude/skills/imessage-blast/
ok "Skill installed to ~/.claude/skills/imessage-blast/"

# ── 7. Directory structure ────────────────────────────────────────────────────
step "Creating directory structure..."
mkdir -p ~/messages/logs
ok "~/messages/logs/ ready"

# ── 8. contacts.csv ───────────────────────────────────────────────────────────
step "Checking contacts.csv..."
if [[ ! -f ~/messages/contacts.csv ]]; then
    printf 'first_name,last_name,phone,service_type,custom_greeting,active\n' > ~/messages/contacts.csv
    ok "~/messages/contacts.csv created (empty, ready to fill)"
else
    ok "~/messages/contacts.csv already exists — not overwritten"
fi

# ── 9. message_template.txt ───────────────────────────────────────────────────
step "Checking message_template.txt..."
if [[ ! -f ~/messages/message_template.txt ]]; then
    cat > ~/messages/message_template.txt <<'TMPL'
{greeting}

[Replace this line with your weekly message body. The greeting above is personalized per contact. This line goes to everyone.]
TMPL
    ok "~/messages/message_template.txt created"
else
    ok "~/messages/message_template.txt already exists — not overwritten"
fi

# ── 10. Permissions ───────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}======================================"
echo   "  Permission Setup (2 manual steps)"
echo -e "======================================${NC}"

echo ""
echo -e "${BOLD}STEP 1 of 2 — Full Disk Access${NC}"
echo "Required so the script can read your Messages delivery history."
echo ""
echo "  1. A System Settings window will open"
echo "  2. Click the lock icon and enter your Mac password"
echo "  3. Find 'Terminal' in the list and toggle it ON"
echo "     (If Terminal isn't listed, click '+' → /Applications/Utilities/Terminal.app)"
echo ""
pause "Press Enter to open Full Disk Access settings..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles" 2>/dev/null \
    || open "/System/Library/PreferencePanes/Security.prefPane" 2>/dev/null \
    || warn "Could not open System Settings automatically — go to: System Settings → Privacy & Security → Full Disk Access"
echo ""
pause "Toggle Terminal ON, then press Enter to continue..."

echo ""
echo -e "${BOLD}STEP 2 of 2 — Automation → Messages${NC}"
echo "Required so the script can send messages through Messages.app."
echo ""
echo "  1. A System Settings window will open"
echo "  2. Find 'Terminal' in the list"
echo "  3. Make sure 'Messages' is toggled ON underneath it"
echo ""
pause "Press Enter to open Automation settings..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation" 2>/dev/null \
    || open "/System/Library/PreferencePanes/Security.prefPane" 2>/dev/null \
    || warn "Could not open System Settings automatically — go to: System Settings → Privacy & Security → Automation"
echo ""
pause "Toggle Messages ON under Terminal, then press Enter to continue..."

# ── 9. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}======================================"
ok "Setup complete!"
echo -e "======================================${NC}"
echo ""
echo "What to do next:"
echo "  1. Edit ~/messages/contacts.csv — add your contacts"
echo "  2. Edit ~/messages/message_template.txt — write your weekly message"
echo "  3. Open Claude Code and run /imessage-blast to send"
echo ""
