# Continuation Prompt — Church of Jesus Christ EMCOMM Winlink Forms

> Paste the contents of this file as your first message when resuming work
> on this project in a new Claude Code session.

---

## Start here

- **Read [CLAUDE.md](CLAUDE.md) first** (standing rules, map, change routine, gotchas) and [CONTRIBUTING.md](CONTRIBUTING.md) for how to run and test. Every test and its last result is in [testing/TEST_CHECKLIST.md](testing/TEST_CHECKLIST.md).
- **This file is public.** Nothing about the maintainer's own community goes here. Private notes and the full history of earlier sessions are in `secure data/handoff/` on the maintainer's computers.
- **The repository is public** and started fresh on 2026-11-05. A clone from before that date must be deleted and cloned again.
- **Live release:** version 2026-11-06.3, tag `v1.0`, released 2026-11-06. A release is the commit the tag names. The installer and Forms ZIP in `dist/`, the deck ZIP and the card PDFs are all release assets. If a Pages build sticks at `building`, ask for a rebuild: `gh api -X POST repos/travislhilton/church-emcomm-wnlk-forms/pages/builds`.
- **Three levels** (Travis, 2026-11-06): any browser on any device; one Windows host laptop per EOC for the server and the simulator; the Windows Winlink station. "If the platform can't run Winlink (Windows only) then it can't host." A Mac is a development machine only; no Mac installer or launcher ships.
- **The Mac Studio's clone:** replace it, because it holds the old history. The steps are in Travis's Google Drive, *Mac Studio - replace EMCOMM clone commands.txt*.

- **Decided 2026-11-07:** VARA HF stays last: once VARA FM has failed in every mode, the HAM sends a Winlink Message over VARA HF.
- **Decision for Travis:** should Winlink's Vara FM Radio-only session join the steps? It needs a Message Pickup Station registered before an outage.

## Open work, in the order it is worth doing

The checklist's *Still open* section lists every row that still needs a person or a device; 50 rows do, nearly all of them below.

1. **A session with people (N8).** Use the simulator's Session tab: Reset before the meeting, GO when the instructions are given, then the debrief for the room (`/debrief`, P19). Open drills use Copper Creek Dam. Tune the scenario's `needs.defaults` from what the room can actually do. Hand out cards 9 and 10 (P23).
2. **Winlink over the air** (two stations): B2–B9 with THIS IS AN EXERCISE ticked and a practice form, then every Contingency step in `docs/PACE_PLAN.md` §5 (B11). Ask the sysops of the local gateways which RMS Relay mode they run, and agree the local VARA FM RMS Post Office. First close every old `localhost:8001` tab (B10). Then F7, the CCD-1 messages (N34) and a live ICS 213RR from a partner agency's station (N32).
3. **PACE and roll-up drills:** I1–I7 at every level, then the live Satellite → Stake → Area roll-up (J4).
4. **Phone and other device checks:** the EMCOMM EOC icon on a real iPhone (P44); a real Android device (P40); a Mac, Linux computer or Chromebook joining by browser (P41); iPhone GPS and Share (C7, C8, C10); Send to EOC, the offline app and the camera scan (L3, L8, L9, L11, L12); print from the app (L15, L18); Home and no-dead-ends taps (L16, L17). L11 failed on 2026-10-31 and was fixed in the WebKit test (L14), so the iPhone repeat is still owed.
5. **Other real-device checks:** a synced folder drop (E5), the USB backup (G2), a laptop hotspot with no internet (P4), a duplex print of the cards (P24), the wall on a TV (F27).
6. **Held:** the remaining outline scenarios (catalog in `docs/SIMULATOR_SCENARIOS.md`; write them with `docs/SCENARIO_AUTHORING.md` and check them with `simulation/scenario_check.py`).

## Machine notes

- Scratch servers for any EOC or simulator check: copy `eoc/` + `templates/` and `simulation/example/juniper-plains/` to a scratch folder. Set `LOCALAPPDATA`, `USERPROFILE` and `EMCOMM_DOCUMENTS` to scratch folders, or the scratch EOC watches the real Drop Folder. Start `eoc_server.py <port>` there and `sim_server.py <port> --data <scratch pack>`, send logs to files, and stop every scratch server by PID when done.
- Playwright: `chromium.launch(channel='chrome')`. Chrome via the Claude extension needs the LAN address `http://<LAN IP>:<port>`.
- Test suites, all at once: `python dev/check-dev-setup.py --tests`. Counts: acronyms 41, public files 5, example 45, sim 190, phone 74, training samples 50, WebKit 37, browsers 186.
- New scenarios: `python simulation/scenario_check.py <file> --pack <export>`. Drill specs: `python simulation/drillconfig.py --check`.
- Patch files with scripts written by the editor, not a Bash heredoc, and keep CRLF where a file has it.
