# FreeISP CAD - current source of truth

## Active CAD task

Finish the **small brain case** first. It houses the 128.3 x 128.3 mm snug-fit electronics tray, the wire-in power modules and cell, and the 115 x 115 mm rev-H brain PCB. The large outer shell is not the active design target until this small case is confirmed.

## Edit and run this exact Fusion script

- Workspace master: `fusion/FIR_ModuleGadget/FIR_ModuleGadget.py`
- Fusion deployed copy: `%APPDATA%/Autodesk/Autodesk Fusion 360/API/Scripts/FIR_ModuleGadget/FIR_ModuleGadget.py`

Fusion currently runs the deployed copy, so keep it synchronized with the workspace master after every edit. Run the script in a **fresh Fusion design**; it deletes its old `FIR Module`, `FIR Brain Case`, and `CHECK:` bodies before rebuilding.

## Fusion launcher - scripts the user runs

The user runs project CAD through **Utilities > Scripts and Add-Ins** in Fusion. Every project script is loaded from `%APPDATA%/Autodesk/Autodesk Fusion 360/API/Scripts/<script>/<script>.py`; its editable workspace master is `fusion/<script>/<script>.py`.

Installed project scripts recorded from the launcher:

- `FIR_Assembly`
- `FIR_BottomBox`
- `FIR_BottomLid`
- `FIR_BoxBottom`
- `FIR_BoxFront`
- `FIR_CurvedLid`
- `FIR_Enclosure`
- `FIR_Faceplate`
- `FIR_Frame`
- `FIR_FullBox`
- `FIR_GadgetPlateCheck`
- `FIR_MainBox`
- `FIR_Mikrotik`
- `FIR_Mini`
- `FIR_Module`
- `FIR_ModuleBase`
- `FIR_ModuleGadget`
- `FIR_ModuleOpen`
- `FIR_ModulePlate`
- `FIR_OverhangTest`
- `FIR_PortPlate`
- `FIR_Shell`
- `FIR_ShellCheck`
- `FIR_ShellTub`
- `FIR_TestTile`
- `FIR_Tray`

`CustomGraphicsSample` and `ExtractBOM` also appear in the Fusion launcher, but they are Autodesk/sample utilities and are **not** FreeISP CAD sources.

### Required edit workflow

1. Identify the exact `FIR_*` script the user selected in Fusion.
2. Edit its workspace master under `fusion/<script>/`.
3. Synchronize the changed `.py` and `.manifest` into the matching `%APPDATA%` Fusion script folder.
4. Ask the user to rerun that same named script in a fresh Fusion design. Do not claim a visual change until the deployed copy is synchronized and run.

### Shared mechanical interface (do not duplicate these values)

- Canonical source: `fusion/_shared/FIR_Interface.py`.
- Deployed copy: `%APPDATA%/Autodesk/Autodesk Fusion 360/API/Scripts/_shared/FIR_Interface.py`.
- `FIR_ModulePlate`, `FIR_ModuleGadget`, `FIR_Shell`, and `FIR_ShellCheck` load this one contract for tray dimensions, PCB dimensions/hole pattern, the +Y cap offset, the four case roof holes, the derived cap-boss pattern, the brain case's outer envelope (`CASE_OUTER_W/H`, `CASE_BODY_Z`), the Tenda switch DC jack, and the whole alarm-horn mount (`horn_mount_points()`, `horn_wire_point()`). Edit the shared file first; do not hand-edit a duplicate coordinate list in an individual part. `FIR_Interface.validate()` raises on import if the contract is self-inconsistent, so a bad edit fails loudly in Fusion instead of quietly building wrong geometry.
- The deployed `_shared` folder must be synchronized whenever the common source or any consuming script changes. `FIR_ModulePlate` retains its deployed workspace-loader wrapper; do not replace that wrapper with a stale copy.

## Current user decisions

