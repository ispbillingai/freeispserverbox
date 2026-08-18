# Lid Fastening Debate

**FreeISP Server Box — how the three lids fasten, what has gone wrong, and the open
design arguments.** Written 18 Aug 2026 by the CAD-side AI, for review by a second AI
and by Francis (the owner). The goal is agreement, not defence: every point below states
the current design, the argument for it, its known weaknesses, and the alternatives that
were considered. Push back anywhere the reasoning is thin.

**To the reviewing AI:** please respond point-by-point (D1–D7), for each one saying
AGREE / DISAGREE / MODIFY with your reasoning, and propose concrete alternatives with
numbers — the constraints in §2 are what any proposal must survive. Vague advice
("consider snap fits") is not useful; "replace the 6 front screws with four 8 × 1.2 mm
cantilever snaps at X ±40/±120, because…" is.

---

## 1. The box in one minute

A wall-mounted, 3D-printed (PETG, FDM) enclosure, outside 280 × 280 × 120 mm, holding a
MikroTik router, a 5-port switch, a mains extension strip + 3 adapters, a 102 mm siren
horn, and a hanging ESP32 "brain" case. Coordinates: origin at footprint centre,
**+Y = front, +Z = up**, walls 3 mm.

It closes with **four printed parts around a tub**:

| Part | What it is | How it currently fastens |
|---|---|---|
| **Tub** | 280 × 280 × 80 open box, floor + 3 walls, front open | — |
| **Top cap** ("top lid") | Deep hat, 286 × 286, covers Z65–120, overlaps the tub walls 15 mm | 8 × M3 horizontally through the skirt into tub-wall bosses, plus 6 snap detents |
| **BottomLid** ("bottom one") | Flat 280 × 80 × 3 plate that IS the front port face; router/switch ports open through it | 6 × M3 from the front into tub bosses, counterbored |
| **CurvedLid** ("the lid at the tail") | 280 × 80 × 65 hood that slides over the port/cable area in front of the BottomLid | slides on rails, then 2 × M3 lock screws into BottomLid bosses |
| **WallPlate** (new) | 276 × ~70 × 9 plate screwed to the wall; the box hangs on it | box hangs on a 45° cleat; 2 × M4 lock screws driven from *inside* the box floor |

## 2. Constraints any proposal must survive

Non-negotiable (owner-measured or owner-decided):

1. All port positions in the BottomLid are **measured on the real hardware** and must not
   move (router jack/LEDs/5×RJ45; switch 68.8 × 11.5 slot).
2. **No sound vents, no gaskets, no port hood** — decided and already un-done once.
3. **Top-rain-tight**: nothing may open a path for water falling from above. That is why
   there are no screws through the cap roof.
4. The horn (X −124..−22, Z 9..111) and the hanging brain case (X −20..114) leave
   ~1–2 mm clearances near the cap; features inside the tub walls at Z66–78 exist
   already (bosses) and new internal geometry must dodge the same inventory.
5. Anti-theft matters: this box lives on customer premises. "Unscrew it and walk away"
   must at minimum require opening the box first.
6. FDM printability: tub prints upright, cap prints roof-down (and is **mirrored
   left/right when assembled** — a real trap), BottomLid prints flat, CurvedLid prints
   face-down (so its outer face cannot carry raised features).
7. Fasteners available: M3 and M4 self-tappers today; brass heat-set inserts are
   possible if we decide they're worth buying (see D2).

Negotiable: everything else, including the number of parts in the front stack, screw
counts, screw locations, and the entire wall-mount concept.

## 3. What has actually gone wrong (the honest history)

1. **Invisible fasteners.** Francis exported the model and could not find where the lids
   screw together. The screws existed — flush ⌀3.4 holes on a 286 mm face — which means
   in practice they did not: a fastening point you cannot see is not a fastening point.
   *Fixed on 17 Aug:* every outside screw now sits in a visible ⌀12 raised pad
   (counterbored, head sinks flush) or, on the face-down-printed cover, a ⌀10 dished
   recess.
