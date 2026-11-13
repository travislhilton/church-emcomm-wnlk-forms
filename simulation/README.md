# Church of Jesus Christ EMCOMM Simulator

The drill engine for the EMCOMM (emergency communications) system: it plays a disaster scenario
against a running EOC (Emergency Operations Center) server so that volunteers, HAM (amateur radio) operators and
EOC operators can practise the whole chain, field → Satellite EOC → Stake EOC → the council line
(Area Seventy) and the welfare line (the Welfare and Self-Reliance Manager, WSRM, then the Area Welfare and Self-Reliance Manager, AWSRM), with the organization names of the pack on
screen and traffic that arrives the way real traffic arrives.

Independent volunteer project, not an official Church product.

## What is in this folder

| File | What |
|---|---|
| `sim_server.py` | The simulator server (Python standard library only, port 8090). Serves the page, the scenario catalog, the map dataset, and the run API (application programming interface). |
| `index.html` | The controller's console: **Session** (the trainer's path, step by step) · **Setup** (organization pack, EOC, scope, scenario) → **Map** → **Run** (clock, PACE level: Primary, Alternate, Contingency, Emergency; injects, net and paper cards) → **Needs** → **Roles** (one card per role player) → **Hot wash** (the evaluation checklist, the after-action report, the debrief). Self-contained: no mapping library, no CDN (content delivery network). |
| `orgpack.py` | Builds the organization pack (councils, stakes, units, buildings, leaders' contacts) from a CDOL (Church Directory of Organizations and Leaders) export folder or reads a prepared `orgpack.json`. |
| `privacy.py` | The two privacy modes: `real` and `pseudonymized` (default: last names kept; first names invented, men's names for men's callings; invented phones in the `555-01xx` range reserved for fiction, no states; emails `first.last@churchemcomm.sim`; no pseudonym equals a real full name in the pack; deterministic per pack). |
| `drillconfig.py` | Drill configuration: from a drill spec (which EOCs, staffed always or optionally, Winlink call signs) and the pack, one file the EOC server and the simulator both load (identity, map folder, call sign, drill event; what each simulator plays) |
| `engine.py` | `plan()` expands a scenario over the pack into a run (every report, note, card and prompt with its minute); `Runner` plays it against the EOC. |
| `scenarios/catalog.json` | The built-in scenario catalog: the invented example community (the Juniper Plains Area, `example/`), one scenario fully developed. A community's own scenarios live beside its directory export in `<export>/simulation/scenarios/` and are listed before these. |
| `scenarios/<id>.json` | A scenario: geography, severity rule, PACE timeline, phases, injects, templates, role cards, hot-wash checks. No organization names. Injects marked `lesson` rehearse a documented failure of a real 2024–2026 disaster ([docs/SIMULATOR_LESSONS.md](../docs/SIMULATOR_LESSONS.md)). |

Design: [docs/SIMULATOR_DESIGN.md](../docs/SIMULATOR_DESIGN.md). Scenario research and the
catalog narrative: [docs/SIMULATOR_SCENARIOS.md](../docs/SIMULATOR_SCENARIOS.md). Map data:
[docs/SIMULATOR_MAPS.md](../docs/SIMULATOR_MAPS.md). What real disasters of 2024 to 2026 taught
and how the injects rehearse it: [docs/SIMULATOR_LESSONS.md](../docs/SIMULATOR_LESSONS.md).

## The invented example community

`example/juniper-plains/` is a complete, entirely invented Church-directory-style export (the Juniper Plains Area: two coordinating councils, eight stakes, 51 wards and branches, invented leaders, drawn ward maps, a drill spec and configuration), built from `example/world.json` by `example/build_example.py`. Load it anywhere a real export goes (Setup → Organization pack; EOC Map data folder) for a public drill, a demonstration or a test. Its scenario is `scenarios/copper-creek-dam.json`.

A real community's own scenarios live beside its export, `<export>/simulation/scenarios/` (a `catalog.json` and the scenario files); the simulator lists them first. A drill's reference cards (`training/build-scenario-cards.py`) and its participant package (`installer/build-sim-package.py`: cards, pseudonymized pack and maps, scenario, drill configuration without paths, Winlink training set, in one zip) are built from a set file beside the export and written outside the repository.

## What never enters the repository

The organization pack (names, buildings, addresses, leaders' phones and emails), the map
dataset, the local scenario bindings and every generated run live **outside the repository**,
by default under `secure data/` (git-ignored, guarded by a pre-commit hook):

```
secure data/<export>/              the CDOL export: csv/, simulator/ (the pack is built from these at run time)
secure data/<export>/simulation/   salt.txt (pseudonym salt), <scenario>.local.json (local bindings), runs/
```

GitHub Pages publishes every committed file, so nothing from these folders may be copied into a
tracked folder, a test fixture, a screenshot or a commit message. The test fixture
`testing/fixtures/orgpack-synthetic.json` is invented.

## Every simulated report is an exercise

The engine ticks **THIS IS AN EXERCISE** on every form it sends (`exercise: YES`, the same flag a
person sets on the Winlink and phone forms), so the EOC shows an EXERCISE badge on each report,
prefixes the work items it derives with "EXERCISE:", and the wall says EXERCISE while every report
on file is one.

## Roles the directory does not list

The Church directory export has bishoprics, stake presidencies, clerks and the welfare line, but
no emergency callings (Emergency Response Director, the Welfare and Self-Reliance Specialist for
emergency communications, HAM operators). Add them on the Setup tab under the pack: organization,
role, name, mobile, email. They are saved in `<pack folder>\simulation\local-roles.json` on the
laptop, never in the repository, become contacts of their organization, and take the privacy mode
like everyone else. Injects and cards can then say `{erd}`, `{erd_phone}`, `{specialist}`,
`{specialist_phone}`.

Under step 2 the Setup tab lists the **must-have roles** for the EOC this simulator plays
(Stake President, specialist, Emergency Response Director, HAM operator, the bishop of every ward
covered; Area Seventy and the Welfare and Self-Reliance Manager at a Council / Area EOC) with who
fills each from the pack, red when nobody does, and an **Add** button that starts the local-role
row. The live EOC Message Center carries the same list on its Setup tab (names and phones saved
with the EOC identity).

## Run it

Installed (installer role 3): double-click **Church of Jesus Christ EMCOMM Simulator** on the
Desktop, which runs `EOC Message Center\simulation\start_simulator.bat` (the same Python the EOC
Server uses). Only a Windows laptop hosts the simulator; everyone else opens its pages in any browser. From the repository,
with the invented example community:

```
python simulation/sim_server.py --data simulation/example/juniper-plains
```

For your own community, pass your export root instead (a folder outside the repository, see
[docs/COMMUNITY_SETUP.md](../docs/COMMUNITY_SETUP.md)). With no `--data`, load the organization pack on the Setup tab.

Then open `http://<this PC's LAN address>:8090/` (the server prints it). The EOC server
(`eoc/eoc_server.py`) must be running on the EOC laptop with a **drill event** open (put DRILL in
its name) so simulated traffic never mixes with a real event. **Reset for the session** on the
Session tab opens that drill event for you.

### The Session tab: a training session, step by step

The page opens on the **Session** tab, the trainer's path:

1. **Before the meeting:** set up and rehearse (pack, EOC, scenario planned; a few minutes at 10× shows every path).
2. **Reset for the session:** the rehearsal stays a rehearsal. A fresh drill event opens on the EOC, the run is planned again at T+0, PACE is set to the scenario's first level, and every EOC screen shows *ready: waiting for the trainer's GO*.
3. **GO** (or one scheduled start time on every laptop). The EOC's SITREP (situation report) clock starts at GO.
4. **Live:** the clock, phase, PACE, score and what comes next.
5. **Finish:** the hot wash, the after-action report, the **debrief** for the projector and the **results** for phones.

The run is saved beside the pack every 30 seconds; **Resume** on the Session tab brings back an interrupted session, paused at the minute it was saved (`/api/session`, `/api/session/reset`, `/api/session/go`, `/api/session/resume`, `/api/sessions`).

### Pages for the room

| Address | What |
|---|---|
| `/debrief` | The debrief for the room: slides for the projector built from the run. What went well first, the score, why it matters (the real-disaster lessons behind the injects), one or two things per role, progress over the group's runs of the same scenario, the next drill date. ← → to move, **F** full screen, **P** print. Linked from the Session tab (step 5) and the Hot wash tab. |
| `/results` | Read-only results for phones on the same network: the scoreboard, the done-when checks, the do-better list and the timeline. It refreshes itself while the clock runs. The Session tab shows its address. |
| `/report` | The after-action report (printable): scoreboard, done-when checks, the do-better list by role, what went well, the needs ledger, the hot wash, the timeline. Also `/api/run/report.txt`. |

### The Setup tab

1. **Organization pack**: press **Browse for the pack…**. A window lists this laptop's folders: click to open them (a double-click opens one folder, not two). The pack folder is marked **✓ organization pack**; a participant package is marked *holds a pack* and offers its `2 Organization pack` in one click; a `.zip` file is shown with how to unzip it. Choosing the folder loads the pack. When the pack carries the drill's settings, **Set up from them** appears. Browse works only on the laptop that runs the simulator; a typed path still works under *What a pack folder looks like*; privacy mode (pseudonymized by
   default). **Real contacts** open a consent form: who consented (normally the Stake President),
   the date, who records it, and the promise that nothing from the run leaves the room. The
   server refuses real mode without it; the consent is shown on the red badge, stamped into the
   run file and the after-action report, remembered in the settings while real contacts are loaded
   (so `--privacy real` at the next start honours it for the same pack) and dropped as soon as the
   pack is loaded pseudonymized again. Texts and role cards can name the stake's emergency roles
   with `{erd}`, `{erd_phone}`, `{specialist}`, `{specialist_phone}` (from the local roles file;
   the role name when nobody holds it).
2. **EOC**: the address of the EOC server this simulator feeds; *Check EOC* shows its name,
   level, event, PACE level, and whether its Winlink Received folder is watched.
3. **Scope**: the stakes (or individual units) this simulator plays. The Satellite EOC's
   simulator plays its assigned wards; the Stake EOC's simulator the rest; the Area simulator
   the stakes nobody is playing.
4. **Scenario**, speed and seed. *Plan the run* expands it; the Run tab shows every item.

The settings (pack path, mode, EOC address, what it plays, scenario, speed, seed, drill event name) persist in the user's local app-data folder
(`%LOCALAPPDATA%\Church of Jesus Christ EMCOMM\simulator-settings.json`).

### Share the setup with another drill controller

The box under *Drill configuration* at the top of the Setup tab has three buttons:

- **Save simulator setup** (`POST /api/sim-setup/save`) writes `church_emcomm_sim_setup_<scenario>_<date>.json`
  (kind `church_emcomm_sim_setup`): scenario, speed, seed, what this simulator plays (`site`: role, stake or councils, the
  wards a Satellite EOC covers, the stakes with their own EOC laptop, whether people play the line above), the drill
  configuration choice if one was applied, the drill event name, the privacy mode it was saved in, this laptop's EOC
  address, and a **pack reference**: the pack folder's name, its counts, and `fingerprint`, the first 16 hex digits of a
  SHA-256 (Secure Hash Algorithm, 256 bits) hash of the sorted `id|name|type` lines of the pack's organizations (`orgpack.organizations`: councils, stakes,
  units, the welfare offices). No contact, address or person is in it.
- **Load simulator setup…** (`POST /api/sim-setup/apply`, first with `dry: true` for the preview) refuses a file whose
  fingerprint is not the loaded pack's ("Load the same organization pack first"), never changes the privacy mode (a file
  saved with real contacts leaves this laptop pseudonymized unless its own consent is recorded on step 1), keeps this
  laptop's EOC address unless the person ticks the file's, and refuses a drill configuration or an EOC setup with where
  each one loads. It is refused while a run is running.
