#!/bin/bash
# Church of Jesus Christ EMCOMM (Emergency Communications) — macOS / Linux installer
#
#   bash installer/install.sh            (from the extracted ChurchEMCOMM_Forms_v1.0.zip)
#
# Installs the same packages as install.ps1 on Windows:
#   [1] Field Volunteer (no amateur radio license)  — browser Worker Forms + Quick Reference Cards
#   [2] HAM Field Operator                          — + the Winlink templates (saved for a Windows machine or VM:
#                                                      Winlink Express itself runs only on Windows)
#   [3] EOC Operator (Satellite, Stake or Council / Area EOC) — + EOC Message Center, EOC server, drill simulator
#
# Everything but Winlink Express is Python 3 (standard library) and HTML, so the EOC server, the Message
# Center, the wall display, the phone page and the simulator run on macOS as they are. No admin rights,
# no internet, nothing installed outside your home folder. Independent volunteer project, not an official
# Church product.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"          # the package root (repo or extracted ZIP)
BASE="$HOME/Documents/Church of Jesus Christ EMCOMM"
DESK="$HOME/Desktop"

echo
echo "  THE CHURCH OF JESUS CHRIST of Latter-day Saints"
echo "  Church of Jesus Christ EMCOMM — installer v1.0 (macOS / Linux)"
echo "  --------------------------------------------------"
echo
echo "  Who is this computer for?"
echo "    [1] Field Volunteer (no amateur radio license): browser Worker Forms + Quick Reference Cards"
echo "    [2] HAM Field Operator: Worker Forms + Winlink templates (for your Windows Winlink machine) + cards"
echo "    [3] EOC Operator: everything, plus the EOC Message Center, EOC server and drill simulator"
echo
choice="${1:-}"
while [ "$choice" != "1" ] && [ "$choice" != "2" ] && [ "$choice" != "3" ]; do
  read -r -p "  Choose 1, 2 or 3: " choice
done
WORKER=1; WINLINK=0; EOC=0
[ "$choice" = "2" ] && WINLINK=1
[ "$choice" = "3" ] && { WINLINK=1; EOC=1; }

echo
echo "  Install location: $BASE"
# Rename from the short-lived name "Church EMCOMM" (installer of 2026-10-31.5) and the old EOC Desktop link names
OLD="Church EMCOMM"
if [ -d "$HOME/Documents/$OLD" ]; then
  # a new folder with no files in it (an EOC Server started first makes an empty Drop Folder) does not count
  if [ -d "$BASE" ] && [ -z "$(find "$BASE" -type f -print -quit)" ]; then rm -rf "$BASE"; fi
  if [ ! -e "$BASE" ]; then mv "$HOME/Documents/$OLD" "$BASE" && echo "  OK  Renamed Documents/$OLD -> Documents/Church of Jesus Christ EMCOMM"
  else cp -Rn "$HOME/Documents/$OLD/." "$BASE/" && echo "  !!  Copied missing files from Documents/$OLD; the old folder was kept, delete it when you have checked"; fi
fi
CFG="${XDG_CONFIG_HOME:-$HOME/.config}"
[ -d "$CFG/$OLD" ] && [ ! -e "$CFG/Church of Jesus Christ EMCOMM" ] && mv "$CFG/$OLD" "$CFG/Church of Jesus Christ EMCOMM"
for n in "$OLD Forms" "$OLD Quick Reference Cards" "$OLD Simulator.command" \
         "$OLD EOC Message Center.html" "$OLD EOC Server.command" "$OLD EOC Drop Folder" \
         "Church of Jesus Christ EOC Message Center.html" "Church of Jesus Christ EOC Server.command" "Church of Jesus Christ EOC Drop Folder"; do
  if [ -e "$DESK/$n" ] || [ -L "$DESK/$n" ]; then rm -rf "$DESK/$n" && echo "  OK  Removed old Desktop item: $n"; fi
done
mkdir -p "$BASE"

