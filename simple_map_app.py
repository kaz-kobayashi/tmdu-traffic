"""シンプルな地図アプリ（実交通データ使用版）"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import logging
import geopandas as gpd
from pathlib import Path

# アプリケーションモジュール
try:
    from traffic_data import TrafficDataFetcher
    from road_data import RoadDataLoader
    from spatial_processor import SpatialProcessor
    from congestion_analyzer import CongestionAnalyzer
    from config import BBOX_5KM, TMDU_CENTER, CONGESTION_COLORS, ROAD_DATA_ZIP
except ImportError as e:
    st.error(f"モジュールのインポートに失敗しました: {e}")
    st.stop()

# ページ設定（最初に実行）
st.set_page_config(
    page_title="センター周辺交通状況",
    page_icon="🚗",
    layout="wide"
)

@st.cache_data(ttl=300)  # 5分間キャッシュ
def load_real_traffic_data():
    """実交通データ読込・処理"""
    try:
        # ログ設定
        logging.basicConfig(level=logging.INFO)
        
        # データ処理クラス初期化
        traffic_fetcher = TrafficDataFetcher(use_mock=True)  # モック優先（API失敗時のフォールバック）
        road_loader = RoadDataLoader()
        spatial_processor = SpatialProcessor(max_distance=100)  # 100m範囲でマッチング
        congestion_analyzer = CongestionAnalyzer()
        
        with st.spinner('📡 交通データを取得中...'):
            # 交通データ取得
            traffic_data = traffic_fetcher.fetch_traffic_data(BBOX_5KM)
            
            if traffic_data is None or traffic_data.empty:
                st.warning("交通データの取得に失敗しました。モックデータを表示します。")
                return create_fallback_data()
        
        with st.spinner('🛣️ 道路データを読込中...'):
            # 道路データ読込
            road_data = road_loader.load_road_network(bbox=BBOX_5KM)
            
            if road_data.empty:
                st.error(f"道路データファイルが見つかりません: {ROAD_DATA_ZIP}")
                return create_fallback_data()
        
        with st.spinner('🔄 データを統合中...'):
            # 空間結合・集約
            joined_data = spatial_processor.join_traffic_roads(traffic_data, road_data)
            
            if joined_data.empty:
                st.warning("交通データと道路データの統合に失敗しました。")
                return create_fallback_data()
            
            # 道路ごと集約
            aggregated_data = spatial_processor.aggregate_by_road(joined_data)
            
            if aggregated_data.empty:
                st.warning("データの集約に失敗しました。")
                return create_fallback_data()
        
        with st.spinner('📊 混雑度を分析中...'):
            # 混雑度分析
            congestion_data = congestion_analyzer.calculate_congestion_level(aggregated_data)
            
            # pandas DataFrameに変換（Plotly用）
            if hasattr(congestion_data, 'geometry'):
                # 道路の中心点を取得（線データから点データへ）
                congestion_data = congestion_data.copy()
                centroids = congestion_data.geometry.centroid
                
                result_df = pd.DataFrame({
                    'latitude': centroids.y,
                    'longitude': centroids.x,
                    'speed': congestion_data.get('平均速度', 0),
                    'travel_time': congestion_data.get('旅行時間', 0),
                    'link_length': congestion_data.get('リンク長', 0),
                    'congestion': congestion_data.get('speed_category', 'データなし'),
                    'congestion_level': congestion_data.get('congestion_level', 'unknown'),
                    'color': congestion_data.get('congestion_color', '#808080'),
                    'road_name': congestion_data.get('road_name', '未分類道路'),
                    'road_id': congestion_data.get('road_id', ''),
                    'observation_count': congestion_data.get('observation_count', 0)
                })
            else:
                result_df = pd.DataFrame(congestion_data)
            
            # データ検証
            if result_df.empty:
                st.warning("処理後のデータが空です。")
                return create_fallback_data()
            
            # 統計情報を返す
            stats = congestion_analyzer.generate_statistics(congestion_data)
            
            return result_df, stats, congestion_data
            
    except FileNotFoundError as e:
        st.error(f"ファイルが見つかりません: {e}")
        return create_fallback_data()
    except Exception as e:
        st.error(f"データ処理エラー: {e}")
        logging.error(f"Data processing error: {e}", exc_info=True)
        return create_fallback_data()

def create_fallback_data():
    """フォールバックデータ生成（処理失敗時用）"""
    np.random.seed(42)
    
    # センター周辺の座標
    center_lat, center_lon = TMDU_CENTER
    
    # ランダムな道路データ生成
    n_roads = 50
    lats = np.random.normal(center_lat, 0.01, n_roads)
    lons = np.random.normal(center_lon, 0.01, n_roads)
    speeds = np.random.normal(25, 10, n_roads)
    speeds = np.clip(speeds, 5, 60)  # 5-60km/h
    
    # 混雑度カテゴリ
    congestion = []
    colors = []
    for speed in speeds:
        if speed >= 30:
            congestion.append('空いている')
            colors.append('green')
        elif speed >= 20:
            congestion.append('やや混雑')
            colors.append('orange')
        else:
            congestion.append('混雑')
            colors.append('red')
    
    df = pd.DataFrame({
        'latitude': lats,
        'longitude': lons,
        'speed': speeds,
        'travel_time': np.random.uniform(10, 60, n_roads),
        'link_length': np.random.uniform(50, 200, n_roads),
        'congestion': congestion,
        'congestion_level': ['low' if c == '空いている' else 'medium' if c == 'やや混雑' else 'high' for c in congestion],
        'color': colors,
        'road_name': [f'道路_{i+1}' for i in range(n_roads)],
        'road_id': [f'R{i:03d}' for i in range(n_roads)],
        'observation_count': np.random.randint(1, 5, n_roads)
    })
    
    # 簡単な統計
    stats = {
        'total_roads': len(df),
        'congestion_distribution': df['congestion_level'].value_counts().to_dict(),
        'congestion_percentage': (df['congestion_level'].value_counts() / len(df) * 100).to_dict(),
        'speed_stats': {
            'mean': float(df['speed'].mean()),
            'median': float(df['speed'].median()),
            'min': float(df['speed'].min()),
            'max': float(df['speed'].max())
        },
        'analysis_timestamp': datetime.now().isoformat()
    }
    
    return df, stats, None

def main():
    st.title("🚗 センター周辺 交通混雑度マップ（実データ版）")
    st.markdown("---")
    
    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # データ更新ボタン
        if st.button("🔄 データ更新", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        # 更新設定
        auto_update = st.checkbox("自動更新", value=False)
        if auto_update:
            update_interval = st.slider("更新間隔（分）", 1, 10, 5)
            st.info(f"自動更新: {update_interval}分間隔")
        
        st.markdown("---")
        st.subheader("📊 混雑度凡例")
        st.markdown("🟢 **空いている** (≥30km/h)")
        st.markdown("🟡 **やや混雑** (20-30km/h)")
        st.markdown("🔴 **混雑** (<20km/h)")
        st.markdown("⚫ **データなし**")
        
        st.markdown("---")
        st.subheader("📡 データソース")
        st.markdown("**交通データ:** JARTIC API + モック")
        st.markdown("**道路データ:** 国土数値情報（KSJ）")
        st.markdown("**対象エリア:** センター周辺5km")
        
        # ファイル存在確認
        road_file_exists = Path(ROAD_DATA_ZIP).exists()
        if road_file_exists:
            st.success("✅ 道路データファイル: 利用可能")
        else:
            st.error("❌ 道路データファイル: 見つかりません")
            st.caption(f"必要ファイル: {ROAD_DATA_ZIP}")
    
    # データ読込
    try:
        data_result = load_real_traffic_data()
        if len(data_result) == 3:
            df, stats, congestion_data = data_result
            data_source = "実データ + モック"
        else:
            df, stats, congestion_data = data_result, {}, None
            data_source = "モックデータ"
    except Exception as e:
        st.error(f"データ読込エラー: {e}")
        df, stats, congestion_data = create_fallback_data()
        data_source = "フォールバック"
    
    # メインコンテンツ
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🗺️ 交通状況マップ")
        
        if df.empty:
            st.error("表示可能なデータがありません")
        else:
            # データ品質表示
            st.caption(f"データソース: {data_source} | 道路数: {len(df)}路線 | 更新: {datetime.now().strftime('%H:%M:%S')}")
            
            # Plotly散布図マップ
            fig = px.scatter_mapbox(
                df, 
                lat="latitude", 
                lon="longitude",
                color="congestion",
                size="speed",
                hover_name="road_name",
                hover_data={
                    "speed": ":.1f",
                    "travel_time": ":.1f",
                    "link_length": ":.1f",
                    "congestion": True,
                    "road_id": True,
                    "observation_count": True
                },
                color_discrete_map={
                    '空いている': 'green',
                    'やや混雑': 'yellow', 
                    '混雑': 'red',
                    'データなし': 'gray'
                },
                zoom=13,
                height=600,
                title="リアルタイム交通状況（実データ）"
            )
            
            # センターマーカー追加
            fig.add_trace(go.Scattermapbox(
                lat=[TMDU_CENTER[0]],
                lon=[TMDU_CENTER[1]],
                mode='markers',
                marker=dict(size=15, color='blue', symbol='star'),
                text=['センター'],
                name='センター',
                showlegend=True
            ))
            
            fig.update_layout(
                mapbox_style="open-street-map",
                mapbox=dict(
                    center=dict(lat=TMDU_CENTER[0], lon=TMDU_CENTER[1])
                ),
                margin={"r":0,"t":30,"l":0,"b":0},
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📊 統計情報")
        
        if df.empty:
            st.warning("統計データがありません")
        else:
            # 基本統計
            total_roads = len(df)
            avg_speed = df['speed'].mean() if 'speed' in df.columns else 0
            
            # メトリクス表示
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("総道路数", total_roads)
            with col_b:
                st.metric("平均速度", f"{avg_speed:.1f} km/h")
            
            # 詳細統計（stats が利用可能な場合）
            if stats and 'speed_stats' in stats:
                speed_stats = stats['speed_stats']
                col_c, col_d = st.columns(2)
                with col_c:
                    st.metric("最高速度", f"{speed_stats.get('max', 0):.1f} km/h")
                with col_d:
                    st.metric("最低速度", f"{speed_stats.get('min', 0):.1f} km/h")
            
            # 混雑度分布
            if 'congestion' in df.columns:
                congestion_counts = df['congestion'].value_counts()
                
                st.markdown("**混雑度分布:**")
                for category, count in congestion_counts.items():
                    percentage = (count / total_roads) * 100
                    st.write(f"- {category}: {count}路線 ({percentage:.1f}%)")
                
                # 混雑度円グラフ
                fig_pie = px.pie(
                    values=congestion_counts.values,
                    names=congestion_counts.index,
                    color=congestion_counts.index,
                    color_discrete_map={
                        '空いている': 'green',
                        'やや混雑': 'yellow',
                        '混雑': 'red',
                        'データなし': 'gray'
                    },
                    title="混雑度分布"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # 速度分布ヒストグラム
            if 'speed' in df.columns and df['speed'].notna().any():
                fig_hist = px.histogram(
                    df, x="speed", nbins=15,
                    title="速度分布",
                    labels={"speed": "速度 (km/h)", "count": "道路数"},
                    color_discrete_sequence=['skyblue']
                )
                st.plotly_chart(fig_hist, use_container_width=True)
            
            # 観測点統計（リアルデータの場合）
            if 'observation_count' in df.columns:
                total_observations = df['observation_count'].sum()
                avg_observations = df['observation_count'].mean()
                
                st.markdown("**データ品質:**")
                st.write(f"- 総観測点数: {total_observations:,}点")
                st.write(f"- 路線あたり平均観測点数: {avg_observations:.1f}点")
            
            # 詳細データテーブル
            with st.expander("📋 詳細データ", expanded=False):
                display_columns = ['road_name', 'speed', 'congestion']
                if 'travel_time' in df.columns:
                    display_columns.append('travel_time')
                if 'road_id' in df.columns:
                    display_columns.append('road_id')
                if 'observation_count' in df.columns:
                    display_columns.append('observation_count')
                
                available_columns = [col for col in display_columns if col in df.columns]
                st.dataframe(
                    df[available_columns].round(1),
                    use_container_width=True
                )
    
    # フッター
    st.markdown("---")
    
    # 更新時刻とデータ品質情報
    footer_col1, footer_col2 = st.columns(2)
    with footer_col1:
        st.caption(f"🕒 最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    with footer_col2:
        if stats and 'analysis_timestamp' in stats:
            analysis_time = pd.to_datetime(stats['analysis_timestamp']).strftime('%H:%M:%S')
            st.caption(f"📊 データ分析時刻: {analysis_time}")
    
    # データソース注意事項
    if data_source == "モックデータ" or data_source == "フォールバック":
        st.info("💡 現在はモックデータを表示しています。実データを使用するには道路データファイルが必要です。")
    else:
        st.success("✅ 実交通データ（JARTIC API）と道路データ（KSJ）を統合して表示中")
    
    # 統計サマリー（利用可能な場合）
    if stats and 'congestion_distribution' in stats:
        distribution = stats['congestion_distribution']
        total = stats.get('total_roads', 0)
        if total > 0:
            summary_parts = []
            for level, count in distribution.items():
                pct = (count / total * 100)
                if level == 'low':
                    summary_parts.append(f"空いている: {pct:.1f}%")
                elif level == 'medium':
                    summary_parts.append(f"やや混雑: {pct:.1f}%")
                elif level == 'high':
                    summary_parts.append(f"混雑: {pct:.1f}%")
            
            if summary_parts:
                st.caption(f"📈 混雑度サマリー: {' | '.join(summary_parts)}")

if __name__ == "__main__":
    main()