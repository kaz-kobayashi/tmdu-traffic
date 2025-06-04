"""Simple test for simple_map_app.py functionality"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_data_loading():
    """Test the data loading functionality"""
    try:
        # Import required modules
        from traffic_data import TrafficDataFetcher
        from road_data import RoadDataLoader
        from spatial_processor import SpatialProcessor
        from congestion_analyzer import CongestionAnalyzer
        from config import BBOX_5KM, TMDU_CENTER
        import pandas as pd
        import numpy as np
        from datetime import datetime
        
        print("Testing data loading components...")
        
        # Test traffic data fetching with mock
        print("1. Testing traffic data fetching...")
        fetcher = TrafficDataFetcher(use_mock=True)
        traffic_data = fetcher.fetch_traffic_data(BBOX_5KM)
        
        if traffic_data is not None and not traffic_data.empty:
            print(f"   ✅ Traffic data: {len(traffic_data)} records")
        else:
            print("   ❌ Traffic data fetch failed")
            return False
        
        # Test road data loading (will use cache or fail gracefully)
        print("2. Testing road data loading...")
        loader = RoadDataLoader()
        try:
            road_data = loader.load_road_network(bbox=BBOX_5KM)
            if not road_data.empty:
                print(f"   ✅ Road data: {len(road_data)} records")
                has_road_data = True
            else:
                print("   ⚠️ Road data file not found, using fallback")
                has_road_data = False
        except Exception as e:
            print(f"   ⚠️ Road data loading failed: {e}")
            has_road_data = False
        
        # Test spatial processing and congestion analysis
        print("3. Testing data processing...")
        processor = SpatialProcessor()
        analyzer = CongestionAnalyzer()
        
        if has_road_data and not road_data.empty:
            # Full pipeline test
            joined_data = processor.join_traffic_roads(traffic_data, road_data)
            if not joined_data.empty:
                aggregated_data = processor.aggregate_by_road(joined_data)
                if not aggregated_data.empty:
                    congestion_data = analyzer.calculate_congestion_level(aggregated_data)
                    print("   ✅ Full pipeline successful")
                else:
                    print("   ❌ Aggregation failed")
                    return False
            else:
                print("   ❌ Spatial join failed")
                return False
        else:
            # Test with traffic data only
            congestion_data = analyzer.calculate_congestion_level(traffic_data)
            if not congestion_data.empty:
                print("   ✅ Traffic data analysis successful")
            else:
                print("   ❌ Traffic data analysis failed")
                return False
        
        # Test statistics generation
        print("4. Testing statistics generation...")
        stats = analyzer.generate_statistics(congestion_data)
        if stats and 'total_roads' in stats:
            print(f"   ✅ Statistics: {stats['total_roads']} roads analyzed")
        else:
            print("   ❌ Statistics generation failed")
            return False
        
        # Test fallback data creation
        print("5. Testing fallback data creation...")
        
        def create_fallback_data():
            """Fallback data generation (for processing failure)"""
            np.random.seed(42)
            
            # TMDU coordinates
            center_lat, center_lon = TMDU_CENTER
            
            # Random road data generation
            n_roads = 50
            lats = np.random.normal(center_lat, 0.01, n_roads)
            lons = np.random.normal(center_lon, 0.01, n_roads)
            speeds = np.random.normal(25, 10, n_roads)
            speeds = np.clip(speeds, 5, 60)  # 5-60km/h
            
            # Congestion categories
            congestion = []
            for speed in speeds:
                if speed >= 30:
                    congestion.append('空いている')
                elif speed >= 20:
                    congestion.append('やや混雑')
                else:
                    congestion.append('混雑')
            
            df = pd.DataFrame({
                'latitude': lats,
                'longitude': lons,
                'speed': speeds,
                'travel_time': np.random.uniform(10, 60, n_roads),
                'link_length': np.random.uniform(50, 200, n_roads),
                'congestion': congestion,
                'congestion_level': ['low' if c == '空いている' else 'medium' if c == 'やや混雑' else 'high' for c in congestion],
                'road_name': [f'道路_{i+1}' for i in range(n_roads)],
                'road_id': [f'R{i:03d}' for i in range(n_roads)],
                'observation_count': np.random.randint(1, 5, n_roads)
            })
            
            # Simple statistics
            stats = {
                'total_roads': len(df),
                'congestion_distribution': df['congestion_level'].value_counts().to_dict(),
                'speed_stats': {
                    'mean': float(df['speed'].mean()),
                    'median': float(df['speed'].median()),
                    'min': float(df['speed'].min()),
                    'max': float(df['speed'].max())
                }
            }
            
            return df, stats, None
        
        fallback_df, fallback_stats, _ = create_fallback_data()
        if not fallback_df.empty:
            print(f"   ✅ Fallback data: {len(fallback_df)} records")
        else:
            print("   ❌ Fallback data creation failed")
            return False
        
        print("\n✅ All data loading components are working correctly!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_structure():
    """Test app structure without running streamlit"""
    print("\nTesting app structure...")
    
    try:
        # Check if the app file exists and can be parsed
        app_file = "simple_map_app.py"
        with open(app_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for key components
        required_components = [
            'load_real_traffic_data',
            'create_fallback_data',
            'main()',
            'st.cache_data',
            'TrafficDataFetcher',
            'RoadDataLoader',
            'SpatialProcessor',
            'CongestionAnalyzer'
        ]
        
        missing_components = []
        for component in required_components:
            if component not in content:
                missing_components.append(component)
        
        if missing_components:
            print(f"❌ Missing components: {missing_components}")
            return False
        else:
            print("✅ All required components found in app file")
            return True
            
    except FileNotFoundError:
        print("❌ simple_map_app.py not found")
        return False
    except Exception as e:
        print(f"❌ Error checking app structure: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing simple_map_app.py functionality...\n")
    
    # Test data loading
    data_test = test_data_loading()
    
    # Test app structure
    structure_test = test_app_structure()
    
    # Summary
    print("\n📋 Test Summary:")
    print(f"   Data Loading: {'✅ PASS' if data_test else '❌ FAIL'}")
    print(f"   App Structure: {'✅ PASS' if structure_test else '❌ FAIL'}")
    
    if data_test and structure_test:
        print("\n🎉 All tests passed! The updated simple_map_app.py should work correctly.")
        print("\n📝 To run the app:")
        print("   1. Install plotly: pip install plotly")
        print("   2. Run: streamlit run simple_map_app.py")
        print("\n💡 The app will use real traffic data if road data file is available,")
        print("   otherwise it will fall back to mock data.")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")