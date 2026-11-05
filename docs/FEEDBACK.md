# Feedback, bugs and drill reports — how to send them and what happens next

*An independent volunteer project, not an official product of The Church of Jesus Christ of Latter-day Saints.*

Every drill, net and real activation turns up something: a label that confused a volunteer, a Winlink step that took three tries, a number on the EOC (Emergency Operations Center) screen that did not add up. The system only improves when those get written down **while they are fresh**. This page is the one place that explains how.

**Volunteers: tell your Team Leader or the stake specialist** (section 2). The GitHub links below need a free GitHub account.

## 1. GitHub issues

Open **[New issue](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new/choose)** and pick a form:

| Form | Use it for |
|---|---|
| **Bug report** | Something did the wrong thing: a form, a Winlink template, the EOC Message Center, the server, the installer, a card or a document |
| **Drill / practice feedback** | What worked, what was confusing, one thing to change — one per person or team right after the exercise |
| **Idea / improvement** | Something the system should do or do differently |

Each form asks for the few things that make a report actionable: your role, which part, what you did and saw, the device and software, the date and the drill name. A free-text "blank issue" is also allowed.

**Most of that is filled in for you.** GitHub lets a link prefill any box on an issue form, so every "report a problem" link in the system carries what it already knows:

| Where you click | What arrives already filled in |
|---|---|
| A Worker form (Disaster Report, Supply Order, Work Crew Log), bottom of the page | Role, *which part* = phone form, the form's name in the title, your phone or browser and screen size, whether it is the installed copy or the portal, date and time, software build |
| The [volunteer portal](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/) footer | Same as above for the portal |
| EOC Message Center → Setup tab → **Report a bug** | Role, *which part* = EOC Message Center, browser, networked or standalone, date and the active event, software build (page and server), and the whole **diagnostic block** (EOC level and name, event, PACE (Primary, Alternate, Contingency, Emergency) level, record counts, watcher states) |
| EOC Message Center → **Drill feedback** | Drill name and date (from the active event), role, the PACE level in force |
| EOC Message Center → **Suggest an idea** | Who it helps |
| README role sections and the links below | Role and part |

You only add what happened. Nothing is sent until you press *Submit new issue*, and you can edit any prefilled box first.

Direct links by role (role and part already chosen):

- Volunteer: [bug](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&role=Helping%20Hands%20Volunteer%20(phone%20form)&part=Phone%20%2F%20browser%20Worker%20Form%20(Disaster%20Report%2C%20Supply%20Order%2C%20Work%20Crew%20Log)) · [drill feedback](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=Helping%20Hands%20Volunteer%20(phone%20form))
- Team Leader / Emergency Response Director (ERD): [bug](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&role=Team%20Leader%20%2F%20Emergency%20Response%20Director) · [drill feedback](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=Team%20Leader%20%2F%20Emergency%20Response%20Director)
- HAM (amateur radio) operator: [bug](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&role=EMCOMM%20HAM%20Operator%20(Winlink)&part=Winlink%20Express%20template%20(Initial%20form%2C%20Load%20Data%2C%20Viewer%2C%20message%20text)) · [drill feedback](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=EMCOMM%20HAM%20Operator%20(Winlink))
- EOC operator: [bug](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&role=EOC%20Operator%20%E2%80%94%20Satellite%2C%20Stake%20or%20Area%20EOC&part=EOC%20Message%20Center%20(tabs%2C%20Open%20form%2C%20SITREP%2C%20roll-up%2C%20events)) · [drill feedback](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=EOC%20Operator%20%E2%80%94%20Satellite%2C%20Stake%20or%20Area%20EOC) — better: use the Setup tab buttons, which add the diagnostics
- Stake President / Bishop / observer: [drill feedback](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=Stake%20President%20%2F%20Bishop%20%2F%20observer)
- Installer problems (any role): [bug](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&part=Installer%20(BAT%20or%20ZIP)%20%2F%20desktop%20shortcuts)
- Cards, README, deck, PACE plan: [bug](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&part=Quick%20Reference%20Cards%20%2F%20README%20%2F%20deck%20%2F%20PACE%20plan)
- Anyone: [idea](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=feature_request.yml)

Checkboxes (the *Impact* line) cannot be prefilled by a link; tick that one yourself.

**No GitHub account?** Creating one takes two minutes and needs only an email address. GitHub is where the work is tracked, so a report there is never lost.

## 2. No-account path — tell the specialist, who files it

Volunteers who will not create an account tell their **Team Leader or the stake Welfare and Self-Reliance Specialist (emergency communications)**, in person, by text or by email, and the specialist files the issue. To make that useful, give them the same facts the form asks for:

- your role and which part (phone form, Winlink, EOC screen, installer, card)
- what you did, what you expected, what you saw — the exact wording of any error
- device and software (iPhone 15 Safari, Windows 11 Chrome, Winlink Express version)
- date, time, and the drill or event name

The portal footer carries this address. Volunteers do not need it: the Volunteer Quick Reference Card tells them to tell their Team Leader or the stake specialist.

## 3. EOC operators — paste the diagnostic block

On the EOC Message Center **Setup** tab, the *Help & feedback* card has **Report a bug**, **Drill feedback** and **Suggest an idea** buttons that open the issue form with everything above filled in, including the diagnostic block (software build, networked or standalone, browser, EOC level and name, active event and PACE level, counts of reports / roster / notes, watcher states, time). **Copy diagnostic info** copies the same block for an email to the specialist, or for pasting into an issue opened some other way.

## 4. During a drill — run a hot wash

The cheapest feedback is collected in the last ten minutes of the exercise, before anyone leaves:

**Before anything leaves the room:** pseudonymized runs still show real unit and building names. Before filing an issue or screenshot, use the invented Juniper Plains Area or the Hot wash tab's "Report as text, units redacted".

The simulator helps: its **Hot wash** tab holds the scenario's checklist, its after-action report (`/report`) lists the do-better items by role, and its **debrief for the room** (`/debrief`) shows the run on the projector, what went well first.

1. The drill lead asks every role, in turn: *what worked, what was confusing, what would you change*. One sentence each; someone types as they talk.
2. The typist files **one Drill feedback issue per role** (or per person for anything specific) the same evening, with the drill name and PACE level in the title.
3. Timings go in too: minutes from "form filled" to "seen at the EOC" at each PACE level exercised. Those numbers are how we know the next drill went better.
4. Anything that blocked a report from getting through is filed as a **Bug** with *It blocked the report* ticked. Those are fixed before the next drill.

## 5. What happens to a report

- New issues get the **needs-triage** label automatically. Within a few days they are confirmed, labelled by part (`forms`, `winlink`, `eoc`, `installer`, `docs`) and given a priority (`blocks-report` first, then `drill-fix`, then everything else).
- Fixes land on `main`, the installer and ZIP on the release page are rebuilt, and the issue is closed with a note saying which build has the fix. **Re-run the installer** to pick it up; your EOC data and backups are kept.
- Wording and card changes follow the same path and show up in the next PDF (Portable Document Format) build.
- Ideas that would add a fourth form are discussed but declined: the three forms mirror the Church's published PDFs on purpose.

## 6. Labels

| Label | Meaning |
|---|---|
| `bug` | Wrong behaviour |
| `drill-feedback` | From a net, tabletop or full drill |
| `enhancement` | Idea / improvement |
| `needs-triage` | Not yet reviewed |
| `blocks-report` | A report could not get through — fix first |
| `drill-fix` | Fix before the next scheduled drill |
| `forms` · `winlink` · `eoc` · `installer` · `docs` | Which part |
