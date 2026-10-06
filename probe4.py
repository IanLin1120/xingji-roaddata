import json, urllib.request, urllib.parse
q='[out:json][timeout:60];(node[highway=traffic_signals](24.6825,120.9015,24.6935,120.9085);node[crossing=traffic_signals](24.6825,120.9015,24.6935,120.9085););out;'
for ep in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(ep,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'probe'}),timeout=90);j=json.loads(r.read());break
    except Exception as e: print('ERR',ep,e)
for e in j['elements']: print(e['id'],e['lat'],e['lon'],e.get('tags'))
