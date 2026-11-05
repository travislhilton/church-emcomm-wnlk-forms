#!/bin/bash
# Church of Jesus Christ EMCOMM — Drill Simulator (macOS / Linux launcher; the Windows one is start_simulator.bat).
# Keep the EOC Server window running too. Run:  bash start_simulator.command
cd "$(dirname "$0")" || exit 1
echo
echo "  Church of Jesus Christ EMCOMM — Drill Simulator (port 8090)"
echo "  Looking for Python..."

# Python 3 (stdlib only): the python.org installer, Homebrew, or Xcode's command line tools all work.
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)' >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo
  echo "  ERROR: Python 3.7 or newer was not found."
  echo "  Install it from https://www.python.org/downloads/macos/ (or: xcode-select --install), then run this again."
  echo
  read -r -p "  Press Return to close " _
  exit 1
fi
echo "  Found Python: $($PY --version 2>&1)"

echo
echo "  Starting the EMCOMM simulator (drill controller)... Keep the EOC Server window running too."
echo
"$PY" sim_server.py "$@"
echo
read -r -p "  Simulator stopped. Press Return to close " _
