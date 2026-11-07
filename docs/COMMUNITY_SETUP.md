# Setting up Church of Jesus Christ EMCOMM (emergency communications) for your Church community

*An independent volunteer project, not an official Church product.*

Any stake or coordinating council can run Emergency Operations Centers (EOCs) that know their own wards, leaders, buildings and maps, and a drill simulator that plays a disaster against them. Everything below happens on the EOC laptop. Your community's data holds names and contacts: it never goes into a repository, an email or a shared drive.

The invented example community, the **Juniper Plains Area** (`simulation/example/juniper-plains/`), has every file described here. Open it next to this page: it is the best reference for the exact layout.

## What an organization pack is

An **organization pack** is the system's picture of your community: its coordinating councils, stakes, wards and branches, their buildings, the leaders in their callings and how to reach them. The Emergency Operations Center (EOC) servers and the drill simulator read it at run time, so reports, maps and drills use your own units.

You do not write the pack itself. You fill a folder of spreadsheet files, called the **export root**, and the software builds the pack from it each time it loads.

```
<export root>/                      a folder you keep private
  csv/                              the directory tables: required (section 1a)
    organizations.csv  contacts.csv  contactmethods.csv
    buildings.csv  building_organizations.csv  relationships.csv
  simulator/                        maps (section 1e)
    organization_boundaries.geojson   required, may be empty
    buildings.geojson  organization_locations.geojson  overlays/   optional
  simulation/                       your drills: written by the steps below
    building-names.json  drill-spec.json  drill-config.json
    scenarios/  sets/
```

**Never put a pack in a repository, a public folder or an issue.** It holds real names, phones and emails. This repository holds no real pack and refuses to accept one: `testing/test_public_files.py`, `.gitignore` and the commit hook all block these files. The only packs here are invented: the Juniper Plains Area and a small test fixture.

If you cannot fill the spreadsheets, `simulation/orgpack.py` also reads a hand-written `orgpack.json` of the same shape. Build the example with `python simulation/orgpack.py simulation/example/juniper-plains --out <private folder>/orgpack.json` to see that shape.

### The smallest pack that works

These files make a working pack: one council, one stake, two wards, one building. Everything in it is invented. Copy it into a new folder, then run the check in section 2. It should end with `Ready.`

`csv/organizations.csv`

```
org_id,org_name,org_type,council_id,stake_id
100,Sample Valley Coordinating Council,Area Coordinating Council,,
200,Sample Valley Stake,Stake,100,
301,Sample Valley 1st Ward,Ward,,200
302,Sample Valley 2nd Ward,Ward,,200
```

`csv/contacts.csv`

```
position_id,person_id,person_name,org_id,role_name,primary_phone,primary_email
1,p1,Alex Example,200,Stake President,555-555-0101,alex@example.com
2,p2,Blair Sample,301,Bishop,555-555-0102,blair@example.com
3,p3,Casey Demo,302,Bishop,555-555-0103,casey@example.com
4,p4,Drew Example,100,Area Seventy,555-555-0104,drew@example.com
```

`csv/contactmethods.csv`

```
owner_kind,position_id,org_id,contact_kind,contact_type,contact_value
Person,1,,Phone,Mobile Phone,555-555-0101
Organization,,200,Phone,OFFICE_PHONE,555-555-0110
```

`csv/buildings.csv` (the address sits on two lines inside its quotes)

```
building_id,address_raw,latitude,longitude
b1,"100 Example Road
Sampleville, UT 84000",40.5,-111.9
```

`csv/building_organizations.csv`

```
building_id,org_id
b1,200
b1,301
b1,302
```

`csv/relationships.csv` (the header line alone is enough)

```
from_org_id,relationship_type,to_org_id
```

`simulator/organization_boundaries.geojson` (empty: no maps yet)

```
{"type": "FeatureCollection", "features": []}
```

Then grow it: add your real units and leaders, draw boundaries (section 1e), and keep the folder private.

## 1. Build the export folder

**The Church directory (CDOL, the Church Directory of Organizations and Leaders) does not export this layout directly.** You copy what your calling lets you see into a set of CSV (comma-separated values) files with the columns below, by hand, from a spreadsheet, or with your own script. Everything goes into one folder, the **export root**. Keep it on the EOC laptop.

The rules below come from the code that reads the folder (`simulation/orgpack.py`). Columns not listed are ignored; extra columns do no harm. Files are UTF-8 (Unicode text; a byte-order mark is fine).

