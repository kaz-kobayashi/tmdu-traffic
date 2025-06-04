"""シンプルな地図アプリ（folium不要版）"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# ページ設定（最初に実行）
st.set_page_config(
    page_title="東京医科歯科大学周辺交通状況",
    page_icon="🚗",
    layout="wide"
)

def create_mock_data():
    """モックデータ生成"""
    np.random.seed(42)
    
    # 東京医科歯科大学周辺の座標
    center_lat, center_lon = 35.7056, 139.7644
    
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
    
    return pd.DataFrame({
        'latitude': lats,
        'longitude': lons,
        'speed': speeds,
        'congestion': congestion,
        'color': colors,
        'road_name': [f'道路_{i+1}' for i in range(n_roads)]
    })

def main():
    st.title("🚗 東京医科歯科大学周辺 交通混雑度マップ")
    st.markdown("---")
    
    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        auto_update = st.checkbox("自動更新", value=False)
        update_interval = st.slider("更新間隔（分）", 1, 10, 5)
        
        st.markdown("---")
        st.subheader("📊 混雑度凡例")
        st.markdown("🟢 **空いている** (≥30km/h)")
        st.markdown("🟠 **やや混雑** (20-30km/h)")
        st.markdown("🔴 **混雑** (<20km/h)")
    
    # メインコンテンツ
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🗺️ 交通状況マップ")
        
        # データ生成
        df = create_mock_data()
        
        # Plotly散布図マップ
        fig = px.scatter_mapbox(
            df, 
            lat="latitude", 
            lon="longitude",
            color="congestion",
            size="speed",
            hover_name="road_name",
            hover_data={"speed": True, "congestion": True},
            color_discrete_map={
                '空いている': 'green',
                'やや混雑': 'orange', 
                '混雑': 'red'
            },
            zoom=13,
            height=600,
            title="リアルタイム交通状況"
        )
        
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(
                center=dict(lat=35.7056, lon=139.7644)
            ),
            margin={"r":0,"t":30,"l":0,"b":0}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📊 統計情報")
        
        # 統計表示
        total_roads = len(df)
        avg_speed = df['speed'].mean()
        
        # 混雑度分布
        congestion_counts = df['congestion'].value_counts()
        
        st.metric("総道路数", total_roads)
        st.metric("平均速度", f"{avg_speed:.1f} km/h")
        
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
                'やや混雑': 'orange',
                '混雑': 'red'
            },
            title="混雑度分布"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # 速度分布ヒストグラム
        fig_hist = px.histogram(
            df, x="speed", nbins=15,
            title="速度分布",
            labels={"speed": "速度 (km/h)", "count": "道路数"}
        )
        st.plotly_chart(fig_hist, use_container_width=True)
    
    # フッター
    st.markdown("---")
    st.caption(f"🕒 最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption("💡 これはデモ用のモックデータです")

if __name__ == "__main__":
    main()