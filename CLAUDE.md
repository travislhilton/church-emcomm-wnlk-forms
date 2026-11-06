# CLAUDE.md — standing rules for this repository

Claude Code reads this file at the start of every session. Human contributors should read it too:
the rules are the project's, not Claude's. How to set up and work with the project is in
[CONTRIBUTING.md](CONTRIBUTING.md); the running handoff (what is in progress, last sessions,
open tests) is [CONTINUE.md](CONTINUE.md); every test and its last result is
[testing/TEST_CHECKLIST.md](testing/TEST_CHECKLIST.md).

## What this is

Winlink Express HTML forms and an EOC (Emergency Operations Center) Message Center for
emergency communications (EMCOMM) in stakes of The Church of Jesus Christ of Latter-day Saints.
Volunteers fill three Church forms on a phone; HAM (amateur radio) operators send them by Winlink;
EOCs collect them, produce the SITREP (situation report) and roll everything up:
**field → Satellite EOC → Stake EOC → the two lines above the stake**: the coordinating council (Area Seventy, decisions) and the welfare line (local Welfare and Self-Reliance Manager, WSRM, then the AWSRM, Area Welfare and Self-Reliance Manager: supplies, approvals, reporting). A **Council / Area EOC** exists only when the council or the welfare region opens one; there is no standing "Area EOC" (organization analysis F1, 2026-10-30).
Communication paths follow the **PACE** plan ([docs/PACE_PLAN.md](docs/PACE_PLAN.md)):
Primary = cellular, Alternate = any surviving internet anywhere, Contingency = radio
(Winlink VHF/UHF **VARA FM**, then VARA HF; voice on FRS/GMRS and the stake net),
Emergency = runner with paper.

It is an **independent volunteer project, not an official Church product**, created by
Travis Hilton (W9TLH). Every overview surface (README, portal, cards, deck cover, release notes)
must carry that disclaimer.

## Map

