import json, urllib.request
V='https://valhalla1.openstreetmap.de'
def post(body):
    try:
        r=urllib.request.urlopen(urllib.request.Request(V+'/route',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'probe'}),timeout=60);return json.loads(r.read())
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
A={'lat':24.68253,'lon':120.88512};B={'lat':24.6819,'lon':120.8740}
for name,locs in (('direct',[A,B]),):
  for c,co in (('motor_scooter',{'top_speed':60}),('motorcycle',{})):
    j=post({'locations':locs,'costing':c,'costing_options':{c:co},'units':'kilometers'})
    if 'trip' in j:
      sh=dec(j['trip']['legs'][0]['shape']);print(name,c,j['trip']['summary']['length'],[p for p in sh if 120.879<p[1]<120.8825])
    else: print(name,c,j)
# find the moto lane midpoint by locate
for c in ('motor_scooter','motorcycle'):
  for hd in (268,):
    via={'lat':24.682384,'lon':120.880484,'type':'through','heading':hd,'heading_tolerance':35,'radius':0}
    j=post({'locations':[A,via,B],'costing':c,'costing_options':{c:{}},'units':'kilometers'})
    if 'trip' in j:
      sh=dec(j['trip']['legs'][0]['shape']);print('via',c,j['trip']['summary']['length'],[p for p in sh if 120.879<p[1]<120.8825])
    else: print('via',c,j)
j=post({'locations':[{'lat':24.68236,'lon':120.8807}],'costing':'auto','verbose':True}) if False else None
