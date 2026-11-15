#!/usr/bin/env python3
"""產生全台區間測速路段資料 app/sec.json
來源:警政署「測速執法設置點」(data.gov.tw 7320)與臺北、桃園、臺中的科技執法資料裡標示「區間」的路段;
位置:公路局里程牌(OSM highway=milestone, highway:TW:dataset=7040)換算里程 → 沿 OpenStreetMap 道路(依單行方向)串成線。
快速道路沒有里程牌,用交流道編號(=里程)換算;縣道、市道用道路起點累計里程;隧道、市區道路用名稱或路口。
用法: python3 secmk.py osm_sec.json.gz out.json"""
import json, gzip, math, re, sys, heapq, collections

D = json.load(gzip.open(sys.argv[1]))
R2 = math.pi / 180
def dist(a, b):
    return math.hypot((a[0]-b[0])*110540, (a[1]-b[1])*111320*math.cos(a[0]*R2))

# ---------- 圖 ----------
XY = {}; ADJ = collections.defaultdict(list); WAYS = D['ways']
for wi, w in enumerate(WAYS):
    ns, g = w['nodes'], w['g']
    for n, p in zip(ns, g): XY[n] = (p[0], p[1])
    ow = w['ow']; fwd = ow != '-1'; bwd = ow not in ('yes', 'true', '1', '-1') or ow == '-1'
    if ow == '-1': fwd, bwd = False, True
    if w['hw'] in ('motorway', 'motorway_link') and ow == '': bwd = False  # 高速、快速道路預設單行
    for i in range(len(ns)-1):
        a, b = ns[i], ns[i+1]; L = dist(g[i], g[i+1])
        if fwd: ADJ[a].append((b, L, wi))
        if bwd: ADJ[b].append((a, L, wi))
GRID = collections.defaultdict(list)
for n, p in XY.items(): GRID[(int(p[0]/.002), int(p[1]/.002))].append(n)
def nodes_near(p, r):
    gx, gy = int(p[0]/.002), int(p[1]/.002); k = int(r/200)+1; out = []
    for x in range(gx-k, gx+k+1):
        for y in range(gy-k, gy+k+1):
            for n in GRID.get((x, y), ()):
                d = dist(p, XY[n])
                if d <= r: out.append((d, n))
    return sorted(out)

def refs_of(w): return [x.strip().replace('台', '').replace('臺', '').replace('線', '') for x in re.split('[;,]', w['ref']) if x.strip()]
def wf_ref(ref):
    return lambda w: ref in refs_of(w)
def wf_name(*names):
    return lambda w: any(k in w['name'] for k in names)

def dijkstra(srcs, tgts, wf, pen=4.0, maxc=60000):
    """srcs/tgts: {node: 起始/結束額外成本};只走 wf 的道路成本 1 倍,其他道路 pen 倍"""
    best = {}; prev = {}; h = []
    for n, c in srcs.items(): best[n] = c; heapq.heappush(h, (c, n))
    good = {}
    while h:
        c, n = heapq.heappop(h)
        if c > best.get(n, 1e18): continue
        if c > maxc: break
        if n in tgts:
            tot = c + tgts[n]
            if 'done' not in good or tot < good['done'][0]: good['done'] = (tot, n)
        if 'done' in good and c > good['done'][0]: break
        for m, L, wi in ADJ.get(n, ()):
            ww = WAYS[wi]; k = 1.0 if wf(ww) else pen
            nc = c + L*k
            if nc < best.get(m, 1e18): best[m] = nc; prev[m] = n; heapq.heappush(h, (nc, m))
    if 'done' not in good: return None
    n = good['done'][1]; path = [n]
    while n in prev: n = prev[n]; path.append(n)
    path.reverse(); return path

def cum(P):
    c = [0.0]
    for i in range(1, len(P)): c.append(c[-1]+dist(P[i-1], P[i]))
    return c
