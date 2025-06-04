"""道路データ処理モジュール"""
import geopandas as gpd
import zipfile
from pathlib import Path
from typing import Optional, Tuple
import logging
from config import ROAD_DATA_ZIP

class RoadDataLoader:
    """KSJ道路データ読込・処理クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._cached_roads: Optional[gpd.GeoDataFrame] = None
    
    def load_road_network(self, zip_path: Path = None, 
                         bbox: Optional[Tuple[float, float, float, float]] = None) -> gpd.GeoDataFrame:
        """
        道路ネットワークデータ読込
        
        Args:
            zip_path: KSJのZIPファイルパス（Noneの場合は設定ファイルのパス使用）
            bbox: フィルタリング用bbox (minLon, minLat, maxLon, maxLat)
            
        Returns:
            GeoDataFrame: 道路データ（EPSG:4326）
        """
        if zip_path is None:
            zip_path = Path(ROAD_DATA_ZIP)
        
        try:
            # キャッシュから読込（同じファイルの場合）
            if self._cached_roads is not None:
                self.logger.info("Using cached road data")
                roads = self._cached_roads.copy()
            else:
                self.logger.info(f"Loading road data from {zip_path}")
                roads = self._load_from_zip(zip_path)
                self._cached_roads = roads.copy()  # キャッシュ保存
                self.logger.info(f"Loaded {len(roads)} road segments")
            
            # BBOX フィルタリング
            if bbox:
                before_count = len(roads)
                roads = self._filter_by_bbox(roads, bbox)
                self.logger.info(f"Filtered by bbox: {before_count} -> {len(roads)} roads")
            
            # スキーマ標準化
            roads = self._standardize_road_schema(roads)
            
            return roads
            
        except Exception as e:
            self.logger.error(f"Road data loading failed: {e}")
            return gpd.GeoDataFrame()
    
    def _load_from_zip(self, zip_path: Path) -> gpd.GeoDataFrame:
        """ZIPファイルからShapefile読込"""
        if not zip_path.exists():
            raise FileNotFoundError(f"Road data file not found: {zip_path}")
        
        with zipfile.ZipFile(zip_path) as zf:
            shp_files = [name for name in zf.namelist() if name.endswith('.shp')]
            if not shp_files:
                raise FileNotFoundError("No shapefile found in ZIP")
            
            # 道路データのShapefileを選択（通常は"Road"が含まれる）
            road_shp = None
            for shp in shp_files:
                if 'Road' in shp or 'road' in shp.lower():
                    road_shp = shp
                    break
            
            if road_shp is None:
                road_shp = shp_files[0]  # 最初のshpファイルを使用
                
            self.logger.info(f"Loading shapefile: {road_shp}")
        
        # Shapefileを読込
        gdf = gpd.read_file(f"zip://{zip_path}!{road_shp}")
        
        # CRS変換（JGD2000 → WGS84）
        if gdf.crs is not None:
            original_crs = gdf.crs
            gdf = gdf.to_crs('EPSG:4326')
            self.logger.info(f"Converted CRS: {original_crs} -> EPSG:4326")
        else:
            self.logger.warning("No CRS information found, assuming EPSG:4326")
            gdf.crs = 'EPSG:4326'
        
        return gdf
    
    def _filter_by_bbox(self, gdf: gpd.GeoDataFrame, 
                       bbox: Tuple[float, float, float, float]) -> gpd.GeoDataFrame:
        """BBOX による空間フィルタリング"""
        minx, miny, maxx, maxy = bbox
        
        # cx indexerを使用した効率的なフィルタリング
        try:
            filtered_gdf = gdf.cx[minx:maxx, miny:maxy]
            return filtered_gdf
        except Exception as e:
            self.logger.warning(f"Spatial filtering failed, using bounds method: {e}")
            
            # フォールバック: bounds を使用
            bounds = gdf.bounds
            mask = (
                (bounds['minx'] <= maxx) & (bounds['maxx'] >= minx) &
                (bounds['miny'] <= maxy) & (bounds['maxy'] >= miny)
            )
            return gdf[mask]
    
    def _standardize_road_schema(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """道路データのスキーマ標準化"""
        if gdf.empty:
            return gdf
        
        # KSJ標準スキーマ対応
        column_mapping = {
            'N01_002': 'road_id',
            'N01_001': 'road_class', 
            'N01_003': 'road_name',
            'N01_004': 'road_number'
        }
        
        # 列名変更（存在する列のみ）
        available_columns = {k: v for k, v in column_mapping.items() if k in gdf.columns}
        if available_columns:
            gdf = gdf.rename(columns=available_columns)
            self.logger.info(f"Renamed columns: {available_columns}")
        
        # road_idの標準化
        if 'road_id' in gdf.columns:
            gdf['road_id'] = gdf['road_id'].astype(str).str.zfill(3)
        elif gdf.index.name is None:
            # road_idが無い場合はindexから生成
            gdf['road_id'] = gdf.index.astype(str).str.zfill(6)
            self.logger.info("Generated road_id from index")
        
        # 道路名の処理
        if 'road_name' in gdf.columns:
            # 空の道路名を処理
            gdf['road_name'] = gdf['road_name'].fillna('未分類道路')
        else:
            gdf['road_name'] = '道路'
        
        # 必要な列のみ保持
        keep_columns = ['road_id', 'road_class', 'road_name', 'geometry']
        # 存在する列のみ保持
        existing_columns = [col for col in keep_columns if col in gdf.columns]
        
        if 'geometry' not in existing_columns:
            self.logger.error("Geometry column not found in road data")
            return gpd.GeoDataFrame()
        
        result = gdf[existing_columns].copy()
        
        # ジオメトリの検証
        invalid_geom = result['geometry'].isna() | (~result['geometry'].is_valid)
        if invalid_geom.any():
            invalid_count = invalid_geom.sum()
            result = result[~invalid_geom]
            self.logger.warning(f"Removed {invalid_count} records with invalid geometry")
        
        return result
    
    def get_road_statistics(self, gdf: gpd.GeoDataFrame) -> dict:
        """道路データの統計情報取得"""
        if gdf.empty:
            return {}
        
        stats = {
            'total_roads': len(gdf),
            'has_road_class': 'road_class' in gdf.columns,
            'has_road_name': 'road_name' in gdf.columns,
            'crs': str(gdf.crs),
            'bounds': gdf.total_bounds.tolist()
        }
        
        if 'road_class' in gdf.columns:
            stats['road_class_distribution'] = gdf['road_class'].value_counts().to_dict()
        
        return stats


def test_road_loader():
    """道路データ読込テスト"""
    from config import BBOX_5KM
    
    loader = RoadDataLoader()
    
    # ログ設定
    logging.basicConfig(level=logging.INFO)
    
    print("Testing road data loading...")
    
    # 道路データ読込テスト
    road_data = loader.load_road_network(bbox=BBOX_5KM)
    
    if not road_data.empty:
        print(f"✅ Successfully loaded {len(road_data)} road segments")
        print(f"Columns: {list(road_data.columns)}")
        print(f"CRS: {road_data.crs}")
        print(f"Bounds: {road_data.total_bounds}")
        
        # 統計情報
        stats = loader.get_road_statistics(road_data)
        print(f"Statistics: {stats}")
        
        # サンプルデータ表示
        print("Sample data:")
        print(road_data.head())
        
    else:
        print("❌ Failed to load road data")
        print("Make sure the road data ZIP file exists in the current directory")


if __name__ == "__main__":
    test_road_loader()