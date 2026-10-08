import urllib.request, json, gzip, time
def get(u,h={}):
    r=urllib.request.Request(u,headers={'User-Agent':'xingji-roaddata/1.0','Accept-Encoding':'gzip',**h})
    try:
        with urllib.request.urlopen(r,timeout=120) as x:
            b=x.read()
            if b[:2]==b'\x1f\x8b': b=gzip.decompress(b)
            return x.status,b
    except urllib.error.HTTPError as e: return e.code,e.read()[:300]
    except Exception as e: return 0,str(e).encode()
for u in ['https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Keelung?$select=RouteName,Direction,Stops&$top=2&$format=JSON',
          'https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/Keelung?$top=2&$format=JSON']:
    st,b=get(u);print(st,len(b),b[:300]);time.sleep(2)
