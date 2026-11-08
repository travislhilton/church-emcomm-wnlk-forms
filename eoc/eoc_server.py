#!/usr/bin/env python3
"""Church of Jesus Christ EMCOMM — EOC Message Center local network server (Python stdlib only, no pip required)."""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import http.server, json, sqlite3, pathlib, socket, threading, time, re, urllib.parse, urllib.request, hashlib
import ctypes, string, shutil, email as _email, os, uuid

# Port: 8080 unless given as the first argument or EOC_PORT (practice drills can run
# a second EOC on the same laptop from another folder: python eoc_server.py 8081).
PORT = int(os.environ.get('EOC_PORT') or (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8080))
VERSION = '1.0'
# The Worker forms / Church of Jesus Christ EMCOMM app version this server ships (APP_VERSION in templates/_shared/emcomm-app.js).
# Phones whose app is older still send fine; the receive page just tells them to update when they have internet.
FORMS_VERSION = '2026-11-07.1'
BASE = pathlib.Path(__file__).resolve().parent   # resolve: before Python 3.9 __file__ is relative when started from this folder
DB_FILE   = BASE / 'eoc_data.db'
HTML_FILE = BASE / 'EOC_Message_Center.html'
WALL_FILE = BASE / 'EOC_Wall_Display.html'   # served at /wall
PHONE_FILE = BASE / 'EOC_Phone.html'          # served at /m (phone page) and /receive (hand-off from the Church of Jesus Christ EMCOMM app)

