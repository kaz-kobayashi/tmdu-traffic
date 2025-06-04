"""アプリケーション設定"""
from typing import Tuple

# 地理的設定
TMDU_CENTER: Tuple[float, float] = (35.7056, 139.7644)  # センター
BBOX_5KM: Tuple[float, float, float, float] = (139.7194, 35.6606, 139.8094, 35.7506)

# API設定
JARTIC_API_URL: str = "https://api.jartic-open-traffic.org/geoserver"
ROAD_TYPE: int = 3  # 一般道路
UPDATE_INTERVAL: int = 300  # 5分間隔（秒）
API_TIMEOUT: int = 30  # APIタイムアウト（秒）

# 可視化設定
CONGESTION_COLORS = {
    'low': '#00ff00',      # 緑：空いている（速度 >= 30km/h）
    'medium': '#ffff00',   # 黄：やや混雑（20-30km/h）
    'high': '#ff0000',     # 赤：混雑（< 20km/h）
    'unknown': '#808080'   # 灰：データなし
}

CONGESTION_THRESHOLDS = {
    'high_speed': 30,      # km/h
    'medium_speed': 20     # km/h
}

# 地図設定
MAP_ZOOM_LEVEL: int = 13
MAP_TILES: str = "OpenStreetMap"
ROAD_LINE_WIDTH: int = 3
ROAD_LINE_OPACITY: float = 0.8

# ファイルパス設定
ROAD_DATA_ZIP: str = "N01-07L-13-01.0a_GML.zip"
LOG_LEVEL: str = "INFO"