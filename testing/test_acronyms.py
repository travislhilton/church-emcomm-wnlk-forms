#!/usr/bin/env python3
"""Every acronym spelled out on its first use, in every user-facing document (CLAUDE.md writing rules).

A "document" is what one reader holds or opens: each Quick Reference Card (front + back) on its own, each CCD-1
scenario card on its own, the slide deck as one document in deck/deck.json order, each page, form, Markdown and
text file on its own. For each document the test finds the FIRST use of every acronym in ACRONYMS and fails when
no expansion is found close to it (EXP_BEFORE characters before, EXP_AFTER after, case-insensitive). A definition
further down (a key, a footnote, a glossary) does not count; one before the first use does, because that is then
the first use. It also fails on an upper-case token that is neither in ACRONYMS nor in NOT_ACRONYMS, so a new
acronym cannot slip in unmapped: add it to ACRONYMS with its expansion (look it up, do not guess) and spell it out
where it first appears.

Documents read:
  README.md, CONTRIBUTING.md, simulation/README.md, docs/*.md
  training/quick-ref-cards.html (one document per card), training/scenario-cards/CCD-1/cards.json (one per card)
  installer/dist-readme.txt (the ZIP read-me), training/practice-forms/README.txt, training/scenario-samples/CCD-1/README.txt
  forms/*.html, eoc/*.html (the Message Center, the wall display, the phone page /m), simulation/index.html
  the three Worker forms and the three Winlink Initial templates
  the deck (deck/slides/*.html in deck/deck.json order)

What is read of them:
  HTML pages      visible text only: no <head>, <script>, <style>, <code>, <pre>, comments or attributes (a
                  tooltip or title attribute is not a spelled-out first use). Text built by scripts is not read.
  Markdown        without code blocks, inline code, link targets, bare URLs and bold markers
  CCD-1 cards     role, titles and every text block of the card's front then back (auto blocks are built from
                  the scenario at print time and not read here)
  text files      as they are

Heuristics (kept deliberately small):
  - "VARA FM" and "VARA HF" are product names: their HF / FM is not a use of HF or FM (VARA itself still needs
    spelling out)
  - NAMES (product and system names such as "RMS Express", Winlink's old program and folder name) and the text of
    an external Markdown link (it names a cited source: a newspaper, a report, a tool's site) are not uses of an
    acronym; an expansion inside them still counts
  - PACE counts as spelled out when "Primary ... Alternate" follows or precedes it closely

Not checked (internal, for maintainers only): CONTINUE.md (session handoff), CLAUDE.md (standing rules for
contributors and Claude Code), testing/TEST_CHECKLIST.md (test log); also the generated Viewer templates (they
repeat the Initial) and the generated PDFs and pages (built from quick-ref-cards.html and cards.json, checked here).

    python testing/test_acronyms.py            # exit code 1 on any miss
    python testing/test_acronyms.py --show     # also list every miss with its context
"""
import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHOW = '--show' in sys.argv
EXP_BEFORE, EXP_AFTER = 160, 260

