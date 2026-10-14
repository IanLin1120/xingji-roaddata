import json, os, sys, urllib.parse
sys.path.insert(0, '.')
from bus import http, token, tdx
try: tok = token(); print('token', 'yes' if tok else 'none (secrets missing)')
except Exception as e: tok = None; print('token error', e)
def q(p):
    try: return tdx(p, tok)
    except Exception as e: print('ERR', p, e); return []
for city in ['MiaoliCounty', 'HsinchuCounty', 'Hsinchu']:
    R = q(f'v2/Bus/Route/City/{city}?$select=RouteUID,RouteName,SubRoutes,DepartureStopNameZh,DestinationStopNameZh,BusRouteType,Operators&$top=3000')
    print(city, 'routes', len(R))
    for r in R:
        n = (r.get('RouteName') or {}).get('Zh_tw', '')
        if any(k in n for k in ['科學', '園區', '紫', '竹科', '科管']) or any(k in json.dumps(r, ensure_ascii=False) for k in ['科學園區', '竹南園區']):
            print('  ROUTE', n, r.get('RouteUID'), r.get('DepartureStopNameZh'), '->', r.get('DestinationStopNameZh'), [ (s.get('SubRouteName') or {}).get('Zh_tw') for s in r.get('SubRoutes') or []][:6])
    S = q(f"v2/Bus/Stop/City/{city}?$filter=contains(StopName/Zh_tw,'智晶')&$top=50")
    for s in S: print('  STOP', s.get('StopUID'), (s.get('StopName') or {}).get('Zh_tw'), s.get('StopPosition'))
    SR = q(f"v2/Bus/StopOfRoute/City/{city}?$filter=Stops/any(s:contains(s/StopName/Zh_tw,'智晶'))&$select=RouteName,SubRouteName,Direction&$top=50")
    for s in SR: print('  STOPOFROUTE', json.dumps(s, ensure_ascii=False)[:300])
I = q("v2/Bus/StopOfRoute/InterCity?$filter=Stops/any(s:contains(s/StopName/Zh_tw,'智晶'))&$select=RouteName,SubRouteName,Direction&$top=50")
for s in I: print('  INTERCITY', json.dumps(s, ensure_ascii=False)[:300])
