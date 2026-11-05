"""Build the printable Quick Reference Card PDFs from training/quick-ref-cards.html.

One PDF per card, US Letter, 0.5 in margins, one card side per page, so a
two-sided card prints front/back on one sheet ("flip on long edge") at any
printer or print shop. Also writes the per-card print HTML (open in a browser
and press Print if you cannot use the PDF) and an all-cards PDF.

Needs Google Chrome (headless print-to-PDF). No internet: the cards use system
fonts and the QR codes are drawn by an inline encoder.

    python training/build-quick-ref-pdfs.py
"""
import os, re, shutil, subprocess, sys, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'training' / 'quick-ref-cards.html'
OUT = ROOT / 'training' / 'pdf'


def find_chrome():
    """$CHROME if set, else the usual place on Windows or macOS, else Chrome on the PATH. Empty if there is none."""
    for path in (os.environ.get('CHROME', ''), r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                 r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                 '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'):
        if path and os.path.isfile(path):
            return path
    return shutil.which('google-chrome') or shutil.which('chromium') or ''


CHROME = find_chrome()

# Output name per card row, in the order they appear in quick-ref-cards.html.
CARDS = [
    ('1', 'Helping_Hands_Volunteer'),
    ('2', 'EMCOMM_HAM_Operator'),
    ('3', 'EOC_Operator'),
    ('4', 'Leaders_Overview'),
    ('5', 'Drill_Controller'),
    ('6', 'Satellite_EOC'),
    ('7', 'Stake_Center_EOC'),
    ('8', 'Council_Area_EOC'),
    ('9', 'Your_First_Drill'),
    ('10', 'Team_Leader_Crew_Chief'),
]
# CSS zoom per card side so each side fits one Letter page (measured in Chrome
# at the 720 px printable width; 1 = natural size). Keys: "<card>-<side index>".
ZOOM = {}  # every side fits at 1 (no zoom), so printing the web page gives the same result; 2026-11-03

PRINT_CSS = """
@page { size: letter; margin: 0.5in; }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
html, body { background: #fff; padding: 0; margin: 0; }
.page-header, .section-label, .print-btn { display: none; }
.card-row { display: block; margin: 0; }
.card { max-width: none !important; width: 100%; min-width: 0; flex: none; box-shadow: none;
        border: 1px solid #b8c2cc; border-top-width: 6px; border-radius: 10px;
        break-after: page; page-break-after: always; break-inside: avoid; page-break-inside: avoid; }
.card:last-child { break-after: auto; page-break-after: auto; }
.pdf-foot { font-size: 13.5px; color: #4A5568; margin-top: auto; padding-top: 8px; border-top: 1px solid #e2e8f0; }
.pdf-foot.pdf-url { margin-top: 0; padding-top: 0; border-top: none; }
/* Print sizes: a touch smaller than the screen card so every side fits one Letter page */
.card { padding: 16px 22px; gap: 8px; min-height: 9.8in; }  /* every side fills its page; never spills onto the next */
.card-title { font-size: 22px; }
.step-text { font-size: 15px; line-height: 1.45; }
.step-text small { font-size: 13.5px; }
.note-box { font-size: 15px; line-height: 1.45; }
.checklist li { font-size: 15px; }
.tier-table { font-size: 14.5px; }
.tier-table td { padding: 6px 10px; }
.phrase-box { font-size: 15px; }
.bishop-node { font-size: 14.5px; padding: 8px 10px; }
.steps { gap: 5px; }
.step-text { line-height: 1.38; }
"""


def split_cards(html):
    head = html[html.index('<head>') + 6: html.index('</head>')]
    body = html[html.index('<body>') + 6: html.index('</body>')]
    script = body[body.index('<script>'):]
    rows = []
    pos = 0
    while True:
        s = body.find('<div class="card-row">', pos)
        if s < 0:
            break
        ends = [i for i in (body.find('<p class="section-label"', s), body.find('<script>', s)) if i > 0]
        e = min(ends)
        chunk = body[s:e].rstrip()
        # drop the "<!-- ═══ ... -->" separator comments that precede the next section label
        chunk = re.sub(r'(\s*<!--[^>]*-->\s*)+$', '', chunk)
        rows.append(chunk)
        pos = e
    return head, rows, script


