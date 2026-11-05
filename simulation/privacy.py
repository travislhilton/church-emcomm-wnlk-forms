#!/usr/bin/env python3
"""Privacy modes for organization packs (Python standard library only).

Two modes (docs/SIMULATOR_DESIGN.md section 5):

  real           names, phones and emails as in the pack. Drills in the room, with consent.
  pseudonymized  last names kept, first names invented, phones NXX-555-01XX (the 555-0100 to 555-0199 range is
                 reserved for fiction in every North American area code; the area code varies so that a pack
                 of any size gets a unique number per person), emails first.last@churchemcomm.sim.
                 The default: tabletops, screenshots, bug reports.

Invented first names are realistic and fit the calling: every role that only a man holds in the Church
(bishop, branch president, stake president, their counselors, clerks and executive secretaries, Area Seventy)
gets a man's name; other roles get a name from the full list. Every invented full name, phone number and email
is unique in the pack, and none of them equals a REAL full name, phone number or email anywhere in the pack
(a pseudonym that happened to be another real leader's name would point at a real person).

Pseudonyms are deterministic: derived from a hash of the CDOL person id and a per-pack salt, so the same
person gets the same pseudonym in every run and on every laptop that uses the same pack folder, and a
different pack gets different pseudonyms.

Organization names, buildings and addresses are never changed (they are public on the Church's meetinghouse
locator); organization phones and emails are replaced in pseudonymized mode so nothing in a pseudonymized run
dials or mails a real place.
"""
import copy
import hashlib
import re
import secrets
from pathlib import Path

