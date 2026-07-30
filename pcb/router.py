"""Grid maze router for the FreeISP brain board.

Single copper layer, so most of the work is deciding what genuinely cannot be
routed in copper. Anything that can't becomes a wire link -- a track on B.Cu,
which on a home-etched board is an insulated wire soldered across the component
side. B.Cu is otherwise empty, so links always find a path.

Clearance is enforced by inflating every obstacle by
    my_half_width + clearance + obstacle_half_width
and blocking any grid cell whose centre falls inside. That is deliberately a
little conservative (oblong pads are treated as circles), which costs some
routing room but means KiCad's DRC agrees with us.
"""

import heapq

GRID = 0.5          # mm per cell
CLEAR = 0.6         # design clearance
EDGE_KEEPOUT = 0.8  # track centre must stay this far inside the board outline

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
TURN_COST = 2       # discourages staircases without forcing wide detours


class Obstacle:
    __slots__ = ("x", "y", "half", "net")

    def __init__(self, x, y, half, net):
        self.x, self.y, self.half, self.net = x, y, half, net


class Router:
    def __init__(self, width, height):
        self.w = int(width / GRID) + 1
        self.h = int(height / GRID) + 1
        self.width, self.height = width, height
        self.pad_obs = []     # circular obstacles from pads
        self.seg_obs = []     # (x1,y1,x2,y2,half,net) from tracks

    # ---------------------------------------------------------------- input
    def add_pad(self, x, y, half, net):
        self.pad_obs.append(Obstacle(x, y, half, net))

    def add_track(self, x1, y1, x2, y2, width, net):
        self.seg_obs.append((x1, y1, x2, y2, width / 2.0, net))

    # ------------------------------------------------------------ geometry
    @staticmethod
    def _seg_dist(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx, cy = x1 + t * dx, y1 + t * dy
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    def _blocked_mask(self, net, half):
        """Cells this net may not occupy, given its own track half-width."""
        blocked = bytearray(self.w * self.h)

        def stamp(cx, cy, radius):
            i0 = max(0, int((cx - radius) / GRID))
            i1 = min(self.w - 1, int((cx + radius) / GRID) + 1)
            j0 = max(0, int((cy - radius) / GRID))
            j1 = min(self.h - 1, int((cy + radius) / GRID) + 1)
            r2 = radius * radius
            for i in range(i0, i1 + 1):
                px = i * GRID
                for j in range(j0, j1 + 1):
                    py = j * GRID
                    if (px - cx) ** 2 + (py - cy) ** 2 <= r2:
                        blocked[j * self.w + i] = 1

        for ob in self.pad_obs:
            if ob.net == net:
                continue
            stamp(ob.x, ob.y, half + CLEAR + ob.half)

        for x1, y1, x2, y2, ohalf, onet in self.seg_obs:
            if onet == net:
                continue
            radius = half + CLEAR + ohalf
            i0 = max(0, int((min(x1, x2) - radius) / GRID))
            i1 = min(self.w - 1, int((max(x1, x2) + radius) / GRID) + 1)
            j0 = max(0, int((min(y1, y2) - radius) / GRID))
            j1 = min(self.h - 1, int((max(y1, y2) + radius) / GRID) + 1)
            for i in range(i0, i1 + 1):
                px = i * GRID
                for j in range(j0, j1 + 1):
                    py = j * GRID
                    if self._seg_dist(px, py, x1, y1, x2, y2) <= radius:
                        blocked[j * self.w + i] = 1

        # board edge
        for i in range(self.w):
            px = i * GRID
            for j in range(self.h):
                py = j * GRID
                if (px < EDGE_KEEPOUT or py < EDGE_KEEPOUT
                        or px > self.width - EDGE_KEEPOUT
                        or py > self.height - EDGE_KEEPOUT):
                    blocked[j * self.w + i] = 1
        return blocked

    # ------------------------------------------------------------- routing
    def _cell(self, x, y):
        return (max(0, min(self.w - 1, int(round(x / GRID)))),
                max(0, min(self.h - 1, int(round(y / GRID)))))

    def route(self, net, a, b, half):
        """Dijkstra with a turn penalty. Returns a list of (x,y) or None."""
        blocked = self._blocked_mask(net, half)
        si, sj = self._cell(*a)
        ti, tj = self._cell(*b)

        # the pads themselves sit inside their own keepout; free the endpoints
        for ci, cj in ((si, sj), (ti, tj)):
            for di in range(-1, 2):
                for dj in range(-1, 2):
                    i, j = ci + di, cj + dj
                    if 0 <= i < self.w and 0 <= j < self.h:
                        blocked[j * self.w + i] = 0

        start = (si, sj, -1)
        dist = {start: 0}
        prev = {}
        pq = [(0, start)]
        goal = None

        while pq:
            d, cur = heapq.heappop(pq)
            if d > dist.get(cur, 1 << 30):
                continue
            i, j, pd = cur
            if (i, j) == (ti, tj):
                goal = cur
                break
            for k, (di, dj) in enumerate(DIRS):
                ni, nj = i + di, j + dj
                if not (0 <= ni < self.w and 0 <= nj < self.h):
                    continue
                if blocked[nj * self.w + ni]:
                    continue
                nd = d + 1 + (TURN_COST if pd != -1 and pd != k else 0)
                nxt = (ni, nj, k)
                if nd < dist.get(nxt, 1 << 30):
                    dist[nxt] = nd
                    prev[nxt] = cur
                    heapq.heappush(pq, (nd, nxt))

        if goal is None:
            return None

        path = []
        cur = goal
        while cur in prev:
            path.append((cur[0] * GRID, cur[1] * GRID))
            cur = prev[cur]
        path.append((cur[0] * GRID, cur[1] * GRID))
        path.reverse()

        # land exactly on the pad centres
        path[0] = a
        path[-1] = b
        return simplify(path)


def simplify(path):
    """Drop collinear intermediate points."""
    if len(path) < 3:
        return path
    out = [path[0]]
    for i in range(1, len(path) - 1):
        ax, ay = out[-1]
        bx, by = path[i]
        cx, cy = path[i + 1]
        if (bx - ax) * (cy - by) != (by - ay) * (cx - bx):
            out.append(path[i])
    out.append(path[-1])
    return out


def mst_edges(points):
    """Prim's minimum spanning tree over a net's pads."""
    if len(points) < 2:
        return []
    inside = [0]
    outside = list(range(1, len(points)))
    edges = []
    while outside:
        best = None
        for i in inside:
            for j in outside:
                d = ((points[i][0] - points[j][0]) ** 2
                     + (points[i][1] - points[j][1]) ** 2)
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        edges.append((i, j))
        inside.append(j)
        outside.remove(j)
    return edges