2. **The back pair could never be driven.** Two cap screws were on the back wall — with
   the box hung on a wall there is 8 mm of air behind it. Moved to the side walls
   (now 4 per side at Y −118/−75/0/+75, all at Z72).
3. **The keyhole wall mount was inadequate** (2–3 kg box on two ⌀11 keyholes, and the
   wall-screw heads poked into the adapter bay). Replaced by the WallPlate — but see D5,
   because Francis looked at the new render and said *"the mount on the back is of no
   purpose, nothing is going to be fastened on that."*
4. **The inspection model is illegible.** The all-up view draws everything ~75%
   transparent. Seat pads seen through a transparent wall look like discs floating in
   space; the cleat rail hides behind the back wall; the wall-lock screws are invisible.
   So even correct geometry *reads* as broken. This is D6 — arguably the root cause of
   half the arguments we've had.

---

## 4. The discussion points

### D1 — Top cap ↔ tub: are 8 side screws + 6 snap detents the right closure?

**Current design.** The cap self-clicks: six stepped bumps on the tub's outer walls
snap into through-windows in the cap skirt (the cap holds itself, hands-free). Then
8 × M3 drive horizontally through visible seat pads into 12 mm wall bosses (4 per side
wall, none on the back or front). Opening = 8 screws + a firm lift.

**For it:** positive click for blind assembly (the brain case descends with 2 mm beside
the horn — you want both hands on the cap, not on screws); screws give the anti-pry,
anti-theft lock; all screws reachable with the box on the wall; nothing penetrates the
roof (rain).

**Weaknesses:** 8 screws is a lot of driving for routine service; the back edge has no
screws at all (2 detents + a crush rib only) — a determined pry at the back-centre works
against plastic spring, not steel; repeated M3-into-PETG wears (D2).

**Alternatives considered:** (a) detents only, no screws — rejected, trivially prya-ble,
no theft resistance; (b) 4 screws instead of 8 — plausible, halves service effort,
weakens clamping of the 286 mm span; (c) quarter-turn cam latches printed into the
skirt — tool-free, but tool-free is *wrong* here (anti-theft wants a tool); (d) one or
two **security screws** (Torx-pin) among the 8 — cheap upgrade, thief needs an uncommon
bit.

**My position:** keep 8 + detents; consider making the two rear screws (Y −118)
Torx-pin security screws. **Question to reviewer:** is the unscrewed back edge a real
pry weakness, and if so, what holds it without putting a screw where no driver reaches?

### D2 — Self-tappers vs heat-set inserts (decision pending with Francis)

Every closure screw currently self-taps into a 2.6 mm printed pilot. The cap and cover
will be opened repeatedly over the box's life; PETG threads strip after some tens of
cycles. Brass M3 heat-set inserts are the standard fix. The CAD is one flag away
(`HEAT_SET_INSERTS` converts every boss pilot to a 4.0 mm insert bore) — the cost is
buying inserts and seating ~16 of them with a soldering iron per box.

**My position:** inserts for the 8 cap screws and the 2 cover lock screws (opened
often); self-tap is fine for the 6 BottomLid screws and everything internal (opened
rarely). **Question:** agree with the split, or all-inserts / all-self-tap?

### D3 — The front stack: is BottomLid + CurvedLid one part too many?

**Current design.** The front is closed twice: the BottomLid is the structural port
face (6 screws, removed rarely — only to extract the router/switch), and the CurvedLid
is the service hood over the plugs and cable mess (slides + 2 screws, removed often).

**For it:** ports stay precisely located by a rigid screwed plate while the
frequently-opened part is a light hood with no precision job; cables exit under the
hood's bottom notches, keeping the rain story; the two parts print flat and face-down
respectively, both cleanly.

**Weaknesses:** it is the most complicated region of the box — plate + shelf + rails +
tongue + groove + the BottomLid's top-edge locating tabs + 8 screws across two parts
(correction from review: the *CurvedLid* itself has no snap/clip feature — only rails,
locator tongue and its two screws); most of the fit problems in this project's history
have been here; Francis has repeatedly found it confusing, and a confusing assembly is
a legitimate design defect, not a user error.