### 1a. The CSV files (`<export root>/csv/`)

The pack builder opens every file in this table. A file you have no data for must still exist with its header line.

| File | Required columns | What they mean |
|---|---|---|
| `organizations.csv` | `org_id`, `org_name`, `org_type`, `council_id`, `stake_id` | One row per organization. `council_id` on a stake row is its coordinating council's `org_id`; `stake_id` on a ward or branch row is its stake's `org_id`. |
| `contacts.csv` | `position_id`, `person_id`, `person_name`, `org_id`, `role_name`, `primary_phone`, `primary_email` | One row per person in a calling. `position_id` is unique per row; `person_id` is the same for one person in every row (pseudonyms are stable by it). |
| `contactmethods.csv` | `owner_kind`, `position_id`, `org_id`, `contact_kind`, `contact_type`, `contact_value` | Phones and emails. See 1c. |
| `buildings.csv` | `building_id`, `address_raw`, `latitude`, `longitude` | One row per building. Coordinates in decimal degrees (WGS84, the World Geodetic System 1984). |
| `building_organizations.csv` | `building_id`, `org_id` | Which building each organization meets in. One row per organization; a stake's row is its stake center. |
| `relationships.csv` | `from_org_id`, `relationship_type`, `to_org_id` | Links between organizations. Only rows whose `relationship_type` starts with `Participating` are used (1d). |

`addresses.csv` (`org_id`, `address_type`, `address_raw`, `latitude`, `longitude`) is optional: `community.py check` counts it, the pack does not read it.

### 1b. `org_type` values

Use these exact words:

