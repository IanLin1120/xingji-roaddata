#!/usr/bin/env python3
"""行跡導航「實境 3D」圖資產生器
讀 OpenStreetMap 台灣資料 + 地形高程圖磚(Terrarium PNG),替每個 0.01° 小格(約 1 公里)整理出:
  e  地形高程:25×25 網格(含邊界,每 0.01/24°),單位 0.25 公尺,差分後用 polyline 字元編碼
  w  道路 / 人行道 / 階梯 / 鐵路:[id, 種類, 座標(polyline 6 位), 標籤, 高度(選填)]
       高度只給橋、高架、隧道、地下道和接上去的階梯:每個點的絕對高度(公分),polyline 字元編碼
       高度由「上下第幾層 + 地形 + 最大坡度」整個路網一起算:引道、匝道從地面依坡度爬升到高架,地下道往下降
  b  建築:[外框(polyline 5 位), 高度(公寸), 底高(公寸)]
  a  水域、綠地:[種類, 外框(polyline 5 位)...]
  n  斑馬線、紅綠燈:[lat, lon, 種類]
每 0.1° 打包成一個 gzip 文字檔:每行「格子代碼<TAB>JSON」,和 App 的離線道路資料包同一種格式。
用法: python3 real.py taiwan.osm.pbf terrarium_dir out/ [z]
"""
import sys, os, re, json, gzip, math, time, heapq
import osmium
from PIL import Image

G = 0.01        # 小格
P = 0.1         # 打包
EN = 24         # 每格地形切幾等分
TZ = 13         # 地形圖磚縮放等級

def encv(vals):
    """一串整數 → polyline 字元(差分)"""
    o = []; p = 0
    for v in vals:
        d = v - p; p = v
        d = ~(d << 1) if d < 0 else (d << 1)
        while d >= 32: o.append(chr((32 | (d & 31)) + 63)); d >>= 5
        o.append(chr(d + 63))
    return ''.join(o)

def enc(pts, prec):
    f = 10 ** prec; o = []; pl = pn = 0
    def e(v):
        v = ~(v << 1) if v < 0 else (v << 1); s = []
        while v >= 32: s.append(chr((32 | (v & 31)) + 63)); v >>= 5
        s.append(chr(v + 63)); return ''.join(s)
    for a, b in pts:
        la = int(math.floor(a * f + 0.5)); lo = int(math.floor(b * f + 0.5))
        o.append(e(la - pl)); o.append(e(lo - pn)); pl, pn = la, lo
    return ''.join(o)

def ckey(lat, lon): return (math.floor(lat / G + 1e-9), math.floor(lon / G + 1e-9))
def dist(a, b):
    return math.hypot((a[0] - b[0]) * 110950, (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0])))

