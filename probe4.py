import json, urllib.request, time
out={}
for prof in ['routed-foot/route/v1/foot','routed-car/route/v1/driving','routed-bike/route/v1/bike']:
    u=f'https://routing.openstreetmap.de/{prof}/120.920850,24.707293;120.919667,24.707711;120.918664,24.709477?steps=true&geometries=polyline6&overview=full&alternatives=false&continue_straight=false'
    t=time.time()
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'probe'}),timeout=40);out[prof]=json.loads(r.read())
    except Exception as e: out[prof]=repr(e)
    out[prof+'_t']=round(time.time()-t,1)
u='https://routing.openstreetmap.de/routed-car/route/v1/driving/121.517,25.0478;121.526,25.054?steps=true&geometries=polyline6&overview=full&alternatives=2'
try: out['alt']=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'probe'}),timeout=40).read())
except Exception as e: out['alt']=repr(e)
print(json.dumps(out,ensure_ascii=False))
