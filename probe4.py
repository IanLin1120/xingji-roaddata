import json, urllib.request, time
A={'lat':24.709477,'lon':120.918664};B={'lat':24.707293,'lon':120.920850};W={'lat':24.707711,'lon':120.919667}
co={'walking_speed':4.8,'alley_factor':1.4,'use_living_streets':.6,'step_penalty':10,'walkway_factor':.85,'sidewalk_factor':.85,'driveway_factor':3}
def get(base,body):
    t=time.time()
    try:
        r=urllib.request.urlopen(urllib.request.Request(base+'/route?json='+urllib.parse.quote(json.dumps(body)),headers={'User-Agent':'probe'}),timeout=40);s=r.status;tx=r.read().decode()[:200]
    except urllib.error.HTTPError as e: s=e.code;tx=e.read().decode()[:300]
    except Exception as e: s='EXC';tx=repr(e)[:200]
    print(base,s,round(time.time()-t,1),tx)
for base in ['https://valhalla1.openstreetmap.de','https://valhalla2.openstreetmap.de']:
    for locs in ([B,W,A],[A,B]):
        get(base,{'locations':[dict(l,type='break') for l in locs],'costing':'pedestrian','costing_options':{'pedestrian':co},'units':'kilometers','language':'en-US','directions_options':{'units':'kilometers','language':'en-US'},'alternates':2})
    get(base,{'locations':[A,B],'costing':'auto','units':'kilometers'})
    get(base,{'locations':[dict(B,type='break'),dict(W,type='break'),{'lat':24.709477,'lon':120.918664,'type':'break','radius':6}],'costing':'pedestrian','costing_options':{'pedestrian':co},'units':'kilometers','alternates':0})
