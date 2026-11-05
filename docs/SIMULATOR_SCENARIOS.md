# Emergency scenarios for the Larkspur Valley (invented example community)

Drill scenarios for the EMCOMM (emergency communications) simulator. Part of an independent volunteer project, not an official product or publication of The Church of Jesus Christ of Latter-day Saints.

**Everything here is invented.** The Juniper Plains Area, the Larkspur Valley, its towns, river, creek, dam, roads, bridges, facilities, its two coordinating councils, eight stakes and 51 wards and branches, and every person, phone number and email are made up ([simulation/example/world.json](../simulation/example/world.json), built into the example organization pack `simulation/example/juniper-plains/`). The coordinates only place the fiction on a map. The scenarios are drill fiction, not forecasts; the disaster lessons they rehearse are real ([SIMULATOR_LESSONS.md](SIMULATOR_LESSONS.md)).

**A real community's scenarios never live in this repository.** They live beside that community's directory export, in `<export>/simulation/scenarios/` (a `catalog.json` and one `<id>.json` per scenario), next to its local bindings. The simulator reads that folder when the pack is loaded; a pack scenario with the same id replaces the built-in one. Scenario files live in `simulation/scenarios/`; the engine and schema are in [SIMULATOR_DESIGN.md](SIMULATOR_DESIGN.md), section 4.

Acronyms used below: EOC (Emergency Operations Center), PACE (Primary, Alternate, Contingency, Emergency: the communications plan, [PACE_PLAN.md](PACE_PLAN.md)), SITREP (situation report), ERD (Emergency Response Director), WSRM (Welfare and Self-Reliance Manager), AWSRM (Area Welfare and Self-Reliance Manager), NWS (National Weather Service), ICS (Incident Command System; ICS 213 is the general message, ICS 213RR the resource request), VARA (the sound-card radio modem Winlink uses: FM, frequency modulation, on VHF/UHF, very high / ultra high frequency; and HF, high frequency), FRS / GMRS (Family / General Mobile Radio Service), HAM (amateur radio operator).

## 1. The valley

The Larkspur Valley runs 46 km north to south in the invented state of Westland. The **Larkspur River** flows south through Kestrel, Juniper Springs, Larkspur and Alder Flat. **Copper Creek** leaves **Copper Creek Reservoir** in the eastern hills through **Copper Creek Dam** (an earth embankment of the Larkspur Valley Irrigation District), runs west through Copper Ridge and the low south side of Larkspur, and joins the river below Center Street. **Saddleback** sits on the west bench under Saddleback Ridge, where the **Saddleback Peak amateur radio repeater** carries the stake nets.

| Town | People | Stakes | Notes |
|---|---|---|---|
| Larkspur | about 41,000 | Larkspur, Larkspur East, Larkspur West | County seat. Main Street runs north-south, Center Street east-west. Larkspur Regional Hospital, the county and city EOCs, the county shelter at Larkspur High School, the Larkspur Care Center |
| Copper Ridge | about 9,000 | Copper Ridge | East bench below the dam; Copper Ridge Retirement Village; Copper Ridge Fire Station (city EOC) |
| Juniper Springs | about 7,500 | Juniper Springs | North of Larkspur; the fairgrounds; the Juniper Springs Stake Center hosts the Council / Area EOC when one opens |
| Kestrel | about 3,200 | Kestrel | Farms, the Kestrel grain elevators and the rail spur |
| Alder Flat | about 5,800 | Alder Flat | River bottoms south of Larkspur |
| Saddleback | about 4,400 | Saddleback | West bench under the ridge |

**Ways in and out.** Route 12 (the Valley Highway) runs the length of the valley and crosses Copper Creek on one bridge at the south edge of Larkspur. Route 30 runs west-east through Saddleback, over the Larkspur River on the **Center Street bridge**, and up to Copper Ridge, where it crosses Copper Creek on the **Route 30 bridge**; Dam Road climbs to the dam. River Road follows the west bank to Alder Flat, where the **Alder Flat bridge** crosses the river. One bridge closure cuts the valley in pieces.

