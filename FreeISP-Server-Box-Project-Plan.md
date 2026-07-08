# FreeISPRADIUS Smart Hotspot Server Box
## Complete Project Plan & Build Bible
_Brand (prototype): **FREEISPRADIUS** · Model: **FIR-HS250** · Owner: Francis · Location: Kenya (Nairobi / Eldoret)_
_Last updated: 24 June 2026_

---

## 0. HOW TO USE THIS DOCUMENT
This is the single source of truth for the project. Save it to `F:\freeispserverbox`.
Sections 1-3 = strategy & context. Sections 4-9 = the actual build (hardware, design, software).
Section 10 = design/render assets. Section 11 = IMPORTANT do-not-forget rules.
Section 12 = roadmap. Section 13 = exactly what to do next. Section 14 = open decisions.

---

## 1. THE OPPORTUNITY
- Kenyan WiFi hotspot operators buy pre-assembled "server boxes" (router + switch + PSU + breaker in an enclosure). Sellers (Kematekh Solutions, Hotspot Kenya, Jasiyo, Lipanet, etc.) assemble commodity parts, brand with a sticker, and sell convenience + support.
- The category is **commoditised** — everyone ships the same MikroTik + M-Pesa + FreeRADIUS stack.
- **Our edge:** a modern, branded, manufactured-looking box with a smart layer (status screen, anti-theft, remote monitoring) tied to **our own PHP billing/management platform**. Hardware is the vehicle; software + smart features + finish are the moat.
- **Validation seen:** the PME "Protel Multi Energy" hydropower controller = standard microcontroller + relays + custom PCB + firmware + branding. Proof the model works — assemble standard parts, add software + branding, sell as a product. Same playbook.

## 2. COMPETITOR INTEL (from Kematekh Solutions, observed)
- They use a **bought IP65 "waterproof adaptor box"**, label seen: **300 x 250 x 120 mm**. Not custom, not printed.
- Router confirmed as **MikroTik RB951 series** (box seen on their build video).
- They stress **"we always buy our products new"** (buyers care about new gear — match this claim).
- Price anchor: a complete hotspot server delivered countrywide at **~KSh 23,750**.
- **The gap we fill:** they have no internal tray, no hidden wiring, no status display, no anti-theft, no branding inside, no companion app. That's our entire differentiation.

## 3. PRODUCT STRATEGY
- **Buy** the molded outer IP65 enclosure (cheap, already waterproof, smooth finish).
- **3D-print** only the custom internal parts (mounting tray / smart-module + branded faceplate).
- **Stay PLASTIC, never metal:** metal is a Faraday cage that kills WiFi + RFID — fatal for a wireless-brained box. Metal only as a future premium "hardened" tier with external antenna/reader.
- **Modular smart-module concept (chosen direction):** build a compact 3D-printed sub-box that holds all OUR electronics (ESP32, screen, RFID, buck, battery, sensors). Build & test it on the bench, then bolt the finished module into the bought server box and connect with ONE cable bundle. Like a cartridge — repeatable, serviceable, testable, and sellable as a standalone upgrade.

---

## 4. ENCLOSURE
- **Outer shell:** bought molded **ABS IP65 "waterproof adaptor box" ~300 x 250 x 120 mm** (interior ~285 x 235 x 110 mm). The 120 mm depth is good — room for a two-layer layout.
  - Source in Kenya: electrical wholesalers (Luthuli Ave / River Road, Nairobi), CCTV shops (Bestcare etc.), Jumia/Jiji. Search: "IP65 distribution box / adaptable box / waterproof adaptor box 300x250x120" or "DB box".
  - Buy the LARGE enclosure type (room for boards), NOT the small cable-joint junction box.
  - Quality check: press the face — a slight "basin" flex that springs back = tough impact-resistant ABS/PP (good). Rock-hard brittle = worse.
