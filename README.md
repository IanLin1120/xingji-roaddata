# 行跡導航 離線道路資料

每週自動從 OpenStreetMap(Geofabrik 台灣資料)產生「行跡導航」App 離線用的道路資料:
道路、紅綠燈、轉彎路口、橋/地下道/高架、鐵路、平交道。

- 產生程式:`build.py`
- 自動執行:`.github/workflows/build.yml`(每週一次,也可在 Actions 頁手動執行)
- 下載檔:Releases 的 `data` 標籤,`manifest.json` + 每 0.5° 一個 `p_<lat>_<lon>.txt.gz`

資料 © OpenStreetMap contributors,依 ODbL 授權。