# Worker forms served to phones on the EOC Wi-Fi at /forms/dr, /forms/so, /forms/wcl.
# Installed: <base>\Field Worker Forms\ next to <base>\EOC Message Center\; repo: templates\<dir>\.
WORKER_FORMS = {
    'dr':  ('disaster-report', 'Church_of_Jesus_Christ_Disaster_Report_Worker.html'),
    'so':  ('supply-order',    'Church_of_Jesus_Christ_Supply_Order_Worker.html'),
    'wcl': ('work-crew-log',   'Church_of_Jesus_Christ_Work_Crew_Log_Worker.html'),
}
# The EOC home-screen app: an icon that opens this EOC's phone page. Plain http cannot hold an offline app, so it works
# only on this EOC's Wi-Fi; the phone page says so and offers the full offline app (the https portal) when there is internet.
APP_ICONS = ('icon-180.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png')
APP_MANIFEST = {
    'name': 'EMCOMM EOC', 'short_name': 'EMCOMM EOC', 'description': "This EOC's phone page. Works on the EOC Wi-Fi only.",
    'id': '/m', 'start_url': '/m', 'scope': '/', 'display': 'standalone', 'orientation': 'portrait',
    'background_color': '#f0f2f5', 'theme_color': '#1a3a5c',
    'icons': [{'src': '/icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'}, {'src': '/icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
              {'src': '/icons/icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}],
}
def _icon_path(name: str):
    if name not in APP_ICONS:      # names on this list only: nothing else on the laptop is reachable through this route
        return None
    for d in (BASE.parent / 'Web App (portal copy)' / 'forms' / 'icons', BASE.parent / 'forms' / 'icons'):
        if (d / name).is_file():
            return d / name
    return None

def _worker_form_path(key: str):
    d, name = WORKER_FORMS[key]
    for p in (BASE.parent / 'Field Worker Forms' / name, BASE.parent / 'templates' / d / name, BASE / name):
        if p.exists():
            return p
    return None

# Discovery: every EOC server announces itself on the LAN by UDP broadcast so a phone can
# pick which EOC to send to when a drill runs more than one EOC on the same network.
DISCOVERY_PORT = 8089
DISCOVERY_EVERY_SEC = 5
PEER_TTL_SEC = 20
BACKUP_DIR = BASE / 'backups'
BACKUP_INTERVAL_SEC = 15 * 60   # auto-backup every 15 minutes
MAX_BACKUPS = 20                 # keep the 20 most recent timed backups
USB_FOLDER = 'ChurchEMCOMM_EOC_Backup'

# Winlink Express keeps every message of a callsign, received and sent, as <Message-ID>.mime in
# <install>\<CALLSIGN>\Messages\ (its folders live in <CALLSIGN>\Data\Registry.txt). The watcher reads those
# files where they are and never moves them; the operator can point it elsewhere via the API or the Message Center.
WINLINK_ROOTS = [pathlib.Path(r'C:\RMS Express'), pathlib.Path(r'C:\Winlink Express')]
WINLINK_DEFAULT_PATH = next((p for p in WINLINK_ROOTS if p.is_dir()), WINLINK_ROOTS[0])
WATCHER_INTERVAL_SEC = 10
WATCHER_INGESTED_DIR = 'EOC Ingested'  # a plain folder of .mime files (not Winlink's store): processed files move here
WINLINK_GRACE_SEC = 300                 # Winlink messages older than the active event's start (less this) are history

# Settings that must survive a restart and suit an unattended start: which Winlink folder and callsign(s) feed this
# EOC. Chosen on the Message Center watcher bar (saved here), written in this file by hand, or given on the command
# line (--winlink-callsign=W9TLH[,W9TLH-3]  --winlink-folder=C:\RMS Express; those win for that run, not saved).
SETTINGS_DIR = pathlib.Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CONFIG_HOME') or (pathlib.Path.home() / '.config')) / 'Church of Jesus Christ EMCOMM'
SETTINGS_FILE = SETTINGS_DIR / 'eoc-settings.json'
# The drill simulator's inbox for simulated Winlink messages: read with Winlink's own folders, never inside them
DRILL_MIME_DIR = SETTINGS_DIR / 'Simulated Winlink'


def _load_settings() -> dict:
    try:
        s = json.loads(SETTINGS_FILE.read_text(encoding='utf-8-sig'))
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def _save_settings(upd: dict) -> bool:
    s = _load_settings(); s.update(upd)
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(s, indent=2), encoding='utf-8')
        return True
    except Exception as e:
        print(f'  [SETTINGS] Could not save {SETTINGS_FILE}: {e}')
        return False


def _cli_arg(name: str):
    for a in sys.argv[1:]:
        if a.startswith('--' + name + '='):
            return a.split('=', 1)[1]
    return None


def _norm_calls(v) -> list:
    if isinstance(v, str):
        v = v.replace(';', ',').split(',')
    return [str(c).strip().upper() for c in (v or []) if str(c).strip()]


def _winlink_callsigns(watch_path) -> list:
    """The callsign folders of a Winlink install folder (each with a Messages folder), e.g. ['W9TLH', 'W9TLH-3']."""
    p = pathlib.Path(watch_path) if watch_path else None
    try:
        return sorted(d.name.upper() for d in p.iterdir() if d.is_dir() and (d / 'Messages').is_dir() and d.name.lower() != 'global folders') if p and p.is_dir() else []
    except OSError:
        return []


def _winlink_sources(watch_path, callsigns=None) -> list:
    r"""What the watcher scans for a configured path: [(folder, own callsign or '', is_winlink_store)].
    A Winlink install folder gives every <CALLSIGN>\Messages (and Global Folders\Messages); a Messages folder
    inside one gives itself; any other folder is a plain folder of .mime files (tests, the simulator, a USB copy)."""
    p = pathlib.Path(watch_path) if watch_path else None
    if not p or not p.is_dir():
        return []
    try:
        subs = [d for d in p.iterdir() if d.is_dir() and (d / 'Messages').is_dir()]
    except OSError:
        subs = []
    if subs:
        out = [(d / 'Messages', '' if d.name.lower() == 'global folders' else d.name.upper(), True) for d in sorted(subs)]
        if callsigns:   # only the callsign(s) chosen to feed this EOC
            out = [o for o in out if o[1] in callsigns]
        return out
    if p.name.lower() == 'messages' and ((p.parent / 'Data').is_dir() or p.parent.name.lower() == 'global folders'):
        return [(p, '' if p.parent.name.lower() == 'global folders' else p.parent.name.upper(), True)]
    return [(p, '', False)]


def _watcher_view() -> dict:
    """Watcher state plus what it is scanning (for /api/watcher/status, the start-up banner, the simulator)."""
    with _watcher_lock:
        st = dict(_watcher_state)
        st['callsigns'] = list(st.get('callsigns') or [])
    src = _winlink_sources(st.get('watch_path'), st['callsigns'])
    st['available'] = _winlink_callsigns(st.get('watch_path'))
    st['mode'] = 'winlink' if (src and src[0][2]) or st['available'] else ('folder' if src else 'none')
    st['sources'] = [{'path': str(f), 'callsign': c} for f, c, _ in src]
    st['missing'] = [c for c in st['callsigns'] if c not in st['available']] if st['available'] else []
    st['settingsFile'] = str(SETTINGS_FILE)
    st['drillDir'] = str(DRILL_MIME_DIR) if st['mode'] == 'winlink' else ''
    return st


def _sender_call(from_hdr: str) -> str:
    """'W9TLH@winlink.org' or 'Name <w9tlh-3@winlink.org>' -> 'W9TLH' / 'W9TLH-3'."""
    m = re.search(r'([A-Za-z0-9/-]+)@', from_hdr or '')
    return (m.group(1) if m else (from_hdr or '').strip()).upper()

# Internet Drop Folder — accepts Worker Form .txt JSON files from email/text/AirDrop/USB
def _get_documents_dir() -> pathlib.Path:
    """Return the user's My Documents folder (CSIDL_PERSONAL) on Windows.
    EMCOMM_DOCUMENTS overrides it: tests and scratch servers use it so they never watch or write the real
    Documents\\...\\EOC Drop Folder (Windows resolves Documents itself and ignores a scratch USERPROFILE)."""
    override = os.environ.get('EMCOMM_DOCUMENTS', '').strip()
    if override:
        p = pathlib.Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p
    try:
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # 5 = CSIDL_PERSONAL
        p = pathlib.Path(buf.value)
        if p.exists():
            return p
    except Exception:
        pass
    return pathlib.Path(os.environ.get('USERPROFILE', str(pathlib.Path.home()))) / 'Documents'

DROP_FOLDER_DEFAULT  = _get_documents_dir() / 'Church of Jesus Christ EMCOMM' / 'EOC Drop Folder'
DROP_INTERVAL_SEC    = 10
DROP_INGESTED_SUBDIR = 'Ingested'

_drop_lock  = threading.Lock()
_drop_state = {
    'enabled':    False,
    'watch_path': '',
    'last_check': None,
    'ingested':   0,
    'errors':     0,
    'last_file':  '',
}

_watcher_lock = threading.Lock()
_watcher_state = {
    'callsigns':  [],     # Winlink callsign(s) that feed this EOC; empty = every callsign in the folder
    'enabled':    False,
    'watch_path': '',
    'last_check': None,
    'ingested':   0,
    'errors':     0,
    'last_file':  '',
}

# ── Database ──────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()

def get_db():
    conn = sqlite3.connect(str(DB_FILE), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id           TEXT PRIMARY KEY,
                received_ms  INTEGER NOT NULL,
                type         TEXT NOT NULL DEFAULT '',
                data_json    TEXT NOT NULL DEFAULT '{}',
                status       TEXT NOT NULL DEFAULT 'new',
                operator_note TEXT NOT NULL DEFAULT '',
                filename     TEXT NOT NULL DEFAULT '',
                dup_key      TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_msg_ms ON messages(received_ms);
            CREATE TABLE IF NOT EXISTS roster (
                id        TEXT PRIMARY KEY,
                data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS incident (
                singleton INTEGER PRIMARY KEY DEFAULT 1,
                data_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS notes (
                id   TEXT PRIMARY KEY,
                ts   INTEGER NOT NULL,
                text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id         TEXT PRIMARY KEY,
                created_ms INTEGER NOT NULL,
                status     TEXT NOT NULL DEFAULT 'open',
                active     INTEGER NOT NULL DEFAULT 0,
                data_json  TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS comms (
                singleton  INTEGER PRIMARY KEY DEFAULT 1,
                data_json  TEXT NOT NULL DEFAULT '{}',
                updated_ms INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS actions (
                id        TEXT PRIMARY KEY,
                ts        INTEGER NOT NULL,
                status    TEXT NOT NULL DEFAULT 'open',
                akey      TEXT NOT NULL DEFAULT '',
                data_json TEXT NOT NULL DEFAULT '{}',
                event_id  TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_act_ev ON actions(event_id);
        """)
        # Databases from before Emergency Events existed: add the event column,
        # then claim every existing record for the first event.
        for tbl in ('messages', 'roster', 'notes'):
            try:
                conn.execute(f'ALTER TABLE {tbl} ADD COLUMN event_id TEXT NOT NULL DEFAULT ""')
            except sqlite3.OperationalError:
                pass
        _ensure_active_event(conn)
        conn.commit()


# ── Emergency Events ──────────────────────────────────────────────────────────
# An EOC works one Emergency Event at a time. Every message, roster entry and
# note belongs to an event. The Setup tab opens a new event, switches between
# events and closes them; new arrivals always file under the active event.
# The `incident` singleton keeps only this EOC's own identity (level, name,
# units covered, parent EOC, the council and welfare lines above a stake); the event's own fields live in `events`.
# sitrepHrs / sitrepBy: the SITREP interval EOC leadership sets for the event (2, 4, 8, 12 or 24 h)
# and who directed it; lastSitrepTs: when a SITREP was last generated (the wall counts from it).
EVENT_FIELDS = ('name', 'area', 'type', 'startTs', 'ic', 'op', 'opPeriodHrs', 'pace', 'paceTs', 'commsEvent',
                'sitrepHrs', 'sitrepBy', 'lastSitrepTs',
                'rollups', 'lastRollupTs', 'closedTs')
_VIEW_ONLY = ('eventId', 'eventStatus', 'eventCreatedMs')


def _event_from_row(r) -> dict:
    d = json.loads(r['data_json'] or '{}')
    d.update({'id': r['id'], 'status': r['status'] or 'open', 'active': bool(r['active']),
              'createdMs': r['created_ms']})
    return d


def _ensure_active_event(conn) -> str:
    """Return the active event's id, creating or migrating one when none exists."""
    row = conn.execute('SELECT id FROM events WHERE active=1 ORDER BY created_ms DESC LIMIT 1').fetchone()
    if row:
        return row['id']
    newest = conn.execute('SELECT id FROM events ORDER BY created_ms DESC LIMIT 1').fetchone()
    if newest:
        conn.execute('UPDATE events SET active=0')
        conn.execute('UPDATE events SET active=1 WHERE id=?', (newest['id'],))
        return newest['id']
    # First run on this database: build the first event from whatever the old
    # incident record held, and give every existing record to it.
    inc_row = conn.execute('SELECT data_json FROM incident WHERE singleton=1').fetchone()
    inc = json.loads(inc_row['data_json']) if inc_row else {}
    ev = {k: inc[k] for k in EVENT_FIELDS if k in inc}
    eid = str(uuid.uuid4())
    conn.execute('INSERT INTO events (id, created_ms, status, active, data_json) VALUES (?,?,?,1,?)',
                 (eid, int(ev.get('startTs') or time.time() * 1000), 'open', json.dumps(ev)))
    for tbl in ('messages', 'roster', 'notes', 'actions'):
        conn.execute(f'UPDATE {tbl} SET event_id=? WHERE event_id=""', (eid,))
    ident = {k: v for k, v in inc.items() if k not in EVENT_FIELDS}
    conn.execute('INSERT OR REPLACE INTO incident (singleton, data_json) VALUES (1,?)',
                 (json.dumps(ident),))
    return eid


def _active_event(conn) -> dict:
    eid = _ensure_active_event(conn)
    return _event_from_row(conn.execute('SELECT * FROM events WHERE id=?', (eid,)).fetchone())


def _event_counts(conn, eid: str) -> dict:
    out = {'dr': 0, 'so': 0, 'wcl': 0, 'msgs': 0, 'roster': 0, 'notes': 0}
    for r in conn.execute('SELECT type, COUNT(*) AS n FROM messages WHERE event_id=? GROUP BY type', (eid,)):
        t = (r['type'] or '').lower()
        if t in out:
            out[t] = r['n']
        out['msgs'] += r['n']
    out['roster'] = conn.execute('SELECT COUNT(*) FROM roster WHERE event_id=?', (eid,)).fetchone()[0]
    out['notes'] = conn.execute('SELECT COUNT(*) FROM notes WHERE event_id=?', (eid,)).fetchone()[0]
    out['actions'] = conn.execute("SELECT COUNT(*) FROM actions WHERE event_id=? AND status!='done'", (eid,)).fetchone()[0]
    return out


def _list_events(conn) -> list:
    _ensure_active_event(conn)
    out = []
    for r in conn.execute('SELECT * FROM events ORDER BY created_ms DESC').fetchall():
        d = _event_from_row(r)
        d['counts'] = _event_counts(conn, r['id'])
        out.append(d)
    return out


def _update_event(conn, eid: str, changes: dict):
    row = conn.execute('SELECT data_json FROM events WHERE id=?', (eid,)).fetchone()
    if not row:
        return None
    ev = json.loads(row['data_json'] or '{}')
    ev.update(changes)
    conn.execute('UPDATE events SET data_json=? WHERE id=?', (json.dumps(ev), eid))
    return ev


# ── Map data (the geographic dataset, served to the Map tab and the wall) ────
_MAP_TYPES = {'.geojson': 'application/geo+json; charset=utf-8', '.json': 'application/json; charset=utf-8',
              '.png': 'image/png', '.csv': 'text/csv; charset=utf-8', '.txt': 'text/plain; charset=utf-8'}
_map_cache = {}


def _map_dir(path_str: str):
    """The dataset's simulator/ folder for a map path from the Setup tab (the export root or
    the simulator folder itself), or None."""
    p = str(path_str or '').strip()
    if not p:
        return None
    d = pathlib.Path(p).expanduser()
    for cand in (d / 'simulator', d):
        if (cand / 'organization_boundaries.geojson').is_file():
            return cand.resolve()
    return None


def _map_info(path_str: str) -> dict:
    """{ok, path, dir, units, buildings, error}: present or not, with counts (parsed once per file state)."""
    d = _map_dir(path_str)
    if not d:
        return {'ok': False, 'path': str(path_str or ''), 'error': 'no map data folder set' if not str(path_str or '').strip() else 'organization_boundaries.geojson not found under that folder'}
    key = str(d)
    try:
        st = (d / 'organization_boundaries.geojson').stat()
        sig = (st.st_mtime, st.st_size)
        if _map_cache.get(key, {}).get('sig') != sig:
            gj = json.loads((d / 'organization_boundaries.geojson').read_text(encoding='utf-8'))
            feats = gj.get('features', [])
            units = sum(1 for f in feats if f.get('properties', {}).get('org_type') in ('Ward', 'Branch'))
            stakes = sum(1 for f in feats if f.get('properties', {}).get('org_type') == 'Stake')
            b = d / 'buildings.geojson'
            nb = len(json.loads(b.read_text(encoding='utf-8')).get('features', [])) if b.is_file() else 0
            _map_cache[key] = {'sig': sig, 'units': units, 'stakes': stakes, 'buildings': nb}
        c = _map_cache[key]
        return {'ok': True, 'path': str(path_str), 'dir': key, 'units': c['units'], 'stakes': c['stakes'], 'buildings': c['buildings']}
    except Exception as e:
        return {'ok': False, 'path': str(path_str), 'error': f'{type(e).__name__}: {e}'}


def _map_path_setting() -> str:
    """The map data folder saved with the EOC identity (Setup tab). Takes _db_lock: call outside it."""
    with _db_lock:
        conn = get_db()
        try:
            r = conn.execute('SELECT data_json FROM incident WHERE singleton=1').fetchone()
            return (json.loads(r['data_json']) if r else {}).get('mapPath') or ''
        finally:
            conn.close()


def _incident_view(conn) -> dict:
    """What the page calls `incident`: this EOC's identity plus the active event's fields."""
    row = conn.execute('SELECT data_json FROM incident WHERE singleton=1').fetchone()
    inc = json.loads(row['data_json']) if row else {}
    ev = _active_event(conn)
    view = {k: v for k, v in inc.items() if k not in EVENT_FIELDS}
    for k in EVENT_FIELDS:
        if k in ev:
            view[k] = ev[k]
    view['eventId'] = ev['id']
    view['eventStatus'] = ev['status']
    view['eventCreatedMs'] = ev['createdMs']
    return view


DRILL_CONFIG_KIND = 'church_emcomm_drill_config'


def _drill_manned(cfg: dict, manned) -> set:
    """The EOCs with people this time: every 'always' EOC plus the optional ones named (simulation/drillconfig.py)."""
    want = {str(m).strip() for m in (manned or []) if str(m).strip()}
    return {e['id'] for e in cfg.get('eocs', []) if e.get('manned', 'always') == 'always' or e['id'] in want}


def _apply_drill_config(cfg: dict, eoc_id: str, manned=None, new_event: bool = True) -> dict:
    """Set this EOC up from a drill configuration: identity, map folder, Winlink call sign(s) and the drill event.
    Opens the drill event unless the active event already has its name (applying again at every start is safe).
    Takes _db_lock: call outside it."""
    if not isinstance(cfg, dict) or cfg.get('kind') != DRILL_CONFIG_KIND:
        raise ValueError('not a drill configuration (church_emcomm_drill_config)')
    e = next((x for x in cfg.get('eocs', []) if x.get('id') == eoc_id), None)
    if not e:
        raise ValueError(f"no EOC {eoc_id!r} in this configuration; choose one of: " + ', '.join(x.get('id', '') for x in cfg.get('eocs', [])))
    on = _drill_manned(cfg, manned)
    ident = json.loads(json.dumps(e.get('identity') or {}))
    if ident.get('mapPath') and not _map_dir(ident['mapPath']):
        # a configuration built on another computer (a participant package): its map folder is not here, so keep
        # the map data folder this EOC already has (Setup -> This EOC -> Map data folder)
        ident.pop('mapPath', None)
    if cfg.get('area') in on and e.get('level') != 'area':
        ident.update(e.get('ifAreaManned') or {})
    ev_spec = dict(cfg.get('event') or {})
    opened = False
    with _db_lock:
        conn = get_db()
        try:
            view = _incident_view(conn)
            if new_event and ev_spec.get('name') and view.get('name') != ev_spec['name']:
                ev = {k: ev_spec[k] for k in EVENT_FIELDS if k in ev_spec and k not in ('rollups', 'lastRollupTs', 'closedTs')}
                ev.setdefault('startTs', int(time.time() * 1000))
                eid = str(uuid.uuid4())
                conn.execute('UPDATE events SET active=0')
                conn.execute('INSERT INTO events (id, created_ms, status, active, data_json) VALUES (?,?,?,1,?)',
                             (eid, int(time.time() * 1000), 'open', json.dumps(ev)))
                conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                             (str(uuid.uuid4()), int(time.time() * 1000), f"Emergency Event opened from the drill configuration: {ev_spec['name']}", eid))
                opened = True
                view = _incident_view(conn)
            roles = dict(view.get('roles') or {})
            roles.update(ident.pop('roles', {}) or {})
            view.update(ident)
            view['roles'] = roles
            view['drillConfig'] = {'name': cfg.get('name', ''), 'eoc': eoc_id, 'manned': sorted(on), 'appliedMs': int(time.time() * 1000)}
            _save_incident_view(conn, view)
            conn.commit()
        finally:
            conn.close()
    calls = [str(c).upper() for c in (e.get('winlink') or [])]
    if calls:
        with _watcher_lock:
            _watcher_state['callsigns'] = calls
            if not _watcher_state.get('watch_path'):
                _watcher_state['watch_path'] = str(WINLINK_DEFAULT_PATH)
            _watcher_state['enabled'] = pathlib.Path(_watcher_state['watch_path']).exists()
            keep = {'winlinkFolder': _watcher_state['watch_path'], 'winlinkCallsigns': calls, 'winlinkWatch': True}
        _save_settings(keep)
    # keep a copy so the next start applies it again (identity and call sign; it never reopens the drill event)
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        (SETTINGS_DIR / 'drill-config.json').write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
        _save_settings({'drillEoc': eoc_id, 'drillManned': sorted(on)})
    except Exception as _se:
        print(f'  [CONFIG] Could not keep a copy for the next start: {_se}')
    print(f"  [CONFIG] {cfg.get('name', 'Drill')}: this EOC is {e.get('name', eoc_id)}; with people: {', '.join(sorted(on))}"
          + ('; drill event opened' if opened else '') + (f"; Winlink {', '.join(calls)}" if calls else ''))
    return {'ok': True, 'eoc': eoc_id, 'name': e.get('name', ''), 'manned': sorted(on), 'eventOpened': opened,
            'winlink': calls, 'mapPath': ident.get('mapPath', '')}


def _save_incident_view(conn, body):
    """PUT /api/incident: identity fields go to the singleton, event fields to the event
    the page was looking at (its eventId), which is normally the active one."""
    body = body if isinstance(body, dict) else {}
    ident = {k: v for k, v in body.items() if k not in EVENT_FIELDS and k not in _VIEW_ONLY}
    conn.execute('INSERT OR REPLACE INTO incident (singleton, data_json) VALUES (1,?)',
                 (json.dumps(ident),))
    eid = str(body.get('eventId') or '')
    if not eid or not conn.execute('SELECT id FROM events WHERE id=?', (eid,)).fetchone():
        eid = _ensure_active_event(conn)
    _update_event(conn, eid, {k: body[k] for k in EVENT_FIELDS if k in body})


def _event_name(conn) -> str:
    ev = _active_event(conn)
    return ev.get('name') or '(unnamed event)'

# ── Backup helpers ────────────────────────────────────────────────────────────

def dump_all_data():
    """Return a snapshot of all EOC data as a JSON-serialisable dict."""
    with _db_lock:
        conn = get_db()
        try:
            messages = [dict(r) for r in conn.execute(
                'SELECT * FROM messages ORDER BY received_ms ASC').fetchall()]
            roster = []
            for r in conn.execute('SELECT data_json, event_id FROM roster').fetchall():
                d = json.loads(r['data_json']); d['eventId'] = r['event_id']; roster.append(d)
            row = conn.execute('SELECT data_json FROM incident WHERE singleton=1').fetchone()
            incident = json.loads(row['data_json']) if row else {}
            notes = [dict(r) for r in conn.execute(
                'SELECT id, ts, text, event_id FROM notes ORDER BY ts ASC').fetchall()]
            events = _list_events(conn)
            comms = _get_comms(conn)
            actions = [_action_row(r) for r in conn.execute('SELECT * FROM actions ORDER BY ts ASC').fetchall()]
        finally:
            conn.close()
    return {
        'exported_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'exported_at_ms': int(time.time() * 1000),
        'version': VERSION,
        'events': events,            # every Emergency Event, active one flagged
        'messages': messages,        # every event's messages (event_id on each)
        'roster': roster,
        'incident': incident,        # this EOC's identity only
        'notes': notes,
        'comms': comms,              # the standing Comms Sheet
        'actions': actions,          # work items (every event's; eventId on each)
    }


def write_json_backup(dest_dir: pathlib.Path, label: str = '') -> pathlib.Path:
    """Write a timestamped JSON export into dest_dir. Returns the file path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    suffix = f'_{label}' if label else ''
    out = dest_dir / f'eoc_backup_{ts}{suffix}.json'
    data = dump_all_data()
    out.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
    return out


def timed_backup_loop():
    """Background thread: write a JSON backup every BACKUP_INTERVAL_SEC seconds."""
    while True:
        time.sleep(BACKUP_INTERVAL_SEC)
        try:
            out = write_json_backup(BACKUP_DIR)
            # Trim old backups — keep only the newest MAX_BACKUPS files
            old = sorted(BACKUP_DIR.glob('eoc_backup_*.json'))[:-MAX_BACKUPS]
            for f in old:
                f.unlink(missing_ok=True)
            data = json.loads(out.read_text(encoding='utf-8'))
            print(f'  [BACKUP] {out.name}  ({len(data["messages"])} messages)')
        except Exception as exc:
            print(f'  [BACKUP] Auto-backup failed: {exc}')


def get_removable_drives():
    """Return root paths of all removable drives: Windows drive letters of type REMOVABLE (ctypes, no pip);
    on macOS the mounted volumes under /Volumes except the boot volume; on Linux the user's /media and /run/media mounts."""
    if sys.platform != 'win32':
        try:
            roots = [pathlib.Path('/Volumes')] if sys.platform == 'darwin' else [pathlib.Path('/media') / os.environ.get('USER', ''), pathlib.Path('/run/media') / os.environ.get('USER', '')]
            out = []
            for root in roots:
                if root.is_dir():
                    for p in root.iterdir():
                        try:
                            if p.is_dir() and not p.is_symlink() and p.resolve() != pathlib.Path('/').resolve():
                                out.append(str(p))
                        except Exception:
                            pass
            return out
        except Exception:
            return []
    try:
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                root = f'{letter}:\\'
                if ctypes.windll.kernel32.GetDriveType(root) == 2:  # DRIVE_REMOVABLE
                    drives.append(root)
            bitmask >>= 1
        return drives
    except Exception:
        return []


def usb_watchdog_loop():
    """Background thread: detect newly inserted USB drives and back up to them."""
    known = set(get_removable_drives())
    while True:
        time.sleep(5)
        try:
            current = set(get_removable_drives())
            for drive in current - known:
                print(f'  [USB]   Drive inserted: {drive}')
                try:
                    dest = pathlib.Path(drive) / USB_FOLDER
                    # Copy the live SQLite file
                    if DB_FILE.exists():
                        dest.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(DB_FILE), str(dest / 'eoc_data.db'))
                    # Also write a human-readable JSON export
                    out = write_json_backup(dest, label='usb')
                    data = json.loads(out.read_text(encoding='utf-8'))
                    print(f'  [USB]   Backed up to {dest}  ({len(data["messages"])} messages)')
                except Exception as exc:
                    print(f'  [USB]   Backup to {drive} failed: {exc}')
            known = current
        except Exception as exc:
            print(f'  [USB]   Watchdog error: {exc}')


# ── Winlink Watcher ──────────────────────────────────────────────────────────

def _parse_mime_file(path: pathlib.Path) -> dict:
    """Parse a Winlink .mime file; return from_, to, subject, date, msg_id, body,
    and any .json attachments (roll-up bundles from a Satellite or Stake EOC)."""
    raw = path.read_bytes()
    msg = _email.message_from_bytes(raw)
    body = ''
    attachments = []   # list of (filename, text) for *.json attachments
    txt_attachments = []   # (filename, text) for *.txt attachments
    xml_attachments = []   # (filename, text) for *.xml attachments (Winlink standard forms: ICS 213, 213RR, ...)
    if msg.is_multipart():
        for part in msg.walk():
            fname = part.get_filename() or ''
            ctype = part.get_content_type()
            if fname.lower().endswith('.xml') or ctype in ('text/xml', 'application/xml'):
                pl = part.get_payload(decode=True)
                if pl:
                    xml_attachments.append((fname or 'form.xml', pl.decode('utf-8-sig', errors='replace')))
                continue
            if fname.lower().endswith('.json') or ctype == 'application/json':
                pl = part.get_payload(decode=True)
                if pl:
                    attachments.append((fname or 'attachment.json', pl.decode('utf-8-sig', errors='replace')))
                continue
            if fname.lower().endswith('.txt'):
                pl = part.get_payload(decode=True)
                if pl:
                    txt_attachments.append((fname, pl.decode('utf-8-sig', errors='replace')))
                continue
            if ctype == 'text/plain' and not body:
                pl = part.get_payload(decode=True)
                if pl:
                    body = pl.decode('utf-8', errors='replace')
    else:
        pl = msg.get_payload(decode=True)
        body = pl.decode('utf-8', errors='replace') if pl else (msg.get_payload() or '')
    # Templates before 2026-10-28 named the body field "attached_text", which Winlink
    # never substitutes: those messages went out with the literal "<var attached_text>"
    # as the body and the report inside a .txt attachment. Read the attachment then.
    if '[Church-' not in body:
        for _name, atext in txt_attachments:
            if '[Church-' in atext:
                body = atext
                break
    return {
        'from_':   str(msg.get('From',       '')),
        'to':      str(msg.get('To',         '')),
        'subject': ' '.join(str(msg.get('Subject', '')).split()),   # a long subject arrives folded over lines
        'date':    str(msg.get('Date',       '')),
        'msg_id':  str(msg.get('Message-ID', '')).strip('<>'),
        'body':    body,
        'attachments': attachments,
        'xml':     xml_attachments,
    }


# ── Partner agencies (a city EOC that does not run this system): Winlink ICS 213 / ICS 213RR ─────────────
ICS_KINDS = {'ics213rr': 'ICS 213RR Resource Request', 'ics213': 'ICS 213 General Message'}


def _parse_ics(mime: dict):
    """An ICS 213 General Message or ICS 213RR Resource Request sent with Winlink's standard templates:
    {'form', 'fields'} from the RMS_Express_Form XML when attached, else from the message text. None otherwise."""
    import xml.etree.ElementTree as _ET
    for name, text in mime.get('xml') or []:
        try:
            root = _ET.fromstring(text.encode('utf-8'))
        except Exception:
            continue
        disp = (root.findtext('form_parameters/display_form') or name or '').upper().replace(' ', '').replace('-', '').replace('_', '')
        if 'ICS213' not in disp:
            continue
        form = 'ics213rr' if 'ICS213RR' in disp else 'ics213'
        fields = {c.tag: (c.text or '').strip() for c in root.find('variables') or [] if (c.text or '').strip()}
        return {'form': form, 'fields': fields}
    head = (mime.get('subject', '') + '\n' + mime.get('body', '')[:400]).upper().replace('-', ' ')
    if 'ICS 213RR' in head or 'RESOURCE REQUEST MESSAGE' in head:
        form = 'ics213rr'
    elif 'ICS 213' in head or 'GENERAL MESSAGE' in head:
        form = 'ics213'
    else:
        return None
    fields = {}
    for line in mime.get('body', '').splitlines():
        if ':' in line and len(line) < 400:
            k, v = line.split(':', 1)
            k = re.sub(r'[^a-z0-9]+', '_', k.strip().lower()).strip('_')[:40]
            if k and v.strip():
                fields[k] = v.strip()
    return {'form': form, 'fields': fields}


def _agency_for(conn, from_hdr: str) -> dict:
    """The partner agency whose Winlink call sign sent the message (EOC identity `agencies`), or one named by the call."""
    call = _sender_call(from_hdr)
    try:
        ags = (_incident_view(conn).get('agencies') or [])
    except Exception:
        ags = []
    for a in ags:
        if isinstance(a, dict) and call and call in [c.strip().upper() for c in str(a.get('call', '')).split(',')]:
            return a
    return {'name': call or 'Partner agency', 'call': call}


def _ingest_ics(mime: dict, ics: dict, filename: str) -> bool:
    """File an agency's ICS message: a note in the log and a work item (a resource request asks for a decision
    and an answer by ICS 213). Takes _db_lock. Returns False for a duplicate (same Message-ID)."""
    f = ics['fields']
    def pick(*keys):   # simulator names (qty, item) and Winlink's standard ones (Qty1, Item1, Priority, Subject)
        for k in keys:
            for fk, v in f.items():
                if k in fk.lower() and v:
                    return v
        return ''
    with _db_lock:
        conn = get_db()
        try:
            eid = _ensure_active_event(conn)
            key = 'ics:' + (mime.get('msg_id') or filename)
            if conn.execute('SELECT id FROM actions WHERE akey=? AND event_id=?', (key, eid)).fetchone():
                return False
            ag = _agency_for(conn, mime.get('from_', ''))
            who = ag.get('name') or 'Partner agency'
            call = ag.get('call') or _sender_call(mime.get('from_', ''))
            subj = re.sub(r'^\s*ICS[\s-]*213(RR)?\s*[-:]\s*', '', mime.get('subject', ''), flags=re.I).strip()
            if ics['form'] == 'ics213rr':
                qty = pick('qty', 'quantity')
                # Winlink's own subject is "ICS 213RR- <incident>- Request #:<number>": name the first item instead
                generic = not subj or re.search(r'request\s*#', subj, re.I)
                what = (pick('item', 'description', 'resource', 'type', 'kind') if generic else subj) or subj
                rnum = pick('reqnum', 'request_number')
                if generic and rnum:
                    what = f'{what} [#{rnum}]'
                title = f'{who} resource request (ICS 213RR): {what}' + (f' ({qty})' if qty else '')
                title = title[:200]
                prio = 1 if re.search(r'urgent|immediate|life', pick('priority'), re.I) else 2
                cat, nxt = 'assist', f'Decide with the ERD and the Stake President; answer {who} by ICS 213 (Winlink to {call}): who comes, how many, crew leader, when'
            else:
                title = f'{who} message (ICS 213): {pick("subject") or subj}'[:200]
                prio, cat = 2, 'other'
                nxt = f'Read it to the ERD; answer {who} by ICS 213 (Winlink to {call}) if it asks something'
            detail = '\n'.join(f'{k.replace("_", " ")}: {v}' for k, v in f.items())[:4000]
            now = int(time.time() * 1000)
            res = _create_action(conn, eid, {'title': title, 'detail': detail, 'cat': cat, 'prio': prio, 'next': nxt, 'key': key,
                                             'from': f'{who} ({call})' if call else who, 'who': 'auto'})
            conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                         (str(uuid.uuid4()), now, f'{ICS_KINDS[ics["form"]]} received by Winlink from {who}' + (f' ({call})' if call else '')
                          + f': {subj or title}', eid))
            conn.commit()
            return bool(res.get('ok'))
        finally:
            conn.close()


# ── Roll-up bundles (Satellite EOC -> Stake EOC -> Council / Area EOC, when one is open) ─────────────────
# A roll-up is the same JSON shape as a shift-handoff export, plus "kind" and
# "from". Any EOC can export one; the EOC above it merges it. Merging never
# replaces: a record is skipped if its id, its dupKey, or its form content
# (formKey) is already in the database, so the same report can arrive by
# Winlink forward AND by roll-up without being counted twice.

def _fnv1a(s: str) -> str:
    """32-bit FNV-1a hex digest. Mirrors fnv1a() in EOC_Message_Center.html —
    both sides must produce identical formKeys."""
    h = 0x811C9DC5
    for b in s.encode('utf-8'):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f'{h:08x}'


def _form_key(record: dict) -> str:
    """Content key for a message record: type + hash of its sub-object (trimmed
    string values, sorted keys, no whitespace)."""
    t = (record.get('type') or '').lower()
    sub = record.get(t) or {}
    canon = {}
    for k in sorted(sub.keys()):
        v = sub[k]
        canon[k] = v.strip() if isinstance(v, str) else v
    js = json.dumps(canon, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return f'form:{t}:{_fnv1a(js)}'


def _looks_like_bundle(data) -> bool:
    return isinstance(data, dict) and (isinstance(data.get('msgs'), list) or _looks_like_reply(data))


# ── Values that arrive from another EOC (roll-ups, replies, the Drop Folder, Winlink attachments) ──
# The pages put record ids into onclick handlers and statuses into badges, so a bundle from outside
# may only bring plain ids and known statuses; anything else gets a fresh id / the default status.
_SAFE_ID_RE = re.compile(r'^[A-Za-z0-9_.:-]{1,64}$')
MSG_TYPES = ('dr', 'so', 'wcl')
MSG_STATUSES = ('new', 'ack', 'assigned', 'complete')


def _safe_id(v) -> str:
    s = str(v) if isinstance(v, (str, int)) and not isinstance(v, bool) else ''
    return s if _SAFE_ID_RE.match(s) else str(uuid.uuid4())


def _ms(v, default=None) -> int:
    """A millisecond timestamp from outside: a number (or numeric text) in range, else `default` (now)."""
    try:
        n = int(float(v))
        if 0 < n < 10 ** 14:
            return n
    except (TypeError, ValueError, OverflowError):
        pass
    return int(time.time() * 1000) if default is None else default


def _clean_log(log) -> list:
    if not isinstance(log, list):
        return []
    return [{'ts': _ms(l.get('ts')), 'who': str(l.get('who') or '')[:80], 'text': str(l.get('text') or '')[:500]}
            for l in log if isinstance(l, dict)][-100:]


def _sender_name(data: dict, fallback: str) -> tuple:
    """(from-dict, display name) of a bundle's sender, whatever shape `from` has."""
    frm = data.get('from') if isinstance(data.get('from'), dict) else {}
    name = frm.get('name') or data.get('exportedBy') or fallback
    return frm, str(name)[:80]


# ── Replies down the chain ────────────────────────────────────────────────────
# A roll-up carries the work items an EOC set UP (waiting on the line above) to the parent EOC.
# The parent answers with a reply bundle: {"kind": "church_eoc_reply", "from": {name, level},
# "replies": [{id, key, title, status, decision, text}], "notes": [...]}. It travels the same
# ways a roll-up does (email, Winlink attachment, USB, the Drop Folder, or straight to the
# child's /api/merge on the LAN) and closes the items it names with the decision, logged.
REPLY_KIND = 'church_eoc_reply'


def _looks_like_reply(data) -> bool:
    return isinstance(data, dict) and data.get('kind') == REPLY_KIND and isinstance(data.get('replies'), list)


def _apply_reply_locked(conn, data: dict) -> dict:
    frm = data.get('from') if isinstance(data.get('from'), dict) else {}
    via = str(frm.get('name') or 'the line above')[:80]
    eid = _ensure_active_event(conn)
    now = int(time.time() * 1000)
    applied, missing = 0, []
    for rp in data.get('replies') or []:
        if not isinstance(rp, dict):
            continue
        row = None
        if rp.get('id'):
            row = conn.execute('SELECT * FROM actions WHERE id=? AND event_id=?', (str(rp['id']), eid)).fetchone()
        if row is None and rp.get('key'):
            row = conn.execute('SELECT * FROM actions WHERE akey=? AND event_id=?', (str(rp['key']), eid)).fetchone()
        if row is None and rp.get('title'):
            row = conn.execute('SELECT * FROM actions WHERE event_id=? AND status=? ORDER BY ts', (eid, 'up')).fetchall()
            row = next((r for r in row if json.loads(r['data_json'] or '{}').get('title') == rp['title']), None)
        if row is None:
            missing.append(str(rp.get('title') or rp.get('id') or '?'))
            continue
        d = json.loads(row['data_json'] or '{}')
        status = rp.get('status') if rp.get('status') in ACTION_STATUSES else 'done'
        decision = str(rp.get('decision') or '').strip()
        if decision:
            d['decision'] = decision
        d['replied'] = {'from': via, 'ts': now, 'text': str(rp.get('text') or '')[:400]}
        log = d.get('log') if isinstance(d.get('log'), list) else []
        log.append({'ts': now, 'who': via, 'text': f"Reply from {via}: " + (decision or str(rp.get('text') or 'answered'))[:300]})
        if status != row['status']:
            log.append({'ts': now, 'who': via, 'text': 'Status: ' + {'open': 'open', 'progress': 'in work', 'up': 'waiting on the line above', 'done': 'done'}[status]})
        d['log'] = log[-100:]
        d['updatedTs'] = now
        conn.execute('UPDATE actions SET status=?, data_json=? WHERE id=?', (status, json.dumps(d), row['id']))
        applied += 1
    notes_new = 0
    for n in data.get('notes') or []:
        if not isinstance(n, dict) or not n.get('text'):
            continue
        txt = str(n['text'])[:4000]
        txt = txt if txt.startswith('[') else f'[{via}] {txt}'
        cur = conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                           (_safe_id(n.get('id')), _ms(n.get('ts'), now), txt, eid))
        notes_new += cur.rowcount if cur.rowcount > 0 else 0
    conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                 (str(uuid.uuid4()), now, f'Reply received from {via}: {applied} work item(s) answered'
                  + (f'; not found here: {", ".join(missing)[:200]}' if missing else ''), eid))
    conn.commit()
    return {'ok': True, 'kind': REPLY_KIND, 'from': via, 'replies_applied': applied, 'missing': missing, 'notes_new': notes_new,
            'new': 0, 'dup': 0, 'roster_new': 0, 'actions_new': 0}


# ── Comms Sheet (stake contacts, Winlink addresses, gateways, voice nets) ─────
# One standing sheet per EOC, kept in the `comms` singleton; event-specific
# changes live on the event (EVENT_FIELDS 'commsEvent'). The sheet travels as a
# small JSON file ({"kind": "church_comms_sheet", "sheet": {...}, "updatedMs"})
# by email, Winlink attachment, USB or the Drop Folder, and a newer copy
# replaces the one on file — so one specialist edits it and every EOC above and
# below gets the same sheet.
COMMS_KIND = 'church_comms_sheet'


def _looks_like_comms(data) -> bool:
    return isinstance(data, dict) and data.get('kind') == COMMS_KIND and isinstance(data.get('sheet'), dict)


def _get_comms(conn) -> dict:
    row = conn.execute('SELECT data_json, updated_ms FROM comms WHERE singleton=1').fetchone()
    if not row:
        return {'sheet': {}, 'updatedMs': 0}
    try:
        sheet = json.loads(row['data_json'])
    except Exception:
        sheet = {}
    return {'sheet': sheet if isinstance(sheet, dict) else {}, 'updatedMs': row['updated_ms'] or 0}


def _put_comms(conn, sheet: dict, updated_ms=None) -> int:
    ms = int(updated_ms or time.time() * 1000)
    conn.execute('INSERT OR REPLACE INTO comms (singleton, data_json, updated_ms) VALUES (1,?,?)',
                 (json.dumps(sheet if isinstance(sheet, dict) else {}), ms))
    return ms


def _import_comms(data: dict, conn=None, via: str = '') -> dict:
    """Take a comms-sheet file on board if it is newer than the one on file."""
    if conn is not None:
        return _import_comms_locked(conn, data, via)
    with _db_lock:
        c = get_db()
        try:
            return _import_comms_locked(c, data, via)
        finally:
            c.close()


def _import_comms_locked(conn, data: dict, via: str = '') -> dict:
    cur = _get_comms(conn)
    inc_ms = int(data.get('updatedMs') or 0)
    frm = (data.get('from') or {}).get('name') or via or 'another EOC'
    if cur['sheet'] and inc_ms and inc_ms <= cur['updatedMs']:
        return {'imported': False, 'from': frm, 'updatedMs': cur['updatedMs'],
                'reason': 'the sheet on file is the same or newer'}
    ms = _put_comms(conn, data['sheet'], inc_ms or None)
    eid = _ensure_active_event(conn)
    stamp = time.strftime('%Y-%m-%d %H:%M', time.localtime(ms / 1000))
    conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                 (str(uuid.uuid4()), int(time.time() * 1000),
                  f'Comms sheet received from {frm} (sheet dated {stamp}) — replaces the one on file', eid))
    conn.commit()
    return {'imported': True, 'from': frm, 'updatedMs': ms}


# ── Work Items ────────────────────────────────────────────────────────────────
# The things in the reports that somebody at this EOC has to act on or decide:
# missionaries not accounted for, injuries and deaths, each "assistance needed"
# answer, every Supply Order awaiting approval, a crew without its safety
# briefing. They are extracted here when a report is filed (any path), so every
# operator's Work Items tab shows the same list, and the operators add their own.
# Item: {id, ts, status open|progress|up|done, key, cat, prio 1..3, title, detail,
#        unit, owner, next, decision, due, src:{id,type}, auto, from, log:[{ts,who,text}]}
ACTION_FIELDS = ('title', 'detail', 'cat', 'prio', 'unit', 'owner', 'next', 'decision', 'due', 'src', 'auto', 'from', 'fromEoc', 'key', 'replied')
ACTION_STATUSES = ('open', 'progress', 'up', 'done')


def _yes(v) -> bool:
    return str(v or '').strip().upper() in ('YES', 'Y')


def _no(v) -> bool:
    return str(v or '').strip().upper() in ('NO', 'N')


def _int(v) -> int:
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return 0


def _is_exercise(v) -> bool:
    """The THIS IS AN EXERCISE flag as a form sends it: YES from a Winlink template or tag,
    true from a Worker form checkbox."""
    return str(v if v is not None else '').strip().lower() in ('yes', '1', 'true', 'on')


def _derive_actions(rec: dict) -> list:
    """Work items a filed report asks for. Deterministic keys: the same report never
    makes the same item twice (uploads, Drop Folder copies and roll-ups dedupe)."""
    t = (rec.get('type') or '').lower()
    sub = rec.get(t) or {}
    if not isinstance(sub, dict):
        return []
    ex = 'EXERCISE: ' if _is_exercise(sub.get('exercise')) else ''
    mid = str(rec.get('id') or '')
    fields = rec.get('fields') if isinstance(rec.get('fields'), dict) else {}
    out = []

    def item(kind, cat, prio, title, detail='', nxt=''):
        out.append({'key': f'{t}:{kind}:{mid}', 'cat': cat, 'prio': prio, 'title': ex + title, 'detail': detail,
                    'next': nxt, 'unit': unit, 'src': {'id': mid, 'type': t}, 'auto': True})

    if t == 'dr':
        unit = sub.get('ward') or sub.get('stake') or '?'
        if _no(sub.get('miss_safe')):
            item('miss', 'missionaries', 1, f'Missionaries not accounted for: {unit}',
                 fields.get('miss_details', ''), 'Tell the Stake President now; contact the mission office')
        inj, dead = _int(sub.get('mem_inj')), _int(sub.get('mem_dead'))
        if inj or dead:
            item('life', 'life', 1, f'{inj} injured / {dead} deaths reported: {unit}',
                 fields.get('mem_details', ''), 'Confirm names and care with the bishop; report up')
        if _yes(sub.get('need_hq')):
            item('hq', 'upward', 1, f'Church headquarters assistance requested: {unit}',
                 sub.get('needs_details') or fields.get('needs_details', ''), 'Send up the welfare line with the SITREP')
        if _yes(sub.get('need_neighbor')):
            item('nbr', 'assist', 2, f'Neighboring unit assistance needed: {unit}',
                 sub.get('needs_details') or fields.get('needs_details', ''), 'Match with a unit that has crews free')
        if _yes(sub.get('need_local')):
            item('local', 'facilities', 2, f'Local Church facilities needed: {unit}',
                 sub.get('needs_details') or fields.get('needs_details', ''), 'Decide which building opens; tell the facilities manager')
        dest = _int(sub.get('homes_dest'))
        if dest:
            item('shelter', 'facilities', 2, f'{dest} homes destroyed, shelter check: {unit}', '', 'Confirm every family has a place to sleep tonight')
        if str(sub.get('bldg_damage') or fields.get('bldg_damage') or '').strip():
            item('bldg', 'facilities', 2, f'Church building damage reported: {unit}',
                 str(sub.get('bldg_damage') or fields.get('bldg_damage') or ''), 'Have the facilities manager inspect before use')
    elif t == 'so':
        unit = sub.get('stake') or '?'
        n = len([p for p in str(sub.get('items') or '').split(';') if p.strip()])
        need = sub.get('del_date') or ''
        item('approve', 'supply', 2, f'Supply Order: {n} item type{"" if n == 1 else "s"}, {unit}' + (f', needed by {need}' if need else ''),
             str(sub.get('items') or '')[:200], 'ERD and welfare line approval, then confirm delivery point and receiver')
    elif t == 'wcl':
        unit = sub.get('chief_ward') or sub.get('chief_stake') or '?'
        if _no(sub.get('safety')):
            item('safety', 'life', 2, f'Crew without safety briefing: {sub.get("chief") or "?"} ({unit})', '', 'Reach the crew chief; no work until the briefing is given')
    return out


def _file_actions(conn, eid: str, rec: dict) -> int:
    """Insert the work items a newly filed report calls for (skipping keys already on file)."""
    n = 0
    now = int(time.time() * 1000)
    for a in _derive_actions(rec):
        if conn.execute('SELECT id FROM actions WHERE akey=? AND event_id=?', (a['key'], eid)).fetchone():
            continue
        a['log'] = [{'ts': now, 'who': 'auto', 'text': 'From the report as filed'}]
        conn.execute('INSERT OR IGNORE INTO actions (id, ts, status, akey, data_json, event_id) VALUES (?,?,?,?,?,?)',
                     (str(uuid.uuid4()), now, 'open', a['key'], json.dumps(a), eid))
        n += 1
    return n


def _action_row(r) -> dict:
    d = json.loads(r['data_json'] or '{}')
    d.update({'id': r['id'], 'ts': r['ts'], 'status': r['status'] or 'open', 'key': r['akey'] or d.get('key', ''),
              'eventId': r['event_id']})
    return d


def _list_actions(conn, eid: str) -> list:
    return [_action_row(r) for r in conn.execute('SELECT * FROM actions WHERE event_id=? ORDER BY ts ASC', (eid,)).fetchall()]


def _clean_action(body: dict) -> dict:
    a = {k: body[k] for k in ACTION_FIELDS if k in body}
    a['title'] = str(a.get('title') or '').strip()
    a['prio'] = _int(a.get('prio')) or 2
    if a['prio'] not in (1, 2, 3):
        a['prio'] = 2
    for k in ('detail', 'cat', 'unit', 'owner', 'next', 'decision', 'due', 'from', 'key'):
        if k in a:
            a[k] = str(a[k] or '')
    src = a.get('src')
    if isinstance(src, dict) and _SAFE_ID_RE.match(str(src.get('id') or '')):
        a['src'] = {'id': str(src['id']), 'type': str(src.get('type') or '').lower()[:8]}
    else:
        a.pop('src', None)
    return a


def _create_action(conn, eid: str, body: dict) -> dict:
    """POST /api/actions: a new work item (an operator's own, or one the page derived, e.g. an
    overdue unit). A `key` already on file for the event returns the existing item instead."""
    a = _clean_action(body)
    if not a['title']:
        return {'ok': False, 'error': 'A work item needs a title'}
    key = a.get('key') or ''
    if key:
        row = conn.execute('SELECT * FROM actions WHERE akey=? AND event_id=?', (key, eid)).fetchone()
        if row:
            return {'ok': True, 'duplicate': True, 'item': _action_row(row)}
    aid = str(body.get('id') or uuid.uuid4())
    ts = int(body.get('ts') or time.time() * 1000)
    status = body.get('status') if body.get('status') in ACTION_STATUSES else 'open'
    who = str(body.get('who') or '')
    log = body.get('log') if isinstance(body.get('log'), list) else []
    a['log'] = (log or [{'ts': ts, 'who': who, 'text': 'Added'}])[-100:]
    a.setdefault('auto', False)
    conn.execute('INSERT OR IGNORE INTO actions (id, ts, status, akey, data_json, event_id) VALUES (?,?,?,?,?,?)',
                 (aid, ts, status, key, json.dumps(a), eid))
    return {'ok': True, 'item': _action_row(conn.execute('SELECT * FROM actions WHERE id=?', (aid,)).fetchone())}


def _update_action(conn, aid: str, body: dict):
    """PATCH /api/actions/<id>: change fields, status, and append a log line."""
    row = conn.execute('SELECT * FROM actions WHERE id=?', (aid,)).fetchone()
    if not row:
        return None
    d = json.loads(row['data_json'] or '{}')
    changes = _clean_action({k: v for k, v in body.items() if k in ACTION_FIELDS and k != 'key'})
    changes.pop('key', None)
    if not changes.get('title'):
        changes.pop('title', None)      # a partial PATCH (the phone page sends only owner / status) never blanks the title
    if 'prio' not in body:
        changes.pop('prio', None)
    d.update(changes)
    now = int(time.time() * 1000)
    who = str(body.get('who') or '')
    log = d.get('log') if isinstance(d.get('log'), list) else []
    status = row['status']
    if 'owner' in changes and changes['owner'] != str(json.loads(row['data_json'] or '{}').get('owner') or ''):
        log.append({'ts': now, 'who': who, 'text': 'Owner: ' + (changes['owner'] or 'nobody')})
    if body.get('status') in ACTION_STATUSES and body['status'] != status:
        status = body['status']
        log.append({'ts': now, 'who': who, 'text': 'Status: ' + {'open': 'open', 'progress': 'in work', 'up': 'waiting on the line above', 'done': 'done'}[status]})
    if str(body.get('log') or '').strip():
        log.append({'ts': now, 'who': who, 'text': str(body['log']).strip()})
    d['log'] = log[-100:]
    d['updatedTs'] = now
    conn.execute('UPDATE actions SET status=?, data_json=? WHERE id=?', (status, json.dumps(d), aid))
    return _action_row(conn.execute('SELECT * FROM actions WHERE id=?', (aid,)).fetchone())


def _merge_bundle(data: dict, via_label: str = '', conn=None) -> dict:
    """Merge a roll-up / handoff bundle into the database. Returns counts.
    Pass an open `conn` when the caller already holds _db_lock (the lock is not
    re-entrant); otherwise the lock is taken here."""
    if conn is not None:
        return _merge_bundle_locked(conn, data, via_label)
    with _db_lock:
        c = get_db()
        try:
            return _merge_bundle_locked(c, data, via_label)
        finally:
            c.close()


def _merge_bundle_locked(conn, data: dict, via_label: str = '') -> dict:
    if _looks_like_reply(data):
        return _apply_reply_locked(conn, data)
    frm, via = _sender_name(data, 'another EOC')
    via = str(via_label)[:80] if via_label else via
    new = dup = roster_new = notes_new = actions_new = bad = 0
    if True:
        try:
            eid = _ensure_active_event(conn)   # a roll-up files under the event we are working
            rows = conn.execute('SELECT id, dup_key, data_json FROM messages WHERE event_id=?', (eid,)).fetchall()
            ids = set(); dups = set(); forms = set()
            for r in rows:
                ids.add(r['id'])
                if r['dup_key']:
                    dups.add(r['dup_key'])
                try:
                    forms.add(_form_key(json.loads(r['data_json'])))
                except Exception:
                    pass
            for m in data.get('msgs') or []:
                # Only a Disaster Report, Supply Order or Work Crew Log is filed, its fields an object (an older record
                # may carry them flat, without the sub-object: the Message Center rebuilds it).
                mtype = str(m.get('type') or '').lower() if isinstance(m, dict) else ''
                if mtype not in MSG_TYPES or not isinstance(m.get(mtype) if m.get(mtype) is not None else {}, dict):
                    bad += 1
                    continue
                m = dict(m)
                m['type'] = mtype
                mid = _safe_id(m.get('id'))
                dk  = str(m.get('dupKey') or '')[:200]
                fk  = _form_key(m)
                if mid in ids or (dk and dk in dups) or fk in forms:
                    dup += 1
                    continue
                m['id'] = mid
                m['dupKey'] = dk
                m['origin'] = str(m.get('origin') or via)[:80]
                m['via'] = via
                m['formKey'] = fk
                status = m.get('status') if m.get('status') in MSG_STATUSES else 'new'
                m['status'] = status
                note = str(m.get('operator_note') or '')[:4000]
                ts = _ms(m.get('ts'))
                m['ts'] = ts
                if not isinstance(m.get('fields'), dict):
                    m.pop('fields', None)
                conn.execute(
                    'INSERT OR IGNORE INTO messages '
                    '(id, received_ms, type, data_json, status, operator_note, filename, dup_key, event_id)'
                    ' VALUES (?,?,?,?,?,?,?,?,?)',
                    (mid, ts, m['type'], json.dumps(m), status, note, str(m.get('filename') or '')[:200], dk, eid)
                )
                ids.add(mid); forms.add(fk)
                if dk:
                    dups.add(dk)
                new += 1
                _file_actions(conn, eid, m)
            # Roster: add units not already present (by name, case-insensitive)
            have = set()
            for r in conn.execute('SELECT data_json FROM roster WHERE event_id=?', (eid,)).fetchall():
                try:
                    have.add(str(json.loads(r['data_json']).get('name') or '').strip().lower())
                except Exception:
                    pass
            for r in data.get('roster') or []:
                if not isinstance(r, dict):
                    continue
                nm = str(r.get('name') or '').strip()[:120]
                if not nm or nm.lower() in have:
                    continue
                r = dict(r); r['name'] = nm; r['id'] = _safe_id(r.get('id')); r['via'] = via
                conn.execute('INSERT OR IGNORE INTO roster (id, data_json, event_id) VALUES (?,?,?)',
                             (r['id'], json.dumps(r), eid))
                have.add(nm.lower()); roster_new += 1
            # Notes: add by id, prefixed with the sending EOC
            for n in data.get('notes') or []:
                if not isinstance(n, dict) or not n.get('text'):
                    continue
                nid = _safe_id(n.get('id'))
                txt = str(n['text'])[:4000]
                txt = txt if txt.startswith('[') else f'[{via}] {txt}'
                cur = conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                                   (nid, _ms(n.get('ts')), txt, eid))
                notes_new += cur.rowcount if cur.rowcount > 0 else 0
            # Work items the sending EOC marked "waiting on the line above": they land here as open
            # items that name the EOC asking, so this EOC's worklist carries the decision.
            now_ms = int(time.time() * 1000)
            for a in data.get('actions') or []:
                if not isinstance(a, dict) or not str(a.get('title') or '').strip():
                    continue
                aid = _safe_id(a.get('id'))
                if conn.execute('SELECT id FROM actions WHERE id=?', (aid,)).fetchone():
                    continue
                c = _clean_action(a)
                c['from'] = via
                c['fromEoc'] = True      # came up in a roll-up: the Message Center offers "Reply to <via>"
                c['auto'] = False
                c['log'] = (_clean_log(a.get('log')) + [{'ts': now_ms, 'who': '', 'text': f'Received from {via}: they are waiting on this EOC'}])[-100:]
                conn.execute('INSERT OR IGNORE INTO actions (id, ts, status, akey, data_json, event_id) VALUES (?,?,?,?,?,?)',
                             (aid, _ms(a.get('ts'), now_ms), 'open', '', json.dumps(c), eid))
                actions_new += 1
            # Log the roll-up itself as a note and in the event record
            stamp = time.strftime('%Y-%m-%d %H:%M')
            inc_s = data.get('incident') if isinstance(data.get('incident'), dict) else {}
            sender_ev = str(inc_s.get('name') or '')[:120]
            conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                         (str(uuid.uuid4()), int(time.time() * 1000),
                          f'Roll-up received from {via} at {stamp}: {new} new, {dup} already on file'
                          + (f', {bad} not a report (skipped)' if bad else '')
                          + (f' (their event: {sender_ev})' if sender_ev else ''), eid))
            ev_row = conn.execute('SELECT data_json FROM events WHERE id=?', (eid,)).fetchone()
            ev = json.loads(ev_row['data_json'] or '{}') if ev_row else {}
            log = ev.get('rollups') or []
            log.append({'from': via, 'level': str(frm.get('level') or '')[:20], 'at': int(time.time() * 1000),
                        'new': new, 'dup': dup, 'exportedAt': _ms(data.get('exportedAt'), 0) or None,
                        'event': sender_ev})
            ev['rollups'] = log[-50:]
            conn.execute('UPDATE events SET data_json=? WHERE id=?', (json.dumps(ev), eid))
            conn.commit()
        finally:
            pass
    return {'ok': True, 'from': via, 'new': new, 'dup': dup,
            'roster_new': roster_new, 'notes_new': notes_new, 'actions_new': actions_new, 'skipped': bad}


def _parse_church_tag(body: str):
    """Return (tag_type, fields_dict) from a [Church-DR/SO/WCL|...] tag, or None."""
    m = re.search(r'\[Church-(DR|SO|WCL)\|([^\]]*)\]', body)
    if not m:
        return None
    tag_type = m.group(1)
    fields = {}
    for pair in m.group(2).split('|'):
        if '=' in pair:
            k, _, v = pair.partition('=')
            fields[k.strip()] = v.strip()
    # THIS IS AN EXERCISE: the tag key from a current template, or the banner an older one lacks
    fields['exercise'] = 'YES' if _is_exercise(fields.get('exercise')) or 'THIS IS AN EXERCISE' in body.upper() else ''
    return tag_type, fields


def _ingest_mime(mime: dict, tag_type: str, tag_fields: dict, filename: str) -> bool:
    """Insert a parsed Winlink message into the EOC database. Returns True if new."""
    msg_id  = mime['msg_id'] or str(uuid.uuid4())
    dup_key = msg_id
    sub_key = tag_type.lower()   # 'dr', 'so', or 'wcl' — matches JS render expectations
    data = {
        'id':       msg_id,
        'type':     sub_key,
        'ts':       int(time.time() * 1000),
        'filename': filename,
        'source':   'auto',
        'from':     mime['from_'],
        'to':       mime.get('to', ''),
        'subject':  mime['subject'],
        'dupKey':   dup_key,
        sub_key:    tag_fields,
        # The complete report as the sender's form built it (lets the EOC operator
        # open the whole form, not just the tag summary). Stripped from roll-ups.
        'body':     mime.get('body', ''),
    }
    with _db_lock:
        conn = get_db()
        try:
            eid = _ensure_active_event(conn)
            if conn.execute('SELECT id FROM messages WHERE dup_key=? AND event_id=?', (dup_key, eid)).fetchone():
                return False
            conn.execute(
                'INSERT OR IGNORE INTO messages '
                '(id, received_ms, type, data_json, status, operator_note, filename, dup_key, event_id)'
                ' VALUES (?,?,?,?,?,?,?,?,?)',
                (msg_id, data['ts'], sub_key, json.dumps(data), 'new', '', filename, dup_key, eid)
            )
            _file_actions(conn, eid, data)
            conn.commit()
            return True
        finally:
            conn.close()


def _active_event_start_s() -> float:
    """Start of the active event (seconds), for skipping Winlink messages that are history. Takes _db_lock."""
    try:
        with _db_lock:
            conn = get_db()
            try:
                row = conn.execute('SELECT created_ms FROM events WHERE active=1 ORDER BY created_ms DESC LIMIT 1').fetchone()
            finally:
                conn.close()
        return (row['created_ms'] / 1000.0) if row else time.time()
    except Exception:
        return time.time()


def _file_sig(f: pathlib.Path, by_content: bool = True):
    """How the watchers remember a file they handled. In a folder the EOC empties (Drop Folder, a plain .mime
    folder) a file is its path, size and modification time: the Worker forms save every report of a kind under
    one name, so the next report saved under that name is new. Winlink's own store is never emptied: by path."""
    if not by_content:
        return str(f)
    try:
        st = f.stat()
        return (str(f), st.st_mtime_ns, st.st_size)
    except OSError:
        return (str(f), 0, 0)


def _ingested_dest(folder: pathlib.Path, f: pathlib.Path) -> pathlib.Path:
    """A free name in the Ingested folder (the same name arrives again and again from the Worker forms)."""
    dest = folder / f.name
    n = 0
    while dest.exists():
        n += 1
        dest = folder / f'{f.stem}_{time.strftime("%Y%m%d-%H%M%S")}_{n}{f.suffix}'
    return dest


def _watcher_loop():
    """Background thread: poll Winlink's message folders (or a plain folder) for new Church .mime files."""
    seen: set = set()        # files handled or permanently given up on (see _file_sig)
    error_counts: dict = {}  # file sig -> failure count; retry up to 3x, then leave it
    while True:
        time.sleep(WATCHER_INTERVAL_SEC)
        with _watcher_lock:
            if not _watcher_state['enabled']:
                continue
            watch_path = _watcher_state['watch_path']
            callsigns = list(_watcher_state.get('callsigns') or [])

        check_time = time.strftime('%H:%M:%S')
        try:
            sources = _winlink_sources(watch_path, callsigns)
            # a Winlink install: the simulator writes its radio traffic to DRILL_MIME_DIR (drillDir in the status), even
            # when the callsign chosen for the drill has no folder on this computer (a public example's SIM-xxx)
            if ((sources and sources[0][2]) or _winlink_callsigns(watch_path)) and DRILL_MIME_DIR.is_dir():
                sources.append((DRILL_MIME_DIR, '', False))   # simulated Winlink traffic of a drill (moved to EOC Ingested beside it)
            if not sources:
                with _watcher_lock:
                    _watcher_state['last_check'] = check_time
                continue
            cutoff = _active_event_start_s() - WINLINK_GRACE_SEC if any(s[2] for s in sources) else 0
            new_files = []
            present = set()
            for folder, own_call, is_store in sources:
                try:
                    for f in folder.iterdir():
                        if f.suffix.lower() == '.mime':
                            sig = _file_sig(f, not is_store)
                            present.add(sig)
                            if sig not in seen:
                                new_files.append((f, folder, own_call, is_store, sig))
                except OSError:
                    continue
            seen &= present          # forget files that are gone (moved to EOC Ingested, deleted)
            for k in [k for k in error_counts if k not in present]:
                del error_counts[k]
            for fpath, folder, own_call, is_store, sig in new_files:
                seen.add(sig)
                try:
                    if is_store and fpath.stat().st_mtime < cutoff:
                        continue  # in Winlink before this event began: history, not traffic for this event
                    mime = _parse_mime_file(fpath)
                    if is_store and own_call and _sender_call(mime.get('from_', '')) == own_call:
                        continue  # this station's own copy of a message it sent
                    # Roll-up bundle attached by a Satellite or Stake EOC?
                    merged_any = False
                    for aname, atext in mime.get('attachments') or []:
                        try:
                            bundle = json.loads(atext)
                        except Exception:
                            continue
                        if _looks_like_bundle(bundle):
                            res = _merge_bundle(bundle)
                            merged_any = True
                            print(f'  [WATCHER] Roll-up from {res["from"]} ({aname}): '
                                  f'{res["new"]} new, {res["dup"]} already on file')
                        elif _looks_like_comms(bundle):
                            res = _import_comms(bundle)
                            merged_any = True
                            print(f'  [WATCHER] Comms sheet from {res["from"]} ({aname}): '
                                  + ('taken on board' if res['imported'] else res.get('reason', 'not newer')))
                    result = _parse_church_tag(mime['body'])
                    if result is None and not merged_any:
                        ics = _parse_ics(mime)
                        if not ics:
                            continue  # not a Church form or a partner agency's ICS form — leave it untouched
                        new = _ingest_ics(mime, ics, fpath.name)
                        if not is_store:
                            ingested_dir = folder.parent / WATCHER_INGESTED_DIR
                            ingested_dir.mkdir(exist_ok=True)
                            fpath.rename(_ingested_dest(ingested_dir, fpath))
                            seen.discard(sig)
                        if new:
                            with _watcher_lock:
                                _watcher_state['ingested'] += 1
                                _watcher_state['last_file'] = fpath.name
                        print(f'  [WATCHER] {ICS_KINDS[ics["form"]]} ' + ('filed' if new else 'already on file') + f': {fpath.name}')
                        continue
                    if result is None:
                        ingested = True
                    else:
                        tag_type, tag_fields = result
                        ingested = _ingest_mime(mime, tag_type, tag_fields, fpath.name)
                    # A plain folder: move the file to EOC Ingested next to it (new or duplicate), so the folder
                    # shows what is left. Winlink's own store is never touched: Winlink keeps its messages.
                    if not is_store:
                        ingested_dir = folder.parent / WATCHER_INGESTED_DIR
                        ingested_dir.mkdir(exist_ok=True)
                        fpath.rename(_ingested_dest(ingested_dir, fpath))
                        seen.discard(sig)   # gone from the folder: the same name may bring the next report
                    if ingested:
                        with _watcher_lock:
                            _watcher_state['ingested'] += 1
                            _watcher_state['last_file'] = fpath.name
                        print(f'  [WATCHER] Ingested [{tag_type if result else "ROLLUP"}] {fpath.name}')
                    else:
                        print(f'  [WATCHER] Duplicate (already in EOC): {fpath.name}')
                except Exception as exc:
                    # Retry up to 3 times for transient errors (DB lock, etc.).
                    # After 3 failures the file stays in Received inbox permanently
                    # so the Winlink operator knows it needs manual attention.
                    n = error_counts.get(sig, 0) + 1
                    error_counts[sig] = n
                    if n < 3:
                        seen.discard(sig)  # allow retry next cycle
                    with _watcher_lock:
                        _watcher_state['errors'] += 1
                    print(f'  [WATCHER] Error ({n}/3) — {fpath.name} left where it is: {exc}')

            with _watcher_lock:
                _watcher_state['last_check'] = check_time
        except Exception as exc:
            with _watcher_lock:
                _watcher_state['errors'] += 1
                _watcher_state['last_check'] = check_time
            print(f'  [WATCHER] Folder check error: {exc}')


# ── Internet Drop Folder Watcher ──────────────────────────────────────────────

def _map_worker_to_eoc(form_type: str, data: dict) -> dict:
    """Map Worker Form JSON keys to the EOC client sub-object format."""
    if form_type == 'DR':
        return {
            'stake':         data.get('inc_stake', ''),
            'ward':          data.get('inc_ward', ''),
            'date':          data.get('inc_date', ''),
            'location':      data.get('inc_location', ''),
            'inc_type':      data.get('inc_type', ''),
            'type':          data.get('inc_type', ''),   # the Winlink tag key; the DR tab and TSV read r.type
            'sp':            data.get('sp_name', ''),
            'submitter':     data.get('sub_name', ''),
            'phone':         data.get('sub_phone', ''),
            'email':         data.get('sub_email', ''),
            'lat':           data.get('stn_lat_d', ''),
            'lon':           data.get('stn_lon_d', ''),
            'grid':          data.get('stn_grid_d', ''),
            'mem_inj':       data.get('mem_injuries', '0') or '0',
            'mem_dead':      data.get('mem_deaths',   '0') or '0',
            'homes_dmg':     data.get('mem_damaged',  '0') or '0',
            'homes_dest':    data.get('mem_destroyed','0') or '0',
            'vol_count':     data.get('vol_count',    '0') or '0',
            'vol_hrs':       data.get('vol_hours',    '0') or '0',
            # Yes / No questions from the PD60000184 paper form (Worker form
            # 2026-10-28+ sends YES / NO / '' for unanswered, like the Winlink tag).
            'miss_safe':     str(data.get('miss_safe',     '') or '').upper(),
            'vol_injuries':  str(data.get('vol_injuries',  '') or '').upper(),
            'need_local':    str(data.get('need_local',    '') or '').upper(),
            'need_neighbor': str(data.get('need_neighbor', '') or '').upper(),
            'need_hq':       str(data.get('need_hq',       '') or '').upper(),
            'notes':         ' | '.join(filter(None, [
                                 data.get('miss_details', ''),
                                 data.get('mem_details', ''),
                                 data.get('bldg_damage', ''),
                                 data.get('community', ''),
                                 data.get('needs_details', ''),
                                 data.get('vol_activities', ''),
                                 data.get('vol_inj_details', ''),
                             ])),
            'bldg_damage':   data.get('bldg_damage', ''),
            'community':     data.get('community', ''),
            'needs_details': data.get('needs_details', ''),
        }
    if form_type == 'SO':
        items_parts = []
        for k, v in data.items():
            # Catalog quantity inputs are gs01, tl01, pi01, wa01, kb01 ... (two
            # letters + two digits); the Worker and Initial forms share the ids.
            if len(k) == 4 and k[:2].isalpha() and k[2:].isdigit() and v:
                try:
                    n = int(v)
                    if n > 0:
                        items_parts.append(f'{k}:{n}')
                except (ValueError, TypeError):
                    pass
        # "Other items" rows go out as LOCAL-<description>:<qty>, the same as the
        # Winlink tag, so both kinds of order aggregate the same way.
        for i in range(1, 6):
            od = str(data.get(f'other_desc{i}', '') or '').strip()
            oq = str(data.get(f'other_qty{i}', '') or '').strip()
            if od and oq:
                items_parts.append(f'LOCAL-{od[:20]}:{oq}')
        return {
            'stake':      data.get('req_stake', ''),
            'contact':    data.get('del_contact', ''),
            'phone':      data.get('del_phone', ''),
            'city':       data.get('del_city', ''),
            'state':      data.get('del_state', ''),
            'zip':        data.get('del_zip', ''),
            'order_date': data.get('order_date', ''),
            'del_date':   data.get('req_del_date', ''),   # the SO stake card's "Needed by"
            'addr':       data.get('del_addr', ''),
            'items':      ';'.join(items_parts),
            'lat':        data.get('stn_lat_d', ''),
            'lon':        data.get('stn_lon_d', ''),
            'grid':       data.get('stn_grid_d', ''),
        }
    if form_type == 'WCL':
        crew_parts = []
        total_hrs  = 0.0
        crew_count = 0
        for i in range(1, 21):
            name = data.get(f'crew_name{i}', '').strip()
            if name:
                crew_count += 1
                stake = data.get(f'crew_stake{i}', '')
                ward  = data.get(f'crew_ward{i}',  '')
                hrs   = data.get(f'crew_hrs{i}',   '0') or '0'
                wo    = data.get(f'crew_wo{i}',    '')
                addr  = data.get(f'crew_addr{i}',  '')
                # Comma-separated like the older drop records; ',' and ';' inside a
                # value would split the entry, so they become spaces.
                clean = lambda v: str(v or '').replace(',', ' ').replace(';', ' ').strip()
                crew_parts.append(','.join(clean(v) for v in (name, stake, ward, hrs, wo, addr)))
                try:
                    total_hrs += float(hrs)
                except (ValueError, TypeError):
                    pass
        chief_hrs = data.get('chief_hrs', '0') or '0'
        try:
            total_hrs += float(chief_hrs)
        except (ValueError, TypeError):
            pass
        return {
            'date':        data.get('log_date', ''),
            'location':    data.get('log_location', ''),
            'chief':       data.get('chief_name', ''),
            'chief_stake': data.get('chief_stake', ''),
            'chief_ward':  data.get('chief_ward', ''),
            'chief_hrs':   chief_hrs,
            'chief_phone': data.get('chief_phone', ''),
            'crew_count':  str(crew_count),
            'total_hrs':   str(round(total_hrs, 1)),
            'crew':        ';'.join(crew_parts),
            # Safety acknowledgment (PD10052209 footnote): Worker sends true/false,
            # the Winlink tag sends safety=YES/NO.
            'safety':      'YES' if str(data.get('safety_cert', '')).lower() in ('true', '1', 'yes', 'on') else 'NO',
            'submitter':   data.get('chief_name', ''),
            'lat':         data.get('stn_lat_d', ''),
            'lon':         data.get('stn_lon_d', ''),
            'grid':        data.get('stn_grid_d', ''),
        }
    return {}


def _detect_form_type(filename: str, data: dict):
    """Detect form type (DR/SO/WCL) from filename; fall back to JSON key signatures."""
    fn = filename.lower()
    if 'disaster' in fn:                              return 'DR'
    if 'supply'   in fn:                              return 'SO'
    if 'work_crew' in fn or 'crew_log' in fn:         return 'WCL'
    if 'mem_injuries' in data or 'bldg_damage' in data: return 'DR'
    if 'del_addr'     in data or 'req_stake'   in data: return 'SO'
    if 'crew_name1'   in data or 'log_date'    in data: return 'WCL'
    return None


def _ingest_drop_file(path: pathlib.Path) -> tuple:
    """Parse a Worker Form .txt JSON file (or a .json roll-up bundle from another
    EOC) and insert into EOC database.
    Returns (form_type, is_new); raises on parse or type-detection errors."""
    raw = path.read_text(encoding='utf-8-sig')  # utf-8-sig strips BOM if present
    return _ingest_text(raw, path.name, source='internet', tag='DROP')


def _ingest_text(raw: str, filename: str, source: str = 'internet', tag: str = 'DROP') -> tuple:
    """Parse one Worker Form file's text (or a roll-up / Comms Sheet .json) and file it.
    Used by the Drop Folder watcher and by POST /api/upload. Returns (form_type, is_new)."""
    data = json.loads(raw.lstrip('﻿'))
    if not isinstance(data, dict):
        raise ValueError('File is not a JSON object')
    if _looks_like_comms(data):
        res = _import_comms(data)
        print(f'  [{tag}]   Comms sheet from {res["from"]}: '
              + ('taken on board' if res['imported'] else res.get('reason', 'not newer')))
        return 'COMMS', res['imported']
    if _looks_like_reply(data):
        res = _merge_bundle(data)
        print(f'  [{tag}]   Reply from {res["from"]}: {res["replies_applied"]} work item(s) answered')
        return 'REPLY', res['replies_applied'] > 0
    if _looks_like_bundle(data):
        res = _merge_bundle(data)
        print(f'  [{tag}]   Roll-up from {res["from"]}: {res["new"]} new, {res["dup"]} already on file')
        return 'ROLLUP', res['new'] > 0
    return _ingest_worker(data, filename, source)


def _ingest_worker(data: dict, filename: str, source: str = 'internet') -> tuple:
    """File one Worker Form report under the active event. Returns (form_type, is_new).
    The duplicate key hashes the form's fields (sorted), so the same report sent from a
    phone twice, or once by upload and once through the Drop Folder, is filed once."""
    form_type = _detect_form_type(filename, data)
    if form_type is None:
        raise ValueError(f'Cannot detect form type (DR/SO/WCL) from {filename!r}')
    canon = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    content_hash = hashlib.sha256(canon.encode('utf-8')).hexdigest()[:16]
    dup_key  = f'drop:{content_hash}'
    msg_id   = str(uuid.uuid4())
    sub_key  = form_type.lower()
    record   = {
        'id':       msg_id,
        'type':     sub_key,
        'ts':       int(time.time() * 1000),
        'filename': filename,
        'source':   source,
        'dupKey':   dup_key,
        sub_key:    dict(_map_worker_to_eoc(form_type, data), exercise='YES' if _is_exercise(data.get('exercise')) else ''),
        # Every field the Worker form saved, so the EOC operator can open the
        # whole form. Stripped from roll-ups.
        'fields':   {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool))},
    }
    with _db_lock:
        conn = get_db()
        try:
            eid = _ensure_active_event(conn)
            if conn.execute('SELECT id FROM messages WHERE dup_key=? AND event_id=?', (dup_key, eid)).fetchone():
                return form_type, False
            conn.execute(
                'INSERT OR IGNORE INTO messages '
                '(id, received_ms, type, data_json, status, operator_note, filename, dup_key, event_id)'
                ' VALUES (?,?,?,?,?,?,?,?,?)',
                (msg_id, record['ts'], sub_key, json.dumps(record), 'new', '', filename, dup_key, eid)
            )
            _file_actions(conn, eid, record)
            conn.commit()
            return form_type, True
        finally:
            conn.close()


