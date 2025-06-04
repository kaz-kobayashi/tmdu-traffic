"""Streamlit メインアプリケーション"""
import streamlit as st
from datetime import datetime, timedelta
import time
import logging
import traceback
from pathlib import Path
import pytz

# 地図関連のインポート（エラーハンドリング付き）
try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
    FOLIUM_ERROR = None
except ImportError as e:
    FOLIUM_AVAILABLE = False
    FOLIUM_ERROR = str(e)
    st_folium = None

# 各モジュールのインポート
from traffic_data import TrafficDataFetcher
from road_data import RoadDataLoader
from spatial_processor import SpatialProcessor
from congestion_analyzer import CongestionAnalyzer
from map_visualizer import MapVisualizer
from config import *

# ログ設定
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """メインアプリケーション"""
    st.set_page_config(
        page_title="センター周辺交通状況",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # foliumエラーを表示（ページ設定後）
    if not FOLIUM_AVAILABLE:
        st.error(f"地図ライブラリの読み込みエラー: {FOLIUM_ERROR}")
        st.info("folium と streamlit-folium のインストールが必要です")
    
    # メインタイトル
    st.title("🚗 センター周辺 交通混雑度マップ")
    st.markdown("---")
    
    # サイドバー設定
    setup_sidebar()
    
    # メインコンテンツ
    display_main_content()

def setup_sidebar():
    """サイドバー設定"""
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # 自動更新設定
        auto_update = st.checkbox("🔄 自動更新（5分間隔）", value=False)
        
        # 手動更新ボタン
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 今すぐ更新", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        with col2:
            if st.button("🗑️ キャッシュクリア", use_container_width=True):
                st.cache_data.clear()
                st.success("キャッシュをクリアしました")
                time.sleep(1)
                st.rerun()
        
        st.markdown("---")
        
        # 表示オプション
        st.subheader("📊 表示オプション")
        
        show_statistics = st.checkbox("統計情報を表示", value=True)
        show_details = st.checkbox("詳細情報を表示", value=False)
        
        # 混雑度しきい値カスタマイズ
        st.subheader("🚦 混雑度設定")
        
        with st.expander("しきい値設定", expanded=False):
            high_speed_threshold = st.slider(
                "空いている（最低速度）", 
                min_value=20, max_value=50, 
                value=CONGESTION_THRESHOLDS['high_speed'],
                help="この速度以上を「空いている」とします"
            )
            
            medium_speed_threshold = st.slider(
                "やや混雑（最低速度）", 
                min_value=10, max_value=30, 
                value=CONGESTION_THRESHOLDS['medium_speed'],
                help="この速度以上を「やや混雑」とします"
            )
            
            # 設定をセッション状態に保存
            st.session_state['speed_thresholds'] = {
                'high_speed': high_speed_threshold,
                'medium_speed': medium_speed_threshold
            }
        
        st.markdown("---")
        
        # データソース情報
        st.subheader("📡 データソース")
        st.write("**交通データ:** JARTIC API")
        st.write("**道路データ:** 国土数値情報")
        st.write(f"**対象エリア:** センター周辺5km")
        st.write(f"**更新間隔:** {UPDATE_INTERVAL//60}分")
        
        # システム情報
        if show_details:
            st.markdown("---")
            st.subheader("🔧 システム情報")
            
            # データファイル存在確認
            road_file_exists = Path(ROAD_DATA_ZIP).exists()
            st.write(f"道路データ: {'✅' if road_file_exists else '❌'}")
            
            # BBOX情報
            st.write(f"**BBOX:** {BBOX_5KM}")
            st.write(f"**中心座標:** {TMDU_CENTER}")
        
        # 自動更新処理
        if auto_update:
            st.info("⏱️ 自動更新モード")
            time.sleep(UPDATE_INTERVAL)
            st.rerun()

def display_main_content():
    """メインコンテンツ表示"""
    # データ読込とマップ生成
    with st.spinner("🔄 データを読み込み中..."):
        traffic_map, stats, error_message = create_traffic_map()
    
    # エラーハンドリング
    if error_message:
        st.error(f"❌ エラーが発生しました: {error_message}")
        st.info("💡 解決方法:")
        st.write("1. 道路データファイル（N01-07L-13-01.0a_GML.zip）が存在することを確認")
        st.write("2. インターネット接続を確認")
        st.write("3. しばらく時間を置いてから再試行")
        return
    
    # 統計情報表示
    if stats and st.session_state.get('show_statistics', True):
        display_statistics(stats)
    
    # 地図表示
    st.subheader("🗺️ 交通混雑度マップ")
    
    if traffic_map:
        # 地図表示オプション
        map_height = st.selectbox(
            "地図の高さ", 
            options=[400, 500, 600, 700, 800], 
            index=2,
            key="map_height"
        )
        
        # 地図表示
        if FOLIUM_AVAILABLE and traffic_map is not None:
            map_data = st_folium(
                traffic_map, 
                width=None,  # 自動幅調整
                height=map_height,
                returned_objects=["last_object_clicked"]
            )
            
            # クリックされた道路の詳細表示
            if map_data['last_object_clicked']:
                display_clicked_road_info(map_data['last_object_clicked'])
        else:
            st.error("🗺️ 地図ライブラリが利用できません")
            st.info("地図表示には folium と streamlit-folium が必要です")
            
    else:
        st.error("🗺️ 地図データの読み込みに失敗しました")
        if not FOLIUM_AVAILABLE:
            st.error("地図ライブラリが利用できません")
        else:
            st.info("基本的な地図を表示します...")
            
            # フォールバック地図
            basic_map = create_basic_map()
            if basic_map is not None:
                st_folium(basic_map, width=None, height=500)
    
    # 最終更新時刻表示（日本時間）
    jst = pytz.timezone("Asia/Tokyo")
    now_jst = datetime.now(tz=jst)
    st.caption(f"🕒 最終更新: {now_jst.strftime('%Y-%m-%d %H:%M:%S')} JST")
    
    # 詳細統計（展開可能）
    if stats and st.session_state.get('show_details', False):
        display_detailed_statistics(stats)

def display_statistics(stats: dict):
    """統計情報表示"""
    st.subheader("📊 交通状況サマリー")
    
    # メイン指標
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_roads = stats.get('total_roads', 0)
        st.metric("📍 総道路数", f"{total_roads:,}", help="分析対象の道路セグメント数")
    
    with col2:
        pct = stats.get('congestion_percentage', {})
        low_pct = pct.get('low', 0)
        st.metric("🟢 空いている", f"{low_pct:.1f}%", help="速度30km/h以上の道路")
    
    with col3:
        medium_pct = pct.get('medium', 0)
        st.metric("🟡 やや混雑", f"{medium_pct:.1f}%", help="速度20-30km/hの道路")
    
    with col4:
        high_pct = pct.get('high', 0)
        st.metric("🔴 混雑", f"{high_pct:.1f}%", help="速度20km/h未満の道路")
    
    # 速度統計
    speed_stats = stats.get('speed_stats', {})
    if speed_stats and speed_stats.get('count', 0) > 0:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_speed = speed_stats.get('mean', 0)
            st.metric("⚡ 平均速度", f"{avg_speed:.1f} km/h")
        
        with col2:
            median_speed = speed_stats.get('median', 0)
            st.metric("📊 中央値速度", f"{median_speed:.1f} km/h")
        
        with col3:
            obs_stats = stats.get('observation_stats', {})
            total_obs = obs_stats.get('total_observations', 0)
            st.metric("🔍 観測点数", f"{total_obs:,}")

def display_clicked_road_info(clicked_data: dict):
    """クリックされた道路の詳細情報表示"""
    if not clicked_data:
        return
    
    st.subheader("🛣️ 選択された道路の詳細")
    
    # クリックされた位置の情報を表示
    lat = clicked_data.get('lat')
    lng = clicked_data.get('lng')
    
    if lat and lng:
        st.info(f"📍 クリック位置: 緯度 {lat:.6f}, 経度 {lng:.6f}")
        st.caption("地図上の道路をクリックすると、その道路の詳細情報が表示されます。")

def display_detailed_statistics(stats: dict):
    """詳細統計表示"""
    with st.expander("📈 詳細統計情報", expanded=False):
        
        # 速度統計詳細
        speed_stats = stats.get('speed_stats', {})
        if speed_stats:
            st.subheader("🚀 速度統計")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**データ数:** {speed_stats.get('count', 0):,}")
                st.write(f"**平均:** {speed_stats.get('mean', 0):.2f} km/h")
                st.write(f"**中央値:** {speed_stats.get('median', 0):.2f} km/h")
                st.write(f"**標準偏差:** {speed_stats.get('std', 0):.2f} km/h")
            
            with col2:
                st.write(f"**最小値:** {speed_stats.get('min', 0):.1f} km/h")
                st.write(f"**最大値:** {speed_stats.get('max', 0):.1f} km/h")
                st.write(f"**第1四分位:** {speed_stats.get('q25', 0):.1f} km/h")
                st.write(f"**第3四分位:** {speed_stats.get('q75', 0):.1f} km/h")
        
        # 観測統計詳細
        obs_stats = stats.get('observation_stats', {})
        if obs_stats:
            st.subheader("🔍 観測統計")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**総観測点数:** {obs_stats.get('total_observations', 0):,}")
                st.write(f"**データ有り道路数:** {obs_stats.get('roads_with_data', 0):,}")
            
            with col2:
                st.write(f"**道路あたり平均観測点数:** {obs_stats.get('mean_per_road', 0):.1f}")
                st.write(f"**道路あたり最大観測点数:** {obs_stats.get('max_per_road', 0)}")

@st.cache_data(ttl=UPDATE_INTERVAL, show_spinner=False)
def create_traffic_map():
    """キャッシュ付きマップ作成"""
    error_message = None
    
    try:
        # カスタム設定の取得
        speed_thresholds = st.session_state.get('speed_thresholds', CONGESTION_THRESHOLDS)
        
        # データ処理オブジェクト初期化
        traffic_fetcher = TrafficDataFetcher(JARTIC_API_URL, API_TIMEOUT)
        road_loader = RoadDataLoader()
        spatial_processor = SpatialProcessor(max_distance=200)  # 200mに拡張（道路カバー率向上）
        congestion_analyzer = CongestionAnalyzer(speed_thresholds)
        map_visualizer = MapVisualizer(TMDU_CENTER, MAP_ZOOM_LEVEL)
        
        # 1. 交通データ取得
        traffic_data = traffic_fetcher.fetch_traffic_data(BBOX_5KM)
        if traffic_data is None or traffic_data.empty:
            return None, {}, "交通データを取得できませんでした。ネットワーク接続を確認してください。"
        
        # 2. 道路データ読込
        road_zip_path = Path(ROAD_DATA_ZIP)
        # 現在のディレクトリとapp.pyのディレクトリの両方をチェック
        if not road_zip_path.exists():
            app_dir = Path(__file__).parent
            alt_road_zip_path = app_dir / ROAD_DATA_ZIP
            if alt_road_zip_path.exists():
                road_zip_path = alt_road_zip_path
            else:
                return None, {}, f"道路データファイルが見つかりません: {ROAD_DATA_ZIP}"
        
        road_data = road_loader.load_road_network(road_zip_path, BBOX_5KM)
        if road_data.empty:
            return None, {}, "道路データを読み込めませんでした。"
        
        # 3. 空間結合
        joined_data = spatial_processor.join_traffic_roads(traffic_data, road_data)
        if joined_data.empty:
            return None, {}, "交通データと道路データの結合に失敗しました。"
        
        # 4. 道路ごと集約
        aggregated_data = spatial_processor.aggregate_by_road(joined_data)
        if aggregated_data.empty:
            return None, {}, "道路データの集約に失敗しました。"
        
        # 5. 混雑度分析
        congestion_data = congestion_analyzer.calculate_congestion_level(aggregated_data)
        stats = congestion_analyzer.generate_statistics(congestion_data)
        
        # 6. 地図作成
        traffic_map = map_visualizer.create_traffic_map(congestion_data, stats)
        
        return traffic_map, stats, None
        
    except Exception as e:
        error_message = f"予期しないエラーが発生しました: {str(e)}"
        logging.error(f"Map creation error: {e}")
        logging.error(traceback.format_exc())
        return None, {}, error_message

def create_basic_map():
    """基本マップ作成（フォールバック用）"""
    map_visualizer = MapVisualizer(TMDU_CENTER, MAP_ZOOM_LEVEL)
    basic_map = map_visualizer._create_base_map()
    map_visualizer._add_university_marker(basic_map)
    return basic_map

if __name__ == "__main__":
    main()