**Church lines.** The Larkspur Coordinating Council (Larkspur, Larkspur East, Larkspur West, Copper Ridge stakes) and the Kestrel Coordinating Council (Juniper Springs, Kestrel, Alder Flat, Saddleback stakes) form the Juniper Plains Area. The welfare line runs to the Juniper Plains Welfare and Self-Reliance Region (office in Larkspur) and the **Bramble Junction Bishops' Storehouse**, 140 km south-west, 2.5 hours by truck on dry roads. Special units: the Larkspur Care Center Branch (a care facility), the Copper Ridge Retirement Branch (a retirement village) and the Larkspur Spanish Branch (members from the three Larkspur stakes).

## 2. The catalog

Each scenario has an id (its file in `simulation/scenarios/`), the hazard, the kind of drill it makes, and the failures it rehearses. **Status**: *developed* means the full timeline, injects, templates, role cards and hot-wash checks exist; *outline* means the catalog entry only, enough for a controller to run it by hand.

| Id | Scenario | Onset | Length | Best for | Status |
|---|---|---|---|---|---|
| `copper-creek-dam` | **Copper Creek Dam failure, Larkspur Valley flood**, Sunday 07:50 | rapid | 4 h | everything at once: an evacuation order before church, a breach, bridges lost, the care facility surrounded, cellular lost in the south, Contingency by radio, Satellite EOC, missionaries, Spanish-speaking families, Supply Orders, city requests, a wet-snow night | **developed** |
| `larkspur-fault-m6.9` | Larkspur fault earthquake under the west bench, M 6.9 | sudden | 4 h | the repeater damaged from the start (simplex and HF), the Center Street bridge closed, liquefaction in the bottoms | outline |
| `saddleback-ridge-fire` | Wind-driven wildland fire on Saddleback Ridge | fast | 3 h | evacuation orders without warning; the repeater site burns; livestock to the fairgrounds | outline |
| `january-ice-storm` | January ice storm: valley-wide outage, five days of cold | slow | 2 h (day 2) | warming centres, generators and carbon monoxide, welfare checks, battery budgets | outline |
| `downslope-windstorm` | Downslope windstorm out of Copper Creek canyon | sudden | 2 h | a short, common event; a scheduled slide to Alternate as cell sites lose battery | outline |
| `kestrel-rail-hazmat` | Rail tank-car release at the Kestrel grain elevators, shelter in place | sudden | 2 h | restraint: accountability by phone and radio only, no runners, no crews | outline |
| `larkspur-river-flood` | Spring snowmelt flood on the Larkspur River, without dam failure | slow | 2 h (day 3) | sandbag crews, pumps, evacuations of the bottoms, status reports over days | outline |
| `regional-outage` | Regional power and telecom failure, 72 hours | sudden | 3 h | pure PACE discipline: radio only, then Starlink at the stake center | outline |
| `route12-mass-casualty` | Multi-vehicle crash with a youth bus on Route 12 in fog | sudden | 1 h | a county incident where the Church's role is accountability and support only | outline |

Developing an outline means writing its inject timeline, templates, roles and hot wash after the pattern of `copper-creek-dam.json`.

## 3. The developed scenario: Copper Creek Dam failure

**Premise.** Sunday 21 March, 07:50, daylight, +4 °C and light rain after three days of warm rain on a deep snowpack. The irrigation district reported seepage at Copper Creek Dam on Saturday evening; at 07:40 the wet area on the downstream face began carrying muddy water. At 07:50 the Larkspur County Sheriff orders Copper Ridge below the dam and the Copper Creek corridor through south Larkspur (south of 500 South) to leave now, and warns the Larkspur River bottoms and Alder Flat to get ready. Sacrament meetings start at 9:00. At 08:28 (T+38) the dam fails.

**Why a Sunday morning.** Members are dressed for church, phones are on silent, and families will drive toward meetinghouses in and near the order zone unless their leaders tell them not to: the first decision is the Stake President's, about the meetings. The county alert reaches most phones but not all, and not in Spanish. The breach comes before the meetings would have started; the water reaches south Larkspur at exactly 9:00.

