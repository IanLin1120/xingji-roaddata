import json, urllib.request, urllib.parse
q='[out:json][timeout:60];(way(around:400,24.7031,120.9187)[highway];way(around:400,24.7031,120.9187)[railway];);out tags geom;'
for ep in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(ep,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'probe'}),timeout=90);j=json.loads(r.read());break
    except Exception as e: print('ERR',ep,e)
print(json.dumps(j))
