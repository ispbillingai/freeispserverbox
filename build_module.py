#!/usr/bin/env python3
"""
FREEISPRADIUS smart-module box generator.
Builds: base tray (with board standoffs), screw-down lid = front faceplate
(screen window, 2 LED holes, RFID tap recess), mounting ears, cable gland hole.
Exports STL parts + an assembled preview render.
"""
import numpy as np
import trimesh
from trimesh.creation import box as Box
from trimesh.creation import cylinder as Cyl

# ---------------- PARAMETERS (mm) ----------------
IN_X, IN_Y, IN_Z = 120.0, 90.0, 45.0     # interior
WALL = 2.5
LID_TH = 3.0
BASE_TH = 3.0
OUT_X = IN_X + 2*WALL
OUT_Y = IN_Y + 2*WALL
OUT_Z = IN_Z + BASE_TH                     # base height (lid sits on top)

# front faceplate features (on the LID)
SCREEN_W, SCREEN_H = 30.0, 24.0            # visible window
LED_D = 5.2
TAP_D = 40.0                               # RFID tap recess
TAP_RECESS = 1.0                           # thin remaining wall (reads through)

M3 = 3.2                                   # clearance
BOSS_D = 7.0

def tube(outer_d, inner_d, h):
    o = Cyl(radius=outer_d/2, height=h, sections=48)
    i = Cyl(radius=inner_d/2, height=h+1, sections=48)
    return o.difference(i)

def move(m, x, y, z):
    m = m.copy(); m.apply_translation([x, y, z]); return m

# ---------------- BASE (open-top tray) ----------------
outer = Box([OUT_X, OUT_Y, OUT_Z]); outer.apply_translation([0,0,OUT_Z/2])
cav = Box([IN_X, IN_Y, IN_Z+1]); cav.apply_translation([0,0,BASE_TH+(IN_Z+1)/2])
base = outer.difference(cav)

# corner screw bosses (for the lid screws) - rise full interior height
boss_positions = [(-(IN_X/2-6), -(IN_Y/2-6)),
                  ( (IN_X/2-6), -(IN_Y/2-6)),
                  (-(IN_X/2-6),  (IN_Y/2-6)),
                  ( (IN_X/2-6),  (IN_Y/2-6))]
for (bx,by) in boss_positions:
    b = tube(BOSS_D, M3-0.6, IN_Z)          # pilot hole for self-tapping M3
    base = base.union(move(b, bx, by, BASE_TH + IN_Z/2))

# board standoffs on the floor (lift boards off base)
def standoff(x,y,h=4,hole=2.6):
    s = tube(6, hole, h)
    return move(s, x, y, BASE_TH + h/2)
# ESP32-S3 (70x26) - 4 standoffs
for dx in (-32,32):
    for dy in (-10,10):
        base = base.union(standoff(-25+dx*0, 0, 4))  # placeholder cluster
# simpler: explicit standoff clusters for clarity
clusters = {
    "ESP32":  [(-50,-10),(-50,10),(8,-10),(8,10)],
    "BUCK":   [(30,-30),(30,-8)],
    "BATT":   [(35,28),(-5,28)],
}
for pts in clusters.values():
    for (x,y) in pts:
        base = base.union(standoff(x,y,4))

# mounting ears (to bolt module into the big server box)
def ear(side):
    e = Box([18,14,4]); 
    e = move(e, side*(OUT_X/2+6), 0, 2)
    hole = Cyl(radius=2.1, height=10, sections=24); hole=move(hole, side*(OUT_X/2+9),0,2)
    return e.difference(hole)
base = base.union(ear(1)).union(ear(-1))

# cable gland hole on the back wall (one bundle out)
gland = Cyl(radius=6, height=WALL*4, sections=48)
gland.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0]))
gland = move(gland, 0, -OUT_Y/2, BASE_TH+12)
base = base.difference(gland)

base.export("/home/claude/work/fir_module_base.stl")

# ---------------- LID = FRONT FACEPLATE ----------------
lid = Box([OUT_X, OUT_Y, LID_TH]); lid.apply_translation([0,0,LID_TH/2])

# screen window (through hole)
win = Box([SCREEN_W, SCREEN_H, LID_TH+2]); win=move(win,-22,12,LID_TH/2)
lid = lid.difference(win)
# 2 LED holes
lid = lid.difference(move(Cyl(radius=LED_D/2,height=LID_TH+2,sections=32), -38,-22,LID_TH/2))
lid = lid.difference(move(Cyl(radius=LED_D/2,height=LID_TH+2,sections=32), -18,-22,LID_TH/2))
# RFID tap recess (blind pocket -> thin wall remains so it reads through)
pocket = Cyl(radius=TAP_D/2, height=LID_TH-TAP_RECESS, sections=64)
pocket = move(pocket, 30, 5, (LID_TH-TAP_RECESS)/2 + TAP_RECESS)
lid = lid.difference(pocket)
# 4 corner screw holes matching bosses
for (bx,by) in boss_positions:
    lid = lid.difference(move(Cyl(radius=M3/2,height=LID_TH+2,sections=24), bx,by,LID_TH/2))

lid.export("/home/claude/work/fir_module_lid.stl")

# ---------------- ASSEMBLED PREVIEW ----------------
scene = trimesh.Scene()
base.visual.face_colors = [60,60,70,255]
lid_show = move(lid, 0,0, OUT_Z + 18)        # float lid above for exploded view
lid_show.visual.face_colors = [150,170,200,255]
scene.add_geometry(base)
scene.add_geometry(lid_show)

for ang,name in [((30,0,40),"iso"),((75,0,15),"top"),((10,0,90),"front")]:
    pass

# render
import math
def render(scene, fname, angles):
    scene.set_camera(angles=angles, distance=300, center=[0,0,OUT_Z/2])
    png = scene.save_image(resolution=(1400,1000), visible=True)
    open(fname,'wb').write(png)

try:
    render(scene, "/home/claude/work/fir_iso.png",  (math.radians(60),0,math.radians(35)))
    print("rendered iso")
except Exception as e:
    print("render failed:", e)

print("base verts:", len(base.vertices), "watertight:", base.is_watertight)
print("lid  verts:", len(lid.vertices),  "watertight:", lid.is_watertight)