copy() {  # copy <src relative to package> <dest>
  if [ -f "$HERE/$1" ]; then mkdir -p "$(dirname "$2")"; cp -f "$HERE/$1" "$2"; echo "  OK  $(basename "$2")"; else echo "  !!  missing in this package: $1"; fi
}

# -- Read-me and the PACE (Primary, Alternate, Contingency, Emergency) plan, every role --
copy "README.md"          "$BASE/README.md"
copy "docs/PACE_PLAN.md"  "$BASE/PACE_PLAN.md"
copy "LICENSE"  "$BASE/LICENSE"

# -- Field Worker forms (every role) -----------------------------------------
echo
echo "  --> Field Worker forms"
W="$BASE/Field Worker Forms"
copy "templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Worker.html" "$W/Church_of_Jesus_Christ_Disaster_Report_Worker.html"
copy "templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Worker.html"       "$W/Church_of_Jesus_Christ_Supply_Order_Worker.html"
copy "templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log_Worker.html"     "$W/Church_of_Jesus_Christ_Work_Crew_Log_Worker.html"
copy "training/quick-ref-cards.html"                                                "$W/Quick_Reference_Cards.html"
if ls "$HERE"/training/pdf/Quick_Reference_Card*.pdf >/dev/null 2>&1; then
  mkdir -p "$W/Quick Reference Cards (PDF)"
  cp -f "$HERE"/training/pdf/Quick_Reference_Card*.pdf "$W/Quick Reference Cards (PDF)/" && echo "  OK  Quick Reference Cards (PDF)"
fi