**Severity** (rule `feature`, polygons drawn from the world geometry): band 3 in the flood path of Copper Creek (narrow in the Copper Ridge reach, spreading over the low south side of Larkspur), band 2 in the Larkspur River flood plain or the evacuation-order zone, band 1 in the warning zone, 0 elsewhere. Care-facility and retirement branches are at least band 2; the Spanish-language branch at least band 1. On the example pack this gives 5 units at band 3 (the care-facility and retirement branches, two east Larkspur wards on the creek, one Copper Ridge ward), 10 at band 2 (the south Larkspur wards, Riverside, Copper Ridge south of the creek, the Alder Flat river wards), 10 at band 1 (the warning zone and the Spanish-language branch) and 26 at band 0: the north stakes, which play **receiving units** (meetinghouses opened by themselves, families staying with relatives, warming-centre Supply Orders and crews).

**Satellite EOC.** When the Route 30 bridge goes at T+45, the Copper Ridge wards south of the creek cannot reach their stake center on the north bench. The scenario's `eocs.satellite` suggests those wards for a Satellite EOC at one of their meetinghouses above the water.

**Partner agencies.** The **Larkspur City EOC** (Fire Station 1, simulator call sign SIM-LKCITY) serves the three Larkspur stakes; the **Copper Ridge City EOC** (Copper Ridge Fire Station, SIM-CRCITY) serves the Copper Ridge Stake. They send ICS 213RR resource requests and ICS 213 answers by Winlink, never Church forms. SIM- call signs are simulator stations, never on the air.

### Timeline (drill minutes after 07:50)

| T+ | Clock | Phase | What happens | PACE |
|---|---|---|---|---|
| 0 | 07:50 | Order and warning | Evacuation order and warning; NWS flash flood warning (T+2) | P (congested) |
| 3 to 6 | 07:53 | Order and warning | Stake President decides the 9:00 meetings; the specialist recommends how members are told (order, warning, Spanish); the stake net opens on the Saddleback Peak repeater | P |
| 10 to 45 | 08:00 | Order and warning | Every unit's first Disaster Report by phone; the care-facility branch reports 46 residents and one van (T+14) and transport is requested through the county (T+16); the county shelter opens at the high school; a north meetinghouse opens by itself (T+20); the Stake President asks which building is the warming centre (T+22); two sister missionaries not accounted for (T+25); the dam worsens (T+30); health-and-welfare policy (T+32); Spanish-language notification (T+34) | P |
| 38 | 08:28 | Breach | **Copper Creek Dam fails.** Net control: priority traffic only | P |
| 45 to 57 | 08:35 | Breach | Route 30 bridge at Copper Ridge carried away; 911 overloaded; a family on a garage roof relayed in writing (T+47); the county liaison takes one consolidated message every 30 minutes (T+50); the wards south of the creek ask for a Satellite EOC (T+55) | P |
| 58 to 66 | 08:48 | Breach | SITREP #1 (first assessment as soon as possible); relatives' inquiries on the net (T+60); city sandbag request for River Road (T+60); Spanish-language branch: four families not reached (T+64); Copper Ridge city asks for accountability teams on the north bench (T+66) | P |
| 70 to 81 | 09:00 | Breach | Water reaches south Larkspur: Route 12 bridge closed, the care center surrounded; the substation floods (T+75); the fibre under the Route 12 bridge is cut (T+78); two failed attempts, the specialist recommends, the Stake President decides, the net announces Contingency (T+80) | **C** |
| 82 to 112 | 09:12 | Contingency | Work items first; county headcount request; care-facility Supply Order; a household not found (T+86, second path T+95); a runner with a paper form (T+92); roll call at the destination one short (T+96); Supply Orders from the flooded wards; a ward not heard from (T+100); the river rises through Riverside (T+104); missionaries found (T+108); a Starlink kit that works only once someone owns it (T+110); families staying with relatives (T+112) | C |
| 115 to 158 | 09:45 | Contingency | City moving crews before the crest (T+115); the repeater on battery (T+120); a meetinghouse flooded (T+122); the Pine Hollow rumour (T+125); boil-water order (T+128); Winlink congested (T+130); the household found in Kestrel (T+134); the flood reaches Alder Flat (T+140); duplicate warming-centre order (T+142); a donations truck and forty walk-up volunteers (T+145, T+148); follow-up reports; the ward not heard from relayed by voice (T+150); the high-school shelter full, the Church asked for a meetinghouse (T+152); carbon monoxide from a generator (T+156); livestock stranded (T+158) | C |
| 160 to 190 | 10:30 | Night | Storehouse truck delivery point and route (T+160); rain turning to wet snow, −3 °C (T+162); round-trip test (T+166); the repeater dies (T+170); overnight plan (T+172); **Alternate** (T+175); county call (T+178); six-figure warming-centre status (T+180); SITREP #2 (T+185); the city asks for warming-centre staff (T+190) | **A** |
| 205 to 225 | 11:15 | Night | AWSRM approvals and the truck by Saddleback and Route 30 (T+205); the 72-hour posture (T+210); first mud-out crews; city mud-out request for tomorrow (T+214); portable cell sites in the north (T+218); test; **Primary** for the north wards (T+225) | **P** (north) |
| 235 to 240 | 11:45 | Night | Close-out note; hot wash | P |

