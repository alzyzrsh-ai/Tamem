import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# إعداد الصفحة وتصميم الواجهة العربية
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
    
    # خيار رفع ملف الإحداثيات من القائمة الجانبية
    uploaded_file = st.sidebar.file_uploader("ارفع ملف الإحداثيات (CSV/Excel)", type=["csv", "xlsx"])
    
    st.write("🔍 **البحث والتحول المباشر إلى الموقع:**")
    col1, col2, col3 = st.columns([3, 3, 2])
    
    with col1:
        search_lat = col1.number_input("أدخل خط العرض (Latitude):", value=16.270000, format="%.6f")
    with search_col2 if 'search_col2' in locals() else col2:
        search_lon = col2.number_input("أدخل خط الطول (Longitude):", value=43.740000, format="%.6f")
    with col3:
        zoom_level = col3.slider("مستوى التقريب (Zoom):", min_value=1, max_value=20, value=12)

    # تجهيز مصفوفة البيانات الأساسية للنقطة المبحوث عنها لإنشاء أيقونة البحث
    data = {'Lat': [search_lat], 'Lon': [search_lon], 'الموقع': ['📍 الهدف المراد فحص صورته الجوية']}
    df_search = pd.DataFrame(data)

    # معالجة ملف الإحداثيات المرفوع إن وجد لدمجه على الصورة الجوية
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_user = pd.read_csv(uploaded_file)
            else:
                df_user = pd.read_excel(uploaded_file)
            st.success("✅ تم دمج نقاط ملف الإحداثيات الحقلية بنجاح!")
            
            # توحيد أسماء الأعمدة لتلائم الخريطة
            lat_col = [col for col in df_user.columns if 'lat' in col.lower() or 'عرض' in col][0]
            lon_col = [col for col in df_user.columns if 'lon' in col.lower() or 'طول' in col][0]
            name_col = [col for col in df_user.columns if 'name' in col.lower() or 'اسم' in col or 'id' in col.lower()][0]
            
            df_user = df_user.rename(columns={lat_col: 'Lat', lon_col: 'Lon', name_col: 'الموقع'})
            df_search = pd.concat([df_search, df_user], ignore_index=True)
            
            # الانتقال التلقائي لأول نقطة في ملف المستخدم
            search_lat = df_user['Lat'].iloc[0]
            search_lon = df_user['Lon'].iloc[0]
        except Exception as e:
            st.error("⚠️ يرجى التأكد من مطابقة أسماء أعمدة الإحداثيات.")

    # 🗺️ بناء خريطة الصور الجوية الفضائية التفاعلية بالكامل باستخدام Plotly Mapbox المجاني
    fig = px.scatter_mapbox(
        df_search, 
        lat="Lat", 
        lon="Lon", 
        hover_name="الموقع",
        color_discrete_sequence=["red"], 
        zoom=zoom_level, 
        height=550
    )
    
    # اختيار وضع خريطة القمر الصناعي المفتوحة بدون مفتاح خاص
    fig.update_layout(
        mapbox_style="white-bg",
        mapbox_layers=[{
            "below": 'traces',
            "sourcetype": "raster",
            "source": [
                "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}"
            ]
        }],
        margin={"r":0,"t":0,"l":0,"b":0},
        mapbox_center={"lat": search_lat, "lon": search_lon}
    )
    
    st.write("👇 **الصور الجوية الفضائية المحدثة (تتحرك وتنتقل للهدف فوراً):**")
    st.plotly_chart(fig, use_container_width=True)

elif task == "📊 التحليل الهيدروجيولوجي (المهام السابقة)":
    st.subheader("📊 أدوات التحليل ومعالجة البيانات الحقلية")
    st.write("هنا يتم تفعيل كافة الحسابات السابقة للـ Numpy والمصفوفات والرسومات البيانية.")