# acronym -> regular expression of its expansion (case-insensitive)
ACRONYMS = {
    'AAR': r'after-action',
    'API': r'application programming interface',
    'APRS': r'Automatic Packet Reporting System',
    'ARDOP': r'Amateur Radio Digital Open Protocol',
    'ARES': r'Amateur Radio Emergency Service',
    'ARRL': r'American Radio Relay League',
    'AUXCOMM': r'auxiliary communications',
    'AWSRM': r'Area Welfare and Self-Reliance Manager',
    'CB': r'Citizens Band',
    'CDN': r'content delivery network',
    'CDOL': r'Church directory|directory',
    'CERT': r'Community Emergency Response Team',
    'CISA': r'Cybersecurity and Infrastructure Security Agency',
    'CLI': r'command-line',
    'CMS': r'Common Message Server',
    'COM': r'serial|communication',
    'CRLF': r'carriage return',
    'CSS': r'Cascading Style Sheets',
    'CSV': r'comma-separated',
    'DANA': r'aislada en niveles altos|upper-level low',
    'DHS': r'Department of Homeland Security',
    'DIRS': r'Disaster Information Reporting System',
    'EMCOMM': r'emergency communications',
    'EMD': r'emergency management',
    'EOC': r'Emergency Operations? Cent',
    'EOP': r'Emergency Operations Plan',
    'EPSG': r'European Petroleum Survey Group',
    'ERD': r'Emergency Response Director',
    'ETA': r'estimated time of arrival',
    'FBI': r'Federal Bureau of Investigation',
    'FCC': r'Federal Communications Commission',
    'FEMA': r'Federal Emergency Management Agency',
    'FM': r'frequency modulation',
    'FRS': r'Family Radio Service|Family / General Mobile Radio Service',
    'GIS': r'geographic information system',
    'GMRS': r'General Mobile Radio Service',
    'GPS': r'Global Positioning System',
    'HAM': r'amateur',
    'HDMI': r'High-Definition Multimedia Interface',
    'HF': r'(?<!very )(?<!ultra )high frequency',
    'HQ': r'headquarters',
    'HTML': r'HyperText Markup Language|web page',
    'HTTP': r'Hypertext Transfer Protocol',
    'IC': r'Incident Command',
    'ICS': r'Incident Command System',
    'IP': r'Internet Protocol',
    'IPAWS': r'Integrated Public Alert and Warning System',
    'ISP': r'internet service provider',
    'JSON': r'JavaScript Object Notation',
    'LAN': r'local (area )?network',
    'LEO': r'low-earth-orbit|low Earth orbit',
    'LF': r'line feed',
    'MURS': r'Multi-Use Radio Service',
    'NC': r'North Carolina',
    'NCEM': r'North Carolina Emergency Management',
    'NCSWIC': r'National Council of Statewide Interoperability Coordinators',
    'NG911': r'Next Generation 911',
    'NIFOG': r'National Interoperability Field Operations Guide',
    'NIMS': r'National Incident Management System',
    'NWS': r'National Weather Service',
    'P2P': r'peer-to-peer',
    'P25': r'Project 25',
    'PACE': r'Primary.{0,220}Alternate',
    'PDF': r'Portable Document Format',
    'PID': r'process ID|process identifier',
    'PSAP': r'public safety answering point',
    'PSPS': r'Public Safety Power Shutoff',
    'PTSD': r'post-traumatic stress disorder',
    'QR': r'Quick Response',
    'RAM': r'random-access memory|memory',
    'RMS': r'Radio Message Server',
    'SHA': r'Secure Hash Algorithm',
    'SHARES': r'SHAred RESources',
    'SITREP': r'situation report',
    'SMS': r'Short Message Service|text messag',
    'TNC': r'terminal node controller',
    'TSV': r'tab-separated',
    'UDP': r'User Datagram Protocol',
    'UHF': r'ultra[ -]high',
    'UPS': r'uninterruptible power supply',
    'URL': r'web address',
    'USGS': r'United States Geological Survey',
    'USB': r'Universal Serial Bus',
    'UTF': r'Unicode',
    'UX': r'user experience',
    'VARA': r'modem',
    'VHF': r'very\W{1,3}(ultra\W{1,3})?high',
    'VIPER': r'Voice Interoperability Plan for Emergency Responders',
    'VM': r'virtual machine',
    'SSH': r'secure shell',
    'WEA': r'Wireless Emergency Alerts',
    'WGS84': r'World Geodetic System',
    'WSRM': r'Welfare and Self-Reliance Manager',
    'WSRS': r'Welfare and Self-Reliance Services',
}
# product and system names: an acronym inside one is not a use of it
NAMES = ['RMS Express', 'MapLibre GL JS', 'ES-Alert']
# upper-case tokens that are not acronyms to spell out: ordinary words written in capitals (banners, status words,
# headings), names (file names, products, form numbers, request and call-sign prefixes), the form and status codes of
# the message tag (DR, SO, WCL, ACK, ASSGN), the simulator's SIM: prefix, everyday words (TV, PC, OK, ID) and units
NOT_ACRONYMS = set('''
FOLDER OFF VERSION QUICK INSTALL AFTER INSTALLING VOLUNTEER OPERATOR LAPTOP GETS INSTALLED DEPENDENCIES TROUBLESHOOTING FILES PACKAGE SUPPORT
A AN AND ARE AT BE BY DO GO IF IN IS IT NO NOT OF ON OR SO TO UP US WE YES THE THIS THAT ALL ANY ONLY NOW NEW
ABOVE ACCOUNTED ACTIVE ALTERNATE AREA AUTO BEFORE BISHOP CARD CELL CENTER CHAIN COMES CONTACTS CONTINGENCY
COORDINATION COUNCIL CREW DATA DECIDES DISASTER DOES DONE DOWN DRILL DROP DURING EACH EMERGENCY END EVERY EXERCISE
EXISTS FIELD FILE FILLS FIVE FLOWS FOR FORM FORMS FOUND FOUR FROM GLANCE GOES HAPPENS HIGH HOP HOW INDEPENDENT
INFORMATION INGEST INJECTS INTERNET ITEMS KNOW LANE LEVEL LINES LOG MESSAGES MISSED MISSIONARY MODE NEEDS
NETWORKED NEXT ONCE ONGOING OPEN OPERATIONS ORDER OUT OVERDUE PATCH PATH PATHS PLAN PRIMARY REACH REAL RECEIVING
REPLY REPORT REPORTS REQUEST RESOURCE RESPONDING RESPONSE ROLE ROLL ROOM RUN SAFE SATELLITE SERVER SETUP SHARE SHIFT
SIMULATED STAKE STANDALONE STARTING STATUS STEP SUPPLY TAB TABS THREE TRAVELS TWO UPDATE USED VOICE WHAT WHEN WHERE
WHO WITH WITHOUT WORDS WORK WORKS WORLD YOU YOUR PRIORITY URGENT ROUTINE IMMEDIATE WARNING
GET POST PUT
CHURCH JESUS CHRIST WINLINK STARLINK QGIS
README CLAUDE CONTRIBUTING CONTINUE FEEDBACK LICENSE TXT ZIP MIT
TV PC OK ID USA N95 AM PM
XS XL XXL XXXL KB MB GB PB
DR SO WCL CCD ACK ASSGN ASSIGNED CONNECTED SIM NN LCE LKS
SATELLITES STAKES REPLIES BACK SENDING IT
'''.split())
NOT_ACRONYM_RX = re.compile(r'^(PD\d+|W\d[A-Z]+|[A-Z]\d{1,2}|T\d*|F\d+|E\d|ICS\d+[A-Z]*)$')
LO, HI = '\x01', '\x02'          # marks a name or a cited source's title: no acronym use inside