SIM_DOMAIN = 'churchemcomm.sim'
MODES = ('real', 'pseudonymized')
# Invented phones: <area code>-555-01<nn>. 555-0100 .. 555-0199 is the range the North American Numbering Plan
# reserves for fiction in every area code, so no invented number can ring anyone. 100 numbers per area code; the
# area code (a plain NXX: no N11 service code, no x9x expansion code, never 555 itself) varies to keep every
# number in a pack unique (about 60 000 numbers).
FICTION_EXCHANGE = '555'
AREA_CODES = tuple(a for a in range(201, 990) if a % 100 != 11 and (a // 10) % 10 != 9 and a != 555)

# Invented men's first names (common in the Intermountain West; none is tied to a person in a pack).
MALE_FIRST_NAMES = (
    'Aaron Adam Alan Albert Alex Allen Andrew Anthony Arthur Austin Barry Ben Benjamin Blake Bradley Brady Brandon '
    'Brent Brett Brian Brigham Brock Bruce Bryce Byron Caleb Calvin Cameron Carl Carson Carter Chad Chandler Charles '
    'Chase Chris Christian Christopher Clark Clayton Clint Cody Cole Colton Connor Cory Craig Curtis Dale Dallin Dalton '
    'Dan Daniel Darin Darrell Darren Dave David Dean Dennis Derek Devin Don Donald Doug Douglas Drew Dustin Dwight '
    'Dylan Eli Elijah Eric Ethan Evan Garrett Gary Gavin George Gordon Grant Greg Gregory Hal Harold Hayden Heber Henry '
    'Hunter Isaac Jacob Jake James Jared Jason Jay Jeff Jeffrey Jeremy Jesse Joel John Jonathan Jordan Joseph Joshua '
    'Justin Karl Keith Kelly Ken Kenneth Kent Kevin Kim Kirk Kurt Kyle Lance Landon Larry Lawrence Lee Leon Levi Lincoln '
    'Logan Lorin Lyle Mark Marshall Martin Mason Matt Matthew Max McKay Michael Mitchell Morgan Nathan Neal Nephi Nick '
    'Noah Nolan Owen Parker Patrick Paul Peter Philip Porter Preston Quinn Ralph Randy Ray Reed Rex Richard Rick Riley '
    'Robert Rodney Roger Ron Ross Russell Ryan Sam Samuel Scott Sean Seth Shane Shawn Spencer Stan Stephen Steve Steven '
    'Stuart Taylor Ted Terry Thomas Tim Timothy Todd Tom Tracy Travis Trent Trevor Troy Tyler Vance Wade Walter Ward '
    'Warren Wayne Wesley Will William Wyatt Zach Zachary'
).split()
# Invented first names for every other role (men's names above plus women's names).
FEMALE_FIRST_NAMES = (
    'Abigail Alice Allison Amanda Amy Andrea Angela Anna April Ashley Barbara Becky Beth Brenda Brittany Brooke Camille '
    'Carol Carolyn Catherine Cheryl Christine Cindy Claire Colleen Connie Crystal Cynthia Danielle Darlene Deborah Denise '
    'Diana Diane Donna Elaine Eleanor Elizabeth Ellen Emily Emma Erin Evelyn Faith Gail Gloria Grace Hannah Heather Heidi '
    'Helen Holly Jackie Jan Jane Janet Janice Jean Jennifer Jessica Jill Joan Joanne Joyce Judy Julia Julie June Karen '
    'Kari Katherine Kathleen Kathy Kayla Kelli Kimberly Kristen Kristin Laura Lauren Leah Linda Lisa Lori Lynn Marcia '
    'Margaret Maria Marie Marilyn Martha Mary Megan Melanie Melissa Michelle Monica Nancy Natalie Nicole Norma Olivia '
    'Pamela Patricia Paula Peggy Rachel Rebecca Rhonda Rose Ruth Sally Sandra Sara Sarah Shannon Sharon Sheila Shelly '
    'Sherri Shirley Stacy Stephanie Susan Tamara Tammy Teresa Tiffany Tina Tracy Valerie Vicki Wendy'
).split()
FIRST_NAMES = sorted(set(MALE_FIRST_NAMES + FEMALE_FIRST_NAMES))
# Roles only men hold in the Church: their invented first names come from MALE_FIRST_NAMES.
MALE_ROLE_WORDS = ('bishop', 'bishopric', 'branch president', 'branch presidency', 'stake president', 'stake presidency',
                   'clerk', 'executive secretary', 'seventy', 'patriarch', 'elders quorum')


def new_salt() -> str:
    return secrets.token_hex(16)


def salt_for(pack_dir) -> str:
    """The pack folder's salt, created on first use (``<pack dir>/simulation/salt.txt``)."""
    p = Path(pack_dir) / 'simulation' / 'salt.txt'
    if p.is_file():
        s = p.read_text(encoding='utf-8').strip()
        if s:
            return s
    p.parent.mkdir(parents=True, exist_ok=True)
    s = new_salt()
    p.write_text(s + '\n', encoding='utf-8')
    return s


def _h(*parts) -> int:
    return int.from_bytes(hashlib.sha256('|'.join(str(p) for p in parts).encode('utf-8')).digest()[:8], 'big')


def _ascii_slug(s: str) -> str:
    s = s.encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', '', s) or 'x'


def is_male_role(role: str) -> bool:
    r = (role or '').lower()
    return any(w in r for w in MALE_ROLE_WORDS)


def org_states(pack: dict) -> dict:
    """org id -> 'UT' / 'ID' (the state of a stake's, unit's or council's place; the Area and welfare offices: UT)."""
    st = {}
    for s in pack.get('stakes', []):
        if s.get('state'):
            st[s['id']] = s['state']
    for u in pack.get('units', []):
        if u.get('state'):
            st[u['id']] = u['state']
    for c in pack.get('councils', []):
        ids = [st.get(x) for x in c.get('stakes', [])]
        st[c['id']] = 'ID' if 'idaho' in (c.get('name') or '').lower() else ('UT' if 'utah' in (c.get('name') or '').lower()
                                                                             else max(set(ids), key=ids.count) if ids else 'UT')
    return st


def digits(s) -> str:
    """A phone number reduced to its digits, without a leading country code 1 (for comparisons)."""
    d = re.sub(r'\D', '', str(s or ''))
    return d[1:] if len(d) == 11 and d.startswith('1') else d


def _real_values(pack: dict) -> tuple:
    """(full names, (first, last) pairs, phone digits, emails) of every real person and organization in the pack, lower case."""
    names, pairs, phones, emails = set(), set(), set(), set()
    for c in pack.get('contacts', []):
        first, last = (c.get('first') or '').strip().lower(), (c.get('last') or '').strip().lower()
        if first or last:
            pairs.add((first, last))
            names.add(f'{first} {last}'.strip())
        if (c.get('name') or '').strip():
            names.add(' '.join(c['name'].lower().split()))
        for k in ('mobile', 'phone'):
            if digits(c.get(k)):
                phones.add(digits(c[k]))
        if (c.get('email') or '').strip():
            emails.add(c['email'].strip().lower())
    for o in list(pack.get('stakes', [])) + list(pack.get('units', [])) + list(pack.get('buildings', [])):
        if digits(o.get('phone')):
            phones.add(digits(o['phone']))
        if (o.get('email') or '').strip():
            emails.add(o['email'].strip().lower())
    return names, pairs, phones, emails


def pseudonymize(pack: dict, salt: str) -> dict:
    """A deep copy of the pack with invented first names, phones and emails. No invented value equals a real
    full name, phone or email of the pack (the used sets start with every real one).
    A participant package is already pseudonymized (``pre_pseudonymized``, set by orgpack.load): its names stay
    the ones the package was built with, and only local roles added on this laptop, real people, are replaced."""
    out = copy.deepcopy(pack)
    done = bool(pack.get('pre_pseudonymized'))
    real_names, real_pairs, real_phones, real_emails = _real_values(pack)
    used_names = set(real_pairs)            # (first, last) in lower case
    used_phones = set(real_phones)          # digits
    used_emails = set(real_emails)
    by_person = {}           # person id -> (first, phone, email) so every role of a person matches
    roles_of = {}
    for c in out['contacts']:
        pid = c.get('person') or c['id']
        roles_of.setdefault(pid, []).append(c.get('role', ''))

    def free_name(first: str, last: str) -> bool:
        return (first.lower(), last.lower()) not in used_names and f'{first} {last}'.strip().lower() not in real_names

    def pick_first(person: str, last: str, male: bool, own: str = '') -> str:
        names = MALE_FIRST_NAMES if male else FIRST_NAMES
        base = _h(salt, 'first', person)
        for i in range(len(names)):
            first = names[(base + i) % len(names)]
            if free_name(first, last) and first.lower() != (own or '').lower():   # never the person's own first name, never a real full name
                used_names.add((first.lower(), last.lower()))
                return first
        for i in range(len(names)):               # more people with one last name than names: a middle initial
            first = f'{names[(base + i) % len(names)]} {"ABCDEFGHJKLMNPRSTW"[(base // 7 + i) % 18]}.'
            if free_name(first, last):
                used_names.add((first.lower(), last.lower()))
                return first
        return names[base % len(names)]

    total = len(AREA_CODES) * 100

    def pick_phone(key: str) -> str:
        base = _h(salt, 'phone', key)
        for i in range(total):
            n = (base + i * 7919) % total            # 7919 is prime and does not divide `total`: every number is reachable
            s = f'{AREA_CODES[n // 100]}-{FICTION_EXCHANGE}-01{n % 100:02d}'
            if digits(s) not in used_phones:
                used_phones.add(digits(s))
                return s
        raise ValueError('more phones in the pack than invented numbers')

    def pick_email(first: str, last: str) -> str:
        stem = f'{_ascii_slug(first)}.{_ascii_slug(last)}' if last else _ascii_slug(first)
        cand = f'{stem}@{SIM_DOMAIN}'
        n = 2
        while cand.lower() in used_emails:
            cand = f'{stem}{n}@{SIM_DOMAIN}'
            n += 1
        used_emails.add(cand.lower())
        return cand

    for c in out['contacts']:
        if done and not c.get('local'):
            continue
        pid = c.get('person') or c['id']
        if pid not in by_person:
            male = any(is_male_role(r) for r in roles_of.get(pid, []))
            first = pick_first(pid, c.get('last', ''), male, c.get('first', ''))
            by_person[pid] = (first, pick_phone(pid), pick_email(first, c.get('last', '')))
        first, phone, email = by_person[pid]
        c['first'] = first
        c['name'] = f"{first} {c.get('last', '')}".strip()
        c['mobile'] = phone if c.get('mobile') else ''
        c['phone'] = phone if (c.get('phone') or c.get('mobile')) else ''
        c['email'] = email if c.get('email') else ''
    for s in [] if done else out['stakes']:
        if s.get('phone'):
            s['phone'] = pick_phone('stake:' + s['id'])
        if s.get('email'):
            s['email'] = pick_email(_ascii_slug(s['name']), '')
    for u in [] if done else out['units']:
        if u.get('phone'):
            u['phone'] = pick_phone('unit:' + u['id'])
    for b in [] if done else out['buildings']:
        if b.get('phone'):
            b['phone'] = pick_phone('bldg:' + b['id'])
    out['privacy'] = 'pseudonymized'
    return out


# a North American phone number written any common way: 4355550123, 435-555-0123, (435) 555-0123, +1 435.555.0123
PHONE_RE = r'(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)'


def apply(pack: dict, mode: str, salt: str = '') -> dict:
    if mode not in MODES:
        raise ValueError(f'unknown privacy mode {mode!r}; use one of {MODES}')
    if mode == 'real' and not pack.get('pre_pseudonymized'):   # a package holds no real contacts to show
        p = copy.deepcopy(pack)
        p['privacy'] = 'real'
        return p
    return pseudonymize(pack, salt or new_salt())


def strip_agency_contacts(obj, names: set):
    """Partner agencies ("agencies": list or dict) keep only the contact's title: "Name, Title" -> "Title".
    The names removed go into `names` for the leak check."""
    if isinstance(obj, dict):
        ag = obj.get('agencies')
        for a in (ag.values() if isinstance(ag, dict) else ag or []):
            if isinstance(a, dict) and a.get('contact'):
                who, _, title = a['contact'].partition(',')
                # a person's name ("Jordan Example", "J. R. Example"), not a role ("Duty officer, Fire Department")
                if title and re.fullmatch(r"[A-Z][\w'.\-]*(?: [A-Z][\w'.\-]*)+", who.strip()):
                    names.add(who.strip())
                    a['contact'] = title.strip()
        for v in obj.values():
            strip_agency_contacts(v, names)
    elif isinstance(obj, list):
        for v in obj:
            strip_agency_contacts(v, names)
    return obj

def scrub_names(obj, names, repl: str = 'the agency contact'):
    """Every string in obj with each of `names` (the partner-agency contacts strip_agency_contacts removed)
    replaced by `repl`, so a text that names the person ("call Jordan Example") does not keep the name."""
    names = sorted({n for n in names if n and len(n) > 3}, key=len, reverse=True)
    if not names:
        return obj
    rx = re.compile('|'.join(re.escape(n) for n in names))

    def walk(o):
        if isinstance(o, str):
            return rx.sub(repl, o)
        if isinstance(o, list):
            return [walk(v) for v in o]
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        return o
    return walk(obj)


def leaks(pseudo: dict, real: dict) -> list:
    """Real contact values that still appear anywhere in the pseudonymized pack (should be empty). Phones are
    compared by their digits too, so '(435) 555-0123' and '435-555-0123' are the same number."""
    real_vals = set()
    for c in real['contacts']:
        for k in ('mobile', 'phone', 'email'):
            if c.get(k):
                real_vals.add(c[k].strip().lower())
        if c.get('first'):
            real_vals.add(c['name'].strip().lower())
    for s in real['stakes']:
        for k in ('phone', 'email'):
            if s.get(k):
                real_vals.add(s[k].strip().lower())
    for u in real['units']:
        if u.get('phone'):
            real_vals.add(u['phone'].strip().lower())
    import json
    blob = json.dumps(pseudo, ensure_ascii=False).lower()
    hits = {v for v in real_vals if v and v in blob}
    blob_digits = {digits(m) for m in re.findall(PHONE_RE, blob)}
    hits |= {v for v in real_vals if len(digits(v)) >= 10 and '@' not in v and digits(v) in blob_digits}
    return sorted(hits)