### PACE timeline

| T+ | Level | Why | Trigger |
|---|---|---|---|
| 0 | P | Cellular up but congested: one call in three fails, texts late, data works | |
| 80 | C | Substation flooded (T+75) and fibre cut (T+78): cell sites in the south off the air. Two failed attempts in 15 minutes; the specialist recommends, the Stake President decides, the net announces | two failed attempts in 15 min |
| 175 | A | Internet works in the north half (home Wi-Fi, a business on Main Street) and the stake center Starlink has a named operator; three round-trip successes at T+170. Alternate means any internet anywhere | round-trip test passed |
| 225 | P | Portable cell sites serve the north half; a second round-trip test passed. The south wards stay on what works for them | round-trip test passed |

The Starlink kit (T+110) gives the EOC its own internet hop to the line above as soon as someone owns its set-up (operator, power with hours, open sky, a test); the field stays at Contingency until the Stake President steps up.

### Who plays what

| Role | What the card asks |
|---|---|
| Controller | Runs the simulator, reads the opening and the breach aloud, hands the paper form to the runner, leads the hot wash |
| Stake President | Decides the meetings, member notification, the warming-centre building, the Satellite EOC, every PACE level, the public-shelter request; corrects a rumour once under their name |
| Welfare and Self-Reliance Specialist (emergency communications) | Opens the net; recommends notification, Spanish-language messages, Contingency, the relay plan and every step up after a round-trip test |
| Emergency Response Director (ERD) | Warming centre, care-facility transport, city requests, volunteers and donations, the overnight plan, the 72-hour posture |
| Bishop or branch president | First report while the phones work, updates after block checks, families with relatives reported as accounted for |
| Team Leader / block captain | Door knocks in the order zone; one report per household; the roll call at the destination |
| HAM operator (ward station or net control) | Reads the net cards; forms by Winlink VARA FM, then VARA HF; traffic priority; the relay frequency when the repeater dies |
| EOC operator | Work items, the missionaries alert, SITREPs on both lines, Supply Orders UP, the six warming-centre figures |
| Satellite EOC | The Copper Ridge wards south of the creek; rolls up once to the Stake EOC |
| Receiving stake EOC | The north stakes: meetinghouses opened by themselves, families with relatives, warming-centre orders and crews |
| Council / Area EOC | Juniper Springs Stake Center: roll-ups from stakes without a laptop, the welfare line's totals |
| Welfare line (WSRM and AWSRM) | Approves Supply Orders; asks for the delivery point and route; a "fulfilled" answer is not a delivery |
| Area Seventy | Email only; the public-shelter approval under a usage agreement |
| County liaison | 911 relays in writing; one message per stake every 30 minutes; the donations truck |

### Lessons rehearsed

