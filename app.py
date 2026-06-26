import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import Geocoder

# إعداد الصفحة لتناسب الهواتف
st.set_page_config(page_title="النظام الجيوفيزيائي", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    body { background-color: #ffffff; }
    /* لضمان ظهور الخريطة بشكل صحيح على المتصفحات المحمولة */
    iframe { width: 100% !important; height: 500px !important; }
</style>
""", unsafe_allow_html=True)

st.title("🌍 نظام التحليل الهيدروجيولوجي - خرائط جوجل")
st.write("---")

# القائمة الجانبية
st.sidebar.header("🛠️ أدوات التحكم")
task = st.sidebar.selectbox("اختر المهمة المطلوبة:", ["🛰️ صور جوجل الجوية والإحداثيات", "📊 المهام السابقة"])

if task == "🛰️ صور جوجل الجوية والإحداثيات":
    st.subheader("🛰️ صور جوجل مابس الفضائية عالية الدقة")
    
    # مدخلات يدوية للتحكم بالخريطة من الأعلى
    col1, col2, col3 = st.columns([3, 3, 2])
    with col1:
        search_lat = st.number_input("خط العرض (Latitude):", value=16.270000, format="%.6f")
    with col2:
        search_lon = st.number_input("خط الطول (Longitude):", value=43.740000, format="%.6f")
    with col3:
        zoom_level = st.slider("مستوى التقريب (Zoom):", min_value=1, max_value=20, value=13)

    # رابط خادم خرائط جوجل الفضائية الرسمي (المباشر والأوضح)
    google_satellite_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
    
    # بناء الخريطة
    m = folium.Map(
        location=[search_lat, search_lon], 
        zoom_start=zoom_level, 
        tiles=google_satellite_url, 
        attr='Google'
    )
    
    # إضافة خيار الهجين (الأسماء فوق صور جوجل) عند تفعيلها من الطبقات
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google Hybrid',
        name='إظهار أسماء المناطق والشوارع',
        overlay=True,
        control=True
    ).add_to(m)

    # 🔍 إضافة أيقونة "العدسة المكبرة" للبحث بالأسماء أو الإحداثيات داخل الخريطة
    Geocoder(placeholder="ابحث عن منطقة أو بئر...").add_to(m)
    
    # وضع علامة تثبيت عند الإحداثي المكتوب
    folium.Marker(
        location=[search_lat, search_lon],
        popup=f"الموقع الحالي:<br>{search_lat}, {search_lon}",
        icon=folium.Icon(color="red", icon="screenshot", prefix="glyphicon")
    ).add_to(m)
    
    folium.LayerControl().add_to(m)

    # عرض الخريطة بسيرفر تفاعلي آمن ومستقر للهواتف
    st.write("👇 **خريطة جوجل مابس (يمكنك السحب والبحث والتقريب):**")
    map_data = st_folium(m, width="100%", height=500, key="google_map_system")
    
    # التقاط الإحداثيات عند النقر بالإصبع
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lng = map_data["last_clicked"]["lng"]
        st.info(f"📍 **الإحداثيات التي نقرت عليها بالإصبع:** {clicked_lat} , {clicked_lng}")

elif task == "📊 المهام السابقة":
    st.subheader("📊 أدوات التحليل السابقة")
