import json, urllib.request
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
            d=~(res>>1) if res&1 else res>>1
            if w==0:la+=d
            else:lo+=d
        o.append((round(la/1e6,6),round(lo/1e6,6)))
    return o
A={'lat':24.70955,'lon':120.91840}
for B in ({'lat':24.7072,'lon':120.9200},{'lat':24.70725,'lon':120.92030},{'lat':24.70705,'lon':120.92010}):
  for co in ({'walking_speed':4.8,'alley_factor':1.4,'use_living_streets':.6,'step_penalty':10},{'walking_speed':4.8,'alley_factor':4,'use_living_streets':.6,'step_penalty':10},{'walkway_factor':.5,'sidewalk_factor':.8},{'shortest':True}):
    j=post('/route',{'locations':[A,B],'costing':'pedestrian','costing_options':{'pedestrian':co},'units':'kilometers'})
    if 'trip' not in j: print(B,co,j);continue
    sh=dec(j['trip']['legs'][0]['shape']);print(B,co,'len',j['trip']['summary']['length'],[m.get('street_names') for m in j['trip']['legs'][0]['maneuvers']]);print('  ',sh[::max(1,len(sh)//25)])
