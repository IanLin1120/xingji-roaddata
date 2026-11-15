# 從台灣 OSM 抽出區間測速路段附近的道路、里程牌、交流道,給區間測速路段資料使用
import osmium, json, sys, re, math
PTS=json.load(open('tools/secpts.json'))
HW={'motorway','trunk','primary','secondary','tertiary','unclassified','residential','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link'}
def near(lat,lon,R=0.22):
    for a,b in PTS:
        if abs(lat-a)<R and abs(lon-b)<R: return True
    return False
class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.ways=[]; s.ms=[]; s.jn=[]
    def node(s,n):
        t=n.tags; hw=t.get('highway','')
        if not n.location.valid(): return
        la,lo=n.location.lat,n.location.lon
        if 'milestone' in hw or ('distance' in t and t.get('highway:TW:dataset')):
            s.ms.append({'lat':round(la,6),'lon':round(lo,6),'d':t.get('distance',''),'n':t.get('network',''),'nm':t.get('name','')})
        elif hw=='motorway_junction' and near(la,lo,0.4):
            s.jn.append({'lat':round(la,6),'lon':round(lo,6),'ref':t.get('ref',''),'nm':t.get('name','')})
    def way(s,w):
        t=w.tags; hw=t.get('highway')
        if hw not in HW: return
        try: g=[[round(n.location.lat,6),round(n.location.lon,6)] for n in w.nodes]
        except Exception: return
        if not any(near(p[0],p[1]) for p in g[::max(1,len(g)//6)]+[g[-1]]): return
        if hw in ('residential','unclassified') and not t.get('ref') and not re.search('隧道|大橋|松藝|環河|壽山|萬壽|青山|向上|東海',t.get('name','')): return
        s.ways.append({'id':w.id,'ref':t.get('ref',''),'name':t.get('name',''),'hw':hw,'ow':t.get('oneway',''),'tun':t.get('tunnel',''),'nodes':[n.ref for n in w.nodes],'g':g})
h=H(); h.apply_file(sys.argv[1],locations=True)
json.dump({'ways':h.ways,'ms':h.ms,'jn':h.jn},open(sys.argv[2],'w'),ensure_ascii=False)
print(len(h.ways),'ways',len(h.ms),'milestones',len(h.jn),'junctions')
