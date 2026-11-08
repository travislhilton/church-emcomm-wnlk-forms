#!/usr/bin/env python3
"""EMCOMM simulator server (Python standard library only).

Serves the simulator page (simulation/index.html), the scenario catalog, and the
geographic dataset that lives OUTSIDE the repository; loads the organization pack at
run time; plans and plays runs against a running EOC (Emergency Operations Center)
server (eoc/eoc_server.py, port 8080).

    python simulation/sim_server.py                       # port 8090, the pack chosen last time (Setup, step 1)
    python simulation/sim_server.py 8091                  # another port
    python simulation/sim_server.py --data "D:\\Drills\\2 Organization pack"   # export root (dataset + pack source)
    python simulation/sim_server.py --privacy real        # real contacts (default: pseudonymized)
    set EMCOMM_SIM_DATA=D:\\Drills\\2 Organization pack   # same as --data

Under /data/ only files below ``<export root>/simulator/`` are served (GeoJSON layers,
overlay images, scale tables). The contact workbook, CSV files and PDFs in the export
root are never reachable through this server. The organization pack is served to the page under
/api/pack in the privacy mode chosen on the Setup tab (pseudonymized by default); nothing from it is
written under the repository.

The server listens on the LAN (participants' phones open /results there). Real contact data beyond the
served pack (the local-roles file with real names, phones and emails; a scenario's local binding with
partner-agency contact names) is served only to the controller laptop itself (a request from this
computer's own addresses) or when the pack is loaded with real contacts (consent recorded). Every other
device gets the pseudonymized view; only the controller laptop may change the local roles. In a
pseudonymized drill the run is planned with the agency contacts reduced to their title, so /api/run,
/report, /results and /debrief never carry those names either.

Settings (pack path, privacy mode, EOC address) persist in the user's local app-data
folder, outside the repository. Generated runs go to ``<export root>/simulation/runs/``.
"""
import datetime
import json
import time
import re
import os
import socket
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine      # noqa: E402
import orgpack     # noqa: E402
import privacy     # noqa: E402

REPO = HERE.parent
DEFAULT_EXPORT = REPO / 'secure data' / 'cdol-2026-10-30'
PORT = 8090
SETTINGS_DIR = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CONFIG_HOME') or (Path.home() / '.config')) / 'Church of Jesus Christ EMCOMM'
_OLD_SETTINGS_DIR = SETTINGS_DIR.with_name('Church EMCOMM')   # the short-lived name of 2026-10-31.5
if _OLD_SETTINGS_DIR.is_dir() and not SETTINGS_DIR.exists():
    try:
        _OLD_SETTINGS_DIR.rename(SETTINGS_DIR)
    except OSError:
        pass
SETTINGS_FILE = SETTINGS_DIR / 'simulator-settings.json'

CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8', '.geojson': 'application/geo+json; charset=utf-8',
    '.csv': 'text/csv; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.pgw': 'text/plain; charset=utf-8',
    '.prj': 'text/plain; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
}


_OWN = {'ips': None}


def own_addresses() -> set:
    """This computer's own addresses: a request from one of them comes from the controller laptop."""
    if _OWN['ips'] is None:
        ips = {'127.0.0.1', '::1', get_local_ip()}
        try:
            ips |= set(socket.gethostbyname_ex(socket.gethostname())[2])
        except Exception:
            pass
        try:
            ips |= {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None)}
        except Exception:
            pass
        _OWN['ips'] = {i.split('%')[0] for i in ips}
    return _OWN['ips']


def default_pack() -> str:
    """The maintainer's own export when this copy sits beside it; otherwise no default (never a path that is not there)."""
    return str(DEFAULT_EXPORT) if DEFAULT_EXPORT.is_dir() else ''


def is_pack_folder(d: Path) -> bool:
    return (d / 'csv' / 'organizations.csv').is_file()


