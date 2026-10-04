#!/usr/bin/env python3
"""行跡導航 離線道路資料產生器
讀 OpenStreetMap 台灣資料(.osm.pbf),挑出導航要用的道路、紅綠燈、橋/地下道、鐵路、平交道,
切成 0.01° 小格(和 App 的 OSMC 格式一樣),再依 0.5° 打包成 gzip 文字檔:每行「格子代碼<TAB>JSON」。
用法: python3 build.py taiwan-latest.osm.pbf out/
"""
import sys, os, re, json, gzip, math, time
import osmium

G = 0.01          # App 的格子大小
P = 0.5           # 打包大小
KEEP = ['highway','name','lanes','oneway','bridge','tunnel','layer','covered','motorcycle','motor_vehicle','motorcar','bicycle',
        'railway','junction','maxspeed','turn:lanes','turn:lanes:forward','turn:lanes:backward']
MAIN = re.compile(r'^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|living_street)$')
SVC = re.compile(r'^(service|track)$')
FOOT = re.compile(r'^(footway|pedestrian|steps|path|cycleway)$')
# 「行人路但其實汽機車可以走」:OSM 把一些鋪石板/地磚的一般街道標成 pedestrian/footway,導航會整條不走。
# 挑出名稱是一般街道(…街/路/巷/弄)、兩端接到汽車道路、沒有禁止車輛標記、沒有車阻的,App 會允許導航走這些路。
CARW = re.compile(r'^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|living_street|service)$')
STREET = re.compile(r'(街|路|大道)(\d+段|[一二三四五六七八九十]段)?$|\d+(巷|弄)$|[^\d]巷$')
NOTCAR = re.compile(r'徒步|步道|老街|夜市|商圈|廣場|公園|園道|天橋|地下道|騎樓|人行|車站|月台|校園|登山|古道|棧道|自行車|單車')
BAR_OK = {'yes', 'permissive', 'designated'}
BARRIER = {'bollard', 'block', 'cycle_barrier', 'kissing_gate', 'stile', 'turnstile', 'full-height_turnstile', 'chain', 'jersey_barrier', 'log', 'swing_gate', 'gate', 'lift_gate', 'motorcycle_barrier', 'step', 'planter'}
NOV = ('no', 'private', 'agricultural', 'forestry', 'emergency', 'official', 'permit', 'delivery', 'customers', 'destination;no')
def ped_kind(t):
    hw = t.get('highway')
    if hw not in ('pedestrian', 'footway'): return None
    if t.get('area') == 'yes' or t.get('footway') in ('sidewalk', 'crossing', 'traffic_island', 'access_aisle') or t.get('covered') == 'yes' or t.get('indoor') == 'yes': return None
    if t.get('tunnel') or t.get('bridge') or t.get('layer', '0') not in ('0', ''): return None
    if t.get('surface') in ('ground', 'dirt', 'earth', 'mud', 'grass', 'sand', 'wood', '泥土', 'gravel', 'unpaved', 'pebblestone', 'unhewn_cobblestone'): return None
    for k in ('access', 'vehicle', 'motor_vehicle', 'motorcar', 'motorcycle'):
        if t.get(k) in NOV: return None
    nm = t.get('name', '')
    if not nm or not STREET.search(nm) or NOTCAR.search(nm): return None
    if t.get('motor_vehicle') in BAR_OK or t.get('motorcar') in BAR_OK or t.get('access') in BAR_OK: return 'p' if hw == 'pedestrian' else 'f'
    return 'p' if hw == 'pedestrian' else 'f'
RAIL = re.compile(r'^(rail|light_rail|subway|narrow_gauge)$')
BG = 0.05         # 自行車道格子(和 App 的 BIKE.G 一樣)
CWV = re.compile(r'^(lane|track|shared_lane|opposite_lane|opposite_track)$'); CWS = re.compile(r'^(lane|track)$')
def bike_kind(t):
    hw = t.get('highway')
    if hw == 'cycleway': return 'd'
    if hw in ('path', 'footway', 'track') and t.get('bicycle') == 'designated': return 'd'
    if CWV.match(t.get('cycleway', '')) or any(CWS.match(t.get('cycleway:' + s, '')) for s in ('right', 'left', 'both')): return 'l'
    return None