_FORM_FILENAMES = {'dr': 'Church_Disaster_Report_Worker.txt', 'so': 'Church_Supply_Order_Worker.txt',
                   'wcl': 'Church_Work_Crew_Log_Worker.txt'}

def _handle_upload(body: dict) -> dict:
    """POST /api/upload. Body is one of:
         {reports: [{form: 'dr'|'so'|'wcl', filename?, data: {...Worker fields}}], to?: <EOC url>}
         {filename, text}   -- a whole Worker .txt, roll-up or Comms Sheet file
    `to` names another EOC on the LAN (from /api/peers); the report is relayed there.
    Must be called WITHOUT _db_lock held (the ingest functions take it)."""
    to = str(body.get('to') or '').rstrip('/')
    if to and to != _lan_url():
        if to not in _peer_urls():
            return {'ok': False, 'error': 'That EOC is not on this network right now'}
        fwd = dict(body); fwd.pop('to', None)
        req = urllib.request.Request(to + '/api/upload', data=json.dumps(fwd).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                res = json.loads(r.read().decode('utf-8'))
            res['relayedBy'] = _eoc_identity().get('name') or _lan_url()
            print(f'  [UPLOAD] Relayed {len(body.get("reports") or [1])} report(s) to {to}')
            return res
        except Exception as exc:
            return {'ok': False, 'error': f'Could not reach that EOC: {exc}'}
    results = []
    items = body.get('reports')
    if items is None and 'text' in body:
        fn = str(body.get('filename') or 'upload.txt')
        try:
            ft, new = _ingest_text(str(body['text']), fn, source='upload', tag='UPLOAD')
            results.append({'filename': fn, 'form': ft, 'status': 'new' if new else 'duplicate'})
        except Exception as exc:
            results.append({'filename': fn, 'status': 'error', 'error': str(exc)})
    for it in (items or []):
        it = it if isinstance(it, dict) else {}
        form = str(it.get('form') or '').lower()
        fn = str(it.get('filename') or _FORM_FILENAMES.get(form, 'upload.txt'))
        data = it.get('data')
        try:
            if not isinstance(data, dict):
                raise ValueError('No form data')
            ft, new = _ingest_worker(data, fn, source='upload')
            results.append({'id': it.get('id', ''), 'filename': fn, 'form': ft, 'status': 'new' if new else 'duplicate'})
        except Exception as exc:
            results.append({'id': it.get('id', ''), 'filename': fn, 'status': 'error', 'error': str(exc)})
    n_new = sum(1 for r in results if r['status'] == 'new')
    n_dup = sum(1 for r in results if r['status'] == 'duplicate')
    n_err = sum(1 for r in results if r['status'] == 'error')
    if results:
        print(f'  [UPLOAD] {n_new} new, {n_dup} already on file, {n_err} error(s)')
    ident = _eoc_identity()
    return {'ok': n_err == 0 and bool(results), 'results': results, 'new': n_new, 'dup': n_dup, 'errors': n_err,
            'eoc': {'name': ident.get('name') or '', 'level': ident.get('level') or '', 'url': _lan_url()},
            'event': ident.get('event') or '', 'receivedAt': int(time.time() * 1000)}


def _eoc_identity() -> dict:
    """This EOC's name, level, location and active event (for /api/status, uploads, discovery)."""
    try:
        with _db_lock:
            conn = get_db()
            try:
                r = conn.execute('SELECT data_json FROM incident WHERE singleton=1').fetchone()
                ev = _active_event(conn)
            finally:
                conn.close()
        inc = json.loads(r['data_json']) if r else {}
    except Exception:
        inc, ev = {}, {}
    return {'name': inc.get('eocName') or '', 'level': inc.get('eocLevel') or '',
            'lat': inc.get('eocLat') or '', 'lon': inc.get('eocLon') or '',
            'event': (ev or {}).get('name') or ''}


# ── Discovery (UDP broadcast) ─────────────────────────────────────────────────
# ── Drill coordination: the simulator feeding this EOC pushes its state here (role it plays,
# scenario, clock, start time); operators press "I am ready" on any screen. Memory only: the
# simulator re-pushes every few seconds, and a restart of either side loses nothing real.
_drill = {}
_drill_ready = {}      # operator name -> ms when they pressed Ready
_drill_lock = threading.Lock()
DRILL_STALE_SEC = 60


def _drill_view():
    """The drill bar's data for /api/status and /api/drill; None when no simulator has pushed."""
    with _drill_lock:
        if not _drill:
            return None
        d = dict(_drill)
        d['ready'] = sorted(_drill_ready)
        d['stale'] = (time.time() * 1000 - int(d.get('seen_ms') or 0)) > DRILL_STALE_SEC * 1000
        return d


_peers = {}            # url -> {name, level, event, url, seen}
_peers_lock = threading.Lock()

def _peer_urls():
    now = time.time()
    with _peers_lock:
        return [u for u, p in _peers.items() if now - p['seen'] < PEER_TTL_SEC]

def _peer_list():
    """This EOC first, then every other EOC heard on the LAN in the last PEER_TTL_SEC seconds."""
    me = _eoc_identity()
    out = [{'url': _lan_url(), 'name': me['name'], 'level': me['level'], 'event': me['event'], 'self': True}]
    now = time.time()
    with _peers_lock:
        for u, p in sorted(_peers.items(), key=lambda kv: (kv[1].get('name') or kv[0]).lower()):
            if u != _lan_url() and now - p['seen'] < PEER_TTL_SEC:
                out.append({'url': u, 'name': p.get('name', ''), 'level': p.get('level', ''),
                            'event': p.get('event', ''), 'self': False})
    return out

def _discovery_announce_loop():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    warned = ''
    while True:
        try:
            me = _eoc_identity()
            msg = json.dumps({'app': 'church-eoc', 'v': 1, 'url': _lan_url(), 'name': me['name'],
                              'level': me['level'], 'event': me['event']}).encode('utf-8')
            # the subnet's own broadcast address too: macOS may refuse or misroute 255.255.255.255
            sent, error = 0, ''
            for addr in ('255.255.255.255', get_local_ip().rsplit('.', 1)[0] + '.255'):
                try:
                    s.sendto(msg, (addr, DISCOVERY_PORT))
                    sent += 1
                except OSError as exc:
                    error = str(exc)
            if not sent and error != warned:
                warned = error                 # say it once: a silent failure hides this EOC from the others
                print(f'  [PEERS]  Cannot announce this EOC ({error}). On a Mac, allow Local Network for this app in System Settings.')
        except Exception:
            pass
        time.sleep(DISCOVERY_EVERY_SEC)

def _discovery_listen_loop():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # two EOC servers on one laptop can both listen
    if hasattr(socket, 'SO_REUSEPORT'):                       # macOS and Linux need this one as well for a shared UDP port
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    try:
        s.bind(('', DISCOVERY_PORT))
    except Exception as exc:
        print(f'  [PEERS]  Discovery listener off ({exc}); phones will see only this EOC')
        return
    while True:
        try:
            raw, _addr = s.recvfrom(4096)
            p = json.loads(raw.decode('utf-8'))
            if p.get('app') != 'church-eoc' or not str(p.get('url', '')).startswith('http'):
                continue
            url = str(p['url']).rstrip('/')
            with _peers_lock:
                new = url not in _peers
                _peers[url] = {'name': str(p.get('name', ''))[:80], 'level': str(p.get('level', ''))[:20],
                               'event': str(p.get('event', ''))[:80], 'seen': time.time()}
            if new and url != _lan_url():
                print(f'  [PEERS]  Found another EOC: {p.get("name") or url} ({url})')
        except Exception:
            pass


def _drop_loop():
    """Background thread: poll the EOC Drop Folder for Worker Form .txt JSON files."""
    seen: set        = set()
    error_counts: dict = {}
    while True:
        time.sleep(DROP_INTERVAL_SEC)
        with _drop_lock:
            if not _drop_state['enabled']:
                continue
            watch_path = pathlib.Path(_drop_state['watch_path'])

        check_time = time.strftime('%H:%M:%S')
        try:
            if not watch_path.exists():
                with _drop_lock:
                    _drop_state['last_check'] = check_time
                continue

            ingested_dir = watch_path / DROP_INGESTED_SUBDIR
            files = [f for f in watch_path.iterdir() if f.suffix.lower() in ('.txt', '.json') and f.is_file()]
            sigs = {f: _file_sig(f) for f in files}
            present = set(sigs.values())
            seen &= present          # forget files that are gone: a Worker form saves the next report under the same name
            for k in [k for k in error_counts if k not in present]:
                del error_counts[k]
            for fpath in files:
                sig = sigs[fpath]
                if sig in seen:
                    continue
                seen.add(sig)
                try:
                    form_type, is_new = _ingest_drop_file(fpath)
                    ingested_dir.mkdir(exist_ok=True)
                    fpath.rename(_ingested_dest(ingested_dir, fpath))
                    seen.discard(sig)
                    if is_new:
                        with _drop_lock:
                            _drop_state['ingested'] += 1
                            _drop_state['last_file'] = fpath.name
                        print(f'  [DROP]   Ingested [{form_type}] {fpath.name}')
                    elif form_type == 'ROLLUP':
                        print(f'  [DROP]   Roll-up had nothing new: {fpath.name}')
                    elif form_type == 'REPLY':
                        print(f'  [DROP]   Reply named no work item on file: {fpath.name}')
                    else:
                        print(f'  [DROP]   Duplicate (already in EOC): {fpath.name}')
                except Exception as exc:
                    n = error_counts.get(sig, 0) + 1
                    error_counts[sig] = n
                    if n < 3:
                        seen.discard(sig)
                    with _drop_lock:
                        _drop_state['errors'] += 1
                    print(f'  [DROP]   Error ({n}/3) — {fpath.name} stays in folder: {exc}')

            with _drop_lock:
                _drop_state['last_check'] = check_time
        except Exception as exc:
            with _drop_lock:
                _drop_state['errors'] += 1
                _drop_state['last_check'] = check_time
            print(f'  [DROP]   Folder check error: {exc}')


# ── Request Handler ───────────────────────────────────────────────────────────
class EOCHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        ts = time.strftime('%H:%M:%S')
        method = getattr(self, '_method', '?')
        print(f'  [{ts}] {method} {self.path}')

    def send_json(self, data, code=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        # No Access-Control-Allow-Origin: only this server's own pages read its API. Phones on https (the
        # GitHub Pages app) hand reports over through /receive, the simulator and other EOCs talk server to server.
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, file=None):
        file = file or HTML_FILE
        try:
            body = file.read_bytes()
        except FileNotFoundError:
            self.send_json({'error': f'{file.name} not found'}, 404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self):
        # A CORS preflight gets no Allow-Origin, so another site's page cannot call this API.
        self._method = 'OPTIONS'
        self.send_response(204)
        self.send_header('Allow', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        self.end_headers()

    def _same_origin(self) -> bool:
        """A browser names the page that sent a POST / PUT / PATCH / DELETE in Origin. Only this server's own
        pages may change data; a request without Origin (Python urllib from the simulator or another EOC,
        curl) is not a browser and passes."""
        origin = self.headers.get('Origin')
        if origin is None:
            return True
        host = (self.headers.get('Host') or '').strip().lower()
        try:
            o = urllib.parse.urlsplit(origin.strip())
        except ValueError:
            return False
        return bool(host) and o.scheme in ('http', 'https') and o.netloc.lower() == host

    def _is_this_laptop(self) -> bool:
        """The person is at the laptop that runs this server (by localhost or by its own network address)."""
        return self.client_address[0].split('%')[0] in _own_addresses()

    def _is_local(self) -> bool:
        return self.client_address[0] in ('127.0.0.1', '::1', '::ffff:127.0.0.1')

    def _refuse_cross_origin(self) -> bool:
        """Answer 403 and return True when a state-changing request comes from another site's page."""
        if self._same_origin():
            return False
        print(f'  [SECURITY] Refused {self.command} {self.path} from page {self.headers.get("Origin")!r}')
        self.send_json({'ok': False, 'error': 'Refused: this request came from a page that is not this EOC server'}, 403)
        return True

    def do_GET(self):
        self._method = 'GET'
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path in ('/', '/index.html'):
            self.send_html(); return
        if path in ('/wall', '/wall.html', '/EOC_Wall_Display.html'):
            # Read-only big board for a TV / projector in the EOC (press F for full screen).
            self.send_html(WALL_FILE); return
        if path in ('/m', '/m/', '/phone', '/receive', '/EOC_Phone.html'):
            # Phone page (the wall QR points here) and the receive page for reports
            # handed over from the Church of Jesus Christ EMCOMM app (the reports ride in the URL fragment).
            self.send_html(PHONE_FILE); return
        if path == '/app.webmanifest':
            self.send_bytes(json.dumps(APP_MANIFEST).encode('utf-8'), 'application/manifest+json'); return
        if path.startswith('/icons/'):
            fp = _icon_path(path[len('/icons/'):])
            if fp:
                self.send_bytes(fp.read_bytes(), 'image/png')
            else:
                self.send_json({'error': 'No such icon here'}, 404)
            return
        if path.startswith('/forms/'):
            key = path[len('/forms/'):].strip('/').lower().replace('.html', '')
            fp = _worker_form_path(key) if key in WORKER_FORMS else None
            if fp:
                self.send_html(fp)
            else:
                self.send_json({'error': 'No such form here. Try /forms/dr, /forms/so or /forms/wcl'}, 404)
            return
        if path == '/api/browse':        # this laptop's folders: for the person at this laptop, never for a phone or another laptop
            if not self._is_this_laptop():
                self.send_json({'error': 'Folders can be browsed only on the laptop that runs the EOC server. Type the full folder path instead.'}, 403); return
            self.send_json(_browse_folder((params.get('path') or [''])[0], (params.get('kind') or ['any'])[0])); return
        if path == '/api/peers':
            self.send_json(_peer_list()); return
        if path == '/api/map/status':
            self.send_json(_map_info(_map_path_setting())); return
        if path.startswith('/map/'):
            # A file of the geographic dataset (boundaries, buildings, overlay images), only from
            # the dataset folder set on the Setup tab, never anything else on the laptop.
            d = _map_dir(_map_path_setting())
            rel = urllib.parse.unquote(path[len('/map/'):])
            if not d or not rel or '..' in rel.split('/') or rel.startswith('/'):
                self.send_json({'error': 'no map data here'}, 404); return
            target = (d / rel).resolve()
            try:
                target.relative_to(d)
            except ValueError:
                self.send_json({'error': 'no map data here'}, 404); return
            if not target.is_file() or target.suffix.lower() not in _MAP_TYPES:
                self.send_json({'error': 'no such map file'}, 404); return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', _MAP_TYPES[target.suffix.lower()])
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'max-age=3600' if target.suffix.lower() == '.png' else 'no-cache')
            self.end_headers()
            self.wfile.write(body)
            return
        if path == '/api/drill':
            self.send_json(_drill_view() or {'active': False}); return
        if path == '/api/backup':
            # Manual on-demand backup (Setup tab button or operator CLI). Handled before _db_lock
            # is taken: dump_all_data() takes the lock itself (it is not re-entrant).
            out = write_json_backup(BACKUP_DIR, label='manual')
            data = json.loads(out.read_text(encoding='utf-8'))
            print(f'  [BACKUP] Manual backup: {out.name}  ({len(data["messages"])} messages)')
            self.send_json({'ok': True, 'file': out.name, 'messages': len(data['messages'])})
            return

        with _db_lock:
            conn = get_db()
            try:
                if path == '/api/status':
                    ev = _active_event(conn)
                    count = conn.execute('SELECT COUNT(*) FROM messages WHERE event_id=?', (ev['id'],)).fetchone()[0]
                    r = conn.execute('SELECT data_json FROM incident WHERE singleton=1').fetchone()
                    inc = json.loads(r['data_json']) if r else {}
                    open_actions = conn.execute("SELECT COUNT(*) FROM actions WHERE event_id=? AND status!='done'", (ev['id'],)).fetchone()[0]
                    self.send_json({'ok': True, 'version': VERSION, 'msgCount': count, 'openActions': open_actions,
                                    'activeEventId': ev['id'], 'activeEventName': ev.get('name') or '',
                                    'activeEventStatus': ev['status'], 'lanUrl': _lan_url(),
                                    # who this EOC is, for the phone page, served forms and discovery
                                    'eocName': inc.get('eocName') or '', 'eocLevel': inc.get('eocLevel') or '',
                                    'eocLat': inc.get('eocLat') or '', 'eocLon': inc.get('eocLon') or '',
                                    'pace': ev.get('pace') or '', 'formsVersion': FORMS_VERSION,
                                    'map': bool(_map_dir(inc.get('mapPath') or '')),
                                    'drill': _drill_view()})

                elif path == '/api/events':
                    self.send_json(_list_events(conn))

                elif path == '/api/messages':
                    # Records of one event: the active one unless ?event=<id> names another.
                    since = int(params.get('since', ['0'])[0])
                    eid = params.get('event', [''])[0] or _ensure_active_event(conn)
                    rows = conn.execute(
                        'SELECT * FROM messages WHERE event_id=? AND received_ms > ? ORDER BY received_ms ASC',
                        (eid, since)
                    ).fetchall()
                    self.send_json([dict(r) for r in rows])

                elif path == '/api/roster':
                    eid = params.get('event', [''])[0] or _ensure_active_event(conn)
                    rows = conn.execute('SELECT data_json FROM roster WHERE event_id=?', (eid,)).fetchall()
                    self.send_json([json.loads(r['data_json']) for r in rows])

                elif path == '/api/incident':
                    self.send_json(_incident_view(conn))

                elif path == '/api/comms':
                    self.send_json(_get_comms(conn))

                elif path == '/api/notes':
                    eid = params.get('event', [''])[0] or _ensure_active_event(conn)
                    rows = conn.execute('SELECT id, ts, text FROM notes WHERE event_id=? ORDER BY ts DESC', (eid,)).fetchall()
                    self.send_json([dict(r) for r in rows])

                elif path == '/api/actions':
                    # Work items of one event (the active one unless ?event=<id>), oldest first.
                    eid = params.get('event', [''])[0] or _ensure_active_event(conn)
                    self.send_json(_list_actions(conn, eid))

                elif path == '/api/watcher/status':
                    conn.close()
                    self.send_json(_watcher_view())
                    return

                elif path == '/api/drop/status':
                    conn.close()
                    with _drop_lock:
                        self.send_json(dict(_drop_state))
                    return

                else:
                    self.send_json({'error': 'Not found'}, 404)
            finally:
                conn.close()

    def do_POST(self):
        self._method = 'POST'
        if self._refuse_cross_origin():
            return
        path = urllib.parse.urlparse(self.path).path
        body = self.read_body()

        if path == '/api/upload':
            # Reports from phones / browsers on the EOC Wi-Fi. Handled before _db_lock is
            # taken: the ingest functions take it themselves (the lock is not re-entrant).
            self.send_json(_handle_upload(body if isinstance(body, dict) else {}))
            return

        if path == '/api/config/apply':   # takes _db_lock itself: before the lock below
            b = body if isinstance(body, dict) else {}
            try:
                self.send_json(_apply_drill_config(b.get('config') or {}, str(b.get('eoc') or ''), b.get('manned') or [], b.get('newEvent', True) is not False))
            except Exception as ex:
                self.send_json({'error': str(ex)}, 400)
            return

        if path == '/api/drill/ready':
            b = body if isinstance(body, dict) else {}
            who = str(b.get('who') or '').strip()[:60] or 'operator'
            flag = bool(b.get('ready', True))
            with _drill_lock:
                if flag:
                    _drill_ready[who] = int(time.time() * 1000)
                else:
                    _drill_ready.pop(who, None)
                names = sorted(_drill_ready)
            print(f'  [DRILL]  {who} is {"ready" if flag else "not ready"} ({len(names)} ready)')
            self.send_json({'ok': True, 'ready': names}); return

        with _db_lock:
            conn = get_db()
            try:
                if not isinstance(body, dict):
                    self.send_json({'error': 'Expected a JSON object'}, 400); return
                if path == '/api/messages':
                    eid = _ensure_active_event(conn)
                    body['id'] = _safe_id(body.get('id'))
                    dup_key = body.get('dupKey', '')
                    msg_type = body.get('type', '')
                    if dup_key:
                        existing = conn.execute(
                            'SELECT id FROM messages WHERE dup_key=? AND type=? AND event_id=?', (dup_key, msg_type, eid)
                        ).fetchone()
                        if existing:
                            self.send_json({'duplicate': True}); return
                    conn.execute(
                        'INSERT OR IGNORE INTO messages (id, received_ms, type, data_json, status, operator_note, filename, dup_key, event_id)'
                        ' VALUES (?,?,?,?,?,?,?,?,?)',
                        (
                            body.get('id', ''),
                            _ms(body.get('ts')),
                            msg_type,
                            json.dumps(body),
                            'new', '',
                            body.get('filename', ''),
                            dup_key,
                            eid,
                        )
                    )
                    if isinstance(body, dict):
                        _file_actions(conn, eid, body)
                    conn.commit()
                    self.send_json({'ok': True})

                elif path == '/api/notes':
                    conn.execute(
                        'INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                        (_safe_id(body.get('id')), _ms(body.get('ts')), str(body.get('text') or ''),
                         _ensure_active_event(conn))
                    )
                    conn.commit()
                    self.send_json({'ok': True})

                elif path == '/api/actions':
                    res = _create_action(conn, _ensure_active_event(conn), body if isinstance(body, dict) else {})
                    conn.commit()
                    self.send_json(res, 200 if res.get('ok') else 400)

                elif path == '/api/events':
                    # Open a new Emergency Event and make it the one every operator works.
                    name = str(body.get('name') or '').strip()
                    if not name:
                        self.send_json({'error': 'Event name is required'}, 400); return
                    ev = {k: body[k] for k in EVENT_FIELDS if k in body and k not in ('rollups', 'lastRollupTs', 'closedTs')}
                    ev['name'] = name
                    if not ev.get('startTs'):
                        ev['startTs'] = int(time.time() * 1000)
                    eid = str(uuid.uuid4())
                    conn.execute('UPDATE events SET active=0')
                    conn.execute('INSERT INTO events (id, created_ms, status, active, data_json) VALUES (?,?,?,1,?)',
                                 (eid, int(time.time() * 1000), 'open', json.dumps(ev)))
                    conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                                 (str(uuid.uuid4()), int(time.time() * 1000),
                                  f'Emergency Event opened: {name}' + (f' ({ev["type"]})' if ev.get('type') else ''), eid))
                    conn.commit()
                    print(f'  [EVENT]  Opened: {name}')
                    self.send_json(_incident_view(conn))

                elif path == '/api/merge':
                    # Roll-up from a Satellite / Stake EOC pasted or imported in the UI.
                    # _db_lock is already held here, so hand the open connection in.
                    if _looks_like_comms(body):
                        try:
                            res = _import_comms(body, conn=conn)
                        except Exception as exc:
                            conn.rollback()
                            self.send_json({'ok': False, 'error': f'Could not read that comms sheet: {exc}'}, 400)
                            return
                        print(f'  [MERGE]  Comms sheet from {res["from"]}: '
                              + ('taken on board' if res['imported'] else res.get('reason', 'not newer')))
                        self.send_json(res)
                    elif not _looks_like_bundle(body):
                        self.send_json({'error': 'Not a roll-up / handoff bundle'}, 400)
                    else:
                        try:
                            res = _merge_bundle(body, conn=conn)
                        except Exception as exc:   # a malformed bundle must still get an answer
                            conn.rollback()
                            print(f'  [MERGE]  Bundle refused: {exc!r}')
                            self.send_json({'ok': False, 'error': f'Could not merge that bundle: {exc}'}, 400)
                            return
                        if res.get('kind') == REPLY_KIND:
                            print(f'  [MERGE]  Reply from {res["from"]}: {res["replies_applied"]} work item(s) answered')
                        else:
                            print(f'  [MERGE]  Roll-up from {res["from"]}: {res["new"]} new, {res["dup"]} already on file')
                        self.send_json(res)

                else:
                    self.send_json({'error': 'Not found'}, 404)
            finally:
                conn.close()

    def do_PUT(self):
        self._method = 'PUT'
        if self._refuse_cross_origin():
            return
        path = urllib.parse.urlparse(self.path).path
        body = self.read_body()

        if path in ('/api/watcher/config', '/api/drop/config') and not (self._is_local() or self.headers.get('Origin')):
            # Which folders this EOC reads: from this computer, or from the Message Center page itself
            # (a browser names its page in Origin, checked above). Not from a script elsewhere on the network.
            self.send_json({'ok': False, 'error': 'Change the watched folders from the Message Center or on the EOC computer'}, 403)
            return

        if path == '/api/drill':
            # The simulator's drill state. Ready names survive re-pushes of the same run and
            # reset when another run is pushed.
            b = body if isinstance(body, dict) else {}
            with _drill_lock:
                same_run = bool(_drill) and _drill.get('run_id') == b.get('run_id')
                _drill.clear()
                _drill.update({k: v for k, v in b.items() if k != 'ready'})
                _drill['seen_ms'] = int(time.time() * 1000)
                if not same_run:
                    _drill_ready.clear()
                names = sorted(_drill_ready)
            self.send_json({'ok': True, 'ready': names}); return

        with _db_lock:
            conn = get_db()
            try:
                if path == '/api/roster':
                    eid = _ensure_active_event(conn)
                    conn.execute('DELETE FROM roster WHERE event_id=?', (eid,))
                    for r in (body if isinstance(body, list) else []):
                        if not isinstance(r, dict):
                            continue
                        r['id'] = _safe_id(r.get('id'))
                        conn.execute('INSERT OR IGNORE INTO roster (id, data_json, event_id) VALUES (?,?,?)',
                                     (r['id'], json.dumps(r), eid))
                    conn.commit()
                    self.send_json({'ok': True})

                elif path == '/api/incident':
                    _save_incident_view(conn, body)
                    conn.commit()
                    self.send_json({'ok': True})

                elif path == '/api/comms':
                    body = body if isinstance(body, dict) else {}
                    ms = _put_comms(conn, body.get('sheet') or {}, body.get('updatedMs'))
                    conn.commit()
                    print('  [COMMS]  Comms sheet saved')
                    self.send_json({'ok': True, 'updatedMs': ms})

                elif path.startswith('/api/events/'):
                    # Switch to an event (activate), close or reopen it, or edit its details.
                    eid = path[len('/api/events/'):]
                    if not conn.execute('SELECT id FROM events WHERE id=?', (eid,)).fetchone():
                        self.send_json({'error': 'No such event'}, 404); return
                    body = body if isinstance(body, dict) else {}
                    changes = {k: body[k] for k in EVENT_FIELDS if k in body}
                    if body.get('status') in ('open', 'closed'):
                        conn.execute('UPDATE events SET status=? WHERE id=?', (body['status'], eid))
                        changes['closedTs'] = int(time.time() * 1000) if body['status'] == 'closed' else None
                        conn.execute('INSERT OR IGNORE INTO notes (id, ts, text, event_id) VALUES (?,?,?,?)',
                                     (str(uuid.uuid4()), int(time.time() * 1000),
                                      'Emergency Event ' + ('closed' if body['status'] == 'closed' else 'reopened'), eid))
                    if changes:
                        _update_event(conn, eid, changes)
                    if body.get('activate'):
                        conn.execute('UPDATE events SET active=0')
                        conn.execute('UPDATE events SET active=1 WHERE id=?', (eid,))
                        print(f'  [EVENT]  Switched to: {_event_name(conn)}')
                    conn.commit()
                    self.send_json(_incident_view(conn))

                elif path == '/api/watcher/config':
                    conn.close()
                    body = body if isinstance(body, dict) else {}
                    new_path = str(body.get('watch_path') or '').strip()
                    with _watcher_lock:
                        if 'enabled' in body:
                            _watcher_state['enabled'] = bool(body['enabled'])
                        if new_path:
                            _watcher_state['watch_path'] = new_path
                            _watcher_state['enabled'] = True
                        if 'callsigns' in body:
                            _watcher_state['callsigns'] = _norm_calls(body.get('callsigns'))
                        keep = {'winlinkFolder': _watcher_state['watch_path'], 'winlinkCallsigns': _watcher_state['callsigns'],
                                'winlinkWatch': _watcher_state['enabled']}
                    _save_settings(keep)   # survives a restart; an unattended start reads it
                    self.send_json(_watcher_view())
                    return

                elif path == '/api/drop/config':
                    conn.close()
                    body = body if isinstance(body, dict) else {}
                    new_path = str(body.get('watch_path') or '').strip()
                    with _drop_lock:
                        if 'enabled' in body:
                            _drop_state['enabled'] = bool(body['enabled'])
                        if new_path:
                            _drop_state['watch_path'] = new_path
                            _drop_state['enabled'] = True
                        self.send_json(dict(_drop_state))
                    return

                else:
                    self.send_json({'error': 'Not found'}, 404)
            finally:
                conn.close()

    def do_PATCH(self):
        self._method = 'PATCH'
        if self._refuse_cross_origin():
            return
        path = urllib.parse.urlparse(self.path).path
        body = self.read_body()

        m = re.match(r'^/api/actions/([^/]+)$', path)
        if m:
            with _db_lock:
                conn = get_db()
                try:
                    item = _update_action(conn, m.group(1), body if isinstance(body, dict) else {})
                    conn.commit()
                    if item is None:
                        self.send_json({'error': 'No such work item'}, 404)
                    else:
                        self.send_json({'ok': True, 'item': item})
                finally:
                    conn.close()
            return

        m = re.match(r'^/api/messages/([^/]+)$', path)
        if m:
            msg_id = m.group(1)
            with _db_lock:
                conn = get_db()
                try:
                    body = body if isinstance(body, dict) else {}
                    if body.get('status') in MSG_STATUSES:
                        conn.execute('UPDATE messages SET status=? WHERE id=?', (body['status'], msg_id))
                    if 'operator_note' in body:
                        conn.execute('UPDATE messages SET operator_note=? WHERE id=?',
                                     (str(body['operator_note'] or ''), msg_id))
                    conn.commit()
                    self.send_json({'ok': True})
                finally:
                    conn.close()
            return

        self.send_json({'error': 'Not found'}, 404)

    def do_DELETE(self):
        self._method = 'DELETE'
        if self._refuse_cross_origin():
            return
        path = urllib.parse.urlparse(self.path).path

        if path == '/api/drill':
            with _drill_lock:
                _drill.clear(); _drill_ready.clear()
            self.send_json({'ok': True}); return

        with _db_lock:
            conn = get_db()
            try:
                m = re.match(r'^/api/messages/([^/]+)$', path)
                if m:
                    conn.execute('DELETE FROM messages WHERE id=?', (m.group(1),))
                    conn.commit()
                    self.send_json({'ok': True}); return

                m = re.match(r'^/api/notes/([^/]+)$', path)
                if m:
                    conn.execute('DELETE FROM notes WHERE id=?', (m.group(1),))
                    conn.commit()
                    self.send_json({'ok': True}); return

                m = re.match(r'^/api/actions/([^/]+)$', path)
                if m:
                    conn.execute('DELETE FROM actions WHERE id=?', (m.group(1),))
                    conn.commit()
                    self.send_json({'ok': True}); return

                m = re.match(r'^/api/events/([^/]+)$', path)
                if m:
                    # Only an empty, inactive event can be removed; a worked event is history.
                    eid = m.group(1)
                    row = conn.execute('SELECT active FROM events WHERE id=?', (eid,)).fetchone()
                    if not row:
                        self.send_json({'error': 'No such event'}, 404); return
                    if row['active']:
                        self.send_json({'error': 'Switch to another event first'}, 400); return
                    if _event_counts(conn, eid)['msgs']:
                        self.send_json({'error': 'That event has reports on file; close it instead'}, 400); return
                    for tbl in ('messages', 'roster', 'notes', 'actions'):
                        conn.execute(f'DELETE FROM {tbl} WHERE event_id=?', (eid,))
                    conn.execute('DELETE FROM events WHERE id=?', (eid,))
                    conn.commit()
                    self.send_json({'ok': True}); return

                self.send_json({'error': 'Not found'}, 404)
            finally:
                conn.close()


