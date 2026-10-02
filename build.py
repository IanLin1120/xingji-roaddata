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
RAIL = re.compile(r'^(rail|light_rail|subway|narrow_gauge)$')

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
        super().__init__(); self.cells = {}
    def cell(self, k):
        c = self.cells.get(k)
        if c is None: c = self.cells[k] = {'w': [], 'n': []}
        return c
    def node(self, n):
        t = n.tags
        hw = t.get('highway'); cr = t.get('crossing'); rw = t.get('railway')
        if hw == 'traffic_signals' or cr == 'traffic_signals' or rw == 'level_crossing':
            lat, lon = n.location.lat, n.location.lon
            self.cell(ckey(lat, lon))['n'].append([n.id, round(lat, 6), round(lon, 6), 'x' if rw == 'level_crossing' else 's', t.get('crossing:barrier', '')])
    def way(self, w):
        t = {k.k: k.v for k in w.tags}
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
    with open(os.path.join(out, 'manifest.json'), 'w') as f: json.dump(man, f, ensure_ascii=False, separators=(',', ':'))
    tot = sum(p['size'] for p in man['packs'].values())
    print(f"{len(h.cells)} cells, {len(packs)} packs, {tot/1048576:.1f} MB, {time.time()-t0:.0f}s")

if __name__ == '__main__': main()
