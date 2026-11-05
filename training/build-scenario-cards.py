#!/usr/bin/env python3
"""Reference cards for one simulation set (a scenario drill), printed like the Quick Reference Cards.

    python training/build-scenario-cards.py <cards.json> [--out <folder>]

The card text lives with the set, not in this script: a public set's cards.json sits in the repository
(training/scenario-cards/<code>/cards.json), a community's own set beside its directory export
(secure data/<export>/simulation/cards/<code>.cards.json). A private cards file is refused for an output folder
inside the repository (except under ROOT/secure data/). Output: one print HTML and one PDF per card (US Letter, one
side per page: print double-sided, flip on long edge) and an all-cards PDF.

cards.json:
  {"kind": "church_emcomm_scenario_cards", "v": 1, "code": "CCD-1", "title": "...", "private": false,
   "scenario": "<scenario id>", "scenario_dirs": ["<folder>", ...],      optional: auto blocks read the scenario
   "training": "<training source .json>", "drill_spec": "<drill spec>",  optional: auto blocks read these
   "cards": [{"no": "A", "file": "Participant_Briefing", "role": "All participants", "color": "#4A7FC1",
              "front": {"title": "...", "blocks": [...]}, "back": {"title": "...", "blocks": [...]}}]}
  Paths are relative to the cards file. Blocks:
   {"part": "heading"}                    a section heading
   {"steps": ["html", ...]}               numbered steps ("<b>Do this</b><small>detail</small>")
   {"note": "html", "kind": "warn"}       a boxed note (kind: info, warn, ok)
   {"list": ["html", ...]}                a check list
   {"table": {"head": [...], "rows": [[...], ...]}}
   {"html": "..."}                        raw HTML
   {"auto": "pace" | "phases" | "done" | "roles" | "eocs" | "messages" | "ics", "max": n, "compact": true}
                                          built from the scenario, drill spec or training source

Needs Google Chrome (headless print to PDF), like training/build-quick-ref-pdfs.py, whose page styles it reuses.
"""
import html
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'simulation'))
import engine  # noqa: E402

_spec = importlib.util.spec_from_file_location('qrc', ROOT / 'training' / 'build-quick-ref-pdfs.py')
qrc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qrc)

E = html.escape
PACE_NAME = {'P': 'Primary: cellular', 'A': 'Alternate: any internet', 'C': 'Contingency: radio', 'E': 'Emergency: runner'}
EXTRA_CSS = """
.sc-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.sc-table th { text-align: left; background: #EEF2F8; color: var(--navy); padding: 5px 8px; font-size: 12.5px; text-transform: uppercase; letter-spacing: .04em; }
.sc-table td { border-top: 1px solid #E2E8F0; padding: 5px 8px; vertical-align: top; line-height: 1.35; }
.sc-note { border-radius: 8px; padding: 9px 12px; font-size: 14.5px; line-height: 1.45; background: #EEF2F8; border-left: 5px solid var(--blue); }
.sc-note.warn { background: #FDF0E6; border-left-color: var(--amber); }
.sc-note.ok { background: #E8F5EE; border-left-color: var(--green); }
.sc-note.stop { background: #FBE9EC; border-left-color: var(--red); }
.sc-list { padding-left: 20px; font-size: 14.5px; line-height: 1.45; }
.sc-table.compact { font-size: 12px; } .sc-table.compact td { padding: 1px 6px; line-height: 1.2; }
.sc-private { font-size: 11px; font-weight: 700; color: var(--red); letter-spacing: .08em; text-transform: uppercase; }
"""


def load(cards_path: Path) -> dict:
    d = json.loads(cards_path.read_text(encoding='utf-8-sig'))
    base = cards_path.parent
    ctx = {'cards': d, 'scenario': None, 'spec': None, 'training': None}
    if d.get('scenario'):
        dirs = [base / p for p in d.get('scenario_dirs', [])]
        ctx['scenario'] = engine.load_scenario(d['scenario'], extra_dirs=dirs)
    if d.get('drill_spec'):
        ctx['spec'] = json.loads((base / d['drill_spec']).read_text(encoding='utf-8-sig'))
    if d.get('training'):
        ctx['training'] = json.loads((base / d['training']).read_text(encoding='utf-8-sig'))
    return ctx


def hm(t0: str, minutes: int) -> str:
    """'T+35' plus the drill clock when the scenario's t0 text starts with a time we can read."""
    m = re.search(r'(\d{1,2}):(\d{2})', t0 or '')
    if not m:
        return f'T+{minutes}'
    tot = int(m.group(1)) * 60 + int(m.group(2)) + minutes
    return f'T+{minutes} ({tot // 60 % 24:02d}:{tot % 60:02d})'


