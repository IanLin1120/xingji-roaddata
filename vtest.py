import json, urllib.request
V = 'https://valhalla1.openstreetmap.de'
hits = json.load(open('hits.json'))
def post(path, body):
    try:
        r = urllib.request.urlopen(urllib.request.Request(V + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'User-Agent': 'xingji-probe'}), timeout=60)
        return json.loads(r.read())
    except urllib.error.HTTPError as e: return {'err': e.code, 'body': e.read().decode()[:400]}
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
for h in hits[:2]:
    dest = {'lat': h[0], 'lon': h[1]}; orig = {'lat': 24.6855, 'lon': 120.9105}
    for c in ('auto', 'motor_scooter'):
        for ig in (False, True):
            co = {c: {'ignore_access': ig}}
            j = post('/route', {'locations': [orig, dest], 'costing': c, 'costing_options': co, 'units': 'kilometers'})
            if 'trip' not in j: print(c, ig, 'ERR', j); continue
            lg = j['trip']['legs'][0]; sh = dec(lg['shape'])
            print(c, 'ignore_access' if ig else 'normal', 'len', j['trip']['summary']['length'], 'time', j['trip']['summary']['time'], 'end', sh[-1], 'dest', h, [m.get('street_names') for m in lg['maneuvers']])
            if ig:
                t = post('/trace_attributes', {'shape': [{'lat': a, 'lon': b} for a, b in sh], 'costing': c, 'costing_options': co, 'shape_match': 'edge_walk', 'filters': {'attributes': ['edge.way_id', 'edge.use', 'edge.road_class', 'edge.names', 'edge.length', 'edge.begin_shape_index', 'edge.end_shape_index', 'edge.surface'], 'action': 'include'}})
                print('  trace', [(e.get('way_id'), e.get('use'), e.get('road_class'), e.get('names'), e.get('surface')) for e in t.get('edges', [])] if 'edges' in t else t)
                t2 = post('/trace_attributes', {'shape': [{'lat': a, 'lon': b} for a, b in sh], 'costing': c, 'shape_match': 'edge_walk', 'filters': {'attributes': ['edge.way_id'], 'action': 'include'}})
                print('  trace normal', t2 if 'edges' not in t2 else len(t2['edges']))