def clean(s, kind):
    if kind == 'html':
        s = re.sub(r'(?is)<head\b.*?</head>', ' ', s)
        s = re.sub(r'(?is)<(script|style|code|pre|template)\b.*?</\1>', ' ', s)
        s = re.sub(r'(?s)<!--.*?-->', ' ', s)
        s = re.sub(r'<[^>]+>', ' ', s)
        s = html.unescape(s)
    elif kind == 'md':
        s = re.sub(r'(?s)```.*?```', ' ', s)
        s = re.sub(r'`[^`\n]*`', ' ', s)
        s = re.sub(r'\[([^\]]*)\]\(https?://[^)]*\)', lambda m: LO + m.group(1) + HI, s)    # a cited source
        s = re.sub(r'\]\([^)]*\)', ']', s)
        s = re.sub(r'<[^>\n]+>', ' ', s)
        s = re.sub(r'https?://\S+', ' ', s)
        s = s.replace('**', '').replace('__', '')
    for n in NAMES:
        s = s.replace(n, LO + n + HI)
    return re.sub(r'\s+', ' ', s)


def documents():
    docs = []

    def add(name, text, kind):
        docs.append((name, clean(text, kind)))

    def read(rel):
        return (REPO / rel).read_text(encoding='utf-8-sig')

    md = ['README.md', 'CONTRIBUTING.md', 'simulation/README.md', *sorted(p.relative_to(REPO).as_posix() for p in REPO.glob('docs/*.md'))]
    for rel in md:
        add(rel, read(rel), 'md')
    for rel in ['installer/dist-readme.txt', 'training/practice-forms/README.txt', 'training/scenario-samples/CCD-1/README.txt']:
        add(rel, read(rel), 'txt')
    # Quick Reference Cards: one document per card row (its front and back)
    rows = re.split(r'<div class="card-row">', read('training/quick-ref-cards.html'))[1:]
    for row in rows:
        row = re.split(r'(?i)</main>|<script', row)[0]
        m = re.search(r'Card (\d+) &#183; Front', row)
        add(f'quick-ref card {m.group(1) if m else "?"}', row, 'html')
    # CCD-1 scenario cards: one document per card
    cj = json.loads(read('training/scenario-cards/CCD-1/cards.json'))

    def strings(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, list):
            for x in v:
                yield from strings(x)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k not in ('auto', 'kind', 'max', 'compact'):
                    yield from strings(x)
    for c in cj.get('cards', []):
        parts = [c.get('role', '')]
        for side in ('front', 'back'):
            if c.get(side):
                parts += [c[side].get('title', ''), *strings(c[side].get('blocks', []))]
        add(f"{cj.get('code', '?')} card {c.get('no', '?')} ({c.get('file', '')})", ' \n '.join(parts), 'html')
    # pages and forms
    pages = sorted(p.relative_to(REPO).as_posix() for p in [*REPO.glob('forms/*.html'), *REPO.glob('eoc/*.html')])
    pages.append('simulation/index.html')
    for f in ('disaster-report', 'supply-order', 'work-crew-log'):
        pages += sorted(p.relative_to(REPO).as_posix() for p in (REPO / 'templates' / f).glob('*.html') if not p.name.endswith('_Viewer.html'))
    for rel in pages:
        add(rel, read(rel), 'html')
    # the deck, in order
    order = json.loads(read('deck/deck.json'))['order']
    add('deck (deck.json order)', ' '.join(read(f'deck/slides/{s}.html') for s in order), 'html')
    return docs


