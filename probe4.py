import json, urllib.request, urllib.parse
bb='24.6820,120.9010,24.6940,120.9090'
q=f'[out:json][timeout:60];(way[highway]({bb});node[highway=traffic_signals]({bb});node[crossing=traffic_signals]({bb}););out tags geom;'
import time
j=None
for ep in ['https://overpass.private.coffee/api/interpreter','https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter','https://overpass-api.de/api/interpreter']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(ep,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'probe'}),timeout=120);j=json.loads(r.read());break
    except Exception as e: print('ERR',ep,e);time.sleep(10)
print(json.dumps(j))