# -- Winlink templates (HAM and EOC): Winlink Express is Windows-only --------
if [ "$WINLINK" = "1" ]; then
  echo
  echo "  --> Winlink templates"
  T="$BASE/Winlink Templates/Church of Jesus Christ EMCOMM Forms"
  for f in "templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Initial.html" "templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Viewer.html" "templates/disaster-report/Church of Jesus Christ Disaster Report.txt" \
           "templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Initial.html" "templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Viewer.html" "templates/supply-order/Church of Jesus Christ Supply Order.txt" \
           "templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log.html" "templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log_Viewer.html" "templates/work-crew-log/Church of Jesus Christ Work Crew Log.txt"; do
    copy "$f" "$T/$(basename "$f")"
  done
  if [ -d "$HERE/training/practice-forms" ]; then
    mkdir -p "$BASE/Winlink Templates/Church of Jesus Christ EMCOMM Practice"
    cp -f "$HERE"/training/practice-forms/* "$BASE/Winlink Templates/Church of Jesus Christ EMCOMM Practice/" && echo "  OK  Practice forms (pre-filled, THIS IS AN EXERCISE)"
    # training copy beside the other EMCOMM folders, so trainers find the forms and their README
    mkdir -p "$BASE/Training/Winlink Practice Forms"
    cp -f "$HERE"/training/practice-forms/* "$BASE/Training/Winlink Practice Forms/" && echo "  OK  Training/Winlink Practice Forms (same forms + README)"
  fi
  if [ -d "$HERE/training/scenario-samples" ]; then
    # retire the public sets an earlier release installed and this one no longer ships (same rule as install.ps1);
    # a private build someone copied in from a participant package says PRIVATE BUILD in its README and is never touched
    for pair in "$BASE/Winlink Templates|Church of Jesus Christ EMCOMM Training " "$BASE/Training|Winlink Training "; do
      parent="${pair%%|*}"; prefix="${pair#*|}"
      [ -d "$parent" ] || continue
      for old in "$parent/$prefix"*/; do
        [ -d "$old" ] || continue
        old="${old%/}"; code="${old##*/}"; code="${code#"$prefix"}"
        [ -d "$HERE/training/scenario-samples/$code" ] && continue
        rd="$old/README.txt"
        if [ -f "$rd" ] && head -n 1 "$rd" | grep -q '^Church of Jesus Christ EMCOMM Winlink training set' && ! grep -qF 'PRIVATE BUILD' "$rd"; then
          rm -rf "$old" && echo "  OK  Retired training set $code (no longer in this release): $old"
        fi
      done
    done
    # scenario training sets: the Church forms; the ICS 213RR forms are built on the Windows station by install.ps1
    for set in "$HERE"/training/scenario-samples/*/; do
      [ -d "$set" ] || continue
      code=$(basename "$set")
      TT="$BASE/Winlink Templates/Church of Jesus Christ EMCOMM Training $code"; TR="$BASE/Training/Winlink Training $code"
      # our own folders: empty them first, so a renumbered set leaves no stale message behind
      for d in "$TT" "$TR"; do [ -d "$d" ] && find "$d" -maxdepth 1 -type f -exec rm -f {} +; mkdir -p "$d"; done
      for f in "$set"*; do [ -f "$f" ] || continue; case "$f" in *.json) ;; *) cp -f "$f" "$TT/";; esac; done
      for f in "$set"*; do [ -f "$f" ] && cp -f "$f" "$TR/"; done
      echo "  OK  Training set $code (Church forms; ICS 213RR text in its README)"
    done
  fi
  echo "  !!  Winlink Express runs only on Windows. Copy the folder '$BASE/Winlink Templates' to that machine (or a Windows VM)"
  echo "      and put its two subfolders under  C:\RMS Express\Global Folders\Templates\ . Pat (the open-source Winlink client) is untested with these templates."
fi

# -- EOC package --------------------------------------------------------------
if [ "$EOC" = "1" ]; then
  echo
  echo "  --> EOC Message Center, server and simulator"
  E="$BASE/EOC Message Center"
  for f in EOC_Message_Center.html EOC_Wall_Display.html EOC_Phone.html eoc_server.py start_eoc_server.command start_eoc_server.bat; do copy "eoc/$f" "$E/$f"; done
  for f in sim_server.py engine.py orgpack.py privacy.py drillconfig.py community.py scenario_check.py index.html README.md start_simulator.command start_simulator.bat; do copy "simulation/$f" "$E/simulation/$f"; done
  # built-in scenarios: replace the folder's contents, so a scenario removed from the release does not linger
  mkdir -p "$E/simulation/scenarios"; rm -f "$E/simulation/scenarios/"*.json
  cp -f "$HERE"/simulation/scenarios/*.json "$E/simulation/scenarios/" && echo "  OK  simulation/scenarios"
  # the invented example community (Juniper Plains Area), same filter as the build scripts and install.ps1:
  # no Python cache, no drill runs, no local role choices
  if [ -d "$HERE/simulation/example" ]; then
    (cd "$HERE/simulation/example" && find . -type f ! -path '*__pycache__*' ! -path '*/simulation/runs/*' ! -path '*/simulation/local-roles.json' -print) |
    while IFS= read -r rel; do
      rel="${rel#./}"; mkdir -p "$(dirname "$E/simulation/example/$rel")"; cp -f "$HERE/simulation/example/$rel" "$E/simulation/example/$rel"
    done
    echo "  OK  simulation/example (invented example community)"
  fi
  # a copy of the volunteer web app as GitHub Pages serves it, to host on another https site if Pages cannot be
  # reached (the EOC server does not serve it: phones on the EOC Wi-Fi use http://<server-ip>:8080/m)
  if [ -f "$HERE/forms/index.html" ]; then
    P="$BASE/Web App (portal copy)"; rm -rf "$P"; mkdir -p "$P"
    cp -R "$HERE/forms" "$P/forms"
    for f in sw.js training/quick-ref-cards.html training/pdf/Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf \
             templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Worker.html \
             templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Worker.html \
             templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log_Worker.html; do
      [ -f "$HERE/$f" ] && mkdir -p "$(dirname "$P/$f")" && cp -f "$HERE/$f" "$P/$f"
    done
    echo "  OK  Web App (portal copy)"
  fi
  mkdir -p "$BASE/EOC Drop Folder"
  # Message Center launcher: the EOC server's page when the server runs on this computer (records shared with every
  # operator), else the standalone file (records kept in this browser only)
  cat > "$E/Open EOC Message Center.command" <<'LAUNCH'
