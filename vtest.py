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
g = h.g[198022103]; a, b = g[0], g[-1]
for c, co in (('motor_scooter', {'ignore_access': True}), ('motor_scooter', {'ignore_access': True, 'service_penalty': 0, 'service_factor': 1}),
              ('motor_scooter', {'ignore_access': True, 'service_penalty': 0, 'service_factor': 1, 'use_living_streets': 1, 'use_primary': 0.5}),
              ('motor_scooter', {'ignore_access': True, 'shortest': True}), ('motorcycle', {'ignore_access': True}), ('motorcycle', {}),
              ('auto', {'ignore_access': True}), ('auto', {'ignore_access': True, 'service_penalty': 80, 'service_factor': 3, 'use_living_streets': .15})):
    j = post('/route', {'locations': [{'lat': a[0], 'lon': a[1]}, {'lat': b[0], 'lon': b[1]}], 'costing': c, 'costing_options': {c: co}, 'units': 'kilometers'})
    if 'trip' not in j: print(c, co, 'ERR', j); continue
    lg = j['trip']['legs'][0]; print(c, co, 'len', j['trip']['summary']['length'], 'time', j['trip']['summary']['time'], [m.get('street_names') for m in lg['maneuvers']])