**Alternatives:** (a) **merge into one front door** — one 280 × 80 part carrying the
port openings *and* the hood, 4–6 screws total. Loses the "service the cables without
exposing the port plate" property, and any port-plate reprint now reprints the whole
front; (b) keep two parts but make the hood **hinge** on the shelf instead of sliding —
fewer alignment features, but a printed hinge is a wear part; (c) keep as-is and rely on
the new visible seats to make it legible.

**My position:** (c), weakly held. The two-part front earns its complexity *if* the
hood is truly opened often; if in practice Francis would service cables once a year,
(a) is honestly better. **Question to reviewer:** given the service pattern of an ISP
CPE box (cable changes ~monthly at worst, port plate essentially never), which wins?

### D4 — CurvedLid locking: 2 screws, or tool-free?

The hood slides on and locks with 2 × M3 into visible dished seats. Tool-free latches
would be nicer for monthly cable service — but the hood is also the easiest theft/tamper
entry (unplug everything), so it arguably *should* need a tool. **My position:** keep
the 2 screws; if D2 goes to inserts, these two are top candidates. **Question:** any
reason a service tech would need tool-free here that outweighs tamper resistance?

### D5 — The wall mount: justify it or redesign it

Francis's verdict on the render: *"the mount on the back is of no purpose, nothing is
going to be fastened on that."* Two readings, both worth answering:

**Reading 1 — it isn't legible.** What the render doesn't show: the tub's back wall now
carries a full-width 45° **cleat bar**; the box hangs on the plate's matching 45° face
and gravity wedges it flat against the plate (this is a French cleat — the standard way
to hang heavy cabinets); a crest wall means the box must *lift 4.4 mm* to come off; and
two **M4 screws driven downward from inside the box floor** into the plate's under-floor
arms block that lift. Once the cap is screwed on, those two screws are unreachable —
**the box cannot leave the wall without being opened first.** That is the entire
anti-theft mechanism, and it is invisible in a transparent render. Nothing on the back
face of the box gets a visible screw *by design* — visible wall fastening is exactly
what a thief unscrews.

**Reading 2 — Francis actually wants something else,** e.g. direct visible screws
through the box into the wall (simplest possible: 4 holes in the back wall, drive
anchors, done). That is stronger and simpler — but the screw heads then live inside the
box (the old adapter-bay interference problem), the box can never be removed without
emptying the back zone to reach them, and anyone with a screwdriver *and the cap key*
has the same access either way, so the theft story is equivalent only if the heads are
inside.

**My position:** the cleat + hidden-lock design is the right mechanism (hang-first
assembly, box removable in one minute by the owner, immovable by a thief), and the real
defect is presentation (D6) plus a missing explanation. But if Francis prefers
**direct through-the-back-wall screws into wall anchors** — 4 × ⌀5 at reachable spots,
heads inside the box, no separate plate to print — I will build that instead; it is a
legitimate, simpler answer as long as we accept "empty the back zone to un-mount".
**Question to reviewer:** cleat-and-lock vs direct through-wall screws, for a 2–3 kg
box on customer premises — which do you argue for, and why?

### D6 — The model must be able to show itself

Half of every argument so far traces to one fact: the inspection assembly draws
everything transparent, and transparent walls turn attached features into floating
ghosts. Proposal: add a **`PRESENTATION` mode** to `FIR_ShellCheck` — all shells fully
opaque, each part a distinct colour, every fastener drawn as a solid bright screw-proxy
in place, and an exploded-view offset option. Renders from that mode become the thing
Francis reviews; the transparent view stays for interference checking only.
**My position:** do this before any further geometry debate. **Question:** anything
else the review view needs to settle arguments (dimensions annotated on bodies? a
section cut?).

### D7 — Engagement numbers (for the record, so the reviewer can check the maths)

Cap M3: 6 mm bite into wall bosses at Z72. BottomLid M3: ~8 mm through-pilot bite (the
new deeper seat cost 1.1 mm). Cover M3: 8 mm boss pilots. Wall locks M4 × 10: 3 mm
floor + 6.6 mm bite, 1 mm of arm left below — never longer than M4 × 10. All screw
positions verified aligned through both assembly mirror-flips by
`tools/fusion_offline_check.py` (86 automated checks, run on the workspace and the
deployed tree).

