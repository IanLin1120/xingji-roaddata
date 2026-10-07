import json, urllib.request, urllib.parse, time
q='[out:json][timeout:90];way[name="環市路二段"](21.8,119.9,25.4,122.1)->.a;way[name="自強路二段"](around.a:300)->.b;way(around.b:250)[highway];out tags geom;'
j=None
for ep in ['https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter','https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(ep,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'probe'}),timeout=150);j=json.loads(r.read());break
    except Exception as e: print('ERR',ep,e);time.sleep(10)
print(json.dumps(j))
