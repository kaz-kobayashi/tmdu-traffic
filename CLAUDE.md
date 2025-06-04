# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains a Streamlit web application for visualizing real-time traffic congestion around Tokyo Medical and Dental University (TMDU). It combines Japanese national spatial data (KSJ/国土数値情報) with JARTIC traffic observation data to provide interactive traffic maps.

## Key Components

### Main Application
- `app.py`: Streamlit web application with interactive traffic visualization
- `config.py`: Application configuration and constants (TMDU coordinates, API settings, visualization parameters)

### Core Modules  
- `traffic_data.py`: JARTIC API client with mock data support
- `road_data.py`: KSJ road centerline data loader
- `spatial_processor.py`: Spatial data integration and road-traffic matching
- `congestion_analyzer.py`: Traffic congestion level calculation
- `map_visualizer.py`: Folium-based interactive map generation

### Utilities
- `t1.py`: Simple traffic API client for testing
- `tokyo_road_loader/tokyo_road_loader.py`: KSJ road data processor with spatial joining

### Data Sources
- KSJ N01-07L road centerline data (Japanese national geospatial format)
- JARTIC traffic observation API (real-time traffic measurements)
- Shapefiles in JGD2000 coordinate system requiring conversion to WGS84

## Development Commands

### Environment Setup
```bash
# Main application dependencies
pip install -r app_requirements.txt

# Tokyo road loader dependencies  
cd tokyo_road_loader
pip install -r requirements.txt
```

### Running the Application
```bash
# Launch Streamlit app
streamlit run app.py
```

### Testing Individual Modules
```bash
# Test traffic data fetching
python traffic_data.py

# Test road data loading
python road_data.py

# Test map visualization  
python map_visualizer.py

# Test simple API client
python t1.py
```

### Utility Scripts
```bash
# Process KSJ road data
python tokyo_road_loader/tokyo_road_loader.py --zip N01-07L-13-01.0a_GML.zip --obs obs_points.csv --output linked_points.geojson
```

## Architecture Notes

### Application Structure
The Streamlit app follows a modular architecture:
1. **Data Layer**: `traffic_data.py` and `road_data.py` handle API calls and file loading
2. **Processing Layer**: `spatial_processor.py` performs geospatial joins and `congestion_analyzer.py` calculates traffic levels  
3. **Visualization Layer**: `map_visualizer.py` creates Folium maps for Streamlit display
4. **Configuration**: `config.py` centralizes all settings (coordinates, thresholds, colors)

### Data Processing Pipeline
1. Load KSJ road data from ZIP archives (`N01-07L-13-01.0a_GML.zip` required)
2. Convert coordinate systems (JGD2000 → WGS84)
3. Fetch JARTIC traffic data for TMDU 5km bbox (or use mock data)
4. Spatially join traffic points to nearest roads (50m max distance)
5. Calculate congestion levels based on speed thresholds
6. Render interactive Folium map in Streamlit

### Coordinate System Handling
- Input data: JGD2000 (EPSG:4612) from KSJ
- Working CRS: WGS84 (EPSG:4326) for API compatibility
- Distance calculations: Web Mercator (EPSG:3857) for metric precision

### Key Configuration
- Target area: 5km around TMDU (35.7056°N, 139.7644°E)
- Mock data mode: `USE_MOCK_DATA = True` in `traffic_data.py`
- Congestion thresholds: 30km/h (green), 20km/h (yellow), <20km/h (red)
- Update interval: 5 minutes (300 seconds)