def table(head, rows, compact=False) -> str:
    h = ''.join(f'<th>{c}</th>' for c in head)
    r = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in rows)
    return f'<table class="sc-table{" compact" if compact else ""}"><tr>{h}</tr>{r}</table>'


def auto(kind: str, ctx: dict, mx: int = 0, compact: bool = False) -> str:
    sc, spec, tr = ctx['scenario'], ctx['spec'], ctx['training']
    t0 = (sc or {}).get('clock', {}).get('t0', '')
    if kind == 'pace' and sc:
        rows = [[hm(t0, p['t']), f"<b>{E(p['level'])}</b> {E(PACE_NAME.get(p['level'], ''))}", E(p.get('why', ''))] for p in sc.get('pace', [])]
        return table(['When', 'Level', 'Why'], rows)
    if kind == 'phases' and sc:
        rows = [[f"T+{p['from']} to T+{p['to']}", f"<b>{E(p['title'])}</b>", E(p.get('narrative', '')[:150].rsplit(' ', 1)[0] + ('…' if len(p.get('narrative', '')) > 150 else ''))]
                for p in sc.get('phases', [])]
        return table(['Minutes', 'Phase', 'What happens'], rows[:mx or None])
    if kind == 'done' and sc:
        return '<ul class="sc-list">' + ''.join(f"<li>{E(c['label'])}</li>" for c in sc.get('done', {}).get('checks', [])) + '</ul>'
    if kind == 'roles' and sc:
        return '<ul class="sc-list">' + ''.join(f"<li>{E(r.get('title', r.get('id', '')))}</li>" for r in sc.get('roles', [])[:mx or None]) + '</ul>'
    if kind == 'eocs' and spec:
        rows = [[E(e.get('name') or e.get('stake') or ', '.join(e.get('councils', []))), E({'stake': 'Stake EOC', 'satellite': 'Satellite EOC', 'area': 'Council / Area EOC'}.get(e.get('level'), e.get('level', ''))),
                 E(e.get('manned', '')), E(', '.join(e.get('winlink') or []) or 'set at the drill')] for e in spec.get('eocs', [])]
        rows += [[E(a.get('name', '')), 'Partner agency (ICS forms only)', '', E(a.get('call', ''))] for a in spec.get('agencies', [])]
        return table(['EOC', 'Level', 'People', 'Winlink'], rows[:mx or None], compact)
    if kind in ('messages', 'ics') and tr:
        items = ([dict(x, _k='church') for x in tr.get('church', [])] if kind == 'messages' else []) + [dict(x, _k='ics') for x in tr.get('ics213rr', [])]
        items.sort(key=lambda x: x['time'])
        code = ctx['cards'].get('code', '')
        allitems = sorted([dict(x, _k='church') for x in tr.get('church', [])] + [dict(x, _k='ics') for x in tr.get('ics213rr', [])], key=lambda x: x['time'])
        num = {id(x): n for n, x in enumerate(allitems, 1)}
        stake_eoc = tr.get('stake_eoc') or f"{tr.get('stake', '')} EOC"
        agency = (tr.get('agency') or {}).get('name') or 'City EOC'
        rows = []
        for it in items:
            n = next(num[id(x)] for x in allitems if x['time'] == it['time'] and x.get('unit', x.get('short')) == it.get('unit', it.get('short')))
            if it['_k'] == 'church':
                form = {'dr': 'Disaster Report', 'so': 'Supply Order', 'wcl': 'Work Crew Log'}.get(it['form'], it['form'])
                rows.append([f'{code} {n:02d}', it['time'], E(form + (' ' + it['tag'] if it.get('tag') else '')), E(it['unit'])])
            else:
                fr = ((it.get('agency') or {}).get('name') or agency) if it['dir'] == 'city-to-stake' else stake_eoc
                rows.append([f'{code} {n:02d}', it['time'], 'ICS 213RR', E(f"{fr}: {it['short']}")])
        return table(['No.', 'Time', 'Form', 'From'], rows[:mx or None], compact)
    return f'<p class="sc-note warn">No data for “{E(kind)}” (the cards file names no scenario, drill spec or training source).</p>'