# ---------- 地形 ----------
class Terrain:
    def __init__(self, d):
        self.d = d; self.tiles = {}
    def tile(self, x, y):
        k = (x, y)
        if k not in self.tiles:
            fn = os.path.join(self.d, f'{TZ}_{x}_{y}.png')
            if not os.path.exists(fn) and os.environ.get('TERR_DL'):
                import urllib.request
                for _ in range(4):
                    try: urllib.request.urlretrieve(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{TZ}/{x}/{y}.png', fn + '.tmp'); os.replace(fn + '.tmp', fn); break
                    except Exception as e: time.sleep(2)
            if os.path.exists(fn):
                im = Image.open(fn).convert('RGB'); self.tiles[k] = im.load()
            else: self.tiles[k] = None
        return self.tiles[k]
    def px(self, lat, lon):
        n = 2 ** TZ; x = (lon + 180) / 360 * n; y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        return x * 256, y * 256
    def raw(self, X, Y):
        tx, ty = int(X // 256), int(Y // 256); t = self.tile(tx, ty)
        if t is None: return 0.0
        r, g, b = t[int(X) - tx * 256, int(Y) - ty * 256]
        return (r * 256 + g + b / 256) - 32768
    def at(self, lat, lon):
        X, Y = self.px(lat, lon); X -= .5; Y -= .5; x0, y0 = math.floor(X), math.floor(Y); fx, fy = X - x0, Y - y0
        v = (self.raw(x0, y0) * (1 - fx) * (1 - fy) + self.raw(x0 + 1, y0) * fx * (1 - fy) + self.raw(x0, y0 + 1) * (1 - fx) * fy + self.raw(x0 + 1, y0 + 1) * fx * fy)
        return max(-3.0, v)  # 海面以下(海床)一律當成海平面附近

class Grid:
    """每格 25×25 網格(和 App 一樣用雙線性內插),所有高度都從這裡取,App 畫出來才會一致"""
    def __init__(self, T): self.T = T; self.c = {}
    def cell(self, k):
        g = self.c.get(k)
        if g is None:
            a, b = k; g = [[round(self.T.at((a + i / EN) * G, (b + j / EN) * G) * 4) / 4 for j in range(EN + 1)] for i in range(EN + 1)]
            self.c[k] = g
        return g
    def at(self, lat, lon):
        k = ckey(lat, lon); g = self.cell(k)
        fi = (lat / G - k[0]) * EN; fj = (lon / G - k[1]) * EN
        i = min(EN - 1, max(0, int(fi))); j = min(EN - 1, max(0, int(fj))); u = fi - i; v = fj - j
        # 和 App 畫地形的三角形一致:(i,j)-(i,j+1)-(i+1,j+1) 與 (i,j)-(i+1,j+1)-(i+1,j)
        A = g[i][j]; B = g[i][j + 1]; Cc = g[i + 1][j + 1]; D = g[i + 1][j]
        if v >= u: return A + v * (B - A) + u * (Cc - B)
        return A + u * (D - A) + v * (Cc - D)

# ---------- OSM ----------
ROAD = re.compile(r'^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|living_street|service|track|road|busway|pedestrian|footway|path|cycleway|steps|corridor|bridleway)$')
RAIL = re.compile(r'^(rail|light_rail|subway|narrow_gauge|monorail|tram|funicular)$')
KEEP = ['highway', 'railway', 'name', 'ref', 'lanes', 'lanes:forward', 'lanes:backward', 'oneway', 'width', 'bridge', 'tunnel', 'layer', 'level',
        'sidewalk', 'sidewalk:both', 'sidewalk:left', 'sidewalk:right', 'footway', 'cycleway', 'cycleway:both', 'cycleway:left', 'cycleway:right',
        'turn:lanes', 'turn:lanes:forward', 'turn:lanes:backward', 'junction', 'service', 'highspeed', 'usage', 'covered', 'surface',
        'motorcycle:lanes', 'placement', 'embankment', 'cutting', 'maxheight', 'electrified', 'gauge', 'motorroad', 'area', 'indoor']
WATERW = re.compile(r'^(river|stream|canal|drain|ditch)$')

def lvl(t):
    try: return int(float(t.get('layer', '0').split(';')[0]))
    except Exception: return 0
def isyes(v): return v is not None and v not in ('no', 'false', '0')

class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []          # (id, kind, refs, coords, tags)
        self.wl = []            # 水道中心線(判斷橋是不是跨河)
        self.bld = []           # (coords, h, mh, centroid)
        self.areas = []          # (kind, rings)
        self.nodes = []         # crossing / signals
    def node(self, n):
        t = n.tags; hw = t.get('highway')
        if hw == 'traffic_signals': self.nodes.append((n.location.lat, n.location.lon, 's'))
        elif hw == 'crossing' or t.get('railway') == 'crossing':
            cr = t.get('crossing', ''); m = t.get('crossing:markings', '')
            if cr in ('zebra', 'marked', 'traffic_signals', 'uncontrolled') or (m and m != 'no'): self.nodes.append((n.location.lat, n.location.lon, 'z'))
        elif t.get('railway') == 'level_crossing': self.nodes.append((n.location.lat, n.location.lon, 'x'))
        elif t.get('natural') == 'tree': self.nodes.append((n.location.lat, n.location.lon, 't'))       # v3 行道樹
        elif hw == 'street_lamp': self.nodes.append((n.location.lat, n.location.lon, 'l'))               # v3 路燈
    def way(self, w):
        t = w.tags; hw = t.get('highway'); rw = t.get('railway')
        kind = None
        if hw and ROAD.match(hw) and t.get('area') != 'yes' and t.get('indoor') != 'yes': kind = 'h'
        elif rw and RAIL.match(rw): kind = 'r'
        elif rw == 'platform': kind = 'p'
        if t.get('natural') == 'tree_row':     # v3 一排樹:每 8 公尺一棵
            try:
                g = [(nd.location.lat, nd.location.lon) for nd in w.nodes]
                for i in range(1, len(g)):
                    L = dist(g[i - 1], g[i]); n = max(1, int(L // 8))
                    for k in range(n): f = k / n; self.nodes.append((g[i - 1][0] + (g[i][0] - g[i - 1][0]) * f, g[i - 1][1] + (g[i][1] - g[i - 1][1]) * f, 't'))
            except osmium.InvalidLocationError: pass
        ww = t.get('waterway')
        if ww and WATERW.match(ww):
            try: self.wl.append([(nd.location.lat, nd.location.lon) for nd in w.nodes])
            except osmium.InvalidLocationError: pass
        if not kind: return
        if hw in ('proposed', 'construction'): return
        try: g = [(nd.location.lat, nd.location.lon) for nd in w.nodes]
        except osmium.InvalidLocationError: return
        if len(g) < 2: return
        tg = {k: t[k] for k in KEEP if k in t}
        self.ways.append((w.id, kind, [nd.ref for nd in w.nodes], g, tg))
    def area(self, a):
        t = a.tags
        if 'building' in t or 'building:part' in t:
            if t.get('building') in ('no',): return
            try:
                rings = [[(n.lat, n.lon) for n in r] for r in a.outer_rings()]
            except Exception: return
            for g in rings:
                if len(g) < 4: continue
                h = None; mh = 0.0
                try: h = float(re.sub(r'[^\d.]', '', t.get('height', '')) or 'x')
                except Exception: h = None
                if h is None:
                    try: h = float(t.get('building:levels')) * 3.2 + (0.6 if 'building' in t else 0)
                    except Exception: h = None
                try: mh = float(re.sub(r'[^\d.]', '', t.get('min_height', '')) or 'x')
                except Exception:
                    try: mh = float(t.get('building:min_level')) * 3.2
                    except Exception: mh = 0.0
                if h is None:
                    b = t.get('building', 'yes')
                    h = {'roof': 4.5, 'garage': 3, 'shed': 3, 'hut': 3, 'carport': 3, 'kiosk': 3, 'toilets': 3.5, 'industrial': 9, 'warehouse': 9,
                         'factory': 10, 'apartments': 16, 'commercial': 12, 'retail': 8, 'school': 13, 'hospital': 20, 'temple': 8, 'house': 9.6,
                         'detached': 9.6, 'terrace': 12.8, 'residential': 12.8, 'train_station': 10, 'transportation': 8, 'church': 10}.get(b, 9.6)
                lat = sum(p[0] for p in g) / len(g); lon = sum(p[1] for p in g) / len(g)
                self.bld.append((g, h, mh, (lat, lon), 1 if t.get('building') == 'roof' else 0))
            return
        kind = None
        if t.get('natural') == 'water' or t.get('waterway') in ('riverbank', 'dock') or t.get('landuse') in ('reservoir', 'basin'): kind = 'w'
        elif t.get('landuse') in ('farmland', 'orchard', 'allotments', 'farmyard'): kind = 'f'
        elif t.get('leisure') in ('park', 'garden', 'pitch', 'golf_course') or t.get('landuse') in ('grass', 'meadow', 'recreation_ground', 'village_green', 'forest', 'cemetery') or t.get('natural') in ('wood', 'scrub', 'grassland'): kind = 'g'
        elif t.get('highway') in ('pedestrian', 'footway') or t.get('area:highway'): kind = 'p'
        elif t.get('landuse') in ('residential', 'commercial', 'retail'): kind = 'u'     # 住商區(App 用來補畫沿街的房子)
        elif t.get('landuse') == 'industrial': kind = 'i'
        if not kind: return
        try:
            rings = [[(n.lat, n.lon) for n in r] for r in a.outer_rings()]
            inner = [[(n.lat, n.lon) for n in ir] for r in a.outer_rings() for ir in a.inner_rings(r)]
        except Exception: return
        self.areas.append((kind, rings, inner))

# ---------- 線段交叉(判斷橋/地下道有沒有跨過其他道路) ----------
def seg_x(p1, p2, q1, q2):
    def o(a, b, c): return (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1])
    d1 = o(q1, q2, p1); d2 = o(q1, q2, p2); d3 = o(p1, p2, q1); d4 = o(p1, p2, q2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

class SegIdx:
    S = 0.002
    def __init__(self, only=None): self.g = {}; self.only = only
    def add(self, wid, g, lv):
        for i in range(len(g) - 1):
            a, b = g[i], g[i + 1]
            for k in self.keys(a, b):
                if self.only is None or k in self.only: self.g.setdefault(k, []).append((wid, a, b, lv))
    def keys(self, a, b):
        S = self.S; i0, i1 = sorted((math.floor(a[0] / S), math.floor(b[0] / S))); j0, j1 = sorted((math.floor(a[1] / S), math.floor(b[1] / S)))
        return [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]
    def crossings(self, wid, g, test):
        """回傳 [(線段索引, 線段上的位置 0~1)]"""
        out = []
        for i in range(len(g) - 1):
            a, b = g[i], g[i + 1]; seen = set()
            for k in self.keys(a, b):
                for (w2, c, d, lv) in self.g.get(k, ()):
                    if w2 == wid or not test(lv) or (w2, c) in seen: continue
                    if seg_x(a, b, c, d):
                        seen.add((w2, c))
                        # 交點位置
                        x1, y1, x2, y2, x3, y3, x4, y4 = a[0], a[1], b[0], b[1], c[0], c[1], d[0], d[1]
                        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
                        if den: out.append((i, ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den))
        return out
    def cross(self, wid, g, test):
        for i in range(len(g) - 1):
            a, b = g[i], g[i + 1]
            for k in self.keys(a, b):
                for (w2, c, d, lv) in self.g.get(k, ()):
                    if w2 != wid and test(lv) and seg_x(a, b, c, d): return True
        return False

GRADE = {'motorway': .05, 'motorway_link': .055, 'trunk': .05, 'trunk_link': .06, 'steps': .75, 'footway': .1, 'path': .12, 'cycleway': .08, 'pedestrian': .1, 'corridor': .12}
RGRADE = {'rail': .03, 'narrow_gauge': .035, 'subway': .04, 'light_rail': .05, 'monorail': .06, 'tram': .06, 'funicular': .5}

def main():
    src, tdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True); t0 = time.time()
    h = H(); h.apply_file(src, locations=True, idx='flex_mem')
    print('osm', len(h.ways), 'ways', len(h.bld), 'buildings', len(h.areas), 'areas', f'{time.time()-t0:.0f}s', flush=True)
    E = Grid(Terrain(tdir))
    if os.environ.get('TERR_DL'):
        # 先把用得到的地形圖磚平行下載好(全台約幾千張)
        need = set()
        def addc(lat, lon):
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    a, b = math.floor(lat / G) + da, math.floor(lon / G) + db
                    for (la, lo) in ((a * G, b * G), ((a + 1) * G, (b + 1) * G), (a * G, (b + 1) * G), ((a + 1) * G, b * G)):
                        X, Y = E.T.px(la, lo); need.add((int(X // 256), int(Y // 256)))
        seen = set()
        for (wid, kind, refs, g, tg) in h.ways:
            for p in g[::4] + [g[-1]]:
                k = ckey(*p)
                if k not in seen: seen.add(k); addc(*p)
        for b in h.bld:
            k = ckey(*b[3])
            if k not in seen: seen.add(k); addc(*b[3])
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(32) as ex: list(ex.map(lambda t: E.T.tile(*t), sorted(need)))
        E.T.tiles = {}
        print('terrain tiles', len(need), f'{time.time()-t0:.0f}s', flush=True)

    # ---- 結構分類 ----
    # s: 0 地面 1 往上(橋/高架) -1 往下(隧道/地下道) 2 自由(階梯、接橋的坡道:高度由兩端決定)
    W = []
    for (wid, kind, refs, g, tg) in h.ways:
        L = lvl(tg); br = isyes(tg.get('bridge')); tn = isyes(tg.get('tunnel')) or (tg.get('covered') == 'yes' and L < 0)
        if br: s, L = 1, max(1, L)
        elif tn or L < 0: s, L = -1, min(-1, L)
        elif tg.get('highway') == 'steps': s = 2
        else: s = 0
        W.append([wid, kind, refs, g, tg, s, L])
    h.ways = None
    # 只替橋/隧道附近建線段索引(全台灣的線段太多,記憶體會不夠)
    SK = set(); sn = set(); tmp = SegIdx()
    for w in W:
        if w[5] != 0:
            sn.update(w[2])
            for i in range(len(w[3]) - 1): SK.update(tmp.keys(w[3][i], w[3][i + 1]))
    idx = SegIdx(SK)
    for w in W:
        if w[1] in ('h', 'r') and w[4].get('highway') not in ('steps', 'corridor'): idx.add(w[0], w[3], w[6] if w[5] != 0 else 0)
    for i, g in enumerate(h.wl): idx.add(-1 - i, g, -99)   # 河流
    h.wl = None
    # ---- 高度:「需求點」往外依坡度遞減(像帳篷),碰到地面為止 ----
    # 高架/陸橋:跨過其他道路、鐵路的地方需要離地 6.8 公尺(人行天橋 6 公尺),連續 250 公尺以上的高架整段都要;
    # 地下道:穿過其他道路、鐵路的地方要低於地面 5.6 公尺;山區隧道沿兩端洞口連線。
    # 需求往外沿路網依坡度(一般道路 6%、國道 5%、鐵路 3%)遞減,所以沒標成橋的引道、匝道也會跟著爬升或下降。
    def wlen(g): return sum(dist(g[i - 1], g[i]) for i in range(1, len(g)))
    # 同一層、相連的橋(或隧道)串成一串,算總長
    par = {}
    def fd(x):
        while par.get(x, x) != x: par[x] = par.get(par[x], par[x]); x = par[x]
        return x
    nw = {}
    for i, w in enumerate(W):
        if w[5] in (1, -1):
            for r in w[2]: nw.setdefault((r, w[5], w[6]), []).append(i)
    for v in nw.values():
        for i in v[1:]: par[fd(i)] = fd(v[0])
    chain = {}
    for i, w in enumerate(W):
        if w[5] in (1, -1): r = fd(i); chain[r] = chain.get(r, 0) + wlen(w[3])
    REQ_UP = {}; REQ_DN = {}
    def req(D, r, v, up):
        o = D.get(r)
        if o is None or (v > o if up else v < o): D[r] = v
    for i, w in enumerate(W):
        wid, kind, refs, g, tg, s, L = w
        if s not in (1, -1): continue
        hw = tg.get('highway'); rw = tg.get('railway'); foot = hw in ('footway', 'path', 'cycleway', 'pedestrian', 'steps', 'corridor')
        gr = RGRADE.get(rw, .03) if kind == 'r' else GRADE.get(hw, .06)
        cum = [0.0]
        for k in range(1, len(g)): cum.append(cum[-1] + dist(g[k - 1], g[k]))
        e0, e1 = E.at(*g[0]), E.at(*g[-1]); Lt = cum[-1] or 1
        lin = [e0 + (e1 - e0) * cum[k] / Lt for k in range(len(g))]
        longc = chain.get(fd(i), 0) > 250
        if s == 1:
            off = ((6.0 if foot else 6.8) + 6.8 * (L - 1))
            if kind == 'r' and tg.get('highspeed') == 'yes': off = max(off, 9.0)
            xs = idx.crossings(wid, g, lambda lv, L=L: lv != -99 and lv < L)
            rv = idx.cross(wid, g, lambda lv: lv == -99)
            for k, r in enumerate(refs):   # 橋面本身至少比地面(或兩端連線)高一點
                req(REQ_UP, r, max(E.at(*g[k]), lin[k]) + (off if longc and xs else (2.0 if rv else 1.0)), True)
            for (k, f) in xs:                # 跨越點:前後兩個點依距離扣掉坡度
                p = (g[k][0] + (g[k + 1][0] - g[k][0]) * f, g[k][1] + (g[k + 1][1] - g[k][1]) * f); need = E.at(*p) + off
                d0 = (cum[k + 1] - cum[k]) * f; d1 = (cum[k + 1] - cum[k]) * (1 - f)
                req(REQ_UP, refs[k], need - gr * d0, True); req(REQ_UP, refs[k + 1], need - gr * d1, True)
        else:
            xs = idx.crossings(wid, g, lambda lv, L=L: lv != -99 and lv > L)
            dep = (4.2 if foot else 5.6) * (-L)
            if kind == 'r' and rw == 'subway': dep = 12 * (-L)
            for k, r in enumerate(refs):
                ge = E.at(*g[k])
                if xs or (kind == 'r' and rw == 'subway') or longc and ge - lin[k] < 3: v = min(ge, lin[k]) - (dep if (longc or rw == 'subway') else 0.5)
                else: v = min(lin[k], ge - 0.5)          # 山區隧道:兩端洞口連線
                req(REQ_DN, r, v, False)
            for (k, f) in xs:
                p = (g[k][0] + (g[k + 1][0] - g[k][0]) * f, g[k][1] + (g[k + 1][1] - g[k][1]) * f); need = E.at(*p) - dep
                d0 = (cum[k + 1] - cum[k]) * f; d1 = (cum[k + 1] - cum[k]) * (1 - f)
                req(REQ_DN, refs[k], need + gr * d0, False); req(REQ_DN, refs[k + 1], need + gr * d1, False)
    # 路網(只取結構附近 600 公尺內的路,全台灣全部放進來記憶體不夠)
    NK = set()
    for w in W:
        if w[5] != 0:
            for p in w[3][::3] + [w[3][-1]]:
                a, b = math.floor(p[0] / .005), math.floor(p[1] / .005)
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1): NK.add((a + da, b + db))
    adj = {}; coord = {}
    for w in W:
        wid, kind, refs, g, tg, s, L = w
        if not any((math.floor(p[0] / .005), math.floor(p[1] / .005)) in NK for p in g[::2] + [g[-1]]): continue
        hw = tg.get('highway'); rw = tg.get('railway')
        gr = RGRADE.get(rw, .03) if kind == 'r' else GRADE.get(hw, .06)
        for k, (r, p) in enumerate(zip(refs, g)):
            coord[r] = p
            if k: d = dist(g[k - 1], p); a, b = refs[k - 1], r; adj.setdefault(a, []).append((b, d * gr)); adj.setdefault(b, []).append((a, d * gr))
    # 路口(3 條以上的路交會)固定在地面:引道從路口開始爬升/下降,旁邊的側車道、支線不會跟著被抬高或挖低
    deg = {}
    for w in W:
        if w[1] not in ('h', 'r') or w[4].get('highway') in ('footway', 'path', 'steps', 'cycleway', 'corridor', 'pedestrian'): continue
        rs = w[2]
        for k, r in enumerate(rs):
            if r in adj: deg[r] = deg.get(r, 0) + (1 if k in (0, len(rs) - 1) else 2)
    def tent(REQ, up):
        best = {}; pq = []
        for r, v in REQ.items():
            key = -v if up else v; best[r] = key; pq.append((key, r))
        heapq.heapify(pq)
        while pq:
            key, r = heapq.heappop(pq)
            if key > best.get(r, 1e18): continue
            for (m, c) in adj.get(r, ()):
                if deg.get(m, 0) >= 3 and m not in REQ: continue
                nk = key + c
                if nk < best.get(m, 1e18):
                    # 已經降(升)回地面以下就不用再往外推
                    if m in coord:
                        ge = E.at(*coord[m])
                        if (up and -nk <= ge) or (not up and nk >= ge): continue
                    best[m] = nk; heapq.heappush(pq, (nk, m))
        return {r: (-k if up else k) for r, k in best.items()}
    zu = tent(REQ_UP, True); zd = tent(REQ_DN, False)
    # v2 坡度上限:從固定在地面的路口往外,高度最多每公尺升降一個坡度(高架在路口前就開始下降,不會在最後一小段直上直下)
    FX = [r for r in adj if deg.get(r, 0) >= 3 and r not in REQ_UP and r not in REQ_DN and r in coord]
    def cap(up):
        best = {}; pq = []
        for r in FX:
            v = E.at(*coord[r]); key = v if up else -v; best[r] = key; pq.append((key, r))
        heapq.heapify(pq)
        while pq:
            key, r = heapq.heappop(pq)
            if key > best.get(r, 1e18): continue
            for (m, c) in adj.get(r, ()):
                nk = key + c
                if nk < best.get(m, 1e18): best[m] = nk; heapq.heappush(pq, (nk, m))
        return {r: (k if up else -k) for r, k in best.items()}
    cu = cap(True); cd = cap(False)
    for r in list(zu):
        if r in cu and zu[r] > cu[r]: zu[r] = cu[r]
    for r in list(zd):
        if r in cd and zd[r] < cd[r]: zd[r] = cd[r]
    def zof(r, p):
        ge = E.at(*p); a = zu.get(r); b = zd.get(r)
        ua = a - ge if a is not None and a > ge else 0; db = ge - b if b is not None and b < ge else 0
        if ua >= db: return ge + ua
        return ge - db
    print('heights', len(zu), len(zd), len(adj), f'{time.time()-t0:.0f}s', flush=True)

    # ---- 分格 ----
    cells = {}
    def C(k):
        c = cells.get(k)
        if c is None: c = cells[k] = {'w': [], 'b': [], 'a': [], 'n': []}
        return c
    for w in W:
        wid, kind, refs, g, tg, s, L = w
        zs = None
        if s != 0 or any(r in zu or r in zd for r in refs):
            zz = [zof(r, p) for r, p in zip(refs, g)]
            if s != 0 or any(abs(v - E.at(*p)) > .25 for v, p in zip(zz, g)): zs = zz
        # 每段依中點分到格子,連續的同格線段成一片(相鄰片共用端點,接得起來)
        pieces = []; cur = None; ck = None
        for i in range(len(g) - 1):
            m = ((g[i][0] + g[i + 1][0]) / 2, (g[i][1] + g[i + 1][1]) / 2); k = ckey(*m)
            if k != ck:
                if cur: pieces.append((ck, cur))
                cur = [i]; ck = k
            cur.append(i + 1)
        if cur: pieces.append((ck, cur))
        for (k, ii) in pieces:
            item = [wid, kind, enc([g[i] for i in ii], 6), tg]
            if zs: item.append(encv([int(round(zs[i] * 100)) for i in ii]))
            C(k)['w'].append(item)
    for (g, hh, mh, cen, roof) in h.bld:
        it = [enc(g, 5), int(round(hh * 10))]
        if mh or roof: it.append(int(round(mh * 10)))
        if roof: it.append(1)
        C(ckey(*cen))['b'].append(it)
    try:
        from shapely.geometry import Polygon, box
        from shapely.validation import make_valid
        for (kind, rings, inner) in h.areas:
            for ring in rings:
                if len(ring) < 4: continue
                try:
                    pg = Polygon([(p[1], p[0]) for p in ring], [[(p[1], p[0]) for p in ir] for ir in inner])
                    if not pg.is_valid: pg = make_valid(pg)
                except Exception: continue
                x0, y0, x1, y1 = pg.bounds
                for a in range(math.floor(y0 / G), math.floor(y1 / G) + 1):
                    for b in range(math.floor(x0 / G), math.floor(x1 / G) + 1):
                        try: q = pg.intersection(box(b * G, a * G, (b + 1) * G, (a + 1) * G))
                        except Exception: continue
                        if q.is_empty: continue
                        polys = [q] if q.geom_type == 'Polygon' else [x for x in getattr(q, 'geoms', []) if x.geom_type == 'Polygon']
                        for pp in polys:
                            pp = pp.simplify(0.00002)
                            if pp.is_empty or pp.area < 2e-9: continue
                            rs = [enc([(y, x) for x, y in pp.exterior.coords], 5)] + [enc([(y, x) for x, y in r.coords], 5) for r in pp.interiors]
                            C((a, b))['a'].append([kind] + rs)
    except ImportError:
        print('shapely missing: skip areas')
    for (la, lo, k) in h.nodes: C(ckey(la, lo))['n'].append([round(la, 6), round(lo, 6), k])
    # 有東西的格子 + 周圍一圈都給地形(海邊、山區看起來才完整)
    ks = set(cells.keys())
    for (a, b) in list(ks):
        for da in (-1, 0, 1):
            for db in (-1, 0, 1): ks.add((a + da, b + db))
    stamp = int(time.time() * 1000)
    packs = {}
    for k in ks: packs.setdefault((math.floor(k[0] * G / P + 1e-9), math.floor(k[1] * G / P + 1e-9)), []).append(k)
    man = {'v': 3, 't': stamp, 'g': G, 'p': P, 'en': EN, 'packs': {}}
    for pk, kk in sorted(packs.items()):
        fn = f'r_{pk[0]}_{pk[1]}.txt.gz'; nw = nb = 0
        with gzip.open(os.path.join(out, fn), 'wt', encoding='utf-8', compresslevel=9) as f:
            for k in sorted(kk):
                c = cells.get(k) or {'w': [], 'b': [], 'a': [], 'n': []}
                g = E.cell(k); flat = [int(round(v * 4)) for row in g for v in row]
                d = {'t': stamp, 'e': encv(flat)}
                for x in ('w', 'b', 'a', 'n'):
                    if c[x]: d[x] = c[x]
                nw += len(c['w']); nb += len(c['b'])
                f.write(f'{k[0]}_{k[1]}\t' + json.dumps(d, ensure_ascii=False, separators=(',', ':')) + '\n')
        man['packs'][f'{pk[0]}_{pk[1]}'] = {'f': fn, 'bb': [pk[0] * P, pk[1] * P, (pk[0] + 1) * P, (pk[1] + 1) * P], 'cells': len(kk), 'ways': nw, 'bld': nb,
                                         'size': os.path.getsize(os.path.join(out, fn))}
    with open(os.path.join(out, 'real.json'), 'w') as f: json.dump(man, f, separators=(',', ':'))
    tot = sum(p['size'] for p in man['packs'].values())
    print(f"{len(ks)} cells, {len(packs)} packs, {tot/1048576:.1f} MB, {time.time()-t0:.0f}s")

if __name__ == '__main__': main()
