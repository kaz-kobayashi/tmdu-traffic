"""PyDeck版交通可視化アプリ"""
import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from datetime import datetime
import pytz
import logging

# 既存モジュールのインポート
try:
    from traffic_data import TrafficDataFetcher
    from road_data import RoadDataLoader
    from spatial_processor import SpatialProcessor
    from congestion_analyzer import CongestionAnalyzer
    from config import TMDU_CENTER, BBOX_5KM, CONGESTION_COLORS, UPDATE_INTERVAL
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    st.error(f"モジュールインポートエラー: {e}")

# ページ設定
st.set_page_config(
    page_title="東京医科歯科大学周辺交通状況 - PyDeck版",
    page_icon="🗺️",
    layout="wide"
)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@st.cache_data(ttl=UPDATE_INTERVAL, show_spinner=False)
def load_and_process_data():
    """データ読み込みと処理（キャッシュ付き）"""
    if not MODULES_AVAILABLE:
        return create_mock_data(), {"status": "mock", "error": "モジュール不可"}
    
    try:
        # データ読み込み
        fetcher = TrafficDataFetcher()
        loader = RoadDataLoader()
        processor = SpatialProcessor()
        analyzer = CongestionAnalyzer()
        
        # 道路データ読み込み
        road_gdf = loader.load_road_data(bbox=BBOX_5KM)
        if road_gdf.empty:
            raise Exception("道路データの読み込みに失敗")
        
        # 交通データ取得
        traffic_gdf = fetcher.fetch_traffic_data(bbox=BBOX_5KM)
        if traffic_gdf.empty:
            raise Exception("交通データの取得に失敗")
        
        # 空間結合
        joined_gdf = processor.join_traffic_roads(traffic_gdf, road_gdf)
        if joined_gdf.empty:
            raise Exception("空間結合に失敗")
        
        # 道路別集約
        road_stats = processor.aggregate_by_road(joined_gdf, road_gdf)
        if road_stats.empty:
            raise Exception("道路別集約に失敗")
        
        # 混雑度分析
        final_data = analyzer.calculate_congestion_level(road_stats)
        
        # PyDeck用データ準備
        pydeck_data = prepare_pydeck_data(final_data)
        
        status_info = {
            "status": "real",
            "road_count": len(road_gdf),
            "traffic_count": len(traffic_gdf),
            "matched_count": len(joined_gdf[joined_gdf['road_id'].notna()]),
            "final_roads": len(final_data)
        }
        
        return pydeck_data, status_info
        
    except Exception as e:
        logger.error(f"Real data processing failed: {e}")
        return create_mock_data(), {"status": "mock", "error": str(e)}

def prepare_pydeck_data(gdf):
    """GeoDataFrameをPyDeck用データに変換"""
    if gdf.empty:
        return pd.DataFrame()
    
    # 道路の線データを点のリストに変換
    roads_data = []
    for idx, row in gdf.iterrows():
        if row.geometry is None:
            continue
            
        # LineStringから座標を抽出
        if hasattr(row.geometry, 'coords'):
            coords = list(row.geometry.coords)
        elif hasattr(row.geometry, 'geoms'):
            # MultiLineStringの場合
            coords = []
            for geom in row.geometry.geoms:
                coords.extend(list(geom.coords))
        else:
            continue
        
        # 混雑度による色設定
        congestion_level = getattr(row, 'congestion_level', 'unknown')
        color = get_color_rgb(congestion_level)
        
        # 道路情報
        road_info = {
            'path': [[lon, lat] for lon, lat in coords],
            'road_id': getattr(row, 'road_id', f'road_{idx}'),
            'road_name': getattr(row, 'road_name', '不明'),
            'speed': getattr(row, '平均速度', 0),
            'congestion': congestion_level,
            'color': color,
            'width': get_width_by_congestion(congestion_level)
        }
        roads_data.append(road_info)
    
    return pd.DataFrame(roads_data)

def get_color_rgb(congestion_level):
    """混雑度に基づくRGB色を取得"""
    color_map = {
        'low': [0, 255, 0, 160],      # 緑（空いている）
        'medium': [255, 255, 0, 160], # 黄（やや混雑）
        'high': [255, 0, 0, 160],     # 赤（混雑）
        'unknown': [128, 128, 128, 160] # 灰（不明）
    }
    return color_map.get(congestion_level, color_map['unknown'])

def get_width_by_congestion(congestion_level):
    """混雑度による線の太さ"""
    width_map = {
        'low': 3,
        'medium': 4,
        'high': 5,
        'unknown': 2
    }
    return width_map.get(congestion_level, 2)

