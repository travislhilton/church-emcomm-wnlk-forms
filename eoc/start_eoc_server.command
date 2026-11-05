#!/bin/bash
# Church of Jesus Christ EMCOMM — EOC Server (macOS / Linux launcher; the Windows one is start_eoc_server.bat).
# Double-click in Finder (after install.sh made it executable) or run:  bash start_eoc_server.command
cd "$(dirname "$0")" || exit 1
echo
echo "  Church of Jesus Christ EMCOMM — EOC Server"
echo "  Looking for Python..."

# Python 3 (stdlib only): the python.org installer, Homebrew, or Xcode's command line tools all work.
# The python.org and Homebrew installs are tried first, by full path: a Finder double-click may not have
# them on PATH, and /usr/bin/python3 without the command line tools is only a placeholder that offers to install them.
PY=""
for c in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)' >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo
  echo "  ERROR: Python 3.7 or newer was not found."
  echo "  Install it BEFORE an emergency: the internet may be down when you need it."
  echo "  Run the Python installer from the EMCOMM USB kit, or download it from"
  echo "  https://www.python.org/downloads/macos/ (or run: xcode-select --install). Then run this again."
  echo "  Keep a copy of the Python installer on the USB kit."
  echo
  read -r -p "  Press Return to close " _
  exit 1
fi
echo "  Found Python: $($PY --version 2>&1)"

echo
echo "  Starting EOC server... (close this window to stop it)"
echo
"$PY" eoc_server.py "$@"
echo
read -r -p "  Server stopped. Press Return to close " _
