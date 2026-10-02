#!/usr/bin/env python3
"""3D 導航地圖(向量圖磚)打包:把 planetiler 產生的 mbtiles 拆成 App 用的資料包。
z0~10 放在 v_base,z11~14 依圖磚中心每 0.5° 一包。每包是 gzip 的二進位串:
  [z:1 byte][x:4 bytes][y:4 bytes][len:4 bytes][pbf 資料(已解壓)] 重複
用法: python3 vec.py taiwan.mbtiles out/
"""
import sys, os, sqlite3, gzip, struct, math, json
P = 0.5
def tile_center(z, x, y):
    n = 2 ** z; lon = (x + .5) / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + .5) / n)))); return lat, lon
def main():
    src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
    db = sqlite3.connect(src); files = {}; info = {}
    def w(key, z, x, y, data):
        f = files.get(key)
        if f is None:
            f = files[key] = gzip.open(os.path.join(out, f'v_{key}.bin.gz'), 'wb', compresslevel=6); info[key] = {'n': 0}
        f.write(struct.pack('>BIII', z, x, y, len(data))); f.write(data); info[key]['n'] += 1
    for z, col, row, data in db.execute('select zoom_level, tile_column, tile_row, tile_data from tiles'):
        y = (2 ** z - 1) - row
        if data[:2] == b'\x1f\x8b': data = gzip.decompress(data)
        if z <= 10: w('base', z, col, y, data)
        else:
            lat, lon = tile_center(z, col, y); w(f"{math.floor(lat / P)}_{math.floor(lon / P)}", z, col, y, data)
    for f in files.values(): f.close()
    man = {'packs': {}}
    for k, v in info.items():
        fn = f'v_{k}.bin.gz'; e = {'f': fn, 'n': v['n'], 'size': os.path.getsize(os.path.join(out, fn))}
        if k != 'base':
            a, b = map(int, k.split('_')); e['bb'] = [a * P, b * P, (a + 1) * P, (b + 1) * P]
        man['packs'][k] = e
    with open(os.path.join(out, 'vec.json'), 'w') as f: json.dump(man, f, separators=(',', ':'))
    print(len(files), 'vec packs', round(sum(e['size'] for e in man['packs'].values()) / 1048576, 1), 'MB', sum(e['n'] for e in man['packs'].values()), 'tiles')
if __name__ == '__main__': main()
