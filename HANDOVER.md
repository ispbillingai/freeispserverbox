# FreeISP Server Box — CAD handover

**Written 16 Aug 2026 for whoever picks this up next.** Read this before touching any
geometry. It records what the box is, what is decided and why, what was tried and
rejected, what is still broken, and the specific traps in this codebase that have
already cost real time.

The owner is **Francis**. He measures the real hardware himself; his numbers are
authoritative and must never be "corrected" by an assumption. He works by building and
iterating from renders, so ship changes and let him look — but **verify before handing
over**, because a script that fails in Fusion is the single thing that has damaged his
trust in this workflow most.

---

## 1. What is being designed

A wall-mounted enclosure for an ISP customer-premises kit, 3D printed in PETG on an FDM
printer. Outside: **280 × 280 × 120 mm**.

It houses:

| Item | Size | Notes |
|---|---|---|
| MikroTik RB951 router | 114 × 139 × 29 mm | measured, incl. full port-face layout |
| Tenda 5-port switch | 82 × 52 × 23 mm | measured |
| Mains extension strip | 240 × 47 × 29 mm | |
| 3 × mains adapters | 46 × 46 × 52 mm | **PLACEHOLDER — not measured** |
| Custom "brain" module | 134 × 134 × 69.6 mm case | ESP32 + PCB, hangs from the lid |
| 12 V 15 W siren horn | flared bell, see §4 | anti-theft alarm |

The brain module is its own sub-project (`FIR_ModuleGadget` case + `FIR_ModulePlate`
electronics tray + a 115 × 115 mm rev-H PCB). It is largely settled; the **large shell is
the active work**.

---

## 2. How the CAD is built — read this first

There is no `.f3d` master. **Every part is a Python script that draws itself in Fusion
360.** One folder per part:

```
fusion/<Name>/<Name>.py          <- workspace master, edit this
fusion/<Name>/<Name>.manifest    <- Fusion script metadata
fusion/_shared/FIR_Interface.py  <- THE shared contract (see below)
```

### 2.1 The deploy trap (has cost hours)

Fusion does **not** run the repo. It runs
`%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts\<Name>\<Name>.py`.

After **every** edit you must copy the `.py`, the `.manifest`, and `_shared/` into that
folder. If you forget, Fusion silently runs old code and you will "fix" geometry that
never executed. Every script prints a `VERSION` string in its final message box — if the
popup shows an old version, the deploy is stale.

`FIR_ModulePlate`'s deployed copy is deliberately a 5-line loader that `exec`s the
workspace file. Do not overwrite it with a real copy.

### 2.2 The shared contract

`fusion/_shared/FIR_Interface.py` is the single source of truth for anything two parts
must agree on: tray and PCB dimensions, the brain-case mounting pattern, the switch's
position and port slot, the horn's envelope and mount, the cap snap detents.

It has **no Fusion imports** (plain Python, runs standalone) and calls `validate()` at
import time — a self-inconsistent edit raises immediately instead of quietly building
wrong geometry. Add new cross-part numbers here, never as a second hand-typed copy in a
part file. Duplicated constants are the historical cause of most bugs in this project.

### 2.3 Coordinate frame

Origin at the footprint centre. **+Y = front** (the port face), **+Z = up**, millimetres.
`HALF = 140`. Floor top is Z3, tub rim Z80, cap roof underside Z117, roof outer Z120.

### 2.4 Two coordinate traps that have both already caused real bugs

**The cap print-flip.** `FIR_Shell.build_top_lid()` draws the cap **roof-down** for
printing, and it is physically **flipped left/right** when assembled. So a feature at
cap-local +X ends up at assembled −X. This was invisible while the brain-boss pattern was
symmetric; the moment the case moved off-centre it became a live bug (four bosses on the
wrong side of the lid). `build_top_lid` now mirrors X exactly once. **Any new asymmetric
cap feature must do the same.**

