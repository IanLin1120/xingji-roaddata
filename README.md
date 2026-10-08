# 行跡導航 離線資料

每週自動從 OpenStreetMap(Geofabrik 台灣資料)產生「行跡導航」App 離線用的資料,放在 Releases 的 `data` 標籤:

| 檔案 | 內容 |
|---|---|
| `manifest.json` | 檔案清單、大小、資料日期 |
| `p_<lat>_<lon>.txt.gz` | 道路、紅綠燈、轉彎路口、橋/地下道/高架、鐵路、平交道(每 0.5° 一包) |
| `bike.txt.gz` | 全台自行車道 |
| `ped.json` | 地圖上標成行人路、其實汽機車可以走的街道白名單(導航用) |
| `bus_<lat>_<lon>.txt.gz` | 全台公車站牌、經過每個站牌的路線與方向(交通部 TDX,每 0.5° 一包) |
| `v_base.bin.gz`、`v_<lat>_<lon>.bin.gz` | 3D 導航地圖(OpenMapTiles 格式向量圖磚,由 Planetiler 產生) |

- 產生程式:`build.py`(道路、自行車道)、`vec.py`(向量圖磚打包)
- 自動執行:`.github/workflows/build.yml`(每週一次,也可在 Actions 頁手動 Run workflow)
- 公車站牌:`bus.py`、`.github/workflows/bus.yml`(每週一次)。在 Settings → Secrets and variables → Actions 加上 `TDX_ID`、`TDX_KEY`(TDX 會員的 Client Id / Secret)會更穩定;沒加也能用免金鑰額度。
- 公車資料來源:交通部 TDX 運輸資料流通服務

資料 © OpenStreetMap contributors,依 ODbL 授權。
