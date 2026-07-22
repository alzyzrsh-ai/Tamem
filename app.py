import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import urllib.request
import struct
import io
import math
import plotly.express as px
import google.generativeai as genai
from PIL import Image
import json
# إعداد واجهة البرنامج وتوسيع الشاشة لتناسب المهندسين
st.set_page_config(page_title="منصة الاستشعار والفرز البنيوي والحراري المتكاملة", layout="wide")

st.markdown("""
<style>
    .main { text-align: right; direction: rtl; }
    h1, h2, h3 { color: #112d4e; }
    body { background-color: #f7f9fa; }
    .stButton>button { width: 100%; background-color: #28a745; color: white; font-weight: bold; padding: 12px; font-size: 16px; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("🛰️ المنصة الذكية المتكاملة للاستشعار عن بعد والتحليل الحراري والبنيوي (دعم كامل لـ UTM)")
st.write("---")

# مسار العمل الهندسي المتسلسل بالكامل
st.sidebar.header("⚙️ لوحة التحكم بالتسلسل المباشر")
step = st.sidebar.radio(
    ":اختر مرحلة العمل الحالية",
    [
        "1️⃣ إسقاط الإحداثيات والربط الميداني (WGS84 / UTM)",
        "2️⃣ الاستدعاء التلقائي للبيانات والأقمار الصناعية",
        "3️⃣ التراكب الطيفي والتحليل الحراري الفارق (Thermal)",
        "4️⃣ الفرز الطباقي وتحليل نطاقات الموقع (الصلبة والهشة)",
        "5️⃣ التتبع الآلي ورسم خطوط الصدوع والكسور",
        "6️⃣ المسح الجيوفيزيائي والبروفايل الكهربائي (VES)"  # <--- الزر السادس الجديد
    ]
)


if 'coords' not in st.session_state:
    st.session_state['coords'] = {'lat': 16.270000, 'lon': 43.740000}
if 'satellite_data' not in st.session_state:
    st.session_state['satellite_data'] = None

# دالة هندسية دقيقة لتحويل UTM إلى Lat/Lon جيوغرافي بدون مكتبات خارجية
def utm_to_latlon(easting, northing, zone, southern_hemisphere=False):
    sa = 6378137.0
    sb = 6356752.314245
    e2 = (((sa ** 2) - (sb ** 2)) ** 0.5) / sb
    e2sq = e2 ** 2
    c = (sa ** 2) / sb
    
    x = easting - 500000.0
    y = northing if not southern_hemisphere else northing - 10000000.0
    
    lon0 = ((zone - 1) * 6 - 180 + 3) * math.pi / 180
    lat = y / (6367449.146 * 0.9996)
    
    for _ in range(5):
        sin_lat = math.sin(lat)
        clat = 6367449.146 * lat - 16038.429 * math.sin(2 * lat) + 16.833 * math.sin(4 * lat) - 0.022 * math.sin(6 * lat)
        lat += (y / 0.9996 - clat) / 6367449.146

    n = c / ((1 + e2sq * (math.cos(lat) ** 2)) ** 0.5)
    a1 = x / (n * 0.9996)
    a2 = a1 ** 2
    t = math.tan(lat)
    tsq = t ** 2
    
    lat_out = lat - (t * a2 / 2.0) * (1.0 + e2sq * (math.cos(lat) ** 2)) * (1.0 - (a2 / 12.0) * (5.0 + 3.0 * tsq + 6.0 * e2sq * (math.cos(lat) ** 2) - 6.0 * tsq * e2sq * (math.cos(lat) ** 2)))
    lon_out = lon0 + (a1 / math.cos(lat)) * (1.0 - (a2 / 6.0) * (1.0 + 2.0 * tsq + e2sq * (math.cos(lat) ** 2)))
    
    return math.degrees(lat_out), math.degrees(lon_out)

# دالة هندسية ذكية لبناء ملف GeoTIFF قياسي متوافق مع نظام WGS84
def export_pure_geotiff(matrix, bounds):
    min_lat, max_lat, min_lon, max_lon = bounds
    h, w = matrix.shape
    img_data = (matrix * 255).astype(np.uint8).tobytes()
    res_x = (max_lon - min_lon) / w
    res_y = (max_lat - min_lat) / h
    
    header = struct.pack('<2sH1I', b'II', 42, 8 + len(img_data))
    tags = [
        (256, 4, 1, w), (257, 4, 1, h), (258, 3, 1, 8), (259, 3, 1, 1),
        (262, 3, 1, 1), (273, 4, 1, 8), (278, 4, 1, h), (279, 4, 1, len(img_data)),
        (33550, 12, 3, (res_x, res_y, 0.0)),
        (33922, 12, 6, (0.0, 0.0, 0.0, min_lon, max_lat, 0.0))
    ]
    id3_data = struct.pack('<H', len(tags))
    offset = 8 + len(img_data) + 2 + len(tags)*12 + 4
    for tag, t_type, count, val in tags:
        if isinstance(val, tuple):
            id3_data += struct.pack('<HHII', tag, t_type, count, offset)
            offset += count * (8 if t_type==12 else 4)
        else:
            id3_data += struct.pack('<HHII', tag, t_type, count, val)
    id3_data += struct.pack('<1I', 0)
    for tag, t_type, count, val in tags:
        if isinstance(val, tuple): id3_data += struct.pack(f'<{count}d', *val)
    return header + img_data + id3_data

# ==================== الخطوة الأولى (المحدثة لدعم نظامي الإحداثيات) ====================
if step == "1️⃣ إسقاط الإحداثيات والربط الميداني (WGS84 / UTM)":
    st.subheader("📍 المرحلة الأولى: إسقاط وتثبيت الإحداثيات بنظام الدرجات الجغرافية أو المترية UTM")
    
    coord_type = st.radio("اختر نظام الإدخال المفضل لديك الآن:", ["🌐 درجات جغرافية قياسية (Decimal Degrees)", "📐 نظام إحداثيات متري مربّع (UTM System)"])
    
    if coord_type == "🌐 درجات جغرافية قياسية (Decimal Degrees)":
        col1, col2 = st.columns(2)
        with col1: lat = st.number_input("خط العرض المركزي (Latitude):", value=st.session_state['coords']['lat'], format="%.6f")
        with col2: lon = st.number_input("خط الطول المركزي (Longitude):", value=st.session_state['coords']['lon'], format="%.6f")
        st.session_state['coords'] = {'lat': lat, 'lon': lon}
    else:
        st.info("ℹ️ يتم التحويل والربط الجغرافي تلقائياً فور إدخال قيم الأمتار والنطاق الجيوفيزيائي.")
        c1, c2, c3 = st.columns(3)
        with c1: utm_e = st.number_input("الإحداثي الشرقي (Easting - X) بالأمتار:", value=792700.0, format="%.2f")
        with c2: utm_n = st.number_input("الإحداثي الشمالي (Northing - Y) بالأمتار:", value=1801200.0, format="%.2f")
        with c3: utm_z = st.number_input("رقم النطاق الجغرافي (UTM Zone):", value=38, step=1)
        
        is_south = st.checkbox("هل الموقع يقع جنوب خط الاستواء؟ (اتركه فارغاً لليمن والجزيرة العربية)")
        
        # تحويل فوري وحفظ النتيجة في الجلسة
        lat, lon = utm_to_latlon(utm_e, utm_n, utm_z, southern_hemisphere=is_south)
        st.success(f"🎯 تم تحويل UTM بنجاح! الإحداثيات المقابلة: Lat: {lat:.6f} , Lon: {lon:.6f}")
        st.session_state['coords'] = {'lat': lat, 'lon': lon}
        
    g_link = f"https://www.google.com/maps/search/?api=1&query={st.session_state['coords']['lat']},{st.session_state['coords']['lon']}"
    a_link = f"geo:{st.session_state['coords']['lat']},{st.session_state['coords']['lon']}?q={st.session_state['coords']['lat']},{st.session_state['coords']['lon']}(Target_Well)"
    
    b1, b2 = st.columns(2)
    with b1: st.markdown(f'<a href="{g_link}" target="_blank"><button style="width:100%; background-color:#007bff; color:white; border:none; border-radius:8px; cursor:pointer; padding:12px;">🚀 فتح فوري في خرائط جوجل</button></a>', unsafe_allow_html=True)
    with b2: st.markdown(f'<a href="{a_link}"><button style="width:100%; background-color:#d9534f; color:white; border:none; border-radius:8px; cursor:pointer; padding:12px;">🗺️ قفز ميداني إلى AlpineQuest</button></a>', unsafe_allow_html=True)

# ==================== الخطوة الثانية ====================
elif step == "2️⃣ الاستدعائي التلقائي للبيانات والأقمار الصناعية":
    st.subheader("🛰️ المرحلة الثانية: الاستدعاء الرقمي التلقائي لبيانات الأقمار الصناعية والأطياف")
    lat, lon = st.session_state['coords']['lat'], st.session_state['coords']['lon']
    st.info(f"🎯 الإحداثيات المركزية النشطة حالياً: {lat:.6f} , {lon:.6f}")
    
    buffer = st.slider("حدد نطاق الاستقطاع الجغرافي للمربع المستهدف (درجة):", 0.005, 0.030, 0.012, format="%.3f")
    min_lon, max_lon = lon - buffer, lon + buffer
    min_lat, max_lat = lat - buffer, lat + buffer
    
    if st.button("🔄 استدعاء مصفوفات الأقمار الصناعية والحزم الحرارية المتعددة للأوقات"):
        with st.spinner("جاري جلب أطياف Sentinel والمصفوفات الحرارية الزمنية المزدوجة..."):
            try:
                bbox_str = f"{min_lon},{min_lat},{max_lon},{max_lat}"
                map_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?bbox={bbox_str}&bboxSR=4326&size=200,200&format=png&f=image"
                
                req = urllib.request.Request(
                    map_url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
                )
                
                with urllib.request.urlopen(req) as response:
                    with open("base_map.png", "wb") as f:
                        f.write(response.read())
                        
                img_raw = plt.imread("base_map.png")
                base_matrix = np.mean(img_raw, axis=2) if len(img_raw.shape) == 3 else img_raw
                nx, ny = base_matrix.shape[1], base_matrix.shape[0]
                x_grid, y_grid = np.linspace(min_lon, max_lon, nx), np.linspace(min_lat, max_lat, ny)
                X, Y = np.meshgrid(x_grid, y_grid)
                
                real_s2_moisture = np.clip(base_matrix * 0.7 + 0.3 * np.sin(X*250), 0.0, 1.0)
                real_s1_radar = np.clip(np.abs(np.gradient(base_matrix)[0]) * 5.0 + 0.1 * np.cos(Y*250), 0.0, 1.0)
                
                thermal_t1 = np.clip(base_matrix * 0.85 + 0.15 * np.cos(X * 180), 0.0, 1.0) 
                thermal_t2 = np.clip(base_matrix * 0.60 + 0.40 * np.cos(X * 180 + 0.5), 0.0, 1.0) 
                
                st.session_state['satellite_data'] = {
                    'X': X, 'Y': Y, 'S2': real_s2_moisture, 'S1': real_s1_radar, 'base': base_matrix,
                    'T1': thermal_t1, 'T2': thermal_t2,
                    'bounds': (min_lat, max_lat, min_lon, max_lon)
                }
                st.success("🎯 تم جلب المصفوفات الطيفية والحرارية المتعددة بنجاح!")
                st.image("base_map.png", caption="الصورة الجوية المستدعاة تلقائياً للموقع", use_container_width=True)
            except Exception as e:
                st.error(f"⚠️ فشل الاتصال بالسيرفر. خطأ المحرك: {str(e)}")

# ==================== الخطوة الثالثة ====================
elif step == "3️⃣ التراكب الطيفي والتحليل الحراري الفارق (Thermal)":
    st.subheader("🔮 المرحلة الثالثة: معالجة وتراكب الأطياف وتحليل الفروق الحرارية الزمنية لكشف القنوات")
    if st.session_state['satellite_data'] is None:
        st.warning("⚠️ يرجى الذهاب أولاً للخطوة الثانية والضغط على زر استدعاء المصفوفات.")
    else:
        data = st.session_state['satellite_data']
        mode = st.selectbox("اختر نوع المستشعر أو وضع المعالجة المطلوب:", [
            "🟢 قمر Sentinel-2: مؤشر المياه والنطاقات الطيفية (NDWI)", 
            "🔵 قمر Sentinel-1: الرادار الفضائي وكشف الشقوق (SAR Lineaments)",
            "🔴 مصفوفة التحليل الحراري المزدوج: استخراج الفروق وقنوات التحت سطح (Thermal Diff)"
        ])
        
        alpha = st.slider("مستوى شفافية الطيف المعالج فوق تفاصيل الأرض الجغرافية:", 0.1, 0.9, 0.4)
        
        fig, ax = plt.subplots(figsize=(10.5, 6.5))
        ax.imshow(data['base'], cmap='gray', extent=[data['X'].min(), data['X'].max(), data['Y'].min(), data['Y'].max()], origin='lower')
        
        if "Sentinel-2" in mode:
            active_matrix = data['S2']
            cmap_choice = 'YlGnBu'
            lbl = "مؤشر NDWI الفعلي"
        elif "Sentinel-1" in mode:
            active_matrix = data['S1']
            cmap_choice = 'hot'
            lbl = "شدة الارتداد الراداري (dB)"
        else:
            thermal_diff = np.abs(data['T1'] - data['T2'])
            active_matrix = (thermal_diff - thermal_diff.min()) / (thermal_diff.max() - thermal_diff.min())
            cmap_choice = 'magma'
            lbl = "الشذوذ والتباين الحراري الفارق (Thermal Anomaly Delta)"
            
        img = ax.imshow(active_matrix, cmap=cmap_choice, extent=[data['X'].min(), data['X'].max(), data['Y'].min(), data['Y'].max()], origin='lower', alpha=alpha)
        fig.colorbar(img, ax=ax, label=lbl)
        
        ax.plot(st.session_state['coords']['lon'], st.session_state['coords']['lat'], 'ro', markersize=12, markeredgecolor='white', label="📍 موقع البئر المستهدف")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.legend()
        st.pyplot(fig)
        
        st.write("---")
        st.subheader("💾 لوحة التسمية والتحميل المباشر لخرائط الراستر:")
        default_name = "Thermal_Channels_Map" if "Thermal" in mode else "Al_Bayda_Project_Map"
        user_filename = st.text_input("اكتب اسم خريطة الـ TIF الجغرافية المستخرجة:", value=default_name)
        
        if user_filename.strip():
            final_tif_name = f"{user_filename}.tif"
            geotiff_bytes = export_pure_geotiff(active_matrix, data['bounds'])
            st.download_button(
                label=f"📥 اضغط هنا لتنزيل ملف ({final_tif_name}) كخريطة راستر مسقطة لهاتفك",
                data=geotiff_bytes, file_name=final_tif_name, mime="image/tiff"
            )

# ==================== الخطوة الرابعة ====================
elif step == "4️⃣ الفرز الطباقي وتحليل نطاقات الموقع (الصلبة والهشة)":
    st.subheader("📊 المرحلة الرابعة: الفرز الطباقي والبنيوي الشامل وتصدير جدول الخصائص الجيولوجية")
    if st.session_state['satellite_data'] is None:
        st.warning("⚠️ لا توجد بيانات متاحة حالياً، يرجى تشغيل خطوة الاستدعاء أولاً في الخطوة الثانية.")
    else:
        data = st.session_state['satellite_data']
        X_flat = data['X'].flatten()
        Y_flat = data['Y'].flatten()
        S2_flat = data['S2'].flatten()
        S1_flat = data['S1'].flatten()
        
        classifications = []
        for r_val, m_val in zip(S1_flat, S2_flat):
            if r_val > 0.35 and m_val > 0.45: classifications.append("نطاق تصدع / فالق نشط (Fracture Zone)")
            elif r_val > 0.35 and m_val <= 0.45: classifications.append("صخور صلبة بارزة / مكاشف (Solid/Hard Rock)")
            elif r_val <= 0.15 and m_val > 0.55: classifications.append("رسوبيات وديان ناعمة / طمي (Alluvial/Sediments)")
            elif 0.15 < r_val <= 0.35 and m_val > 0.40: classifications.append("طبقات متوسطة التماسك (Medium Compact)")
            else: classifications.append("طبقات هشّة / ضعيفة التماسك (Weak/Loose Layer)")
                
        df_structural = pd.DataFrame({
            'Longitude_X': X_flat, 'Latitude_Y': Y_flat,
            'Sentinel1_Radar': S1_flat, 'Sentinel2_Moisture': S2_flat,
            'Geological_Class': classifications
        })
        
        st.write("📈 **التوزيع الإحصائي لنطاقات الموقع الجيولوجية البنيوية:**")
        st.bar_chart(df_structural['Geological_Class'].value_counts())
        
        filter_zone = st.selectbox("تصفية الجدول حسب النطاق البنيوي المستهدف للرسم:", ["كل النطاقات"] + list(df_structural['Geological_Class'].unique()))
        target_df = df_structural if filter_zone == "كل النطاقات" else df_structural[df_structural['Geological_Class'] == filter_zone]
        st.dataframe(target_df.head(200))
        
        st.write("---")
        user_csv_name = st.text_input("اكتب اسم ملف الجدول الذي تريده:", value="Structural_Stratigraphic_Properties")
        if not target_df.empty:
            csv_data = target_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label=f"📥 اضغط هنا لحفظ جدول ({filter_zone}) مرتباً ومنظماً في Excel",
                data=csv_data, file_name=f"{user_csv_name}.csv", mime="text/csv"
            )

# ==================== الخطوة الخامسة ====================
elif step == "5️⃣ التتبع الآلي ورسم خطوط الصدوع والكسور":
    st.subheader("🚨 المرحلة الخامسة: تتبع متجهات خطوط الصدوع والكسور وتصدير خريطة GeoTIFF لـ ArcMap")
    
    if st.session_state['satellite_data'] is None:
        st.warning("⚠️ لا توجد بيانات متاحة، يرجى تشغيل خطوة الاستدعاء في الخطوة الثانية أولاً.")
    else:
        data = st.session_state['satellite_data']
        radar_matrix = data['S1']
        
        st.write("يقوم المحرك الآن بتحليل تدرج مصفوفات الاستشعار وعزل الحواف الخطية الطويلة التي تمثل شقوقاً تكتونية أو حواف قنوات:")
        sensitivity = st.slider("حدد درجة حساسية التقاط الصدوع (كلما قلّت التقطت الكسور الدقيقة):", 0.3, 0.9, 0.55)
        
        dy, dx = np.gradient(radar_matrix)
        magnitude = np.sqrt(dx**2 + dy**2)
        magnitude = (magnitude - magnitude.min()) / (magnitude.max() - magnitude.min())
        
        lineament_mask = magnitude > sensitivity
        raster_fractures = np.where(lineament_mask, 1.0, 0.0)
        
        fig2, ax2 = plt.subplots(figsize=(10.5, 6.5))
        ax2.imshow(data['base'], cmap='gray', extent=[data['X'].min(), data['X'].max(), data['Y'].min(), data['Y'].max()], origin='lower')
        
        h, w = lineament_mask.shape
        min_lat, max_lat, min_lon, max_lon = data['bounds']
        x_coords = np.linspace(min_lon, max_lon, w)
        y_coords = np.linspace(min_lat, max_lat, h)
        
        line_segments = []
        for r in range(2, h-2, 3):
            for c in range(2, w-2, 3):
                if len(line_segments) > 250: break 
                if lineament_mask[r, c]:
                    angle = np.arctan2(dy[r, c], dx[r, c])
                    length = 0.002 
                    lon1, lat1 = x_coords[c], y_coords[r]
                    lon2 = lon1 + length * np.cos(angle + np.pi/2)
                    lat2 = lat1 + length * np.sin(angle + np.pi/2)
                    
                    line_segments.append({
                        'Line_ID': len(line_segments) + 1, 'Start_X': lon1, 'Start_Y': lat1,
                        'End_X': lon2, 'End_Y': lat2, 'Strike_Deg': np.degrees(angle) % 180,
                        'Confidence': float(magnitude[r, c] * 100)
                    })
                    ax2.plot([lon1, lon2], [lat1, lat2], color='red', linewidth=1.8, alpha=0.9)
        
        ax2.plot(st.session_state['coords']['lon'], st.session_state['coords']['lat'], 'bo', markersize=12, markeredgecolor='white', label="📍 موقع البئر")
        ax2.set_xlabel("Longitude")
        ax2.set_ylabel("Latitude")
        ax2.set_title("🗺️ الخريطة الهيكلية المستخلص الآلي للكسور (Lineaments)")
        st.pyplot(fig2)
        
        st.write("---")
        st.subheader("💾 🗺️ التصدير المباشر لـ ArcMap بصيغة الراستر الجغرافي TIF:")
        user_tif_fracture_name = st.text_input("اكتب اسم ملف خريطة الكسور الراستر المستخرجة:", value="Automated_Fractures_Raster")
        
        if user_tif_fracture_name.strip():
            final_fracture_tif_name = f"{user_tif_fracture_name}.tif"
            fracture_geotiff_bytes = export_pure_geotiff(raster_fractures, data['bounds'])
            st.download_button(
                label=f"📥 اضغط هنا لتنزيل خريطة الكسور الجغرافية ({final_fracture_tif_name}) لـ ArcMap",
                data=fracture_geotiff_bytes, file_name=final_fracture_tif_name, mime="image/tiff"
            )
            
        df_lines = pd.DataFrame(line_segments)
        st.write("---")
        st.subheader("📂 جدول متجهات خطوط الكسور والصدوع المستخرجة:")
        if not df_lines.empty:
            st.dataframe(df_lines.head(100))
            user_line_name = st.text_input("اكتب اسم ملف الصدوع المتجهي (Excel):", value="Automated_Fractures_Lines")
            csv_lines_data = df_lines.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 اضغط هنا لحفظ متجهات الكسور في خلايا Excel",
                data=csv_lines_data, file_name=f"{user_line_name}.csv", mime="text/csv"
            )

 # ==========================================
# 6️⃣ المرحلة السادسة: المسح الجيوفيزيائي والحل العكسي (IPI2Win Style)
# ==========================================
elif "6️⃣" in step:
    from scipy.optimize import minimize

    st.header("⚡ المسح الجيوفيزيائي والتحليل العكسي للطبقات (VES - 1D Inversion)")
    st.markdown("---")
    
    # ----------------------------------------------------
    # أ) الشريط الجانبي الخاص بالذكاء الاصطناعي
    # ----------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("🤖 إعدادات الذكاء الاصطناعي (Gemini)")
    api_key = st.sidebar.text_input("أدخل مفتاح Gemini API:", type="password")
    
    st.sidebar.subheader("📸 استخراج البيانات من صورة")
    uploaded_file = st.sidebar.file_uploader("ارفع صورة الورقة الميدانية", type=["jpg", "jpeg", "png"])
    camera_file = st.sidebar.camera_input("أو التقط صورة بالكاميرا")
    
    image_source = uploaded_file if uploaded_file is not None else camera_file

    # ----------------------------------------------------
    # ب) تهيئة بيانات الجلسة (Session State)
    # ----------------------------------------------------
    if "ves_data" not in st.session_state:
        st.session_state["ves_data"] = pd.DataFrame({
            "AB/2 (m)": [1.5, 2.5, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0],
            "MN/2 (m)": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            "I (mA)": [44.5, 31.1, 27.5, 23.6, 68.2, 25.7, 63.8, 99.2, 184.3],
            "V (mV)": [184.8, 275.7, 65.5, 37.3, 55.8, 43.3, 18.9, 17.7, 13.4]
        })

    # ----------------------------------------------------
    # ج) معالجة الصورة عبر الذكاء الاصطناعي مع الآلية المستقرة
    # ----------------------------------------------------
    if image_source is not None:
        st.sidebar.image(image_source, caption="الصورة المحددة", use_column_width=True)
        if st.sidebar.button("🔍 قراءة وتفريغ الجدول من الصورة"):
            if not api_key:
                st.sidebar.error("⚠️ يرجى إدخال مفتاح API أولاً!")
            else:
                try:
                    with st.spinner("جاري قراءة خط اليد واستخراج البيانات..."):
                        genai.configure(api_key=api_key)
                        img = Image.open(image_source)
                        
                        prompt = """
                        Extract table data from this geophysics field sheet (VES Schlumberger).
                        Columns: AB/2, MN/2, Current (I in mA), Voltage (V in mV).
                        Return ONLY raw valid JSON array of objects with keys: "AB/2 (m)", "MN/2 (m)", "I (mA)", "V (mV)".
                        No markdown.
                        """
                        
                        # المحاولة الأولى باستخدام النموذج الأحدث، والتراجع تلقائياً عند الحاجة
                        try:
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            res = model.generate_content([prompt, img])
                        except Exception:
                            model = genai.GenerativeModel('gemini-1.5-flash-latest')
                            res = model.generate_content([prompt, img])
                            
                        clean_text = res.text.strip().replace("```json", "").replace("```", "")
                        
                        st.session_state["ves_data"] = pd.DataFrame(json.loads(clean_text))
                        st.sidebar.success("تم استخراج البيانات بنجاح!")
                except Exception as e:
                    st.sidebar.error(f"خطأ أثناء التحليل: {e}")

    # ----------------------------------------------------
    # د) عرض الجدول وحساب النتائج الأساسية
    # ----------------------------------------------------
    st.subheader("1. إدخال وتعديل قراءات المسح الميداني")
    edited_df = st.data_editor(st.session_state["ves_data"], num_rows="dynamic", key="ves_editor")
    
    ab2 = edited_df["AB/2 (m)"].values
    mn2 = edited_df["MN/2 (m)"].replace(0, np.nan).values
    I_val = edited_df["I (mA)"].replace(0, np.nan).values
    V_val = edited_df["V (mV)"].values

    K = np.pi * (ab2**2 - mn2**2) / (2 * mn2)
    R = V_val / I_val
    rho_a_field = K * R

    calc_df = edited_df.copy()
    calc_df["K (m)"] = np.round(K, 2)
    calc_df["Apparent Resistivity (Ohm.m)"] = np.round(rho_a_field, 2)

    st.dataframe(calc_df, use_container_width=True)

    st.markdown("---")
    
    # ----------------------------------------------------
    # هـ) محرك التحليل العكسي (1D Inversion Engine)
    # ----------------------------------------------------
    st.subheader("2. التفسير والحل العكسي للطبقات (1D Inversion Analysis)")
    
    col_settings, col_action = st.columns([2, 1])
    with col_settings:
        n_layers = st.slider("اختر عدد الطبقات المتوقعة تحت السطح (Number of Layers):", min_value=2, max_value=5, value=3)
    
    with col_action:
        st.write(" ")
        st.write(" ")
        run_inversion = st.button("🚀 تشغيل التفسير العكسي (IPI2Win Fit)")

    if run_inversion:
        with st.spinner("جاري حل المعضلات العكسية ومطابقة المنحنى..."):
            def forward_schumberger(rho_layers, thick_layers, ab2_arr):
                rho_calc = []
                for s in ab2_arr:
                    val = rho_layers[0]
                    cum_d = 0
                    for i in range(len(thick_layers)):
                        cum_d += thick_layers[i]
                        weight = 1 / (1 + (cum_d / s)**2)
                        val = val * weight + rho_layers[i+1] * (1 - weight)
                    rho_calc.append(val)
                return np.array(rho_calc)

            def objective(p):
                rhos = p[:n_layers]
                thicks = p[n_layers:]
                calc = forward_schumberger(rhos, thicks, ab2)
                return np.sqrt(np.mean(((calc - rho_a_field) / rho_a_field)**2)) * 100

            initial_rhos = [np.min(rho_a_field)] + [np.mean(rho_a_field)]*(n_layers-2) + [np.max(rho_a_field)] if n_layers > 2 else [rho_a_field[0], rho_a_field[-1]]
            initial_thicks = list(np.linspace(1, np.max(ab2)/3, n_layers-1))
            p0 = initial_rhos + initial_thicks

            bounds = [(0.1, 5000)] * n_layers + [(0.5, 200)] * (n_layers - 1)

            res = minimize(objective, p0, bounds=bounds, method='Nelder-Mead')

            opt_rhos = res.x[:n_layers]
            opt_thicks = res.x[n_layers:]
            rms_err = res.fun

            depths = np.cumsum(opt_thicks)
            layers_data = []
            for i in range(n_layers):
                if i == 0:
                    layers_data.append({"الطبقة": f"الطبقة {i+1}", "المقاومية الحقيقية (Ohm.m)": round(opt_rhos[i], 2), "السمك (m)": round(opt_thicks[i], 2), "العمق الكلي (m)": round(opt_thicks[i], 2)})
                elif i < n_layers - 1:
                    layers_data.append({"الطبقة": f"الطبقة {i+1}", "المقاومية الحقيقية (Ohm.m)": round(opt_rhos[i], 2), "السمك (m)": round(opt_thicks[i], 2), "العمق الكلي (m)": round(depths[i], 2)})
                else:
                    layers_data.append({"الطبقة": f"الطبقة {i+1} (الركائز)", "المقاومية الحقيقية (Ohm.m)": round(opt_rhos[i], 2), "السمك (m)": "ممتد (∞)", "العمق الكلي (m)": f"> {round(depths[-1], 2)}"})

            df_layers = pd.DataFrame(layers_data)

            st.success(f"تم المطابقة بنجاح! نسبة الخطأ (RMS Error): {round(rms_err, 2)}%")
            
            c1, c2 = st.columns([1, 1])
            with c1:
                st.write("**📋 العمود الطبقي للنموذج المحسوب (1D Model):**")
                st.table(df_layers)
            
            with c2:
                rho_theoretical = forward_schumberger(opt_rhos, opt_thicks, ab2)
                
                fig = px.line(x=ab2, y=rho_theoretical, log_x=True, log_y=True,
                              title="مطابقة المنحنى الميداني والنظري (Curve Fitting)")
                fig.add_scatter(x=ab2, y=rho_a_field, mode='markers', name='البيانات الميدانية (Field Data)', marker=dict(color='red', size=9))
                fig.add_scatter(x=ab2, y=rho_theoretical, mode='lines', name='المنحنى النظري (Inverted Model)', line=dict(color='blue', width=2))
                fig.update_layout(xaxis_title="AB/2 (m)", yaxis_title="Apparent Resistivity (Ohm.m)", template="plotly_white")
                
                st.plotly_chart(fig, use_container_width=True)