**BottomLid vs CurvedLid handedness.** The BottomLid is a flat plate **turned over** onto
the tub front, so its source +X becomes shell −X. The CurvedLid is **not** turned over —
it prints face-down and only tips up 90° to slide on, so its source +X stays shell +X.
They do not share a source frame. The cover's openings were once written in the
BottomLid's frame and every notch landed on the wrong device. `FIR_ShellCheck`
re-verifies this every run.

### 2.5 Verification harness — it exists now, run it

`tools/fusion_offline_check.py` executes these scripts **offline** by stubbing the
Fusion API: it registers fake `adsk` / `adsk.core` / `adsk.fusion` modules in
`sys.modules` before importing each script, records every extrude and loft as an exact
prism (rect/circle/polygon swept along an axis), then queries the result — screw
alignment through both assembly flips, seat geometry, driver corridors, the cleat mate.

```
python tools/fusion_offline_check.py                                    # workspace tree
python tools/fusion_offline_check.py "%APPDATA%/Autodesk/Autodesk Fusion 360/API/Scripts"
```

Run it after every geometry change, on **both trees**. Rules already learned the hard
way, baked into the harness:

1. **It calls each script's real `run()`**, not the bare `build_*` functions. Calling
   builders directly once let a stale variable name in the final `messageBox` reach
   Francis — the model built perfectly and then threw on the last line.
2. Mind the cm↔mm factor (Fusion is internally cm) and which construction plane each
   sketch is on (`xY`→extrude Z, `xZ`→extrude Y, `yZ`→extrude X).
3. Fillets/chamfers/text are no-ops offline (the scripts guard them); the one clearance
   that depends on fillet material — the R7 corner driver pockets — is enforced
   analytically in `FIR_Interface.validate()` instead.

This turns "run it and send me a screenshot" into "here are the measured clearances",
which is exactly what this workflow had been missing.

### 2.6 The parts

| Script | What it builds |
|---|---|
| `FIR_Shell` | The tub, the deep top cap, and the horn sled. **The main print source.** |
| `FIR_BottomLid` | Flat front port face, 280 × 80 × 3 |
| `FIR_CurvedLid` | Sliding outer cover, 280 × 80 × 65 hood |
| `FIR_WallPlate` | The wall plate the box hangs on: French cleat + under-floor lock arms |
| `FIR_ModuleGadget` | The small brain case |
| `FIR_ModulePlate` | The electronics tray inside it |
| `FIR_ShellCheck` | **Inspection only, never print it.** Imports the real builders and assembles everything. |
| `FIR_GadgetPlateCheck` | Brain case + tray fit inspection |

`FIR_ShellCheck` has two useful flags at the top: `SHELLS_ONLY` (the five printed
shells, nothing else) and `SHOW_SCREW_MARKERS` (bright pins on every fastener axis).

Older `FIR_*` scripts in the repo are superseded experiments.

---

## 3. Confirmed measurements — do not change without Francis

### MikroTik RB951 — port face, x from left edge, z from base

| Feature | x | z | size |
|---|---|---|---|
| DC jack | 11 | 15 | ⌀6.5 |
| Reset | 19 | 10 | ⌀2.5 |
| PWR LED | 25 | 9.5 | 4 × 3 |
| ACT LED | 33 | 9.5 | 4 × 3 |
| 5 × RJ45 | 44.5 / 58.5 / 72.5 / 86.5 / 100.5 | 16 | 13.5 × 12.5 |

Body 114 × 139 × 29, sits on 3.5 mm standoffs, front face against the BottomLid.

### Tenda 5-port switch

- 82 wide × 52 deep × 23 high, centred at **shell X −71**
- One long service opening **68.8 × 11.5 mm**, 3.2 mm above its base, 6.6 mm land each
  side (replaced five guessed RJ45 cuts)
- **DC jack ⌀6 mm on its right-hand end face** (shell −X), centre 8.3 mm forward of the
  rear face. Height on that face is **assumed 11.5 mm — NOT MEASURED**