def point_at(P, C, s):
    if s <= 0: return P[0], 0
    for i in range(1, len(P)):
        if C[i] >= s:
            t = (s-C[i-1])/max(1e-9, C[i]-C[i-1]); a, b = P[i-1], P[i]
            return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t), i
    return P[-1], len(P)-1
def cut(P, s0, s1):
    C = cum(P); a, i = point_at(P, C, s0); b, j = point_at(P, C, s1)
    return [a]+P[i:j]+[b]
def project(P, q):
    C = cum(P); best = (1e18, 0)
    kx = math.cos(q[0]*R2)*111320; ky = 110540
    for i in range(len(P)-1):
        ax, ay = (P[i][1]-q[1])*kx, (P[i][0]-q[0])*ky; bx, by = (P[i+1][1]-q[1])*kx, (P[i+1][0]-q[0])*ky
        dx, dy = bx-ax, by-ay; L2 = dx*dx+dy*dy; t = 0 if not L2 else max(0, min(1, -(ax*dx+ay*dy)/L2))
        d = math.hypot(ax+t*dx, ay+t*dy)
        if d < best[0]: best = (d, C[i]+t*math.sqrt(L2))
    return best

def route_through(anchors, wf, snap=150):
    for r in (60, snap, 300):
        P, pos = _route_through(anchors, wf, r)
        if P: return P, pos
    return None, None
def _route_through(anchors, wf, snap):
    """anchors: [(km,(lat,lon))] 依行進順序;回傳折線與每個 anchor 在線上的位置"""
    P = []; pos = []; last = None
    for i in range(len(anchors)-1):
        a, b = anchors[i][1], anchors[i+1][1]
        src = {last: 0} if last is not None else {n: d*4 for d, n in nodes_near(a, snap)[:80]}
        tg = {n: d*4 for d, n in nodes_near(b, snap)[:80]}
        if not src or not tg: return None, None
        path = dijkstra(src, tg, wf, maxc=dist(a, b)*3+3000)
        if not path: return None, None
        seg = [XY[n] for n in path]
        if P and seg and seg[0] == P[-1]: seg = seg[1:]
        P += seg; last = path[-1]
    if len(P) < 2: return None, None
    for km, q in anchors: pos.append((km, project(P, q)[1]))
    return P, pos

def km_to_s(pos, km):
    """里程 → 線上位置(分段線性內插,超出兩端就外推)"""
    pos = sorted(pos, key=lambda x: x[1])
    ks = [p[0] for p in pos]; ss = [p[1] for p in pos]
    inc = ks[-1] > ks[0]
    for i in range(len(pos)-1):
        k0, k1 = ks[i], ks[i+1]
        if min(k0, k1)-1e-9 <= km <= max(k0, k1)+1e-9 and k0 != k1:
            return ss[i]+(km-k0)/(k1-k0)*(ss[i+1]-ss[i])
    # 外推
    if (km < ks[0]) == inc or (km > ks[0]) == (not inc):
        i = 0
    else: i = len(pos)-2
    k0, k1 = ks[i], ks[i+1]
    if k0 == k1: return None
    return ss[i]+(km-k0)/(k1-k0)*(ss[i+1]-ss[i])

# ---------- 里程牌 ----------
def parse_km(s):
    s = (s or '').strip()
    m = re.match(r'^(\d+)\s*[Kk]\s*\+?\s*(\d+)', s)
    if m: return int(m[1])+int(m[2])/1000
    m = re.match(r'^(\d+(?:\.\d+)?)\s*(?:[Kk]|km)?$', s)
    if m: return float(m[1])
    return None
MS = collections.defaultdict(list)
for m in D['ms']:
    k = parse_km(m['d'])
    if k is not None and m['n']: MS[m['n'].replace('臺', '台')].append((k, (m['lat'], m['lon'])))