---

## 5. Response format

Reviewer: answer D1–D6 (D7 is reference), each as **AGREE / DISAGREE / MODIFY +
reasoning + concrete numbers**. If you propose new geometry, state where it lives in
the coordinate frame of §1 and which §2 constraint it touches. Francis then picks the
winners, and the surviving decisions get built, verified offline, and re-rendered in
the D6 presentation view before he looks again.

---

## 6. AGREEMENT RECORD — settled 18 Aug 2026, round 2 (built and verified)

The reviewing AI responded twice; the following is the reconciled outcome, **already
implemented, offline-verified (106 checks, both trees) and deployed**:

1. **D1 (cap closure): AGREED as designed** — slide fit + snap-to-hold + 8 side
   screws; snaps position, screws carry load. Added from review: a **1.2 mm 45°
   lead-in chamfer** on the skirt's lower inner edge, and an **engraved arrow** inside
   the roof pointing at the front (a triangle survives the assembly mirror; text
   would not).
2. **D2 (inserts): AGREED, selective and per-closure** — the single global flag was
   replaced by `CAP_BOSS_INSERTS` / `COVER_LOCK_INSERTS` / `BOTTOM_LID_INSERTS`, all
   defaulting to 2.6 mm self-tap. The cover-lock boss was **widened 7 → 10 mm** and its
   screws moved **X ±125 → ±122** (clearing the cover channel rib at 129.1 by 2.1 mm)
   so it can take a real insert later. Per review: `M3_INSERT_BORE_D = 4.0` is a
   **placeholder** — set it from the bought insert's datasheet before flipping any
   flag. *Pending Francis: buy the inserts.*
3. **D3 (tongue): AGREED, reviewer's version** — the 249 mm tongue is replaced by
   **four 25 mm tabs at X −90/−30/+30/+90**, same 0.3 mm clearances. The `CLR = 0.4`
   vs hard-coded `0.3` conflict is dead: **one shared `COVER_RAIL_CLR = 0.3`** in the
   contract now drives the BottomLid rails, the CurvedLid channels and the coupons.
4. **D4 (cover lock): AGREED with additions** — 2 screws kept; the lock bosses now end
   **flush at the cover's inner face = a hard end stop** the screws clamp against, and
   each channel carries a **0.15 mm anti-rattle nub** that engages only over the last
   5 mm of travel.
5. **D5 (wall mount): AGREED, keep the cleat** — it is tamper-resistance, not
   vault-grade security; its job is "cannot be removed without first opening the box",
   which it does. Conditions adopted: wall anchors appropriate to the real wall, and a
   **9 kg / 24 h hang test** on a printed plate before deployment (box weighs 2–3 kg).
6. **D6 (legibility): BUILT** — `FIR_ShellCheck` now has `PRESENTATION = True`: all
   shells opaque + solid fastener markers; combine with `CAP_LIFT` / `COVER_TRAVEL`
   for an exploded view. Transparent stays for interference hunting only.
7. **Orientation (C): mechanically keyed, not just labeled** — a block on the
   BottomLid rail (shell +X) plus a matching relief in the cover's shell +X channel:
   the correct cover clears it by 2.5 mm; a reversed cover hits it and stands ~7 mm
   proud with its lock seats visibly open. The cap was already keyed by its short
   front wall; the BottomLid by its asymmetric ports.
8. **Coupons before any 280 mm print: BUILT as `FIR_FitCoupons`** — three pairs:
   full-perimeter cap/tub fit rings (the 281/280 slide + warp test), a 70 mm cap-wall
   section (detent click + seated screw), and a 65 mm rail-lock end slice (slide,
   flush stop, nub click, lock screw, and the flipped-cover refusal test). Pass
   criteria are in the script's popup. *Pending Francis: print them.*

Open items after this round: buy inserts → measure → set the bore → flip the two
flags; print the coupons; hang-test the wall plate at 9 kg/24 h; and the §6.3
measurements from HANDOVER.md (horn foot distance, switch jack height, adapter dims).