def create_mock_data():
    """モックデータ生成（PyDeck用）"""
    np.random.seed(42)
    center_lat, center_lon = TMDU_CENTER
    
    roads_data = []
    for i in range(30):
        # ランダムな道路線を生成
        start_lat = np.random.normal(center_lat, 0.005)
        start_lon = np.random.normal(center_lon, 0.005)
        end_lat = start_lat + np.random.normal(0, 0.003)
        end_lon = start_lon + np.random.normal(0, 0.003)
        
        speed = np.random.normal(25, 10)
        speed = np.clip(speed, 5, 60)
        
        if speed >= 30:
            congestion = 'low'
        elif speed >= 20:
            congestion = 'medium'
        else:
            congestion = 'high'
        
        road_info = {
            'path': [[start_lon, start_lat], [end_lon, end_lat]],
            'road_id': f'mock_road_{i}',
            'road_name': f'道路_{i+1}',
            'speed': speed,
            'congestion': congestion,
            'color': get_color_rgb(congestion),
            'width': get_width_by_congestion(congestion)
        }
        roads_data.append(road_info)
    
    return pd.DataFrame(roads_data)

def create_pydeck_map(roads_df, center=TMDU_CENTER):
    """PyDeckマップ作成"""
    
    # 道路レイヤー
    road_layer = pdk.Layer(
        "PathLayer",
        data=roads_df,
        get_path="path",
        get_color="color",
        get_width="width",
        width_scale=20,
        width_min_pixels=2,
        pickable=True,
        auto_highlight=True
    )
    
    # 東京医科歯科大学マーカー
    university_data = [{
        'lat': center[0],
        'lon': center[1],
        'name': '東京医科歯科大学'
    }]
    
    university_layer = pdk.Layer(
        "ScatterplotLayer",
        data=university_data,
        get_position=['lon', 'lat'],
        get_fill_color=[0, 0, 255, 200],
        get_radius=100,
        pickable=True
    )
    
    # ビューステート
    view_state = pdk.ViewState(
        latitude=center[0],
        longitude=center[1],
        zoom=13,
        pitch=45,
        bearing=0
    )
    
    # デッキ作成
    deck = pdk.Deck(
        layers=[road_layer, university_layer],
        initial_view_state=view_state,
        tooltip={
            "html": "<b>道路名:</b> {road_name}<br/>"
                   "<b>平均速度:</b> {speed:.1f} km/h<br/>"
                   "<b>混雑度:</b> {congestion}",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        },
        map_style='mapbox://styles/mapbox/light-v9'
    )
    
    return deck

def main():
    st.title("🗺️ 東京医科歯科大学周辺 交通混雑度マップ - PyDeck版")
    st.markdown("---")
    
    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # データ更新
        if st.button("📱 データを更新", type="primary"):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # 3D設定
        st.subheader("🎮 3D表示設定")
        pitch = st.slider("視点角度", 0, 60, 45, help="地図の傾き角度")
        bearing = st.slider("回転角度", 0, 360, 0, help="地図の回転角度")
        
        st.markdown("---")
        
        # 凡例
        st.subheader("📊 混雑度凡例")
        st.markdown("🟢 **空いている** (≥30km/h)")
        st.markdown("🟡 **やや混雑** (20-30km/h)")
        st.markdown("🔴 **混雑** (<20km/h)")
        st.markdown("⚫ **データなし**")
    
    # メインコンテンツ
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("🗺️ 3D交通状況マップ")
        
        # データ読み込み
        with st.spinner("データを読み込み中..."):
            roads_df, status_info = load_and_process_data()
        
        if not roads_df.empty:
            # PyDeckマップ表示
            deck = create_pydeck_map(roads_df)
            
            # 動的にview_stateを更新
            deck.initial_view_state.pitch = pitch
            deck.initial_view_state.bearing = bearing
            
            st.pydeck_chart(deck)
        else:
            st.error("データの読み込みに失敗しました")
    
    with col2:
        st.subheader("📊 データ状況")
        
        # ステータス表示
        if status_info["status"] == "real":
            st.success("✅ リアルデータ")
            st.metric("道路総数", status_info["road_count"])
            st.metric("交通観測点", status_info["traffic_count"])
            st.metric("マッチング成功", status_info["matched_count"])
            st.metric("表示道路数", status_info["final_roads"])
        else:
            st.warning("⚠️ モックデータ")
            if "error" in status_info:
                st.error(f"エラー: {status_info['error']}")
            st.info("実データの処理に失敗したため、デモ用データを表示中")
        
        # 統計情報
        if not roads_df.empty:
            st.subheader("📈 統計情報")
            
            # 混雑度分布
            congestion_counts = roads_df['congestion'].value_counts()
            
            for congestion, count in congestion_counts.items():
                emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴', 'unknown': '⚫'}.get(congestion, '❓')
                label = {'low': '空いている', 'medium': 'やや混雑', 'high': '混雑', 'unknown': '不明'}.get(congestion, '不明')
                st.write(f"{emoji} {label}: {count}路線")
            
            # 平均速度
            avg_speed = roads_df['speed'].mean()
            st.metric("平均速度", f"{avg_speed:.1f} km/h")
    
    # フッター
    st.markdown("---")
    jst = pytz.timezone("Asia/Tokyo")
    now_jst = datetime.now(tz=jst)
    st.caption(f"🕒 最終更新: {now_jst.strftime('%Y-%m-%d %H:%M:%S')} JST")
    st.caption("🎮 左サイドバーで3D表示を調整できます")

if __name__ == "__main__":
    main()