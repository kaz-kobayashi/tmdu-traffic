
"""
tokyo_road_loader.py
--------------------
Utility for loading Tokyo road centerline data
(N01-07L-13-01.0a_GML.zip from KSJ) and performing
basic operations such as CRS conversion and nearest‐road
search for traffic observation points.

Requirements:
    pip install geopandas pyproj shapely fiona rtree pandas

Usage example:
    python tokyo_road_loader.py --zip N01-07L-13-01.0a_GML.zip \
                                --obs obs_points.csv \
                                --output linked_points.geojson
"""

import argparse
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


def load_roads(zip_path: Path, shp_name: str = None) -> gpd.GeoDataFrame:
    """Load KSJ road centerline data from a ZIP archive.

    Args:
        zip_path: Path to the KSJ ZIP file.
        shp_name: Optional shapefile name inside the ZIP.
                  If None, the first .shp found is used.

    Returns:
        GeoDataFrame in EPSG:4326 with columns:
            - road_id  (str)
            - road_class (str)  KSJ N01_001
            - road_name  (str)  KSJ N01_003
            - geometry   (LineString/MultiLineString)
    """
    # Auto-detect shapefile if not provided
    if shp_name is None:
        with zipfile.ZipFile(zip_path) as zf:
            shp_candidates = [m for m in zf.namelist() if m.lower().endswith('.shp')]
            if not shp_candidates:
                raise FileNotFoundError("No .shp file found in ZIP archive.")
            shp_name = shp_candidates[0]

    gdf = gpd.read_file(f"zip://{zip_path}!{shp_name}")
    # Convert JGD2000 (EPSG:4612) → WGS84 (EPSG:4326)
    gdf = gdf.to_crs(4326)

    # Prepare key columns
    gdf["road_id"] = gdf["N01_002"].astype(str).str.zfill(3)
    gdf = gdf[["road_id", "N01_001", "N01_003", "geometry"]].rename(
        columns={"N01_001": "road_class", "N01_003": "road_name"}
    )
    return gdf


def load_obs(obs_csv: Path) -> gpd.GeoDataFrame:
    """Load observation points CSV with columns: obs_code, lon, lat"""
    df = pd.read_csv(obs_csv)
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.lon, df.lat),
        crs=4326
    )
    return gdf


def attach_nearest_road(gdf_obs: gpd.GeoDataFrame,
                        gdf_roads: gpd.GeoDataFrame,
                        max_distance_m: float = 20) -> gpd.GeoDataFrame:
    """Spatially join nearest road_id to each observation point.

    Args:
        gdf_obs: observation points (EPSG:4326)
        gdf_roads: roads (EPSG:4326)
        max_distance_m: max planar distance in metres to accept match

    Returns:
        gdf_obs with added 'road_id' column (NaN if no match)
    """
    # Reproject to metric CRS for distance calculation
    gdf_obs_m = gdf_obs.to_crs(3857)
    gdf_roads_m = gdf_roads.to_crs(3857)
    joined = gpd.sjoin_nearest(
        gdf_obs_m, gdf_roads_m[["road_id", "geometry"]],
        how="left", max_distance=max_distance_m
    )
    gdf_obs["road_id"] = joined["road_id"].values
    return gdf_obs


def main():
    parser = argparse.ArgumentParser(description="Tokyo road loader & joiner")
    parser.add_argument("--zip", type=Path, required=True,
                        help="Path to KSJ ZIP file (e.g., N01-07L-13-01.0a_GML.zip)")
    parser.add_argument("--obs", type=Path, required=True,
                        help="CSV with columns obs_code,lon,lat for observation points")
    parser.add_argument("--output", type=Path, default="linked_points.geojson",
                        help="Output GeoJSON with road_id attached")
    parser.add_argument("--maxdist", type=float, default=20,
                        help="Max distance (m) for nearest road search")
    parser.add_argument("--shpname", type=str, default=None,
                        help="Optional shapefile name inside ZIP")
    args = parser.parse_args()

    roads = load_roads(args.zip, args.shpname)
    obs = load_obs(args.obs)
    obs_linked = attach_nearest_road(obs, roads, args.maxdist)
    obs_linked.to_crs(4326).to_file(args.output, driver="GeoJSON")
    print(f"Saved {len(obs_linked)} points with road_id to {args.output}")


if __name__ == "__main__":
    main()
