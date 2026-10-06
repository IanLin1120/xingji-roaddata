import json, urllib.request, urllib.parse
bb='24.6820,120.9010,24.6940,120.9090'
q=f'[out:json][timeout:60];(way[highway]({bb});node[highway=traffic_signals]({bb});node[crossing=traffic_signals]({bb}););out tags geom;'
for ep in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(ep,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'probe'}),timeout=90);j=json.loads(r.read());break
    except Exception as e: print('ERR',ep,e)
print(json.dumps(j))