- **Save drill configuration** (`POST /api/drillconfig/save`) writes the established `church_emcomm_drill_config`:
  `drill_config_from_screen()` turns what this simulator plays into a drill spec (this EOC with the call sign from the
  step 3 Winlink address; at a Stake EOC whose line above is played by people, the Council / Area EOC of its council;
  at a Council / Area EOC, the stakes with their own EOC laptop) and calls `drillconfig.validate_spec()` and
  `drillconfig.build()` exactly as the command line does. Every EOC in it is staffed *always*; optional EOCs and partner
  agencies need a hand-written spec. A Satellite EOC's own wards are not part of the drill configuration format, so the
  other simulator ticks them on step 2. Refused while real contacts are loaded: the file carries the leaders' pseudonyms.

## How simulated traffic arrives at the EOC

The PACE level in force decides the channel (the scenario changes it on its timeline; the
controller sets it when the players decide; both push it to the EOC header):

| Level | Channel | What the EOC operator sees |
|---|---|---|
| P, A | `POST /api/upload` (the phone app's path) | a phone / browser upload |
| C | a Winlink `.mime` message written into the EOC's watched Received folder, from the unit's simulated station (`SIM-…@winlink.org`), with the same `[Church-XX|…]` tagged body the Winlink templates send | a Winlink message, ingested by the watcher |
| C, no watched folder | a **paper card** on the Run tab with the full report text | types it in |
| E | a paper card | types it in |

Voice traffic is a **net card** the HAM role player reads over the net; scenario events are
posted to the EOC notes log prefixed `SIM:`; prompts tell a role player what to decide.
**Work items** (`kind: work_item`) are posted to the EOC's Work Items list (`/api/actions`): a request
or decision the reports cannot derive, such as the mission office asking for names, the county asking
for a headcount, the Stake President asking which building opens. The hot wash's **Gather evidence**
button reads that list back and fills in, under each check that has an `auto` rule, who owned the
item, how fast, its status and whether a decision was recorded; the controller still presses ✓ or ✗.

## What the simulator expects back: needs, consequences, the scoreboard

Everything the simulator sends creates a **need** the EOC must meet, with a deadline in drill
minutes: a work item owned within 10–30 minutes and closed (or set UP) within its limit, a
leadership question answered as a recorded decision, a paper or net report typed in within
25 minutes with the numbers as on the card. The simulator reads the EOC every few seconds and
keeps a **Needs** ledger (Needs tab: state, countdown, evidence, Waive for anything the room is
not playing). The **scoreboard** (Run tab, the page header, and the DRILL bar on the Message
Center, wall and phone) shows needs met, overdue, the score, minutes to an owner, HIGH items
without an owner, and the scenario's done-when checks.

The world answers what the EOC does. A need **met** brings its resolution (the shelter decision
→ the facilities manager opens the building; the delivery point named → the Bishops' Storehouse
truck leaves Bramble Junction); a need **overdue** brings the pressure back (the Stake President calls again
with a tighter deadline, the mission president comes on the county liaison's line, the truck is
held, the bishop asks over the net who has the injured list). Items that wait on a need show as
*waiting* on the Run tab with what they wait for; **Force now** fires one regardless.

The line above the stake answers too: unless the Setup tab says **people play the line above**,
the simulator plays the welfare line and the Council / Area EOC. A Supply Order set UP is approved
25–30 drill minutes later and closed DONE on the EOC with the decision and the truck's ETA (estimated time of arrival); a
headquarters-assistance request is acknowledged; at T+185 whatever is still UP gets its answer.
The reply is a `church_eoc_reply` bundle through the EOC's `/api/merge`, the same bundle a real
Council / Area EOC sends back: its Message Center offers **Reply to <EOC>** on every item that came
up in a roll-up, downloads the JSON (JavaScript Object Notation) file, and the lower EOC merges it like a roll-up (or its Drop Folder
watcher ingests it).

At the end (T+240, or Stop) the simulator writes the **after-action report** beside the run file
and serves it at `/report` (Hot wash tab → After-action report): scoreboard, done-when checks, the
**do-better list by role** (every need not met on time, with the evidence and one coaching line),
what went well, the needs ledger, the hot-wash answers and the timeline. The text version goes
into the drill-feedback issue. Pseudonymized runs still show real unit and building names. Before
filing an issue or screenshot, use the invented Juniper Plains Area or the Hot wash tab's "Report as
text, units redacted".

## Several EOCs in one drill

One simulator per EOC. On the Setup tab each drill director says **what this simulator plays**:
a **Stake EOC** (and which wards a Satellite EOC covers in this drill), a **Satellite EOC** (which
wards), or a **Council / Area EOC** (which coordinating councils, and which of their stakes have
their own EOC laptop; the rest are played by the Area simulator and arrive as roll-up files in
the Area EOC's Drop Folder at the SITREP times, merged by its watcher like an emailed roll-up; reports dated after a stake's last roll-up are
marked *skipped* when the rest is done, so the run ends).
The stakes people play must send their own roll-ups by the real path. Reports go to the EOC that covers the ward; items another EOC's simulator plays
are listed as *elsewhere* and never fired here. Every simulator uses the same scenario and seed.

The simulator pushes its state to its EOC, so the Message Center, the wall display and the phone
page show a **drill bar** (scenario, what this EOC plays, the clock or the countdown, who pressed
**I am ready**). The Run tab's **EOCs in this drill** lists every EOC heard on the network with its
simulator's state and flags a different scenario, seed or start time. **Schedule** starts the clock
at a wall-clock time; simulators at different sites set the same time and start together without
any network between them. Remote sites report ready by voice.
Every simulated report says SIMULATED in its text and carries the run id, so two runs never
collide in the EOC's duplicate check.

## Writing a scenario

Step by step: [docs/SCENARIO_AUTHORING.md](../docs/SCENARIO_AUTHORING.md). In short: copy
`scenarios/copper-creek-dam.json`, keep the structure (section 4 of the design document),
and put only geography and story in it: units are selected by distance, polygon, flags
(`care_facility`, `retirement`, `language_unit`) or sample, never by name. Anything that must
name a real unit goes into the local binding `secure data/<export>/simulation/<id>.local.json`
(same shape; `severity_override` by unit name, injects with `where.unit` or `where.units`,
extra notes). Add the scenario to `catalog.json` with its `applies.bbox` so a pack from another
area is not offered it.

## Tests

`python testing/test_sim.py` (synthetic pack, scratch EOC on port 8085, simulator on 8095):
pack and privacy, planning, Winlink bodies against the EOC's own parser, delivery over every
channel, PACE push, the run API, the session flow and the room pages. `--keep` leaves both servers
running for browser checks. `python testing/test_example.py` checks the invented example community
and its participant package; `python testing/test_public_files.py` checks that no real community
reached a public file.