- The switch was moved inboard from X−85 to X−71 specifically so a straight barrel plug
  goes in from the side: **25.0 mm of air** at the jack face instead of 11.0 mm

### Alarm horn (12 V 15 W siren)

- Bounding box **102 wide × 105 long × 102 high**, tightening bolts stand ~15 mm off the back
- **It is a flared bell, not a drum.** Measured taper rear→mouth: **⌀74 → ⌀76 (middle) →
  ⌀83 (¾) → ⌀102 (mouth only)**. Bracket stand ~29 mm
- Mounting foot: **⌀69 mm disc, three ⌀6 mm holes**, isosceles — 38.5 mm base, 50 mm sides
- **NOT MEASURED:** distance from the mouth face to the foot disc centre. Currently
  assumed 99 mm; only the small sled reprints if it is wrong

### Brain stack

- Case 134 × 134 × 69.6, hangs from the cap, installed **+47 mm X, +10 mm Y**
- Tray 128.3 × 128.3 × 3 as a snug push fit in a 129 × 129 R9.5 pocket (0.35 mm/side)
- PCB 115 × 115 × 1.6, holes 4.5 mm in from each edge, **component face DOWN**, 52 mm
  above the tray top

---

## 4. Decisions already made, and why — don't re-litigate these

**Box is 120 mm tall.** 80 mm tub + 55 mm cap − 15 mm overlap.

**The brain case hangs from the lid, 47 mm off centre toward the MikroTik.** This is not
arbitrary. A full search of the cavity — every device, every piece of tub hardware, all
three horn orientations, 0.5 mm grid — found **no 102 × 120 × 102 mm void anywhere** in
the original layout. The brain case spans the middle from Z36.6 down, leaving only 70 mm
of full-height width beside it, and 17 mm once 120 mm of clear depth is also needed. The
+47 mm shift opens the switch-side column the horn stands in. The contract refuses to
load if that shift is reduced without moving the horn.

**The horn lives inside, on the floor behind the switch**, lying down, axis front-to-back,
mouth toward the front panel. It cannot be tilted — a 20° tilt already needs more headroom
than the 114 mm cavity has. Envelope X −124..−22, Y −27.5..77.5, Z 9..111.

**No sound vents anywhere.** Francis's call: the siren is loud enough that a plastic box
will not meaningfully muffle it. A slotted window was cut through both front parts and
then removed. `HORN_VENTS = False` records this. **Do not re-add a grille without asking.**

**Water scope: top-rain-tight only.** Rain from above must never reach the components;
dripping out of the bottom is fine and expected. Verified by geometry — continuous roof,
every roof edge sheds onto the outside of the cap skirt, the skirt gap opens downward
below the tub rim, the front seam drains through the cover's downward notches. **No
gaskets, no keyhole plugs, no port hood are wanted.**

**Horn fastening uses an adapter-plate sled.** The horn's own bracket arm and rear
tightening bolts hang over its foot holes, so **no in-box driver path to any foot bolt
exists**. All three measured foot bolts are driven on the bench into a printed sled; the
bolted-up horn+sled drops into a floor curb and two M4 wing screws (well clear of
everything above) clamp it. Service = two screws.

**Cap closure: 8 screws + 6 snap detents — all screws on the side walls (17 Aug 2026).**
Four M3 per side wall at Y −118/−75/0/+75, all at Z72, horizontally through the skirt
into 12 × 12 × 12 mm wall bosses. The old back pair at X ±115 is **gone**: it could not
be driven with the box hanging on a wall (8 mm of air behind it). The Y−118 row sits just
off the back corners and replaces it; the back edge is additionally held by its two snap
detents. Six stepped bumps on the tub's outer walls (Y ±45 sides, X ±45 back) snap into
10 × 6.5 mm through-windows in the skirt, so the cap clicks and holds itself before any
screw goes in.

