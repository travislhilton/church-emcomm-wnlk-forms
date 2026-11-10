# Church of Jesus Christ EMCOMM

Emergency communications (EMCOMM) digital forms for **The Church of Jesus Christ of Latter-day Saints** ward, stake and Area disaster response.

> **An independent volunteer project.** Created by Travis Hilton (W9TLH) as a contribution to the EMCOMM community, to support Church emergency communications. It is not an official product, publication or service of The Church of Jesus Christ of Latter-day Saints and is not endorsed by the Church. The three forms mirror the Church's published PDF (Portable Document Format) forms so the data lines up with what the Church already asks for.

Digitizes the three official Church emergency response forms — Disaster Report (DR), Supply Order (SO) and Work Crew Log (WCL) — so volunteers can fill them on any phone or laptop, and HAM (amateur radio) operators can relay the data by Winlink radio email when cell and internet are gone. An Emergency Operations Center (EOC) Message Center collects every incoming report in one browser window, generates the situation report (SITREP), and forwards it with the Disaster Reports and Supply Orders up the chain by email or Winlink at every level of the communications plan. The same Message Center runs at a Satellite EOC in a ward building, at the Stake Center EOC, and at a Council / Area EOC when the coordinating council or the welfare region opens one — so the welfare line (the local Welfare and Self-Reliance Manager, WSRM, then the Area Welfare and Self-Reliance Manager, AWSRM) sees the same structured data the stake does.

The chain is **field → Satellite EOC → Stake EOC → the council line (Area Seventy) and the welfare line (WSRM, then AWSRM)**, and every piece below is written for every hop.

## Find your role

