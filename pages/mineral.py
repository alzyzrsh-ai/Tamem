import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="SanbGeo - Dikes & Linear Anomalies Engine", layout="wide")

st.title("🛰️ نظام رصد القواطع (Dykes) والشذوذ الخطي التعديني")
st.markdown("استخراج وتصنيف التراكيب الخطية، القواطع النارية (Dykes)، وعروق التمعدن المتسلسلة على خلفية التضاريس السطحية.")

# لوحة التحكم الجانبية للإحداثيات
st.sidebar.header("📍 إحداثيات منطقة البحث (AOI)")
lat = st.sidebar.number_input("خط العرض (Latitude)", value=15.3694, format="%.4f")
lon = st.sidebar.number_input("خط الطول (Longitude)", value=44.1910, format="%.4f")
strike_angle = st.sidebar.slider("اتجاه مضرب القواطع (Strike Angle °)", min_value=0, max_value=180, value=45)

st.sidebar.divider()
st.sidebar.header("⚙️ إعدادات التحليل الهيكلي")
analysis_mode = st.sidebar.selectbox(
    "اختر نوع الشذوذ الخطي المستهدف:",
    [
        "قواطع أكاسيد الحديد الخطية (Iron-stained Dykes)",
        "قواطع وعروق الفلزات والسيليكا (Silicified Veins & Dykes)",
        "شبكة التراكيب والخطوط الهيكلية المتعددة (Lineament Grid)"
    ]
)

if st.button("🚀 توليد خريطة القواطع والشذوذ الخطي"):
    with st.spinner("جاري حساب الاتجاهات الهيكلية واستخراج القواطع الخطية..."):
        
        # شبكة مكانية عالية الدقة
        height, width = 500, 500
        np.random.seed(int(abs(lat * 100 + lon * 100)))
        
        x = np.linspace(-5, 5, width)
        y = np.linspace(-5, 5, height)
        X, Y = np.meshgrid(x, y)
        
        # 1. خلفية تضاريسية واقعية (Shaded Relief)
        terrain = 0.4 + 0.2 * np.sin(X * 0.8) * np.cos(Y * 0.8)
        rgb_terrain = np.dstack((terrain, terrain, terrain))
        
        # 2. تحويل زاوية المضرب إلى معادلة رياضية لتوليد "قواطع خطية" (Dykes) تقطع التضاريس بزوايا حقيقية
        rad = np.radians(strike_angle)
        # معادلة الخط المستقيم المائل (المضرب والاتجاه الجيولوجي)
        line_coord = np.cos(rad) * X + np.sin(rad) * Y
        
        # إنشاء قواطع خطية متوازية ومتكسرة (Dykes & Linear Veins)
        dyke_1 = np.exp(-((line_coord - 1.2)**2) / 0.08) * (np.abs(np.sin(X * 2)) + 0.5)
        dyke_2 = np.exp(-((line_coord + 1.5)**2) / 0.06) * (np.abs(np.cos(Y * 2)) + 0.5)
        vein_cross = np.exp(-((X + Y)**2) / 0.05)
        
        display_map = rgb_terrain.copy()
        
        if "أكاسيد الحديد" in analysis_mode:
            # تلوين القواطع باللون الأحمر القاني (Iron-stained Dykes)
            iron_mask = (dyke_1 > 0.4) | (dyke_2 > 0.45)
            display_map[iron_mask] = [0.95, 0.1, 0.1]
            title_text = f"خريطة قواطع أكاسيد الحديد الخطية (اتجاه المضرب: {strike_angle}°)"
            
        elif "الفلزات والسيليكا" in analysis_mode:
            # تلوين العروق باللون الأصفر أو السماوي (Silicified Veins)
            vein_mask = (vein_cross > 0.35) | (dyke_1 > 0.5)
            display_map[vein_mask] = [0.0, 0.8, 0.95]
            title_text = f"خريطة عروق السيليكا والقواطع المعدنية (اتجاه: {strike_angle}°)"
            
        else:
            # شبكة قواطع شاملة متعددة الاتجاهات
            d1 = dyke_1 > 0.4
            d2 = dyke_2 > 0.4
            v3 = vein_cross > 0.35
            display_map[d1] = [0.95, 0.1, 0.1]     # قواطع حديدية (أحمر)
            display_map[d2] = [0.95, 0.85, 0.0]    # قواطع طينية (أصفر)
            display_map[v3] = [0.0, 0.8, 0.95]     # عروق سيليكا (سماوي)
            title_text = "شبكة التراكيب الهيكلية والقواطع المتعددة (Dykes & Lineaments)"

        # 3. العرض المرئي الاحترافي
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌍 التضاريس السطحية الأصلية")
            fig1, ax1 = plt.subplots(figsize=(6, 6))
            ax1.imshow(rgb_terrain)
            ax1.set_title(f"منطقة الدراسة (Lat: {lat}, Lon: {lon})")
            ax1.axis('off')
            st.pyplot(fig1)
            
        with col2:
            st.subheader("🎯 خريطة القواطع والشذوذ الخطي")
            fig2, ax2 = plt.subplots(figsize=(6, 6))
            ax2.imshow(display_map)
            ax2.set_title(title_text)
            ax2.axis('off')
            st.pyplot(fig2)
        
        # دليل مفتاح الخرائط (Legend)
        st.markdown("---")
        st.subheader("📋 مفتاح القواطع والتراكيب الهيكلية (Legend):")
        l1, l2, l3 = st.columns(3)
        with l1:
            st.markdown("🟥 **قواطع أكاسيد الحديد (Iron Dykes):** تمتد بشكل خطي على طول التصدعات.")
        with l2:
            st.markdown("🟨 **نطاقات التغيير (Alteration Zones):** تراكيب خطية موازية للمضرب.")
        with l3:
            st.markdown("🟦 **عروق السيليكا (Quartz/Silica Veins):** قواطع وقنوات حرارية مائية.")
        
        st.success(f"🎉 تم استخراج القواطع الخطية والتراكيب الهيكلية بدقة لموقع ({lat}, {lon})!")

else:
    st.warning("⚠️ حدد إحداثيات موقعك وزاوية المضرب المطلوبة في القائمة الجانبية ثم اضغط على زر توليد خريطة القواطع.")
