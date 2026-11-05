# Writing a simulator scenario

*An independent volunteer project, not an official product of The Church of Jesus Christ of Latter-day Saints.*

This guide walks you through writing a drill scenario for the Church of Jesus Christ EMCOMM (emergency communications) simulator, from a copy of the example to a tested run. A scenario plays a disaster against a running EOC (Emergency Operations Center): reports from the wards, net cards for the HAM (amateur radio) operators, decisions for the Stake President, requests from a city EOC, answers from the line above the stake. It also says what the EOC must do about each of them, and how the score and the hot wash read the result.

Read first: [SIMULATOR_DESIGN.md](SIMULATOR_DESIGN.md) (how the simulator works) and [COMMUNITY_SETUP.md](COMMUNITY_SETUP.md) (your community's export). The field reference in each section below comes from the code that reads the file, `simulation/engine.py` (`load_scenario`, `merge_local`, `severity_of`, `plan`, `resolve`, `build_form` and the `Runner`). A key the engine does not read does nothing; the validator (step 11) flags it.

**Where your scenario lives.** A scenario for a real community names real places, so it never goes into this repository (GitHub Pages publishes every committed file). Keep it beside your export: `<export root>/simulation/scenarios/<id>.json`, listed in `<export root>/simulation/scenarios/catalog.json`. The simulator lists those before the built-in ones. Public examples use only the invented Juniper Plains Area.

---

## 1. Copy the example

Copy `simulation/scenarios/copper-creek-dam.json` to `<export root>/simulation/scenarios/<your-id>.json`. It is complete and passes every check, so you change a working scenario instead of starting from nothing.

The top level:

| Key | Type | Meaning |
|---|---|---|
| `kind`, `v` | text, number | `church_emcomm_scenario`, `1` |
| `id` | text | Letters, digits, `.`, `_`, `-` only. Same as the file name without `.json` |
| `name`, `hazard`, `onset`, `summary` | text | Shown on the Setup tab, the run file, the report and the debrief. `summary` is the story in one paragraph |
| `sources` | list of text | Where the facts come from (hazard studies, plans) |
| `applies` | object | `{"bbox": [west, south, east, north]}`: the area it fits (step 10) |
| `clock` | object | `t0` (label for minute 0, for example "Sunday 07:50 local, light rain"), `duration_min` (default 240), `default_speed` (default 1) |
| `geo`, `severity` | object | Step 2 |
| `pace`, `phases` | list | Step 3 |
| `templates` | object | Step 4 |
| `injects` | list | Steps 5 and 6 |
| `needs`, `done`, `hotwash` | object, object, list | Step 7 |
| `roles` | list | Step 8 |
| `eocs`, `agencies` | object | Step 5 (Satellite EOC suggestion, partner agencies) |
| `lessons_note`, `agencies_note`, any `note` | text | Documentation only |

Change `id`, `name`, `summary` and `clock` first. Then work down this guide.

## 2. Geography and severity

A scenario names **geography** (a dam, a flood plain, a canyon road), never a ward. Each unit gets a **severity band** from 0 (unaffected) to 3 (worst), from where its meetinghouse is. Templates then give band-3 wards worse numbers than band-1 wards.

**`geo`** holds points and areas:

- A point: `"dam": [lat, lon]` (latitude first).
- `features`: named areas.
  - Polygon: `{"type": "polygon", "coords": [[lon, lat], [lon, lat], …]}` (**longitude first**, the GeoJSON order).
  - Circle: `{"type": "circle", "center": [lat, lon], "radius_km": 4}`.

Watch the order: points and circle centers are `[lat, lon]`, polygon corners are `[lon, lat]`. A swapped polygon contains no unit.

**`severity`** has one rule:

| `rule` | Keys | How a unit's band is found |
|---|---|---|
| `distance_km` | `from` (a `geo` point, default `epicenter`), `bands: [{"max": km, "level": n}, …]` | The first band whose `max` the distance does not exceed. A band without `max` catches the rest |
| `feature` | `default` (band outside every area, default 0), `bands: [{"in": "<feature>", "level": n}, …]` | The first area the unit is inside |
| `constant` | `level` | Every unit the same |

Also:

- `default_no_location`: the band of a unit with no coordinates (default 1).
- `boost`: raise some units after the rule. `{"in": "<feature>", "add": 1}` adds inside an area. `{"flag": "care_facility", "min": 2}` sets a floor for a flag (`care_facility`, `retirement`, `language_unit`), and may `add`.
- The result is always kept between 0 and 3.
- `severity_override` (`{"<unit name>": band}`) sets one unit by name. It names a unit, so it belongs in the local binding (step 9), not the scenario.

**Check the units per band.** Run the validator with your pack (step 11). Its info line reads, for example, `severity 0/1/2/3 = 26/10/10/5`. A drill where every unit is band 0 sends nothing interesting; a drill where every unit is band 3 overwhelms the room. Aim for a few band-3 units, more in bands 1 and 2, and most at 0.

## 3. PACE and phases

**`pace`** is the PACE (Primary, Alternate, Contingency, Emergency) level over the drill clock. The runner pushes each step to the EOC header the moment it comes into force; it also chooses how reports arrive (step 5).

```json
"pace": [
  {"t": 0, "level": "P", "why": "Cellular is up but congested."},
  {"t": 80, "level": "C", "why": "The substation flooded; two failed attempts in 15 minutes. The specialist recommended Contingency, the Stake President decided, the net announced it.", "trigger": "two failed attempts in 15 min"},
  {"t": 175, "level": "A", "why": "A round-trip test passed.", "trigger": "round-trip test passed"}
]
```

- `t` (minutes from T+0, ascending, the first at 0), `level` (`P`, `A`, `C`, `E`), `why` (shown to the controller and on the cards), `trigger` (optional).
- Write `why` the way the plan works: the stake Welfare and Self-Reliance Specialist (emergency communications) recommends, the Stake President decides, the ERD (Emergency Response Director) or the specialist announces it. Step back up only after a round-trip test.

**`phases`** split the story for the controller: `{"id", "from", "to", "title", "narrative", "controller"}`. `narrative` is read to the room; `controller` is a private note ("Do not hint at the breach"). Phases must not overlap and must fit inside `clock.duration_min`.

## 4. Templates: the reports

A template is the field set of one kind of report. Its keys are the **Worker form field names** (the same names the phone app sends), so the EOC files a simulated report exactly like a real one.

| Form | Fields (Worker form names) |
|---|---|
| Disaster Report (`dr`) | `inc_type`, `inc_date`, `period_from`, `period_to`, `inc_location`, `inc_stake`, `inc_ward`, `sp_name`, `sp_phone`, `sp_email`, `sub_name`, `sub_phone`, `sub_email`, `miss_safe`, `miss_details`, `mem_injuries`, `mem_deaths`, `mem_damaged`, `mem_destroyed`, `mem_details`, `bldg_damage`, `community`, `need_local`, `need_neighbor`, `need_hq`, `needs_details`, `vol_count`, `vol_hours`, `vol_activities`, `vol_injuries`, `vol_inj_details` |
| Supply Order (`so`) | `req_stake`, `order_date`, `req_del_date`, `del_contact`, `del_phone`, `del_addr`, `del_city`, `del_state`, `del_zip`, `proj_name`, `proj_num`, `stake_pres`, `other_desc1`…`other_desc5`, `other_qty1`…`other_qty5`, `other_num1`…, `other_unit1`…; catalog items through `items` (below) |
| Work Crew Log (`wcl`) | `log_date`, `log_location`, `chief_name`, `chief_stake`, `chief_ward`, `chief_hrs`, `chief_phone`, `safety_cert`; crew rows through `crew` (below) |

The engine fills `inc_stake` and `inc_ward` (Disaster Report), `req_stake` (Supply Order), `chief_stake` and `chief_ward` (Work Crew Log) from the unit when the template leaves them out, adds the unit's coordinates (`stn_lat_d`, `stn_lon_d`, `stn_grid_d`), and ticks THIS IS AN EXERCISE. Yes/no fields take `YES` or `NO`; `safety_cert` takes `true`.

**Value shapes** (`engine.resolve`). The band key is the unit's severity as text, `"0"` to `"3"`:

| Shape | Example | Result |
|---|---|---|
| Literal text | `"{building}, {city}"` | The text, placeholders filled |
| Number | `0` | `"0"` |
| Range | `{"range": {"0": [0, 0], "2": [0, 2], "3": [1, 4]}}` | A whole number between min and max |
| Pick | `{"pick": {"1": ["…", "…"], "3": ["…"]}}` | One text at random, placeholders filled |
| Yes | `{"yes": {"0": 1.0, "3": 0.9}}` | `YES` with that probability, else `NO` |

A band missing from the map uses the nearest **lower** band given, then the lowest. So `{"range": {"2": [1, 3]}}` gives band 3 the band-2 range, and bands 0 and 1 the band-2 range too (the lowest given): give band 0 its own entry when it should be zero. A bare band map without `range`, `pick` or `yes` resolves to an empty value: always wrap it.

**Supply Order items** use the Church catalog ids of the Supply Order form (two letters and two digits, for example `wa01` bottled water, `kb01` cleaning kits, `gs10`, `pi02`; the full list is in `templates/supply-order/…_Worker.html`):

```json
"items": {"range": {"2": {"wa01": [10, 25], "kb01": [15, 40]}, "3": {"wa01": [20, 50], "kb01": [40, 90]}}}
```

A drawn 0 leaves the item off.

**Work Crew Log crews:**

```json
"crew": {"count": {"1": [3, 6], "3": [5, 10]}, "hrs": {"1": [2, 4], "3": [3, 6]}, "wo": {"pick": {"1": ["Sandbags", "Welfare checks"], "3": ["Door knocks"]}}}
```

The crew names come from the unit's leaders in the pack, then "Crew member n". The paper form has 16 rows: keep `count` at 16 or fewer.

**Placeholders.** Two kinds:

- **Once-filled** (the same everywhere in the run): `{stake}` (the stake or stakes in scope), `{eoc}`, `{eoc_call}`, `{eoc_winlink}`, `{eoc_email}`, `{today}`, `{erd}`, `{erd_phone}`, `{specialist}`, `{specialist_phone}`, and the agency placeholders (step 5).
- **Per-unit** (filled for the unit an inject expanded to): everything above plus `{unit}`, `{unit_type}`, `{unit_call}` (the unit's simulated Winlink station, `SIM-…`), `{city}`, `{state}`, `{zip}`, `{address}`, `{building}`, `{building_name}`, `{bishop}`, `{bishop_role}`, `{bishop_phone}`, `{bishop_email}`, `{crew_chief}`, `{crew_chief_phone}`, `{stake_president}`, `{stake_center}`, `{stake_center_name}`, `{stake_center_city}`, `{stake_center_zip}`, `{tomorrow}`, `{severity}`.

Templates, and injects with `each: unit`, `each: stake` or `same_as`, get both kinds. **Role cards and injects that fire once get only the once-filled ones: a per-unit placeholder stays literal there** ("{bishop}" on the card). Write "the bishop" in those texts. An unknown placeholder also stays literal. `{erd}` and `{specialist}` read the local roles file beside the pack; with nobody named they say "the Emergency Response Director" and "the Welfare and Self-Reliance Specialist (emergency communications)".

## 5. Injects by kind

Every inject has `id` (unique), `kind` and a time. Common keys:

| Key | Meaning |
|---|---|
| `t` | A minute (`12`), or a window `{"from": 10, "to": 45}`: each unit gets its own minute in it |
| `each` | `once` (default), `unit` (one per unit that passes `where`), `stake` (one per stake, filled with the first such unit of the stake) |
| `where` | Which units (below) |
| `same_as` | The id of an **earlier** inject: the same units it expanded to (the care center's Disaster Report, then its Supply Order) |
| `to` | Which EOC of the drill: `stake`, `satellite`, `area`, `all`, `unit`. Default: reports follow their unit; notes and cards `all`; work items `stake`; roll-ups `area`. `eoc` is read as `all` |
| `role` | The role card it is for (`ham`, `stake_president`, `eoc`, …; the ids of step 8) |
| `note` | For the author and the controller; not sent |
| `lesson` | One line: the real-disaster failure it rehearses ([SIMULATOR_LESSONS.md](SIMULATOR_LESSONS.md)). Shown with the card and on the debrief's "why it matters" slide |
| `need`, `after` | Step 6 |

**`where`** (all given conditions must hold):

| Key | Meaning |
|---|---|
| `severity`, `severity_min`, `severity_max` | The band, exactly or as limits |
| `in` | Inside a `geo.features` area |
| `flags_any`, `flags_none` | Lists of `care_facility`, `retirement`, `language_unit` |
| `sample` | A whole number: that many units at random (`1` = one unit). A decimal up to 1: that share (`0.5` = half; `1.0` = all) |
| `tag` | Remember the chosen units under this name |
| `tag_not` | Leave out the units an earlier inject remembered under this tag (a cut-off ward sends no follow-up) |
| `unit`, `units` | A unit name or names. **Local binding only** (step 9) |

The same seed on every simulator draws the same units, so sites stay in step.

**The kinds:**

| `kind` | What it does | Its own keys |
|---|---|---|
| `form` | A Church form from a unit, delivered by the PACE channel | `form` (`dr`, `so`, `wcl`), `template`, `channel` |
| `note` | A line in the EOC notes log, prefixed `SIM:` | `text` |
| `voice` | A **net card**: the HAM role player reads it over the net; the operator types what is said | `text`, `role` |
| `prompt` | A card for a role player: a decision to make | `text`, `role` |
| `paper` | A card a "runner" hands in | `text` |
| `work_item` | An item on the EOC's Work Items list: a request the reports cannot derive (the mission office, the county, the Stake President) | `title`, `detail`, `next`, `cat`, `prio` (1 high, 2 normal; default 2), `due` (text such as `"08:36"` or `"now"`), `from`, `text`, `unit` (once-only items) |
| `reply` | The line above answers (step 6) | `match`, `decision`, `status`, `from`, `text` |
| `ics` | A partner agency's Winlink ICS (Incident Command System) form, never a Church form | `form` (`ics213`, `ics213rr`; default `ics213`), `agency` (default `city_eoc`), `subject`, `fields`, `text` |
| `rollup` | Council / Area simulator only: one roll-up bundle per stake it plays itself, with that stake's reports due so far | `text` (`{stake}` becomes the stake's name) |

**How a `form` arrives.** `channel` is `by_pace` (default), or fixed: `phone`, `drop`, `winlink`, `paper`, `voice`. By PACE: P and A arrive as a phone upload; C as a Winlink message in the EOC's watched folder (a paper card when the EOC has none); E as a paper card. A `voice` or `paper` delivery means a person must type it in, which creates a need (step 6).

**`ics` fields** use the labels of Winlink's ICS forms: `incident_name`, `to_name`, `from_name`, `subject`, `date`, `time`, `message`, `approved_by`; for a 213RR also `request_number`, `priority`, `qty`, `kind`, `type`, `item`, `requested_arrival`, `deliver_to`, `substitutes`, `requested_by`, `contact`.

**Partner agencies** (`agencies` at the top): `{"city_eoc": {"name": "…", "call": "SIM-…", "contact": "…", "place": "…"}}`. Each key gives placeholders `{city_eoc}`, `{city_eoc_call}`, `{city_eoc_contact}`, `{city_eoc_place}`. In a public scenario use invented names and `SIM-` call signs; real ones go in the local binding.

**A Satellite EOC suggestion** (`eocs`): `{"satellite": {"name": "…", "where": {…}}, "area": {"name": "…"}}`. The Setup tab offers the units matching `where` to a Satellite EOC's simulator.

## 6. Needs, consequences and replies

The score comes from **needs**: what the EOC owes for each thing the simulator sends. The engine registers them:

- every `work_item` (one need: owned and closed in time);
- every work item the EOC itself derives from a simulated report (injuries, missionaries, headquarters assistance, Supply Order approval…);
- every report a person must type in (paper or net card), compared field by field with the card;
- every `voice`, `prompt`, `paper` or `note` card that carries a `need` block.

**Need categories** (`cat`) and the engine's default limits, in drill minutes:

| `cat` | Owner within | Done within | Decision required | Counts as done |
|---|---|---|---|---|
| `missionaries` | 10 | 90 | no | DONE |
| `life` | 10 | 120 | no | DONE |
| `upward` | 15 | 60 | no | UP or DONE |
| `supply` | 20 | 150 | yes | UP or DONE |
| `facilities` | 30 | 120 | no | DONE |
| `assist` | 30 | 120 | no | DONE |
| `roster` | 30 | 60 | no | DONE |
| `other` | 30 | 120 | no | DONE |
| a typed-in report | typed within 25 | | | 80 % of the fields match the card |

Change them for the whole scenario in `needs.defaults` (`{"supply": {"owner": 20, "done": 150, "decision": true, "done_states": ["up", "done"]}, "report": {"typed": 25}}`).

**A `need` block** on an inject:

- On a `work_item`: overrides its rule: `owner`, `done`, `decision`, `done_states`, `label`, `role`.
- On a card (`voice`, `prompt`, `paper`, `note`): the EOC must make a work item for it: `cat`, `prio`, `owner`, `done`, `decision`, `title_contains` (the work item's title must contain this text: tell the players in the card, "a work item with 'warming' in the title"), `label`, `role`. Or `form` (`dr`, `so`, `wcl`): the card carries a report to type in.
- On a `form`: overrides the rule of the needs the report creates (for example `typed`).

**Consequences** (`after` on any inject): the inject waits until a need reaches a state, then fires.

```json
{"id": "n-meetings-told", "kind": "note", "after": {"need": "p-meetings", "is": "met", "delay": 10}, "text": "Bishops confirm: meetings cancelled."},
{"id": "v-meeting-cars", "kind": "voice", "after": {"need": "p-meetings", "is": "overdue"}, "role": "ham", "text": "Families are arriving for the 9:00 meeting…"}
```

- `need`: the inject id. For a need the EOC derives from a report, add `#` and its kind: `#miss`, `#life`, `#hq`, `#nbr`, `#local`, `#shelter`, `#bldg`, `#approve`, `#safety`, or `#report` (the typed-in report).
- `is`: `met` (fires on met or met late; the default), `overdue` (fires on overdue or missed), `missed`, `late`.
- `delay`: minutes after the need reached that state.
- With `each: unit` and the same units (`same_as`), each unit's consequence follows that unit's own need. A per-unit consequence of a stake-wide need follows the one need.

Write both paths for the important needs: a resolution when the EOC copes (the truck leaves), pressure when it does not (the Stake President asks again, with a tighter deadline). Nothing is forced: the players earn either path.

**Replies from the line above** (`kind: reply`): the simulator plays the welfare line and the Council / Area EOC, unless the Setup tab says people play the line above.

```json
{"id": "r-so-care", "kind": "reply", "each": "unit", "same_as": "so-care", "after": {"need": "so-care#approve", "is": "met", "delay": 25},
 "from": "Welfare line (WSRM)", "match": {"cat": "supply", "status": "up"}, "status": "done",
 "decision": "Approved by the WSRM; on the storehouse truck, ETA 14:00.", "text": "WSRM to {eoc}: Supply Order from {unit} approved."}
```

- `match` picks the EOC's work items to close: `cat` (one or a list), `status` (default `up`; a list, or `any`), `key_prefix`, `title_contains`. A per-unit reply also matches the unit.
- `status` the items get: `done` (default), `progress` or `open`. `decision` is written into them.
- With nothing waiting that matches, the reply still goes to the notes log, and the Run tab says so.

## 7. Done checks and the hot wash

**`done.checks`** are the scoreboard's "Done when" lines. Each has `id`, `label` and exactly one test:

| Test | Passes when |
|---|---|
| `"sitrep": n, "by": T` | SITREP number n (situation report) was generated by minute T. Make #1 early ("first assessment as soon as possible"); set later ones from the interval leadership sets for the drill event, never a fixed rule |
| `"no_unowned_high": true` | No high-priority need is left without an owner |
| `"pct_min": 70` | At least that share of needs met (met late counts half) |
| `"cat_met": "missionaries"` | Every need of that category met |
| `"need_met": "<inject id>"` | Every need of that inject met (pending until it fires) |

**`hotwash`** is the checklist read at the end: `{"t": minute, "check": "what should have happened", "how": "where to look"}`. Add an `auto` rule and **Gather evidence** reads the EOC's work items for you; the controller still records ✓ or ✗:

```json
"auto": {"items": {"title_contains": "meetings"}, "expect": {"min_count": 1, "decision": true}}
```

- `items` filters: `cat` (one or a list), `key_prefix`, `title_contains`.
- `expect`: `min_count`, `max_count` (catches duplicates: one item per household or shelter), `owner_within_min`, `done_within_min`, `status_in` (list), `decision`, `no_unowned_high`.

The after-action report, the debrief for the room and `/results` are built from these needs, checks and hot-wash lines.

## 8. Role cards

`roles` is a list of `{"id", "title", "cards": [{"t": minute, "text": "…"}]}`. The ids are what injects name in `role`. The example has `controller`, `stake_president`, `specialist`, `erd`, `bishop`, `team_leader`, `ham`, `eoc`, `satellite_eoc`, `receiving_stake`, `area_eoc`, `awsrm`, `area_seventy`, `county_liaison`. Cards may have a negative `t` (before T+0: what to set up).

Role cards are hand-outs, filled **once**: use only once-filled placeholders (step 4). Keep the Church roles right on every card: the specialist recommends, the Stake President decides, the ERD or the specialist announces.

## 9. The local binding

Some lines must name a real unit: the ward whose meetinghouse loses power, the care center by name, the real city EOC. Those go in a **local binding**, never in the scenario:

`<export root>/simulation/<scenario id>.local.json`, beside your export, never in a repository.

It has the scenario's shape, and the engine merges it over the scenario (`merge_local`):

| Key | Merge |
|---|---|
| `injects` | An inject with the same `id` replaces the scenario's; others are added. Here `where` may use `unit` and `units` (names as in the pack) |
| `severity_override` | `{"<unit name>": band}`, merged |
| `agencies` | Merged by key: the real city EOC, its call sign and contact |
| `geo.features`, `templates` | Added or replaced by name |
| `roles`, `hotwash`, `phases` | Replace the scenario's lists when given |
| `notes` | Kept for the controller |

The simulator finds it by the scenario id when the pack is loaded.

## 10. The catalog entry

The Setup tab lists a scenario only when `catalog.json` in the same folder lists it:

```json
{"kind": "church_emcomm_scenario_catalog", "v": 1, "area": "…",
 "scenarios": [{"id": "<your-id>", "name": "…", "hazard": "…", "onset": "rapid", "duration_min": 240, "status": "developed",
                "applies": {"bbox": [west, south, east, north]}, "summary": "…", "pace": "…", "severity": "…", "sources": [], "lessons": []}]}
```

`applies.bbox` is in degrees (longitude, latitude). The Setup tab marks a scenario "applies here" when the box overlaps the pack's meetinghouses; a pack from another area is not offered it. A scenario in your folder with the same id as a built-in one replaces it.

## 11. Validate and test

**Run the validator** (`simulation/scenario_check.py`):

```
python simulation/scenario_check.py "<export root>/simulation/scenarios/<id>.json" --pack "<export root>"
python simulation/scenario_check.py "<file>" --pack "<export root>" --local "<export root>/simulation/<id>.local.json" --catalog "<export root>/simulation/scenarios/catalog.json"
```

It reports unknown keys (typos the engine would silently ignore), missing ids, wrong value shapes, template fields that are not on the Worker form, `same_as` and `after` targets that do not exist, times outside the run, overlapping phases, per-unit placeholders in once-filled texts, and the done checks. With `--pack` it plans the scenario once: injects that reach no unit, units per band, placeholders left after planning, local-binding unit names not in the pack. Fix every error; read every warning. The Setup tab runs the same check before *Plan the run*.

**A test plan at 60×.** Before anyone plays it:

1. A scratch EOC server with a DRILL event open; the simulator on your pack, pseudonymized.
2. Plan the run; read the Run tab's list: every inject at a sensible minute, the right units.
3. Run at 60× (4 hours in 4 minutes) with nobody acting: every channel fires (phone, Winlink, paper, net cards), PACE steps reach the EOC header, the "overdue" consequences fire, the score ends low.
4. Run again at 10× and play the EOC: own items, record decisions, set Supply Orders UP. The "met" resolutions and the replies fire; the score rises.
5. Read the after-action report and the debrief: every do-better line makes sense to a volunteer.

## 12. Winlink training set, cards and the participant package

**Winlink training set.** A set of filled Church forms and ICS 213RR resource requests, numbered in drill-clock order, that trainees send from Winlink Express. The source (`installer/make-scenario-samples.py` reads it):

| Key | Meaning |
|---|---|
| `kind`, `v` | `church_emcomm_training_samples`, `1` |
| `scenario`, `code`, `title` | The scenario id; the set's code (for example `CCD-1`); the title |
| `stake`, `stake_eoc` | The receiving stake; its EOC's name (default "<stake> EOC") |
| `agency` | `{"name", "place", "short"}`: the city or county EOC that sends and answers the ICS 213RR requests; `short` names it in the file names (default "City EOC") |
| `places` | `{"<unit name>": [lat, lon]}`: where each unit's station is |
| `church` | Filled Church forms: `form` (`dr`, `so`, `wcl`), `unit`, `time` ("08:02"), `context` (what it is for and the answer it expects), `fields` (Worker field names, step 4), optional `tag` |
| `ics213rr` | Resource requests: `dir` (`city-to-stake` or `stake-to-city`), `time`, `short` (a short title), `context`, `fields` (Winlink's ICS213RR field names: `FormTitle`, `IncName`, `ActivityDateTime1`, `ReqNum`, `Priority`, `Qty1`…, `Kind1`…, `Type1`…, `Item1`…, `ReqDateTime1`…, `Delivery`, `Subs1`, `ReqName`, …; the script refuses a value longer than the form allows), optional `agency` (same keys, over the set's: a set with both a city and a county EOC) |
| `day`, `people`, `note` | For the author |

The public example is `training/scenario-samples-src/copper-creek-dam.json`. Your community's source goes beside the export, and is built into a private folder:

```
python installer/make-scenario-samples.py "<export root>/simulation/training/<source>.json" --out "<private folder>"
```

**Reference cards** for the set (participant briefing, controller and evaluators, the Winlink messages): a `cards.json` built with `python training/build-scenario-cards.py <cards.json>`. The format is at the top of that script; the public example is `training/scenario-cards/CCD-1/cards.json`. A private cards file goes in `<export root>/simulation/cards/`.

**The participant package**: cards, the pseudonymized pack and maps, the scenario and its binding, the drill configuration and the training set in one zip. Write a set file `<export root>/simulation/sets/<CODE>.set.json` (the format is at the top of `installer/build-sim-package.py`) and run:

```
python installer/build-sim-package.py "<export root>/simulation/sets/<CODE>.set.json"
```

The zip is written outside the repository. The builder refuses it if a real phone, email or leader's name is left inside.

## 13. Privacy checklist

Before you share anything:

- [ ] The scenario names geography only. Unit, building, partner and person names are in the local binding.
- [ ] Nothing real is in the repository: the scenario, its catalog, binding, training source, cards and set live beside your export. `python testing/test_public_files.py` passes.
- [ ] Phones in public examples are invented `555-01xx` numbers; emails are `@churchemcomm.sim`; call signs are `SIM-…`.
- [ ] Runs that leave the room are pseudonymized. Pseudonymized runs still show real unit and building names: before filing an issue or a screenshot, use the invented Juniper Plains Area or the Hot wash tab's "Report as text, units redacted".
- [ ] Real contacts only with the Stake President's consent recorded on the Setup tab, and nothing from that run leaves the room.
- [ ] Participant packages go only to the drill's participants.
