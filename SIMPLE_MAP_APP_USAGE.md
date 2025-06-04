# Simple Map App - Real Traffic Data Version

This document explains how to use the updated `simple_map_app.py` which now integrates real traffic data instead of just mock data.

## Overview

The updated app now:
1. **Imports and uses existing modules** (traffic_data.py, road_data.py, spatial_processor.py, congestion_analyzer.py)
2. **Loads real road data** from the KSJ shapefile (N01-07L-13-01.0a_GML.zip)
3. **Fetches real traffic data** from JARTIC API (with mock fallback)
4. **Processes and joins the data** using existing spatial processing modules
5. **Displays real data** on Plotly map instead of mock data
6. **Keeps the same UI structure** but with enhanced real data functionality

## Prerequisites

### Required Python Libraries
Install the required libraries:
```bash
pip install plotly>=5.15.0
```

All other required libraries should already be available:
- streamlit
- pandas
- numpy
- geopandas
- requests
- shapely

### Required Data Files
Make sure you have the road data file in the project directory:
- `N01-07L-13-01.0a_GML.zip` (KSJ road centerline data)

## Usage

### Running the Application
```bash
streamlit run simple_map_app.py
```

### Features

#### 1. Real Data Integration
- **Traffic Data**: Uses JARTIC API with mock fallback
- **Road Data**: Uses Japanese national geospatial data (KSJ)
- **Spatial Integration**: Joins traffic observations to road segments
- **Congestion Analysis**: Calculates real congestion levels based on speed thresholds

#### 2. Data Processing Pipeline
The app follows this processing pipeline:
1. Load traffic data from JARTIC API (or mock if API fails)
2. Load road network data from KSJ shapefile
3. Spatially join traffic observations to nearest roads
4. Aggregate multiple observations per road segment
5. Calculate congestion levels based on average speeds
6. Display results on interactive map

#### 3. UI Components

**Main Map**:
- Interactive Plotly mapbox with real traffic data
- Color-coded congestion levels (green/yellow/red/gray)
- Hover information showing speed, travel time, road details
- Tokyo Medical and Dental University marker

**Sidebar Controls**:
- Data refresh button (clears 5-minute cache)
- Auto-update toggle
- Congestion level legend
- Data source information
- File status indicators

**Statistics Panel**:
- Total road count and average speed
- Congestion distribution (pie chart)
- Speed distribution (histogram)
- Observation quality metrics
- Detailed data table (expandable)

#### 4. Data Caching
- 5-minute cache for processed data (@st.cache_data)
- Manual refresh capability
- Automatic fallback to mock data if processing fails

#### 5. Error Handling
- Graceful fallback to mock data if:
  - Road data file is missing
  - API connection fails
  - Spatial processing errors occur
- User-friendly error messages
- Processing status indicators

## Configuration

The app uses settings from `config.py`:
- **BBOX_5KM**: Target area around Tokyo Medical and Dental University
- **TMDU_CENTER**: University coordinates for map centering
- **CONGESTION_THRESHOLDS**: Speed thresholds for congestion classification
- **ROAD_DATA_ZIP**: Path to road data file

## Data Quality Indicators

The app provides several data quality indicators:

**Data Source Status**:
- ✅ Real data: Using integrated traffic and road data
- ⚠️ Mock data: Using fallback due to missing files or API issues
- ❌ Error: Processing failed

**File Status**:
- ✅ Road data file: Available and accessible
- ❌ Road data file: Missing or inaccessible

**Processing Metrics**:
- Total observation points
- Road coverage rate
- Average observations per road
- Spatial matching distance statistics

## Troubleshooting

### Common Issues

1. **"plotly not available" error**
   ```bash
   pip install plotly
   ```

2. **"Road data file not found" error**
   - Ensure `N01-07L-13-01.0a_GML.zip` is in the project directory
   - Check file permissions

3. **Empty map display**
   - Check data processing logs in terminal
   - Try manual refresh with sidebar button
   - Verify internet connection for API access

4. **Slow loading**
   - Data processing can take 10-30 seconds on first load
   - Subsequent loads use cache (5-minute TTL)

### Debug Mode
Set environment variable for verbose logging:
```bash
export LOG_LEVEL=DEBUG
streamlit run simple_map_app.py
```

## Development Notes

### Module Dependencies
The app depends on these custom modules:
- `traffic_data.py`: JARTIC API client with mock fallback
- `road_data.py`: KSJ road data loader with CRS conversion
- `spatial_processor.py`: Spatial joining and aggregation
- `congestion_analyzer.py`: Congestion level calculation
- `config.py`: Application configuration

### Data Flow
```
JARTIC API → TrafficDataFetcher → GeoDataFrame
KSJ Shapefile → RoadDataLoader → GeoDataFrame
    ↓
SpatialProcessor.join_traffic_roads() → Joined GeoDataFrame
    ↓
SpatialProcessor.aggregate_by_road() → Aggregated GeoDataFrame
    ↓
CongestionAnalyzer.calculate_congestion_level() → Final GeoDataFrame
    ↓
Plotly MapBox Visualization
```

### Performance Optimization
- Data caching reduces repeated processing
- Spatial indexing improves join performance
- Coordinate system optimization for distance calculations
- Efficient memory usage with pandas/geopandas operations

## Testing

Run the test script to verify functionality:
```bash
python test_simple_map_app.py
```

This will test:
- Module imports
- Data loading pipeline
- Fallback data generation
- App structure validation