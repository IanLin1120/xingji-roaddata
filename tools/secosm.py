# 從台灣 OSM 抽出區間測速路段會用到的道路、里程牌,給 secbuild 使用
import osmium, json, sys, re
REFS=['台9','台9丁','台15','台3','台61','台13甲','台21','台1','台26','台11','台62','台62甲','台64','台65','台7乙','台2','台1甲','140','182','北118','苗140','市182','高182','南182']
NAMES=['自強隧道','辛亥隧道','鳳鼻','仁水隧道','中仁隧道','草埔隧道','觀音隧道','谷風隧道','東澳隧道','瑪陵隧道','金門大橋','松藝路','環河路','壽山路','萬壽路','青山路','向上路','台62甲','東海街']
def norm(r): return r.replace('臺','台').replace('線','').replace(' ','')
HW={'motorway','trunk','primary','secondary','tertiary','unclassified','residential','motorway_link','trunk_link','primary_link','secondary_link'}
class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.ways=[]; s.ms=[]; s.refs={}
    def node(s,n):
        t=n.tags
        if t.get('highway')=='milestone' or 'distance' in t or t.get('pk') or (t.get('highway')=='mile_marker'):
            s.ms.append({'lat':round(n.location.lat,6),'lon':round(n.location.lon,6),'t':dict(t)})
    def way(s,w):
        t=w.tags; hw=t.get('highway')
        if hw not in HW: return
        ref=norm(t.get('ref','')); nm=t.get('name','')
        refs=[x for x in re.split('[;,]',ref) if x]
        for x in refs: s.refs[x]=s.refs.get(x,0)+1
        hit=any(x in REFS for x in refs) or any(k in nm for k in NAMES) or any(k in (t.get('tunnel:name','')) for k in NAMES)
        if not hit: return
        try: g=[[round(n.location.lat,6),round(n.location.lon,6)] for n in w.nodes]
        except Exception: return
        s.ways.append({'id':w.id,'ref':ref,'name':nm,'hw':hw,'ow':t.get('oneway',''),'tun':t.get('tunnel',''),'br':t.get('bridge',''),'lay':t.get('layer',''),'nodes':[n.ref for n in w.nodes],'g':g,'ms':t.get('maxspeed','')})
h=H(); h.apply_file(sys.argv[1],locations=True)
json.dump({'ways':h.ways,'ms':h.ms,'refs':sorted(h.refs.items(),key=lambda x:-x[1])[:400]},open(sys.argv[2],'w'),ensure_ascii=False)
print(len(h.ways),'ways',len(h.ms),'milestones')
