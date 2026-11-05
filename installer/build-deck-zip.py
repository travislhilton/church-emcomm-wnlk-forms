#!/usr/bin/env python3
"""Build dist/ChurchEMCOMM_Deck_v1.0.zip from deck/ (every file, names 'deck/...' with forward slashes).

Run after any change under deck/:   python installer/build-deck-zip.py
Expect 33 entries (index.html, deck.json, 31 slides) unless slides were added or removed.
"""
import pathlib, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'dist' / 'ChurchEMCOMM_Deck_v1.0.zip'


def main():
    files = sorted(p for p in (ROOT / 'deck').rglob('*') if p.is_file())
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT).as_posix())
    tmp.replace(OUT)
    print(f'{OUT.relative_to(ROOT)}: {len(files)} entries, {OUT.stat().st_size} bytes')


if __name__ == '__main__':
    main()
