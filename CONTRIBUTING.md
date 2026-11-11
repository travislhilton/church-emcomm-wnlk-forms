# Contributing to Church of Jesus Christ EMCOMM

Thank you for helping. This project is maintained by volunteers for stake emergency
communications. It is an independent volunteer project, not an official product of
The Church of Jesus Christ of Latter-day Saints.

Read **[CLAUDE.md](CLAUDE.md)** first: it holds the project's standing rules (only three forms,
Winlink template rules, generated files, writing rules, the change routine). They apply to every
contributor, whether you write code yourself or with Claude Code.

## 1. Access

- The repository is **public**. Fork it and open a pull request; the maintainer is Travis Hilton, W9TLH. To compare fields with the Church forms, use the PDF (Portable Document Format) links in the README and keep them in `forms-source/`, which git ignores.
- The volunteer portal is public on GitHub Pages: <https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/>.
- Report problems and drill notes as GitHub issues (templates are provided; see [docs/FEEDBACK.md](docs/FEEDBACK.md)).

## 2. Set up a development machine (Windows or macOS)

| Tool | Why |
|---|---|
| [Git for Windows](https://git-scm.com/download/win) (a Mac has git with the Xcode command line tools) | version control (includes Git Bash) |
| [Python 3.8 or later](https://www.python.org/downloads/windows/) (tick *Add python.exe to PATH*; any current 3.x works) | EOC (Emergency Operations Center) server, simulator, build and test scripts (standard library only, nothing to `pip install`). Keep the code 3.8-compatible: the README tells EOC operators 3.8 or later |
| Google Chrome | testing pages; headless Chrome builds the card PDFs (Portable Document Format) and icons |
| [GitHub CLI](https://cli.github.com/) (`gh`) | pull requests, releases |
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | optional, recommended: see section 6 |
| Winlink Express, VARA FM / HF (VARA: the sound-card radio modem Winlink uses) | only to test the Winlink templates and radio paths |

```
git clone https://github.com/travislhilton/church-emcomm-wnlk-forms.git
cd church-emcomm-wnlk-forms
git config core.hooksPath .githooks
```

Run `git config core.hooksPath .githooks` once per clone. It turns on the project's pre-commit hook (`.githooks/pre-commit`): it refuses any staged file under `secure data/`, `forms-source/Originals/`, `eoc/eoc_data.db*` or `session-screenshots/`, and runs `python testing/test_public_files.py` and `python testing/test_acronyms.py`. Never skip it with `--no-verify`.

### Working from Windows or a Mac

Check any machine before you start. `--fix` turns on the commit hook; `--tests` runs every test suite.

```
python dev/check-dev-setup.py --fix
```

| Part of the job | Windows 11 | macOS |
|---|---|---|
| Edit, generators, every test suite, `installer/build-release.py`, commit, `gh` | yes | yes |
| Card PDFs, deck slide measurements | yes | on a Windows computer (a virtual machine, VM, or a Windows laptop), because the layout is set for Windows fonts |
| Winlink Express checks, `install.bat` roles | yes | on a Windows computer |
| PowerShell syntax check of the installer | yes | skipped without `pwsh`: after a change to `install.ps1`, build once on Windows |

**The same folder from two systems.** A Parallels VM sees the Mac's `Projects` folder as `X:`. Windows and macOS then share the files and the `.git` folder, so use one session at a time.

**Another machine** has its own clone. Move work with `git push` and `git pull` on a branch. Copy `secure data/` by hand, on an encrypted drive or over Secure Shell (SSH) between your own computers; it never goes through GitHub, and neither GitHub nor a chat is a place for it.

**A Mac reaching a Windows computer.** Run `dev/setup-windows-vm-ssh.ps1` on the Windows computer as administrator (its header has the steps), then add it to `~/.ssh/config` on the Mac. SSH is open to the local network only. A Mac on another network needs Tailscale on the Windows computer and the script's `-Tailscale` switch. `check-dev-setup.py` on a Mac checks the `w9tlh-7` and `w9tlh-3` entries.

**Windows checks from a Mac.** Keep a clone on the Windows computer outside any synced folder (for example `C:\dev\church-emcomm-wnlk-forms`), push your branch, then over SSH: `git pull` there and `python dev/check-dev-setup.py --tests`. Its login shell is PowerShell, so send PowerShell commands. Never run tests in the folder the installed EOC server uses.

**Line endings** are set by `.gitattributes`, so every machine sees the same bytes: line feed (LF), except carriage return + line feed (CRLF) for `.txt` (Winlink reads a template definition with LF as one line), `.bat`, `.cmd` and `.ps1`. If dozens of files show as changed, do not commit: run the check above.

## 3. Map of the repository

See the table in [CLAUDE.md](CLAUDE.md#map). The short version: `templates/` (the three forms, each as Winlink template, viewer and phone form), `forms/` (the public portal and installable Church of Jesus Christ EMCOMM app), `eoc/` (server, Message Center, wall display, phone page), `simulation/` (the drill simulator: server, console page, engine, the invented Juniper Plains example community and its scenario), `installer/` (installer and build scripts), `training/` (cards, practice forms, Winlink training sets), `deck/` (slides), `docs/` (the PACE plan: Primary, Alternate, Contingency, Emergency; simulator design, [scenario authoring](docs/SCENARIO_AUTHORING.md), community setup), `testing/` (checklist and tests), `.githooks/` (the pre-commit hook).

One naming exception: the Work Crew Log's Winlink Initial template is `templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log.html` (no `_Initial` suffix). The other two are `…_Initial.html`.

## 4. Run things locally

| What | How |
|---|---|
| EOC server (networked Message Center) | `cd eoc` → `python eoc_server.py` → open the **Network** address it prints. Stop an installed server first (only one can use port 8080). Its database `eoc/eoc_data.db` is git-ignored. |
| Second EOC on the same PC (drills) | copy `eoc/` and `templates/` to another folder → `python eoc_server.py 8081` |
| Phone page / phone forms | `http://<your LAN IP>:8080/m` from a phone on the same Wi-Fi (allow Python through the Windows firewall on private networks) |
| Wall display | `http://<LAN IP>:8080/wall`, press F |
| Portal and phone forms as GitHub Pages serves them | from the repo root: `python -m http.server 9877 --bind 0.0.0.0` → `http://<LAN IP>:9877/forms/` (the offline app and GPS, Global Positioning System, location need https or `localhost`) |
| Deck | `http://<LAN IP>:9877/deck/index.html` |
| EMCOMM simulator (drills) | `python simulation/sim_server.py --data simulation/example/juniper-plains` (the invented example) → `http://<LAN IP>:8090/`; needs an EOC server with a drill event open. Installed by role 3 under `EOC Message Center\simulation\` (`start_simulator.bat`). A real community's organization pack and map dataset come from `secure data/` at run time (see `simulation/README.md`) |
| On a Mac | development only, the same commands. A Mac cannot host the system or install it: only Windows hosts, because Winlink Express needs Windows |
| Cards → PDFs | `python training/build-quick-ref-pdfs.py` |
| After editing the app module | `python installer/sync-app-module.py` |
| After editing an Initial template | `python installer/make-viewers.py` |
| Installer builds | `python installer/build-release.py` (one-file installer and ZIP, on Windows or macOS; a new file must be added with `git add` before a build ships it); deck: `python installer/build-deck-zip.py` |

## 5. Making a change

1. Create a branch: `git switch -c short-description`.
2. Make the change and regenerate whatever is generated (see the table above).
3. **Test it** (section 7) and record the result in `testing/TEST_CHECKLIST.md`: update the test's row and add a Run Log line. Note anything still open in `CONTINUE.md`.
4. Run `python testing/test_public_files.py` before **every** commit (the pre-commit hook runs it for you once `core.hooksPath` is set). GitHub Pages publishes every committed file: no real community, no contacts, nothing from `secure data/`.
5. Commit (`git commit -F message.txt` avoids PowerShell quoting problems), push the branch, open a pull request with `gh pr create`. Describe what you tested and on which devices.
6. The maintainer reviews, merges, builds the installer and ZIP, uploads the release files and moves the `v1.0` tag.

Tests that need real equipment (Winlink over radio, an iPhone, a TV, a USB (Universal Serial Bus) drive) are marked 🔒 in the checklist. If you have the equipment, run them and record the result: that is one of the most useful contributions there is.

## 6. Developing with Claude Code

[Claude Code](https://docs.claude.com/en/docs/claude-code) is Anthropic's coding assistant for the terminal. Most of this project was built with it, and it is set up to continue that way:

- **`CLAUDE.md`** (repository root) is loaded automatically at the start of every Claude Code session. It gives Claude the project's rules, map, routine and known pitfalls, so you do not have to explain them.
- **`CONTINUE.md`** is the running handoff: what was done last, what is open, the machine notes. Ask Claude to read it at the start of a session ("read CONTINUE.md and tell me where things stand") and to update it at the end.
- **`testing/TEST_CHECKLIST.md`** is where Claude records what it tested and how; review it in the pull request.

### A good session

1. Open a terminal in the repository folder and run `claude`.
2. Say what you want in plain words, with the *why*: "Volunteers at shelters keep forgetting to set the ward on the Disaster Report. Make the ward field required on the phone form and show a clear message." Claude reads the code, proposes or makes the change, and keeps generated files in step.
3. Ask Claude to **test it for real**, not just reason about it: run `python testing/test_phone_api.py`, start the servers, and check the pages in Chrome with the Claude in Chrome extension (it can click through the forms, read the page and measure layouts).
4. Ask it to update the checklist and `CONTINUE.md`, then to commit on a branch and open a pull request. Read the diff yourself before merging.

### Tips

- Give Claude the reason behind a request; it then gets the details right (wording, which surfaces to update, which tests to run).
- Paste screenshots of what you see (save them in `session-screenshots/`, which is git-ignored, and say "see screenshot").
- Claude cannot hold a radio, an iPhone or a TV. When a change needs one, ask it to write the test steps into the checklist (marked 🔒) for a person to run.
- Keep personal data and anything from `secure data/` out of prompts you would not want in the repository history; never paste passwords or tokens.
- Claude's permission prompts are there for a reason: read what a command does before approving pushes, release uploads or deletions.

## 7. Testing

- **Server and phone flow**: `python testing/test_phone_api.py` starts two scratch EOC servers (ports 8080 and 8081) and checks the phone page, served forms, discovery between EOCs, upload, duplicates and relay. `--keep` leaves them running for browser testing.
- **Incident read-out**: `python testing/test_readout.py` starts a scratch EOC server (port 8086, `--port=` to move it), seeds invented reports and checks `GET /api/readout` against the contract in `docs/contracts/emcomm-readout/` (schema, fingerprint, no personal or medical details, null for what nobody reported, `readout-latest.json`). With Playwright installed it also runs the Message Center's own `buildSitrep()` in Chromium and compares the totals; without it, it skips that part and says so.
- **Winlink training sets**: `python testing/test_training_samples.py` regenerates every set from `training/scenario-samples-src/` and compares, checks that only invented contacts appear, opens each filled Church form in Chromium and has the EOC server (scratch, port 8183) ingest the message it builds, and builds each ICS 213RR (Incident Command System resource request) from the local standard Winlink form the way the installer does (skipped without Winlink Express).
- **Offline app on the iPhone engine**: `python testing/test_offline_webkit.py` serves the repo on port 8099 and drives WebKit (the engine of every iPhone browser) through a hanging network, an offline network and a lost localStorage copy: the app must start, open forms, save, open and close the Outbox within seconds. Needs `python -m pip install playwright` and `python -m playwright install webkit` (test only, never shipped).
- **Example community and packages**: `python testing/test_example.py` checks the invented Juniper Plains Area against `simulation/example/world.json`, plans its scenario for every EOC of its drill, and builds a participant package (cards, pseudonymized pack, scenario, Winlink set) with its leak check and its refusals.
- **No real community in public files**: `python testing/test_public_files.py` refuses anything shaped like an organization pack outside the invented example and the test fixture. On the maintainer's computer it also scans every tracked file and the release files for the guarded terms and, with a directory export present, for every real unit, leader name, phone and email. Run it before every commit (the pre-commit hook does).
- **Acronyms spelled out**: `python testing/test_acronyms.py` reads every user-facing document (each card, each CCD-1 scenario card, the deck, the pages and forms, the Markdown and text guides) and fails when an acronym's first use has no expansion next to it, or when an upper-case word is not in its acronym list yet (add it with its expansion). `--show` lists each miss with its context. The pre-commit hook runs it after the public-files check.
- **Simulator**: `python testing/test_sim.py` runs the engine, privacy and server checks against the invented pack in `testing/fixtures/` and a scratch EOC (port 8085; simulator on 8095). Never point a test at `secure data/`.
- **Browser checks**: the recipes are in `testing/TEST_CHECKLIST.md`, section by section (Worker forms, Winlink templates, Drop Folder, EOC Message Center, wall display, Comms Sheet, phones and the Church of Jesus Christ EMCOMM app).
- **Layout checks**: deck slides measured in the deck loader; wall display measured in a 1920×1080 iframe; card sides ≤ 952 px at 720 px width (see CLAUDE.md, *Gotchas*).
- **Winlink templates**: `testing/make-winlink-test-copies.ps1` builds substituted copies for browser testing; the real test is in Winlink Express.

## 8. Style

- Plain JavaScript, HTML (HyperText Markup Language) and CSS (Cascading Style Sheets) in single self-contained files; Python standard library only.
- Match the surrounding code; comment the *why*, not the *what*.
- Light and dark themes where the page already has them; touch targets at least 44 px on phone pages; 16 px inputs on iPhone.
- User-facing text follows the writing rules in CLAUDE.md.
