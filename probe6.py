import json, urllib.request, urllib.parse
q='[out:json][timeout:60];node[highway=bus_stop](24.700,120.905,24.716,120.930)->.s;.s out;rel(bn.s)[type=route];out tags;'
for url in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        b=urllib.request.urlopen(urllib.request.Request(url,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'xingji-probe'}),timeout=90).read()
        j=json.loads(b);break
    except Exception as e: print('ERR',url,e)
for e in j['elements']:
    if e['type']=='relation': print('REL',e['id'],json.dumps(e.get('tags'),ensure_ascii=False))
for e in j['elements']:
    if e['type']=='node': print('STOP',e['id'],e['lat'],e['lon'],json.dumps(e.get('tags'),ensure_ascii=False)[:200])
