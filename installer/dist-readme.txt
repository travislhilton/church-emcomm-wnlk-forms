Church of Jesus Christ EMCOMM
============================================
Version: {VERSION}

An independent volunteer project by amateur radio operators supporting Church
emergency communications. Not an official product of The Church of Jesus
Christ of Latter-day Saints.

QUICK INSTALL
-------------
1. Open the "installer" folder in this ZIP
2. Double-click install.bat
3. Choose your role:
   [1] Field Volunteer (no HAM license)
   [2] HAM (amateur radio) Field Operator
   [3] EOC (Emergency Operations Center) Operator: Satellite, Stake or Council / Area EOC

No internet required. No admin rights required.
Installs to: Documents\Church of Jesus Christ EMCOMM\  (with README.md and PACE_PLAN.md, the PACE (Primary, Alternate, Contingency, Emergency) plan)
  (C:\Church of Jesus Christ EMCOMM\ when Documents syncs to OneDrive)

AFTER INSTALLING: FIELD VOLUNTEER ([1])
---------------------------------------
1. Open a form from the "Church of Jesus Christ EMCOMM Forms" folder on the Desktop.
2. Print Card 1 (Helping Hands Volunteer): desktop shortcut
   "Church of Jesus Christ EMCOMM Quick Reference Cards".
3. On a phone, nothing installs from here. Open the portal and add it to the home screen:
   https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/

AFTER INSTALLING: HAM OPERATOR ([2])
------------------------------------
1. Restart Winlink Express.
2. New Message -> Select Template -> Global Templates -> Church of Jesus Christ EMCOMM Forms.
3. To practice: Global Templates -> Church of Jesus Christ EMCOMM Practice.
4. Winlink Express not installed yet? Install it, then run this installer again.
5. Print Card 2 (EMCOMM HAM Operator).

AFTER INSTALLING: EOC LAPTOP ([3])
----------------------------------
1. Double-click "Church of Jesus Christ EMCOMM EOC Server" on the Desktop.
   A black window opens. Keep it open: closing it stops the EOC.
2. The first time, Windows asks whether Python may use the network.
   Tick "Private networks" and press Allow. If it was refused, the server
   window says so and shows the three steps that fix it.
3. Double-click "Church of Jesus Christ EMCOMM EOC Message Center".
   Its Overview tab shows a "Set up this EOC" checklist. Work down it; each step
   has a Go button: name this EOC, open the event, set the PACE (Primary,
   Alternate, Contingency, Emergency) level and the SITREP (situation report)
   interval, choose the Winlink callsign (step 1 the folder, normally
   C:\RMS Express; step 2 tick the callsign), fill the roster, load the Comms Sheet.
4. Other operators, phones and the TV open the addresses the server window shows.
5. Read Card 3 (EOC Operator) and the card for your level: 6 Satellite, 7 Stake Center,
   8 Council / Area. They are under the desktop shortcut
   "Church of Jesus Christ EMCOMM Quick Reference Cards".
   For a drill: the Simulator shortcut, Card 5 (Drill Controller) and Card 9 (Your First Drill).
Run the installer again at any time to update: reports and settings are kept.

WHAT GETS INSTALLED
-------------------
[1] Field Volunteer:
  - 3 Worker Forms (Disaster Report, Supply Order, Work Crew Log)
  - Quick Reference Cards (web page) and the printable PDFs (Portable Document Format) -- one PDF per
    role, US Letter (8.5 x 11 in), front and back on one sheet: print
    double-sided, "flip on long edge", at any printer or print shop
  - Desktop shortcuts in "Church of Jesus Christ EMCOMM Forms" folder

[2] HAM Field Operator -- everything in [1] plus:
  - Winlink Express templates (3 .txt definitions + entry forms + viewer forms) installed to:
    C:\RMS Express\Global Folders\Templates\Church of Jesus Christ EMCOMM Forms\
    (saved under the install folder if Winlink is not yet installed)
    Restart Winlink Express, then: New Message -> Select Template -> Global Templates
  - Practice forms: 7 pre-filled copies (THIS IS AN EXERCISE ticked) from the
    simulator's Copper Creek Dam scenario, invented Larkspur Stake data, installed to:
    C:\RMS Express\Global Folders\Templates\Church of Jesus Christ EMCOMM Practice\
    A received Church form message opens as the form in the browser (viewer);
    the message text carries the same report for anyone reading it as email.