def bkey(lat, lon): return f"{math.floor(lat / BG)}_{math.floor(lon / BG)}"

def want_way(t):
    hw = t.get('highway')
    if hw:
        if MAIN.match(hw): return True
        if SVC.match(hw) and (t.get('tunnel') or t.get('bridge') or t.get('layer')): return True
        if FOOT.match(hw) and t.get('bridge'): return True
    rw = t.get('railway')
    return bool(rw and RAIL.match(rw))

def enc(pts, prec=6):
    f = 10 ** prec; o = []; pl = pn = 0
    def e(v):
        v = ~(v << 1) if v < 0 else (v << 1)
        s = []
        while v >= 32:
            s.append(chr((32 | (v & 31)) + 63)); v >>= 5
        s.append(chr(v + 63)); return ''.join(s)
    for a, b in pts:
        la = int(math.floor(a * f + 0.5)); lo = int(math.floor(b * f + 0.5))
        o.append(e(la - pl)); o.append(e(lo - pn)); pl, pn = la, lo
    return ''.join(o)

def ckey(lat, lon): return f"{math.floor(lat / G)}_{math.floor(lon / G)}"
def pkey(ck):
    a, b = map(int, ck.split('_'))
    return f"{math.floor(a * G / P + 1e-9)}_{math.floor(b * G / P + 1e-9)}"