| `org_type` | Used for |
|---|---|
| `Area Coordinating Council` | a coordinating council (the Area Seventy's council) |
| `Stake` | a stake |
| `Ward` | a ward |
| `Branch` | a branch |
| `Welfare and Self-Reliance Region` | optional: the local welfare office (the WSRM, Welfare and Self-Reliance Manager) |
| `Area PEF Self Reliance Office` | optional: the Area welfare office (the AWSRM, Area Welfare and Self-Reliance Manager) |
| `Area` | optional: the Area itself |

Any other `org_type` is ignored.

### 1c. Contacts and roles

Only these `role_name` values are kept (`orgpack.py`: `STAKE_ROLES`, `UNIT_ROLES`, `WELFARE_ROLES`, `COUNCIL_ROLES`). Every other row of `contacts.csv` is dropped.

- **Stake:** Stake President · Stake Presidency First Counselor · Stake Presidency Second Counselor · Stake Clerk · Stake Executive Secretary · Stake Assistant Clerk
- **Ward or branch:** Bishop · Branch President · Bishopric First Counselor · Bishopric Second Counselor · Branch Presidency First Counselor · Branch Presidency Second Counselor · Ward Clerk · Branch Clerk · Ward Executive Secretary · Branch Executive Secretary · Ward Assistant Clerk · Ward Assistant Clerk--Finance · Ward Assistant Clerk--Membership
- **Welfare line:** Area Welfare and Self-Reliance Manager · Welfare and Self-Reliance Manager · Humanitarian Specialist · WSRS (Welfare and Self-Reliance Services) Senior Service Missionary
- **Council:** Area Seventy

The directory has no emergency callings. Add the Emergency Response Director (ERD), the stake Welfare and Self-Reliance Specialist (emergency communications) and the HAM (amateur radio) operators on the simulator's Setup tab. They are saved beside the export in `simulation/local-roles.json`.

`contactmethods.csv` rows:

- **A person's phone or email:** `owner_kind` = `Person`, `position_id` = the contact's row. `contact_kind` = `Phone` or `Email`. A `contact_type` of `Mobile Phone` is used as the mobile number. Without one, the first `Phone` row is used, then `primary_phone`.
- **An organization's phone or email:** any other `owner_kind` (for example `Organization`), `org_id` = the organization. Phones: `contact_type` = `MEETINGHOUSE_PHONE` or `OFFICE_PHONE`. Email: `contact_kind` = `Email`.

### 1d. Places and special units

- **Addresses.** `address_raw` is the address as lines: a street line, then a line like `City, State 12345` (US-style; a full state name or a two-letter code; ZIP+4 is fine). A facility name may come first. Other formats still load, without city and ZIP.
- **Language units that draw from several stakes.** A `relationships.csv` row whose `relationship_type` starts with `Participating` between a ward or branch and a stake (either direction) adds that stake to the unit's `draws_from`.
- **Care-facility, retirement and language units.** Set `special_unit` to `true` on the unit's boundary feature (1e). The name then decides the flag: "Spanish" or a ward name with brackets → `language_unit`; "retirement" → `retirement`; any branch, or a name with "care", "center", "nursing" and similar → `care_facility`. Scenarios select units by these flags.

### 1e. Maps (optional, but every map needs boundaries)

The pack builder reads `simulator/organization_boundaries.geojson`. With no maps, use an empty file: `{"type": "FeatureCollection", "features": []}`. Everything works; the EOC Map tab and the simulator map stay empty. Scenarios still place each unit by its meetinghouse coordinates (`buildings.csv`), so severity by area and the catalog's area check still work.

| File (`<export root>/simulator/`) | What |
|---|---|
| `organization_boundaries.geojson` | One `Polygon` or `MultiPolygon` feature per ward, branch and stake, in WGS84 (`[longitude, latitude]`). Properties: `org_id` (required, matches `organizations.csv`), `org_name`, `org_type`, `stake_id`, optional `label_latitude`, `label_longitude`, `area_sq_km`, `special_unit` |
| `buildings.geojson` | Optional. One `Point` per building; properties `building_id`, `address_raw`, `organization_names` (list) |
| `organization_locations.geojson` | Optional. One `Point` per organization, for the simulator map |
| `overlays/manifest.json` + image files | Optional. Map images laid over the boundaries |

**Drawing boundaries.** Use any GIS (geographic information system) tool, for example QGIS or geojson.io. Trace each unit's area as a polygon, set its `org_id`, and export GeoJSON in WGS84 (EPSG:4326, the European Petroleum Survey Group code for it).

**Placing a map image.** Each `manifest.json` entry is one image placed on one organization. The image must be north-up in Web Mercator. Fields read by the EOC and the simulator:

| Field | Meaning |
|---|---|
| `kind` | `source_map_artwork` |
| `overlay_id` | unique id of this entry |
| `org_id` | the organization it belongs to |
| `image_path` | the image file, relative to the export root (for example `simulator/overlays/maps/stake-map.png`) |
| `web_mercator_bounds` | `[west, south, east, north]` in EPSG:3857 metres |
| `recommended_opacity` | 0 to 1 (0.6 works well) |
| `paper_label` | optional title shown with the map |

`simulation/example/build_example.py` writes such a manifest for its drawn maps; copy its pattern.

### 1f. Building names

The directory gives addresses, not names. `community.py init` writes `simulation/building-names.json` with a suggested name per building: the stake center convention ("<Stake> Center"), else "<City> Meetinghouse, <street>". Replace the suggestions with the names people use. Name welfare offices, Bishops' Storehouses and care centers by hand: no rule can guess them.

## 2. Check it and start your setup files

```
python simulation/community.py check "<export root>"
python simulation/community.py init  "<export root>"
```

`check` lists each file, its row or feature count, what it enables, and builds the organization pack once to prove it works. `init` writes two starter files into `<export root>/simulation/`:

- `building-names.json` (1f).
- `drill-spec.json`: every stake as an optional stake EOC and your coordinating councils under one optional Council / Area EOC.

## 3. The drill spec and the drill configuration

Edit `drill-spec.json`:

| Field | Meaning |
|---|---|
| `kind`, `v` | `church_emcomm_drill_spec`, `1` |
| `name` | the drill's name |
| `scenario` | the scenario id (`<export root>/simulation/scenarios/<id>.json`, or a built-in one) |
| `export` | the export root, relative to the spec (`..` when the spec sits in `<export root>/simulation/`) |
| `privacy` | `pseudonymized` (default) or `real` |
| `event` | the drill event the EOC opens: `name` (put DRILL in it), `type`, `sitrepHrs` (the interval leadership sets), `sitrepBy` (who set it) |
| `eocs` | one entry per EOC: `id`; `level` = `stake`, `satellite` or `area`; `stake` (the stake's name, for stake and satellite); `councils` (council names, for area); `building` (a `building_id`, optional; a stake EOC defaults to its stake center); `manned` = `always` or `optional`; `winlink` (the call signs that feed it); `name` (optional) |
| `agencies` | partner agencies that do not run this system (section 6): `id`, `name`, `call`, `contact`, `place`, `serves` (stake names) |

Then build the configuration:

```
python simulation/drillconfig.py "<export root>/simulation/drill-spec.json"
```

It checks every stake, council and building name against the pack and stops on a wrong one. It writes `drill-config.json` beside the spec: every EOC's identity (name, units, location, the council line with the Area Seventy and the welfare line with the WSRM), the must-have roles it knows, the map data folder, the Winlink call sign and the drill event.

## 4. Privacy

- **Pseudonymized (the default).** Last names are kept. First names, phones and emails are invented: invented phone numbers in the `555-01xx` range reserved for fiction (`<area code>-555-0123`, no state attached) and `first.last@churchemcomm.sim` emails. A pseudonym never equals any real full name in the pack. The same person gets the same pseudonym every run (a per-export salt in `simulation/salt.txt`).
- **Real contacts** only with recorded consent: the Stake President's consent is entered on the simulator's Setup tab (who consented, the date, who records it) and stamped on every run and report. Nothing from such a run leaves the room.
- **Unit and building names stay real in both modes.** Before a screenshot or an issue leaves the room, use the invented Juniper Plains Area or the Hot wash tab's "Report as text, units redacted".

## 5. Load it: actual operations and drills

- **EOC Message Center** (each EOC laptop, the EOC server running): Setup → **Load a drill configuration** → the file → which EOC this laptop is → tick the optional EOCs that have people. Or start the server unattended: `eoc_server.py --config=<file> --eoc=<id> [--manned=<id,id>]`. The server keeps a copy and re-applies the identity and call sign at every start.
- **Maps for actual operations without a drill**: Setup → This EOC → **Map data folder** = the export root. The Map tab and the wall draw your wards and stakes; click a ward on the Map tab and choose **Show map** under *Church directory maps* to lay your map image for it over the boundaries.
- **Simulator** (one per EOC laptop): Setup → **Drill configuration** → the same file and choices. It loads the pack, the scenario and what it plays. Or Setup → 1. Organization pack → **Browse…** to the export root (folders that hold a pack are marked), then **Load pack**. Browse works only on the laptop that runs the simulator. A participant package is a zip file: unzip it first, then choose its `2 Organization pack` folder.
- **Winlink**: the EOC reads the received messages of the chosen call sign straight from Winlink Express (`C:\RMS Express\<CALLSIGN>\Messages`) and a drill's simulated radio traffic from its own *Simulated Winlink* inbox.

## 6. Partner agencies (a city EOC that does not run this system)

A city or county EOC often needs Helping Hands crews from the stakes (sandbags, shovels, moving supplies) and the stakes need things from it (inspections, roads). Such an agency does not run this system and never receives Church forms. Its traffic uses the standard Winlink Express **ICS (Incident Command System) forms**:

- **ICS 213RR Resource Request** to ask for resources (crews, equipment, supplies), with quantity, kind, where and when.
- **ICS 213 General Message** for answers, updates and questions.

Name the agency in the drill spec (`agencies`). The EOC server recognizes an ICS 213RR or 213 from that call sign (from the form data Winlink attaches, or from the message text) and files it as a work item named for the agency with the request in its detail, and a note in the log; the stake answers from Winlink Express with an ICS 213. Agency names and call signs are local details: they live in the spec and the scenario's local binding beside the export, never in the repository.

## 7. Scenarios

The built-in scenarios belong to the invented example community: use them to learn the system. For your own area write a scenario with **[SCENARIO_AUTHORING.md](SCENARIO_AUTHORING.md)** (copy `simulation/scenarios/copper-creek-dam.json`) and keep it beside your export, never in a repository: `<export root>/simulation/scenarios/<id>.json` with a `catalog.json` listing it. The simulator lists those before the built-in ones. Put anything that names your units, buildings or partners in its local binding (`<export root>/simulation/<scenario>.local.json`).

## 8. Package a drill for its participants

A drill's reference cards, its organization pack (contacts pseudonymized) and its Winlink training set travel to the participants as one private zip. Write a set file beside the export (`<export root>/simulation/sets/<CODE>.set.json`; the format is at the top of `installer/build-sim-package.py`), the set's cards (`training/build-scenario-cards.py` describes the cards file) and then:

```
python installer/build-sim-package.py "<export root>/simulation/sets/<CODE>.set.json"
```

The zip goes beside the export (never into the repository). The builder refuses a package that still holds a real phone, email or leader's name.
