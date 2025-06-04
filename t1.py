import requests, json
import pandas as pd

bbox = (139.749, 35.663, 139.785, 35.699)  # minLon,minLat,maxLon,maxLat
time_code = 202506040900  # YYYYMMDDhhmm, 5分単位
url = (
    "https://api.jartic-open-traffic.org/geoserver"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=t_travospublic_measure_5m"
    "&srsName=EPSG:4326&outputFormat=application/json"
    "&exceptions=application/json"
    f"&cql_filter=道路種別=3 AND 時間コード={time_code} "
    f"AND BBOX(\"ジオメトリ\",{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},'EPSG:4326')"
)
r = requests.get(url)
features = r.json()["features"]
df = pd.json_normalize([f["properties"] for f in features])
print(df.head())