for k in MS:  # 同一里程多個(雙向各一)只留一個平均
    g = collections.defaultdict(list)
    for km, p in MS[k]: g[round(km, 3)].append(p)
    MS[k] = sorted((km, (sum(p[0] for p in v)/len(v), sum(p[1] for p in v)/len(v))) for km, v in g.items())

def anchors_ms(net, a, b, near=None):
    lo, hi = min(a, b), max(a, b)
    L = [x for x in MS.get(net, []) if lo-1.01 <= x[0] <= hi+1.01]
    if near: L = [x for x in L if dist(x[1], near) < 40000]
    # 去掉位置不連續的(里程牌資料錯誤):相鄰 0.5 公里卻差很遠
    L = sorted(L)
    ok = []
    for x in L:
        if ok and dist(ok[-1][1], x[1]) > (x[0]-ok[-1][0])*1000*2.5+300: continue
        ok.append(x)
    return ok

# ---------- 交流道 ----------
def anchors_jn(ref, a, b, near):
    wf = wf_ref(ref); L = collections.defaultdict(list)
    for j in D['jn']:
        if not re.match(r'^\d+[A-Z]?$', j['ref']): continue
        k = float(re.match(r'\d+', j['ref'])[0])
        if not (min(a, b)-6 <= k <= max(a, b)+6): continue
        p = (j['lat'], j['lon'])
        if dist(p, near) > 30000: continue
        # 必須在這條快速道路旁
        if not any(wf(WAYS[wi]) for d, n in nodes_near(p, 80)[:30] for _, _, wi in ADJ.get(n, ())): continue
        L[k].append(p)
    return sorted((k, (sum(p[0] for p in v)/len(v), sum(p[1] for p in v)/len(v))) for k, v in L.items())

