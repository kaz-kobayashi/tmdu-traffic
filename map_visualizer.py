"""地図可視化モジュール"""
import geopandas as gpd
import pandas as pd
from typing import Tuple, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import folium
import json
import logging
from config import (
    TMDU_CENTER, MAP_ZOOM_LEVEL, MAP_TILES, 
    ROAD_LINE_WIDTH, ROAD_LINE_OPACITY, CONGESTION_COLORS
)

# foliumのインポート（エラーハンドリング付き）
try:
    import folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False
    folium = None

class MapVisualizer:
    """地図可視化クラス"""
    
    def __init__(self, center: Tuple[float, float] = TMDU_CENTER, zoom: int = MAP_ZOOM_LEVEL):
        self.center = center
        self.zoom = zoom
        self.logger = logging.getLogger(__name__)
    
    def create_traffic_map(self, road_data: gpd.GeoDataFrame, 
                          stats: Optional[Dict[str, Any]] = None) -> Optional[object]:
        """
        交通状況地図作成
        
        Args:
            road_data: 混雑度付き道路データ
            stats: 統計情報（オプション）
            
        Returns:
            folium.Map: 作成された地図（folium利用可能時）
        """
        if not FOLIUM_AVAILABLE:
            self.logger.error("Folium is not available - cannot create map")
            return None
            
        try:
            # ベースマップ作成
            m = self._create_base_map()
            
            # 道路レイヤー追加
            if not road_data.empty:
                self._add_road_layer(m, road_data)
                self.logger.info(f"Added {len(road_data)} road segments to map")
            else:
                self.logger.warning("No road data to display")
            
            # 統計情報パネル追加
            if stats:
                self._add_statistics_panel(m, stats)
            
            # 凡例追加
            self._add_legend(m)
            
            # 大学位置マーカー追加
            self._add_university_marker(m)
            
            return m
            
        except Exception as e:
            self.logger.error(f"Map creation failed: {e}")
            # フォールバック: 基本マップのみ
            return self._create_base_map()
    
    def _create_base_map(self) -> Optional[object]:
        """ベースマップ作成"""
        if not FOLIUM_AVAILABLE:
            return None
            
        m = folium.Map(
            location=self.center,
            zoom_start=self.zoom,
            tiles=MAP_TILES
        )
        
        # タイル層の追加オプション
        folium.TileLayer(
            tiles='CartoDB positron',
            name='CartoDB Positron',
            attr='CartoDB'
        ).add_to(m)
        
        # レイヤーコントロール追加
        folium.LayerControl().add_to(m)
        
        return m
    
    def _add_road_layer(self, m: object, road_data: gpd.GeoDataFrame):
        """道路レイヤー追加"""
        for idx, row in road_data.iterrows():
            try:
                if pd.isna(row.geometry):
                    continue
                
                # 色とスタイル設定
                color = row.get('congestion_color', CONGESTION_COLORS['unknown'])
                
                # 線の太さを混雑度に応じて調整
                weight = self._get_line_weight(row.get('congestion_level', 'unknown'))
                
                # ポップアップ情報作成
                popup_html = self._create_popup_html(row)
                
                # ツールチップ作成
                tooltip_text = self._create_tooltip_text(row)
                
                # シンプルなPolyLineを使用（lambda関数を避ける）
                if hasattr(row.geometry, 'coords'):
                    coords = list(row.geometry.coords)
                    # 座標を緯度経度順に変換（Foliumは[lat, lon]順）
                    locations = [(lat, lon) for lon, lat in coords]
                    
                    folium.PolyLine(
                        locations=locations,
                        color=color,
                        weight=weight,
                        opacity=1.0,  # 完全不透明にして見やすく
                        popup=folium.Popup(popup_html, max_width=350),
                        tooltip=tooltip_text
                    ).add_to(m)
                else:
                    # MultiLineString などの場合
                    try:
                        import shapely.ops
                        if row.geometry.geom_type == 'MultiLineString':
                            for line in row.geometry.geoms:
                                coords = list(line.coords)
                                locations = [(lat, lon) for lon, lat in coords]
                                folium.PolyLine(
                                    locations=locations,
                                    color=color,
                                    weight=weight,
                                    opacity=1.0,  # 完全不透明にして見やすく
                                    popup=folium.Popup(popup_html, max_width=350),
                                    tooltip=tooltip_text
                                ).add_to(m)
                    except Exception as geom_error:
                        self.logger.warning(f"Failed to process geometry: {geom_error}")
                
            except Exception as e:
                self.logger.warning(f"Failed to add road segment {idx}: {e}")
                continue
    
    def _get_line_weight(self, congestion_level: str) -> int:
        """混雑度に応じた線の太さ決定"""
        weight_map = {
            'high': 8,     # 混雑: 太い
            'medium': 6,   # やや混雑: やや太い
            'low': 4,      # 空いている: 標準
            'unknown': 2   # データなし: 細い
        }
        return weight_map.get(congestion_level, 4)
    
    def _create_popup_html(self, row: pd.Series) -> str:
        """ポップアップHTML作成"""
        road_name = row.get('road_name', 'N/A')
        road_id = row.get('road_id', 'N/A')
        speed = row.get('平均速度', 'N/A')
        travel_time = row.get('旅行時間', 'N/A')
        congestion_level = row.get('congestion_level', 'unknown')
        speed_category = row.get('speed_category', 'データなし')
        observation_count = row.get('observation_count', 'N/A')
        
        # 数値の整形
        if pd.notna(speed) and speed != 'N/A':
            try:
                speed = f"{float(speed):.1f}"
            except (ValueError, TypeError):
                speed = 'N/A'
        
        if pd.notna(travel_time) and travel_time != 'N/A':
            try:
                travel_time = f"{float(travel_time):.0f}"
            except (ValueError, TypeError):
                travel_time = 'N/A'
        
        # 混雑度に応じた背景色
        bg_color = {
            'high': '#ffe6e6',      # 薄い赤
            'medium': '#fff9e6',    # 薄い黄
            'low': '#e6ffe6',       # 薄い緑
            'unknown': '#f0f0f0'    # 薄い灰色
        }.get(congestion_level, '#f0f0f0')
        
        html = f"""
        <div style="font-family: 'Noto Sans JP', Arial, sans-serif; 
                    background-color: {bg_color}; 
                    padding: 10px; 
                    border-radius: 5px;
                    min-width: 250px;">
            <h4 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">
                {road_name}
            </h4>
            <hr style="margin: 8px 0; border: 1px solid #ddd;">
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px;">
                <div><strong>混雑状況:</strong></div>
                <div style="color: {row.get('congestion_color', '#666')}; font-weight: bold;">
                    {speed_category}
                </div>
                
                <div><strong>平均速度:</strong></div>
                <div>{speed} km/h</div>
                
                <div><strong>旅行時間:</strong></div>
                <div>{travel_time} 秒</div>
                
                <div><strong>観測点数:</strong></div>
                <div>{observation_count} 地点</div>
                
                <div><strong>道路ID:</strong></div>
                <div style="font-family: monospace; font-size: 11px;">{road_id}</div>
            </div>
        </div>
        """
        return html
    
    def _create_tooltip_text(self, row: pd.Series) -> str:
        """ツールチップテキスト作成"""
        road_name = row.get('road_name', '道路名不明')
        speed_category = row.get('speed_category', 'データなし')
        speed = row.get('平均速度', 'N/A')
        
        if pd.notna(speed) and speed != 'N/A':
            try:
                speed_text = f" ({float(speed):.1f}km/h)"
            except (ValueError, TypeError):
                speed_text = ""
        else:
            speed_text = ""
        
        return f"{road_name}: {speed_category}{speed_text}"
    
    def _add_statistics_panel(self, m: object, stats: Dict[str, Any]):
        """統計情報パネル追加"""
        if 'congestion_percentage' not in stats:
            return
        
        percentages = stats['congestion_percentage']
        total_roads = stats.get('total_roads', 0)
        
        # 速度統計
        speed_stats = stats.get('speed_stats', {})
        avg_speed = speed_stats.get('mean', 0)
        
        # 観測統計
        obs_stats = stats.get('observation_stats', {})
        total_observations = obs_stats.get('total_observations', 0)
        
        html = f"""
        <div style="position: fixed; 
                    top: 10px; right: 10px; 
                    width: 280px; height: auto; 
                    background-color: rgba(255,255,255,0.95); 
                    border: 2px solid #333; 
                    border-radius: 8px;
                    z-index: 9999; 
                    font-size: 13px; 
                    padding: 15px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    font-family: 'Noto Sans JP', Arial, sans-serif;">
            <h4 style="margin: 0 0 12px 0; color: #333; border-bottom: 2px solid #333; padding-bottom: 5px;">
                📊 交通状況統計
            </h4>
            
            <div style="margin-bottom: 10px;">
                <strong>対象道路数:</strong> {total_roads} 路線<br>
                <strong>観測点数:</strong> {total_observations} 地点
            </div>
            
            <div style="margin-bottom: 15px;">
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <span style="color: {CONGESTION_COLORS['low']}; font-size: 18px; margin-right: 8px;">●</span>
                    <span>空いている: <strong>{percentages.get('low', 0):.1f}%</strong></span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <span style="color: {CONGESTION_COLORS['medium']}; font-size: 18px; margin-right: 8px;">●</span>
                    <span>やや混雑: <strong>{percentages.get('medium', 0):.1f}%</strong></span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <span style="color: {CONGESTION_COLORS['high']}; font-size: 18px; margin-right: 8px;">●</span>
                    <span>混雑: <strong>{percentages.get('high', 0):.1f}%</strong></span>
                </div>
                <div style="display: flex; align-items: center;">
                    <span style="color: {CONGESTION_COLORS['unknown']}; font-size: 18px; margin-right: 8px;">●</span>
                    <span>データなし: <strong>{percentages.get('unknown', 0):.1f}%</strong></span>
                </div>
            </div>
            
            {f'<div><strong>平均速度:</strong> {avg_speed:.1f} km/h</div>' if avg_speed > 0 else ''}
            
            <div style="margin-top: 10px; font-size: 11px; color: #666; border-top: 1px solid #ddd; padding-top: 8px;">
                最終更新: {pd.Timestamp.now().strftime('%H:%M:%S')}
            </div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(html))
    
    def _add_legend(self, m: object):
        """凡例追加"""
        legend_html = f"""
        <div style="position: fixed; 
                    bottom: 30px; left: 30px; 
                    width: 200px; height: auto; 
                    background-color: rgba(255,255,255,0.95); 
                    border: 2px solid #333; 
                    border-radius: 8px;
                    z-index: 9999; 
                    font-size: 13px; 
                    padding: 15px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    font-family: 'Noto Sans JP', Arial, sans-serif;">
            <h4 style="margin: 0 0 12px 0; color: #333; border-bottom: 2px solid #333; padding-bottom: 5px;">
                🚦 混雑度凡例
            </h4>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span style="color: {CONGESTION_COLORS['low']}; font-size: 20px; margin-right: 10px;">■</span>
                <span>空いている (≥30km/h)</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span style="color: {CONGESTION_COLORS['medium']}; font-size: 20px; margin-right: 10px;">■</span>
                <span>やや混雑 (20-30km/h)</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span style="color: {CONGESTION_COLORS['high']}; font-size: 20px; margin-right: 10px;">■</span>
                <span>混雑 (<20km/h)</span>
            </div>
            <div style="display: flex; align-items: center;">
                <span style="color: {CONGESTION_COLORS['unknown']}; font-size: 20px; margin-right: 10px;">■</span>
                <span>データなし</span>
            </div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
    
    def _add_university_marker(self, m: object):
        """東京医科歯科大学マーカー追加"""
        folium.Marker(
            self.center,
            popup=folium.Popup(
                """
                <div style="font-family: 'Noto Sans JP', Arial, sans-serif; text-align: center;">
                    <h4 style="margin: 5px; color: #333;">🏥 東京医科歯科大学</h4>
                    <p style="margin: 5px; font-size: 12px;">湯島キャンパス</p>
                </div>
                """,
                max_width=200
            ),
            tooltip="東京医科歯科大学 湯島キャンパス",
            icon=folium.Icon(
                color='red',
                icon='plus',
                prefix='fa'
            )
        ).add_to(m)


