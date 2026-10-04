import json, sys, urllib.request, osmium
V = 'https://valhalla1.openstreetmap.de'
IDS = {198022103, 198022089}
class W(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.g = {}
    def way(s, w):
        if w.id in IDS: s.g[w.id] = [(round(n.location.lat, 6), round(n.location.lon, 6)) for n in w.nodes]
h = W(); h.apply_file(sys.argv[1], locations=True, idx='flex_mem')
print('geom', h.g)
def post(path, body):
    try:
        r = urllib.request.urlopen(urllib.request.Request(V + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'User-Agent': 'xingji-probe'}), timeout=60)
        return json.loads(r.read())
    except urllib.error.HTTPError as e: return {'err': e.code, 'body': e.read().decode()[:300]}
    except Exception as e: return {'err': str(e)}
def dec(s, p=6):
    i = lat = lon = 0; out = []
    while i < len(s):
        for which in (0, 1):
            sh = res = 0
            while True:
                b = ord(s[i]) - 63; i += 1; res |= (b & 31) << sh; sh += 5
                if b < 32: break
            d = ~(res >> 1) if res & 1 else res >> 1
            if which == 0: lat += d
            else: lon += d
        out.append((lat / 10**p, lon / 10**p))
    return out
for wid, g in h.g.items():
    a, b = g[0], g[-1]
    q = ((a[0] * 3 + g[len(g)//2][0]) / 4, (a[1] * 3 + g[len(g)//2][1]) / 4) if len(g) > 2 else ((a[0]+b[0])/2, (a[1]+b[1])/2)
    for name, L in (('end-to-end', [a, b]), ('to-quarter', [b, q])):
        for c in ('auto', 'motor_scooter'):
            for ig in (False, True):
                co = {c: {'ignore_access': ig}}
                j = post('/route', {'locations': [{'lat': x, 'lon': y} for x, y in L], 'costing': c, 'costing_options': co, 'units': 'kilometers'})
                if 'trip' not in j: print(wid, name, c, ig, 'ERR', j); continue
                lg = j['trip']['legs'][0]; sh = dec(lg['shape'])
                print(wid, name, c, 'IGN' if ig else 'norm', 'len', j['trip']['summary']['length'], 'end', sh[-1], 'want', L[-1], [m.get('street_names') for m in lg['maneuvers']])
                if ig:
                    t = post('/trace_attributes', {'shape': [{'lat': x, 'lon': y} for x, y in sh], 'costing': c, 'costing_options': co, 'shape_match': 'edge_walk', 'filters': {'attributes': ['edge.way_id', 'edge.use', 'edge.road_class', 'edge.begin_shape_index', 'edge.end_shape_index'], 'action': 'include'}})
                    print('   trace IGN', [(e.get('way_id'), e.get('use'), e.get('road_class'), e.get('begin_shape_index'), e.get('end_shape_index')) for e in t.get('edges', [])] if 'edges' in t else t)
                    t2 = post('/trace_attributes', {'shape': [{'lat': x, 'lon': y} for x, y in sh], 'costing': c, 'shape_match': 'edge_walk', 'filters': {'attributes': ['edge.way_id'], 'action': 'include'}})
                    print('   trace normal', t2 if 'edges' not in t2 else [e.get('way_id') for e in t2['edges']])