class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__(); self.cells = {}; self.bike = {}; self.carN = set(); self.barN = set(); self.ped = []; self.carName = {}
    def cell(self, k):
        c = self.cells.get(k)
        if c is None: c = self.cells[k] = {'w': [], 'n': []}
        return c
    def node(self, n):
        t = n.tags
        hw = t.get('highway'); cr = t.get('crossing'); rw = t.get('railway')
        b = t.get('barrier')
        if (b in BARRIER and t.get('motor_vehicle') not in BAR_OK and t.get('motorcar') not in BAR_OK and t.get('access') not in BAR_OK) or hw == 'steps': self.barN.add(n.id)
        if hw == 'traffic_signals' or cr == 'traffic_signals' or rw == 'level_crossing':
            lat, lon = n.location.lat, n.location.lon
            self.cell(ckey(lat, lon))['n'].append([n.id, round(lat, 6), round(lon, 6), 'x' if rw == 'level_crossing' else 's', t.get('crossing:barrier', '')])
    def way(self, w):
        t = {k.k: k.v for k in w.tags}
        bk = bike_kind(t)
        if bk:
            g = [(round(nd.location.lat, 6), round(nd.location.lon, 6)) for nd in w.nodes if nd.location.valid()]
            if len(g) >= 2:
                m = g[len(g) // 2]; self.bike.setdefault(bkey(*m), []).append([bk, enc(g, 5)])
        hw = t.get('highway', '')
        if CARW.match(hw) and t.get('access') not in ('no', 'private'):
            self.carN.update(nd.ref for nd in w.nodes)
            nm = t.get('name')
            if nm:
                try: m = w.nodes[len(w.nodes) // 2].location; self.carName.setdefault(nm, set()).add((math.floor(m.lat / 0.01), math.floor(m.lon / 0.01)))
                except Exception: pass
        pk = ped_kind(t)
        if pk:
            try:
                g = [(round(nd.location.lat, 6), round(nd.location.lon, 6)) for nd in w.nodes]
                if len(g) >= 2: self.ped.append((w.id, pk, t.get('name', ''), [nd.ref for nd in w.nodes], g))
            except osmium.InvalidLocationError: pass
        if not want_way(t): return
        try: g = [(round(nd.location.lat, 6), round(nd.location.lon, 6)) for nd in w.nodes]
        except osmium.InvalidLocationError: g = [(round(nd.location.lat, 6), round(nd.location.lon, 6)) for nd in w.nodes if nd.location.valid()]
        if len(g) < 2: return
        tg = {k: t[k] for k in KEEP if k in t}
        e = enc(g); item = [w.id, tg, e]
        for k in {ckey(a, b) for a, b in g}: self.cell(k)['w'].append(item)

def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    t0 = time.time(); h = H()
    h.apply_file(src, locations=True, idx='flex_mem')
    stamp = int(time.time() * 1000)
    packs = {}
    for k, c in h.cells.items(): packs.setdefault(pkey(k), []).append(k)
    man = {'v': 1, 't': stamp, 'g': G, 'p': P, 'packs': {}}
    for pk, ks in sorted(packs.items()):
        fn = f"p_{pk}.txt.gz"; nw = nn = 0
        with gzip.open(os.path.join(out, fn), 'wt', encoding='utf-8', compresslevel=9) as f:
            for k in sorted(ks):
                c = h.cells[k]; nw += len(c['w']); nn += len(c['n'])
                f.write(k + '\t' + json.dumps({'t': stamp, 'p': 1, 'w': c['w'], 'n': c['n']}, ensure_ascii=False, separators=(',', ':')) + '\n')
        a, b = map(int, pk.split('_'))
        man['packs'][pk] = {'f': fn, 'bb': [a * P, b * P, (a + 1) * P, (b + 1) * P], 'cells': len(ks), 'ways': nw, 'nodes': nn,
                            'size': os.path.getsize(os.path.join(out, fn))}
    # 自行車道:全台一個檔;有道路的地方都放一格(沒有自行車道就是空格,App 才知道這格已經有資料)
    bks = set(h.bike.keys())
    for k in h.cells:
        a, b = map(int, k.split('_')); bks.add(f"{math.floor(a * G / BG + 1e-9)}_{math.floor(b * G / BG + 1e-9)}")
    with gzip.open(os.path.join(out, 'bike.txt.gz'), 'wt', encoding='utf-8', compresslevel=9) as f:
        for k in sorted(bks): f.write(k + '\t' + json.dumps({'t': stamp, 'p': 1, 'w': h.bike.get(k, [])}, separators=(',', ':')) + '\n')
    man['bike'] = {'f': 'bike.txt.gz', 'cells': len(bks), 'ways': sum(len(v) for v in h.bike.values()), 'size': os.path.getsize(os.path.join(out, 'bike.txt.gz'))}
    # 汽機車其實可以走的「行人路」白名單
    ped = {}; rej = {}
    def glen(g): return sum(math.hypot((g[i][0] - g[i-1][0]) * 111000, (g[i][1] - g[i-1][1]) * 101000) for i in range(1, len(g)))
    for wid, pk, nm, refs, g in h.ped:
        ends = (refs[0] in h.carN) + (refs[-1] in h.carN)
        why = None
        if any(r in h.barN for r in refs): why = 'barrier'
        elif ends < (1 if pk == 'p' else 2): why = 'ends'
        elif glen(g) > (900 if pk == 'p' else 500): why = 'long'
        elif pk == 'f':
            # 有名字的人行道常和同名的汽車道路並排,這種不算
            ca, cb = math.floor(g[len(g)//2][0] / 0.01), math.floor(g[len(g)//2][1] / 0.01)
            cs = h.carName.get(nm, ())
            if any(abs(a - ca) <= 1 and abs(b - cb) <= 1 for a, b in cs): why = 'samename'
        if why: rej[why] = rej.get(why, 0) + 1; continue
        m = g[len(g) // 2]; ped[str(wid)] = [round(m[0], 5), round(m[1], 5), pk]
    with open(os.path.join(out, 'ped.json'), 'w') as f: json.dump({'t': stamp, 'w': ped}, f, ensure_ascii=False, separators=(',', ':'))
    man['ped'] = {'f': 'ped.json', 'ways': len(ped), 'size': os.path.getsize(os.path.join(out, 'ped.json'))}
    print('ped whitelist', len(ped), 'rejected', rej)
    vm = os.path.join(out, 'vec.json')
    if os.path.exists(vm):
        with open(vm) as f: man['vec'] = json.load(f)
        os.remove(vm)
    with open(os.path.join(out, 'manifest.json'), 'w') as f: json.dump(man, f, ensure_ascii=False, separators=(',', ':'))
    tot = sum(p['size'] for p in man['packs'].values())
    print(f"{len(h.cells)} cells, {len(packs)} packs, {tot/1048576:.1f} MB, {time.time()-t0:.0f}s")

if __name__ == '__main__': main()
