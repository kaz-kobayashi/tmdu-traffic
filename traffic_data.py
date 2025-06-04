"""JARTIC交通データ取得・処理モジュール（モックデータ対応）"""
import requests
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import logging
import numpy as np
from shapely.geometry import Point
from config import JARTIC_API_URL, ROAD_TYPE, API_TIMEOUT

# モックデータモード設定
USE_MOCK_DATA = True

class TrafficDataFetcher:
    """JARTIC APIからの交通データ取得クラス（モックデータ対応）"""
    
    def __init__(self, api_url: str = JARTIC_API_URL, timeout: int = API_TIMEOUT, use_mock: bool = USE_MOCK_DATA):
        self.api_url = api_url
        self.timeout = timeout
        self.use_mock = use_mock
        self.logger = logging.getLogger(__name__)
    
    def fetch_traffic_data(self, bbox: Tuple[float, float, float, float], 
                          time_code: Optional[int] = None) -> Optional[gpd.GeoDataFrame]:
        """
        交通データ取得（モックデータ対応）
        
        Args:
            bbox: (minLon, minLat, maxLon, maxLat)
            time_code: YYYYMMDDhhmm形式（None時は現在時刻-5分）
            
        Returns:
            GeoDataFrame: 交通データ（None時はエラー）
        """
        if self.use_mock:
            self.logger.info("Using mock traffic data")
            return self._generate_mock_data(bbox)
        
        if time_code is None:
            time_code = self._get_current_time_code()
        
        try:
            url = self._build_api_url(bbox, time_code)
            self.logger.info(f"Fetching traffic data from API: time_code={time_code}")
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            gdf = self._parse_geojson_response(data)
            
            if gdf.empty:
                self.logger.warning("No traffic data returned from API, falling back to mock data")
                return self._generate_mock_data(bbox)
            
            # データ検証・クリーニング
            gdf = self.validate_traffic_data(gdf)
            self.logger.info(f"Successfully fetched {len(gdf)} traffic records")
            
            return gdf
            
        except requests.RequestException as e:
            self.logger.error(f"API request failed: {e}, falling back to mock data")
            return self._generate_mock_data(bbox)
        except Exception as e:
            self.logger.error(f"Data processing failed: {e}, falling back to mock data")
            return self._generate_mock_data(bbox)
    
    def _generate_mock_data(self, bbox: Tuple[float, float, float, float]) -> gpd.GeoDataFrame:
        """モック交通データ生成"""
        minx, miny, maxx, maxy = bbox
        
        # ランダムな観測点を生成（センター周辺）
        np.random.seed(42)  # 再現可能な結果のため
        n_points = 200  # 観測点数を増やして道路カバー率向上
        
        # 観測点の座標生成（BBOX内）
        lons = np.random.uniform(minx, maxx, n_points)
        lats = np.random.uniform(miny, maxy, n_points)
        
        # 混雑度に応じた速度データ生成
        # 都心部により近い場所は混雑する傾向
        center_lon, center_lat = (minx + maxx) / 2, (miny + maxy) / 2
        distances = np.sqrt((lons - center_lon)**2 + (lats - center_lat)**2)
        
        # 距離に基づく基準速度（近いほど遅い）
        base_speeds = 50 - (distances / distances.max()) * 30  # 20-50km/h
        
        # 時間帯による変動（現在時刻ベース）
        current_hour = datetime.now().hour
        if 7 <= current_hour <= 9 or 17 <= current_hour <= 19:  # 通勤ラッシュ
            speed_factor = 0.6
        elif 22 <= current_hour or current_hour <= 5:  # 深夜
            speed_factor = 1.3
        else:  # その他
            speed_factor = 1.0
        
        speeds = base_speeds * speed_factor
        speeds += np.random.normal(0, 5, n_points)  # ノイズ追加
        speeds = np.clip(speeds, 5, 80)  # 5-80km/hに制限
        
        # 旅行時間計算（仮想リンク長100m、速度から算出）
        link_lengths = np.random.uniform(50, 200, n_points)  # 50-200m
        travel_times = (link_lengths / 1000) / (speeds / 3600)  # 秒
        
        # 現在時刻コード生成
        current_time = datetime.now()
        time_code = int(current_time.strftime("%Y%m%d%H%M"))
        
        # データフレーム作成
        data = {
            '道路種別': [ROAD_TYPE] * n_points,
            '時間コード': [time_code] * n_points,
            '平均速度': speeds,
            '旅行時間': travel_times,
            'リンク長': link_lengths,
            'longitude': lons,
            'latitude': lats
        }
        
        df = pd.DataFrame(data)
        
        # ジオメトリ作成
        geometry = [Point(lon, lat) for lon, lat in zip(lons, lats)]
        
        # GeoDataFrame作成
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
        
        self.logger.info(f"Generated {len(gdf)} mock traffic data points")
        return gdf
    
    def _get_current_time_code(self) -> int:
        """現在時刻から5分前のtime_code生成"""
        now = datetime.now() - timedelta(minutes=5)
        # 5分単位に丸める
        minutes = (now.minute // 5) * 5
        time_str = now.strftime(f"%Y%m%d%H{minutes:02d}")
        return int(time_str)
    
    def _build_api_url(self, bbox: Tuple[float, float, float, float], 
                       time_code: int) -> str:
        """API URL構築"""
        return (
            f"{self.api_url}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typeNames=t_travospublic_measure_5m"
            f"&srsName=EPSG:4326&outputFormat=application/json"
            f"&exceptions=application/json"
            f"&cql_filter=道路種別={ROAD_TYPE} AND 時間コード={time_code} "
            f"AND BBOX(\"ジオメトリ\",{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},'EPSG:4326')"
        )
    
    def _parse_geojson_response(self, data: Dict[str, Any]) -> gpd.GeoDataFrame:
        """GeoJSON レスポンス解析"""
        if 'features' not in data or not data['features']:
            return gpd.GeoDataFrame()
        
        try:
            gdf = gpd.GeoDataFrame.from_features(data['features'], crs='EPSG:4326')
            
            # 必要な列の確認
            required_columns = ['道路種別', '時間コード', '平均速度', '旅行時間', 'リンク長']
            missing_columns = [col for col in required_columns if col not in gdf.columns]
            
            if missing_columns:
                self.logger.warning(f"Missing columns: {missing_columns}")
            
            return gdf
        
        except Exception as e:
            self.logger.error(f"Failed to parse GeoJSON response: {e}")
            return gpd.GeoDataFrame()
    
    def validate_traffic_data(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """交通データ検証・クリーニング"""
        if gdf.empty:
            return gdf
        
        original_count = len(gdf)
        
        # 異常値除外
        if '平均速度' in gdf.columns:
            # 負の値や極端に大きい値を除外
            before_count = len(gdf)
            gdf = gdf[(gdf['平均速度'] >= 0) & (gdf['平均速度'] <= 150)]  # 0-150km/h
            if len(gdf) < before_count:
                self.logger.info(f"Removed {before_count - len(gdf)} records with invalid speed")
        
        if '旅行時間' in gdf.columns:
            # 負の値除外
            before_count = len(gdf)
            gdf = gdf[gdf['旅行時間'] >= 0]
            if len(gdf) < before_count:
                self.logger.info(f"Removed {before_count - len(gdf)} records with invalid travel time")
        
        # 数値型変換
        numeric_columns = ['平均速度', '旅行時間', 'リンク長']
        for col in numeric_columns:
            if col in gdf.columns:
                gdf[col] = pd.to_numeric(gdf[col], errors='coerce')
        
        # ジオメトリがNaNの行を除外
        gdf = gdf.dropna(subset=['geometry'])
        
        cleaned_count = len(gdf)
        if cleaned_count < original_count:
            self.logger.info(f"Data cleaning: {original_count} -> {cleaned_count} records")
        
        return gdf


def test_traffic_fetcher():
    """交通データ取得テスト"""
    from config import BBOX_5KM
    
    fetcher = TrafficDataFetcher(use_mock=True)
    
    # ログ設定
    logging.basicConfig(level=logging.INFO)
    
    print("Testing JARTIC API connection (with mock fallback)...")
    traffic_data = fetcher.fetch_traffic_data(BBOX_5KM)
    
    if traffic_data is not None and not traffic_data.empty:
        print(f"✅ Successfully fetched {len(traffic_data)} traffic records")
        print(f"Columns: {list(traffic_data.columns)}")
        print(f"Speed range: {traffic_data['平均速度'].min():.1f} - {traffic_data['平均速度'].max():.1f} km/h")
        print(f"Sample data:")
        print(traffic_data[['平均速度', '旅行時間', 'リンク長']].head())
    else:
        print("❌ Failed to fetch traffic data")


if __name__ == "__main__":
    test_traffic_fetcher()