def test_map_visualizer():
    """地図可視化テスト"""
    import sys
    sys.path.append('.')
    
    from traffic_data import TrafficDataFetcher
    from road_data import RoadDataLoader
    from spatial_processor import SpatialProcessor
    from congestion_analyzer import CongestionAnalyzer
    from config import BBOX_5KM
    
    # ログ設定
    logging.basicConfig(level=logging.INFO)
    
    print("Testing map visualization...")
    
    # データ準備
    traffic_fetcher = TrafficDataFetcher()
    road_loader = RoadDataLoader()
    spatial_processor = SpatialProcessor()
    congestion_analyzer = CongestionAnalyzer()
    visualizer = MapVisualizer()
    
    try:
        # データ取得・処理
        print("Processing data...")
        traffic_data = traffic_fetcher.fetch_traffic_data(BBOX_5KM)
        road_data = road_loader.load_road_network(bbox=BBOX_5KM)
        
        if traffic_data is not None and not road_data.empty:
            # データ統合・分析
            joined_data = spatial_processor.join_traffic_roads(traffic_data, road_data)
            aggregated_data = spatial_processor.aggregate_by_road(joined_data)
            congestion_data = congestion_analyzer.calculate_congestion_level(aggregated_data)
            stats = congestion_analyzer.generate_statistics(congestion_data)
            
            # 地図作成
            print("Creating map...")
            traffic_map = visualizer.create_traffic_map(congestion_data, stats)
            
            # 地図保存
            output_file = "test_traffic_map.html"
            traffic_map.save(output_file)
            print(f"✅ Map saved to {output_file}")
            
        else:
            print("❌ Failed to load input data")
            # テスト用の基本マップ作成
            basic_map = visualizer._create_base_map()
            basic_map.save("test_basic_map.html")
            print("Created basic map for testing")
            
    except Exception as e:
        print(f"❌ Map visualization test failed: {e}")


if __name__ == "__main__":
    test_map_visualizer()