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

### 2.5 Verification harness — do this, it is the whole difference

You can execute these scripts **offline** by stubbing the Fusion API. Register fake
`adsk` / `adsk.core` / `adsk.fusion` modules in `sys.modules` before importing the
script, record every extrude and loft as an axis-aligned prism, then query the result for
interference and clearance. Mind the cm↔mm factor (Fusion is internally cm) and which
construction plane each sketch is on (`xY`→extrude Z, `xZ`→extrude Y, `yZ`→extrude X).

Two rules learned the hard way:

1. **Call the script's real `run()`**, not its `build_*` functions. Calling builders
   directly once let a stale variable name in the final `messageBox` reach Francis — the
   model built perfectly and then threw on the last line.
2. **Run both trees** — the workspace master and the deployed `%APPDATA%` copy.

This turns "run it and send me a screenshot" into "here are the measured clearances",
which is exactly what this workflow has been missing.

### 2.6 The parts

| Script | What it builds |
|---|---|
| `FIR_Shell` | The tub, the deep top cap, and the horn sled. **The main print source.** |
| `FIR_BottomLid` | Flat front port face, 280 × 80 × 3 |
| `FIR_CurvedLid` | Sliding outer cover, 280 × 80 × 65 hood |
| `FIR_ModuleGadget` | The small brain case |
| `FIR_ModulePlate` | The electronics tray inside it |
| `FIR_ShellCheck` | **Inspection only, never print it.** Imports the real builders and assembles everything. |
| `FIR_GadgetPlateCheck` | Brain case + tray fit inspection |

`FIR_ShellCheck` has two useful flags at the top: `SHELLS_ONLY` (four printed shells,
nothing else) and `SHOW_SCREW_MARKERS` (bright pins on every fastener axis).

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

**Cap closure: 8 screws + 6 snap detents.** Three M3 per side wall at Y −75/0/+75 and a
back pair at X ±115, all at Z72, horizontally through the skirt into 12 × 12 × 12 mm wall
bosses. Six stepped bumps on the tub's outer walls (Y ±45 sides, X ±45 back) snap into
10 × 6.5 mm through-windows in the skirt, so the cap clicks and holds itself before any
screw goes in.

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

### 6.1 Fastening is not legible (the live complaint)

Francis exported the model and **could not find anywhere to screw the two big lids
together from outside.** The screws are there — 3.4 mm clearance holes in the cap skirt at
Z72, plus 6 counterbored M3 through the BottomLid — but a 3.4 mm flush hole on a 286 mm
face is invisible in a shaded render, and the only obvious features on that face are the
10 mm snap windows.

This is a real design failure, not a rendering artifact: **a fastening point you cannot
see is a fastening point that does not exist.** It needs visible, seated fastening —
recessed pads or counterbores around each hole so the head sits flat and the location
reads at a glance.

Related: **eight M3 self-tappers into printed plastic on a lid that will be opened
repeatedly** will strip. Brass heat-set inserts and machine screws are the normal answer
and have not been discussed with him yet.

### 6.2 Wall mounting is inadequate

Currently: two keyholes in the back wall at X ±60 — an ⌀11 mm circle at Z56 with a
5 × 18 mm slot below. Francis's judgement, which I agree with: **"those can barely even
hold this on the wall."** The box will weigh roughly 2–3 kg loaded.

Also unresolved: the wall screw heads protrude into the box at Z47–56, and the adapter
bank starts about 4 mm inside that wall — likely interference.

This needs a proper mounting design, probably a separate wall bracket or plate the box
locks onto, and it should be treated as a real sub-problem rather than two holes.

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

1. **Bench:** bolt the horn's foot to the printed sled with three M4 × 8
2. Drop the horn+sled into the tub's floor curb; two M4 × 10 wing screws behind it
3. Drop in the router and the switch (snap cradles); the switch stays serviceable
4. Extension strip, adapters, strap
5. BottomLid: 6 counterbored M3 from the front
6. Cover slides on the rails, 2 lock screws
7. **Separately:** assemble the brain stack into the cap — case-to-cap screws first while
   the case is empty, then the PCB, then the tray. This order is mandatory.
8. Lower the cap straight down until the six detents click, then 8 M3 screws

Screw engagement, all verified: case-to-cap M3 × 12 = 9 mm bite; BottomLid M3 = 9 mm; cap
side M3 = 6 mm; horn M4 × 10 = 7 mm and bottoms exactly at the pilot floor with 2 mm of
tub floor beneath. **Never use longer than M4 × 10 in the horn pads.**

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

1. **Fix the fastening legibility** (§6.1) — recessed, visible screw seats on the cap and
   the BottomLid. This is what he is asking for right now.
2. **Design the wall mounting properly** (§6.2) — treat it as its own problem.
3. Get the two outstanding measurements (§6.3) and set them.
4. Raise heat-set inserts vs self-tappers as a decision.
5. Build the offline harness (§2.5) before changing geometry, not after.