| Path | What |
|---|---|
| `templates/<form>/` | Per form: Winlink **Initial** template, generated **Viewer**, phone **Worker** form, and the `.txt` template definition (CRLF). Forms: `disaster-report`, `supply-order`, `work-crew-log` |
| `templates/_shared/emcomm-app.js` | **Single source** of the Church of Jesus Christ EMCOMM app module (Outbox, Send to EOC, QR scan, hand-off, offline app). Inlined into the Worker forms and `forms/index.html` by `installer/sync-app-module.py` |
| `forms/` | GitHub Pages volunteer portal (= the installable Church of Jesus Christ EMCOMM web app): `index.html`, `comms.html`, `manifest.webmanifest`, `icons/`, `vendor/jsQR.js` (Apache-2.0, see `vendor/jsQR-LICENSE.txt`) |
| `sw.js` | Service worker for the offline app (scope = repo root on GitHub Pages) |
| `eoc/` | `eoc_server.py` (Python stdlib only, SQLite), `EOC_Message_Center.html`, `EOC_Wall_Display.html` (`/wall`), `EOC_Phone.html` (`/m`, `/receive`) |
| `installer/` | `install.ps1` / `install.bat`, `build-release.py` (one-file BAT and ZIP, on any machine; `dist-readme.txt` is the ZIP's read-me), `make-viewers.py`, `sync-app-module.py`, `build-deck-zip.py` |
| `training/` | Quick reference cards (`quick-ref-cards.html` → `build-quick-ref-pdfs.py` → `pdf/`); practice forms; scenario training sets (`scenario-samples-src/` → `installer/make-scenario-samples.py` → `scenario-samples/`); a set's own cards (`scenario-cards/<CODE>/cards.json` → `build-scenario-cards.py`). Participant packages: `installer/build-sim-package.py` (private sets only, written outside the repo) |
| `deck/` | Overview slide deck (1920×1080 slides, order in `deck/deck.json`) |
| `docs/` | `PACE_PLAN.md` (authoritative comms plan), `FEEDBACK.md`, `SIMULATOR_DESIGN.md` (simulator program design, scenario schema, privacy modes, map UX), `SIMULATOR_SCENARIOS.md` (hazard research and the scenario catalog), `SIMULATOR_MAPS.md` (how a simulator places the git-ignored geographic dataset), `COMMUNITY_SETUP.md` (another area's export, pack, maps, drill spec), `SCENARIO_AUTHORING.md` (writing a scenario: every field the engine reads) |
| `simulation/` | EMCOMM simulator: `sim_server.py` (port 8090; `/results` for phones, `/debrief` slides for the room, `/report`), `index.html` (controller console + canvas map), `orgpack.py`, `privacy.py`, `engine.py`, `drillconfig.py` (`--check` validates a drill spec), `scenario_check.py` (scenario validator: run it on every new or edited scenario), `scenarios/` (the invented example's catalog + scenario JSON). `example/` is an **invented** community (Juniper Plains Area: `world.json` → `build_example.py` → `juniper-plains/` export with maps) for public drills and tests. A real community's packs, scenarios (`<export>/simulation/scenarios/`), local bindings, cards, set files, packages and runs live in `secure data/`, never in the repo. See `simulation/README.md` |
| `testing/` | `TEST_CHECKLIST.md`, `test_phone_api.py`, `test_offline_webkit.py` (WebKit, needs Playwright), `test_browsers.py` (every page in Chromium, Firefox and WebKit at phone, tablet and laptop sizes), `test_sim.py` (+ `fixtures/orgpack-synthetic.json`, invented), Winlink test helpers |
| `dist/` | Built release files (committed byte for byte, CRLF BAT; uploaded to the GitHub release and served by Pages, the download link the README and cards use) |
| `dev/` | `check-dev-setup.py` (is this machine ready: run it first on any machine; `--fix`, `--tests`), `setup-windows-vm-ssh.ps1` (lets a Mac reach the Windows VM by Secure Shell) |
| `.githooks/` | `pre-commit`: refuses private paths and runs `test_public_files.py`; enable once with `git config core.hooksPath .githooks` |

## Hard rules

1. **Only three forms**: Disaster Report (PD60000184), Supply Order (PD10052205), Work Crew Log (PD10052209). Do not add forms. Every field on the Church PDF must exist on every surface (Worker, Initial, Viewer, message body and tag, server map, EOC views); copy PDF wording, drop handwriting instructions.
2. **Winlink templates** (`*_Initial.html`): XHTML 1.0 Transitional; form action `http://{FormServer}:{FormPort}`; hidden `msg_body` carries the message (never name a field `attached_text` or `attached_file`); `buildMsg()` ends with the `[Church-XX|key=val|…]` tag and a `CSV,…` line; no external CSS/JS; the `.txt` definition next to it is `Form:<Initial>,<Viewer>` with **CRLF** line endings.
3. **Viewers are generated**: edit the Initial, then `python installer/make-viewers.py`. Never hand-edit `*_Viewer.html`.
4. **The app module is generated into pages**: edit `templates/_shared/emcomm-app.js`, then `python installer/sync-app-module.py` (CI-style check: `--check`). Never edit the inlined copies between the `EMCOMM-APP` markers.
5. **Versions move together**: a change the server must know about bumps `APP_VERSION` (module) and `FORMS_VERSION` (`eoc_server.py`); any change to a cached portal file bumps `CACHE` in `sw.js`.
6. **Only a Windows computer hosts** (maintainer, 2026-11-06): a platform that cannot run Winlink Express cannot host. The EOC server and the simulator run on a Windows laptop; a phone, tablet, Mac, Linux computer or Chromebook is a client, in any browser, and no installer or launcher for those platforms ships. Three levels, used in every doc and card: any browser, Windows host, Windows Winlink station. Plain-http LAN pages cannot use phone GPS (forms served by the EOC use the EOC location); https portal pages cannot fetch the LAN server (the app hands reports to `/receive` in the URL fragment instead).
7. **No external dependencies at runtime**: no CDN, no web fonts, no frameworks. The only vendored library is `forms/vendor/jsQR.js`; do not add more without the maintainer's approval.
8. **Server lock**: `_db_lock` is not re-entrant. Functions that take it (`_ingest_worker`, `_merge_bundle`, `_import_comms`) must be called outside it, or be passed `conn=` where supported.
9. **Never commit** `secure data/` (guarded by `.gitignore` and the shipped `.githooks/pre-commit`, which also refuses the paths below and runs `test_public_files.py`), `forms-source/` (the Church's PDFs: the README links to the official copies), `.claude/`, `eoc/eoc_data.db*`, `session-screenshots/`. Never put credentials in any file.
10. **The repository is public, and GitHub Pages publishes every committed file** (not just the portal: `docs/`, `CONTINUE.md`, `eoc/` all load from `travislhilton.github.io`). Anything committed is public, in its history too: no secrets, contacts, personal data, or contents of `secure data/` (the simulator dataset), in any file, test fixture or commit message. Code that needs that data loads it at run time from `secure data/` or a user-chosen path. **No real community at all** in public files (maintainer, 2026-11-01): no real stake, ward, place, county plan, scenario or person, not even a description; public examples, scenarios, training sets, cards and tests use the invented Juniper Plains Area. **No organization pack** except the invented example and the test fixture: a real pack, its export, drill spec, bindings and packages stay in `secure data/` (build one with `docs/COMMUNITY_SETUP.md`). `CONTINUE.md` and the checklist are public too; notes about the maintainer's own community go in `secure data/handoff/`. `python testing/test_public_files.py` must pass before every commit.

## Writing rules (every doc, form, card, slide, UI string)

- Spell out every acronym on first use in each document or card (EOC, PACE, SITREP, AWSRM, ERD, VARA, RMS, CMS, GPS, …). `python testing/test_acronyms.py` checks it (each card its own document, the deck in slide order, visible UI text only); a new acronym goes into its map with the expansion, a plain capitalized word into its not-an-acronym list.
- PACE vocabulary only for delivery paths. Alternate = **any internet anywhere** (home, shelter, business, meetinghouse, Starlink), never just meetinghouse/Starlink. Contingency data = **VARA FM** then VARA HF (never "packet").
- Church-guideline alignment: the stake **Welfare and Self-Reliance Specialist (emergency communications)** recommends the level, the **Stake President decides**, the ERD or specialist announces it. Never "the ERD declares"; never "Emergency Communications Specialist (ECS)". SITREPs: first assessment as soon as possible, then "regular status reports" on the interval EOC leadership sets — do not invent a fixed interval.
- Plain sentences for volunteers under stress: short, one action each.

## Change routine

1. Make the change. Regenerate what is generated (viewers, app module, card PDFs, deck ZIP).
2. Test it for real (see CONTRIBUTING.md → Testing): `python testing/test_acronyms.py` for any text change, `python testing/test_phone_api.py`, the browser checks for the parts you touched, deck slides and card sides measured when edited.
3. Update `testing/TEST_CHECKLIST.md` (the test rows, each with its Reference links to a card and a README section, the current status, and a Run Log line) and `CONTINUE.md` (what changed, what is open) **in the same commit**.
4. Rebuild: `python installer/build-release.py`, `python installer/build-deck-zip.py` when `deck/` changed. Run the installer role you touched and compare installed files with the repo.
5. Commit with a message file (`git commit -F msg.txt`; PowerShell 5.1 mangles quotes). Work on a branch and open a pull request unless you are the maintainer.
6. **Maintainer only**: `gh release upload v1.0 … --clobber` (list the assets afterwards: an HTTP 500 can delete the old asset without uploading the new one), move the `v1.0` tag, push.

## Development machines

Claude sessions run on the Windows 11 VM (maintainer, 2026-11-04). **Hosting and Winlink are tested on Windows; every browser client is in scope** (maintainer, 2026-11-06): `testing/test_browsers.py` runs Chromium, Firefox and WebKit at phone, tablet and laptop sizes, and the real phones, Android and non-Windows browsers are checklist rows. A Mac is a development machine only. Run `python dev/check-dev-setup.py` first on a new machine. The VM's newer Python hides what an older one refuses: see the older-Python gotcha below. Rules and steps: CONTRIBUTING.md section 2.

- **Only one session at a time in one folder.** The MacBook Pro's Windows VM sees the Mac's own folder as `X:`, so both use the same files and the same `.git`. Another machine has its own clone and syncs through git; `secure data/` never goes through git.
- **Still needs Windows:** Winlink Express checks, the installer roles, and card PDFs and deck measurements (their layout is set for Windows fonts). A Mac reaches the VM by Secure Shell (`ssh w9tlh-3`).

## Gotchas learned the hard way

- The public repository started fresh on 2026-11-05. A clone made before then has unrelated history: delete it and clone again. Never force-push from it, because that would publish its history.
- On the Windows VM the shell's working directory drifts: start commands with `cd /x/church-emcomm-wnlk-forms &&` (Bash) or `Set-Location X:\church-emcomm-wnlk-forms;` (PowerShell).
- Write each commit message to a new file name (`msg-<topic>.txt`), never a reused `msg.txt`, and check `git log -1 --format=%s` before pushing: a failed write once committed the previous message.
- Line endings are set by `.gitattributes`, so they match on Windows and macOS: LF, with CRLF for `.txt`, `.bat`, `.cmd`, `.ps1`. Generators that write a committed file must pass `newline=` so the bytes do not depend on the machine. If dozens of files show as changed, it is line endings: run `python dev/check-dev-setup.py` and do not commit.
- A Windows installer role writes to the VM's Documents, which is `C:\Mac\Home\Documents`, not `C:\Users\<name>\Documents`: compare installed files there.
- Deck slide with no Chrome extension: scratch copy of `deck/`, a hook after `showSlide(0); scaleSlide();` that calls `showSlide(k)` and writes the content bottom into a `#measure` div, `python -m http.server` (fetch refuses `file://`), then `chrome --headless=new --window-size=1920,1080 --virtual-time-budget=8000 --dump-dom <url>`.
- Chrome driven by the Claude extension cannot open `localhost`; use the LAN address (`http://<LAN IP>:8080`, dev server `:9877`).
- Never name a page global `status` (it is `window.status`, a string).
- On Windows a second server **binds a port that is already in use without an error** (`allow_reuse_address`), and the old process keeps answering: when a page or `curl` shows stale behaviour after a restart, list the port's owner (`Get-NetTCPConnection -State Listen`) and stop every stale scratch server by PID before trusting the result.
- A subprocess whose stdout is an unread pipe freezes once the pipe fills: send server logs to a file.
- The VM's Python 3.14 hides what breaks the promised 3.8: `write_text(newline=)` needs 3.10 (use `open(..., newline=)`), `__file__` is relative before 3.9 (always `.resolve()`), backslashes in f-string expressions need 3.12. `test_example.py` scans for these. To run the suites on an older Python here: unzip python.org's `python-<version>-embed-amd64.zip` into a scratch folder, delete its `._pth` file, run `dev/check-dev-setup.py --tests` with that `python.exe`.
- A `\n` inside a Bash heredoc fed to Python becomes a real newline and once silently broke three templates: patch files with a script written by the editor, then grep the result.
- Wall display layout: measure in a same-origin 1920×1080 iframe; deck slides: measure in the deck loader (`showSlide(i)`, content bottom above the footer at ~988 px); cards: every side ≤ 952 px at 720 px width.