# ── Startup ───────────────────────────────────────────────────────────────────
def _is_private_v4(ip: str) -> bool:
    try:
        a, b_ = (int(x) for x in ip.split('.')[:2])
    except ValueError:
        return False
    return a == 10 or (a == 172 and 16 <= b_ <= 31) or (a == 192 and b_ == 168)


def _host_ipv4s() -> list:
    """Every IPv4 address of this computer that is not loopback / link-local, private ranges first."""
    found = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in found and not ip.startswith('127.') and not ip.startswith('169.254.'):
                found.append(ip)
    except Exception:
        pass
    return sorted(found, key=lambda ip: (not _is_private_v4(ip), ip))


# ── Folder browser for the Message Center: only for the person at this laptop ──
_OWN_IPS = None
def _own_addresses() -> set:
    """This computer's own addresses: a request from one of them comes from someone at this laptop."""
    global _OWN_IPS
    if _OWN_IPS is None:
        ips = {'127.0.0.1', '::1', '::ffff:127.0.0.1'}
        try:
            ips.add(get_local_ip())
        except Exception:
            pass
        for fn in (lambda: socket.gethostbyname_ex(socket.gethostname())[2], lambda: [a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None)]):
            try:
                ips |= set(fn())
            except Exception:
                pass
        _OWN_IPS = {i.split('%')[0] for i in ips}
    return _OWN_IPS


