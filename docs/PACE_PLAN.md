# Communications PACE Plan — Church of Jesus Christ EMCOMM (Emergency Communications)

**PACE** = **P**rimary · **A**lternate · **C**ontingency · **E**mergency. It is the standard way emergency managers and the military plan communications: pick four ways to move a message, each one independent of the last, and know in advance exactly when to step down to the next one. The guidance from CISA (the Cybersecurity and Infrastructure Security Agency) and NCSWIC (the National Council of Statewide Interoperability Coordinators) for public-safety agencies sums up the two rules that matter:

> A PACE plan moves from level to level based on failures of the current communication mode.
> The same communications path or method should never be used more than once.

This document applies that framework to the Church of Jesus Christ EMCOMM system. The level definitions are **aligned with the county ARES (Amateur Radio Emergency Service) Communication PACE Plan** where the stake sits, so that "we are at Contingency" means the same thing to a stake HAM (amateur radio operator) and to the county Emergency Operations Center (EOC). The plan covers the whole chain: field → Satellite EOC → Stake EOC → the council line (Area Seventy) and the welfare line (the Welfare and Self-Reliance Manager, WSRM, then the Area Welfare and Self-Reliance Manager, AWSRM). The deck, README and quick-reference cards carry the short version. **Fill in the stake-specific sheet (§6) before any activation.**

This plan, and the digital forms system it belongs to, were created by **Travis Hilton (W9TLH)** as a contribution to the EMCOMM community. It is an independent volunteer project, not an official publication of The Church of Jesus Christ of Latter-day Saints; the Church guidelines it quotes are the authority, this plan is one way to carry them out.

---

## 1. Why PACE, and why it fits the Church structure

- The Church's *Emergency Communication Guidelines* tell stake presidents they "may call a Welfare and Self-Reliance Specialist to manage emergency communications" who "recommends backup mode(s) of communication that will work most effectively." That specialist works "under the direction of priesthood leaders" and never replaces them: the specialist **recommends**, the stake president **decides**. PACE is simply a disciplined way to write down those backup modes and the order they are used.
- The same guidelines set the chain this plan sits in. A **stake Welfare and Self-Reliance Specialist** (the Church's title for the emergency communications specialist) "is called by and reports to the Stake Presidency." **Area Welfare and Self-Reliance Specialists** "are called by and report to the Area Seventy (under the direction of the Area Presidency) and coordinate closely with the Area Welfare and Self-Reliance Managers (AWSRM's)" and "communicate as needed with both the coordinating council and the AWSRM"; the **local Welfare and Self-Reliance Manager (WSRM)** is kept informed and coordinated with. The Church Headquarters Emergency Response team supports the AWSRMs. The guidelines also encourage local specialists "to identify individuals with communications equipment and technical capabilities who can support local leaders" — the stake HAMs this plan organizes — and say "Amateur radio should be seen as one of several options."
- The same guidelines rate amateur radio as "very resilient, even in the worst circumstances" and note that "80 percent of the communications infrastructure is often working again within 72 hours." That is the whole case for PACE: the first three days are when the Primary path is most likely to be gone, and when the Stake President most needs reports from the field.
- Washington State EMD's (Emergency Management Division) PACE plan puts Winlink email at its Alternate, Contingency **and** Emergency data levels, routed through SHARES (SHAred RESources, the federal HF (high frequency) radio program) RMS (Radio Message Server) stations, with SITREPs (situation reports), ICS-213RR resource requests and other ICS (Incident Command System) forms as the traffic. Our three Church forms are the same kind of structured traffic, and our Winlink templates play the same role.
- **A county ARES plan** (the one this plan was first aligned with) runs a PACE matrix with one ladder per function. Its *Email* ladder is Facility ISP (internet service provider) → Starlink Wi-Fi → Amateur Radio (Winlink) → Runner, and its *Phone* ladder is Cellular → Wi-Fi from local ISP → Starlink Wi-Fi. Both radio ladders go repeater → simplex. Amateur radio is the county's **Emergency** level for public-safety voice, which means ARES operators are tasked by the county once it reaches that level. Our plan adopts the county's level boundaries (internet = Alternate, radio = Contingency, runner = Emergency) and plans around the county's claim on ARES operators.
- Stakes that already run a tiered plan (for example the Grand Junction stake handbook: phones first, then "any method adequate" including FRS (Family Radio Service), CB (Citizens Band), MURS (Multi-Use Radio Service), GMRS (General Mobile Radio Service) and amateur radio on a published simplex frequency; wards on assigned FRS channels reporting to the stake on MURS or GMRS) are running PACE without the name.

## 2. The plan — three ladders, one set of levels

Like the county plan, this plan keeps **one ladder per function**. A stake response has two hops and three functions:

- **Field → Stake EOC, digital forms and messages** (§2a) — getting a completed Disaster Report, Supply Order or Work Crew Log (or any written message) from a volunteer's phone to the Stake EOC Message Center.
- **Field → Stake EOC, voice** (§2b) — tactical coordination: "we have an injury," "crew 3 is moving to the next street," "is the EOC receiving?" Voice carries what cannot wait for a form, and it is how a Team Leader with no HAM in reach still gets a report in.
- **Stake EOC → the lines above the stake** (§2c) — the SITREP going up to **both** the coordinating council (the Area Seventy) and the welfare line (the local Welfare and Self-Reliance Manager, WSRM, then the **AWSRM**, Area Welfare and Self-Reliance Manager); the Disaster Reports and Supply Orders going up the welfare line; approvals and situation updates coming back down. There is no standing Area EOC: a **Council / Area EOC** exists only when the council or the welfare region opens one.

