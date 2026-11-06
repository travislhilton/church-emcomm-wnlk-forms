# Continuation Prompt — Church of Jesus Christ EMCOMM Winlink Forms

> Paste the contents of this file as your first message when resuming work
> on this project in a new Claude Code session.

---

## Start here

- **Read [CLAUDE.md](CLAUDE.md) first** (standing rules, map, change routine, gotchas) and [CONTRIBUTING.md](CONTRIBUTING.md) for how to run and test. Every test and its last result is in [testing/TEST_CHECKLIST.md](testing/TEST_CHECKLIST.md).
- **This file is public.** Nothing about the maintainer's own community goes here. Private notes and the full history of earlier sessions are in `secure data/handoff/` on the maintainer's computers.
- **The repository is public** and started fresh on 2026-11-05. A clone from before that date must be deleted and cloned again.
- **Live release:** version 2026-11-05.1, tag `v1.0`. A release is the commit the tag names. The installer and Forms ZIP in `dist/`, the deck ZIP and the card PDFs are all release assets.

## Open work, in the order it is worth doing

1. **A session with people (N8).** Use the simulator's Session tab: Reset before the meeting, GO when the instructions are given, then the debrief for the room (`/debrief`). Open drills use Copper Creek Dam. Tune the scenario's `needs.defaults` from what the room can actually do.
2. **Winlink over the air** (two stations): B2–B9 with THIS IS AN EXERCISE ticked and a practice form. First close every old `localhost:8001` tab (B10). Then send the CCD-1 messages (N34) and a live ICS 213RR from a partner agency's station (N32).
3. **iPhone and Mac checks:** print from the app (L15, L18), offline app, Home and no-dead-ends taps (L11, L16, L17); `install.sh` on a Mac (N25).
4. **Machines:** EOC discovery between two separate computers with a Mac; a second Mac; Playwright on a Mac for the browser tests.
5. **Held:** the remaining outline scenarios (catalog in `docs/SIMULATOR_SCENARIOS.md`; write them with `docs/SCENARIO_AUTHORING.md` and check them with `simulation/scenario_check.py`).

## Machine notes

- Scratch servers for any EOC or simulator check: copy `eoc/` + `templates/` and `simulation/example/juniper-plains/` to a scratch folder. Set `LOCALAPPDATA`, `USERPROFILE` and `EMCOMM_DOCUMENTS` to scratch folders, or the scratch EOC watches the real Drop Folder. Start `eoc_server.py <port>` there and `sim_server.py <port> --data <scratch pack>`, send logs to files, and stop every scratch server by PID when done.
- Playwright: `chromium.launch(channel='chrome')`. Chrome via the Claude extension needs the LAN address `http://<LAN IP>:<port>`.
- Test suites, all at once: `python dev/check-dev-setup.py --tests`. Counts: acronyms 41, public files 5, example 43, sim 187, phone 70, training samples 50, WebKit 37.
- New scenarios: `python simulation/scenario_check.py <file> --pack <export>`. Drill specs: `python simulation/drillconfig.py --check`.
- Patch files with scripts written by the editor, not a Bash heredoc, and keep CRLF where a file has it.