Injects marked `lesson` in the scenario file (25 of them) rehearse the failure modes in [SIMULATOR_LESSONS.md](SIMULATOR_LESSONS.md). Each has a need the EOC must meet, a resolution when it does and a consequence when it does not.

| Lesson | What the EOC must do | Injects (→ resolution / consequence) |
|---|---|---|
| Official alert late or incomplete (Valencia, Kerr County) | The specialist recommends, the Stake President decides, the ERD or specialist announces: area, action, channels, languages; the meetings decided before members drive | `p-meetings` → `n-meetings-told` / `v-meeting-cars`; `p-alert-members` → `n-notify-moved` / `v-notify-late`; `p-spanish`, `v-spanish-branch` |
| Care-facility residents without transport, roll call at the destination (Eaton, Noto) | County transport, destination, headcount at departure and arrival | `dr-care`, `wi-care-transport` → `n-care-moved` / `v-care-left`; `v-care-roll` |
| 911 saturated (Helene, Valencia) | Relay in writing with address, people, access, call-back path; record the county's acknowledgement | `n-911`, `v-roof` → `n-rescue` / `v-roof-again`; `v-co` |
| Agencies refuse health-and-welfare traffic (Helene) | Publish the stake's own path, net control and successor | `p-hw-policy`, `v-hw-relatives` → `n-hw-complaint` |
| Saturated public-safety radio (Helene) | Name a liaison; one consolidated message per slot | `p-liaison-slots` → `v-county-norecord` |
| Reported versus verified missing (Helene, Valencia, Kerr County, Lahaina) | One item per household; families with relatives passed to their home wards; SITREP shows two numbers | `v-missing-family`, `v-missing-runner`, `v-family-found` → `v-third-trip`; `v-host-families`; `v-found` |
| Isolated units unreported (Noto, Helene) | "Not heard from" is a status; relay attempt; type the 30-word relayed report | `n-not-heard`, `dr-relay` → `n-area-asks-unit` |
| Satellite terminal without an operator, power or sky (Noto, Helene) | Operator, power with hours, open sky, then the round-trip test | `p-starlink-setup` → `n-starlink` / `n-starlink-nosignal` |
| Repeater dies; the blackout outlasts the plan (Helene) | Relay plan before the repeater fails; the 72-hour posture | `v-repeater-battery`, `n-repeater-down`, `dr-west-relayed` / `n-south-silent`; `p-72h` |
| Rumours misallocate resources (Helene, Magna 2020) | Verify with the county; one correction under the Stake President's name | `v-rumour-dam` → `n-rumour-stopped` / `n-self-evac` |
| Winlink congestion (Milton, Georgia) | Rank traffic; stop tests; short bodies | `n-winlink-congested`, `p-traffic-priority` → `n-queue` |
| False "fulfilled" and duplicate orders (Helene) | A fulfilled reply is a promise; consolidate orders per centre | `wi-dup-order`; `v-no-truck` → `n-no-water` |
| Unasked volunteers and goods (Helene, Valencia) | Receiving site with an inventory owner, or a refusal; no crew without a team leader | `v-box-truck` → `n-bus-lane`; `v-walkups` → `wcl-unsupervised` |
| Shelters become the second disaster (Buncombe, Noto) | Area approval and usage agreement; six figures per building; heat, fuel and dry clothing for the night | `n-shelter-full`, `p-shelter-usage` → `n-area-usage` / `v-shelter-toilets`; `wi-shelter-status`; `n-cold-night`, `wi-overnight` → `v-generator-out` |

### Done when, hot wash, traffic

**Done when** (the scoreboard): SITREP #1 by T+75 and #2 by T+210; every missionaries need met; no high-priority need without an owner; at least 70 % of needs met; the meetings decided in time; member notification decided and announced in time; the Pine Hollow rumour verified before relay. The **hot wash** has 30 checks, 15 with automatic evidence rules (Gather evidence).

**Traffic volume** with the example pack, seed 5: a Stake EOC simulator for the Larkspur Stake (7 units) plans about 156 items (22 reports, 39 net cards, 45 notes, 23 prompts, 12 work items, 7 ICS messages, 8 replies) with 37 needs; a receiving stake such as Juniper Springs about 97; a Council / Area simulator for both councils about 330, most of them inside roll-ups.