All three ladders use the **same four level names and the same network at each level**, so the specialist recommends one level, the Stake President decides it (§3), and everyone knows what to do on every ladder. Each level uses a different network from the one above it, so no single failure takes out two levels. The two hops can be at different levels at the same time: a stake with no local internet (field hop at C) can still reach a welfare line that has internet, because Winlink's central servers store the message until it is picked up.

### 2a. Digital forms and messages

| Level | Network | How the form travels | Who moves it |
|---|---|---|---|
| **P — Primary** | Cellular | Volunteer fills the Worker Form on their phone, taps **Share / Send**, and texts or emails the `.txt` file straight to the Team Leader, Emergency Response Director (ERD), or the EOC. The EOC operator saves it to the **EOC Drop Folder**; it is ingested within 10 seconds. | Volunteer |
| **A — Alternate** | Any surviving internet, anywhere | Cell is down but internet is not. The volunteer joins **any Wi-Fi that still has internet — at home, a shelter, a business, a neighbor's house, a meetinghouse, or a Starlink dish** — and sends the same file by email or iMessage / Wi-Fi messaging. Volunteers are not limited to Church buildings or stake equipment: any working internet connection, wherever they are, is the Alternate path. Files that reach a HAM by AirDrop, Nearby Share or USB (Universal Serial Bus, thumb) drive go into the Winlink template (**Load Data**) and out by **Telnet** over whatever internet the HAM can reach, wired or Starlink. EOC ingests from the Drop Folder or from Winlink. | Volunteer, Team Leader, HAM |
| **C — Contingency** | Radio | No internet anywhere. The file reaches the HAM by Nearby Share (Android), AirDrop (iPhone to a Mac or another iPhone only) or a USB (Universal Serial Bus) thumb drive (see *From an iPhone to a Windows laptop* below). The HAM submits the Winlink template over **VHF/UHF (very high / ultra high frequency) radio using the VARA FM software modem** to the nearest **RMS Gateway**. If that gateway has lost its internet it may hold the message for the CMS (Common Message Servers, Winlink's central mail store). If not, the HAM uses the local **VARA FM RMS Post Office**, then **VARA FM P2P (peer-to-peer)** straight to a nearby EOC's Winlink station on the stake's P2P frequency (§6a). If none of these work, **HF (high frequency) radio with VARA HF, 40 m / 80 m** reaches a gateway anywhere in the country. The steps are in §5. A full report is under 2 KB. Reports that arrive by voice (ladder 2b) are typed straight into the template or the Message Center. | Team Leader, HAM |
| **E — Emergency** | Feet | No working radio path either. The report goes **on paper**: the volunteer taps **Print** under the filled form (any printer on the same Wi-Fi, or the printer's own Wi-Fi Direct network; iPhone AirPrint, Android print service), or fills a **blank paper form** from the go-bag, and a runner carries it to the Team Leader or the EOC. Before an event every volunteer prints 3 blank copies of each form (portal → *Paper forms*). The digital report stays in the Outbox. The EOC operator types it in. Files saved on phones are sent the moment any higher path returns. | Everyone |

### 2b. Voice

| Level | Network | How voice traffic moves | Who |
|---|---|---|---|
| **P — Primary** | Cellular | Cell phone call or text between volunteer, Team Leader, ERD and EOC. | Everyone |
| **A — Alternate** | Any surviving internet, anywhere; landline | Wi-Fi calling, FaceTime, WhatsApp or similar over any Wi-Fi with internet — home, shelter, business, meetinghouse, Starlink. **Landline** telephones (the meetinghouse phone, a home phone) where the wiring survived — the Church guidelines list the landline as a mode "tied to a physical address" that often works when cell service does not; the Stake Center and meetinghouse numbers go on the sheet (§6a). | Everyone |
| **C — Contingency** | Radio | **Ward level:** volunteers and crews on the ward's assigned **FRS/GMRS** channel to the Team Leader. **Stake level:** Team Leaders and HAMs on the **stake VHF/UHF amateur net** — repeater first, published simplex frequency when the repeater is down. The EOC operator takes the report and types the fields into the Winlink template or the Message Center. GMRS repeater use requires a GMRS license; FRS needs none. | Volunteer (FRS/GMRS), Team Leader, HAM (amateur) |
| **E — Emergency** | Feet | Runner, face to face. | Everyone |

### 2c. Stake EOC → the two lines above the stake (council line and welfare line)

What goes up: the **SITREP** (the first assessment as soon as possible, then on the interval EOC leadership sets for the event — 2, 4, 8, 12 or 24 hours on the Message Center's Setup tab, on the schedule the Area Seventy or the AWSRM asks for; the Church guidelines say only "regular status reports"), every **Disaster Report** and **Supply Order** as it is logged, and the handoff JSON (JavaScript Object Notation data file) if the EOC relocates. What comes down: Supply Order approvals, situation updates, and deployment authorizations.

The Church's structure gives a stake two lines above it, not one EOC: the **council line** (the coordinating council is the Area Seventy and his stakes; no building, phone or Winlink address of its own; the Area Seventy is reached by email) and the **welfare line** (the local WSRM, reporting to the AWSRM in the Area office). The **Area Welfare and Self-Reliance Specialist** works both. So: the **SITREP goes to both lines**; **Disaster Reports and Supply Orders go to the welfare line**, which has a Winlink address; approvals come back down the welfare line. A **Council / Area EOC** exists only when the council or the welfare region opens one (the Area Specialist's station); then it is the EOC the stakes report to and roll up to. The people on both lines may be at an office, at home, or travelling; the plan assumes they can be anywhere with any connection.

| Level | Network | How the Stake EOC reaches the council line and the welfare line |
|---|---|---|
| **P — Primary** | Cellular / internet | SITREP generated in the Message Center and sent by **email** to both lines; Supply Orders and Disaster Reports forwarded by **Winlink Telnet** to the welfare line's Winlink address so they arrive as structured messages. Phone call for anything urgent. |
| **A — Alternate** | Any surviving internet, anywhere | Same, over **whatever internet the Stake EOC can reach** — facility ISP, Starlink, a nearby business, an operator's home — and whatever the two lines can reach at their end; Wi-Fi calling for voice. Nothing else changes. |
| **C — Contingency** | Radio | **Data:** the EOC HAM sends the SITREP and forms over **VHF/UHF with VARA FM** to the local RMS Gateway, which may hold it if its internet is down. Otherwise by the local **VARA FM RMS Post Office**, then **VARA FM P2P** to a nearby EOC, then **VARA HF** to a gateway anywhere in the country (the steps are in §5). Through a gateway the message lands in the **Winlink CMS**, and the welfare line (or the Council / Area EOC) picks it up by whatever connection *they* have — Telnet if they still have internet, radio if not. No timing sync is needed; Winlink stores it. They reply the same way. The council line usually has email only: it gets the SITREP as soon as any internet returns, or the Area Specialist relays it. **Voice:** **VHF/UHF** to the Council / Area EOC HAM station when one is open, on the area's repeater system where it reaches. **Only if that fails, HF** on the published frequency, or relay through the **county EOC amateur station** (HF / SHARES-capable) with the stake liaison. What reaches differs by area, so each stake records its own path on the stake PACE sheet (§6). |
| **E — Emergency** | Satellite phone, someone else's path, or feet | No stake radio path works. A **satellite phone**, if the stake or the Area has one (the Church guidelines list it as a mode that "works when cell phones are down"; Church communication equipment is positioned at headquarters, some welfare facilities and area offices — record on the sheet whether one is reachable), calls the welfare line directly. Otherwise the **stake liaison at the county EOC** passes the SITREP by county Starlink or satellite phone (the county's Command Trailer and EOC both carry them); or a courier carries the printed SITREP and handoff USB to the Council / Area EOC if one is open, else to the nearest stake center that is up. Queued Winlink messages go out automatically the moment any path returns. |

**Why the levels are independent:** P rides the cellular carriers. A rides a different network — wired ISP or Starlink — through Wi-Fi, and the Winlink CMS is reached over that same internet. C uses no internet at all: amateur VHF/UHF (VARA FM) and HF (VARA HF) into the Winlink RMS network for data, amateur and FRS/GMRS frequencies for voice. E uses no electronics. A disaster that takes out one level does not automatically take out the next.

**What never changes:** the three forms, the Winlink templates and the EOC Message Center are identical at every level. Only the transport changes. Load Data, auto-ingest, the `[Church-XX|…]` tags and the SITREP generator all work the same whether the message arrived by email, VARA FM, HF, or was typed in from a voice report.

**Voice at Contingency, not Emergency.** FRS/GMRS and VHF/UHF amateur voice sit at C deliberately. They are working radio paths that run alongside Winlink over VARA FM, not a last resort. (The county's own plan puts amateur radio at *Emergency* for public-safety voice because the county has P25 (Project 25 public-safety digital radio) and NIFOG (National Interoperability Field Operations Guide) channels above it; the stake has no such layers, so radio is our third level, not our fourth.) Emergency is reserved for the case where no radio works at all.

### 2d. More than one EOC — Satellite EOCs, the Stake Center EOC and a Council / Area EOC

The Message Center is the same software at every level; what differs is who it reports to. A stake can run it in three places at once:

| EOC | Where | Covers | Reports to |
|---|---|---|---|
| **Satellite EOC** (optional, one or more) | A ward meetinghouse other than the Stake Center — chosen because it is closer to the damage, on the far side of a closed road or river, or has power and internet when the Stake Center does not | The wards (or the part of the community) the Stake President assigns to it on the stake sheet (§6d) | Stake Center EOC |
| **Stake Center EOC** | The Stake Center | Every ward not assigned to a Satellite EOC, plus everything the Satellite EOCs roll up | The two lines above the stake (§2c): SITREP to the council line and the welfare line, forms to the welfare line; a Council / Area EOC when one is open |
| **Council / Area EOC** (only when opened) | The Area Welfare and Self-Reliance Specialist's station, opened by the coordinating council or the welfare region. The Church positions its own communication equipment "at Church headquarters, some welfare facilities, and area offices," so an area office, a welfare facility or a stake center is the likely anchor; record the actual location on the sheet | Every stake in the Council | Area Presidency / Church headquarters as directed |

Each EOC runs its own server and database, has its own **drop email address** (for the EOC Drop Folder), its own **Winlink address**, its own net and FRS/GMRS assignments, and sets its **level** (Satellite / Stake / Council-Area), **name**, **units covered**, the **EOC it reports to** and, at a Stake EOC, the **council line and welfare line** addresses on the Setup tab. The level changes the roster vocabulary — a Satellite or Stake EOC tracks **wards** and bishops, a Council / Area EOC tracks **stakes** and stake presidents — and puts the EOC's name in the header, the SITREP and the server console. The Disaster Report has an optional **Ward** field for this: leave it blank for a stake-wide report, fill it when a ward reports through a Satellite or Stake EOC.

**Every report has one home EOC.** Volunteers and HAMs do exactly what they do today; the only thing that changes is *which* EOC address or net they are given. The Team Leader card for a ward assigned to a Satellite EOC carries that EOC's drop email, Winlink address and net, not the Stake Center's. A report that lands at the wrong EOC is not re-keyed; it is rolled up like any other.

**Roll-up** is how a lower EOC feeds the one above it, on the same ladder as §2c:

| Level | How the roll-up travels |
|---|---|
| **P / A** | Setup tab → **Export Roll-up JSON** (keep "only new since last roll-up" ticked) → attach the `.json` to an email to the parent EOC's drop email. The parent's Drop Folder watcher merges it automatically, zero-touch, within 10 s. |
| **C** | The same file attached to a **Winlink** message to the parent's Winlink address (the Contingency steps in §5, in order). The parent's Winlink watcher finds the `.json` attachment and merges it. About 1 KB per record — a 30-record roll-up is still a short message on HF. Alternatively **Forward** the original Church form messages in Winlink; the parent ingests them as if they had arrived directly. |
| **E** | The `.json` on a USB drive with the printed SITREP, by runner or courier. The parent drops it in its Drop Folder or clicks **Import Roll-up JSON (merge)**. |

The SITREP itself still goes up as text at every level (§2c); the roll-up carries the structured records behind it. Send the roll-up with every SITREP (on the event's SITREP interval) or whenever the parent asks.

**Nothing is counted twice.** A merge skips any record whose id, Winlink Message-ID or form content is already on file — so the same Disaster Report can arrive by Winlink forward *and* in a roll-up, or in two successive roll-ups, and appears once. Merge never replaces: the parent's own status and notes on a record are kept. Roster entries merge by name; notes arrive prefixed with the sending EOC's name. The SITREP gains a **Section H: Reporting EOCs** listing each lower EOC, how many roll-ups it sent and when the last one arrived, so the Area can see which stakes — and the stake which satellites — have gone quiet. The Messages tab shows a **Via** column with the EOC each record came through. **Import Handoff JSON** is a different thing: it *replaces* everything and is for shift change only.

**When to open a Satellite EOC:** the specialist recommends it and the Stake President decides, when a group of wards cannot reach the Stake Center in reasonable time — roads cut, the river between, the Stake Center itself damaged or dark — or when the volume from one part of the stake would swamp one operator team. Name it, assign the wards, publish its addresses on the stake sheet (§6d), and open it with the same installer choice [3]. Close it by sending a final roll-up and noting "Satellite EOC closed" in the SITREP; the Stake Center keeps every record.

## 3. Triggers — when to step down, when to step back up

The **stake Welfare and Self-Reliance Specialist (emergency communications) recommends** the level, the **stake president decides** it (for a single-ward net, the bishop), and the **ERD or the specialist announces** the level in force on the net. This follows the Church guidelines: the specialist "recommends backup mode(s) of communication that will work most effectively" and works "under the direction of priesthood leaders," never replacing them. Operators do not drift between levels on their own.

**Step down one level when any of these is true:**
1. Two attempts on the current path fail within 15 minutes (text/email not delivered, Wi-Fi gives no internet, Winlink session fails to connect, no gateway answers, no one answers the net).
2. The current path is so congested that a single form takes longer than 30 minutes to reach the EOC.
3. The stake president decides it on the specialist's recommendation (for example, a known tower or fiber cut, a county EOC announcement, or the county tasking our ARES operators).

**Step back up only when:** a test message has gone round-trip on the higher path and been confirmed by the EOC. Until then, stay at the lower level even if the higher one "seems" to be back. Congestion in the first hours after a disaster comes and goes.

**One sheet for the numbers:** the contacts, EOC Winlink addresses and drop emails, the RMS gateways in order and the net frequencies in §6 are kept in the EOC Message Center's **Comms Sheet** (Setup tab), which is shown on every operator's Comms tab and the wall display, printed for go-bags, pasted as text into Winlink or email, and sent as a small JSON file that every other EOC takes on board automatically; volunteers and HAMs load the same file on the portal's Comms sheet page. Event-only changes (a net moved to simplex) go in the sheet's "this event only" box.

**Announce and log:** the level in force is announced on the stake net at each check-in and written in the EOC SITREP header. The EOC operator sets it on the Message Center's Setup tab (*PACE level in force*): the SITREP header, the page header and the wall display then show it, and a note logs each change with the time. The **PACE** button in the Message Center header shows the level in force and opens this section's rules as an operator checklist (step down, step back up, what changes at each level), printable as one page for the EOC desk. Use the same level names as the county so a stake liaison at the county EOC can report our status without translation.

**Volunteers never have to think about this.** Their instruction is the same at every level: fill the form, save it, send it by text, email or Wi-Fi if you can; otherwise get it to a HAM or read it to your Team Leader on FRS/GMRS. The Team Leader and HAM carry the PACE decision.

## 4. Roles at each level

Stake HAM operators serve under the Stake President's direction, through the stake Welfare and Self-Reliance Specialist (emergency communications). The specialist assigns them to the net, the EOC station and the field.

| Role | P | A | C | E |
|---|---|---|---|---|
| **Helping Hands volunteer** | Fill, save, Share / Send by text or email | Join any Wi-Fi with internet — home, shelter, business, meetinghouse, Starlink — and send by email or Wi-Fi messaging; or hand the file to the Team Leader | Hand the file to a HAM (AirDrop, Nearby Share, USB) **and/or** read the fields to the Team Leader on **FRS/GMRS** | **Print** the report, or fill a blank paper form; runner to Team Leader |
| **Team Leader / Crew Chief** | Receive files by text/email, forward to EOC | Collect files, forward over Wi-Fi or carry to HAM | Monitor the ward FRS/GMRS channel; relay reports on the **stake VHF/UHF net** (repeater, then simplex); carry files to the HAM; keep a paper log of who reported | Collect paper forms; runner to EOC; keep a stack of blank forms |
| **HAM operator** | Standing by; monitor the net | Load Data → Submit via **Telnet** (wired or Starlink) | Load Data → Submit via **VHF/UHF VARA FM** to a gateway, then the steps in §5: the local **VARA FM RMS Post Office**, **VARA FM P2P**, **VARA HF**; take voice reports on the stake net and type them into the template | Hold saved files; send when any path returns |
| **EOC operator** | Save emailed/texted files to the Drop Folder; SITREP to both lines by email, forms to the welfare line by Winlink Telnet | Drop Folder (Wi-Fi email) or Winlink auto-ingest; same upward traffic over Starlink | Winlink auto-ingest (slower); type voice reports from the stake net straight into the Message Center; SITREP and forms to the welfare line by VARA FM or HF into the CMS | Type paper reports in; printed SITREP + handoff USB to the liaison or courier; export handoff JSON if relocating |
| **Stake president · ERD · stake Welfare and Self-Reliance Specialist (emergency communications)** | Specialist recommends the level, stake president decides, ERD or specialist announces it on the net; monitor net; approve Supply Orders | same | same; know which HAMs the county has tasked | same; decide whether to relocate to the backup EOC |
| **Stake liaison at county EOC** | Not needed | Not needed | Pass urgent traffic to the lines above the stake via the county amateur station if the stake's own radio path is marginal | Pass the SITREP to the welfare line by county Starlink or satellite phone |
| **Council line (Area Seventy) · welfare line (WSRM, AWSRM) · Council / Area EOC if open** | Receive SITREP by email (both lines), forms by Winlink (welfare line); reply by email / Winlink; phone for urgent | same, over any internet they have | Pick up Winlink traffic from the CMS by Telnet or radio, whichever the Area has; reply the same way; monitor the published voice frequencies (VHF/UHF, then HF) | Receive by county liaison or courier; hold replies for the first path that returns |

## 5. Pre-event preparation (readiness per level)

Every level must be **exercised before it is needed**. A path that has never been tested is not a path.

- **P:** Volunteers install the app now, with internet (a volunteer who did not can still report at the EOC: the wall QR (Quick Response) code opens the forms with no app, and the phone page offers an **EMCOMM EOC** home-screen icon that works only on that EOC's Wi-Fi): iPhone Safari → Share → Add to Home Screen; Android Chrome → Install app. They open each form once. A bookmark is not enough: only the installed app works with no signal. They load the stake's Comms Sheet (portal → Comms sheet → Load sheet file), have saved and shared one practice form, and know their Team Leader's phone number and the EOC email address. EOC operator has the Drop Folder shortcut and has tested one email-to-drop ingest.
- **A:** Volunteers know that any Wi-Fi with internet is the Alternate path — home, a shelter, a business, a neighbor, a meetinghouse — and have tried sending the file over Wi-Fi with cellular turned off. The meetinghouse Wi-Fi password is on the Team Leader card. If the stake has Starlink, it is staged with power and someone knows how to put it up. HAM has done Load Data + Submit over Telnet.
- **C:** HAM has the nearest VHF/UHF RMS Gateway programmed and has connected to it within the last 30 days. The stake knows which RMS Relay mode each of its gateways runs (ask the sysop). The EOCs have agreed one local VARA FM RMS Post Office, and each EOC station has left and collected one Post Office message there. Each EOC station has sent and received one Winlink P2P message over VARA FM with a neighbouring EOC on the stake's P2P frequency. Each HAM go-kit holds a USB-C / Lightning thumb drive (see *From an iPhone to a Windows laptop* below). At least one stake HAM holds General or Extra, has VARA HF installed, and has made one HF Winlink connection within the last 90 days. Stake VHF/UHF net frequencies (repeater and simplex) and ward FRS/GMRS channel assignments are published on the sheet below and checked against county GMRS use. Team Leaders own an FRS/GMRS radio and have checked in on a practice net. A monthly net exercises the voice path.
- **E:** Paper copies of the three Church forms are in every Team Leader's kit. The runner route from each staging area to the EOC is known.
- **Stake → up:** The Area Seventy's email and the WSRM's and AWSRM's email, phone and Winlink address are on the sheet and have each received a test SITREP in the last 90 days. The EOC HAM has sent one Winlink message to the welfare line's address by radio and had it answered. If a Council / Area EOC station exists, its call sign, VHF/UHF voice frequency or repeater, and HF backup frequency are published, the VHF/UHF path to it has been tested, and the stake liaison to the county EOC is named and has visited the county EOC.

**County coordination:** record which stake HAMs are ARES members. When the county reaches its own Emergency level it tasks ARES operators; plan the stake net around the HAMs who remain. Keep the stake voice net off county, NIFOG and ARES frequencies.

**The Winlink steps at Contingency, in order.** Each step has its own session and its own **Send as** choice, in Winlink Express's own terms. Move down a step only when the one above fails.

| Step | Use it when | Session | Send as | What happens |
|---|---|---|---|---|
| 1. **RMS Gateway** | Always try this first | Vara FM Winlink | Winlink Message | The gateway passes the message to the CMS. Any station picks it up over any connection. |
| 2. **Held at the RMS Gateway** | That gateway has lost its internet | Vara FM Winlink (no change) | Winlink Message (no change) | Works only if the gateway's sysop (system operator) set RMS Relay to **Hold for Internet access**. The gateway stores the message and sends it to the CMS when its internet returns. A recipient who connects to that gateway can also retrieve it. You cannot see when it goes, so expect a delay. **"No CMS available"** means this gateway is not holding mail: go to step 3. |
| 3. **Local VARA FM RMS Post Office** | No gateway will hold the message, or it cannot wait | Vara FM RMS Post Office | Post Office | The message stays at that RMS for pickup. It is not sent to the CMS or forwarded. **The recipient must connect to the same RMS** to collect it. |
| 4. **VARA FM P2P (peer-to-peer)** | No Post Office can be reached | Vara FM P2P | Peer-to-Peer | The message goes straight to the other station, with no RMS or CMS. Both stations must be ready on the agreed frequency, and the message must be addressed to the station you connect to. It is not forwarded beyond that station. |
| 5. **VARA HF** | VARA FM has failed in every mode above | Vara HF Winlink | Winlink Message | HF (high frequency) reaches an RMS Gateway anywhere in the country, and from there the CMS, so the welfare line can pick it up. |

- **Match Send as to the session.** A message of the wrong type stays in the Outbox with no error. When you change step, open the queued message and check Send as.
- **Only a gateway set up for it holds mail.** RMS Relay is optional, and the sysop chooses its mode before an outage. In its Normal mode a gateway with no internet rejects you with "No CMS available". Ask the sysops of your gateways which mode they run, and write it on the Comms Sheet.
- **Steps 3 and 4 reach only the station you planned with.** Neither reaches the CMS, so the welfare line sees nothing unless it connects to that same Post Office. To go further, the receiving operator sends it on as a new message.
- **Receiving stations must act too.** At step 3 the receiving EOC opens a Vara FM RMS Post Office session to collect its mail. At step 4 it keeps a Vara FM P2P session open on the stake's P2P frequency (§6a, §6d).
- **Check the delivery.** A message held or waiting for pickup has not arrived. Confirm anything urgent by voice on the net.

Messages received by these sessions land in the same Winlink `Messages` folder, so the EOC watcher reads them the same way. Practise each step before the event (§5 **C**).

**From an iPhone to a Windows laptop.** At Contingency there is no internet. AirDrop cannot reach a Windows laptop, and Mail or iCloud need internet. Plan one of these two:

1. **A USB-C / Lightning thumb drive in each HAM go-kit** (one that plugs into an iPhone and into a laptop). The volunteer taps **Save to My Phone** → **Save to Files** → the drive. The HAM plugs the drive into the Winlink laptop and uses **Load Data**.
2. **Run the EOC server with a travel router and no internet.** Phones join the router's Wi-Fi and tap **Send to EOC** (the wall display shows the QR, Quick Response, code). Nothing needs the internet. Pack the router and its power in the EOC kit (§6b).

**USB distribution kit.** Before the event, copy these to a USB drive for every EOC and HAM go-kit. Nothing on it needs the internet to install:

- the single-file installer (`ChurchEMCOMM_Installer_v1.0.bat`) and the ZIP package (`ChurchEMCOMM_Forms_v1.0.zip`)
- the Quick Reference Card PDFs (Portable Document Format files)
- this PACE plan
- the Python 3 installer for Windows from python.org
- the Winlink Express installer and the VARA FM and VARA HF installers
- the stake Comms Sheet file (`church_comms_sheet_….json`) and a printed copy

**Python with no internet.** The EOC server needs Python 3. Install it **before** the event, from python.org, and tick *Add python.exe to PATH*. The server launcher needs a real Python 3, not the Microsoft Store placeholder that only opens the Store (type `python --version` in a command window: a version number means it is real). On a Mac, the first `python3` may ask to download Apple's command-line tools from the internet: run it once before the event.

**Annual drill:** run the full chain at every level in one exercise. Start at P, turn off cellular and use Wi-Fi (A), pull the internet and go VARA FM + FRS/GMRS voice (C), then runner only (E). Time each step. The simulator writes an after-action report and a debrief for the room from the run (its `/report` and `/debrief` pages; see [simulation/README.md](../simulation/README.md)); file one **Drill feedback** issue per role, or tell the stake specialist ([FEEDBACK.md](FEEDBACK.md)). The EMCOMM simulator (`simulation/`, Quick Reference Card 5) plays the wards and the lines above so the drill has traffic without a disaster; one simulator per EOC, and the stakes people play send their own roll-ups by the real path.

## 6. Stake PACE sheet — fill in before activation

Modeled on the ICS-205 Incident Radio Communications Plan that public-safety PACE plans reference, and on the per-site resource inventory in the county plan. Keep a printed copy at the EOC and with every HAM operator.

### 6a. Paths

| Item | Value |
|---|---|
| Stake | |
| Emergency Response Director (name / phone) | |
| Stake Welfare and Self-Reliance Specialist, emergency communications (name / call sign / phone) | |
| Local Welfare and Self-Reliance Manager (WSRM) for this stake (name / phone) | |
| **P** — EOC email address for form files | |
| **P** — EOC operator cell for texted files | |
| **A** — Landline numbers: Stake Center EOC / Satellite EOC / backup EOC meetinghouse | |
| **A** — Meetinghouse Wi-Fi (network / password location) — volunteers may also use any other internet they can reach | |
| **A** — Starlink (who has it / where staged) | |
| **A** — Stake EOC Winlink address | `________@winlink.org` |
| **Council line** — Area Seventy / coordinating council (name / email; Winlink if any) | |
| **Welfare line** — AWSRM name / email / phone | |
| **Welfare line** — AWSRM Winlink address | |
| **Welfare line** — Area Welfare and Self-Reliance Specialist (name / call sign / phone / Winlink) | |
| **Council / Area EOC**, only if one is opened — location (area office / welfare facility / stake center) / HAM station (call sign / VHF/UHF voice frequency or repeater / HF backup frequency) | |
| **E** — Satellite phone (stake-owned, area office, or county: number / who holds it) | |
| **E** — Stake liaison to the county EOC (name / call sign) | |
| **C** — Nearest VHF/UHF RMS Gateway (call sign / frequency / mode / does it hold mail when its internet is down?) | |
| **C** — Backup VHF/UHF gateway (same details) | |
| **C** — Agreed local VARA FM RMS Post Office (call sign / frequency), and the EOC stations that collect from it | |
| **C** — HF gateway(s) tried and working (call sign / band / mode) | |
| **C** — Winlink P2P (peer-to-peer) frequency over VARA FM, and the EOC stations that listen on it (call signs) | |
| **C** — Stake voice net, primary: repeater (freq / offset / tone) | |
| **C** — Stake voice net, backup: simplex frequency | |
| **C** — Ward FRS/GMRS channel assignments (checked against county GMRS) | Ward 1: __  Ward 2: __  Ward 3: __ |
| **C** — Net schedule (routine / activation) | |
| **E** — Runner routes (staging area → EOC) | |
| County liaison — county EOC Winlink address | |
| County liaison — county amateur repeater(s) | |
| Stake HAMs who are ARES members (may be tasked by the county) | |
| Level in force (update during activation) | P / A / C / E — recommended by ______, decided by the stake president at ______ |

### 6b. Resources by site

| Resource | Stake Center EOC | Satellite EOC (ward building: ______) | Backup EOC (meetinghouse: ______) | HAM go-kit |
|---|---|---|---|---|
| Internet (facility / Starlink / any reachable) | | | | |
| Landline phone (number) | | | | |
| Satellite phone (number / who holds it) | | | | |
| Winlink station (call sign, Telnet / VARA FM / VARA HF) | | | | |
| VHF/UHF amateur radio | | | | |
| HF radio + antenna | | | | |
| FRS/GMRS radio | | | | |
| Power (battery / generator / solar) | | | | |
| Paper forms stocked (blank copies of each form: portal → *Paper forms*, or an EOC form address + `?blank=1`, **Print**) | | | | |
| EOC Message Center USB drive | | | | |
| USB distribution kit (§5) and a USB-C / Lightning thumb drive for iPhones | | | | |
| Travel router (no internet needed) for **Send to EOC** | | | | |

### 6c. One-page matrix (same layout as the county plan)

| Level | Field → EOC: forms (data) | Field → EOC: voice | EOC internet | Stake EOC → council line and welfare line |
|---|---|---|---|---|
| **Primary** | Cell text / email from phone | Cell phone call / text | Facility ISP | SITREP by email to both lines; forms to the welfare line by Winlink Telnet; phone |
| **Alternate** | Any Wi-Fi with internet, anywhere: email / messaging; HAM Telnet | Wi-Fi calling; landline (meetinghouse / home phone) | Starlink or any reachable ISP | Same over any reachable internet; Wi-Fi calling; landline |
| **Contingency** | Winlink VHF/UHF VARA FM: RMS Gateway, then the local RMS Post Office, then P2P to a nearby EOC; then HF | FRS/GMRS (ward) · VHF/UHF amateur net (stake): repeater, then simplex | none | Winlink VARA FM / HF into the CMS, the welfare line picks up by any connection; voice to the Council / Area EOC station if open: VHF/UHF, then HF, or via the county EOC amateur station |
| **Emergency** | Runner with paper form | Runner | none | Stake / area satellite phone if one exists; liaison at county EOC (county Starlink / sat phone); courier to the Council / Area EOC if open, else the nearest stake center that is up; relocate to backup EOC |

### 6d. EOC assignments (fill in when more than one EOC is open — see §2d)

| EOC | Level | Location (building / address) | Wards or part of community covered | Drop email | Winlink address | P2P frequency (VARA FM) | Net / FRS-GMRS channels | Reports to | Operator lead (name / call sign) |
|---|---|---|---|---|---|---|---|---|---|
| Stake Center EOC | Stake | | all wards not listed below | | | | | council line + welfare line (§6a); Council / Area EOC if open | |
| Satellite EOC 1 | Satellite | | | | | | | Stake Center EOC | |
| Satellite EOC 2 | Satellite | | | | | | | Stake Center EOC | |
| Council / Area EOC (only if opened) | Council / Area | | all stakes in the Council | | | | | Area Presidency / Church headquarters as directed | |

Roll-up schedule: with every SITREP (interval set on the Setup tab: ____ h, directed by ________) · At C the roll-up goes as a Winlink attachment to the "Reports to" Winlink address · Last roll-up sent: ______ at ______ · Satellite EOC opened / closed (date, time, by whom): ______

## 7. Sources

- Winlink Express 1.8.6.0 Help: *No-Internet Operating Modes*, *Starting a Session*, *Composing a Message*, *Making a Peer-to-Peer Connection*, and the session names in the program itself. The help is installed with Winlink Express.
- Winlink, *Frequently Asked Questions*, "What is RMS Relay?" (the three RMS Relay modes; 2019, check it against your gateways): https://winlink.org/sites/default/files/download/wl2k_faq_5.pdf
- A county ARES *Communication PACE Plan* (the county's own spreadsheet, shared with the stake; access controlled by the county ARES): PACE ladders per function and a per-site resource inventory (command trailer, county EOC, backup EOC). Ask your county ARES for yours.
- CISA / NCSWIC, *PACE Plan* guidance (definitions of each level and the "never reuse a path" rule): https://www.cisa.gov/sites/default/files/2023-05/23_0426_ncswic_PACE-Plan_508.pdf
- Indiana Department of Homeland Security (DHS), *PACE Communications County Plan Template* ("Contingency requires entirely different devices"): https://secure.in.gov/dhs/files/PACE-Communications-County-Plan-Template-1-1.docx
- Washington State EMD, *Logistics Section Communications Annex* (PACE with Winlink at A/C/E, SHARES RMS stations, ICS-205): https://mil.wa.gov/asset/60f9cd5f8ad09
- The Church of Jesus Christ of Latter-day Saints, *Emergency Communication Guidelines*: https://www.churchofjesuschrist.org/study/manual/emergency-response/emergency-communication-guidelines?lang=eng
- The Church of Jesus Christ of Latter-day Saints, *Emergency Response* leader resources (2020), the manual the guidelines belong to: https://www.churchofjesuschrist.org/study/manual/emergency-response?lang=eng
- The Church of Jesus Christ of Latter-day Saints, *Emergency Communications Planning* (leader page; as of 2026-10-28 it redirects to the guidelines above): https://providentliving.churchofjesuschrist.org/leader/emergency-preparedness-and-response/communications/planning?lang=eng
- Grand Junction Stake emergency communication plan (phones first, then FRS/CB/MURS/GMRS/amateur simplex): http://shastadefense.com/Emergency%20Communication%20Plan%2012012013(2).pdf
- Church Tech Forum, *Ward Emergency Communications Plan* (ward FRS channels reporting to stake on MURS/GMRS): https://tech.churchofjesuschrist.org/forum/viewtopic.php?t=45345
- Field Notes, *PACE* (practitioner placement of FRS, amateur voice, Winlink, APRS (Automatic Packet Reporting System) at Contingency): https://field-notes.readthedocs.io/en/latest/PACE.html
- Wikipedia, *PACE (communication methodology)*: https://en.wikipedia.org/wiki/PACE_(communication_methodology)

The stake examples are member-written local plans, not official Church policy. The Church guidelines say amateur radio "should be seen as one of several options" the specialist is familiar with, note that Church headquarters runs its own amateur radio nets and that local nets "may also be organized at the local unit level under the direction of priesthood leaders," and refer equipment questions to the Meetinghouse Facilities Handbook. The county's P25, talk-around and NIFOG tactical channels are public-safety resources and are not part of this plan.