- The brain PCB mounts inside the **small brain case**, not directly to `FIR_Shell` / the large top casing.
- The small brain case attaches directly to the current `FIR_Shell` deep top cap using four reinforced internal bosses at cap X = +/-58.5 and Y = -30/+50. Each cap boss is 9 mm OD x **10.8 mm** high with a 13 mm roof-root flange and a 2.6 mm pilot. The case is installed 10 mm toward cap +Y; its four symmetric local roof holes are `(-58.5,-40)`, `(58.5,-40)`, `(-58.5,40)`, `(58.5,40)`. This moves the formerly corner-adjacent pair 20 mm inward for easy screwdriver access. Use four low-profile M3 x 12 self-tapping screws from inside the empty case upward into the cap pilots: 3 mm through the case roof plus 9 mm thread engagement, leaving 1.8 mm at the end of the cap boss. The shorter hidden boss lifts the new 69.6 mm case to 1.1 mm over the MikroTik; no external ears are used.
- The deep top cap retains a continuous 3 mm roof.  Its brain-case boss flanges begin exactly at the roof's inside face, so they are fused into the roof rather than floating below it.  `FIR_ShellCheck` must mirror this same roof/boss stack.
- **Assembly order is mandatory:** (1) tighten the four case-to-cap screws upward from inside the empty brain case; (2) install and screw down the brain PCB; (3) install and secure the populated electronics tray from the open bottom; (4) assemble the cap/case onto the large shell.  Do not try to tighten the cap screws after the PCB is installed.
- **PCB orientation / vertical contract:** never edit the PCB itself.  Its populated silkscreen/component face points **DOWN** toward the ModulePlate; its bare solder-tail face points UP toward the small-case roof.  The measured face-to-face distance from the ModulePlate flat top at local Z = 3.0 mm to the PCB component face is **52.0 mm** (allowed inspection range 50.0–55.0 mm).  In `FIR_ModuleGadget`, the component face is Z = 55.0 mm and the solder face is Z = 56.6 mm.  `FIR_GadgetPlateCheck` must display and fail this contract if it goes outside the allowed range.
- **Three fastening systems — never interchange them:** (1) tray: four M3 self-tappers come from below through `FIR_ModulePlate` into the mid-edge, wall-embedded tray bosses; (2) PCB: four **M3 x 10** board screws enter upward from the open component-side bottom through the unchanged PCB holes and take 8.4 mm of grip in the short roof-post pilots; (3) case-to-cap: four low-profile M3 x 12 screws start inside the empty brain case, pass upward through roof clearance holes, and thread into the large top-cap bosses.
- The four PCB roof posts are internal-only reinforced structures above the bare solder side: 9 mm core, 13 mm roof collar, a 2.6 mm blind pilot matched to M3 x 10, and two 3 mm ribs per post.  The post zone is 10 mm high; collar and ribs overlap 0.5 mm into the roof for a true structural Fusion/print join, while preserving a 2.5 mm outer roof skin.  The ESP32/socket and other PCB component envelopes hang **DOWN** into the 52 mm plate-side gap.  These changes must never create exterior roof protrusions or alter the flat outer roof.
- The small case must retain a completely smooth outer silhouette: its four roof-mount holes use internal-only 9.5 mm load-spreading pads, embedded 0.5 mm into the roof for a true Fusion join. Their 6.4 mm internal counterbores and 3.4 mm M3 clearances start below the pad face, so all four holes are visibly open from the cavity to the outside. Never add rectangular ribs or other reinforcement that crosses the rounded exterior outline or creates corner tabs/protrusions.
- The ModulePlate is a **snug hand-push fit** in the 129 x 129 mm R9.5 Gadget pocket: tray outer dimensions are 128.3 x 128.3 mm with R9.15 corners, leaving a controlled 0.35 mm on each side/arc. This replaces the physically loose old 125 mm tray. Its 0.5 mm underside entry chamfer avoids elephant-foot jamming. The tray is seated on one continuous rounded internal ledge ring: outer 130 x 130 mm R10, inner 126.3 x 126.3 mm R8.15, maintaining 1 mm support under the plate and no exterior corner tabs.
- **Tray seating datum:** `FIR_ModulePlate` is local Z = 0..3 mm and its top face contacts the underside of the ModuleGadget ledges beginning at local Z = 3 mm. Do not translate the assembled plate upward by `PLATE_SEAT_Z`; that would overlap the ledges and tray-boss bases. `FIR_GadgetPlateCheck` is the dedicated actual-case + actual-plate inspection script.
- The four mid-edge `TRAY_MOUNT` posts are only for fixing the 128.3 x 128.3 electronics tray. They are reinforced 9 mm bosses with 11 mm feet, a clearly visible 4.6 mm entry mouth leading to a 2.6 mm threaded pilot, and 12 mm wall-embedded ribs; they are not top-shell mounts.
- The PCB J4 (TFT) and J5 (RC522) edge faces **+X**.
- The +X case wall has one uninterrupted **50 x 5 mm** J4/J5 Dupont-wire slot, centred at local Z = 29 mm (Z = 26.5..31.5): exactly halfway between the ModulePlate top at Z = 3 and the downward PCB component face at Z = 55. This gives the wires a straight drop before they turn outward. It has no decorative border, recess, `POWER` / `INTERNET` labels, divider, or LED holes.
- The dedicated BottomLid 10 mm power-cable pass-through and CurvedLid power notch share the X = +10 mm centreline.  This is a cable-route correction only; measured MikroTik, PoE, RJ45, jack, switch, and other port openings must not be changed unless the user explicitly requests it.
- **Confirmed PoE switch / long-port decision:** the actual switch is 82 mm face width x 52 mm depth x 23 mm height, retained at shell X = -85 with its front against the BottomLid.  Its five guessed individual openings are replaced only in `FIR_BottomLid` by one 68.8 x 11.5 mm rectangular service slot (the requested approximately 69 x 11.5): local centre X = +85, Y = 15.45; assembled centre X = -85, Z = 15.45.  The 68.8 mm value preserves the supplied 6.6 mm side lands exactly.  The slot lower edge is 3.2 mm above the switch base.  This makes the remaining top land 8.3 mm; do not silently change it to 7 mm without a new owner decision.  `FIR_Shell` and `FIR_ShellCheck` must keep the same 82 x 52 x 23 switch envelope and one long service envelope.  CurvedLid remains a separate cable-cover decision; do not turn its low cable notches into a 69 mm window unless explicitly requested.
- **Real alarm horn - now cut into the cap:** the supplied horn is treated as 104 mm body diameter x 102 mm external height, with a 69 mm mounting flange and an isosceles 3-hole pattern (38.5 mm base, 50 mm equal sides, measured 6 mm holes).  It cannot fit inside the tub behind the switch because it conflicts with the brain case and other hardware, so it mounts externally on the cap roof at assembled X = -96, Y = +28, roof Z = 120, apex pointing outboard (-X).  The three assembled bolt axes are (-123.088, 28), (-76.942, 8.75), and (-76.942, 47.25); it keeps a 4.5 mm gap behind the switch and a harmless 5 mm external body overhang.  `FIR_Shell.build_top_lid()` now cuts the real mount: three 6.5 mm through-holes, each with a 14 mm internal load-spreading pad 3.5 mm tall embedded 0.5 mm into the roof (6 mm of material at every bolt), plus a 12.5 mm PG7 cable-gland hole with a 24 mm internal pad at 43 mm radius toward the box back - under the 104 mm body but clear of the 69 mm flange, so the lead drops into free air beside the brain case.  **Through-bolt only** (bolt + washers + locknut from inside); never self-tap a 104 mm horn into a 3 mm printed roof.  **Print-flip gotcha:** the cap prints roof-down and is physically flipped left/right on assembly, so `FIR_Shell` mirrors the horn's assembled X exactly once when placing it - the four brain bosses never exposed this because their pattern is symmetric.
- **Confirmed Tenda switch DC jack:** 6 mm barrel jack on the switch's own right-hand end face (shell -X), centre 8.3 mm forward of its rear face.  Its height on that face is **not measured**; 11.5 mm above the switch base (mid-height) is an assumption and `FIR_ShellCheck` reports it as one every run.  The switch cradle's back side post on that end used to sit straight across the jack; it is now clipped to 8 mm tall so the plug corridor is clear.  It is clipped rather than windowed on purpose - a window through a 2.5 mm post leaves the material above it floating.  **Open decision:** that end face has only 11.0 mm of air to the side wall.  A straight barrel plug (~14 mm) will not fit; a right-angle plug (~10 mm) will.  Either use a right-angle DC plug or move the switch inboard, which also moves the BottomLid 68.8 mm slot.  If the jack is actually on the switch's other end, flip `POE_JACK_SIDE` in `FIR_Interface.py` to `+1.0` - everything else follows from that one constant.
- **Large-shell closure:** the 281 mm inner top cap slides over the 280 mm tub with 0.5 mm nominal side/back clearance and 15 mm vertical overlap. Three 20 x 2 x 2 mm crush ribs give 0.3 mm intended PETG interference; six external side M3 screws at Y = -75/0/+75 and Z = 72 lock the cap to the tub. This is a mechanical closure, not a gasketed/IP-rated seal.
- **Front closure:** the BottomLid closes the tub front and is held by six counterbored front M3 screws. The CurvedLid slides from the outside toward the tub over the two shelf rails (0.3 mm guide clearance), then its 249 x 1 x 0.7 mm tongue enters the BottomLid groove with print clearance. Two front M3 screws lock the CurvedLid; there is no snap/detent. The cap front wall intentionally has a 0.5 mm clearance seam above the lid/cover top.
- **Port handedness - resolved:** the BottomLid is a flat plate that is turned **over** onto the tub front, so its source +X becomes shell -X.  The CurvedLid is **not** turned over: it prints face-down and only tips up 90 degrees about X to slide onto the shelf, so its source +X stays shell +X.  The two parts therefore do not share a source frame, and CurvedLid's openings had been written in the BottomLid's mirrored one - every notch landed on the wrong device.  `FIR_CurvedLid` now carries them in true shell X (router notches +34.5..+90.5, switch notches -53..-117, power notch -10).  No notch size and no physical position changed; only the sign was corrected.  `FIR_ShellCheck.check_cover_handedness()` re-proves this every run by testing each notch against the real router/switch spans, so the fault cannot return silently.  `FIR_Assembly` is still a presentation-only reflected view and cannot prove cover orientation.
- `FIR_ShellCheck` is the **all-up inspection model only**, never a print source. It clears bodies named `CHECK: ALL-UP` before rebuilding the actual current tub/cap/front closure, actual brain case, actual tray, component-side-down PCB/module/connector envelopes, router, confirmed PoE switch and its DC jack/plug, extension/adapters, the bought horn over the mount the cap now really carries, and low-floor cable paths. It no longer holds its own copy of the tub or the deep cap - those duplicates were deleted, because a second definition of a printed part is exactly how this model drifts away from what actually prints. It also republishes `FIR_Shell`'s own build notes in its report, so a cradle feature the tub had to trim is visible to anyone running the all-up view instead of `FIR_Shell` directly. Its four PCB-screw and other driver-travel cylinders are inspection-only and hidden by default (`SHOW_DRIVER_ACCESS = False`); set it true only to inspect assembly access, never confuse those transparent separate guides with printed structure. It live-reloads current builders on every run rather than showing a cached older Gadget. It derives its case transform from the actual stack: `(X=0, Y=+10, Z=117 + CAP_LIFT - 10.8 - BODY_Z)`, currently Z = `36.6 + CAP_LIFT` mm. That preserves 1.1 mm clearance above the MikroTik and now 7.1 mm above the confirmed 23 mm-high PoE switch. Its visible mains warning is intentional: the old mains proxy intersected the brain case and must not be treated as a finished route.
- The small case visual direction is clean and minimal: soft corners, an uninterrupted flat top roof for a clean print finish, functional side vents, and the slim J4/J5 wire slot. Do not add top panels, display windows, rings, rails, logos, engravings, or decorative I/O trim unless the user explicitly asks.
- Set `SHOW_TRAY = True` in `FIR_ModuleGadget.py` only to inspect the transparent fit view; set it back to `False` for print export.