# ---------- 道路起點累計里程(縣道、市道) ----------
def anchors_cum(ref, end, a, b, near, cr=30000):
    wf0 = wf_ref(ref); ns = set()
    wf = lambda w: wf0(w) and any(dist(p, near) < cr for p in w['g'][::max(1, len(w['g'])//4)]+[w['g'][-1]])
    for w in WAYS:
        if wf(w): ns.update(w['nodes'])
    if not ns: return []
    key = {'W': lambda n: XY[n][1], 'E': lambda n: -XY[n][1], 'N': lambda n: -XY[n][0], 'S': lambda n: XY[n][0]}[end]
    start = min(ns, key=key)
    # 只沿這條路(雙向)算距離
    UND = collections.defaultdict(list)
    for w in WAYS:
        if not wf(w): continue
        for i in range(len(w['nodes'])-1):
            x, y = w['nodes'][i], w['nodes'][i+1]; L = dist(w['g'][i], w['g'][i+1]); UND[x].append((y, L)); UND[y].append((x, L))
    best = {start: 0}; h = [(0, start)]
    while h:
        c, n = heapq.heappop(h)
        if c > best[n]: continue
        for m, L in UND[n]:
            if c+L < best.get(m, 1e18): best[m] = c+L; heapq.heappush(h, (c+L, m))
    out = []
    for km in sorted(set([min(a, b)-.3, max(a, b)+.3, (a+b)/2])):
        cand = [(abs(c-km*1000), n) for n, c in best.items() if abs(c-km*1000) < 150]
        if cand: out.append((km, XY[min(cand)[1]]))
    return out

def directed(anchors_sorted, a, b, wf, fixlen=False):
    """依行進方向 a→b 串出折線並切出 a~b"""
    inc = b > a
    an = sorted(anchors_sorted, key=lambda x: x[0], reverse=not inc)
    # 只留包住 a~b 的
    lo, hi = min(a, b), max(a, b)
    inner = [x for x in an if lo <= x[0] <= hi]
    before = [x for x in an if (x[0] < lo if inc else x[0] > hi)]
    after = [x for x in an if (x[0] > hi if inc else x[0] < lo)]
    sel = (before[-1:] if before else []) + inner + (after[:1] if after else [])
    if len(sel) < 2: return None
    P, pos = route_through(sel, wf)
    if not P: return None
    s0, s1 = km_to_s(pos, a), km_to_s(pos, b)
    if s0 is None or s1 is None or s1 <= s0: return None
    T = cum(P)[-1]
    if fixlen:  # 交流道、累計里程不夠準:中心點照里程,長度照公告
        L = abs(b-a)*1000; m = (s0+s1)/2; s0, s1 = m-L/2, m+L/2
        if s0 < 0: s1 -= s0; s0 = 0
        if s1 > T: s0 = max(0, s0-(s1-T)); s1 = T
    return cut(P, max(0, s0), min(T, s1))

def path_between(p, q, wf, snap=120):
    src = {n: d*2 for d, n in nodes_near(p, snap)[:60]}; tg = {n: d*2 for d, n in nodes_near(q, snap)[:60]}
    if not src or not tg: return None
    path = dijkstra(src, tg, wf, maxc=dist(p, q)*3+3000)
    return [XY[n] for n in path] if path else None

def name_ends(names, near, r=6000):
    wf = wf_name(*names); pts = []
    for w in WAYS:
        if wf(w) and any(dist(x, near) < r for x in w['g'][::max(1, len(w['g'])//5)]+[w['g'][-1]]): pts += w['g']
    if not pts: return None
    # 最遠的兩點
    a = max(pts, key=lambda x: dist(x, near)); b = max(pts, key=lambda x: dist(x, a))
    return a, b, wf

def crossing(road, other, near, r=3000):
    A = set(); B = set()
    for w in WAYS:
        if not any(dist(x, near) < r for x in w['g'][::max(1, len(w['g'])//5)]+[w['g'][-1]]): continue
        if road in w['name']: A.update(w['nodes'])
        if other in w['name']: B.update(w['nodes'])
    c = A & B
    if not c: return None
    return XY[min(c, key=lambda n: dist(XY[n], near))]

def extend(P0, wf, length, toward=None):
    return P0

def plen(P): return cum(P)[-1]
def same(P, Q):
    return max(project(Q, p)[0] for p in P[::max(1, len(P)//20)]) < 18

# ---------- 路段清單 ----------
B = 'b'; F = 'f'
SPECS = [
 # 省道(公路局里程牌)
 dict(id='t9-56', n='台9線 北宜公路(頭城)56.6K~68.6K', t='ms', net='台9線', a=56.6, b=68.6, dir=B, lim=40, pt=(24.849024, 121.79389)),
 dict(id='t9-gy', n='台9線 蘇花改 觀音隧道', t='name', names=['觀音隧道'], dir=B, lim=70, pt=(24.433311, 121.77481), r=9000),
 dict(id='t9-gf', n='台9線 蘇花改 谷風隧道', t='name', names=['谷風隧道'], dir=B, lim=70, pt=(24.365217, 121.77798), r=9000),
 dict(id='t9-da', n='台9線 蘇花改 東澳隧道', t='name', names=['東澳隧道'], dir=B, lim=70, pt=(24.536793, 121.836655), r=9000),
 dict(id='t3-82', n='台3線 峨眉 82.2K~84.3K', t='ms', net='台3線', a=82.2, b=84.3, dir=B, lim=60, pt=(24.70351, 121.04712)),
 dict(id='t13a-8', n='台13甲線 造橋 8.3K~9.5K', t='ms', net='台13甲線', a=8.3, b=9.5, dir=B, lim=60, pt=(24.632866, 120.85721)),
 dict(id='t13a-9', n='台13甲線 造橋 9.8K~11K', t='ms', net='台13甲線', a=9.8, b=11.0, dir=B, lim=60, pt=(24.632866, 120.85721)),
 dict(id='t3-103', n='台3線 三灣 103.2K~108K', t='ms', net='台3線', a=103.2, b=108.0, dir=B, lim=60, pt=(24.61412, 120.952415)),
 dict(id='t3-114', n='台3線 114.3K~123.6K', t='ms', net='台3線', a=114.3, b=123.6, dir=B, lim=60, pt=(24.61412, 120.952415)),
 dict(id='t21-n', n='台21線 魚池 53.8K~51.1K(北向)', t='ms', net='台21線', a=53.8, b=51.1, dir=F, lim=60, pt=(23.94172, 120.92913)),
 dict(id='t21-s', n='台21線 魚池 51.1K~53.9K(南向)', t='ms', net='台21線', a=51.1, b=53.9, dir=F, lim=60, pt=(23.94172, 120.92913)),
 dict(id='t1-429', n='台1線 佳冬戰備道 429.5K~433K', t='ms', net='台1線', a=429.5, b=433.0, dir=B, lim=70, pt=(22.442274, 120.56305)),
 dict(id='t26-8', n='台26線 尖山段 8.5K~13.7K', t='ms', net='台26線', a=8.5, b=13.7, dir=B, lim=70, pt=(22.140097, 120.70218)),
 dict(id='t9-cp', n='台9線 南迴 草埔隧道', t='name', names=['草埔隧道'], dir=B, lim=70, pt=(22.241491, 120.805786), r=8000),
 dict(id='t11-126', n='台11線 成功(小馬)126.13K~129.61K', t='ms', net='台11線', a=126.13, b=129.61, dir=B, lim=60, pt=(22.980171, 121.30966)),
 dict(id='t11-24', n='台11線 壽豐 24.1K~26.6K', t='ms', net='台11線', a=24.1, b=26.6, dir=B, lim=50, pt=(23.778915, 121.56065)),
 dict(id='t7b-5', n='台7乙線 三峽 5.3K~8.1K', t='ms', net='台7乙線', a=5.3, b=8.1, dir=B, lim=40, pt=(24.870596, 121.37518)),
 dict(id='t2-73', n='台2線 瑞芳 73.7K~79.6K', t='ms', net='台2線', a=73.7, b=79.6, dir=B, lim=60, pt=(25.120869, 121.82302)),
 dict(id='t2-79', n='台2線 瑞芳 79.7K~84K', t='ms', net='台2線', a=79.7, b=84.0, dir=B, lim=60, pt=(25.123339, 121.8755)),
 dict(id='t2-85', n='台2線 貢寮 85.8K~87.5K', t='ms', net='台2線', a=85.8, b=87.5, dir=B, lim=50, pt=(25.112902, 121.912)),
 dict(id='t2-105', n='台2線 貢寮 105.8K~113.2K', t='ms', net='台2線', a=105.8, b=113.2, dir=B, lim=60, pt=(25.0158, 121.98824)),
 dict(id='t9-19', n='台9線 石碇 19K~23.1K', t='ms', net='台9線', a=19.0, b=23.1, dir=B, lim=40, pt=(24.95693, 121.623634)),
 dict(id='t9-26', n='台9線 坪林 26.2K~32.2K', t='ms', net='台9線', a=26.2, b=32.2, dir=B, lim=40, pt=(24.943071, 121.6709)),
 dict(id='t9-33', n='台9線 坪林 33.3K~37.2K', t='ms', net='台9線', a=33.3, b=37.2, dir=B, lim=40, pt=(24.936045, 121.70352)),
 dict(id='t3-389', n='台3線 內門 389.5K~392.5K', t='ms', net='台3線', a=389.5, b=392.5, dir=B, lim=60, pt=(22.975607, 120.46869)),
 dict(id='t3-30', n='台3線 大溪 30.5K~31.8K', t='ms', net='台3線', a=30.5, b=31.8, dir=B, lim=50, pt=(24.893774, 121.32434)),
 dict(id='t3-50', n='台3線 龍潭 50.5K~51.7K', t='ms', net='台3線', a=50.5, b=51.7, dir=B, lim=60, pt=(24.85213, 121.204475)),
 dict(id='t1a-18', n='台1甲線 龜山 萬壽路一段 18.8K~20K', t='ms', net='台1甲線', a=18.8, b=20.0, dir=B, lim=50, pt=(25.01177, 121.37562)),
 # 快速道路(交流道里程)
 dict(id='t61-122n', n='台61線 通霄 122.6K~115.6K(北向)', t='jn', ref='61', a=122.6, b=115.6, dir=F, lim=90, pt=(24.494154, 120.67632)),
 dict(id='t61-122s', n='台61線 通霄 122.2K~130.2K(南向)', t='jn', ref='61', a=122.2, b=130.2, dir=F, lim=90, pt=(24.494154, 120.67632)),
 dict(id='t61-177', n='台61線 鹿港 177K~168.1K(北向)', t='jn', ref='61', a=177.0, b=168.1, dir=F, lim=90, pt=(24.081823, 120.42038)),
 dict(id='t61-157n', n='台61線 清水 157.8K~151.6K(北向)', t='jn', ref='61', a=157.8, b=151.6, dir=F, lim=90, pt=(24.21861, 120.52289)),
 dict(id='t61-148s', n='台61線 清水 148.1K~156.4K(南向)', t='jn', ref='61', a=148.1, b=156.4, dir=F, lim=90, pt=(24.21861, 120.52289)),
 dict(id='t62-ml', n='台62線 瑪陵隧道(西向)', t='name', names=['瑪陵隧道'], dir=F, west=True, lim=70, pt=(25.128988, 121.697014), r=3000),
 dict(id='t62-11', n='台62線 暖暖 11.3K~6.2K(西向)', t='jn', ref='62', a=11.3, b=6.2, dir=F, lim=80, pt=(25.10219, 121.7531)),
 dict(id='t64-21', n='台64線 中和 21.4K~23.2K(東向)', t='jn', ref='64', a=21.4, b=23.2, dir=F, lim=70, pt=(25.018978, 121.47077)),
 dict(id='t64-25', n='台64線 中和 25.2K~28.2K', t='jn', ref='64', a=25.2, b=28.2, dir=B, lim=70, pt=(24.994034, 121.49126)),
 dict(id='t64-1', n='台64線 八里 1.6K~5.4K(西向)', t='jn', ref='64', a=5.4, b=1.6, dir=F, lim=80, pt=(25.111614, 121.422195)),
 dict(id='t65-7', n='台65線 新莊 7.9K~4.5K(北向)', t='jn', ref='65', a=7.9, b=4.5, dir=F, lim=80, pt=(24.999134, 121.451256)),
 # 縣道、市道(道路起點累計)
 dict(id='c140-16', n='縣道140線 三義 16.2K~16.9K', t='cum', ref='140', end='W', a=16.2, b=16.9, dir=B, lim=60, pt=(24.345043, 120.744514)),
 dict(id='c140-23', n='縣道140線 三義 23.1K~25.1K', t='cum', ref='140', end='W', a=23.1, b=25.1, dir=B, lim=60, pt=(24.345043, 120.744514)),
 dict(cr=80000, id='c182-27e', n='市道182線 龍崎 27.22K~28.36K(往高雄)', t='cum', ref='182', end='W', a=27.2248, b=28.358, dir=F, lim=50, pt=(22.950447, 120.38326)),
 dict(cr=80000, id='c182-27w', n='市道182線 龍崎 28.34K~27.19K(往關廟)', t='cum', ref='182', end='W', a=28.3378, b=27.1907, dir=F, lim=50, pt=(22.950447, 120.38326)),
 dict(cr=80000, id='c182-28', n='市道182線 內門 28.9K~31.8K', t='cum', ref='182', end='W', a=28.9, b=31.8, dir=B, lim=50, pt=(22.924803, 120.421616)),
 dict(cr=90000, id='t9d-59', n='台9丁線 秀林 59.5K~64K', t='cum', ref='9丁', end='N', a=59.5, b=64.0, dir=B, lim=40, pt=(24.245474, 121.72361)),
 # 隧道、市區道路(名稱、路口)
 dict(id='tp-zq', n='自強隧道', t='name', names=['自強隧道'], dir=B, lim=50, pt=(25.090601, 121.549255)),
 dict(id='tp-xh', n='辛亥隧道', t='name', names=['辛亥隧道'], dir=B, lim=50, pt=(25.011496, 121.5559)),
 dict(id='t15-fb', n='台15線 鳳鼻隧道', t='name', names=['鳳鼻'], dir=B, lim=60, pt=(24.87992, 120.95467)),
 dict(id='t9-rs', n='台9線 蘇花改 仁水隧道', t='name', names=['仁水隧道'], dir=B, lim=60, pt=(24.227335, 121.69864)),
 dict(id='t9-zr', n='台9線 蘇花改 中仁隧道', t='name', names=['中仁隧道'], dir=B, lim=70, pt=(24.266958, 121.7247)),
 dict(id='km-br', n='金門大橋', t='name', names=['金門大橋'], dir=B, lim=60, pt=(24.452068, 118.303474)),
 dict(id='ks-sy', n='高雄 鳥松 松藝路', t='name', names=['松藝路'], dir=B, lim=50, pt=(22.669724, 120.34302), r=2500),
 dict(id='ntp-ss', n='新莊 壽山路(往新莊)', t='name', names=['壽山路'], dir=F, east=True, lim=40, pt=(25.043957, 121.39826), r=1500),
 dict(id='tc-xs', n='台中 向上路六段(中興路口→自立路口,東往西)', t='plen', names=['向上路'], L=1601, dir=F, west=True, lim=50, pt=(24.202772, 120.568183)),
 dict(id='ntp-hh', n='新店 環河路(中央路~白馬寺)', t='xlen', road='環河路', x1='中央路', L=1500, dir=B, lim=60, pt=(24.97182, 121.529236)),
 dict(id='ty-qs', n='龜山 青山路二段', t='xlen', road='青山路', x1='文青路', L=1700, dir=B, lim=50, pt=(25.031464, 121.39822)),
 dict(id='kl-62a', n='台62甲線 3號隧道出口~東海街出口(南往北)', t='plen', ref='62甲', L=1700, dir=F, north=True, lim=50, pt=(25.124674, 121.77938)),
]

out = []; rep = []
def emit(sp, P, suffix='', dir_=F):
    L = plen(P)
    out.append({'id': sp['id']+suffix, 'n': sp['n'], 'lim': sp['lim'], 'dir': dir_, 'len': round(L), 'p': [[round(x[0], 6), round(x[1], 6)] for x in P]})
    d0 = min(project(P, sp['pt'])[0], 99999) if sp.get('pt') else -1
    rep.append(f"{sp['id']+suffix:14s} {sp['n'][:30]:30s} {dir_} {L:7.0f}m  離公告點 {d0:6.0f}m")

def both(sp, mk):
    """雙向路段:兩個方向各串一次;路線重疊(沒有分隔島)就合成一筆;一個方向失敗或繞遠路就用另一個方向當雙向"""
    P1 = mk(False); P2 = mk(True)
    if P1 and P2:
        l1, l2 = plen(P1), plen(P2)
        if l1 > l2*1.4: P1 = None
        elif l2 > l1*1.4: P2 = None
    if P1 and P2 and same(P1, P2): emit(sp, P1, '', B)
    elif P1 and P2:
        emit(sp, P1, '-a', F); emit(sp, P2, '-b', F)
    elif P1 or P2: emit(sp, P1 or P2, '', B)
    else: rep.append(f"{sp['id']:14s} ❌ 失敗")

for sp in SPECS:
    t = sp['t']
    try:
        if t in ('ms', 'jn', 'cum'):
            if t == 'ms':
                an = anchors_ms(sp['net'], sp['a'], sp['b'], sp['pt']); ref = re.sub('[台線]', '', sp['net']); wf = wf_ref(ref)
            elif t == 'jn':
                an = anchors_jn(sp['ref'], sp['a'], sp['b'], sp['pt']); wf = wf_ref(sp['ref'])
            else:
                an = anchors_cum(sp['ref'], sp['end'], sp['a'], sp['b'], sp['pt'], sp.get('cr', 30000)); wf = wf_ref(sp['ref'])
            if len(an) < 2: rep.append(f"{sp['id']:14s} ❌ 錨點不足 {len(an)}"); continue
            if sp['dir'] == F:
                P = directed(an, sp['a'], sp['b'], wf, t != 'ms')
                if P: emit(sp, P)
                else: rep.append(f"{sp['id']:14s} ❌ 串線失敗")
            else:
                a, b = min(sp['a'], sp['b']), max(sp['a'], sp['b'])
                fx = t != 'ms'
                both(sp, lambda rev: directed(an, b, a, wf, fx) if rev else directed(an, a, b, wf, fx))
        elif t == 'name':
            r = name_ends(sp['names'], sp['pt'], sp.get('r', 6000))
            if not r: rep.append(f"{sp['id']:14s} ❌ 找不到道路"); continue
            a, b, wf = r
            if sp.get('east') and a[1] > b[1]: a, b = b, a
            if sp.get('west') and a[1] < b[1]: a, b = b, a
            if sp['dir'] == F:
                P = path_between(a, b, wf)
                if P: emit(sp, P)
                else: rep.append(f"{sp['id']:14s} ❌")
            else: both(sp, lambda rev: path_between(b, a, wf) if rev else path_between(a, b, wf))
        elif t == 'xing':
            p = crossing(sp['road'], sp['x1'], sp['pt']); q = crossing(sp['road'], sp['x2'], sp['pt'])
            if not p or not q: rep.append(f"{sp['id']:14s} ❌ 路口 {p} {q}"); continue
            P = path_between(p, q, wf_name(sp['road']), 40)
            if P: emit(sp, P)
            else: rep.append(f"{sp['id']:14s} ❌")
        elif t == 'xlen':
            p = crossing(sp['road'], sp['x1'], sp['pt'])
            if not p: rep.append(f"{sp['id']:14s} ❌ 路口"); continue
            wf = wf_name(sp['road']); ends = name_ends([sp['road']], sp['pt'], 3000)
            far = max(ends[:2], key=lambda e: dist(e, p)) if ends else sp['pt']
            P = path_between(p, far, wf, 60)
            if not P: rep.append(f"{sp['id']:14s} ❌"); continue
            P = cut(P, 0, min(sp['L'], plen(P)))
            both(sp, lambda rev: (path_between(P[-1], P[0], wf, 60) if rev else P))
        elif t == 'plen':
            wf = wf_ref(sp['ref']) if sp.get('ref') else wf_name(*sp['names']); p = sp['pt']
            ns = set()
            for w in WAYS:
                if wf(w): ns.update(w['nodes'])
            key = (lambda x: x[0]) if sp.get('north') else (lambda x: -x[0]) if sp.get('south') else (lambda x: x[1]) if sp.get('east') else (lambda x: -x[1])
            far = max((XY[n] for n in ns if dist(XY[n], p) < 4000), key=key)
            P = path_between(p, far, wf, 80)
            if P: emit(sp, cut(P, 0, min(sp['L'], plen(P))))
            else: rep.append(f"{sp['id']:14s} ❌")
    except Exception as e:
        rep.append(f"{sp['id']:14s} ❌ {e!r}")

import time
json.dump({'v': 1, 't': time.strftime('%Y-%m-%d'), 'src': '警政署測速執法設置點、臺北/桃園/臺中科技執法資料;位置:公路局里程牌、OpenStreetMap', 's': out}, open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
print('\n'.join(rep)); print(len(out), '筆')
