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
    j=post('/route',{'locations':[A,{'lat':P[0],'lon':P[1],'type':'break'}],'costing':'pedestrian','costing_options':{'pedestrian':co},'units':'kilometers'})
    if 'trip' not in j: print(P,j);continue
    sh=dec(j['trip']['legs'][0]['shape'])
    print(P,'len',j['trip']['summary']['length'],'shape',sh[::max(1,len(sh)//25)],sh[-1])