FOLDER_MARKS = {   # what each kind of folder looks like, so the right one can be marked in the list
    'map': ('map data', lambda d: (d / 'csv' / 'organizations.csv').is_file() or (d / 'simulator' / 'organization_boundaries.geojson').is_file()
            or (d / 'organization_boundaries.geojson').is_file()),
    'winlink': ('Winlink Express', lambda d: (d / 'RMS Express.exe').is_file()),
    'any': ('', lambda d: False),
}


def _browse_folder(start: str, kind: str = 'any') -> dict:
    """One folder of this laptop: its subfolders, and which look like the kind of folder asked for."""
    label, looks = FOLDER_MARKS.get(kind, FOLDER_MARKS['any'])
    drives = [f'{c}:\\' for c in string.ascii_uppercase if os.path.exists(f'{c}:\\')] if os.name == 'nt' else ['/']
    here = pathlib.Path(start).expanduser() if start else pathlib.Path.home() / 'Documents'
    while not here.is_dir() and here.parent != here:          # a typed path that does not exist: its nearest real parent
        here = here.parent
    if not here.is_dir():
        here = pathlib.Path.home()
    mark = lambda d: bool(label) and looks(d)
    folders, error = [], ''
    try:
        for d in sorted(here.iterdir(), key=lambda x: x.name.lower()):
            try:
                if d.is_dir() and not d.name.startswith(('.', '$')) and d.name != 'System Volume Information':
                    folders.append({'name': d.name, 'path': str(d), 'mark': mark(d)})
            except OSError:
                continue
    except OSError as e:
        error = f'This folder cannot be read: {e.strerror or e}'
    return {'path': str(here), 'parent': str(here.parent) if here.parent != here else '', 'mark': mark(here), 'label': label,
            'folders': folders, 'drives': drives, 'error': error}


