import json, urllib.request
A={'lat':24.709477,'lon':120.918664}
V='https://valhalla1.openstreetmap.de'
def post(path,body):
    try:
        r=urllib.request.urlopen(urllib.request.Request(V+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'probe'}),timeout=60);return json.loads(r.read())
    except urllib.error.HTTPError as e: return {'err':e.code,'body':e.read().decode()[:300]}
def dec(s,p=6):
    i=la=lo=0;o=[]
    while i<len(s):
        for w in (0,1):
            sh=res=0
            while True:
                b=ord(s[i])-63;i+=1;res|=(b&31)<<sh;sh+=5
                if b<32:break
            dd=~(res>>1) if res&1 else res>>1
            if w==0:la+=dd
            else:lo+=dd
        o.append((round(la/1e6,6),round(lo/1e6,6)))
    return o
co={'walking_speed':4.8,'alley_factor':1.4,'use_living_streets':.6,'step_penalty':10}
for P in [(24.707252,120.920302),(24.7073,120.92030),(24.70745,120.9203),(24.707808,120.919533),(24.707884,120.920296)]:
W={'lat':24.707711,'lon':120.919667};B={'lat':24.707293,'lon':120.920850}
base={'walking_speed':4.8,'alley_factor':1.4,'use_living_streets':.6,'step_penalty':10}
new=dict(base,walkway_factor=.85,sidewalk_factor=.85,driveway_factor=3)
def run(tag,locs,co):
    j=post('/route',{'locations':locs,'costing':'pedestrian','costing_options':{'pedestrian':co},'units':'kilometers'})
    if 'trip' not in j: print(tag,j);return
    o=[]
    for lg in j['trip']['legs']: sh=dec(lg['shape']);o.append(sh[::max(1,len(sh)//12)]+[sh[-1]])
    print(tag,'len',j['trip']['summary']['length'],o)
for co,cn in ((base,'base'),(new,'new')):
  for r in (30,10,0):
    w=dict(W,type='break',radius=r)
    run(f'{cn} r{r} dest',[A,w,dict(B,type='break',radius=30)],co)
    run(f'{cn} r{r} cand',[A,w,{'lat':24.707289,'lon':120.920302,'type':'break','radius':6}],co)
run('new direct',[A,{'lat':24.707289,'lon':120.920302,'type':'break','radius':6}],new)
