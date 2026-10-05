import sys, json, urllib.request, osmium, math
A={'lat':24.709477,'lon':120.918664};B={'lat':24.707293,'lon':120.920850}
BB=(24.7064,120.9188,24.7096,120.9222)
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.w=[]
    def way(s,w):
        t={k.k:k.v for k in w.tags}
        if 'highway' not in t: return
        try: g=[(n.ref,round(n.location.lat,6),round(n.location.lon,6)) for n in w.nodes]
        except Exception: return
        if any(BB[0]<=a<=BB[2] and BB[1]<=b<=BB[3] for _,a,b in g): s.w.append((w.id,t,g))
h=H(); h.apply_file(sys.argv[1],locations=True,idx='flex_mem')
use={}
for wid,t,g in h.w:
    for r,_,_ in g: use.setdefault(r,set()).add(wid)
def d(a,b):return math.hypot((a[0]-b[0])*111000,(a[1]-b[1])*101000)
for wid,t,g in h.w:
    ends=[len(use[g[0][0]])-1,len(use[g[-1][0]])-1]
    near=min(d((x[1],x[2]),(B['lat'],B['lon'])) for x in g)
    print(wid,{k:v for k,v in t.items() if k in('highway','name','footway','access','foot','service','area','indoor','layer','level')},'n',len(g),'ends',ends,'distB',round(near),'pts',[x[1:] for x in g][:12])
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
for co in ({'walking_speed':4.8,'alley_factor':1.4,'use_living_streets':.6,'step_penalty':10},{'walkway_factor':.5,'sidewalk_factor':.7,'step_penalty':0},{'shortest':True},{'shortest':True,'ignore_access':True}):
    j=post('/route',{'locations':[A,B],'costing':'pedestrian','costing_options':{'pedestrian':co},'units':'kilometers','alternates':2})
    if 'trip' not in j: print('ERR',co,j);continue
    print('ROUTE',co,j['trip']['summary']['length'],dec(j['trip']['legs'][0]['shape']))
    loc=post('/locate',{'locations':[B],'costing':'pedestrian','verbose':False})
print('LOCATE',json.dumps(post('/locate',{'locations':[B,A],'costing':'pedestrian'}))[:1500])