- **Printed parts go INSIDE** this shell. Never print the waterproof shell itself (FDM isn't reliably watertight and costs more).

### Mounting the internal parts (the bought box has NO built-in posts)
You create mounting features by PRINTING them, not by needing them on the box:
1. **Drop-in tray/module** sized to rest on the box's internal ledge, trapped by the screwed-down lid.
2. **Printed standoff posts glued to the box floor** — CA glue/epoxy/solvent cement; **scuff/sand first if the box is PP** (PP resists glue).
3. **Back-wall screws** (rear face only, not weather-exposed) into the tray; seal heads with silicone — alternative.
4. **Mounting ears** on the printed module that bolt to the box wall/floor.
- **MANDATORY before CAD:** measure your ACTUAL bought box with calipers — interior floor, internal ledge height/width, wall taper (the basin slope), knockout positions. Box dimensions vary by brand. **Design to the box you're holding, not the label number.**

---

## 5. THE SMART-MODULE (our printed sub-box)
Compact printed box holding all our electronics; front face = the visible faceplate; screw-down lid; mounting ears; one cable bundle out.

- **Front faceplate shows:** 1.8" screen, POWER + INTERNET status LEDs, RFID "TAP" zone. (No MCB, no siren on the plate — kept clean.)
- **Inside:** ESP32-S3, LM2596 buck, 18650 + TP4056, MPU-6050, RC522 (against the wall behind the TAP zone), small buzzer.
- **Siren (12V horn):** lives in the BIG server box, not the module (keeps module compact; loud part separate).
- **Lid:** screw-down, 4 × M3 (most reliable/repeatable).
- **Design target:** interior ~120 x 90 x 45 mm, walls 2.5 mm. (Adjust to measured parts.)

### Component dimensions (standard sizes for the bought parts — verify on arrival)
| Part | Size (mm) | Notes |
|---|---|---|
| ESP32-S3 DevKitC N16R8 | ~70 x 26 x 13 | use ESP32-S3 pinouts, NOT Uno |
| 1.8" ST7735 TFT | PCB ~56 x 34; glass ~35 x 28 | window ~30 x 24 |
| RC522 RFID | ~60 x 40 x 5 | reads through ~2-3 mm plastic (thin TAP wall) |
| LM2596 dual-USB buck | ~52 x 27 x 15 | 12V->5V 3A |
| TP4056 charger | ~26 x 17 x 4 | protected version |
| 18650 cell + holder | ~75 x 20 x 20 | 1000mAh 3.7V (honest capacity) |
| MPU-6050 | ~22 x 17 x 3 | I2C |
| Status LEDs | 5 mm round | holes 5.2 mm |

### Design files produced (starter, parametric)
- `fir_module_base.stl` + `fir_module_lid.stl` — watertight, printable v1 (base box w/ screw bosses, board standoffs, mounting ears, gland hole; lid w/ screen window, 2 LED holes, RFID tap recess).
- `build_module.py` — editable source; every dimension is a named variable at the top. Re-run to regenerate after changing numbers.
- These are the ENGINEERING geometry. Refine in Fusion 360 (precise) and render for beauty in Fusion/Blender.

---

## 6. 3D PRINTING
- **Printer (available):** Creality **Ender-3 V3 Plus** — build volume **300 x 300 x 330 mm** (confirmed), up to 600 mm/s, nozzle to 300C, supports PLA/PETG/ABS/TPU/CF. **Open-frame (not enclosed).**
  - 300 x 300 bed fits a one-piece tray AND allows batch-printing multiple trays at once. Big upgrade over the 220mm Ender-3 V3 SE.
- **Materials:**
  - **PETG** — internal trays/module + general parts. Prints on the open-frame Plus, no enclosure, tough, moisture-OK. **Start everything here.**
  - **ASA** — visible/outdoor faceplate = the "socket look" (rigid, matte, UV-stable). Needs an enclosure on the Plus + ventilation. Use later for exposed parts; not urgent because the bought ABS shell faces the weather.
  - **ABS** — the literal socket material, but yellows/embrittles in sun; fallback only, indoor.
  - **PLA** — TEST/FIT prints only. Looks fine (glossy) but softens ~55C and goes brittle outdoors; toy-like feel. Not for final parts.
- **Workflow:** prototype/fit in PLA -> real trays/module in PETG -> outdoor faceplate in ASA (once enclosure added).
- **"Molded look" finish:** fine layers (0.12-0.16 mm), fuzzy-skin OFF for smooth (or ON to mimic grain), light sanding; ASA/ABS can be vapor-smoothed (PETG can't). Print in colored filament, don't paint-dip.
- **Filament sourcing KE:** iForge, Cubic3D, Nerokas, Microless, Jumia/Jiji. Buy sealed + desiccant.

---

## 7. SMART LAYER (the brain)
- **ESP32-S3** = control + intelligence. MikroTik still does ALL routing/hotspot/billing. They pair: MikroTik = network, ESP32 = brain/personality.
- **Connectivity (chosen):** ESP32-S3 joins a **hidden management SSID** on the RB951 (separate from the customer hotspot SSID), so a customer renaming their WiFi can't break it. No extra hardware.
- **Screen (1.8" ST7735) shows:** ONLINE status, PPPoE count, Hotspot count, status dot — AND a **live port map** (port icons 1-5 turn green when a cable is plugged in/active, grey when empty), read from MikroTik link state. Show/hide/off per box, pushed from PHP.
- **Status colors:** green = good, amber = ISP/internet down, red = offline/tamper.
- **Exterior port-status:** shown on the monitor (port map) and/or small per-port LEDs — see which ports are live without opening the box.
- **OTA:** ESP32 firmware OTA over WiFi (signed .bin + version, staged rollout, rollback); router/billing config pushed from PHP via MikroTik API/RADIUS.

---

## 8. ANTI-THEFT (Tier 1 — local, no GSM)
- **Detects:** tamper (reed/lid), power cut (mains sense), moved/torn-off-mount (accelerometer), offline (server heartbeat watchdog).
- **Owner vs thief = CARD DISARM:** swipe valid RFID card (RC522, inside behind faceplate, reads through plastic) -> disarm ~10 min -> open silently, logs card + time. Cards revocable via OTA.
- **Siren silence = CARD ONLY** (a button inside is useless vs a thief already inside).
- **Logic:**
  - Valid card -> disarm 10 min -> open silently (log).
  - Armed + lid opens (no swipe) -> 15s chirp -> SIREN.
  - Armed + torn off mount / violent motion -> SIREN instantly (skip grace).
  - Siren auto-timeout ~2-3 min, then STAY in logged alarm state; re-trigger if motion continues.
- **Outage vs theft:** box fuses power+motion+lid (power-lost + stationary + closed = quiet "outage" log; power-lost + motion = theft). SERVER correlates fleet-wide: many boxes silent = regional outage (suppress); one box dark while neighbours fine = suspicious (alert). **"Silence is the alarm"** via heartbeat watchdog.
- **Honest limit:** if power AND internet are both cut, the box can only alarm locally (can't SMS). **GSM module (Tier 2) is the only true remote alert in that case.**
- **Bonus:** on confirmed theft, remotely disable the router -> stolen box = brick.

## 9. POWER & BATTERY (right-sized)
- ESP32 + screen ~1-1.5 W. Day-to-day powered from box 12V via **LM2596 buck (12V->5V 3A)** -> ESP32 USB/5V; trickle-charges the cell.
- Backup = **1000mAh 3.7V Li-ion** (HONEST capacity; AVOID fake "7800mAh UltraFire") + **protected TP4056**. ~4-8 h ESP32 runtime — only need minutes-to-hours to alarm/report. NOT a 1 kWh battery.
- Keeping the WHOLE hotspot (router+APs, 10-30 W) alive through a blackout = a separate, bigger, optional premium DC-UPS. Different decision.

---

## 9b. BILL OF MATERIALS (prototype — bought, ~KSh 10,300 + lid sensor)
| Part | Use | KSh |
|---|---|---|
| ESP32-S3 DevKitC N16R8 (dual Type-C, WiFi) | brain | 1,400 |
| 1.8" ST7735 TFT (128x160 SPI) | screen | 1,100 |
| Beginner's RFID Dev Kit (RC522 + relay + buzzer + buttons + LEDs + breadboard + jumpers + extras) | core modules | 3,886 |
| MFRC-522 standalone (spare reader + cards) | card disarm | 460 |
| 12V 122dB security siren horn | alarm | 900 |
| MPU-6050 accelerometer + gyro | motion/theft | 750 |
| TP4056 charger (protected) | backup charge | 350 |
| 1000mAh 3.7V Li-ion cell | backup power | 850 |
| LM2596 dual-USB buck 12V->5V 3A | power ESP32 | 640 |
| Reed magnet detection switch (+ magnet) | lid/tamper | ~150 |

**Verify on arrival:** kit's relay + RC522 present; whether a reed module is included.
**Wiring notes:** ESP32-S3 pinouts (not Uno); ST7735 + RC522 = SPI (shared bus, separate CS); MPU-6050 = I2C; battery + (red) -> TP4056 B+, - (black) -> B-.
**Later/optional:** WS2812 LED + diffuser (premium light bar), per-port LEDs, GSM+GPS (Tier 2).

---

## 9c. SOFTWARE PLATFORM (PHP — the moat)
- Stack: **PHP / Laravel + FreeRADIUS + MikroTik API + Safaricom Daraja (M-Pesa STK/Paybill)**.
- Endpoint: `POST /api/box/event` — type = tamper/power/motion/heartbeat (box_id, type, timestamp, battery, signal, last_ip).
- **Heartbeat watchdog cron:** flag boxes silent > N min; correlate fleet-wide (area outage vs single suspicious box).
- Alerting: SMS/WhatsApp/push + dashboard. Config push to MikroTik. Firmware OTA hosting + staged rollout + rollback.
- Fleet dashboard: status, user counts, event history, last-seen + last-known IP/location.

---

## 10. DESIGN & RENDER ASSETS
**Tool split (use the right one for each job):**
- **CAD (Fusion 360)** = the buildable, dimensioned, printable model. Free for personal/startup.
- **Image AI (ChatGPT GPT-4o / Midjourney)** = beautiful CONCEPT renders for marketing/pitch/packaging (NOT buildable files; ignore real mm).
- **Blender** = pretty renders of the REAL model (import the CAD/STL, add materials/lighting). Use for beauty, not precision.
- Approved exterior concept exists (FreeISP glowing logo, green light-bar, screen, big green POWER/INTERNET LEDs, TAP zone, hidden door, side-in/bottom-out glands, spec label "FIR-HS250"). Use as the visual target.

**EXTERIOR prompt (concept render):** photorealistic market-ready wall-mounted smart WiFi hotspot enclosure, 300x250x120mm matte light-grey ABS, fine grain, rounded corners, no front screws; glowing green "FreeISP" logo + slim green light-bar; 1.8" LCD showing ONLINE/PPPoE:12/Hotspot:34 + green dot; LARGE bold green POWER + INTERNET LEDs; per-port status indicators; clearly marked RFID "TAP" pad with wave icon; small openable access door/flap (recessed grip) hiding reset+power buttons, flush + fine seam; silver spec label "FREEISPRADIUS Model FIR-HS250 12V 2A S/N + QR"; cable glands power+internet IN on LEFT side, internet OUT on BOTTOM; discreet side ventilation louvres; studio lighting, clean grey gradient bg, 4k photorealistic.

**INTERIOR prompt (concept render):** photorealistic top-down inside an open IP65 box with a multi-layer matte-black 3D-printed tray (factory look); top layer REAL MikroTik RB951 (cable IN port 1, OUT port 5) + 12V adapter + 4-port switch; lower layer ESP32-S3, PSU brick, LM2596 buck, 18650 + red TP4056, accelerometer, RFID-RC522, buzzer, 12V siren, breaker, terminal blocks; ALL wiring hidden in channels/under trays; reed switch on body + magnet on lid (door sensor); clear acrylic showcase cover (premium tier only); side ventilation louvres; glands left-in/bottom-out; bright top-down flat-lay, 4k photorealistic.
> Correction notes for renders: RB951 = WHITE/grey PLASTIC-CASED router (5 LAN ports in a row + barrel jack, internal antenna), NOT a bare green board. Label = "RFID-RC522". ESP32-S3 = narrow board, 2x USB-C, headers both sides. Buck = red dual-USB. Battery = 18650 1000mAh.

---

## 11. IMPORTANT NOTES (do not forget)
1. **Breadboard FIRST, PCB second.** Prove prototype + firmware before any PCB, or you pay for boards that don't work.
2. **Stay plastic, not metal** — metal kills WiFi + RFID. Premium hardened tier only, with external antenna/reader.
3. **Battery: honest capacity only** — avoid fake high-mAh cells; pair bare cell with PROTECTED TP4056.
4. **Clear/glass cover = premium tier only** — needs spotless internals; dust/condensation risk outdoors.
5. **Card is the kill-switch, not a button.** Only a valid RFID card silences the siren; inside controls live only after disarm.
6. **Tier 1 can't remote-alert during a full power+internet cut** — local siren + server silence-detection only. GSM (Tier 2) for true remote alert.
7. **Order packaging LAST** — only after enclosure size + product final, so boxes/inserts fit.
8. **Use ESP32-S3 pinouts, not Uno diagrams.** Ignore the Uno boards in the kits.
9. **Verify kit contents on arrival** (relay, RC522, reed module).
10. **Ventilation: cross-flow, downward/hooded outdoors, never top-open.**
11. **Measure the real bought box with calipers before CAD** — design to the box in hand, not the label.
12. **Design files are the build; renders are the sell.** Don't judge a printable STL by a pretty-picture standard — they're different jobs.

---

## 12. ROADMAP
**Phase 1 - Prototype (now):**
- Breadboard the smart layer (ESP32-S3 -> RB951 mgmt SSID -> screen/LEDs/RFID/siren/reed -> POST to PHP).
- Buy a sample 300x250x120 IP65 box + glands; measure it precisely.
- Print the smart-module (PLA test fit -> PETG real) and check parts fit + box fit.
- Build the PHP `/api/box/event` endpoint + heartbeat watchdog (cheapest, highest-value software task).

**Phase 2 - Custom PCB:**
- Once breadboard works, design a CARRIER board in **EasyEDA** (modules plug into headers; screw terminals for 12V/siren/reed/LEDs; ESP32 on a socket; mounting holes matched to the printed module; silkscreen logo+model+serial).
- Order from **JLCPCB / PCBWay** (~$2-5 / 5 boards + shipping; optional PCBA). Carrier board first; fully-integrated later at volume.

**Phase 3 - Productise:**
- Branding + spec-label; retail packaging (low-MOQ: **PrintShopKE**, **Chassy Technologies** ~50-100 pcs, ~7-10 days, Eldoret delivery; **Bafana Packaging**; volume: Pakspace, DPL Kenya, Maharshi, Carton Manufacturers).
- CA type-approval + KEBS checks; Daraja onboarding (own Paybill vs aggregator); product tiers (Lite / Pro / Max).

---

## 13. NEXT STEPS (do these in order)
1. **Measure your bought IP65 box** with calipers (floor, ledge, wall taper, knockouts). Record numbers here.
2. **Print a PLA test** of `fir_module_base.stl` + `fir_module_lid.stl`; check: ESP32 sits on standoffs? screen lines up with window? module fits the box + ears reach a wall? Note any mismatch.
3. **Adjust `build_module.py`** parameters to the real measurements (or rebuild in Fusion 360 from the Section 5 spec); reprint in PETG.
4. **Breadboard the electronics** and confirm screen + RFID + reed + siren + WiFi mgmt-SSID all work together.
5. **Write the PHP `/api/box/event` endpoint + heartbeat watchdog** (your strongest first software task — leverages your PHP background).
6. Iterate the faceplate aesthetics in Fusion (screen pocket + bezel, logo emboss, vent slots, lid lip/groove) -> render for beauty.

---

## 14. OPEN DECISIONS
- [ ] Confirm printer is the Ender-3 V3 Plus you have (yes) + whether to add an enclosure for ASA.
- [ ] Per-port status: monitor port-map (chosen) and/or physical per-port LEDs?
- [ ] Logo: short "FreeISP" mark (chosen for front) + full "FREEISPRADIUS" on label.
- [ ] Handle style: recessed grip on door (current plan) vs external handle.
- [ ] Glass/clear cover: which tier(s) get it.
- [ ] Battery runtime target; buzzer-on-module yes/no (currently siren in big box only).
- [ ] Remote disarm-before-service flow details.
- [ ] Final module + faceplate dimensions after measuring real parts/box.

---

## APPENDIX — PROJECT FILES
- `FreeISP-Server-Box-Project-Plan.md` — this document (the bible).
- `fir_module_base.stl`, `fir_module_lid.stl` — printable starter smart-module.
- `build_module.py` — editable parametric source for the module.
- (Concept renders: keep your ChatGPT/Blender exterior shots alongside.)
