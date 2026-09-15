from fastapi import FastAPI, HTTPException
import requests
from datetime import datetime

app = FastAPI(title="Geophysical Real-Time Data API")

# 1. جلب عناصر المجال المغناطيسي المرجعي (WMM) من NOAA
@app.get("/api/v1/geomagnetic")
def get_geomagnetic_data(latitude: float, longitude: float, altitude_km: float = 0.0):
    """
    تسترجع قيم المجال المغناطيسي الواقعية (Declination, Inclination, Total Intensity)
    بناءً على نموذج WMM لـ NOAA عند إحداثيات محددة.
    """
    current_year = datetime.now().year
    url = "https://www.ngdc.noaa.gov/geomag-web/calculators/calculateIgrfwmm"
    
    params = {
        'lat1': latitude,
        'lon1': longitude,
        'elevation': altitude_km,
        'elevationUnits': 'K',
        'startYear': current_year,
        'model': 'WMM',
        'resultFormat': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        result = data['result'][0]
        return {
            "latitude": latitude,
            "longitude": longitude,
            "declination_deg": result.get("declination"),
            "inclination_deg": result.get("inclination"),
            "total_intensity_nT": result.get("totalintensity"),
            "horizontal_intensity_nT": result.get("horizintensity"),
            "north_component_nT": result.get("xcomponent"),
            "east_component_nT": result.get("ycomponent"),
            "vertical_component_nT": result.get("zcomponent"),
            "model_used": "WMM"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الاتصال بخدمة NOAA: {str(e)}")

# 2. الاستعلام عن وجود مسوحات كهرومغناطيسية/جاذبية حقلية قريبة عبر USGS 
@app.get("/api/v1/airborne-surveys")
def check_usgs_surveys(min_lat: float, max_lat: float, min_lon: float, max_lon: float):
    """
    البحث عن مسوحات كهرومغناطيسية أو مغناطيسية جوية حقلية متاحة في قاعدة بيانات USGS
    """
    usgs_endpoint = "https://mrdata.usgs.gov/airborne/geo-api.php"
    
    params = {
        'bbox': f"{min_lon},{min_lat},{max_lon},{max_lat}",
        'format': 'json'
    }
    
    try:
        response = requests.get(usgs_endpoint, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"status": "No specific survey data found in bounding box"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب بيانات المسح الجوي: {str(e)}")
