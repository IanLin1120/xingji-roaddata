#!/usr/bin/env python3
"""全台公車站牌 + 經過每個站牌的路線(交通部 TDX),給「行跡導航」離線用。

輸出(放在 out/):
  bus_<lat>_<lon>.txt.gz  每 0.5 度一包,每行「<格子>\t<json>」,格子 = floor(緯度/0.01)_floor(經度/0.01)
                          json = {"t":資料時間,"s":[[StopUID,站名,緯度,經度,縣市代碼,[[路線名,方向,往哪裡],...]],...]}
  bus.json                給 build.py 併進 manifest.json 的 "bus" 區塊

TDX 金鑰(GitHub Secrets 的 TDX_ID / TDX_KEY)有填就用;沒填就用免金鑰額度(每個 IP 每天約 50 次,這裡只用 23 次)。
抓取失敗時沿用 Releases 上一版的資料,不會讓 App 的公車資料消失。
"""
import gzip, json, math, os, sys, time, urllib.parse, urllib.request

CITIES = ['Taipei', 'NewTaipei', 'Taoyuan', 'Taichung', 'Tainan', 'Kaohsiung', 'Keelung', 'Hsinchu', 'HsinchuCounty',
          'MiaoliCounty', 'ChanghuaCounty', 'NantouCounty', 'YunlinCounty', 'ChiayiCounty', 'Chiayi', 'PingtungCounty',
          'YilanCounty', 'HualienCounty', 'TaitungCounty', 'KinmenCounty', 'PenghuCounty', 'LienchiangCounty']
G = 0.01   # App 站牌格子大小(和 3transit.js 的 BS.cells 一樣)
P = 0.5    # 每個下載包的範圍
REL = 'https://github.com/IanLin1120/xingji-roaddata/releases/download/data/'
UA = 'xingji-roaddata/1.0 (+https://github.com/IanLin1120/xingji-roaddata)'


def http(url, data=None, headers=None, timeout=180):
    h = {'User-Agent': UA, 'Accept-Encoding': 'gzip'}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        if r.headers.get('Content-Encoding') == 'gzip' or b[:2] == b'\x1f\x8b': b = gzip.decompress(b)
        return b


def token():
    cid, key = os.environ.get('TDX_ID', '').strip(), os.environ.get('TDX_KEY', '').strip()
    if not cid or not key: return None
    body = urllib.parse.urlencode({'grant_type': 'client_credentials', 'client_id': cid, 'client_secret': key}).encode()
    j = json.loads(http('https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token', body,
                        {'Content-Type': 'application/x-www-form-urlencoded'}, 60))
    return j['access_token']


def tdx(path, tok):
    url = 'https://tdx.transportdata.tw/api/basic/' + path + ('&' if '?' in path else '?') + '$format=JSON'
    last = None
    for i in range(6):
        try:
            return json.loads(http(url, headers={'Authorization': 'Bearer ' + tok} if tok else {}))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 403) and not tok: raise
            time.sleep(8 * (i + 1) if e.code == 429 else 4 * (i + 1))
        except Exception as e:
            last = e; time.sleep(4 * (i + 1))
    raise last


def zh(o): return (o or {}).get('Zh_tw') or (o or {}).get('En') or ''


def fallback(out, why):
    """這次抓不到:沿用 Releases 上一版的 bus 區塊(舊檔案還在 Releases 裡)"""
    print('bus: 抓取失敗,沿用上一版 —', why)
    try:
        m = json.loads(http(REL + 'manifest.json', timeout=60))
        if m.get('bus'):
            with open(os.path.join(out, 'bus.json'), 'w') as f: json.dump(m['bus'], f, ensure_ascii=False, separators=(',', ':'))
            print('bus: 已沿用上一版', m['bus'].get('t'))
    except Exception as e:
        print('bus: 也讀不到上一版', e)


