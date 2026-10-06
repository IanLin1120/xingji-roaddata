import json, urllib.request, urllib.parse
q='[out:json][timeout:60];way(around:180,24.7031,120.9187)[highway];out tags geom;way(around:180,24.7031,120.9187)[railway];out tags geom;'
for ep in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(ep,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'probe'}),timeout=90);j=json.loads(r.read());break
    except Exception as e: print('ERR',ep,e)
for e in j['elements']:
    t=e.get('tags',{});g=[(round(x['lat'],6),round(x['lon'],6)) for x in e.get('geometry',[])]
    print(e['id'],{k:v for k,v in t.items() if k in('highway','railway','name','bridge','layer','tunnel','oneway','lanes','ref','level','man_made')},len(g),g[0],g[-1],g[:8] if len(g)<=8 else g[::max(1,len(g)//8)])