def block(b: dict, ctx: dict) -> str:
    if 'part' in b:
        return f'<p class="card-part">{b["part"]}</p>'
    if 'steps' in b:
        return '<div class="steps">' + ''.join(f'<div class="step"><div class="step-num">{i}</div><div class="step-text">{s}</div></div>'
                                               for i, s in enumerate(b['steps'], 1)) + '</div>'
    if 'note' in b:
        return f'<div class="sc-note {E(b.get("kind", "info"))}">{b["note"]}</div>'
    if 'list' in b:
        return '<ul class="sc-list">' + ''.join(f'<li>{x}</li>' for x in b['list']) + '</ul>'
    if 'table' in b:
        return table(b['table'].get('head', []), b['table'].get('rows', []))
    if 'html' in b:
        return b['html']
    if 'auto' in b:
        return auto(b['auto'], ctx, b.get('max', 0), b.get('compact', False))
    raise ValueError(f'unknown block {b}')


def side(card: dict, which: str, ctx: dict) -> str:
    s = card[which]
    col = card.get('color', 'var(--blue)')
    priv = '<p class="sc-private">Private: for this drill’s participants only. Do not post or forward.</p>' if ctx['cards'].get('private') else ''
    label = f"{E(ctx['cards'].get('code', ''))} card {E(card['no'])} &#8212; {'Front' if which == 'front' else 'Back'}"
    body = ''.join(block(b, ctx) for b in s.get('blocks', []))
    turn = '<p class="turn-over">Turn over &#8594;</p>' if which == 'front' and card.get('back') else ''
    if which == 'back' or not card.get('back'):
        turn += ('<p class="pdf-foot">Church of Jesus Christ EMCOMM &#8212; an independent volunteer project by Travis Hilton (W9TLH), '
                 'not an official publication of the Church</p>')
    return (f'<div class="card card-{which}" style="border-top-color:{col}">\n<div class="card-head"><div>\n'
            f'<p class="card-role">{E(card.get("role", ""))}</p>\n<span class="card-side{" back" if which == "back" else ""}" style="background:{col}">{label}</span>\n'
            f'<h2 class="card-title">{E(s["title"])}</h2>\n</div></div>\n{priv}{body}{turn}\n</div>\n')


def inside_repo_outside_secure(path: Path) -> bool:
    """True for a folder inside the repository that is not under ROOT/secure data/ (git-ignored)."""
    p, repo = Path(path).resolve(), ROOT.resolve()
    sec = (repo / 'secure data').resolve()
    if p != repo and repo not in p.parents:
        return False
    return not (p == sec or sec in p.parents)


def render(cards_path: Path) -> tuple:
    """(cards dict, [(file stem, page HTML)]) for every card and the all-cards page, nothing written."""
    ctx = load(cards_path)
    d = ctx['cards']
    page_src = (ROOT / 'training' / 'quick-ref-cards.html').read_text(encoding='utf-8')
    head = page_src[page_src.index('<head>') + 6: page_src.index('</head>')].replace('</style>', EXTRA_CSS + '</style>')
    rows, pages = [], []
    for card in d['cards']:
        row = '<div class="card-row">\n' + side(card, 'front', ctx) + (side(card, 'back', ctx) if card.get('back') else '') + '</div><!-- row -->'
        rows.append(row)
        pages.append((f"{d['code']}_Card_{card['no']}_{card['file']}",
                      qrc.page(head, row, f"{d['code']} card {card['no']} — {card['file'].replace('_', ' ')}") + '</body>\n</html>\n'))
    pages.append((f"{d['code']}_Cards_All", qrc.page(head, '\n'.join(rows), f"{d['code']} reference cards") + '</body>\n</html>\n'))
    return d, pages


def main(argv, check=None):
    """Build the cards. `check(label, text)` (the participant-package builder's leak check) sees the cards file's
    text and every rendered page BEFORE anything is printed; it raises (SystemExit) to refuse."""
    if not argv or argv[0].startswith('-'):
        print(__doc__)
        return 2
    cards_path = Path(argv[0]).resolve()
    d, pages = render(cards_path)
    out = Path(argv[argv.index('--out') + 1]).resolve() if '--out' in argv else cards_path.parent / 'pdf'
    if d.get('private') and inside_repo_outside_secure(out):
        sys.exit(f'{out}: a private set\'s cards are never written into the repository (use a folder outside it or under secure data/)')
    if check:
        check(cards_path.name, cards_path.read_text(encoding='utf-8-sig'))
        for name, page in pages:
            check(f'{name}.html', page)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for name, page in pages:
        hp, pp = out / f'{name}.html', out / f'{name}.pdf'
        hp.write_text(page, encoding='utf-8')
        if pp.exists():
            pp.unlink()
        qrc.print_pdf(hp, pp)
        results.append((pp.name, qrc.page_count(pp)))
    for n, p in results:
        print(f'{n}: {p} pages')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