**Winlink training set.** `training/scenario-samples-src/copper-creek-dam.json` (code **CCD-1**) holds 24 ready-filled messages for the Larkspur Stake EOC on the same clock: 16 Church forms from the Larkspur Stake's wards and branch (first reports, the care-facility report and Supply Order, the missionaries and their UPDATE, Work Crew Logs) and 8 ICS 213RR requests between the Larkspur City EOC and the stake EOC. `python installer/make-scenario-samples.py` builds it.

## 4. Outline scenarios

**Larkspur fault earthquake, M 6.9** (`larkspur-fault-m6.9`). A winter weekday at 06:30 in the dark. An invented fault at the foot of the west bench ruptures from Saddleback to Juniper Springs. Older brick homes and downtown Larkspur fail; the Center Street bridge closes for inspection and splits Larkspur West from the county seat; the river bottoms liquefy around Alder Flat; Copper Creek Dam is inspected and holds. The Saddleback Peak repeater is damaged, so the net starts on simplex and VARA HF. *PACE:* P for 10 minutes, then C; A at T+170 after a round-trip test. *Severity:* distance bands 5 / 12 / 30 km from an epicentre under Saddleback, +1 in the river flood plain, care facilities at least 2.

**Wildland fire on Saddleback Ridge** (`saddleback-ridge-fire`). A late-August afternoon fire runs down the west bench on a dry wind. Saddleback and the Larkspur West bench evacuate; Route 30 west closes for smoke; the repeater site burns. Shelters at the Juniper Springs stake center; horses and livestock to the fairgrounds. *PACE:* P in the valley; C for the bench wards when their cell sites burn; simplex when the repeater is lost. *Severity:* band 3 inside the fire polygon, 2 within 2 km, 1 for the rest of Saddleback and Larkspur West.

**January ice storm** (`january-ice-storm`). Day 2 of an ice storm: most of the valley without power, Route 12 glare ice, −18 °C at night. Welfare checks, care facilities on generators, meetinghouses as warming centres, carbon monoxide. *PACE:* P while cell sites hold battery, A from the stake center Starlink, C as sites go dark. *Severity:* band 2 everywhere, 3 for care facilities and the rural units.

**Downslope windstorm** (`downslope-windstorm`). An east wind out of the Copper Creek canyon before dawn: trees and lines down across Copper Ridge and east Larkspur. A short, common event with a scheduled slide to Alternate. *PACE:* P, then A at T+60. *Severity:* band 2 in Copper Ridge and east Larkspur, 1 in the rest of the Larkspur council.

**Rail tank-car release at Kestrel** (`kestrel-rail-hazmat`). A derailment at the Kestrel grain elevators ruptures a tank car of anhydrous ammonia on a still morning; shelter in place for a 3 km downwind sector. Nobody moves: no runners, no crews, accountability by phone and radio only. *PACE:* P throughout. *Severity:* band 3 in the plume sector, 1 within 5 km.

**Spring snowmelt flood** (`larkspur-river-flood`). Day 3 of high water on the Larkspur River and Pine Hollow Creek without any dam failure: sandbag crews, pumps, evacuations of the bottoms, status reports over days. *PACE:* P and A, a Contingency slice for crews in the bottoms. *Severity:* band 3 in the flood plain, 2 within 1.5 km.

**Regional outage, 72 hours** (`regional-outage`). No damage, no casualties, no power, no cellular, no internet anywhere for three days. *PACE:* C from T+0; A for the EOC's own internet from T+60 (Starlink); never P. *Severity:* band 1 everywhere, 2 for care facilities.

**Crash with a youth bus on Route 12** (`route12-mass-casualty`). A Saturday-morning pile-up in fog involves a bus taking youth to a stake activity. The county leads; the Church's role is accountability and support for families, restraint on the net, and the Stake President's judgement about what goes up the line. *PACE:* P throughout. *Severity:* band 2 for the units nearest the crash and the youth's home units.
