#!/usr/bin/env python3
"""暫時用:統計台灣 OSM 中標成行人路但可能其實汽機車可通行的道路"""
import sys, re, collections, osmium
CAR = re.compile(r'^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|living_street|service)$')
NAMES = ('東民五街', '東民二街', '東民三街', '東民一街', '東民六街')
class A(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.car = set(); s.ped = []; s.hit = []
    def way(s, w):
        t = {k.k: k.v for k in w.tags}; hw = t.get('highway')
        if not hw: return
        if t.get('name') in NAMES:
            try: m = w.nodes[len(w.nodes)//2].location; s.hit.append((w.id, dict(t), round(m.lat,6), round(m.lon,6), w.nodes[0].ref, w.nodes[-1].ref))
            except Exception: s.hit.append((w.id, dict(t)))
        refs = [n.ref for n in w.nodes]
        if CAR.match(hw) and t.get('access') not in ('no', 'private'): s.car.update(refs)
        elif hw in ('pedestrian', 'footway', 'path', 'living_street') and t.get('area') != 'yes':
            lat = lon = None
            try: lat, lon = w.nodes[len(refs)//2].location.lat, w.nodes[len(refs)//2].location.lon
            except Exception: pass
            s.ped.append((w.id, hw, t, refs, lat, lon))
a = A(); a.apply_file(sys.argv[1], locations=True, idx='flex_mem')
print('== 東民街 tags'); [print(*h, 'end_car', h[4] in a.car if len(h)>4 else '', h[5] in a.car if len(h)>4 else '') for h in a.hit]
import json; json.dump([h[2:4] for h in a.hit if len(h)>2], open('hits.json','w'))
c = collections.Counter(); sf = collections.Counter(); ex = collections.defaultdict(list)
for i, hw, t, refs, lat, lon in a.ped:
    nm = t.get('name', ''); street = bool(re.search(r'(街|路|巷|弄)(\d+[巷弄號])?$', nm)) or bool(re.search(r'\d+(巷|弄)$', nm))
    ends = (refs[0] in a.car) + (refs[-1] in a.car); mid = sum(1 for r in refs[1:-1] if r in a.car)
    k = (hw, 'street' if street else ('named' if nm else 'noname'), f'ends{ends}')
    c[k] += 1
    if street: sf[(hw, t.get('surface', '-'))] += 1
    if street and len(ex[hw]) < 60: ex[hw].append((i, nm, t.get('surface', '-'), t.get('motor_vehicle', ''), t.get('vehicle', ''), t.get('access', ''), ends, mid, round(lat or 0, 4), round(lon or 0, 4)))
print('== counts'); [print(k, v) for k, v in sorted(c.items())]
print('== surface of street-named'); [print(k, v) for k, v in sf.most_common(40)]
for hw, L in ex.items():
    print('== examples', hw); [print(x) for x in L]
kw = collections.Counter()
for i, hw, t, refs, lat, lon in a.ped:
    for k in ('motor_vehicle', 'motorcar', 'motorcycle', 'vehicle', 'access', 'moped'):
        if k in t and hw == 'pedestrian': kw[(k, t[k])] += 1
print('== access tags on pedestrian'); [print(k, v) for k, v in kw.most_common(40)]
