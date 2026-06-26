import streamlit as st
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import Geocoder

# إعداد ; } وتصميم الواجهة العربية المخصصة
st.set_page_config(page_title="النظام الجيوفيزيائي", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    body { background-color: #ffffff; }
</style>
""", unsafe_allow_html=True)

st.title("🌍 نظام التحليل الهيدروجيولوجي الذكي")
st.write("---")

# القائمة الجانبية للتحكم بالمهام
st.sidebar.header("🛠️ أدوات التحكم والمهام")
task = st.sidebar.selectbox("اختر المهمة المطلوبة:", [
    "🛰️ الصور الجوية وإسقاط الإحداثيات", 
    "📊 التحليل الهيدروجيولوجي (المهام السابقة)"
])

if task == "🛰️ الصور الجوية وإسقاط الإحداثيات":
    st.subheader("🛰️ مستكشف الصور الجوية وتحديد مواقع الآبار والجسات")
    
    # 1. إضافة أدوات البحث اليدوي بالإحداثيات فوق الخريطة مباشرة
    st.write("🔍 **البحث المباشر عن موقع بالإحداثيات:**")
    search_col1, search_col2, search_col3 = st.columns([3, 3, 2])
    
    with search_col1:
        search_lat = st.number_input("أدخل خط العرض (Latitude):", value=15.3694, format="%.6f")
    with search_col2:
        search_lon = st.number_input("أدخل خط الطول (Longitude):", value=44.1910, format="%.6f")
    with search_col3:
        zoom_level = st.slider("مستوى التقريب (Zoom):", min_value=1, max_value=20, value=13)

    # خيار رفع ملف الإحداثيات من القائمة الجانبية
    uploaded_file = st.sidebar.file_uploader("ارفع ملف الإحداثيات (CSV/Excel)", type=["csv", "xlsx"])
    
    # استدعاء سيرفر خرائط جوجل للصور الجوية عالية الدقة (Google Satellite)
    google_satellite_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
    
    # بناء الخريطة بناءً على الإحداثيات المبحوث عنها أعلاه
    m = folium.Map(
        location=[search_lat, search_lon], 
        zoom_start=zoom_level, 
        tiles=google_satellite_url, 
        attr='Google Satellite'
    )
    
    # إضافة طبقة الهجين (أسماء الشوارع والمعالم فوق الصور الجوية)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google Hybrid',
        name='Google Hybrid (خرائط هجين)',
        overlay=False,
        control=True
    ).add_to(m)
    
    # إضافة زر البحث بالأسماء والمدن (عدسة مكبرة داخل الخريطة)
    Geocoder(placeholder="ابحث عن مدينة أو منطقة...").add_to(m)
    
    # إضافة علامة متحركة عند الإحداثيات المبحوث عنها يدوياً
    folium.Marker(
        location=[search_lat, search_lon],
        popup=f"الموقع الحالي المبحوث عنه:<br>Lat: {search_lat}<br>Lon: {search_lon}",
        icon=folium.Icon(color="blue", icon="search")
    ).add_to(m)
    
    folium.LayerControl().add_to(m)

    # معالجة ملف الإحداثيات المرفوع وإسقاط النقاط تلقائياً
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            st.success("✅ تم تحميل ملف الإحداثيات بنجاح جاري إسقاط النقاط...")
            
            lat_col = [col for col in df.columns if 'lat' in col.lower() or 'عرض' in col][0]
            lon_col = [col for col in df.columns if 'lon' in col.lower() or 'طول' in col][0]
            name_col = [col for col in df.columns if 'name' in col.lower() or 'اسم' in col or 'id' in col.lower()][0]
            
            for index, row in df.iterrows():
                folium.Marker(
                    location=[row[lat_col], row[lon_col]],
                    popup=f"📍 {row[name_col]}<br>Lat: {row[lat_col]}<br>Lon: {row[lon_col]}",
                    icon=folium.Icon(color="red", icon="info-sign")
                ).add_to(m)
                
            m.location = [df[lat_col].iloc[0], df[lon_col].iloc[0]]
            
        except Exception as e:
            st.error(f"⚠️ يرجى التأكد من مطابقة أسماء أعمدة الإحداثيات في الملف.")

    # عرض الخريطة التفاعلية في التطبيق
    st.write("👇 **الصور الجوية التفاعلية لجوجل مابس:**")
    map_data = st_folium(m, width=850, height=500, key="hydro_map")
    
    # التقاط وتفاعل الإحداثيات عند النقر على الخريطة
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lng = map_data["last_clicked"]["lng"]
        
        st.info(f"📍 **النقطة التي نقرت عليها بالإصبع حالياً:**")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("خط العرض المستخرج:", value=f"{clicked_lat}")
        with col2:
            st.text_input("خط الطول المستخرج:", value=f"{clicked_lng}")

elif task == "📊 التحليل الهيدروجيولوجي (المهام السابقة)":
    st.subheader("📊 أدوات التحليل ومعالجة البيانات الحقلية")
    st.write("هنا يتم تفعيل كافة الحسابات السابقة.")
    
    data_file = st.file_uploader("ارفع ملف البيانات الحقلية للتحليل", type=["csv", "txt"])
    if data_file is not None:
        st.success("تم استقبال ملف البيانات.")
