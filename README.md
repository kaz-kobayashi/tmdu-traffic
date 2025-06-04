# 東京医科歯科大学周辺 交通混雑度マップ

東京医科歯科大学湯島キャンパス周辺5km四方の道路混雑度をリアルタイムで可視化するWebアプリケーションです。

## 🚀 クイックスタート

### 1. 環境セットアップ

```bash
# 依存ライブラリインストール
pip install -r app_requirements.txt
```

### 2. アプリ起動

```bash
# Streamlitアプリ起動
streamlit run app.py
```

ブラウザで http://localhost:8501 にアクセスしてください。

## 📊 主要機能

### 🗺️ リアルタイム交通マップ
- **JARTIC交通量API**からの5分間隔データ取得
- **混雑度3段階表示**（緑：空き/黄：やや混雑/赤：混雑）
- **インタラクティブ地図**（ズーム、パン、クリック詳細表示）

### 📈 統計ダッシュボード
- 道路別混雑度分布
- 平均速度・旅行時間統計
- リアルタイム更新（5分間隔）

### ⚙️ カスタマイズ機能
- 混雑度しきい値調整
- 自動更新ON/OFF
- 詳細統計表示切替

## 🎯 対象エリア

**東京医科歯科大学湯島キャンパス中心5km四方**
- 中心座標: 35.7056°N, 139.7644°E
- 対象道路: 一般道路（JARTIC道路種別=3）

## 🏗️ システム構成

```
app.py                    # Streamlitメインアプリ
├── config.py            # 設定管理
├── traffic_data.py      # 交通データ取得
├── road_data.py        # 道路データ処理
├── spatial_processor.py # 空間データ統合
├── congestion_analyzer.py # 混雑度分析
└── map_visualizer.py   # 地図可視化
```

## 📡 データソース

- **交通データ**: [JARTIC公開交通データ](https://api.jartic-open-traffic.org/)
- **道路データ**: [国土数値情報 道路中心線](https://nlftp.mlit.go.jp/ksj/)

## ⚠️ 前提条件

1. **道路データファイル必須**
   - `N01-07L-13-01.0a_GML.zip` が同一ディレクトリに必要
   - [国土数値情報ダウンロードサイト](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N01-v3_0.html)から取得

2. **インターネット接続**
   - JARTIC APIへのリアルタイムアクセスが必要

## 🔧 トラブルシューティング

### よくある問題

**❌ 道路データが見つからない**
```
FileNotFoundError: N01-07L-13-01.0a_GML.zip
```
→ 国土数値情報から東京都道路データをダウンロードして配置

**❌ 交通データ取得エラー**
```
API request failed
```
→ インターネット接続とJARTIC APIの稼働状況を確認

**❌ geopandasインストールエラー**
```bash
# conda使用を推奨
conda install geopandas
```

### デバッグモード

個別モジュールのテスト実行:
```bash
python traffic_data.py    # 交通データ取得テスト
python road_data.py      # 道路データ読込テスト
python map_visualizer.py # 地図作成テスト
```

## 📈 パフォーマンス

- **データ取得**: 30秒以内
- **地図描画**: 3秒以内  
- **キャッシュ**: 5分間隔で自動更新

## 🔮 今後の拡張予定

- 時系列分析機能
- 他大学エリア対応
- 混雑予測機能
- モバイル対応

## 📄 ライセンス

このプロジェクトはMITライセンスのもとで公開されています。

## 🤝 コントリビューション

バグ報告や機能要望は Issues でお知らせください。

---

**開発者**: Claude Code  
**最終更新**: 2025年6月