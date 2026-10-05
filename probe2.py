import sys, osmium, json, urllib.request
BB=(24.7060,120.9150,24.7120,120.9230)
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.w=[]; s.nodes={}
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
for wid,t,g in h.w:
    if t['highway'] in ('footway','path','pedestrian','steps','service','cycleway','track','corridor'):
        ends=[len(use[g[0][0]])-1,len(use[g[-1][0]])-1]; mid=sum(len(use[r])-1 for r,_,_ in g[1:-1])
        print(wid,t,'pts',len(g),'from',g[0][1:],'to',g[-1][1:],'conn_ends',ends,'conn_mid',mid)
V='https://valhalla1.openstreetmap.de'
def post(path,body):
    try:
        r=urllib.request.urlopen(urllib.request.Request(V+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'probe'}),timeout=60);return json.loads(r.read())
    except urllib.error.HTTPError as e: return {'err':e.code,'body':e.read().decode()[:300]}
for co in ({},{'walkway_factor':.6,'sidewalk_factor':.8},{'ignore_access':True}):
    j=post('/route',{'locations':[{'lat':24.70966,'lon':120.91855},{'lat':24.70878,'lon':120.92065}],'costing':'pedestrian','costing_options':{'pedestrian':co},'units':'kilometers'})
    print('ROUTE',co, j.get('trip',{}).get('summary') if 'trip' in j else j, [m.get('street_names') for m in j['trip']['legs'][0]['maneuvers']] if 'trip' in j else '')