**Every outside screw sits in a visible seat (17 Aug 2026 — this was Francis's live
complaint).** A flush 3.4 mm hole on a 286 mm face is invisible in a shaded render, so:
the 8 cap screws each sit in a **⌀12 mm pad standing 2.5 mm proud** of the skirt with a
⌀6.5 counterbore cut back to the original skirt face (the M3 pan head disappears fully
into the pad; every engagement number is unchanged). The 6 BottomLid screws get the same
⌀12 pad, 1.5 mm proud, with the counterbore re-cut from the pad top — the head land
**grows from 0.8 to 1.9 mm**. The CurvedLid prints face-down, so its 2 lock screws get a
⌀10 **dished recess** 1.0 mm into the face instead of a proud pad. Seat dimensions live
in `FIR_Interface.py` (`M3_SEAT_*`, `CAP_SEAT_*`, `LID_SEAT_*`, `COVER_SEAT_*`).

**Wall mount: printed wall plate + French cleat (17 Aug 2026 — replaces the keyholes).**
The two ⌀11 keyholes could barely hold a 2–3 kg box and their screw heads protruded into
the adapter bank; both problems are gone. `FIR_WallPlate` (276 × ~70 × 9 mm) screws to
the wall with up to six 4.5 mm screws whose heads sit in pockets **inside the plate** —
nothing enters the box. A full-width 45° cleat bar on the tub's back wall (X ±95,
Z50.8–64, protruding 5.8 mm) drops onto the plate's matching 45° face and gravity wedges
the box back flat against the plate. A crest wall behind the bar tip means the box must
**lift 4.4 mm** before it can be pulled off — and two **M4 × 10 lock screws driven DOWN
from inside the box** (at X ±129, Y −130, into the plate's under-floor arms) stop that
lift. With the cap screwed on, those screws are unreachable: **the box cannot leave the
wall without first opening it.** That is the anti-theft story. Everything sits below Z65
so the cap skirt never touches the plate. All numbers are in `FIR_Interface.py`
(`WALL_*`, `CLEAT_*`) and `validate()` enforces the mate.

---

## 5. Tried and rejected — do not redo these

- **Horn mounted externally on the cap roof.** Built on a wrong assumption that the horn
  was a 104 mm drum standing upright. It is a flared bell on a swivel foot lying on its
  side. Every clearance computed against that shape was void.
- **Replacing the horn's third foot bolt with a printed locating peg.** Francis rejected
  losing a real fastener, and he was right — the model then showed that the two remaining
  bolts were not reachable either, which is what produced the sled.
- **Sound vents in the BottomLid and CurvedLid.** Cut, then removed (see §4).
- **Gaskets / IP sealing / port hood.** Explicitly out of scope.

---

## 6. OPEN PROBLEMS — this is where the work is

*(Fastening legibility and wall mounting were the two big ones; both were fixed on
17 Aug 2026 — see §4. What remains:)*

### 6.1 Heat-set inserts vs self-tappers (decision pending with Francis)

**Eight M3 self-tappers into printed plastic on a lid that will be opened repeatedly**
will eventually strip. Brass M3 heat-set inserts with machine screws are the normal
answer. The geometry is one flag away: flip `HEAT_SET_INSERTS = True` in
`FIR_Interface.py` and every tub/lid boss pilot converts from a 2.6 mm self-tap to the
4.0 mm insert bore. `FIR_Shell`'s popup raises this on every run. Needs Francis's call
(he'd have to buy inserts and use a soldering iron to seat them).

### 6.2 Wall plate load testing

The cleat + arms are dimensioned generously for a 2–3 kg box (full-width 45° bearing +
the whole back face flat on the plate), but a printed part on a real wall deserves a
hang test with the loaded weight before rollout. Print the plate flat, wall face down.

### 6.3 Unmeasured values currently carried as assumptions

Both are reported in the Fusion message box on every run:

| Value | Assumed | Effect if wrong |
|---|---|---|
| Horn mouth face → foot disc centre | 99 mm | only the small sled reprints |
| Switch DC jack height above its base | 11.5 mm | sets the clipped cradle post beside it |
| Adapter dimensions | 46 × 46 × 52 | placeholder, affects the whole back zone |

### 6.4 Thermal

With the vents deleted there is now **zero airflow**, around 10–15 W of electronics inside
a sealed box. Expect roughly 15–25 °C above ambient inside. It will work; the adapters age
faster. Flagged, not urgent, owner is aware.

### 6.5 Known tight fits (all verified, none failing)

| Clearance | Value |
|---|---|
| Horn mouth ring ↔ cap side-bolt boss (worst, during drop-in) | 1.00 mm |
| Horn ↔ brain case (at the mouth only) | 2.0 mm |
| Brain case ↔ MikroTik top | 1.1 mm |
| Horn top ↔ cap roof underside | 6.0 mm |
| Brain case ↔ +X wall (J4/J5 wire route) | 23.0 mm |

The brain case descends **blind** with 2 mm beside the horn when the cap closes. Lower it
slowly and square; a 3 mm tilt eats the gap.

---

## 7. Assembly order (as designed today)

0. **On the wall first:** level `FIR_WallPlate`, drive its wall screws (up to six ⌀4.5,
   heads finish inside the plate)
1. **Bench:** bolt the horn's foot to the printed sled with three M4 × 8
2. Drop the horn+sled into the tub's floor curb; two M4 × 10 wing screws behind it
3. Drop in the router and the switch (snap cradles); the switch stays serviceable
4. Extension strip, adapters, strap
5. **Hang the tub:** hold it against the plate, slide down until the cleat wedges home,
   then drive the two M4 × 10 floor locks straight down from inside at (±129, −130).
   These must go in **before the cap** — they are unreachable afterwards, by design.
6. BottomLid: 6 M3 into their visible pads from the front
7. Cover slides on the rails, 2 lock screws into their dished seats
8. **Separately:** assemble the brain stack into the cap — case-to-cap screws first while
   the case is empty, then the PCB, then the tray. This order is mandatory.
9. Lower the cap straight down until the six detents click, then 8 M3 side screws — all
   of them drivable with the box on the wall

Steps 5–9 can also be done on the bench and the whole box hung afterwards, but then the
cap must come off again for the floor locks — hang first, cap last.

Screw engagement, all verified: case-to-cap M3 × 12 = 9 mm bite; BottomLid M3 = 8 mm
(the deeper seat costs 1.1 mm); cap side M3 = 6 mm; horn M4 × 10 = 7 mm and bottoms
exactly at the pilot floor with 2 mm of tub floor beneath; wall-lock M4 × 10 = 6.6 mm
into the plate arm with 1 mm of arm left below. **Never use longer than M4 × 10 in the
horn pads or the wall-lock holes.**

---

## 8. Working with Francis

- **Build and iterate.** He would rather see a change and react to it than answer a long
  list of questions. Ask only when two readings would produce materially different work.
- **His measurements win.** When something conflicts, the physical part is right.
- **Flag every assumption loudly**, in the Fusion popup, not just in chat.
- **Verify before handing over.** Run the scripts. He has been given broken code before
  and it is the main reason he distrusts this loop.
- **Do not defend a bad design when he pushes back.** Twice in this session he was right
  and the model confirmed it — the horn's unreachable bolts, and the missing back-wall
  screws on the cap.
- If he asks what a feature in a render is, tell him he can click it: every body in
  `FIR_ShellCheck` is named, and inspection-only bodies are prefixed `CHECK:`.

---

## 9. Suggested first moves for whoever takes over

1. Have Francis run `FIR_ShellCheck` (and `FIR_WallPlate`) and react to the new screw
   seats and wall mount — both were his complaints, both are now built, and both are in
   the deployed tree.
2. Get his decision on heat-set inserts (§6.1) — the geometry is one flag away.
3. Get the two outstanding measurements (§6.3) and set them.
4. Print the wall plate first and hang-test it with real weight (§6.2).
5. Run `python tools/fusion_offline_check.py` on both trees after **every** geometry
   change (§2.5) — it is fast and it has already caught real coordinate bugs.