def browse_folder(start: str) -> dict:
    """One folder of this laptop for the Setup tab's Browse window: subfolders, which are organization packs, which
    hold one (a participant package), the .zip files that must be unzipped first, and the usual places to start."""
    drives = [f'{c}:\\' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{c}:\\')] if os.name == 'nt' else ['/']
    home = Path.home()
    places = [{'name': n, 'path': str(home / n)} for n in ('Desktop', 'Documents', 'Downloads') if (home / n).is_dir()]
    here = Path(start).expanduser() if start else home / 'Documents'
    while not here.is_dir() and here.parent != here:     # a typed path that does not exist: its nearest real parent
        here = here.parent
    if not here.is_dir():
        here = home

    def holds_pack(d: Path) -> list:
        found = []
        try:
            for i, c in enumerate(d.iterdir()):
                if i > 200:
                    break
                if c.is_dir() and is_pack_folder(c):
                    found.append(str(c))
        except OSError:
            pass
        return found
    folders, zips, error = [], [], ''
    try:
        for d in sorted(here.iterdir(), key=lambda x: x.name.lower()):
            try:
                if d.is_dir() and not d.name.startswith(('.', '$')) and d.name != 'System Volume Information':
                    pk = is_pack_folder(d)
                    folders.append({'name': d.name, 'path': str(d), 'pack': pk, 'holds_pack': (not pk) and bool(holds_pack(d))})
                elif d.is_file() and d.suffix.lower() == '.zip':
                    zips.append(d.name)
            except OSError:
                continue
    except OSError as e:
        error = f'This folder cannot be read: {e.strerror or e}'
    return {'path': str(here), 'parent': str(here.parent) if here.parent != here else '', 'pack': is_pack_folder(here),
            'packs_inside': holds_pack(here), 'folders': folders, 'zips': zips, 'drives': drives, 'places': places, 'error': error}


def pack_drill_config() -> Path:
    """drill-config.json inside the loaded pack (a participant package carries one), or None."""
    p = STATE.settings.get('packPath') or ''
    f = Path(p) / 'simulation' / 'drill-config.json' if p else None
    return f if f and f.is_file() else None


def is_controller(ip: str) -> bool:
    """True for a request from the controller laptop (loopback or one of its own addresses)."""
    ip = (ip or '').split('%')[0]
    if ip.startswith('::ffff:'):
        ip = ip[7:]
    return ip.startswith('127.') or ip == '::1' or ip in own_addresses()


def get_local_ip() -> str:
    """The LAN address other devices can reach (same trick as eoc_server.py)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_settings(s: dict):
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(s, indent=1), encoding='utf-8')
    except Exception as e:
        print(f'  WARNING: settings not saved: {e}')


def parse_args(argv):
    port, export, priv = PORT, os.environ.get('EMCOMM_SIM_DATA') or '', ''
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == '--data' and args:
            export = args.pop(0)
        elif a == '--privacy' and args:
            priv = args.pop(0)
        elif a.isdigit():
            port = int(a)
        elif a in ('-h', '--help'):
            print(__doc__)
            sys.exit(0)
    return port, export, priv


def dataset_info(export: Path) -> dict:
    """What the page needs to know about the dataset: present or not, and counts."""
    sim = export / 'simulator'
    info = {'ok': False, 'exportRoot': str(export), 'simulatorDir': str(sim), 'counts': {}}
    if not sim.is_dir():
        info['error'] = 'simulator folder not found under the export root'
        return info
    try:
        # the overlay images (the directory's own map artwork) are optional: boundaries and buildings are enough for a map
        mp = sim / 'overlays' / 'manifest.json'
        man = json.loads(mp.read_text(encoding='utf-8')) if mp.is_file() else []
        info['counts']['overlays'] = len(man)
        info['counts']['artwork'] = sum(1 for r in man if r.get('kind') == 'source_map_artwork')
        info['counts']['boundaryImages'] = sum(1 for r in man if r.get('kind') == 'transparent_organization_boundary')
        info['counts']['missingImages'] = sum(1 for r in man if not (export / r['image_path']).is_file())
        gj = json.loads((sim / 'organization_boundaries.geojson').read_text(encoding='utf-8'))
        info['counts']['organization_boundaries'] = len(gj.get('features', []))
        for name in ('buildings', 'organization_locations'):
            f = sim / f'{name}.geojson'
            info['counts'][name] = len(json.loads(f.read_text(encoding='utf-8')).get('features', [])) if f.is_file() else 0
        info['ok'] = True
    except Exception as e:
        info['error'] = f'{type(e).__name__}: {e}'
    return info


class State:
    """Server-wide state: the pack as loaded, the pack as served (privacy applied), the current run."""

    def __init__(self):
        self.lock = threading.RLock()
        self.export = None            # Path: export root (dataset + pack source)
        self.pack_real = None
        self.pack = None
        self.privacy = 'pseudonymized'
        self.consent = None           # {'by', 'role', 'date', 'recordedBy', 'recordedAt', 'packPath'} while real contacts are loaded
        self.pack_error = ''
        self.runner = None
        self.settings = load_settings()
        self.lan_ip = get_local_ip()
        self.port = PORT

    def pack_dir(self) -> Path:
        # with no pack yet, runs and settings-like files go under the user's app-data folder
        return self.export if self.export else SETTINGS_DIR

    def load_pack(self, path: str, mode: str, consent: dict = None):
        """Load (or reload) the pack. Real contacts need the recorded consent (checked by the caller);
        it is stamped into the served pack (so every run and report carries it) and remembered in the
        settings for this pack path, so a restart with --privacy real can honour it. Pseudonymized drops it."""
        with self.lock:
            p = Path(path).expanduser().resolve()
            pack = orgpack.load(p)
            if pack.get('pre_pseudonymized'):      # a participant package holds no real contacts, whatever was asked
                mode = 'pseudonymized'
            if mode == 'pseudonymized':
                salt = privacy.salt_for(p if p.is_dir() else p.parent)
                served = privacy.pseudonymize(pack, salt)
                consent = None
            else:
                served = privacy.apply(pack, 'real')
                consent = dict(consent or self.consent or {})
                consent['packPath'] = str(p)
                served['consent'] = consent
            self.export, self.pack_real, self.pack, self.privacy, self.pack_error = (p if p.is_dir() else p.parent), pack, served, mode, ''
            self.consent = consent or None
            self.settings.update({'packPath': str(p), 'privacy': mode})
            if consent:
                self.settings['consent'] = consent
            else:
                self.settings.pop('consent', None)
            save_settings(self.settings)

    def scenario_dirs(self) -> list:
        # a pack's own scenarios (beside its export, never in the repository) come before the built-in ones
        return [engine.pack_scenarios_dir(self.export)] if self.export else []

    def local_binding(self, sid: str) -> Path:
        return self.pack_dir() / 'simulation' / f'{sid}.local.json'

    def runs_dir(self) -> Path:
        return self.pack_dir() / 'simulation' / 'runs'

    def info(self) -> dict:
        with self.lock:
            d = dataset_info(self.export) if self.export else {'ok': False, 'error': 'no export root / pack loaded', 'counts': {}}
            d['lanIp'] = self.lan_ip
            d['eocUrl'] = self.settings.get('eocUrl') or f'http://{self.lan_ip}:8080'
            d['site'] = self.settings.get('site') or {}
            d['scenario'] = self.settings.get('scenario', '')
            d['drill'] = self.settings.get('drill') or None
            d['controllerUrl'] = f'http://{self.lan_ip}:{self.port}'
            d['settingsFile'] = str(SETTINGS_FILE)
            d['pack'] = orgpack.summary(self.pack) if self.pack else None
            d['packPath'] = self.settings.get('packPath', '')
            d['packError'] = self.pack_error
            d['localRoles'] = sum(1 for c in (self.pack_real or {}).get('contacts', []) if c.get('local'))
            d['privacy'] = self.privacy
            d['consent'] = self.consent if self.privacy == 'real' else None
            d['run'] = {'id': self.runner.run['id'], 'status': self.runner.run['clock']['status'], 'scenario': self.runner.run['scenario']['name']} if self.runner else None
            d['runsDir'] = str(self.runs_dir())
            d['packDrillConfig'] = bool(self.pack) and pack_drill_config() is not None   # a participant package carries the drill's settings
            return d


STATE = State()


def eoc_probe(url: str) -> dict:
    """Status, incident, watcher and drop-folder state of an EOC server (server-side, no CORS)."""
    url = url.rstrip('/')
    out = {'ok': False, 'url': url}
    try:
        out['status'] = engine._http(url + '/api/status', timeout=4)
        out['ok'] = True
    except Exception as e:
        out['error'] = str(e)
        return out
    for key, path in (('incident', '/api/incident'), ('watcher', '/api/watcher/status'), ('drop', '/api/drop/status'), ('roster', '/api/roster')):
        try:
            out[key] = engine._http(url + path, timeout=4)
        except Exception as e:
            out[key] = {'error': str(e)}
    w, d = out.get('watcher') or {}, out.get('drop') or {}
    out['receivedDir'] = (w.get('watch_path', '') if w.get('enabled') and w.get('watch_path') and w.get('mode', 'folder') == 'folder'
                          and Path(w['watch_path']).is_dir() else '')   # never write into Winlink Express's own store
    if not out['receivedDir'] and w.get('enabled') and w.get('drillDir') and Path(w['drillDir']).is_dir():
        out['receivedDir'] = w['drillDir']   # the EOC's Simulated Winlink inbox, read beside the real Winlink folder
    out['dropDir'] = d.get('watch_path', '') if d.get('enabled', True) and d.get('watch_path') and Path(d['watch_path']).is_dir() else ''
    return out


def scenario_view(sid: str, real: bool) -> dict:
    """The scenario merged with its local binding. Unless `real` (the controller laptop, or real contacts loaded),
    partner-agency contacts keep only their title, any text naming them loses the name, and the binding's
    file path and private notes are left out."""
    sc = engine.load_scenario(sid, local_path=STATE.local_binding(sid), extra_dirs=STATE.scenario_dirs())
    if real:
        return sc
    names = set()
    sc = privacy.scrub_names(privacy.strip_agency_contacts(sc, names), names)
    sc.pop('local_notes', None)
    if sc.get('local_binding'):
        sc['local_binding'] = 'yes'
    return sc


def scenario_for_run(sid: str) -> dict:
    """What a run is planned from: in a pseudonymized drill without agency contact names (the run is served on the LAN)."""
    return scenario_view(sid, STATE.privacy == 'real')


def local_roles_view(trusted: bool) -> dict:
    """GET /api/local-roles. The controller laptop (or a real-contact drill) sees the file as typed; any other
    device sees each role with the pseudonyms the drill uses, no notes and no file path, read only."""
    lp = orgpack.local_roles_path(STATE.settings.get('packPath') or STATE.export)
    base = {'ok': True, 'suggested': orgpack.SUGGESTED_ROLES, 'orgs': orgpack.organizations(STATE.pack),
            'required': orgpack.required_status(STATE.pack, STATE.settings.get('site') or {})}
    roles = orgpack.read_local_roles(lp)
    if trusted:
        return dict(base, path=str(lp), roles=roles, readonly=False)
    served = {c['id']: c for c in STATE.pack.get('contacts', []) if c.get('local')}
    out = []
    for i, r in enumerate(roles):
        c = served.get(f'local-{i + 1}') or {}
        out.append({'org': r.get('org', ''), 'role': r.get('role', ''), 'first': c.get('first', ''), 'last': c.get('last', ''),
                    'mobile': c.get('mobile', ''), 'phone': c.get('phone', ''), 'email': c.get('email', ''), 'note': ''})
    return dict(base, path='', roles=out, readonly=True)


def plan_run(body: dict) -> dict:
    """Plan a run from the Setup tab's request (or the same request again, for a session reset). Call with STATE.lock held."""
    sid = body.get('scenario') or ''
    sc = scenario_for_run(sid)
    site = dict(body.get('site') or {})
    eoc = dict(body.get('eoc') or site.get('eoc') or {})
    eoc_url = (eoc.get('url') or STATE.settings.get('eocUrl') or f'http://{STATE.lan_ip}:8080').rstrip('/')
    probe = eoc_probe(eoc_url)
    st = probe.get('status') or {}
    eoc.setdefault('name', st.get('eocName', ''))
    eoc.setdefault('level', st.get('eocLevel', ''))
    _calls = (probe.get('watcher') or {}).get('callsigns') or []   # the Winlink call sign that feeds this EOC
    if _calls:
        eoc.setdefault('call', _calls[0])
        eoc.setdefault('winlink', f'{_calls[0]}@winlink.org')
    eoc['url'] = eoc_url
    if site:
        site['eoc'] = eoc
    run = engine.plan(STATE.pack, sc, {'stakes': body.get('stakes'), 'units': body.get('units'), 'exclude': body.get('exclude'),
                                       'eoc': eoc, 'seed': body.get('seed'), 'speed': body.get('speed'), 'today': body.get('today'),
                                       'site': site or None})
    run['eoc_probe'] = {'ok': probe.get('ok'), 'event': st.get('activeEventName', ''), 'receivedDir': probe.get('receivedDir', ''), 'dropDir': probe.get('dropDir', '')}
    run['plan_request'] = {k: v for k, v in body.items() if k != 'session'}
    STATE.settings['lastPlan'] = run['plan_request']
    if STATE.runner:
        STATE.runner.shutdown()
    STATE.runner = engine.Runner(run, eoc_url, STATE.runs_dir(), received_dir=probe.get('receivedDir', ''), drop_dir=probe.get('dropDir', ''),
                                 controller_url=f'http://{STATE.lan_ip}:{STATE.port}')
    STATE.runner.refresh_board()
    STATE.settings['eocUrl'] = eoc_url
    if site:
        STATE.settings['site'] = {k: v for k, v in site.items() if k != 'eoc'}
    save_settings(STATE.settings)
    return run


# ── the trainer's session: set up before the meeting, reset, GO, live, results; saved and resumable ──
RUN_FILE = re.compile(r'^run-(\d{8}-\d{6}-[0-9a-f]{4})\.json$')


def list_sessions(limit: int = 40) -> list:
    """The runs saved beside the pack, newest first: what each was, how far it got, whether it can be resumed."""
    out = []
    d = STATE.runs_dir()
    if not d.is_dir():
        return out
    cur = STATE.runner.run['id'] if STATE.runner else ''
    for f in sorted(d.glob('run-*.json'), key=lambda x: x.stat().st_mtime, reverse=True):
        m = RUN_FILE.match(f.name)
        if not m:
            continue
        try:
            r = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        c = r.get('clock') or {}
        hist = r.get('score_hist') or []
        out.append({'id': m.group(1), 'scenario': (r.get('scenario') or {}).get('name', ''), 'site': (r.get('site') or {}).get('label', ''),
                    'status': c.get('status', ''), 'minute': round(float(c.get('saved_elapsed', c.get('elapsed_min', 0)) or 0), 1),
                    'saved': f.stat().st_mtime, 'session': bool((r.get('session') or {}).get('ready')), 'rehearsal': bool(r.get('rehearsal')),
                    'pct': (hist[-1] or {}).get('pct') if hist else None, 'report': (d / f'run-{m.group(1)}-report.html').is_file(),
                    'current': m.group(1) == cur, 'resumable': c.get('status') in ('running', 'paused', 'scheduled') and m.group(1) != cur})
        if len(out) >= limit:
            break
    return out


def debrief_history(r) -> list:
    """This group's earlier scored runs of the same scenario (sessions and plain runs, never rehearsals), oldest first."""
    name = r.run['scenario']['name']
    out = []
    for x in reversed(list_sessions(200)):
        # the current run is added by the debrief with its live score (the saved one can be up to 30 s old)
        if x['current'] or x['scenario'] != name or x['rehearsal'] or x['pct'] is None or x['status'] not in ('stopped', 'finished'):
            continue
        out.append({'pct': x['pct'], 'current': False, 'label': datetime.datetime.fromtimestamp(x['saved']).strftime('%d %b')})
    return out


def debrief_next(r) -> list:
    """Other developed scenarios that fit this pack, for 'the next drill'."""
    try:
        cat = engine.catalog(extra_dirs=STATE.scenario_dirs())
    except Exception:
        return []
    bbox = orgpack.Index(STATE.pack).bbox() if STATE.pack else None
    out = []
    for s in cat['scenarios']:
        if s['id'] == r.run['scenario']['id'] or s.get('status', 'developed') == 'outline':
            continue
        if bbox and engine.bbox_overlaps(s.get('applies', {}).get('bbox'), bbox) is False:
            continue
        out.append(s['name'])
    return out


def session_status() -> dict:
    """Everything the Session tab shows: each step of the trainer's flow with its state."""
    r = STATE.runner
    url = STATE.settings.get('eocUrl') or f'http://{STATE.lan_ip}:8080'
    probe = eoc_probe(url)
    st = probe.get('status') or {}
    run = None
    if r:
        c = r.run['clock']
        run = {'id': r.run['id'], 'scenario': r.run['scenario']['name'], 'status': c['status'], 'minute': round(r.elapsed(), 1),
               'duration': c.get('duration_min', 240), 'speed': c['speed'], 'site': (r.run.get('site') or {}).get('label', ''),
               'session': bool((r.run.get('session') or {}).get('ready')), 'rehearsal': bool(r.run.get('rehearsal')),
               'event': (r.run.get('session') or {}).get('event', ''), 'pace': engine.pace_at(r.run['pace'], r.elapsed()),
               'counts': engine.counts(r.run), 'score': r.score_brief(), 'start_at_ms': int(c['start_at_wall'] * 1000) if c.get('start_at_wall') else 0,
               'ready': [n for row in (r.run.get('board') or []) if row.get('self') for n in (row.get('ready') or [])]}
        ph = [p for p in r.run.get('phases', []) if p['from'] <= r.elapsed() < p['to']]
        run['phase'] = ph[0]['title'] if ph else ''
        nxt = sorted((it for it in r.run['items'] if it['status'] == 'pending' and it.get('local', True)), key=lambda it: it['t'])[:5]
        run['next'] = [{'t': it['t'], 'kind': it['kind'], 'what': (it.get('work') or {}).get('title') or it.get('unit') or (it.get('role') or '').replace('_', ' ') or it['kind']} for it in nxt]
    sessions = list_sessions()
    return {'ok': True, 'pack': bool(STATE.pack), 'pack_label': (STATE.pack or {}).get('source', ''), 'privacy': STATE.privacy,
            'eoc': {'url': url, 'ok': bool(probe.get('ok')), 'name': st.get('eocName', ''), 'event': st.get('activeEventName', ''), 'pace': st.get('pace', '')},
            'planned_before': bool(STATE.settings.get('lastPlan')), 'run': run,
            'resumable': [x for x in sessions if x['resumable']], 'sessions': sessions[:12],
            'results_url': f'http://{STATE.lan_ip}:{STATE.port}/results'}


def session_reset(body: dict) -> dict:
    """Reset for the session: whatever ran before (a rehearsal) is stopped and kept as a rehearsal; the EOC gets a
    fresh drill event (no rehearsal traffic, the SITREP clock starts at GO); the same run is planned again at T+0;
    PACE is set to the scenario's first level; every EOC screen shows the drill ready, waiting for the trainer."""
    with STATE.lock:
        if not STATE.pack:
            return {'ok': False, 'error': 'Load an organization pack first (Setup, step 1).'}
        r = STATE.runner
        req = dict((r.run.get('plan_request') if r else None) or STATE.settings.get('lastPlan') or {})
        if not req.get('scenario'):
            return {'ok': False, 'error': 'Plan the run once first (Setup, step 4): the reset plans the same run again.'}
        if r:
            if r.run['clock']['status'] in ('running', 'paused', 'scheduled', 'stopped'):
                r.run['rehearsal'] = True
            if r.run['clock']['status'] in ('running', 'paused', 'scheduled'):
                r.stop()
            r.save()
        url = ((req.get('eoc') or {}).get('url') or STATE.settings.get('eocUrl') or f'http://{STATE.lan_ip}:8080').rstrip('/')
        sc = scenario_for_run(req['scenario'])
        name = str(body.get('event') or '').strip() or f"DRILL: {sc['name']} (THIS IS AN EXERCISE)"
        event_ok, event_err = False, ''
        if body.get('new_event', True):
            try:
                inc = engine._http(url + '/api/incident', timeout=5)
                ev = {'name': name, 'type': inc.get('type') or sc.get('hazard', '').capitalize(), 'sitrepHrs': inc.get('sitrepHrs') or '2',
                      'sitrepBy': inc.get('sitrepBy') or 'Stake President', 'area': inc.get('area', '')}
                engine._http(url + '/api/events', 'POST', ev, timeout=8)
                event_ok = True
            except Exception as e:
                event_err = f'The EOC at {url} did not open a fresh drill event: {e}'
        run = plan_run(req)
        nr = STATE.runner
        nr.run['session'] = {'ready': True, 'reset_ms': int(time.time() * 1000), 'event': name if event_ok else ''}
        nr._log('Session reset: ' + (f'fresh drill event "{name}" on the EOC; ' if event_ok else '') + 'planned at T+0, waiting for GO')
        nr._push_pace(engine.pace_at(run['pace'], 0), 'session reset: the scenario starts here')
        nr.save()
        nr.push_drill()
        return {'ok': True, 'run': run['id'], 'event': name if event_ok else '', 'warning': event_err, 'counts': engine.counts(run)}


def session_go(body: dict) -> dict:
    """GO: start now, or at a wall-clock time every simulator of the drill shares ("HH:MM")."""
    r = STATE.runner
    if not r:
        return {'ok': False, 'error': 'Nothing planned: plan the run, then Reset for the session.'}
    if body.get('at'):
        return r.schedule(str(body['at']))
    r.start()
    return {'ok': True, 'status': r.run['clock']['status']}


def session_resume(run_id: str) -> dict:
    """Bring back a run from its saved file (after a restart or a closed window). It comes back paused at the minute
    it was saved; GO continues it."""
    if not re.fullmatch(r'\d{8}-\d{6}-[0-9a-f]{4}', run_id or ''):
        return {'ok': False, 'error': 'unknown run'}
    f = STATE.runs_dir() / f'run-{run_id}.json'
    if not f.is_file():
        return {'ok': False, 'error': 'no saved run ' + run_id}
    with STATE.lock:
        run = json.loads(f.read_text(encoding='utf-8'))
        c = run['clock']
        if c.get('status') == 'stopped':
            return {'ok': False, 'error': 'That run was finished; open its report instead.'}
        if c.get('status') in ('running', 'scheduled'):
            c['elapsed_min'] = float(c.get('saved_elapsed', c.get('elapsed_min', 0)) or 0)
            c['started_wall'], c['start_at_wall'] = None, None
            c['status'] = 'paused' if c['elapsed_min'] > 0 else 'planned'
        url = (run.get('eoc') or {}).get('url') or STATE.settings.get('eocUrl') or f'http://{STATE.lan_ip}:8080'
        probe = eoc_probe(url)
        if STATE.runner:
            STATE.runner.shutdown()
        STATE.runner = engine.Runner(run, url, STATE.runs_dir(), received_dir=probe.get('receivedDir', ''), drop_dir=probe.get('dropDir', ''),
                                     controller_url=f'http://{STATE.lan_ip}:{STATE.port}')
        STATE.runner._log(f"Session resumed from its saved file at {engine.fmt_t(c['elapsed_min']) if hasattr(engine, 'fmt_t') else 'T+' + str(round(c['elapsed_min']))}: press GO to continue")
        STATE.runner.save()
        STATE.runner.push_drill()
        return {'ok': True, 'run': run_id, 'status': c['status'], 'minute': round(c['elapsed_min'], 1)}


def check_scenario(sid: str) -> dict:
    """The scenario validator's result for a scenario of the catalog, with its local binding and over the loaded pack."""
    import scenario_check
    try:
        sc = engine.load_scenario(sid, extra_dirs=STATE.scenario_dirs())
    except FileNotFoundError as e:
        return {'ok': False, 'errors': [str(e)], 'warnings': [], 'info': []}
    sc.pop('local_binding', None)
    lp = STATE.local_binding(sid)
    try:
        local = json.loads(lp.read_text(encoding='utf-8-sig')) if lp.is_file() else None
    except Exception as e:
        return {'ok': False, 'errors': [f'local binding: {e}'], 'warnings': [], 'info': []}
    try:
        cat = engine.catalog(extra_dirs=STATE.scenario_dirs())
    except Exception:
        cat = None
    res = scenario_check.check(sc, local, STATE.pack, cat, 'the scenario catalog')
    res['scenario'] = sid
    return res


RESULTS_EMPTY = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="20"><title>Drill results</title>
<style>body{font-family:system-ui,Arial,sans-serif;margin:24px;color:#1a2744;background:#f7f8fa}p{color:#6b7a8d}</style></head>
<body><h1>Drill results</h1><p>No drill has started on this simulator yet. This page refreshes by itself.</p>
<p style="font-size:12px">Church of Jesus Christ EMCOMM: an independent volunteer project, not an official Church product.</p></body></html>"""

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):                       # quiet: one line per request is noise during drills
        a = str(args[0]) if args else ''          # send_error logs the status code, not the request line
        if '/data/' not in a and '/api/run ' not in a and '/api/info' not in a and '/api/run/needs' not in a:
            super().log_message(fmt, *args)

    def send_bytes(self, body: bytes, ctype: str, cache: str = 'no-cache', status=HTTPStatus.OK):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj, status=HTTPStatus.OK):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode('utf-8'), CONTENT_TYPES['.json'], status=status)

    def send_file(self, path: Path, cache: str):
        ctype = CONTENT_TYPES.get(path.suffix.lower(), 'application/octet-stream')
        with open(path, 'rb') as f:
            data = f.read()
        self.send_bytes(data, ctype, cache)

    def trusted(self) -> bool:
        """Real contact data beyond the served pack goes only to the controller laptop, or to anyone in a real-contact drill."""
        return STATE.privacy == 'real' or is_controller(self.client_address[0])

    def read_body(self) -> dict:
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            return {}

    # ── GET ──
    def do_GET(self):
        url = urlsplit(self.path)
        path, q = unquote(url.path), parse_qs(url.query)
        try:
            if path in ('/', '/index.html'):
                return self.send_file(HERE / 'index.html', 'no-cache')
            if path == '/api/info':
                return self.send_json(STATE.info())
            if path == '/api/browse':            # the laptop's folders: for the person at the laptop, never for a phone on the Wi-Fi
                if not is_controller(self.client_address[0]):
                    return self.send_json({'error': 'Browse works only on the laptop that runs the simulator.'}, HTTPStatus.FORBIDDEN)
                return self.send_json(browse_folder((q.get('path') or [''])[0]))
            if path == '/api/pack/drill-config':   # the drill configuration a participant package carries in its pack
                if not is_controller(self.client_address[0]):
                    return self.send_json({'error': 'Only on the laptop that runs the simulator.'}, HTTPStatus.FORBIDDEN)
                f = pack_drill_config()
                if not f:
                    return self.send_json({'error': 'This pack has no simulation\\drill-config.json.'}, HTTPStatus.NOT_FOUND)
                return self.send_json(json.loads(f.read_text(encoding='utf-8-sig')))
            if path == '/api/pack':
                with STATE.lock:
                    if not STATE.pack:
                        return self.send_json({'error': STATE.pack_error or 'no pack loaded'}, HTTPStatus.NOT_FOUND)
                    return self.send_json(STATE.pack)
            if path == '/api/local-roles':
                with STATE.lock:
                    if not STATE.pack_real:
                        return self.send_json({'ok': False, 'error': 'Load an organization pack first.'}, HTTPStatus.NOT_FOUND)
                    return self.send_json(local_roles_view(self.trusted()))
            if path == '/api/scenarios':
                cat = engine.catalog(extra_dirs=STATE.scenario_dirs())
                bbox = orgpack.Index(STATE.pack).bbox() if STATE.pack else None
                for s in cat['scenarios']:
                    s['applies_here'] = engine.bbox_overlaps(s.get('applies', {}).get('bbox'), bbox) if bbox else None
                    s['local_binding'] = STATE.local_binding(s['id']).is_file()
                return self.send_json(cat)
            if path.startswith('/api/scenarios/') and path.endswith('/check'):
                # the scenario validator (simulation/scenario_check.py) for the Setup tab, before "Plan the run"
                sid = path[len('/api/scenarios/'):-len('/check')]
                return self.send_json(check_scenario(sid))
            if path.startswith('/api/scenarios/'):
                sid = path[len('/api/scenarios/'):]
                sc = scenario_view(sid, self.trusted())
                stake = (q.get('stake') or [''])[0]
                if stake and STATE.pack:
                    sc = dict(sc, suggested_satellite_units=engine.suggest_satellite_units(STATE.pack, sc, stake))
                return self.send_json(sc)
            if path == '/api/eoc':
                return self.send_json(eoc_probe((q.get('url') or [STATE.settings.get('eocUrl') or f'http://{STATE.lan_ip}:8080'])[0]))
            if path == '/api/session':
                return self.send_json(session_status())
            if path == '/api/sessions':
                return self.send_json({'ok': True, 'sessions': list_sessions(200)})
            if path == '/results':
                # read-only results for the room (participants' phones): the scoreboard, the done-when checks, the do-better
                # list and the timeline; refreshes itself while the clock runs
                r = STATE.runner
                if not r or r.run['clock']['status'] == 'planned':
                    return self.send_bytes(RESULTS_EMPTY.encode('utf-8'), CONTENT_TYPES['.html'])
                try:
                    r._needs_tick()
                except Exception:
                    pass
                page = engine.report_html(r.report())
                if r.run['clock']['status'] in ('running', 'paused'):
                    page = page.replace('<head>', '<head><meta http-equiv="refresh" content="30">', 1)
                return self.send_bytes(page.encode('utf-8'), CONTENT_TYPES['.html'])
            if path == '/debrief':
                # the debrief for the room (projector): slides from the after-action report, with this group's
                # earlier runs of the same scenario and the next scenarios to try
                r = STATE.runner
                if not r or r.run['clock']['status'] == 'planned':
                    return self.send_bytes(RESULTS_EMPTY.encode('utf-8'), CONTENT_TYPES['.html'])
                try:
                    r._needs_tick()
                except Exception:
                    pass
                return self.send_bytes(engine.debrief_html(r.report(), debrief_history(r), debrief_next(r), f'http://{STATE.lan_ip}:{STATE.port}/results').encode('utf-8'), CONTENT_TYPES['.html'])
            if path == '/api/run':
                r = STATE.runner
                return self.send_json(r.state() if r else {'status': 'none'})
            if path == '/api/run/export':
                r = STATE.runner
                if not r:
                    return self.send_json({'error': 'no run'}, HTTPStatus.NOT_FOUND)
                return self.send_bytes(export_text(r.state()).encode('utf-8'), CONTENT_TYPES['.txt'])
            if path in ('/api/run/report', '/api/run/report.txt', '/api/run/report.html', '/report'):
                # The after-action report: JSON for the page, text for the feedback issue, HTML to print
                r = STATE.runner
                if not r:
                    return self.send_json({'error': 'no run'}, HTTPStatus.NOT_FOUND)
                if (q.get('refresh') or ['1'])[0] != '0':
                    try:
                        r._needs_tick()
                    except Exception:
                        pass
                rep = r.report()
                fmt = (q.get('format') or [''])[0] or ('html' if path.endswith('.html') or path == '/report' else 'txt' if path.endswith('.txt') else 'json')
                if fmt == 'html':
                    return self.send_bytes(engine.report_html(rep).encode('utf-8'), CONTENT_TYPES['.html'])
                if fmt == 'txt':
                    txt = engine.report_text(rep)
                    if (q.get('redact') or [''])[0]:
                        # for a public feedback issue: unit, building, stake and place names numbered, leaders' last names dropped
                        txt = engine.redact_text(txt, [p for p in (STATE.pack, STATE.pack_real) if p])
                    return self.send_bytes(txt.encode('utf-8'), CONTENT_TYPES['.txt'])
                return self.send_json(rep)
            if path.startswith('/data/'):
                rel = path[len('/data/'):]
                if not STATE.export:
                    return self.send_error(HTTPStatus.NOT_FOUND, 'no export root loaded')
                if not rel.startswith('simulator/') or '..' in rel.split('/'):
                    return self.send_error(HTTPStatus.FORBIDDEN, 'only simulator/ files are served')
                target = (STATE.export / rel).resolve()
                try:
                    target.relative_to((STATE.export / 'simulator').resolve())
                except ValueError:
                    return self.send_error(HTTPStatus.FORBIDDEN, 'outside the simulator folder')
                if not target.is_file():
                    return self.send_error(HTTPStatus.NOT_FOUND, 'no such dataset file')
                return self.send_file(target, 'max-age=3600' if target.suffix.lower() == '.png' else 'no-cache')
            if path.startswith('/scenarios/'):
                local = (engine.SCENARIOS_DIR / path[len('/scenarios/'):]).resolve()
                if local.is_file() and str(local).startswith(str(engine.SCENARIOS_DIR)):
                    return self.send_file(local, 'no-cache')
            self.send_error(HTTPStatus.NOT_FOUND)
        except FileNotFoundError as e:
            self.send_json({'error': str(e)}, HTTPStatus.NOT_FOUND)
        except Exception as e:
            self.send_json({'error': f'{type(e).__name__}: {e}'}, HTTPStatus.INTERNAL_SERVER_ERROR)

    # ── POST ──
    def do_POST(self):
        path = unquote(urlsplit(self.path).path)
        body = self.read_body()
        try:
            if path == '/api/pack':
                mode = body.get('privacy') or STATE.privacy
                consent = None
                if mode == 'real':
                    # Real contacts only with the consent recorded on the page: who consented (normally the
                    # Stake President), the date, who records it, and the promise that nothing leaves the room.
                    c = body.get('consent') if isinstance(body.get('consent'), dict) else {}
                    by, date, rec = (str(c.get(k) or '').strip() for k in ('by', 'date', 'recordedBy'))
                    if not (body.get('confirm') and by and date and rec and c.get('inRoom')):
                        return self.send_json({'ok': False, 'error': "Real-contact mode needs the consent recorded on the page: who consented, the date, who records it, and the in-the-room promise."}, HTTPStatus.BAD_REQUEST)
                    consent = {'by': by, 'role': str(c.get('role') or 'Stake President').strip() or 'Stake President', 'date': date, 'recordedBy': rec,
                               'scope': str(c.get('scope') or '').strip(), 'recordedAt': datetime.datetime.now().isoformat(timespec='seconds')}
                where = body.get('path') or STATE.settings.get('packPath') or default_pack()
                if not where:
                    return self.send_json({'ok': False, 'error': 'Choose the organization pack folder first: press Browse.'}, HTTPStatus.BAD_REQUEST)
                STATE.load_pack(where, mode, consent)
                return self.send_json({'ok': True, 'info': STATE.info()})
            if path == '/api/local-roles':
                with STATE.lock:
                    if not STATE.pack_real:
                        return self.send_json({'ok': False, 'error': 'Load an organization pack first.'}, HTTPStatus.BAD_REQUEST)
                    if not is_controller(self.client_address[0]):
                        return self.send_json({'ok': False, 'error': 'Only the controller laptop (the one running the simulator) changes the local roles.'}, HTTPStatus.FORBIDDEN)
                    roles = [r for r in (body.get('roles') or []) if isinstance(r, dict) and str(r.get('org', '')).strip() and str(r.get('role', '')).strip()]
                    known = {o['id'] for o in orgpack.organizations(STATE.pack_real)}
                    bad = [r for r in roles if str(r['org']) not in known]
                    if bad:
                        return self.send_json({'ok': False, 'error': f'unknown organization id(s): {", ".join(str(r["org"]) for r in bad)}'}, HTTPStatus.BAD_REQUEST)
                    keep = ('org', 'role', 'first', 'last', 'mobile', 'phone', 'email', 'note')
                    roles = [{k: str(r.get(k, '')).strip() for k in keep} for r in roles]
                    pack_path = STATE.settings.get('packPath') or str(STATE.export)
                    lp = orgpack.write_local_roles(orgpack.local_roles_path(pack_path), roles)
                    STATE.load_pack(pack_path, STATE.privacy, STATE.consent)      # the same privacy mode (and consent) this session chose
                    return self.send_json({'ok': True, 'path': str(lp), 'count': len(roles), 'info': STATE.info()})
            if path == '/api/drillconfig':
                # A drill configuration (simulation/drillconfig.py): the pack, its privacy mode, the scenario and
                # what this simulator plays, given which optional EOCs have people this time.
                import drillconfig
                cfg, eoc_id = body.get('config') or {}, str(body.get('eoc') or '')
                if not isinstance(cfg, dict) or cfg.get('kind') != drillconfig.CONFIG_KIND:
                    return self.send_json({'ok': False, 'error': 'not a drill configuration file'}, HTTPStatus.BAD_REQUEST)
                me = next((e for e in cfg.get('eocs', []) if e.get('id') == eoc_id), None)
                if not me:
                    return self.send_json({'ok': False, 'error': f'no EOC {eoc_id!r} in this configuration'}, HTTPStatus.BAD_REQUEST)
                manned = list(body.get('manned') or [])
                if me.get('manned') == 'optional' and eoc_id not in manned:
                    manned.append(eoc_id)                       # this laptop has people
                mode = cfg.get('privacy') or 'pseudonymized'
                if mode == 'real':
                    return self.send_json({'ok': False, 'error': 'This configuration holds real contacts: load the pack with consent on step 1 instead.'}, HTTPStatus.BAD_REQUEST)
                pack_path = cfg.get('pack') or ''
                if not pack_path or not Path(pack_path).exists():
                    # built on another computer (a participant package): use the pack loaded on step 1 here
                    pack_path = STATE.settings.get('packPath') or default_pack()
                STATE.load_pack(pack_path, mode, None)
                if STATE.pack_error:
                    return self.send_json({'ok': False, 'error': STATE.pack_error}, HTTPStatus.BAD_REQUEST)
                site = drillconfig.site_for(cfg, eoc_id, manned)
                with STATE.lock:
                    STATE.settings['site'] = site
                    STATE.settings['scenario'] = cfg.get('scenario', '')
                    # one simulator per EOC laptop: unless told otherwise it plays against this laptop's EOC server
                    STATE.settings['eocUrl'] = (body.get('eocUrl') or f'http://{STATE.lan_ip}:8080').rstrip('/')
                    STATE.settings['drill'] = {'name': cfg.get('name', ''), 'eoc': eoc_id, 'eocName': me.get('name', ''),
                                               'manned': sorted(drillconfig.manned_set(cfg, manned))}
                    save_settings(STATE.settings)
                return self.send_json({'ok': True, 'site': site, 'scenario': cfg.get('scenario', ''), 'drill': STATE.settings['drill'], 'info': STATE.info()})
            if path == '/api/settings':
                with STATE.lock:
                    for k in ('eocUrl', 'site'):
                        if k in body:
                            STATE.settings[k] = body[k]
                    save_settings(STATE.settings)
                return self.send_json({'ok': True})
            if path == '/api/run/plan':
                with STATE.lock:
                    if not STATE.pack:
                        return self.send_json({'ok': False, 'error': 'Load an organization pack first.'}, HTTPStatus.BAD_REQUEST)
                    if STATE.runner and STATE.runner.run['clock']['status'] == 'running':
                        return self.send_json({'ok': False, 'error': 'A run is in progress. Stop it first.'}, HTTPStatus.CONFLICT)
                    run = plan_run(body)
                    return self.send_json({'ok': True, 'run': STATE.runner.state(), 'counts': engine.counts(run)})
            if path == '/api/session/reset':
                return self.send_json(session_reset(body))
            if path == '/api/session/go':
                return self.send_json(session_go(body))
            if path == '/api/session/resume':
                return self.send_json(session_resume(str(body.get('id') or '')))
            r = STATE.runner
            if path.startswith('/api/run/') and not r:
                return self.send_json({'ok': False, 'error': 'No run planned.'}, HTTPStatus.BAD_REQUEST)
            if path == '/api/run/start' or path == '/api/run/resume':
                r.start()
            elif path == '/api/run/pause':
                r.pause()
            elif path == '/api/run/stop':
                r.stop()
            elif path == '/api/run/speed':
                r.set_speed(float(body.get('speed') or 1))
            elif path == '/api/run/jump':
                r.jump(float(body.get('minute') or 0))
            elif path == '/api/run/pace':
                return self.send_json(r.set_pace(str(body.get('level') or 'P'), str(body.get('why') or ''), push=body.get('push', True)))
            elif path == '/api/run/item':
                act = body.get('action')
                if act == 'fire':
                    return self.send_json({'ok': True, 'item': r.fire(body.get('id', ''), force=bool(body.get('force')))})
                r.set_status(body.get('id', ''), {'skip': 'skipped', 'hold': 'held', 'pending': 'pending'}.get(act, 'pending'))
            elif path == '/api/run/schedule':
                return self.send_json(r.schedule(str(body.get('at') or '')))
            elif path == '/api/run/unschedule':
                r.unschedule()
            elif path == '/api/run/board':
                return self.send_json({'ok': True, 'board': r.refresh_board()})
            elif path == '/api/run/hotwash':
                r.hotwash(int(body.get('n', 0)), str(body.get('result') or ''), str(body.get('note') or ''))
            elif path == '/api/run/evidence':
                res = r.gather_evidence()
                try:
                    r._needs_tick()
                except Exception:
                    pass
                return self.send_json(res)
            elif path == '/api/run/need':
                return self.send_json(r.set_need(str(body.get('id') or ''), str(body.get('action') or '')))
            elif path == '/api/run/needs':
                # read the EOC now (the loop does this every few seconds while the clock runs)
                r._needs_tick(final=bool(body.get('final')))
                return self.send_json({'ok': True, 'score': r.score(), 'needs': r.state().get('needs', [])})
            elif path == '/api/run/report':
                rep = r.write_report()
                return self.send_json({'ok': True, 'file': str(r.runs_dir / f"run-{r.run['id']}-report.html"), 'score': rep['score']})
            elif path == '/api/run/eoc':
                # the Winlink / Drop folders can appear after planning (the operator enables the watcher): refresh them
                probe = eoc_probe(r.eoc_url)
                r.received_dir, r.drop_dir = probe.get('receivedDir', ''), probe.get('dropDir', '')
                board = r.refresh_board()
                return self.send_json({'ok': probe.get('ok', False), 'receivedDir': r.received_dir, 'dropDir': r.drop_dir, 'board': board})
            else:
                return self.send_json({'error': 'Not found'}, HTTPStatus.NOT_FOUND)
            return self.send_json({'ok': True, 'clock': r.state()['clock']})
        except (FileNotFoundError, KeyError) as e:
            self.send_json({'ok': False, 'error': str(e)}, HTTPStatus.NOT_FOUND)
        except Exception as e:
            self.send_json({'ok': False, 'error': f'{type(e).__name__}: {e}'}, HTTPStatus.INTERNAL_SERVER_ERROR)


def export_text(run: dict) -> str:
    """Hot wash and log as plain text for the drill-feedback issue."""
    L = [f"EMCOMM drill hot wash - {run['scenario']['name']}", f"Run {run['id']} - {run['created']} - privacy: {run['pack']['privacy']}" + engine.consent_line(run['pack'].get('consent')),
         f"EOC: {run['eoc'].get('name', '')} ({run['eoc'].get('level', '')}) - {len(run['scope']['units'])} units played", '']
    for h in run.get('hotwash', []):
        L.append(f"[{h.get('result') or ' '}] T+{h.get('t', 0)}: {h['check']}" + (f"  -- {h['note']}" if h.get('note') else ''))
        if h.get('evidence'):
            L.append(f"      evidence ({h.get('suggest', '')}): {h['evidence']}")
    L += ['', 'PACE timeline:'] + [f"  T+{s['t']:g} {s['level']}  {s.get('why', '')}" for s in run['pace']]
    L += ['', 'Log:'] + [f"  {e['wall']} T+{e['t']:g}  {e['text']}" for e in run.get('log', [])]
    return '\n'.join(L) + '\n'


def main():
    port, export, priv = parse_args(sys.argv[1:])
    s = STATE.settings
    pack_path = export or s.get('packPath') or default_pack()
    mode = priv or s.get('privacy') or 'pseudonymized'
    consent = s.get('consent') if isinstance(s.get('consent'), dict) else None
    if mode == 'real' and not (priv and consent and consent.get('by') and consent.get('packPath') == str(Path(pack_path).expanduser().resolve())):
        # real contacts only by an explicit choice each start (--privacy real), and only when the page
        # recorded the consent for this very pack in an earlier session; otherwise pseudonymized
        if priv == 'real':
            print('  NOTE: --privacy real ignored: no recorded consent for this pack. Record it on the Setup tab.')
        mode, consent = 'pseudonymized', None
    if not pack_path:
        STATE.pack_error = ''                    # a new laptop: nothing chosen yet, and that is not an error
    elif not Path(pack_path).expanduser().exists():
        STATE.pack_error = f'The pack used last time is not at {pack_path} any more. Choose it again: press Browse.'
    else:
        try:
            STATE.load_pack(pack_path, mode, consent)
        except Exception as e:
            STATE.pack_error = f'{type(e).__name__}: {e}'
            STATE.export = Path(pack_path) if Path(pack_path).is_dir() else None
    STATE.port = port
    srv = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print('EMCOMM simulator server')
    print(f'  Page:     http://{STATE.lan_ip}:{port}/   (this PC: http://localhost:{port}/)')
    if STATE.pack:
        c = orgpack.summary(STATE.pack)
        print(f'  Pack:     {pack_path}')
        print(f"  Loaded:   {c['stakes']} stakes, {c['units']} units, {c['buildings']} buildings, {c['contacts']} contacts - privacy: {STATE.privacy.upper()}")
    elif export or s.get('packPath'):
        print(f'  Pack:     {pack_path}')
        print(f'  WARNING:  pack not loaded: {STATE.pack_error} -- pass --data <export root> or load one on the Setup tab')
    else:
        print('  Pack:     none yet. Open the page and load the Church directory export on the Setup tab (step 1);')
        print('            it stays on this laptop. Add the callings the directory lacks (ERD, specialist) under it.')
    print(f'  Runs:     {STATE.runs_dir()}')
    print('  Stop with Ctrl+C')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if STATE.runner:
            if STATE.runner.run['clock']['status'] == 'running':
                STATE.runner.pause()                  # saved: Resume on the Session tab after the next start
            STATE.runner.save()
            STATE.runner.shutdown(clear=True)     # takes the drill bar off the EOC's screens


if __name__ == '__main__':
    main()