def outside_names(text, start):
    """True when position `start` is not inside a NAMES / cited-source span."""
    return text.rfind(LO, 0, start) <= text.rfind(HI, 0, start)


def misses_in(text):
    out = []
    for a, rx in ACRONYMS.items():
        pat = r'(?<![A-Za-z0-9-])' + re.escape(a) + r'(?!(?!s\b)[A-Za-z0-9])'     # EOC or EOCs
        if a in ('HF', 'FM'):
            pat = r'(?<!VARA )(?<!Vara )(?<!VARA FM / )' + pat                     # VARA FM / VARA HF: product names
        m = next((m for m in re.finditer(pat, text) if outside_names(text, m.start())), None)
        if not m:
            continue
        i = m.start()
        if not re.search(rx, text[max(0, i - EXP_BEFORE): i + len(a) + EXP_AFTER], re.I):
            out.append((a, text[max(0, i - 70): i + 80].replace(LO, '').replace(HI, '')))
    return out


def unmapped_in(text):
    found = {}
    for m in re.finditer(r'(?<![A-Za-z0-9_-])[A-Z][A-Z0-9]+(?![A-Z0-9_])(?!(?!s\b)[a-z])', text):
        t = m.group(0)
        if t in ACRONYMS or t in NOT_ACRONYMS or NOT_ACRONYM_RX.match(t) or not outside_names(text, m.start()):
            continue
        found.setdefault(t, text[max(0, m.start() - 50): m.end() + 50].replace(LO, '').replace(HI, ''))
    return found


def check(results, name, ok, detail=''):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f'  ({detail})' if detail and not ok else ''))


def main():
    try:
        sys.stdout.reconfigure(errors='replace')        # --show prints document text on a cp1252 console
    except AttributeError:
        pass
    results = []
    docs = documents()
    check(results, f'{len(docs)} documents read (cards, CCD-1 cards, pages, forms, Markdown, text, deck)', len(docs) >= 40, len(docs))
    total_miss, total_unmapped = 0, 0
    for name, text in docs:
        miss, unm = misses_in(text), unmapped_in(text)
        total_miss += len(miss)
        total_unmapped += len(unm)
        check(results, f'{name}: every acronym spelled out at its first use', not miss and not unm,
              ', '.join([a for a, _ in miss] + [f'{t} (not in ACRONYMS)' for t in unm]))
        if SHOW:
            for a, ctx in miss:
                print(f'        {a:7s} ...{ctx}...')
            for t, ctx in unm.items():
                print(f'        {t:7s} (unmapped) ...{ctx}...')
    ok = all(results)
    print(f'\n{sum(results)}/{len(results)} passed ({total_miss} first uses without expansion, {total_unmapped} unmapped upper-case tokens)'
          + ('' if ok or SHOW else '; run with --show for the context'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