[3] EOC Operator (Satellite, Stake or Council / Area EOC) -- everything in [2] plus:
  - EOC (Emergency Operations Center) Message Center (opens in any browser)
    Same software at a Satellite EOC (ward building), the Stake Center EOC and
    a Council / Area EOC; each one rolls its records up to the EOC above it
  - EOC network server for multi-operator mode (needs Python 3)
  - EOC Wall Display: read-only big board for a TV / projector in the EOC,
    served by the server at http://<server-ip>:8080/wall (press F = full screen)
  - EOC Drop Folder for reports received by email, text, or USB (Universal Serial Bus) drive, and for
    roll-up .json files from a Satellite or Stake EOC
  - Church of Jesus Christ EMCOMM Simulator for drills (one per EOC laptop): plays a scenario against the
    running EOC server; installed under EOC Message Center\simulation\ with
    start_simulator.bat (port 8090). The organization pack is loaded on its Setup
    tab from the Church directory export and never leaves the laptop. To try it with no
    export, load the invented example: EOC Message Center\simulation\example\juniper-plains\
  - A copy of the volunteer web app (Web App (portal copy)\), to host on another https
    site if GitHub Pages cannot be reached
  - Desktop shortcuts: "Church of Jesus Christ EMCOMM EOC Message Center" (opens the
    EOC Server's page when the server runs on that laptop, else the standalone file),
    "Church of Jesus Christ EMCOMM EOC Server", "Church of Jesus Christ EMCOMM EOC Drop Folder",
    "Church of Jesus Christ EMCOMM Simulator"

DEPENDENCIES
------------
- Google Chrome or Microsoft Edge  (required; if neither is found, the installer offers to open the download page)
- Winlink Express  ([2] and [3]; if it is missing, the installer offers to open the download page.
  Install it, then run this installer again so the templates go into Winlink.)
  Download: https://downloads.winlink.org/User%20Programs/
- Python 3.8 or later  ([3] networked server mode and simulator only). Install it from
  https://www.python.org/downloads/ before it is needed ("Add python.exe to PATH") and keep
  the Python installer on the USB kit with this package.

TROUBLESHOOTING
---------------
Mac, Linux, Chromebook, Android, iPhone: nothing to install. Use the portal in any browser.
    Only a Windows computer can host the EOC server or the simulator, or run Winlink Express.

If Windows blocks install.bat after downloading from the internet:
  Right-click this ZIP file -> Properties -> Unblock -> OK
  Then re-extract and run installer\install.bat again.

If PowerShell says scripts are disabled:
  Right-click install.ps1 -> Run with PowerShell
  Or open PowerShell and run:
    powershell -ExecutionPolicy Bypass -File installer\install.ps1

FILES IN THIS PACKAGE
---------------------
installer\install.bat           -- Double-click to start
installer\install.ps1           -- Installer script
templates\disaster-report\      -- Disaster Report (Winlink .txt + HTML (web page) template, Worker form)
templates\supply-order\         -- Supply Order (Winlink .txt + HTML template, Worker form)
templates\work-crew-log\        -- Work Crew Log (Winlink .txt + HTML template, Worker form)
eoc\                            -- EOC Message Center, server, and launcher (Satellite, Stake or Council / Area EOC)
simulation\                     -- EMCOMM drill simulator (sim_server.py, start_simulator.bat, scenarios\)
training\                       -- Quick Reference Cards (web page)
training\pdf\                   -- Quick Reference Card PDFs (Letter, double-sided; one per role + all-in-one)
training\practice-forms\        -- 7 pre-filled Winlink practice forms (THIS IS AN EXERCISE) and their README
training\scenario-samples\      -- Scenario training sets (CCD-1: Copper Creek Dam, invented Larkspur Stake)
simulation\example\             -- The invented Juniper Plains Area, for drills without a directory export
forms\, sw.js                   -- The volunteer web app as GitHub Pages serves it (portal, comms page, icons)
README.md                       -- What the system is and how it fits together
docs\PACE_PLAN.md               -- The PACE (Primary, Alternate, Contingency, Emergency) communications plan

LICENSE
-------
MIT License: see the LICENSE file. forms\vendor\jsQR.js keeps its own Apache-2.0 license.
Independent volunteer project, not an official Church product.

SUPPORT
-------
Contact your stake Welfare and Self-Reliance Specialist (emergency communications)
or your Emergency Response Director.
Report a problem: https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new/choose