def get_local_ip():
    """This computer's address on the EOC network. With internet, the interface that carries the default route;
    with none (a Wi-Fi router alone, the usual EOC), the host's own addresses: a private one (10/8, 172.16/12,
    192.168/16) first. Only 127.0.0.1 when no network is up at all: phones cannot reach that."""
    for probe in ('8.8.8.8', '10.255.255.255', '192.168.255.255'):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect((probe, 80))   # UDP: nothing is sent; only picks the outgoing interface
                ip = s.getsockname()[0]
            finally:
                s.close()
            if ip and not ip.startswith('127.') and not ip.startswith('0.') and not ip.startswith('169.254.'):
                if probe == '8.8.8.8' or _is_private_v4(ip):
                    return ip
        except Exception:
            pass
    hosts = _host_ipv4s()
    return hosts[0] if hosts else '127.0.0.1'


LAN_URL_REFRESH_SEC = 60
_LAN_URL = ''
_LAN_URL_AT = 0.0
_LAN_WARNED = ''
def _lan_url():
    """The URL operators on the EOC Wi-Fi use to reach this server (the wall shows it and its QR code).
    Looked up again every minute: the laptop may join the EOC Wi-Fi after the server started."""
    global _LAN_URL, _LAN_URL_AT, _LAN_WARNED
    now = time.time()
    if not _LAN_URL or now - _LAN_URL_AT > LAN_URL_REFRESH_SEC:
        ip = get_local_ip()
        _LAN_URL, _LAN_URL_AT = f'http://{ip}:{PORT}', now
        if ip.startswith('127.') and _LAN_WARNED != ip:
            _warn_loopback_only()
        _LAN_WARNED = ip
    return _LAN_URL


