import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# إعداد الصفحة للعمل على الهواتف بشكل كامل
st.set_page_config(page_title="النظام الجيوفيزيائي", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    body { background-color: #ffffff; }
    /* إجبار المتصفح على إظهار الخريطة دون اختفاء */
    .stFolium iframe { width: 100% !important; height: 450px !important; }
</style>
""", unsafe_allow_html=True)

st.title("🌍 نظام التحليل الهيدروجيولوجي - خرائط جوجل")
st.write("---")

# القائمة الجانبية للتحكم
st.sidebar.header("🛠️ أدوات التحكم")
task = st.sidebar.selectbox("اختر المهمة المطلوبة:", ["🛰️ صور جوجل الجوية والإحداثيات", "📊 المهام السابقة"])

if task == "🛰️ صور جوجل الجوية والإحداثيات":
    st.subheader("🛰️ مستكشف صور جوجل مابس الفضائية")
    
    # خانات إدخال الإحداثيات للبحث المباشر والقفز للموقع
    st.write("🔍 **اكتب الإحداثيات هنا للانتقال والبحث الفوري:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        search_lat = st.number_input("خط العرض (Latitude):", value=16.270000, format="%.6f")
    with col2:
        search_lon = st.number_input("خط الطول (Longitude):", value=43.740000, format="%.6f")
    with col3:
        zoom_level = st.slider("مستوى التقريب (Zoom):", min_value=1, max_value=20, value=13)

    # خيار رفع ملف الإحداثيات
    uploaded_file = st.sidebar.file_uploader("ارفع ملف الإحداثيات (CSV/Excel)", type=["csv", "xlsx"])

    # 📌 السيرفر البديل والأسرع لصور جوجل الجوية لضمان عدم الحجب
    google_satellite_url = 'https://mt0.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
    
    # بناء الخريطة وتثبيتها على الإحداثيات المكتوبة
    m = folium.Map(
        location=[search_lat, search_lon], 
        zoom_start=zoom_level, 
        tiles=google_satellite_url, 
        attr='Google Maps'
    )
    
    # وضع علامة تثبيت حمراء عند الإحداثي المبحوث عنه
    folium.Marker(
        location=[search_lat, search_lon],
        popup=f"الموقع المستهدف:<br>{search_lat}, {search_lon}",
        icon=folium.Icon(color="red", icon="flag")
    ).add_to(m)

    # معالجة ملف الإحداثيات المرفوع إن وجد
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            lat_col = [col for col in df.columns if 'lat' in col.lower() or 'عرض' in col][0]
            lon_col = [col for col in df.columns if 'lon' in col.lower() or 'طول' in col][0]
            name_col = [col for col in df.columns if 'name' in col.lower() or 'اسم' in col or 'id' in col.lower()][0]
            
            for index, row in df.iterrows():
                folium.Marker(
                    location=[row[lat_col], row[lon_col]],
                    popup=f"📍 {row[name_col]}",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)
            st.success("✅ تم إسقاط نقاط الملف بنجاح!")
        except Exception as e:
            st.error("⚠️ تأكد من أسماء الأعمدة.")

    # عرض خريطة جوجل التفاعلية بأمان تام
    st.write("👇 **خريطة جوجل الفضائية التفاعلية (تتحرك تلقائياً للأرقام المكتوبة أعلاه):**")
    map_data = st_folium(m, width="100%", height=450, key="hydro_google_final_v1")
    
    # التقاط الإحداثيات عند النقر بالإصبع
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lng = map_data["last_clicked"]["lng"]
        st.info(f"📍 **الإحداثيات الناتجة عن نقرتك الحالية:** {clicked_lat} , {clicked_lng}")

elif task == "📊 المهام السابقة":
    st.subheader("📊 أدوات التحليل ومعالجة البيانات الحقلية")
