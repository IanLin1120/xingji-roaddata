# 探查:政府開放資料裡的區間測速、OSM 的 average_speed
import json, urllib.request, urllib.parse, re, sys, os, csv, io
os.makedirs('probe', exist_ok=True)
UA={'User-Agent':'Mozilla/5.0 xingji'}
def get(u, t=60):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read()
SETS=['7320','13940','100856','100857','106636','135957','178168','25935','170673','139129','167749','167752','151949','160171','145873','148455','52544','177486']
log=[]
for sid in SETS:
    try:
        j=json.loads(get('https://data.gov.tw/api/v2/rest/dataset/'+sid))
        title=json.dumps(j,ensure_ascii=False)[:0]
        urls=re.findall(r'"(https?://[^"]+)"', json.dumps(j,ensure_ascii=False))
        urls=[u for u in urls if re.search(r'download|csv|json|DownloadFile|api',u,re.I) and 'data.gov.tw/dataset' not in u]
        tt=(j.get('result') or {}).get('title') or ''
        log.append(f'== {sid} {tt} {len(urls)} urls')
        for i,u in enumerate(dict.fromkeys(urls)):
            try:
                b=get(u,90)
                for enc in ('utf-8-sig','big5','cp950'):
                    try: s=b.decode(enc); break
                    except: s=None
                if not s: continue
                fn=f'probe/{sid}_{i}.txt'; open(fn,'w').write(s)
                n=s.count('區間'); log.append(f'  {u} {len(s)} bytes 區間x{n}')
                if n: open(f'probe/sec_{sid}_{i}.txt','w').write('\n'.join(l for k,l in enumerate(s.splitlines()) if k==0 or '區間' in l))
            except Exception as e: log.append(f'  ERR {u} {e}')
    except Exception as e: log.append(f'== {sid} ERR {e}')
q='[out:json][timeout:180];area["ISO3166-1"="TW"]->.a;(relation["enforcement"="average_speed"](area.a);node["enforcement"="average_speed"](area.a);way["enforcement"="average_speed"](area.a););out body geom;'
for ep in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        b=urllib.request.urlopen(urllib.request.Request(ep,data=('data='+urllib.parse.quote(q)).encode(),headers=UA),timeout=240).read()
        open('probe/osm_avg.json','wb').write(b); log.append(f'osm {len(b)}'); break
    except Exception as e: log.append(f'osm ERR {ep} {e}')
open('probe/log.txt','w').write('\n'.join(log)); print('\n'.join(log))
