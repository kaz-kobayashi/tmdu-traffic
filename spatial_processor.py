"""空間データ統合処理モジュール"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from typing import Optional, Dict, Any
import logging
import numpy as np

class SpatialProcessor:
    """空間データ統合処理クラス"""
    
    def __init__(self, max_distance: float = 50.0):
        self.max_distance = max_distance  # 最大マッチング距離（メートル）
        self.logger = logging.getLogger(__name__)
        self._road_gdf = None  # 道路データを保存
    
    def join_traffic_roads(self, traffic_gdf: gpd.GeoDataFrame, 
                          road_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        交通データと道路データの空間結合
        
        Args:
            traffic_gdf: 交通データ（点データ）
            road_gdf: 道路データ（線データ）
            
        Returns:
            GeoDataFrame: 結合済みデータ
        """
        if traffic_gdf.empty or road_gdf.empty:
            self.logger.warning("Input data is empty")
            return gpd.GeoDataFrame()
        
        try:
            self.logger.info(f"Starting spatial join: {len(traffic_gdf)} traffic points, "
                           f"{len(road_gdf)} road segments")
            
            # CRS の確認と統一
            if traffic_gdf.crs != road_gdf.crs:
                self.logger.info("CRS mismatch detected, converting to EPSG:4326")
                traffic_gdf = traffic_gdf.to_crs('EPSG:4326')
                road_gdf = road_gdf.to_crs('EPSG:4326')
            
            # メートル単位のCRSに変換（距離計算のため）
            traffic_utm = traffic_gdf.to_crs('EPSG:3857')
            road_utm = road_gdf.to_crs('EPSG:3857')
            
            # 道路データから必要な列のみ選択
            road_columns = ['road_id', 'geometry']
            if 'road_name' in road_gdf.columns:
                road_columns.append('road_name')
            if 'road_class' in road_gdf.columns:
                road_columns.append('road_class')
            
            road_utm_selected = road_utm[road_columns].copy()
            
            # 最近傍結合
            self.logger.info(f"Performing spatial join with max distance: {self.max_distance}m")
            
            joined = gpd.sjoin_nearest(
                traffic_utm, 
                road_utm_selected, 
                how='left',
                max_distance=self.max_distance,
                distance_col='distance_to_road'
            )
            
            # 元のCRSに戻す
            joined = joined.to_crs('EPSG:4326')
            
            # 結合結果の統計
            matched_count = joined['road_id'].notna().sum()
            total_count = len(joined)
            match_rate = matched_count / total_count if total_count > 0 else 0
            
            # 距離統計
            if 'distance_to_road' in joined.columns:
                distances = joined['distance_to_road'].dropna()
                if not distances.empty:
                    avg_distance = distances.mean()
                    max_distance = distances.max()
                    self.logger.info(f"Distance stats - avg: {avg_distance:.1f}m, max: {max_distance:.1f}m")
            
            self.logger.info(f"Spatial join completed: {matched_count}/{total_count} "
                           f"({match_rate:.1%}) matched")
            
            # 道路データを保存（集約で使用）
            self._road_gdf = road_gdf
            
            return joined
            
        except Exception as e:
            self.logger.error(f"Spatial join failed: {e}")
            return gpd.GeoDataFrame()
    
    def aggregate_by_road(self, joined_gdf: gpd.GeoDataFrame, road_gdf: gpd.GeoDataFrame = None) -> gpd.GeoDataFrame:
        """
        道路ごとのデータ集約
        
        Args:
            joined_gdf: 空間結合済みデータ
            
        Returns:
            GeoDataFrame: 道路ごと集約データ
        """
        if joined_gdf.empty or 'road_id' not in joined_gdf.columns:
            self.logger.warning("No valid data for aggregation")
            return gpd.GeoDataFrame()
        
        # 道路IDが有効なデータのみ
        valid_data = joined_gdf[joined_gdf['road_id'].notna()].copy()
        
        if valid_data.empty:
            self.logger.warning("No matched data for aggregation")
            return gpd.GeoDataFrame()
        
        self.logger.info(f"Aggregating {len(valid_data)} records by road_id")
        
        # 数値列の特定
        numeric_columns = ['平均速度', '旅行時間', 'リンク長']
        available_numeric = [col for col in numeric_columns if col in valid_data.columns]
        
        if not available_numeric:
            self.logger.warning("No numeric columns found for aggregation")
            return gpd.GeoDataFrame()
        
        # 集約関数の定義
        agg_functions = {}
        
        # 数値列は平均値
        for col in available_numeric:
            agg_functions[col] = 'mean'
        
        # 文字列列は最初の値
        string_columns = ['road_name', 'road_class']
        for col in string_columns:
            if col in valid_data.columns:
                agg_functions[col] = 'first'
        
        # 距離は平均
        if 'distance_to_road' in valid_data.columns:
            agg_functions['distance_to_road'] = 'mean'
        
        try:
            # 道路ごと集約
            aggregated = valid_data.groupby('road_id').agg(agg_functions).reset_index()
            
            # 観測点数を手動で追加
            observation_counts = valid_data.groupby('road_id').size().reset_index(name='observation_count')
            aggregated = aggregated.merge(observation_counts, on='road_id', how='left')
            
            # ジオメトリの取得（道路の線形状）
            # 元の道路データから正しいジオメトリを取得
            if self._road_gdf is not None:
                road_geom_dict = {}
                for road_id in aggregated['road_id']:
                    # 元の道路データから該当道路のジオメトリを取得
                    matching_roads = self._road_gdf[self._road_gdf['road_id'] == road_id]
                    if not matching_roads.empty:
                        road_geom_dict[road_id] = matching_roads.iloc[0]['geometry']
                
                # ジオメトリを追加
                aggregated['geometry'] = aggregated['road_id'].map(road_geom_dict)
                
                # GeoDataFrame として作成
                result_gdf = gpd.GeoDataFrame(aggregated, geometry='geometry', crs='EPSG:4326')
            else:
                self.logger.warning("No road geometry data available")
                result_gdf = gpd.GeoDataFrame(aggregated)
            
            # 統計情報のログ出力
            road_count = len(result_gdf)
            avg_observations = result_gdf['observation_count'].mean() if 'observation_count' in result_gdf.columns else 0
            
            self.logger.info(f"Aggregation completed: {road_count} unique roads, "
                           f"avg {avg_observations:.1f} observations per road")
            
            return result_gdf
            
        except Exception as e:
            self.logger.error(f"Aggregation failed: {e}")
            return gpd.GeoDataFrame()
    
    def calculate_road_coverage(self, traffic_gdf: gpd.GeoDataFrame, 
                               road_gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """
        道路カバレッジ分析
        
        Args:
            traffic_gdf: 交通データ
            road_gdf: 道路データ
            
        Returns:
            Dict: カバレッジ統計
        """
        if traffic_gdf.empty or road_gdf.empty:
            return {}
        
        # 空間結合実行
        joined = self.join_traffic_roads(traffic_gdf, road_gdf)
        
        if joined.empty:
            return {'coverage_rate': 0, 'matched_roads': 0, 'total_roads': len(road_gdf)}
        
        # カバレッジ統計計算
        matched_roads = joined['road_id'].nunique()
        total_roads = len(road_gdf)
        coverage_rate = matched_roads / total_roads if total_roads > 0 else 0
        
        # 距離統計
        distance_stats = {}
        if 'distance_to_road' in joined.columns:
            distances = joined['distance_to_road'].dropna()
            if not distances.empty:
                distance_stats = {
                    'mean_distance': float(distances.mean()),
                    'median_distance': float(distances.median()),
                    'max_distance': float(distances.max()),
                    'std_distance': float(distances.std())
                }
        
        return {
            'coverage_rate': coverage_rate,
            'matched_roads': matched_roads,
            'total_roads': total_roads,
            'traffic_points': len(traffic_gdf),
            'matched_points': len(joined[joined['road_id'].notna()]),
            'distance_stats': distance_stats
        }


def test_spatial_processor():
    """空間処理テスト"""
    import sys
    sys.path.append('.')
    
    from traffic_data import TrafficDataFetcher
    from road_data import RoadDataLoader
    from config import BBOX_5KM
    
    # ログ設定
    logging.basicConfig(level=logging.INFO)
    
    print("Testing spatial processing...")
    
    # データ読込
    traffic_fetcher = TrafficDataFetcher()
    road_loader = RoadDataLoader()
    processor = SpatialProcessor(max_distance=100)  # 100mに拡張
    
    # 交通データ取得
    print("Fetching traffic data...")
    traffic_data = traffic_fetcher.fetch_traffic_data(BBOX_5KM)
    
    # 道路データ読込
    print("Loading road data...")
    road_data = road_loader.load_road_network(bbox=BBOX_5KM)
    
    if traffic_data is not None and not road_data.empty:
        # 空間結合テスト
        print("Testing spatial join...")
        joined_data = processor.join_traffic_roads(traffic_data, road_data)
        
        if not joined_data.empty:
            print(f"✅ Spatial join successful: {len(joined_data)} records")
            
            # 集約テスト
            print("Testing aggregation...")
            aggregated_data = processor.aggregate_by_road(joined_data)
            
            if not aggregated_data.empty:
                print(f"✅ Aggregation successful: {len(aggregated_data)} roads")
                print(f"Columns: {list(aggregated_data.columns)}")
                
                # カバレッジ分析
                print("Testing coverage analysis...")
                coverage = processor.calculate_road_coverage(traffic_data, road_data)
                print(f"Coverage stats: {coverage}")
                
            else:
                print("❌ Aggregation failed")
        else:
            print("❌ Spatial join failed")
    else:
        print("❌ Failed to load input data")


if __name__ == "__main__":
    test_spatial_processor()