def with_zoom(row_html, card_no):
    """Inline a CSS zoom on each card side of a row (front = 0, back = 1)."""
    out, idx, pos = [], 0, 0
    while True:
        s = row_html.find('<div class="card ', pos)
        if s < 0:
            out.append(row_html[pos:]); break
        z = ZOOM.get(f'{card_no}-{idx}', 1)
        out.append(row_html[pos:s])
        out.append(f'<div style="zoom:{z}" class="card ')
        pos = s + len('<div class="card ')
        idx += 1
    return ''.join(out)


def page(head, rows_html, title):
    # the disclaimer is on every card back already (class card-disclaimer); the print copy adds where to find the project
    foot = '<p class="pdf-foot pdf-url">travislhilton.github.io/church-emcomm-wnlk-forms/forms/</p>'   # the public portal
    rows_html = rows_html.replace('</div>\n</div>', foot + '</div>\n</div>')  # harmless if no match
    head = head.replace('</style>', PRINT_CSS + '</style>')
    head = re.sub(r'<title>.*?</title>', f'<title>{title}</title>', head, flags=re.S)
    return f'<!doctype html>\n<html lang="en">\n<head>{head}</head>\n<body>\n{rows_html}\n'


def print_pdf(html_path, pdf_path):
    if not CHROME:
        raise SystemExit('Google Chrome was not found: install it, or set CHROME to its full path')
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--no-pdf-header-footer', '--virtual-time-budget=12000',
           f'--print-to-pdf={pdf_path}', html_path.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not pdf_path.exists():
        print(r.stdout[-800:], r.stderr[-800:])
        raise SystemExit(f'Chrome did not write {pdf_path}')


def page_count(pdf_path):
    data = pdf_path.read_bytes()
    # the page tree can be nested: the root's /Count is the largest
    counts = [int(c) for c in re.findall(rb'/Type\s*/Pages[^>]*?/Count\s+(\d+)', data)]
    return max(counts) if counts else -1


def main():
    html = SRC.read_text(encoding='utf-8')
    head, rows, script = split_cards(html)
    assert len(rows) == len(CARDS), f'expected {len(CARDS)} card rows, found {len(rows)}'
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    all_rows = []
    for (no, name), row in zip(CARDS, rows):
        body = with_zoom(row, no)
        all_rows.append(body)
        title = f'Quick Reference Card {no} — {name.replace("_", " ")}'
        html_path = OUT / f'Quick_Reference_Card_{no}_{name}.html'
        pdf_path = OUT / f'Quick_Reference_Card_{no}_{name}.pdf'
        html_path.write_text(page(head, body, title) + script + '</body>\n</html>\n', encoding='utf-8')
        if pdf_path.exists():
            pdf_path.unlink()
        print_pdf(html_path, pdf_path)
        results.append((pdf_path.name, pdf_path.stat().st_size, page_count(pdf_path)))
    all_html = OUT / 'Quick_Reference_Cards_All.html'
    all_pdf = OUT / 'Quick_Reference_Cards_All.pdf'
    all_html.write_text(page(head, '\n'.join(all_rows), 'Quick Reference Cards — all roles') + script + '</body>\n</html>\n', encoding='utf-8')
    if all_pdf.exists():
        all_pdf.unlink()
    print_pdf(all_html, all_pdf)
    results.append((all_pdf.name, all_pdf.stat().st_size, page_count(all_pdf)))
    for name, size, pages in results:
        print(f'{name}: {size} bytes, {pages} pages')


if __name__ == '__main__':
    main()
