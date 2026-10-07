import json, urllib.request, urllib.parse, time
q='[out:json][timeout:60];(way(around:120,24.6950,120.9082)[highway];way(around:120,24.70645,120.9178)[highway];);out tags geom;'
j=None
for ep in ['https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter','https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(ep,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'probe'}),timeout=120);j=json.loads(r.read());break
    except Exception as e: print('ERR',ep,e);time.sleep(10)
print(json.dumps(j))