def main():
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    try: tok = token()
    except Exception as e: print('bus: TDX 金鑰驗證失敗,改用免金鑰額度', e); tok = None
    print('bus: 使用', 'TDX 金鑰' if tok else '免金鑰額度')
    stops = {}   # uid -> [uid, name, lat, lon, city, {(route,dir): dest}]
    ok = 0
    for city in CITIES + ['InterCity']:
        base = ('v2/Bus/StopOfRoute/InterCity' if city == 'InterCity' else f'v2/Bus/StopOfRoute/City/{city}') + '?$select=RouteName,Direction,Stops&$top=1000&$skip='
        try:
            # TDX 沒指定筆數時只回 30 筆:每次 1000 條路線分頁抓到完
            L = []
            for sk in range(0, 60000, 1000):
                pg = tdx(base + str(sk), tok); L += pg
                if len(pg) < 1000: break
        except Exception as e:
            print('bus:', city, '失敗', e)
            if not tok and getattr(e, 'code', 0) in (401, 403, 429): return fallback(out, f'{city}: {e}')
            continue
        ok += 1; n0 = len(stops)
        for r in L:
            rn, d = zh(r.get('RouteName')), int(r.get('Direction') or 0)
            ss = sorted(r.get('Stops') or [], key=lambda s: s.get('StopSequence') or 0)
            if not rn or not ss: continue
            dest = zh(ss[-1].get('StopName'))
            for s in ss:
                uid, p = s.get('StopUID'), s.get('StopPosition') or {}
                la, lo = p.get('PositionLat'), p.get('PositionLon')
                if not uid or not la or not lo: continue
                e = stops.get(uid)
                if not e: e = stops[uid] = [uid, zh(s.get('StopName')), round(la, 6), round(lo, 6), city, {}]
                if s is not ss[-1]: e[5][(rn, d)] = dest   # 終點站不列「往 終點」
        print(f'bus: {city} 路線 {len(L)},新增站牌 {len(stops) - n0}')
        time.sleep(0.4 if tok else 1.5)
    if ok < 12 or len(stops) < 20000: return fallback(out, f'只成功 {ok} 個縣市、{len(stops)} 個站牌')
    stamp = int(time.time() * 1000)
    cells = {}
    for e in stops.values():
        k = f'{math.floor(e[2] / G + 1e-9)}_{math.floor(e[3] / G + 1e-9)}'
        cells.setdefault(k, []).append([e[0], e[1], e[2], e[3], e[4], sorted([[rn, d, dst] for (rn, d), dst in e[5].items()])])
    packs = {}
    for k in cells:
        a, b = map(int, k.split('_')); packs.setdefault(f'{math.floor(a * G / P + 1e-9)}_{math.floor(b * G / P + 1e-9)}', []).append(k)
    man = {'v': 2, 't': stamp, 'g': G, 'p': P, 'stops': len(stops), 'packs': {}}
    for pk, ks in sorted(packs.items()):
        fn = f'bus_{pk}.txt.gz'
        with gzip.open(os.path.join(out, fn), 'wt', encoding='utf-8', compresslevel=9) as f:
            for k in sorted(ks): f.write(k + '\t' + json.dumps({'v': 2, 't': stamp, 's': cells[k]}, ensure_ascii=False, separators=(',', ':')) + '\n')
        a, b = map(int, pk.split('_'))
        man['packs'][pk] = {'f': fn, 'bb': [a * P, b * P, (a + 1) * P, (b + 1) * P], 'cells': len(ks),
                            'stops': sum(len(cells[k]) for k in ks), 'size': os.path.getsize(os.path.join(out, fn))}
    with open(os.path.join(out, 'bus.json'), 'w') as f: json.dump(man, f, ensure_ascii=False, separators=(',', ':'))
    print(f"bus: {len(stops)} 站牌,{len(cells)} 格,{len(packs)} 包,{sum(p['size'] for p in man['packs'].values())/1048576:.1f} MB")


if __name__ == '__main__': main()