def _warn_loopback_only():
    print()
    print('  ' + '!' * 72)
    print('  !!  NO NETWORK: this computer has no address phones can reach (only 127.0.0.1).')
    print('  !!  Join the EOC Wi-Fi (or plug in the router), then wait a minute: the wall and')
    print('  !!  the phone page show the new address by themselves. Until then only this')
    print('  !!  computer can open the Message Center.')
    print('  ' + '!' * 72)
    print()


if __name__ == '__main__':
    init_db()
    net_url  = _lan_url()   # warns loudly when only loopback is found
    ip = net_url.split('//', 1)[1].rsplit(':', 1)[0]
    loc_url  = f'http://localhost:{PORT}'

    # Start background threads
    threading.Thread(target=timed_backup_loop, daemon=True, name='auto-backup').start()
    threading.Thread(target=usb_watchdog_loop, daemon=True, name='usb-watchdog').start()

    # Drill configuration on the command line (unattended start): --config=<file> --eoc=<id> [--manned=a,b]
    _cfg_path = _cli_arg('config')
    _kept = SETTINGS_DIR / 'drill-config.json'
    if not _cfg_path and _load_settings().get('drillEoc') and _kept.is_file():
        try:   # the configuration applied last time: identity and call sign again, no new event
            _apply_drill_config(json.loads(_kept.read_text(encoding='utf-8-sig')), _load_settings()['drillEoc'],
                                _load_settings().get('drillManned') or [], new_event=False)
        except Exception as _ce:
            print(f'  [CONFIG] Could not apply the kept drill configuration: {_ce}')
    if _cfg_path:
        try:
            _cfg = json.loads(pathlib.Path(_cfg_path).read_text(encoding='utf-8-sig'))
            _apply_drill_config(_cfg, _cli_arg('eoc') or '', (_cli_arg('manned') or '').split(','))
            _save_settings({'drillConfigFile': str(pathlib.Path(_cfg_path).resolve()), 'drillEoc': _cli_arg('eoc') or '',
                            'drillManned': [m for m in (_cli_arg('manned') or '').split(',') if m]})
        except Exception as _ce:
            print(f'  [CONFIG] Could not load {_cfg_path}: {_ce}')

    # Winlink watcher: folder and callsign(s) from the command line, else the settings file, else Winlink's
    # install folder; with no callsign chosen and only one on this computer, that one
    _set = _load_settings()
    _wfolder = _cli_arg('winlink-folder') or _set.get('winlinkFolder') or str(WINLINK_DEFAULT_PATH)
    _wcli = _cli_arg('winlink-callsign')
    _wcalls = _norm_calls(_wcli if _wcli is not None else _set.get('winlinkCallsigns'))
    _wfrom = 'command line' if _wcli is not None else ('settings file' if _wcalls else '')
    if not _wcalls and len(_winlink_callsigns(_wfolder)) == 1:
        _wcalls, _wfrom = _winlink_callsigns(_wfolder), 'the only callsign here'
    if pathlib.Path(_wfolder).exists() and _set.get('winlinkWatch', True):
        with _watcher_lock:
            _watcher_state['enabled']    = True
            _watcher_state['watch_path'] = _wfolder
            _watcher_state['callsigns']  = _wcalls
    try:
        DRILL_MIME_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    threading.Thread(target=_watcher_loop, daemon=True, name='watcher').start()

    # Create and auto-start the Internet Drop Folder watcher
    try:
        DROP_FOLDER_DEFAULT.mkdir(parents=True, exist_ok=True)
    except Exception as _de:
        print(f'  [DROP]   Could not create drop folder: {_de}')
    with _drop_lock:
        _drop_state['enabled']    = True
        _drop_state['watch_path'] = str(DROP_FOLDER_DEFAULT)
    threading.Thread(target=_drop_loop, daemon=True, name='drop-watcher').start()

    # Discovery: announce this EOC on the LAN and listen for others (phones pick from the list)
    threading.Thread(target=_discovery_announce_loop, daemon=True, name='discovery-announce').start()
    threading.Thread(target=_discovery_listen_loop, daemon=True, name='discovery-listen').start()

    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), EOCHandler)

    width = max(len(net_url), len(loc_url)) + 14
    bar = '=' * width
    def row(label, value=''):
        content = f'  {label:<10}{value}' if value else f'  {label}'
        return f'  | {content:<{width - 4}} |'

    # Which EOC is this? (set on the Setup tab; same software at Satellite, Stake and Council / Area EOCs)
    try:
        with _db_lock:
            _c = get_db()
            try:
                _r = _c.execute('SELECT data_json FROM incident WHERE singleton=1').fetchone()
                _ev = _active_event(_c)
                _ev['counts'] = _event_counts(_c, _ev['id'])
            finally:
                _c.close()
        _inc = json.loads(_r['data_json']) if _r else {}
    except Exception:
        _inc = {}; _ev = {}
    _eoc_line = (_inc.get('eocName') or 'not named yet - set it on the Setup tab')
    _lvl = {'satellite': 'Satellite EOC', 'stake': 'Stake EOC', 'area': 'Council / Area EOC'}.get(_inc.get('eocLevel', ''), '')
    if _lvl:
        _eoc_line = f'{_eoc_line}  [{_lvl}]'
    _ev_line = ((_ev.get('name') or 'unnamed - open one on the Setup tab')
                + (f'  [{_ev.get("status", "open")}, {_ev.get("counts", {}).get("msgs", 0)} reports]' if _ev else ''))

    print()
    print(f'  +{bar}+')
    print(row('Church of Jesus Christ EMCOMM — EOC Message Center Server'))
    print(f'  +{bar}+')
    print(row('Local:',   loc_url))
    print(row('Network:', net_url))
    print(f'  |{" " * width}|')
    print(row('Share the Network URL with all EOC operators on this WiFi.'))
    print(row('Wall display (TV / projector, read-only, press F):'))
    print(row(f'             {net_url}/wall'))
    print(row('Phones on this Wi-Fi (new forms, Send to EOC):'))
    print(row(f'             {net_url}/m'))
    print(f'  |{" " * width}|')
    print(row('This EOC:', _eoc_line))
    print(row('Event:', _ev_line))
    print(row('Roll-ups:  .json from a lower EOC merge automatically'))
    print(row('           (Drop Folder or Winlink attachment).'))
    print(row('Comms:     a comms-sheet .json (contacts, gateways, nets) arriving'))
    print(row('           the same way replaces the sheet on file when newer.'))
    print(f'  |{" " * width}|')
    print(row(f'Auto-backup: every {BACKUP_INTERVAL_SEC // 60} min -> {BACKUP_DIR.name}/'))
    print(row('USB backup:  insert any USB drive to back up immediately.'))
    print(row('Manual:      GET /api/backup  or  Export button in the EOC UI.'))
    print(f'  |{" " * width}|')
    _wv = _watcher_view()
    if _wv.get('enabled') and _wv.get('mode') == 'winlink':
        print(row(f'Watcher:     AUTO — Winlink Express at {_wv["watch_path"]}'))
        if _wv['callsigns']:
            print(row('             feeds this EOC: ' + ', '.join(_wv['callsigns']) + f'  ({_wfrom})'))
        else:
            print(row('             NO CALLSIGN CHOSEN: reading ' + (', '.join(_wv['available']) or 'every station') + '.'))
            print(row('             Choose on the Message Center watcher bar, or set'))
            print(row('             "winlinkCallsigns" in eoc-settings.json (see below).'))
        if _wv['missing']:
            print(row('             NOT FOUND here: ' + ', '.join(_wv['missing']) + ' (check the callsign).'))
        print(row('             Received messages since the event began; Winlink keeps its own.'))
    elif _wv.get('enabled') and _wv.get('mode') == 'folder':
        print(row('Watcher:     AUTO — .mime files in a folder (moved to EOC Ingested):'))
        print(row(f'             {_wv["watch_path"]}'))
    else:
        print(row('Watcher:     Winlink Express not found (C:\\RMS Express).'))
        print(row('             Set its folder on the Message Center watcher bar.'))
    print(row(f'Settings:    {SETTINGS_FILE}'))
    print(f'  |{" " * width}|')
    print(row('Drop:        Internet drop folder — always watching.'))
    print(row(f'             {DROP_FOLDER_DEFAULT}'))
    print(row('             Save any Worker Form .txt file here to ingest (within 10 sec).'))
    print(f'  |{" " * width}|')
    print(row('Press Ctrl+C to stop.'))
    print(f'  +{bar}+')
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Server stopped.')