| You are | Start here |
|---|---|
| A Helping Hands volunteer, Team Leader or Crew Chief with any phone, tablet or computer | [For Field Volunteers](#for-field-volunteers--no-install-needed) — nothing to install |
| A licensed HAM operator at a field station or the EOC | [[2] HAM Field Operator](#2-ham-field-operator-licensed-amateur-radio) |
| Running a Satellite or Stake Center EOC | [[3] EOC Operator](#3-eoc-operator--satellite-stake-center-or-council--area-eoc-full-install) |
| The Area Seventy's council, the welfare line (WSRM, AWSRM), the Area Welfare and Self-Reliance Specialist, or a Council / Area EOC operator | [[4] Council and Area](#4-council-and-area--the-two-lines-above-the-stake) |
| A Stake President, Bishop or Emergency Response Director (ERD) | [For Stake and Ward Leaders](#for-stake-presidents-bishops-and-emergency-response-directors) |
| Joining an EOC or a drill from your own device | [Which device can I use?](#which-device-can-i-use) |
| Planning the stake's communications | [Communications PACE (Primary, Alternate, Contingency, Emergency) Plan](#communications-pace-plan) and [docs/PACE_PLAN.md](docs/PACE_PLAN.md) |

## Which device can I use?

Bring any device. Only two jobs need a Windows computer.

| What you are doing | What you need |
|---|---|
| Filling in forms: Helping Hands volunteer, Team Leader, Crew Chief | Any phone, tablet or computer with a browser |
| Leading or observing: Stake President, Bishop, Emergency Response Director (ERD) | Any device with a browser |
| Working as an EOC operator on the EOC Wi-Fi | Any device with a browser: open the address the EOC host shows |
| Showing the wall display | Any screen with a browser |
| Taking part in a drill: results and the debrief | Any device with a browser |
| **Hosting** the EOC server or the simulator (one laptop per EOC) | **A Windows laptop** |
| **Sending by Winlink** as a HAM operator | **A Windows computer** with Winlink Express |

**Any device** means iPhone, Android, iPad, Mac, Linux or Chromebook, in Chrome, Edge, Firefox or Safari.

**Why Windows for those two:** Winlink Express runs only on Windows, and a computer that cannot run Winlink cannot host. A phone, tablet, Mac, Linux computer or Chromebook joins the host by browser.

## The Three Forms

| Form | Church PDF | Who fills it | What it tracks |
|---|---|---|---|
| **Disaster Report** | [PD60000184](https://providentliving.churchofjesuschrist.org/bc/providentliving/content/emergency%20response/PD60000184_000_Emergency_Response_Disaster_Update_2016.pdf?lang=eng) | ERD or Helping Hands volunteer | Missionaries and members accounted for, injuries, homes damaged, Church buildings, community, volunteers deployed, anticipated needs, GPS (Global Positioning System) location |
| **Supply Order** | [PD10052205](https://providentliving.churchofjesuschrist.org/bc/providentliving/content/emergency%20response/PD10052205_000_WEL_ER%20Supply%20Order%20Form.pdf?lang=eng) | Team Leader or ERD | Items from the Church catalog (65 items plus local items) with quantities, delivery contact and address, requested date, signatures |
| **Work Crew Log** | [PD10052209](https://providentliving.churchofjesuschrist.org/bc/providentliving/content/emergency%20response/PD10052209_000_WEL_ER%20WorkCrewLog_HighRes.pdf?lang=eng) | Crew Chief | Up to 16 crew members, hours (auto-totaled), work orders, location, safety certification |

The links open the official PDFs on the Church's Provident Living site. The Church owns those forms, so this repository does not store them. If a link stops working, ask your area welfare office for the current form.

Every form reaches the EOC the same way at every level of the plan: the volunteer fills it, saves it, and sends the file by whatever path is open. The EOC shows it as the whole form (the **Open** button on any row) and rolls it up.

## Communications PACE Plan

The system is built around a **PACE** plan (Primary · Alternate · Contingency · Emergency), the framework the Cybersecurity and Infrastructure Security Agency (CISA), state emergency management and the military use: four independent networks, stepped through in order as each one fails, never reusing a path. There are three ladders: **field → Stake EOC** for digital forms and messages, **field → Stake EOC** for voice, and **Stake EOC → the council line (Area Seventy) and the welfare line (WSRM, then AWSRM)**. The level boundaries match the **county ARES (Amateur Radio Emergency Service) PACE plan** so a stake HAM and the county EOC mean the same thing by "Contingency." The forms, Winlink templates and EOC are identical at every level; only the transport changes.

| Level | Network | Field → EOC: forms & messages | Field → EOC: voice | Stake EOC → council line and welfare line |
|---|---|---|---|---|
| **P** Primary | Cellular | Volunteer taps **Share / Send** and texts or emails the file to the Team Leader, Emergency Response Director (ERD), or EOC Drop Folder | Cell phone call or text | SITREP by email to both lines (the Area Seventy's council; the welfare line, WSRM then AWSRM); forms by **Winlink Telnet** (Winlink over the internet) to the welfare line's Winlink address; phone for urgent |
| **A** Alternate | Any surviving internet, anywhere | Cell is down. Volunteer joins **any Wi-Fi that still has internet — at home, a shelter, a business, a neighbor's house, a meetinghouse, or a Starlink dish** — and emails / messages the same file. HAM: **Load Data** → Submit by Telnet over whatever internet is reachable | Wi-Fi calling / FaceTime / WhatsApp over the same Wi-Fi; a **landline** (meetinghouse or home phone) where the wiring survived | Same, over whatever internet the stake and the Area can each reach, including Starlink; landline |
| **C** Contingency | Radio | HAM sends the Winlink template over **VHF/UHF (very high / ultra high frequency) radio with the VARA FM modem** to the nearest **RMS (Radio Message Server) Gateway**, which may hold the message if its internet is down. Then the local **VARA FM RMS Post Office**, then **VARA FM P2P (peer-to-peer)** straight to a nearby EOC, then **HF (high frequency) radio with VARA HF**. [The steps are in the PACE plan](docs/PACE_PLAN.md#5-pre-event-preparation-readiness-per-level) | Volunteers on **FRS/GMRS (Family Radio Service / General Mobile Radio Service)** handhelds to the Team Leader; Team Leaders and HAMs on the **stake VHF/UHF amateur net** (repeater, then simplex). The operator types voice reports into the template or EOC | Winlink by VARA FM or HF into the **CMS** (Winlink's Common Message Servers); the welfare line picks it up by whatever connection they have. Voice to the Council / Area EOC station if one is open: **VHF/UHF** where the area's repeaters reach, **only if that fails HF**, or relay via the county EOC amateur station |
| **E** Emergency | Feet | Paper form carried by runner to the Team Leader or EOC: printed from the phone (**Print** under the form), or a blank paper form filled by hand ([how](#paper-forms--the-emergency-e-path)) | Runner / face to face | Stake or area **satellite phone** if one exists; stake liaison at the county EOC uses county Starlink / sat phone; courier to the Council / Area EOC if one is open, else to the nearest stake center that is up |

Step down after two failed attempts in 15 minutes or when the Stake President decides it — the stake Welfare and Self-Reliance Specialist (emergency communications) recommends the level, the Stake President decides, and the ERD or the specialist announces it on the net, as the Church's *Emergency Communication Guidelines* describe; step back up only after a test message round-trips. Volunteers do the same thing at every level. **Full plan, triggers, per-role duties, county coordination and the stake fill-in sheet: [docs/PACE_PLAN.md](docs/PACE_PLAN.md).**

---

## For Field Volunteers — Phone App, No Account

Helping Hands volunteers with a phone or tablet can be operating in under a minute. No Windows PC, no app store, no account required.

### Volunteer portal (open this on any phone or tablet)

**[https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/)**

Works on iPhone, Android, and any tablet.

**Before the emergency: install the app now, with internet** (no app store; it is a web app). A bookmark is not enough: only the installed app works with no signal. Forgot? At the EOC, scan the wall QR code: the forms work there with no app ([see Phones on the EOC Wi-Fi](#phones-on-the-eoc-wi-fi--new-reports-and-send-to-eoc)).
- **iPhone / iPad:** open the portal in Safari → **Share** → **Add to Home Screen**. Always open the forms from the **Church of Jesus Christ EMCOMM** icon (the phone may shorten the name under it). In a form or the Comms Sheet, tap **‹ Home** at the top to go back; a PDF opens in a browser view with its own **Done** button.
- **Android:** open the portal in Chrome → **Install app** (or ⋮ menu → Install app).
- **Open each form once** from the app.
- **Load your stake's Comms Sheet now** (portal → **Comms sheet** → **Load sheet file**). It holds the numbers and email addresses to send to, and works with no signal.

The app keeps the three forms on the phone: they open, capture GPS and save reports with **no signal at all**, and it updates itself whenever the phone has internet (open it before a drill or activation). A phone cannot copy the app to another phone without internet; a volunteer who never installed it can still fill in forms at the EOC from the EOC Wi-Fi.

### Volunteer workflow — 4 steps

1. Open the portal (scan a QR (Quick Response) code at your station, or go to the web address (URL) above)
2. Tap your form type — Disaster Report, Supply Order, or Work Crew Log
3. Fill in the form — your GPS (Global Positioning System) location is captured automatically when the form opens (allow location access if your phone asks). Tap **Get GPS Location** to refresh it. On a device that can't provide a location the GPS box grays out; tap **Enter coordinates manually** if you know them.
4. Send it — no files to manage:
   - **No signal where you are?** Tap **Save to Outbox**. The report stays on the phone; fill in and save as many as you need (each one keeps its own GPS).
   - **At the EOC (Emergency Operations Center):** join the EOC Wi-Fi (the wall display has a QR code for it), open the app, tap **Send to EOC** and scan the EOC QR code on the wall (or type the address under it). The EOC shows a green "received" screen and the Outbox empties. Sending twice is harmless.
   - **Have cell or internet anywhere?** Any Wi-Fi with internet counts — home, a shelter, a business, a meetinghouse, Starlink. Tap **Share by text or email** and send it straight to your Team Leader, Emergency Response Director, or the Stake EOC.
   - **Can't reach the EOC at all?** Tap **Save to My Phone** and get the file to a HAM radio operator — USB (thumb) drive, AirDrop, or Android Nearby Share. The operator loads it into Winlink and sends it to the Stake EOC by radio. From the Stake EOC your report goes on up the welfare line (WSRM, AWSRM) the same way.
   - **Nothing connects at all (Emergency)?** Tap **Print** under the form and give the paper to your Crew Chief or a runner, or copy it onto a blank paper form. See [Paper forms](#paper-forms--the-emergency-e-path).

> **iPhone:** the Outbox lives inside the Church of Jesus Christ EMCOMM app, so open the app (not Safari) to send it. After the green receipt, switch back to the app and tap **Yes**. If the receipt says a report failed, tap **No**: it stays in your Outbox.

### Paper forms — the Emergency (E) path

When nothing connects (no cell, no internet anywhere, no radio path), the report goes **on paper, by hand**, to your Crew Chief or a runner, who carries it to the Team Leader or the EOC. The EOC operator, or a HAM operator, types it in.

The printed page is laid out like the Church paper form it is based on (Disaster Report PD60000184, Supply Order PD10052205 on two pages, Work Crew Log PD10052209 in landscape): the same sections, labels and order, with the few boxes this project adds (THIS IS AN EXERCISE, the ward, the sender's GPS (Global Positioning System) location, the Crew Chief's safety box). The footer names the Church form it is based on and says it is not an official Church form.

**Before an event — keep paper on hand:**
1. Open the [portal](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/) and find **Paper forms** under the three form buttons.
2. Tap **Blank Disaster Report**, **Blank Supply Order** or **Blank Work Crew Log**. Each opens an empty form, with no date and no GPS filled in.
3. Tap **Print this blank form**. Print 3 of each. In the iPhone app, Print opens the form in the browser view (an iPhone home-screen app cannot print by itself): the print screen opens there; if it does not, tap **Share** → **Print**; then tap **Done** to return to the app. Open the portal once in Safari too, so printing also works with no internet.
4. Keep them with a pen in your go-bag. Team Leaders and EOCs keep a larger stack.

**During an event — print the report you filled in:**
1. Open your report (from the form, or the **Outbox** → **Open**).
2. Tap **Print** under the form. The printed page carries every answer in the boxes of the Church form layout, long answers in full, and a line saying where the paper goes.
3. The printer must be on the same Wi-Fi as your phone. If it offers its own Wi-Fi (Wi-Fi Direct), join that network first in Settings → Wi-Fi. No internet is needed.
   - **iPhone:** AirPrint printers appear in the print screen.
   - **Android:** the phone's print service (Default Print Service, or the printer maker's plugin).
   - **Laptop:** the form's **Print** works with any printer the laptop can reach.
4. Give the printed form to your Crew Chief or a runner.
5. **No printer?** Copy the report onto a blank paper form by hand.
6. Keep the report in your **Outbox** as well: it goes in digitally when any path comes back, and the EOC files a duplicate only once.

The same **Print** button is on forms served by an EOC (`http://<server-ip>:8080/forms/dr`, `so`, `wcl`), so an EOC can print blank forms for its paper stock (add `?blank=1` to the address) and type in paper that arrives by runner.

### Volunteer Quick Reference Card

The Volunteer Quick Reference Card has the QR (Quick Response) code, these steps, a pre-emergency checklist, and a no-signal fallback — print it, laminate it, keep it in your go-bag.

**[Open / Print the Volunteer Quick Reference Card](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/quick-ref-cards.html)** · **[Download the PDF](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf)** (US Letter, front and back on one sheet — print double-sided, "flip on long edge", at any printer or print shop)

### Printable Quick Reference Cards (PDF)

One PDF per role, formatted for 8.5 × 11 in paper with the card's front on page 1 and its back on page 2. Print double-sided ("flip on long edge"), then laminate or fold. Every card works in black and white.

| Card | For | PDF |
|---|---|---|
| 1 | Helping Hands Volunteer | [Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf) |
| 2 | EMCOMM HAM Operator | [Quick_Reference_Card_2_EMCOMM_HAM_Operator.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_2_EMCOMM_HAM_Operator.pdf) |
| 3 | EOC Operator (Satellite, Stake or Council / Area EOC) | [Quick_Reference_Card_3_EOC_Operator.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_3_EOC_Operator.pdf) |
| 4 | Bishops, Stake Presidents and Emergency Response Directors | [Quick_Reference_Card_4_Leaders_Overview.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_4_Leaders_Overview.pdf) |
| 5 | Drill Controller (the Church of Jesus Christ EMCOMM Simulator) | [Quick_Reference_Card_5_Drill_Controller.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_5_Drill_Controller.pdf) |
| 6 | Satellite EOC: what it does and what it owes the Stake Center (print with card 3) | [Quick_Reference_Card_6_Satellite_EOC.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_6_Satellite_EOC.pdf) |
| 7 | Stake Center EOC: who decides, what goes to the two lines above (print with card 3) | [Quick_Reference_Card_7_Stake_Center_EOC.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_7_Stake_Center_EOC.pdf) |
| 8 | Council / Area EOC: only when one is opened; stakes, totals, headquarters assistance (print with card 3) | [Quick_Reference_Card_8_Council_Area_EOC.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_8_Council_Area_EOC.pdf) |
| 9 | Your First Drill: for every drill participant, any role | [Quick_Reference_Card_9_Your_First_Drill.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_9_Your_First_Drill.pdf) |
| 10 | Team Leader and Crew Chief: leading a Helping Hands crew | [Quick_Reference_Card_10_Team_Leader_Crew_Chief.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_10_Team_Leader_Crew_Chief.pdf) |
| All | All ten cards in one file (20 pages) | [Quick_Reference_Cards_All.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Cards_All.pdf) |

The same PDFs are inside the ZIP package under `training\pdf\`, and the installer puts them in `Documents\Church of Jesus Christ EMCOMM\Field Worker Forms\Quick Reference Cards (PDF)\` with a shortcut straight on the desktop, *Church of Jesus Christ EMCOMM Quick Reference Cards*. To rebuild them after editing the cards: `python training/build-quick-ref-pdfs.py` (needs Chrome).

### For Team Leaders and ERDs — how to onboard volunteers at a staging area

The fastest way to get 20–40 volunteers operating at once is QR posters. Post them before workers arrive — at the staging area entrance, the sign-in table, and distribution points.

**[Print QR Posters](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/qr-posters.html)** — open this link in any browser and print. The main poster covers all three forms in one scan. Individual form posters work for dedicated stations.

Share the portal URL (web address) or QR poster image by text or email to pre-register volunteers before an activation.

> **No internet at all?** Install option **[1] Field Volunteer** puts the forms on the device before a disaster. Paper forms are the last resort: keep [blank paper forms](#paper-forms--the-emergency-e-path) in the go-bag.

---

## For HAM Operators and EOC — Install on Windows

| | Best For | Links |
|---|---|---|
| **Overview deck** | Stake EMCOMM planning and training | [Download ZIP](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Deck_v1.0.zip) |
| **Single-file installer** | Most users — one file, double-click it; fits in an email or on a USB (Universal Serial Bus) stick | [Download](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Installer_v1.0.bat) |
| **ZIP package** | The same installer plus every file laid out as folders, to look inside | [Download](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Forms_v1.0.zip) |

These links serve the files from the project's GitHub Pages site. The same files are on the [v1.0 release page](https://github.com/travislhilton/church-emcomm-wnlk-forms/releases/tag/v1.0).

---

## Install

### Single-file installer (recommended)
1. **Download** `ChurchEMCOMM_Installer_v1.0.bat` and save it anywhere
2. **Double-click** it — if Windows shows "Windows protected your PC" → click **More info** → **Run anyway**

### ZIP package
1. **Download** `ChurchEMCOMM_Forms_v1.0.zip` and save it anywhere
2. **Unblock** — right-click the ZIP → Properties → check **Unblock** → OK *(skip if no Unblock checkbox appears)*
3. **Extract** the ZIP, open the `installer\` folder, double-click **`install.bat`**
4. If Windows shows "Windows protected your PC" → click **More info** → **Run anyway**

> **Do not** use right-click → Run as Administrator — not needed, and installs to the wrong location.

**No internet required. No admin rights required.**

The installer puts everything in `Documents\Church of Jesus Christ EMCOMM\`. When Documents syncs to OneDrive (or another cloud service), it uses `C:\Church of Jesus Christ EMCOMM\` instead, so the EOC database never sits in a synced folder, and moves an earlier install there. The paths below say Documents; read them as that folder.

### Mac, Linux, Chromebook, Android and iPhone
There is nothing to install. Open the [portal](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/) in any browser, or, on the EOC Wi-Fi, the address the EOC host shows.

These devices cannot host the EOC server or the simulator, and they cannot run Winlink Express: both need a Windows computer. See [Which device can I use?](#which-device-can-i-use)

---

## After Installing — What To Do

The installer asks who you are. Choose your role and follow the steps below.

---

### [1] Field Volunteer *(no HAM license)*

**What installs:** Three browser-based worker forms + Quick Reference Cards (web page and PDFs), with desktop shortcuts.

**Install now (Windows, no admin rights):**
- **[Download the single-file installer](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Installer_v1.0.bat)** → double-click it → choose **[1]** · or **[download the ZIP package](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Forms_v1.0.zip)** → right-click → Properties → **Unblock** → extract → run `installer\install.bat` ([details](#install))
- Needs only a browser (the installer offers Chrome if it finds none)
- On a phone or tablet nothing installs — use the [portal](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/) instead

**To fill a form:**
1. Open the form from the **Church of Jesus Christ EMCOMM Forms** folder on your Desktop
2. Fill in all fields — GPS is captured automatically when opened from the online portal; a locally installed copy can't use GPS (browsers only allow it over https), so the GPS box grays out and you can type coordinates manually
3. Click **Save to Outbox** to keep it in this browser, or **Save to My Phone** for a `.txt` file (a Save dialog asks where)
4. On the EOC Wi-Fi click **Send to EOC** and type the EOC address shown on the wall; with internet, email the file to your Team Leader, Emergency Response Director, or the Stake EOC; otherwise get it to a HAM radio operator (USB drive, AirDrop, Nearby Share) to send by Winlink. Nothing works: click **Print** and send the paper by runner ([Paper forms](#paper-forms--the-emergency-e-path))

**Who to call, where to send it — do this before the emergency:** load your stake's Comms Sheet now ([Comms sheet](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/comms.html) → **Load sheet file**, with the file your stake specialist sends). It holds the points of contact, the EOC emails and Winlink addresses and the FRS/GMRS channels, and works with no signal.

**Print your Quick Reference Card** — open the *Church of Jesus Christ EMCOMM Quick Reference Cards* shortcut on your desktop and print `Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf` double-sided. Laminate it and keep it with your go-bag. Or download it directly: [Volunteer card PDF](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf) · [all cards on one web page](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/quick-ref-cards.html)

---

### [2] HAM Field Operator *(licensed Amateur Radio)*

**What installs:** Everything in [1] plus Winlink Express templates installed directly into Winlink. Needs Winlink Express; for radio, VARA FM or VARA HF (see [Requirements](#requirements)).

Stake HAM operators serve under the Stake President's direction, through the stake Welfare and Self-Reliance Specialist (emergency communications), who assigns them to the net, the EOC station and the field.

**Install now, in this order (Windows, no admin rights for the Church package):**
1. **Winlink Express** — [download from winlink.org](https://downloads.winlink.org/User%20Programs/) (Winlink_Express_install_*.zip), install, enter your callsign and a Winlink password, and make one **Telnet** connection to confirm it works
2. **The Church package** — **[single-file installer](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Installer_v1.0.bat)** (double-click it) or the **[ZIP package](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Forms_v1.0.zip)** (Unblock → extract → `installer\install.bat`) → choose **[2]**. It copies the templates into `C:\RMS Express\Global Folders\Templates\Church of Jesus Christ EMCOMM Forms\` ([details](#install)). Restart Winlink Express afterwards
3. **For Contingency (radio):** **VARA FM** for VHF/UHF and **VARA HF** for HF — [download from downloads.winlink.org](https://downloads.winlink.org/VARA%20Products/) (free at reduced speed; a one-time license unlocks full speed), plus your radio's sound-card interface. Program the nearest RMS gateway from [winlink.org/RMSChannels](https://winlink.org/RMSChannels)
4. **Your card:** [Quick_Reference_Card_2_EMCOMM_HAM_Operator.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_2_EMCOMM_HAM_Operator.pdf)

**A. Create and send a Church form in Winlink** — the usual case: a bishop, Team Leader or Emergency Response Director gives you the report by voice on the net, in person or on paper, and you type it in:
1. Open Winlink Express → **New Message** → **Select Template** → **Global Templates** → *Church of Jesus Christ EMCOMM Forms* → choose *Church of Jesus Christ Disaster Report*, *… Supply Order*, or *… Work Crew Log*
2. The form opens in your browser. **Drill, test or training? Tick THIS IS AN EXERCISE** at the top (as on the ICS 213, the Incident Command System general message): the message starts with an exercise banner, the subject starts with EXERCISE, and the EOC marks the report. Fill it in. Your callsign, name and station location are already filled from Winlink setup, and **Sender Location** is your station. **Save Data** keeps a copy of what you typed (a Save dialog lets you choose the folder) so you can reload it later with **Load Data**
3. **Submit**. The message lands in the Outbox with the report as its text. Address it to **your** EOC's Winlink address (Satellite or Stake Center, from the stake **Comms Sheet**, see [3]); the Stake EOC sends it on up the welfare line (WSRM, then the Area Welfare and Self-Reliance Manager, AWSRM)
4. **Open Session** by the level in force: **Telnet** over any internet (Primary / Alternate), at Contingency, in order: **Vara FM Winlink** to the nearest RMS Gateway (Send as Winlink Message); a gateway that has lost its internet may hold the message, and "No CMS available" means it will not; **Vara FM RMS Post Office** at the agreed station (Send as Post Office; the recipient must connect to the same station); **Vara FM P2P** straight to a nearby EOC's station on the stake's P2P frequency (Send as Peer-to-Peer); **Vara HF Winlink** (Send as Winlink Message) once VARA FM has failed in every mode: a special case a HAM operator does by hand, sending only what must go, because HF is slow. A message whose Send as does not match the session stays in the Outbox: [the steps are in the PACE plan](docs/PACE_PLAN.md#5-pre-event-preparation-readiness-per-level)
5. Confirm the message is in Sent Items and confirm receipt with the EOC on the net. Step down a level after two failed attempts in 15 minutes or when the Stake President decides it; step back up only after a test message round-trips

**B. Send a form a volunteer filled in** — a Helping Hands volunteer or Team Leader used the portal and saved a `.txt` file:
1. Receive the volunteer's `.txt` save file (by text, email, Nearby Share, AirDrop from an iPhone to a Mac, or a USB-C / Lightning thumb drive from your go-kit: AirDrop cannot reach a Windows laptop)
2. Open the matching template exactly as in step A1
3. Click **Load Data** and select the file — every field fills in. Your callsign and station location are never overwritten
4. Check **Sender Location**: if the volunteer's phone captured GPS, those coordinates are kept; if not, the form is stamped with your station's location and the message says so (*Source: HAM operator station … loaded form had no GPS*)
5. Review, then **Submit** and send exactly as in steps A3–A5

**If Submit shows "localhost refused to connect" (ERR_CONNECTION_REFUSED):** Winlink Express listens on `localhost:8001` only while the form is open, and it stops listening the moment *any* request other than the form's own Submit reaches that port (its log says *Standard Forms submission rejected: The form server accepts only POST submissions*). The usual cause is an old browser tab from an earlier Submit (address `localhost:8001`) being reloaded, which Chrome does by itself when you click a tab it has put to sleep. Nothing was sent. Recover in a minute: close the message window and every `localhost:8001` tab, Select Template again, Load Data again, Submit. Keep one form open at a time.

**The message text is the report** — plain text, no attachment, nothing extra on the air. At the receiving station, Winlink Express opens the message as the filled-in form in the browser (a view-only copy with Print / Copy / Save buttons); anyone reading it as ordinary email, such as the AWSRM, sees the same report as text.

**Addresses, gateways and nets** come from the stake **Comms Sheet** (see [3]): the EOC Winlink addresses, the RMS gateways to try in order, the repeater and simplex frequencies. Keep the printed copy in the go-bag, or load the sheet file on your phone at the portal's [Comms sheet](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/comms.html) page.

**Print your Quick Reference Card** — print and laminate the HAM Operator card: [Quick_Reference_Card_2_EMCOMM_HAM_Operator.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_2_EMCOMM_HAM_Operator.pdf) (Letter, double-sided).

---

**C. Practice and demonstrations** — seven **pre-filled practice forms** install beside the templates under *Church of Jesus Christ EMCOMM Practice* (three Disaster Reports, two Supply Orders, two Work Crew Logs from the simulator's earthquake scenario, invented Alpha Stake data, **THIS IS AN EXERCISE already ticked**). Select Template → *Church of Jesus Christ EMCOMM Practice* → pick one → it opens filled in → Submit → send it to your EOC. A training copy with its README also installs in `Documents\Church of Jesus Christ EMCOMM\Training\Winlink Practice Forms\` (desktop shortcut *Training - Winlink Practice Forms*), to hand to a new operator or copy to another station. A realistic exercise message in a minute, for your own practice or to show a new operator the whole round trip. Regenerate them for your own stake with `python installer/make-practice-forms.py --data <export> --out <folder>` (keep that folder private).

**D. Scenario training sets** — a full Winlink exercise for one drill, numbered in drill-clock order. **CCD-1** (Copper Creek Dam failure, Larkspur Stake, in the invented example community) has 24 messages: 16 filled Church forms from the stake's wards and care-center branch (Disaster Reports from the evacuation zones, the missing sister missionaries and their update, the care-center roll call, Supply Orders for the evacuated residents, clean-up and a warming centre, Work Crew Logs for the sandbag, moving and warming-centre crews) and 8 **ICS 213RR Resource Requests** on Winlink's standard form between the stake EOC and the Larkspur City EOC (four each way). Select Template → *Church of Jesus Christ EMCOMM Training CCD-1*; the copy and its README (every message, what it is for, the answer it expects) are in `Documents\Church of Jesus Christ EMCOMM\Training\Winlink Training CCD-1\`. The installer builds the ICS 213RR forms from the station's own standard Winlink form. Everything in it is invented. **Your own stake's set** (your units, places and city EOC) is written beside your directory export, never in the repository, and goes to the drill's participants in a private **participant package** (see the simulator section below). A new public set: write `training/scenario-samples-src/<scenario>.json` and run `python installer/make-scenario-samples.py`.

### [3] EOC Operator — Satellite, Stake Center or Council / Area EOC *(full install)*

**What installs:** Everything in [1] and [2] plus the EOC Message Center, the network server, the Wall Display and the [Church of Jesus Christ EMCOMM Simulator](#the-church-of-jesus-christ-emcomm-simulator--a-drill-without-a-disaster) for drills (Desktop shortcut *Church of Jesus Christ EMCOMM Simulator*). The same package runs at every EOC level — see *Running more than one EOC* below.

**Install now, in this order (Windows, no admin rights for the Church package):**
1. **Python 3.8 or later** (runs the EOC server) — [python.org/downloads](https://www.python.org/downloads/windows/) (tick *Add python.exe to PATH*). Install it before the event: the server launcher needs a real Python 3, not the Microsoft Store placeholder that only opens the Store (`python --version` must print a version). Keep the python.org installer on the stake's USB distribution kit ([docs/PACE_PLAN.md §5](docs/PACE_PLAN.md))
2. **Winlink Express** — [download from winlink.org](https://downloads.winlink.org/User%20Programs/), as in [2]
3. **The Church package** — **[single-file installer](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Installer_v1.0.bat)** (double-click it) or the **[ZIP package](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Forms_v1.0.zip)** (Unblock → extract → `installer\install.bat`) → choose **[3]** ([details](#install)). Desktop shortcuts: *Church of Jesus Christ EMCOMM EOC Server*, *… EOC Message Center*, *… EOC Drop Folder*
4. **For Contingency (radio):** VARA FM / VARA HF — [downloads.winlink.org](https://downloads.winlink.org/VARA%20Products/), as in [2]
5. **Optional:** a TV or spare monitor for the [Wall Display](#wall-display); the [Overview deck](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Deck_v1.0.zip) for training; your card: [Quick_Reference_Card_3_EOC_Operator.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_3_EOC_Operator.pdf)

**Multi-operator mode (networked — recommended for activations):**
1. On the EOC laptop: double-click **Church of Jesus Christ EMCOMM EOC Server** on your Desktop — a console window opens showing your network URL (e.g. `http://10.1.2.3:8080`)
2. Share that URL with all operators on the same Wi-Fi — they open it in any browser
3. **Setup tab** (once per activation): EOC level (Satellite, Stake or Council / Area), EOC name, the units it covers, the EOC it reports to (name, drop email, Winlink address) and, at a Stake EOC, the **two lines above the stake**: the council line (Area Seventy) and the welfare line (WSRM, then AWSRM), each with email and Winlink address, from the stake PACE sheet. The level sets the vocabulary on every tab (wards and bishops, or stakes and stake presidents) and the SITREP header. Then **Open a New Event** for this emergency (name, type, area, start date) and fill in its details (Stake President or incident lead, your operator name, operational period, and the **PACE level in force**) for the SITREP header. Change the PACE level there whenever the Stake President decides a new one: the header, the SITREP and the wall display all follow it, and a note logs the change with the time
   - **Help is one click away.** The header's **Help** button (or the **?** key) opens the *EOC Operator Guide*: every instruction for the page, with Print buttons. The **PACE** button next to it always shows the level in force; click it for **when and how to step down or back up**: the triggers, who decides, a step-by-step checklist each way, and what changes for the operator at each level
   - **One Emergency Event at a time.** Every report, roster entry and note belongs to an event. New arrivals (Winlink, Drop Folder, roll-ups) always file under the active event, and every operator on the server works the same one. When the next emergency comes, open a new event: the old one keeps all of its reports and can be switched back to at any time for review, export or forwarding. Every event has a name; use **Rename** on its row (or **Name / rename this event**) to change the name, type or area at any time. Close an event when it is over (it stays on file); the server backup holds every event
4. In Winlink Express, check for new mail periodically (or enable Telnet auto-check every 5 min)
5. Church form messages are **ingested automatically** — a blue bar in the EOC shows `📡 AUTO-INGEST ACTIVE` and messages appear on all screens within 10 seconds of Winlink receiving them
6. **Choose the Winlink callsign that feeds this EOC** (once): click the blue bar, type the callsign (it lists the ones found on this computer, e.g. `W9TLH, W9TLH-3`), then choose the folder in the folder browser: `C:\RMS Express` is marked as the Winlink Express folder. The choice is saved in `%LOCALAPPDATA%\Church of Jesus Christ EMCOMM\eoc-settings.json` for every later start. Winlink keeps each callsign's messages in `C:\RMS Express\<CALLSIGN>\Messages\`; the EOC reads the **received** ones there, only those that arrived after the event began, and never moves or changes them, so Winlink keeps its own mail. For an unattended start, put the callsign in that file (`"winlinkCallsigns": ["W9TLH"]`) or start the server with `--winlink-callsign=W9TLH`. With only one callsign on the computer, it is used without asking.
7. All operators see every incoming message in real time. Click a row's status badge to cycle it **NEW → ACK → ASSGN → DONE**; the change syncs to every screen
8. **Work Items** (second tab): the worklist. Every report filed adds the items it calls for on its own (missionaries not accounted for, injuries, each assistance request, every Supply Order awaiting approval, a crew without its safety briefing, an overdue unit); operators add their own. Click an item to set the owner, status (OPEN, IN WORK, UP = waiting on the line above, DONE), next action and the decision. See [Work Items](#work-items--what-the-reports-ask-you-to-do-or-decide)
9. Click the 📄 **Open** button on any row (Messages, Disaster Reports, Supply Orders or Work Crew Logs tab) to see the whole form laid out as the volunteer filled it — every section, the ordered items or crew list, the sender's location and radio operator — with **Print**, **Copy text** and **Save .txt** buttons. Winlink messages also show the plain text exactly as received.
10. **SITREP** (Disaster Reports tab → **Generate SITREP**): the first assessment as soon as possible, then on the **SITREP interval** EOC leadership sets for the event on the Setup tab (2, 4, 8, 12 or 24 hours, and who directed it — the Church guidelines ask for "regular status reports" to the Area Seventy, so use the schedule the Area Seventy or AWSRM asks for). The tab shows when the next one is due; generating one restarts the clock. The header carries the PACE level set on the Setup tab (or a blank to fill in); **Copy** it, and send it to the parent EOC / AWSRM by email (Primary / Alternate) or as a Winlink message (Contingency). Forward Disaster Reports and Supply Orders to the AWSRM's Winlink address from Winlink Express as they are logged, or send a roll-up (see *Running more than one EOC*)
11. **Phones in the EOC** send reports straight in: they scan the wall's QR code and tap **Send to EOC** (see [Phones on the EOC Wi-Fi](#phones-on-the-eoc-wi-fi--new-reports-and-send-to-eoc)). Set the **EOC location** on Setup → This EOC so their forms carry it. Every instruction is also in the page's **Help** button
12. Backups write automatically every 15 minutes to `Documents\Church of Jesus Christ EMCOMM\EOC Message Center\backups\`. Insert a USB drive at any time for an immediate backup copy.

> **Folders are chosen by clicking.** The Map data folder, the Drop Folder (click the green drop bar) and the Winlink Express folder open a folder browser on the laptop that runs the EOC server. From another laptop you type the path instead.

> **Auto-ingest not detecting messages?** Click the blue watcher bar: check the callsign and the folder (`C:\RMS Express`). The console window says which callsign feeds the EOC when the server starts. As a fallback, drag the message's `.mime` file from `C:\RMS Express\<CALLSIGN>\Messages\` (named by its Message ID, shown in Winlink) onto the EOC window.

**Receiving reports via text message, email, AirDrop, or USB (no Winlink needed):**

When a volunteer sends their `.txt` form file by text or email, the EOC operator saves it to the **EOC Drop Folder**:

1. Volunteer fills form → taps **Save to My Phone** → shares the `.txt` file by text, email, AirDrop, or USB drive
2. EOC operator receives it on their phone or email
3. Operator saves the `.txt` file to the **EOC Drop Folder** (Desktop shortcut: *Church of Jesus Christ EMCOMM EOC Drop Folder*)
4. The EOC server ingests it automatically within 10 seconds — a green **🌐 INTERNET DROP ACTIVE** bar appears when it's watching

Processed files move to `EOC Drop Folder\Ingested\` automatically.

**From an iPhone:** when a volunteer taps **Save to My Phone**, the share sheet opens — **Save to Files** lets them pick the folder (iCloud Drive → Downloads works with the synced-folder tip below), or they can send it straight from that sheet by Mail (preferred) or Messages. To send a saved file later, open Files, long-press the file → **Share** → Mail or Messages. AirDrop only reaches other Apple devices — it cannot send directly to the Windows EOC laptop. On the EOC laptop, open the email, right-click the attachment → **Save As** → the Drop Folder.

> **Tip — Windows Phone Link (Android only):** If the EOC operator has an Android phone, pair it with the EOC laptop using the Windows **Phone Link** app (Settings → Mobile devices). Text message attachments appear directly in Windows and can be saved to the Drop Folder in one click. Phone Link with an iPhone does not surface attachments — use email or the synced-folder option below.

> **Tip — Zero-touch with iCloud Drive or OneDrive:** Install **iCloud for Windows** (Microsoft Store) on the EOC laptop and sign in with the operator's Apple ID, so iCloud Drive appears at `C:\Users\<you>\iCloudDrive\`. Then click the green drop bar in the EOC → **configure** → set the watch path to `C:\Users\<you>\iCloudDrive\Downloads`. Any form the operator saves on their iPhone, or any attachment they **Save to Files** from Mail or Messages, syncs down and is ingested automatically. OneDrive works the same way (built into Windows 11; install the OneDrive app on the phone). Allow 10–60 seconds for sync on top of the 10-second poll.

**Single-operator mode (standalone — no server):**
1. Open **Church of Jesus Christ EMCOMM EOC Message Center** from your Desktop
2. In Winlink Express, receive messages → each one is a `.mime` file in `C:\RMS Express\<your callsign>\Messages\`, named by its Message ID (shown in Winlink's message list)
3. Drag and drop a `.mime` file onto the EOC window — the form data populates automatically (the file is decoded in the browser, so messages sent by older templates with the report as a `.txt` attachment load too)
4. Use the tabs to route reports: Disaster Reports → Supply Orders → Work Crew Logs; the 📄 **Open** button on any row shows the whole form with Print / Copy text / Save .txt; **Work Items** lists what the reports ask you to do or decide
5. At shift end: click **Export Handoff JSON** (a JavaScript Object Notation data file) and hand the file to the incoming operator — they click **Import Handoff JSON** to restore the active event's data
6. Emergency Events work here too (Setup tab): each event's records are kept in the browser, and a past event can be switched to or exported from its row

> **Note:** Auto-ingest only runs when the EOC server is running (networked mode). In standalone mode, drag-drop is the only way to load messages.

### Work Items — what the reports ask you to do or decide

The same list is on the phone page (`/m`, the wall QR code): tap an item to see it, **Take it**, or move it to In work, Up or Done. Your name goes in the item's log.

Reports pile up faster than anyone can read them twice. The **Work Items** tab turns them into a list the EOC works from, shared by every operator on the server:

- **Added on their own** when a report is filed by any path (Winlink, Drop Folder, phone, roll-up): *missionaries not accounted for* and *injuries or deaths* (high priority), *Church headquarters assistance requested*, *neighboring unit assistance needed*, *local Church facilities needed*, *homes destroyed: shelter check*, *Church building damage*, one item per **Supply Order** awaiting ERD and welfare-line approval, a **crew without its safety briefing**, and a roster unit that goes **overdue**. Each one keeps its source: 📄 opens the report.
- **Added by operators**: a call to return, a shelter to confirm, a decision the Stake President must make. Type it in the box, pick a category and priority, name an owner.
- **Each item** carries the unit, category, priority, **owner**, **status**, **next action**, a due time, the **decision** when it is made, and a log of every change with the operator's name.
- **Worklists** are the filter buttons: *Life safety*, *Missionaries*, *Supplies*, *Facilities*, *Assistance*, *Overdue units*, *Waiting on the line above*, *No owner*, *Done*. Leadership looks at the counts; operators work the list. **Copy list as text** goes into an email or Winlink message; **Copy as TSV** (tab-separated values) into a spreadsheet.
- **UP = waiting on the line above you.** The item goes with the next **Export Roll-up JSON** and lands *open* on the EOC above, naming your EOC, so the decision is on their list until they close it.
- **The SITREP** gains **Section I: Open decisions and actions** (what waits on the line above, what is being worked here, the decisions recorded in the period). The **Overview** shows the open count and the **wall display** lists the high-priority items and flags any with no owner.
- Standalone (no server) works too: items are derived in the browser and kept with the event; **Export Handoff JSON** carries them to the next shift.

### Phones on the EOC Wi-Fi — new reports and Send to EOC

Phones are clients only; the EOC laptop running the server is the only server. The EOC Wi-Fi needs no internet, so this works at every PACE level.

- **Anyone in the EOC** scans the main QR code on the wall display (or opens `http://<server-ip>:8080/m`, shown on the Setup tab). The **phone page** offers **New Disaster Report / Supply Order / Work Crew Log**: fill it in, tap **Send to EOC**, see a green "received" screen. No files, no app, nothing to install. Reports arrive on every EOC screen within seconds, marked *Phone / browser*.
- **No app? No problem.** Someone who never installed the app can still report: the forms on the phone page need no app. The page also shows how to put an **EMCOMM EOC** icon on the home screen (iPhone: Safari → **Share** → **Add to Home Screen**; Android: browser menu → **Add to Home screen**). **That icon works only on this EOC's Wi-Fi.** The EOC server is plain http, and a phone keeps an offline app only from an https page, so the icon cannot open in the field. When the phone can reach the internet, the page also offers **Install the full offline app**. When it cannot, give anyone going out with no signal paper forms.
- **GPS on those forms:** phones only share GPS with secure (https) pages and the EOC server is plain http on the LAN (local network), so forms served by the EOC are filled in with the **EOC location** (Setup tab → This EOC → EOC latitude / longitude, or *Use this computer's location*). The worker can change it.
- **Field workers back from a shelter** with reports in the Church of Jesus Christ EMCOMM app's Outbox: join the EOC Wi-Fi, open the app, **Outbox → Send to EOC**, scan the wall QR code (the app reads it with the camera; iPhone uses the bundled jsQR reader) or type the address under it. The app hands the reports to the EOC's receive page, which files them and shows the receipt. Their field GPS travels with each report.
- **Join the Wi-Fi by QR:** put the EOC Wi-Fi name and password on Setup → This EOC and the wall adds a second QR code that joins a phone to the network (the password is then shown on the wall; leave it blank to keep it off).
- **More than one EOC on one network** (drills mimicking EOCs in different cities): each EOC server announces itself on the LAN (UDP, User Datagram Protocol, broadcast on port 8089) and lists the others; the phone shows every EOC with its name and event and the report goes to the one picked (the server the phone is on relays it). Give every EOC a distinct name on the Setup tab. A second server on the same laptop: `python eoc_server.py 8081` from another folder.
- **Updates without internet:** the EOC server cannot update the app on a phone (the app comes from the portal and refreshes itself whenever the phone has internet). It does not need to: new forms at the EOC come from the EOC server and always match it, and the server accepts reports from older app versions; the receive page tells the worker when their app is out of date.
- **Firewall:** the first time the server runs, allow Python on **private networks** in the Windows firewall prompt, or phones cannot reach it. Guest Wi-Fi that keeps devices apart blocks it too; use the EOC's own router.
- **The full EOC Message Center works on a phone** too (same address, `/`): the layout stacks for narrow screens.

### Map tab

With the Church directory export on the EOC laptop (the same folder the simulator uses; set **Map data folder** on the Setup tab with **Browse…**, which marks the export folder; it never leaves the laptop), the **Map** tab draws every ward of the stake (every stake at a Council / Area EOC) as an outline **filled by roster status**: grey not reported, green reported and fine, amber reported with needs, red alert (missionaries not accounted for, injuries or deaths), blue voice contact, dashed amber overdue. Meetinghouses are dots, this EOC a blue ring, reports with a GPS fix small black squares. Click a ward for its roster line and reports; drag to pan, wheel to zoom. Ward names on the Roster tab must match the directory's names. Without a map folder the tab just says so and everything else works as before.

### Wall display

A read-only **big board** for a TV, projector or spare monitor so everyone in the EOC sees the same picture without crowding an operator's screen: the event and the **PACE level in force**, reports received (and how many are still NEW), which wards (or stakes, at a Council / Area EOC) have reported and which are overdue, homes damaged / destroyed, injured / deaths, volunteers and hours, open Supply Orders and the top items, the next SITREP due, the last 12 arrivals, a red alert strip (missionaries not accounted for, injuries, Church HQ (headquarters) support requested, overdue units) and the comms status (Winlink watcher, Drop Folder, last arrival, last roll-up). It refreshes every 10 seconds from the EOC server. Nothing on it can be clicked.

1. **Plug the TV in** as a second screen on any PC on the EOC Wi-Fi (an HDMI, High-Definition Multimedia Interface, cable), or use a laptop, Chromecast or smart-TV browser
2. Open **`http://<server-ip>:8080/wall`** in any browser on that screen (the server window prints the exact URL; the Message Center header has a **📺 Wall display** link and the Setup tab a *Wall Display* card with **Copy wall URL**), then press **F**, or click **Full screen (F)** in the bottom-right corner, for full screen (the same button or F leaves it)
3. **Operators join from the wall:** the bottom-left corner shows a **QR code** and the server's address on the EOC Wi-Fi (`http://<server-ip>:8080`). Anyone in the room scans it with a phone or laptop camera, or types the address, and lands on the EOC Message Center. The QR code is drawn by the wall page itself, so no internet is needed
4. Keep the **Roster** complete, with expected report windows, and keep the **PACE level** and event details current on the Setup tab — the wall is only as good as what the operators enter. Until the roster is filled in, the board lists the units named on the Setup tab as *Waiting*
5. Options on the URL: `?refresh=5` (seconds), `?sitrep=N` (overrides the event's interval on this screen only), `?latest=16` (rows of arrivals). If the server stops, the wall says so and keeps the last picture
6. When the Map data folder is set, a **map tile** above the roster shows the same status map, auto-fitted, with a count line (7 of 9 wards reported · 2 with needs)

Needs the networked server (no wall in standalone mode). No internet is needed: the page carries no outside fonts or scripts.

### EMCOMM Comms Sheet

One emergency-communications sheet for the whole stake, so points of contact, Winlink addresses, gateways and net frequencies are typed once and seen by everyone:

- **Edit it once:** Setup tab → **Comms Sheet**. Four tables (points of contact; EOCs with their Winlink address and drop email; Winlink RMS gateways in the order to try them at Contingency; voice nets with frequency, offset, tone and FRS/GMRS channels), a net schedule and notes. A box for **this event only** (a net moved to simplex, a temporary gateway) shows on top in orange and clears when the event closes. Every change is dated.
- **Everyone sees it:** the **Comms** tab on every operator's screen (phone and email links are tappable), the [wall display](#wall-display) (Nets & contacts panel), **Print sheet** for a one-page go-bag copy, and **Copy as text** for a Winlink message, email or stake-wide text.
- **Every EOC gets the same sheet:** **Export sheet JSON** (about 2 KB) → attach it to an email to each EOC's drop email (P/A), to a Winlink message to each EOC's Winlink address (C), or carry it on USB (E). The receiving EOC's server takes it on board automatically from the Drop Folder or the Winlink attachment when it is newer than the sheet on file, and logs a note; in standalone mode use **Import sheet JSON**. Satellite, Stake Center and Area EOCs therefore all work from one sheet.
- **Volunteers and HAMs:** send them the same JSON file by text or email; they open the portal's **[Comms sheet](https://travislhilton.github.io/church-emcomm-wnlk-forms/forms/comms.html)** page and tap **Load sheet file**. It stays on the phone and works without service, with tap-to-call numbers. A sheet can also be published in this repository as `forms/comms/<stake-code>.json` and opened as `forms/comms.html?stake=<stake-code>` (see `forms/comms/example.json`).

**Print your Quick Reference Cards** — print and laminate the EOC Operator card: [Quick_Reference_Card_3_EOC_Operator.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_3_EOC_Operator.pdf) (Letter, double-sided), and the card for your level: [Satellite EOC (6)](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_6_Satellite_EOC.pdf), [Stake Center EOC (7)](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_7_Stake_Center_EOC.pdf) or [Council / Area EOC (8)](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_8_Council_Area_EOC.pdf).

### Running more than one EOC — Satellite, Stake Center and Council / Area

The same install (choice [3]) runs at every EOC level (Quick Reference Cards 6, 7 and 8 give each level its own sheet). On the **Setup** tab each EOC sets its **level**, **name**, the **units it covers** and the **parent EOC** it reports to (name, drop email, Winlink address):

| Level | Where | Tracks | Rolls up to |
|---|---|---|---|
| **Satellite EOC** (optional, one or more) | A ward building away from the Stake Center, covering the wards or the part of the community the Stake President assigns to it — because it is closer to the damage, cut off from the Stake Center, or has power and internet when the Stake Center does not | Wards and bishops | Stake Center EOC |
| **Stake Center EOC** | The Stake Center | Wards and bishops, plus everything the Satellite EOCs roll up | The two lines above the stake (SITREP to the council line and the welfare line; forms to the welfare line), or a Council / Area EOC when one is open |
| **Council / Area EOC** (only when opened) | The Area Welfare and Self-Reliance Specialist's station, opened by the coordinating council or the welfare region at an area office, a welfare facility or a stake center | Stakes and stake presidents | Area Presidency / Church headquarters as directed |

Volunteers and HAM operators do exactly what they do today — they are simply given the address or net of *their* EOC on the stake sheet. Each EOC has its own server, database, Drop Folder email and Winlink address. The Disaster Report has an optional **Ward** field so a Satellite or Stake EOC can track reports by ward (leave it blank for a stake-wide report).

**Roll-up** moves records up the chain without anyone re-keying them, on the same PACE ladder as the SITREP:

1. On the lower EOC: Setup tab → **Export Roll-up JSON** (keep "only new since last roll-up" ticked) — one small `.json` file
2. Send it to the parent EOC: **P / A** attach it to an email to the parent's drop email · **C** attach it to a Winlink message to the parent's Winlink address (about 1 KB per record) · **E** carry it on a USB drive with the printed SITREP
3. On the parent EOC nothing needs clicking: the Drop Folder watcher and the Winlink watcher both merge `.json` roll-ups automatically. From USB, drop it in the Drop Folder or click **Import Roll-up JSON (merge)**

Nothing is counted twice — a merge skips any record it already has by id, Winlink Message-ID or form content, and keeps the parent's own status and notes. A roll-up carries the summary fields of each report, not the full text (radio airtime), so **Open** at the parent EOC shows the summary and says where the complete form is. The SITREP gains **Section H: Reporting EOCs** (who rolled up, how much, when), the Overview shows the same, and the Messages tab has a **Via** column. **Import Handoff JSON** is different: it *replaces* everything and is for shift change only. Full detail and the EOC assignment sheet: [docs/PACE_PLAN.md §2d and §6d](docs/PACE_PLAN.md).

---

### [4] Council and Area — the two lines above the stake

Above the Stake EOC the Church structure has **two lines, not one EOC**:

- **The council line.** The **coordinating council** is the Area Seventy and the stakes he presides over. It has no building, phone or Winlink address of its own; the Area Seventy is reached by **email**. Priesthood decisions (help moving between stakes, a shared building opened as a Satellite EOC across a stake line) come down this line.
- **The welfare line.** The **local Welfare and Self-Reliance Manager (WSRM)** supports the stakes of one or more councils from a regional office and reports to the **Area Welfare and Self-Reliance Manager (AWSRM)** in the Area office. Supplies, Bishops' Storehouse deliveries and Supply Order approvals come down this line, and it reports onward to Church headquarters.
- **The Area Welfare and Self-Reliance Specialist** (called by the Area Seventy, usually a HAM) works both lines: the Church guidelines say they communicate "with both the coordinating council and the AWSRM" and keep the local WSRM informed.

So a Stake EOC sends its **SITREP to both lines** and its **Disaster Reports and Supply Orders to the welfare line**: by email at Primary / Alternate, by Winlink at Contingency (the welfare line has a Winlink address; the council gets the SITREP when any internet returns). The **Setup** tab has a row for each line (name, email, Winlink address), the SITREP header lists both, and the stake PACE sheet carries the same addresses ([docs/PACE_PLAN.md §6a](docs/PACE_PLAN.md)).

**A Council / Area EOC** exists only when the council or the welfare region opens one: the Area Specialist's station at an area office, a welfare facility or a stake center (the Church positions communication equipment at headquarters, some welfare facilities and area offices). When one is open, the stakes set it as the EOC they **report to** and their roll-ups merge there.

**Install now (Council / Area EOC):** exactly the [3] list above — [Python 3](https://www.python.org/downloads/windows/), [Winlink Express](https://downloads.winlink.org/User%20Programs/), then the **[single-file installer](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Installer_v1.0.bat)** or **[ZIP package](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Forms_v1.0.zip)** → choose **[3]**; [VARA FM / HF](https://downloads.winlink.org/VARA%20Products/) for radio.

**What installs:** the same choice **[3]** as a stake. On the **Setup** tab set the level to **Council / Area EOC**; the roster then tracks stakes and stake presidents instead of wards and bishops, the SITREP header says Council / Area EOC, and upward reporting is "Area Presidency / Church headquarters as directed". Open one **Emergency Event** per emergency, as a stake does; each stake's roll-ups and forwarded forms land in the active event. The [wall display](#wall-display) works the same here, with a stake board instead of a ward board.

**What arrives, and how:**
- **Stake SITREPs** by email (Primary / Alternate) or Winlink (Contingency), on each stake's SITREP interval. Section H of each one lists which Satellite EOCs reported to that stake.
- **Disaster Reports and Supply Orders** forwarded by Winlink from each Stake EOC — they auto-ingest like any Church form message, so the Area sees the same structured record the stake logged.
- **Stake roll-ups** (`.json` files) by email attachment, Winlink attachment or USB. The Drop Folder watcher and the Winlink watcher merge them with no clicks; nothing is counted twice.
- At Contingency the stake sends by radio into the Winlink servers and the welfare line or the Council / Area EOC picks it up by Telnet or radio, whichever it has. At Emergency, through the stake's liaison at the county EOC or by courier.

**What the welfare line or the Council / Area EOC does with it:**
1. **Overview** and **SITREP Section H** show which stake has gone quiet — chase it by the next path down
2. **Open** any Supply Order, decide, and reply (approve / deny / modify): open the item on the Work Items tab (it says *from <that stake EOC>*), press **Reply to <EOC>**, and send the `.json` reply to that stake EOC's drop email or Winlink address from the stake sheet; their Message Center closes the item **DONE** with the decision written in (a reply by voice or email works too; the stake then marks its copy DONE itself)
3. At a Council / Area EOC, generate the **Area SITREP** (Disaster Reports tab) for the Area Presidency and Church headquarters; it carries every stake's totals
4. Keep the upper side of the stake PACE sheets current: the Area Seventy's email, the WSRM's and the AWSRM's email, phone and Winlink address, and the Council / Area EOC station's call sign, VHF/UHF voice frequency or repeater, and HF backup frequency when one exists. Every stake tests those addresses quarterly.

**Training:** the EOC Operator path plus one drill: set the level to Council / Area, merge a stake roll-up, answer a Supply Order, send an Area SITREP. Full roles-by-level table: [docs/PACE_PLAN.md §4](docs/PACE_PLAN.md).

---

## For Stake Presidents, Bishops and Emergency Response Directors

You do not need to run any of this. The decisions that are yours:

- **Call the specialist.** A stake Welfare and Self-Reliance Specialist (emergency communications) recommends the PACE level during an activation; the Stake President decides; the ERD or the specialist announces it on the net. This is how the Church's *Emergency Communication Guidelines* describe it.
- **Approve the stake PACE sheet** ([docs/PACE_PLAN.md §6](docs/PACE_PLAN.md)): which meetinghouse is the backup EOC, which ward building could be a Satellite EOC, who holds the Starlink and the satellite phone, the council line and welfare line addresses, the county liaison.
- **Put the forms on phones before the event.** Ten minutes at a ward preparedness night or Helping Hands orientation: volunteers install the app (not a bookmark), open each form once, load the stake's Comms Sheet and fill one practice form. Post the QR posters at staging areas.
- **Keep paper on hand.** Every volunteer carries 3 blank copies of each form and a pen in the go-bag; Team Leaders and EOCs keep a larger stack ([Paper forms](#paper-forms--the-emergency-e-path)). Paper is the Emergency path when nothing else connects.
- **Drill it.** A monthly 15-minute net, one two-hour tabletop a year, and one full field-to-Area test a year. A path that has never been tested is not a path.
- **Read the Bishop's Overview card** — one sheet, the whole system, no technical detail: [Quick_Reference_Card_4_Leaders_Overview.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_4_Leaders_Overview.pdf) (Letter, double-sided) or the [web page](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/quick-ref-cards.html). The [Overview deck](https://travislhilton.github.io/church-emcomm-wnlk-forms/dist/ChurchEMCOMM_Deck_v1.0.zip) is the stake planning and training presentation.

During an activation the Stake EOC gives you accurate totals for your reports to the Stake President and the Area, and sends every Supply Order up the welfare line (WSRM, then AWSRM) for approval.

---

## Training and drills

| Role | Time | What they practice | Where |
|---|---|---|---|
| Helping Hands volunteer | 5 minutes | Install the app (not a bookmark), open each form once, load the Comms Sheet, fill one practice form, find the saved file, share it to yourself; print blank paper forms for the go-bag and try **Print** on the practice form | Ward preparedness night or Helping Hands orientation |
| Team Leader / Crew Chief | 1 hour | Collect `.txt` files by AirDrop, USB or email; deliver to the HAM; monitor the ward FRS/GMRS channel; keep a paper log | ERD or Team Leader training meeting |
| HAM operator | 4–6 hours + monthly net | Install templates; Load Data for all three forms; switch Telnet → VARA FM → VARA HF; one test message per connection type | EMCOMM net or a dedicated session |
| EOC operator (Satellite, Stake, Area) | Half day + tabletop | Start the server; Setup tab; load sample `.mime` and `.txt` files; generate and send a SITREP at each PACE level; shift handoff; roll-up | Stake EMCOMM training day |

- **Monthly 15-minute net:** roll call, one Winlink test message with dummy form data, EOC reads back key fields, gateway and equipment notes. Rotate the PACE level each month; once a quarter the test message goes all the way to the welfare line (AWSRM).
- **Annual tabletop (2 hours):** round 1 at Alternate (any Wi-Fi, Telnet, SITREP by email), round 2 at Contingency (VARA FM, USB transfer, FRS/GMRS reports relayed on the stake net, SITREP by radio). Debrief: only the transport changed.
- **Annual full drill:** Worker Form → Winlink → Satellite EOC → Stake EOC → the council line and the welfare line, every PACE level, time each step, after-action review.

### The Church of Jesus Christ EMCOMM Simulator — a drill without a disaster

The simulator plays a scenario against the running EOC server: Disaster Reports, Supply Orders and Work Crew Logs from the stake's own wards arrive by the channel the PACE level in force selects (phone upload at P and A, a Winlink `.mime` into the Received folder at C, a paper card at E), notes land in the EOC log, net cards go to the HAM operators, prompts go to the role players (the specialist recommends, the Stake President decides), and **work items** from the mission office, the county, the welfare line or the Stake President land on the EOC's Work Items list. The clock runs at 1× to 60×. The **hot wash** is the scenario's evaluation checklist; **Gather evidence** reads the EOC's Work Items list (who owned what, when, what was decided) and fills in what it can see.

- **A training session, step by step:** the simulator opens on its **Session** tab, the trainer's path: (1) before the meeting, set up and rehearse (pack, EOC, scenario planned; a few minutes at 10× shows every path); (2) **Reset for the session** keeps the rehearsal as a rehearsal, opens a fresh drill event on the EOC (no rehearsal traffic), plans the same run again at T+0 and sets PACE to the scenario's first level, and every EOC screen shows *ready: waiting for the trainer's GO*; (3) give the instructions and press **GO** (or schedule one start time on every laptop): the EOC's SITREP clock starts at GO; (4) watch the clock, phase, PACE, score and what comes next; (5) stop, then the hot wash, the after-action report, the [debrief for the room](#debrief-for-the-room) and the results at `http://<laptop>:8090/results` on any phone. The run saves itself every 30 seconds; after a restart or a closed window, **Resume** brings it back paused at the minute it was saved. A wall with a DRILL event open but no run says so.
- **Run it:** on the EOC laptop, with the EOC Server running and a DRILL event open, double-click **Church of Jesus Christ EMCOMM Simulator** on the Desktop (installer role [3]; it runs `EOC Message Center\simulation\start_simulator.bat`), or from the repository `python simulation\sim_server.py`. Then open `http://<laptop>:8090`. Setup → Map → Run → Roles → Hot wash. Card: [Quick_Reference_Card_5_Drill_Controller.pdf](https://travislhilton.github.io/church-emcomm-wnlk-forms/training/pdf/Quick_Reference_Card_5_Drill_Controller.pdf).
- **Data:** the organization pack comes from the Church directory export and the map from a local dataset; both stay on the laptop, never in the repository. [What a pack is and how to build one](docs/COMMUNITY_SETUP.md). Pseudonymized by default; real contacts only after the Stake President's consent is **recorded on the Setup tab** (who consented, the date, who records it, and the promise that nothing leaves the room); the consent is stamped on the badge, every run and the after-action report. The directory export has no emergency callings, so the Emergency Response Director, the specialist and the HAM operators are added on the Setup tab and saved beside the pack on the laptop.
- **Drill configuration — one file sets up every EOC and simulator:** the drill director writes a short *drill spec* beside the pack in `secure data` (which EOCs take part, the stake or councils each covers, its building, whether people **always** or only **optionally** staff it, its Winlink call sign) and runs `python simulation/drillconfig.py "<spec>.json"`. The resulting `drill-config.json` (organization names and pseudonymized contacts: it stays in `secure data`, never in the repository) is loaded on each EOC laptop: **Message Center → Setup → Load a drill configuration** (or start the server with `--config=<file> --eoc=<id> [--manned=<id,id>]` for an unattended start) sets the EOC identity, units, location, the EOC above, the council line (Area Seventy) and the welfare line (WSRM), the must-have roles it knows, the **map data folder**, the **Winlink call sign** that feeds the EOC and the drill event; **Simulator → Setup → Drill configuration** loads the pack, the scenario and what that simulator plays. Tick the optional EOCs that have people this time: one nobody staffs is played by a simulator; when the Council / Area EOC has people, the stake EOCs report to it.
- **Your own Church community:** export your councils, stakes, wards, leaders, buildings and maps from the Church directory into the layout in [docs/COMMUNITY_SETUP.md](docs/COMMUNITY_SETUP.md), run `python simulation/community.py check` and `init` on it, edit the starter drill spec and build the configuration. The maps work for actual operations too (Setup → Map data folder; the Map tab can lay the directory's own ward maps over the boundaries).
- **Partner agencies:** a city or county EOC that does not run this system exchanges the standard Winlink **ICS 213RR Resource Request** and **ICS 213 General Message** with the stakes, never Church forms; the EOC files each one as a work item named for the agency.
- **Several EOCs:** one simulator per EOC. Each drill director says what theirs plays: a Stake EOC (and the wards a Satellite EOC covers), a Satellite EOC (its wards), or a Council / Area EOC (its coordinating councils, with the stakes that have no EOC laptop played by the simulator and delivered as roll-up files into the Area EOC's Drop Folder; the stakes people play send their own roll-ups by the real path). Every EOC screen shows the drill bar with **I am ready**; the Run tab lists every EOC on the network and its state; **Schedule** starts every simulator at the same wall-clock time.
- **Scoring:** every report, card and work item the simulator sends creates a **need** with a deadline in drill minutes (owned, closed, decision recorded, typed in with the right numbers). A need met brings its resolution (the truck leaves Bramble Junction); a need overdue brings the caller back. The welfare line answers Supply Orders set UP unless people play the line above. The **scoreboard** is on the Run tab and in the DRILL bar of every EOC screen; the **after-action report** (scoreboard, done-when checks, the do-better list by role, the needs ledger, the hot wash, the timeline) is written when the run ends and printed from the Hot wash tab.
- **Scenarios and the example community:** the repository holds no real community. It ships an **invented** one, the **Juniper Plains Area** (two coordinating councils, eight stakes, 51 wards and branches, invented leaders with 555-01xx phones, drawn ward maps, a drill configuration; `simulation/example/juniper-plains/`, installed under `EOC Message Center\simulation\example\`), so anyone can run a drill, a demonstration or a test without a directory export: Simulator → Setup → Organization pack → that folder. Its developed scenario, **Copper Creek Dam failure**, starts at 07:50 on a Sunday in March with an evacuation order below a seeping dam; the dam fails at T+38 (4 hours, 148 injects including 47 consequences and replies, 14 roles, 30 hot-wash checks, 8 done-when checks): sacrament meetings to cancel, a care center surrounded by water, sister missionaries not accounted for, Contingency when the flood takes the substation and the fibre, warming centres, a rumour about a second dam, Helping Hands crews for the city EOC by ICS 213RR, a cold wet night. Its injects rehearse the failure modes of the real disasters of 2024 to 2026 ([docs/SIMULATOR_LESSONS.md](docs/SIMULATOR_LESSONS.md)); eight more hazards for the valley are outlined in [docs/SIMULATOR_SCENARIOS.md](docs/SIMULATOR_SCENARIOS.md). **Your own stake's scenarios** name your real places, so they live beside your directory export (`<export>/simulation/scenarios/`, listed by the simulator before the built-in ones), never in the repository.
- **Participant packages (private):** a drill's own reference cards (`training/build-scenario-cards.py`: participant briefing, controller and evaluators, the Winlink messages), its organization pack and maps with every leader **pseudonymized**, its scenario and drill configuration, and its Winlink training set go to the participants as one zip: `python installer/build-sim-package.py "<export>/simulation/sets/<CODE>.set.json"`. The zip is written beside the export, never into the repository; the builder refuses a package that still holds a real phone, email or leader's name. The example's own package (`simulation/example/juniper-plains/simulation/sets/CCD-1.set.json`) shows what one holds; its cards are in `training/scenario-cards/CCD-1/`.
- **Write your own scenario:** [docs/SCENARIO_AUTHORING.md](docs/SCENARIO_AUTHORING.md), step by step from the example.
- Details: [simulation/README.md](simulation/README.md), [docs/SIMULATOR_DESIGN.md](docs/SIMULATOR_DESIGN.md), [docs/SIMULATOR_SCENARIOS.md](docs/SIMULATOR_SCENARIOS.md), [docs/SIMULATOR_MAPS.md](docs/SIMULATOR_MAPS.md).

#### Debrief for the room

When the run ends, the simulator builds a short slide show for the projector from the run: `http://<laptop>:8090/debrief`. Open it from the Session tab (step 5) or the Hot wash tab.

- What went well comes first.
- Then the score, told honestly.
- Why it matters: the real-disaster lessons behind the injects the room missed.
- One or two things to do better, per role.
- Progress over the group's runs of the same scenario.
- The next drill date.

Keys: ← → to move, **F** full screen, **P** print (one slide per page). Names on the slides are invented unless real contacts were loaded with recorded consent.

The deck's *Training Path by Role*, *Church of Jesus Christ EMCOMM Simulator*, *Pre-Event Deployment Checklist* and *Next Steps* slides are the presenter's version of this section.

---

## Requirements

| Requirement | Notes |
|---|---|
| **A web browser** | **All roles** — Chrome, Edge, Firefox or Safari, on any device |
| **Winlink Express** | **[2] HAM Field Operator, [3] EOC and [4] Council / Area EOC** — required to send and receive Winlink messages · [Download at winlink.org](https://winlink.org) |
| **VARA FM / VARA HF** | **Contingency only** — software modems for Winlink by VHF/UHF or HF radio; free at reduced speed, a one-time license unlocks full speed · [Download at downloads.winlink.org](https://downloads.winlink.org/) · needs a radio-to-PC audio interface and a Technician (VHF/UHF) or General (HF) license |
| **Python 3.8 or later** | **[3] EOC and [4] Council / Area EOC only** — required for multi-operator networked server mode and the simulator (standalone EOC works without it) · [Download at python.org](https://www.python.org/downloads/) · install it before the event; the Microsoft Store placeholder that only opens the Store does not count |
| **Windows 10 or 11** | **The EOC host laptop and every HAM station only** — the installer, EOC server, simulator and Winlink Express run here. Everyone else joins by browser from any device: see [Which device can I use?](#which-device-can-i-use) |

---

## Simulator maps and geographic data

A community's map dataset provides organization boundaries, building locations and geographically positioned map images. The [simulator map guide](docs/SIMULATOR_MAPS.md) explains Google Maps, Leaflet and MapLibre compatibility, placement metadata, image resolution, exceptions and verification limits. Use vector boundaries for interactive territory and load original map artwork as needed. A real community's dataset stays on the EOC laptop (here, the git-ignored `secure data/` folder), never in the repository; [docs/COMMUNITY_SETUP.md](docs/COMMUNITY_SETUP.md) describes the layout. The invented example, `simulation/example/juniper-plains/`, shows every file.

## Support, feedback and bug reports

Contact your stake Welfare and Self-Reliance Specialist (emergency communications) or your Emergency Response Director.

Found a problem, or just finished a drill? **Tell your Team Leader or the stake specialist** (what you did, what you saw, which device). They pass it on.

Anyone with a GitHub account can **[open an issue](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new/choose)** — there are short forms for a bug report, drill feedback and ideas. The *report a problem* links at the bottom of every Worker form and the portal, and the **Report a bug / Drill feedback / Suggest an idea** buttons on the EOC Setup tab, open those forms with your role, the part of the system, your device, the date, the event, the PACE level and (from the EOC) the diagnostic block already filled in. Pseudonymized runs still show real unit and building names. Before filing an issue or screenshot, use the invented Juniper Plains Area or the Hot wash tab's "Report as text, units redacted". The whole process, including the end-of-drill hot wash and prefilled links by role, is in [docs/FEEDBACK.md](docs/FEEDBACK.md).

| Role | Report a bug | Drill feedback |
|---|---|---|
| Volunteer | [bug (phone form)](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&role=Helping%20Hands%20Volunteer%20(phone%20form)&part=Phone%20%2F%20browser%20Worker%20Form%20(Disaster%20Report%2C%20Supply%20Order%2C%20Work%20Crew%20Log)) | [drill](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=Helping%20Hands%20Volunteer%20(phone%20form)) |
| Team Leader / ERD | [bug](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&role=Team%20Leader%20%2F%20Emergency%20Response%20Director) | [drill](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=Team%20Leader%20%2F%20Emergency%20Response%20Director) |
| HAM operator | [bug (Winlink template)](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&role=EMCOMM%20HAM%20Operator%20(Winlink)&part=Winlink%20Express%20template%20(Initial%20form%2C%20Load%20Data%2C%20Viewer%2C%20message%20text)) | [drill](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=EMCOMM%20HAM%20Operator%20(Winlink)) |
| EOC operator | use the Setup tab button (adds diagnostics), or [bug](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&role=EOC%20Operator%20%E2%80%94%20Satellite%2C%20Stake%20or%20Area%20EOC&part=EOC%20Message%20Center%20(tabs%2C%20Open%20form%2C%20SITREP%2C%20roll-up%2C%20events)) | [drill](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=EOC%20Operator%20%E2%80%94%20Satellite%2C%20Stake%20or%20Area%20EOC) |
| Stake President / Bishop / observer | — | [drill](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=drill_feedback.yml&role=Stake%20President%20%2F%20Bishop%20%2F%20observer) |
| Installer trouble (any role) | [bug (installer)](https://github.com/travislhilton/church-emcomm-wnlk-forms/issues/new?template=bug_report.yml&part=Installer%20(BAT%20or%20ZIP)%20%2F%20desktop%20shortcuts) | |

## Contributing — developing this project (with Claude Code)

Volunteers are welcome to improve the forms, the EOC Message Center, the docs and the deck. Start with **[CONTRIBUTING.md](CONTRIBUTING.md)**: setup on Windows, a map of the repository, how to run and test everything, the release routine, and how to use **Claude Code** (Anthropic's coding assistant) to develop and evolve the system. **[CLAUDE.md](CLAUDE.md)** holds the standing project rules that Claude Code reads automatically in every session — read it yourself too; the rules apply to human contributors as well.

## License

The code and documentation are under the [MIT License](LICENSE): you may use, copy and change them, for your own community or anything else, as long as the license notice stays with them. `forms/vendor/jsQR.js` keeps its own Apache-2.0 license ([forms/vendor/jsQR-LICENSE.txt](forms/vendor/jsQR-LICENSE.txt)).

The license covers this project's own work only. It gives no rights to the Church's name, trademarks or forms, which belong to their owner. This is an independent volunteer project, not an official Church product.

## About

This system — the three forms, the Winlink templates, the EOC Message Center, the installer, the PACE plan and the overview deck — was created by **Travis Hilton (W9TLH)** as a contribution to the EMCOMM community. It is offered freely to any stake, ward or amateur radio group that can use it. It is an independent volunteer project, not an official product or publication of The Church of Jesus Christ of Latter-day Saints.
