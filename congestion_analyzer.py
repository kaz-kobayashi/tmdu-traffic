"""混雑度分析モジュール"""
import pandas as pd
import geopandas as gpd
from typing import Dict, Any, Tuple
import numpy as np
import logging
from config import CONGESTION_COLORS, CONGESTION_THRESHOLDS

class CongestionAnalyzer:
    """混雑度分析・計算クラス"""
    
    def __init__(self, speed_thresholds: Dict[str, float] = None):
        self.speed_thresholds = speed_thresholds or CONGESTION_THRESHOLDS
        self.colors = CONGESTION_COLORS
        self.logger = logging.getLogger(__name__)
    
    def calculate_congestion_level(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        混雑度レベル計算
        
        Args:
            gdf: 道路データ（平均速度含む）
            
        Returns:
            GeoDataFrame: 混雑度レベル付きデータ
        """
        if gdf.empty:
            return gdf
        
        result = gdf.copy()
        
        # 平均速度列の確認
        if '平均速度' not in result.columns:
            self.logger.warning("No speed data found, marking all as unknown")
            result['congestion_level'] = 'unknown'
            result['congestion_color'] = self.colors['unknown']
            result['speed_category'] = 'データなし'
            return result
        
        # 速度データの前処理
        speeds = result['平均速度'].copy()
        
        # 数値変換
        speeds = pd.to_numeric(speeds, errors='coerce')
        
        # 混雑度レベル分類
        conditions = [
            speeds >= self.speed_thresholds['high_speed'],    # 30km/h以上
            speeds >= self.speed_thresholds['medium_speed'],  # 20-30km/h
            speeds < self.speed_thresholds['medium_speed']    # 20km/h未満
        ]
        choices = ['low', 'medium', 'high']
        
        # 条件適用
        result['congestion_level'] = np.select(
            conditions, 
            choices, 
            default='unknown'  # NaNやその他の値
        )
        
        # 色マッピング
        result['congestion_color'] = result['congestion_level'].map(self.colors)
        
        # 日本語カテゴリ
        congestion_labels = {
            'low': '空いている',
            'medium': 'やや混雑',
            'high': '混雑',
            'unknown': 'データなし'
        }
        result['speed_category'] = result['congestion_level'].map(congestion_labels)
        
        # 統計ログ
        level_counts = result['congestion_level'].value_counts()
        self.logger.info(f"Congestion analysis completed: {dict(level_counts)}")
        
        return result
    
    def generate_statistics(self, gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """
        混雑度統計情報生成
        
        Args:
            gdf: 混雑度レベル付きデータ
            
        Returns:
            Dict: 統計情報
        """
        if gdf.empty:
            return {
                'total_roads': 0,
                'congestion_distribution': {},
                'congestion_percentage': {},
                'speed_stats': {},
                'analysis_timestamp': pd.Timestamp.now().isoformat()
            }
        
        total_roads = len(gdf)
        
        # 混雑度レベル別集計
        if 'congestion_level' in gdf.columns:
            level_counts = gdf['congestion_level'].value_counts()
            level_percentages = (level_counts / total_roads * 100).round(1)
        else:
            level_counts = pd.Series(dtype=int)
            level_percentages = pd.Series(dtype=float)
        
        stats = {
            'total_roads': total_roads,
            'congestion_distribution': level_counts.to_dict(),
            'congestion_percentage': level_percentages.to_dict(),
            'analysis_timestamp': pd.Timestamp.now().isoformat()
        }
        
        # 速度統計
        if '平均速度' in gdf.columns:
            speed_data = pd.to_numeric(gdf['平均速度'], errors='coerce').dropna()
            if not speed_data.empty:
                stats['speed_stats'] = {
                    'count': int(len(speed_data)),
                    'mean': float(speed_data.mean()),
                    'median': float(speed_data.median()),
                    'min': float(speed_data.min()),
                    'max': float(speed_data.max()),
                    'std': float(speed_data.std()),
                    'q25': float(speed_data.quantile(0.25)),
                    'q75': float(speed_data.quantile(0.75))
                }
            else:
                stats['speed_stats'] = {'count': 0}
        
        # 旅行時間統計
        if '旅行時間' in gdf.columns:
            travel_time_data = pd.to_numeric(gdf['旅行時間'], errors='coerce').dropna()
            if not travel_time_data.empty:
                stats['travel_time_stats'] = {
                    'count': int(len(travel_time_data)),
                    'mean': float(travel_time_data.mean()),
                    'median': float(travel_time_data.median()),
                    'min': float(travel_time_data.min()),
                    'max': float(travel_time_data.max())
                }
        
        # 観測点数統計
        if 'observation_count' in gdf.columns:
            obs_data = pd.to_numeric(gdf['observation_count'], errors='coerce').dropna()
            if not obs_data.empty:
                stats['observation_stats'] = {
                    'total_observations': int(obs_data.sum()),
                    'mean_per_road': float(obs_data.mean()),
                    'max_per_road': int(obs_data.max()),
                    'roads_with_data': int((obs_data > 0).sum())
                }
        
        return stats
    
    def analyze_congestion_trends(self, gdf: gpd.GeoDataFrame, 
                                 road_class_col: str = 'road_class') -> Dict[str, Any]:
        """
        道路クラス別混雑度分析
        
        Args:
            gdf: 混雑度レベル付きデータ
            road_class_col: 道路クラス列名
            
        Returns:
            Dict: 道路クラス別分析結果
        """
        if gdf.empty or 'congestion_level' not in gdf.columns:
            return {}
        
        trends = {}
        
        # 道路クラス別分析
        if road_class_col in gdf.columns:
            class_analysis = {}
            
            for road_class in gdf[road_class_col].dropna().unique():
                class_data = gdf[gdf[road_class_col] == road_class]
                if not class_data.empty:
                    class_stats = self.generate_statistics(class_data)
                    class_analysis[str(road_class)] = class_stats
            
            trends['by_road_class'] = class_analysis
        
        # 速度範囲別分析
        if '平均速度' in gdf.columns:
            speed_data = pd.to_numeric(gdf['平均速度'], errors='coerce').dropna()
            if not speed_data.empty:
                # 速度範囲の定義
                speed_ranges = [
                    (0, 10, '極低速'),
                    (10, 20, '低速'),
                    (20, 30, '中速'),
                    (30, 50, '高速'),
                    (50, float('inf'), '極高速')
                ]
                
                range_analysis = {}
                for min_speed, max_speed, label in speed_ranges:
                    mask = (speed_data >= min_speed) & (speed_data < max_speed)
                    count = mask.sum()
                    percentage = (count / len(speed_data) * 100) if len(speed_data) > 0 else 0
                    
                    range_analysis[label] = {
                        'count': int(count),
                        'percentage': round(percentage, 1),
                        'range': f"{min_speed}-{max_speed if max_speed != float('inf') else '∞'}km/h"
                    }
                
                trends['by_speed_range'] = range_analysis
        
        return trends
    
    def get_congestion_summary(self, gdf: gpd.GeoDataFrame) -> str:
        """
        混雑度サマリーテキスト生成
        
        Args:
            gdf: 混雑度レベル付きデータ
            
        Returns:
            str: サマリーテキスト
        """
        if gdf.empty:
            return "データがありません。"
        
        stats = self.generate_statistics(gdf)
        
        total = stats['total_roads']
        percentages = stats.get('congestion_percentage', {})
        
        if not percentages:
            return f"対象道路数: {total}（混雑度データなし）"
        
        # 主要な混雑状況
        high_pct = percentages.get('high', 0)
        medium_pct = percentages.get('medium', 0)
        low_pct = percentages.get('low', 0)
        unknown_pct = percentages.get('unknown', 0)
        
        # 速度統計
        speed_stats = stats.get('speed_stats', {})
        avg_speed = speed_stats.get('mean', 0)
        
        summary_parts = [
            f"対象道路数: {total}路線",
        ]
        
        if low_pct > 0:
            summary_parts.append(f"空いている: {low_pct}%")
        if medium_pct > 0:
            summary_parts.append(f"やや混雑: {medium_pct}%")
        if high_pct > 0:
            summary_parts.append(f"混雑: {high_pct}%")
        
        if avg_speed > 0:
            summary_parts.append(f"平均速度: {avg_speed:.1f}km/h")
        
        return " | ".join(summary_parts)


def test_congestion_analyzer():
    """混雑度分析テスト"""
    import sys
    sys.path.append('.')
    
    from traffic_data import TrafficDataFetcher
    from road_data import RoadDataLoader
    from spatial_processor import SpatialProcessor
    from config import BBOX_5KM
    
    # ログ設定
    logging.basicConfig(level=logging.INFO)
    
    print("Testing congestion analysis...")
    
    # データ準備
    traffic_fetcher = TrafficDataFetcher()
    road_loader = RoadDataLoader()
    spatial_processor = SpatialProcessor()
    analyzer = CongestionAnalyzer()
    
    # データ取得・処理
    print("Fetching and processing data...")
    traffic_data = traffic_fetcher.fetch_traffic_data(BBOX_5KM)
    road_data = road_loader.load_road_network(bbox=BBOX_5KM)
    
    if traffic_data is not None and not road_data.empty:
        # 空間結合・集約
        joined_data = spatial_processor.join_traffic_roads(traffic_data, road_data)
        aggregated_data = spatial_processor.aggregate_by_road(joined_data)
        
        if not aggregated_data.empty:
            # 混雑度分析テスト
            print("Testing congestion level calculation...")
            congestion_data = analyzer.calculate_congestion_level(aggregated_data)
            
            print(f"✅ Congestion analysis successful: {len(congestion_data)} roads")
            print(f"Columns: {list(congestion_data.columns)}")
            
            # 統計生成テスト
            print("Testing statistics generation...")
            stats = analyzer.generate_statistics(congestion_data)
            print(f"Statistics: {stats}")
            
            # トレンド分析テスト
            print("Testing trend analysis...")
            trends = analyzer.analyze_congestion_trends(congestion_data)
            print(f"Trends: {trends}")
            
            # サマリー生成テスト
            print("Testing summary generation...")
            summary = analyzer.get_congestion_summary(congestion_data)
            print(f"Summary: {summary}")
            
        else:
            print("❌ No aggregated data for analysis")
    else:
        print("❌ Failed to load input data")


if __name__ == "__main__":
    test_congestion_analyzer()