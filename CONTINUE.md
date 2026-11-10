# Continuation Prompt — Church of Jesus Christ EMCOMM Winlink Forms

> Paste the contents of this file as your first message when resuming work
> on this project in a new Claude Code session.

---

## Start here

- **Read [CLAUDE.md](CLAUDE.md) first** (standing rules, map, change routine, gotchas) and [CONTRIBUTING.md](CONTRIBUTING.md) for how to run and test. Every test and its last result is in [testing/TEST_CHECKLIST.md](testing/TEST_CHECKLIST.md).
- **This file is public.** Nothing about the maintainer's own community goes here. Private notes and the full history of earlier sessions are in `secure data/handoff/` on the maintainer's computers.
- **The repository is public** and started fresh on 2026-11-05. A clone from before that date must be deleted and cloned again.
- **Live release:** version 2026-11-09.1, tag `v1.0`, released 2026-11-09 with Travis's OK. A release is the commit the tag names. The installer and Forms ZIP in `dist/`, the deck ZIP and the card PDFs are all release assets. If a Pages build sticks at `building`, ask for a rebuild: `gh api -X POST repos/travislhilton/church-emcomm-wnlk-forms/pages/builds`.
- **In 2026-11-09.1:** everything of 2026-11-07.1 (the simulator's Setup a new person can follow; a folder browser for every folder the Message Center asks for) and, at Travis's request, **no EMCOMM files in OneDrive**: when Documents syncs to the cloud, the installer uses `C:\Church of Jesus Christ EMCOMM`, moves an earlier install there (skipping SQLite's `*.db-shm`, deleting the old folder only when every file arrived), and the server's Drop Folder follows the install folder (checklist A14). An unsynced Documents still gets the install.
- **Three levels** (Travis, 2026-11-06): any browser on any device; one Windows host laptop per EOC for the server and the simulator; the Windows Winlink station. "If the platform can't run Winlink (Windows only) then it can't host." A Mac is a development machine only.
- **Contingency Winlink steps** (`docs/PACE_PLAN.md` §5): RMS Gateway; held at the gateway (RMS Relay *Hold for Internet access*, set by its sysop); the local VARA FM RMS Post Office; VARA FM P2P; then, once VARA FM has failed in every mode, a Winlink Message over VARA HF, by hand, only what must go. No Winlink Radio-only sessions. Voice to the Council / Area EOC is VHF/UHF first, HF only if that fails.

## Incident read-out (merged into `main` as pull request #1, not released)

- **Incident read-out for a voice net** (2026-11-10, version 2026-11-10.1): `eoc/readout.py` builds an `emcomm-readout/1` document from the active event (the SITREP's own totals, ported from `buildSitrep()`; facts only, never injuries, deaths, missionary status, names, phones, emails, addresses or GPS; null where nothing was reported). `GET /api/readout` returns it; `readout-latest.json` beside the server is rewritten on that call and whenever a SITREP is generated (the page's save of a new `lastSitrepTs`). The contract is the station project's, copied unchanged into `docs/contracts/emcomm-readout/`: change it there first, never here alone. README *Incident read-out for a voice net*; checklist F32 (passed on a Mac, 51/51 with Chromium parity) and F33 (open).
- **Choices to confirm with Travis:** an exercise is any report marked THIS IS AN EXERCISE or a drill simulator feeding the EOC (the app has no event-level exercise flag; the wall shows EXERCISE only when every report is marked); expected units come from the event's Roster, else *Units covered* on Setup, else null; needs lists name each unit once; a report with no unit is "unit not named".
- **Windows checks done** (2026-11-10, on the VM): the release rebuilt on Windows (PowerShell syntax check passed; the BAT byte-identical to the Mac build, the ZIP the same files and timestamps); role 3 installs `readout.py`; F33 passed (the document reached W9TLH-7 over the LAN, Generate SITREP rewrites `readout-latest.json`, a reader holding it open on NTFS gets a logged skip and the next SITREP writes it); every suite on Python 3.8 and 3.14. `test_readout.py` falls back to the installed Chrome when Playwright's Chromium is not downloaded, and `dev/check-dev-setup.py` no longer crashes printing a failure to a cp1252 console or file. On a Mac `test_training_samples.py` leaves its Winlink `.mime` files in the working directory (no Winlink folder, so the drill folder is empty): delete them, never commit them.
- **Release 2026-11-10.1 only with Travis's OK.** W9TLH-7 already runs it (installed from `main` on 2026-11-10 with Travis's OK).
- **The VM's own install** (`C:\Mac\Home\Documents`, a Parallels shared folder) does not enforce Windows share modes: test file locking on a local NTFS folder, never there.

## Do this first

1. **Ask Travis whether to release 2026-11-10.1** (the incident read-out), and to confirm the two read-out choices above.
2. **W9TLH-7** runs 2026-11-10.1 from `C:\Church of Jesus Christ EMCOMM`; its EOC server and simulator are running, and Travis set up the simulator's organization pack on 2026-11-10 (details in `secure data/handoff/machines.md`). Before a drill there: choose the scenario, start a DRILL event in the Message Center, point the Map data folder at the pack. A locked, stale `eoc_data.db-shm` stayed in the old OneDrive folder: delete that folder once Windows lets go of it.
3. **The station side of the read-out** is in the sibling repository `ham-net-speech-to-text` (its `contracts/emcomm-readout/` is the source of the contract; the copy here must stay identical, line endings aside).

## Decisions waiting for Travis

- **Comms Sheet structured fields:** a *Use* column on the gateways table (RMS Gateway, VARA FM RMS Post Office, VARA FM P2P, VARA HF), a *Holds mail when internet is down* column, and the P2P frequency on the sheet and the wall. Asked on 2026-11-07, not answered.

## Open work, in the order it is worth doing

The checklist's *Still open* section lists every row that still needs a person or a device; 50 rows do, nearly all of them below.

1. **A session with people (N8).** Use the simulator's Session tab: Reset before the meeting, GO when the instructions are given, then the debrief for the room (`/debrief`, P19). Open drills use Copper Creek Dam. Tune the scenario's `needs.defaults` from what the room can actually do. Hand out cards 9 and 10 (P23).
2. **Winlink over the air** (two stations): B2–B9 with THIS IS AN EXERCISE ticked and a practice form, then every Contingency step in `docs/PACE_PLAN.md` §5 (B11). Ask the sysops of the local gateways which RMS Relay mode they run, and agree the local VARA FM RMS Post Office. First close every old `localhost:8001` tab (B10). Then F7, the CCD-1 messages (N34) and a live ICS 213RR from a partner agency's station (N32).
3. **PACE and roll-up drills:** I1–I7 at every level, then the live Satellite → Stake → Area roll-up (J4). EOC discovery between two real computers already works (P46: W9TLH-3 saw W9TLH-7).
4. **Phone and other device checks:** the EMCOMM EOC icon on a real iPhone (P44); a real Android device (P40); a Mac, Linux computer or Chromebook joining by browser (P41); iPhone GPS and Share (C7, C8, C10); Send to EOC, the offline app and the camera scan (L3, L8, L9, L11, L12); print from the app (L15, L18); Home and no-dead-ends taps (L16, L17). L11 failed on 2026-10-31 and was fixed in the WebKit test (L14), so the iPhone repeat is still owed.
5. **Other real-device checks:** a synced folder drop (E5), the USB backup (G2), a laptop hotspot with no internet (P4), a duplex print of the cards (P24), the wall on a TV (F27).
6. **An install test in the repository.** The role 3 install checks (installed files equal the repository; the installed EOC server and simulator start, serve every page, file an uploaded report, load the example pack) have so far been a scratch script outside the repository, and a corrupted character once stopped it from running without anyone noticing (corrected in the checklist, 2026-11-07). Make it `testing/test_install.py`, with a check that it ran.
7. **Test timing:** `test_phone_api.py` has stopped three times on WinError 10053 and `test_browsers.py` timed out once; each passed on rerun. Find the request before trusting a single failing run.
8. **Held:** the remaining outline scenarios (catalog in `docs/SIMULATOR_SCENARIOS.md`; write them with `docs/SCENARIO_AUTHORING.md` and check them with `simulation/scenario_check.py`).

## Machine notes

- **SSH to W9TLH-7 works** (2026-11-09): `ssh w9tlh-7` from this VM, passwordless. The account name, paths and the scripts that set it up are in `secure data/handoff/machines.md`, which stays private. Its login shell is PowerShell: send PowerShell, never `&`.
- **The Mac Studio's clone:** replace it, because it holds the old history. The steps are in Travis's Google Drive, *Mac Studio - replace EMCOMM clone commands.txt*.
- Scratch servers for any EOC or simulator check: copy `eoc/` + `templates/` and `simulation/example/juniper-plains/` to a scratch folder. Set `LOCALAPPDATA`, `USERPROFILE` and `EMCOMM_DOCUMENTS` to scratch folders, or the scratch EOC watches the real Drop Folder. Start `eoc_server.py <port>` there and `sim_server.py <port> --data <scratch pack>`, send logs to files, and stop every scratch server by PID when done.
- Playwright: `chromium.launch(channel='chrome')`, plus Firefox and WebKit for `test_browsers.py`. On this VM WebKit lays a tablet out at 656 px (a scaled display), which is stricter, not wrong. A test that clicks must click like a person: two clicks 150 ms apart for a double-click.
- Test suites, all at once: `python dev/check-dev-setup.py --tests`. Counts: acronyms 41, public files 5, example 45, sim 190, phone 77, read-out 51, training samples 50, WebKit 37, browsers 213.
- New scenarios: `python simulation/scenario_check.py <file> --pack <export>`. Drill specs: `python simulation/drillconfig.py --check`.
- Patch files with scripts written by the editor, not a Bash heredoc, and keep CRLF where a file has it. In Python, write Windows paths as raw strings (`r'C:\Users'`): `\U` is an escape.
