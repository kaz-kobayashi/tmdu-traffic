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
        st.error("必要なモジュールがインポートできません")
        return pd.DataFrame(), {"status": "error", "error": "モジュール不可"}
    
    status_info = {"status": "processing"}
    
    try:
        # データ読み込み
        st.info("📂 道路データを読み込み中...")
        loader = RoadDataLoader()
        road_gdf = loader.load_road_data(bbox=BBOX_5KM)
        
        if road_gdf.empty:
            st.error("❌ 道路データファイル（N01-07L-13-01.0a_GML.zip）が見つかりません")
            return pd.DataFrame(), {"status": "error", "error": "道路データなし"}
        
        st.success(f"✅ 道路データ読み込み完了: {len(road_gdf)} 路線")
        
        # 交通データ取得
        st.info("🚗 交通データを取得中...")
        fetcher = TrafficDataFetcher(use_mock=False)  # 実データを強制
        traffic_gdf = fetcher.fetch_traffic_data(bbox=BBOX_5KM)
        
        if traffic_gdf.empty:
            st.warning("⚠️ JARTIC APIからデータを取得できませんでした。モックデータを使用します。")
            fetcher_mock = TrafficDataFetcher(use_mock=True)
            traffic_gdf = fetcher_mock.fetch_traffic_data(bbox=BBOX_5KM)
            status_info["data_source"] = "mock"
        else:
            st.success(f"✅ 交通データ取得完了: {len(traffic_gdf)} 観測点")
            status_info["data_source"] = "real"
        
        # 空間結合
        st.info("🗺️ 空間データ結合中...")
        processor = SpatialProcessor(max_distance=200.0)  # 距離を200mに拡大
        joined_gdf = processor.join_traffic_roads(traffic_gdf, road_gdf)
        
        if joined_gdf.empty:
            st.error("❌ 空間結合に失敗しました")
            return pd.DataFrame(), {"status": "error", "error": "空間結合失敗"}
        
        # マッチング統計
        matched_count = len(joined_gdf[joined_gdf['road_id'].notna()])
        match_rate = matched_count / len(joined_gdf) if len(joined_gdf) > 0 else 0
        st.success(f"✅ 空間結合完了: {matched_count}/{len(joined_gdf)} ({match_rate:.1%}) マッチ")
        
        # 道路別集約
        st.info("📊 道路別データ集約中...")
        road_stats = processor.aggregate_by_road(joined_gdf, road_gdf)
        
        if road_stats.empty:
            st.error("❌ 道路別集約に失敗しました")
            return pd.DataFrame(), {"status": "error", "error": "集約失敗"}
        
        st.success(f"✅ 集約完了: {len(road_stats)} 路線にデータが集約されました")
        
        # 混雑度分析
        st.info("🚦 混雑度分析中...")
        analyzer = CongestionAnalyzer()
        final_data = analyzer.calculate_congestion_level(road_stats)
        
        # PyDeck用データ準備
        pydeck_data = prepare_pydeck_data(final_data)
        
        if pydeck_data.empty:
            st.error("❌ PyDeck用データ変換に失敗しました")
            return pd.DataFrame(), {"status": "error", "error": "データ変換失敗"}
        
        st.success(f"✅ 処理完了: {len(pydeck_data)} 路線を地図表示用に変換")
        
        status_info.update({
            "status": "success",
            "road_count": len(road_gdf),
            "traffic_count": len(traffic_gdf),
            "matched_count": matched_count,
            "match_rate": match_rate,
            "final_roads": len(final_data),
            "pydeck_roads": len(pydeck_data)
        })
        
        return pydeck_data, status_info
        
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        st.error(f"❌ データ処理エラー: {str(e)}")
        return pd.DataFrame(), {"status": "error", "error": str(e)}

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
        roads_df, status_info = load_and_process_data()
        
        if not roads_df.empty and status_info["status"] == "success":
            # PyDeckマップ表示
            deck = create_pydeck_map(roads_df)
            
            # 動的にview_stateを更新
            deck.initial_view_state.pitch = pitch
            deck.initial_view_state.bearing = bearing
            
            st.pydeck_chart(deck)
        else:
            if status_info["status"] == "error":
                st.error("❌ データ処理に失敗しました")
                st.info("必要なファイル:")
                st.code("N01-07L-13-01.0a_GML.zip (道路データ)")
                st.info("このファイルをプロジェクトルートに配置してください")
            else:
                st.error("データの読み込みに失敗しました")
    
    with col2:
        st.subheader("📊 データ状況")
        
        # ステータス表示
        if status_info["status"] == "success":
            if status_info.get("data_source") == "real":
                st.success("✅ リアル交通データ")
            else:
                st.warning("⚠️ モック交通データ")
                st.caption("JARTIC APIが利用できないため")
            
            st.metric("道路総数", status_info["road_count"])
            st.metric("交通観測点", status_info["traffic_count"])
            st.metric("マッチング成功", f"{status_info['matched_count']} ({status_info['match_rate']:.1%})")
            st.metric("集約後道路数", status_info["final_roads"])
            st.metric("表示道路数", status_info["pydeck_roads"])
            
        elif status_info["status"] == "error":
            st.error("❌ データ処理エラー")
            st.caption(f"詳細: {status_info.get('error', '不明なエラー')}")
            
            # 解決方法の提示
            st.subheader("🔧 解決方法")
            st.markdown("""
            1. **道路データファイル確認**
               - `N01-07L-13-01.0a_GML.zip` が必要
               - [国土数値情報](https://nlftp.mlit.go.jp/ksj/)からダウンロード
            
            2. **ファイル配置**
               - プロジェクトルートディレクトリに配置
               - Streamlit Cloudの場合はリポジトリに追加
            """)
        else:
            st.info("⏳ データ処理中...")
        
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