#!/bin/bash
# Church of Jesus Christ EMCOMM: opens the EOC (Emergency Operations Center) Message Center.
# EOC server running on this computer: its page (records shared with every operator). Not running: the standalone file.
cd "$(dirname "$0")" || exit 1
PORT="${EOC_PORT:-8080}"
if curl -sf -m 2 -o /dev/null "http://127.0.0.1:$PORT/api/status"; then T="http://localhost:$PORT/"; else T="$PWD/EOC_Message_Center.html"; fi
if command -v open >/dev/null 2>&1; then open "$T"; else xdg-open "$T" >/dev/null 2>&1 & fi
LAUNCH
  chmod +x "$E/start_eoc_server.command" "$E/simulation/start_simulator.command" "$E/Open EOC Message Center.command" 2>/dev/null
  # Desktop shortcuts: symbolic links (Finder opens .command files in Terminal)
  if [ -d "$DESK" ]; then
    rm -f "$DESK/Church of Jesus Christ EMCOMM EOC Message Center.html"   # the old link straight to the standalone file
    ln -sfn "$E/Open EOC Message Center.command"      "$DESK/Church of Jesus Christ EMCOMM EOC Message Center.command"
    ln -sfn "$E/start_eoc_server.command"             "$DESK/Church of Jesus Christ EMCOMM EOC Server.command"
    ln -sfn "$E/simulation/start_simulator.command"   "$DESK/Church of Jesus Christ EMCOMM Simulator.command"
    ln -sfn "$BASE/EOC Drop Folder"                   "$DESK/Church of Jesus Christ EMCOMM EOC Drop Folder"
    echo "  OK  Desktop shortcuts: EOC Message Center, EOC Server, Church of Jesus Christ EMCOMM Simulator, EOC Drop Folder"
  fi
  if command -v python3 >/dev/null 2>&1; then echo "  OK  Python: $(python3 --version 2>&1)"; else echo "  !!  Python 3 not found: install it from https://www.python.org/downloads/macos/ for the EOC server and the simulator (the standalone Message Center works without it)"; fi
  echo
  echo "  macOS notes: the first time a .command file opens, macOS may ask you to allow it (System Settings → Privacy & Security)."
  echo "  Chrome or Safari both open the Message Center; the server pages are http://<this Mac's LAN IP>:8080 (wall: /wall, phones: /m)."
  echo "  The Drop Folder watcher and the USB backup work here too (USB: any volume that appears under /Volumes while the server runs)."
fi

# -- Field Worker shortcuts ---------------------------------------------------
if [ -d "$DESK" ]; then
  mkdir -p "$DESK/Church of Jesus Christ EMCOMM Forms"
  for f in "$W"/*.html; do ln -sfn "$f" "$DESK/Church of Jesus Christ EMCOMM Forms/$(basename "$f")"; done
  if [ -d "$W/Quick Reference Cards (PDF)" ]; then
    ln -sfn "$W/Quick Reference Cards (PDF)" "$DESK/Church of Jesus Christ EMCOMM Forms/Quick Reference Cards (PDF)"
    ln -sfn "$W/Quick Reference Cards (PDF)" "$DESK/Church of Jesus Christ EMCOMM Quick Reference Cards"
    echo "  OK  Desktop/Church of Jesus Christ EMCOMM Quick Reference Cards (one PDF per role)"
  fi
  echo "  OK  Desktop/Church of Jesus Christ EMCOMM Forms (links to the Worker forms and the cards)"
fi

echo
echo "  --------------------------------------------------"
echo "  Installed under: $BASE"
[ "$EOC" = "1" ] && echo "  Start the EOC server: double-click 'Church of Jesus Christ EMCOMM EOC Server.command' on the Desktop (or: bash \"$BASE/EOC Message Center/start_eoc_server.command\")"
echo "  Done."
