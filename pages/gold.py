# 2. تهيئة وتوثيق Google Earth Engine باستخدام Secrets مع معالجة الأخطاء
@st.cache_resource
def init_earth_engine():
    try:
        if "GEE_SERVICE_ACCOUNT" in st.secrets:
            gee_secret = st.secrets["GEE_SERVICE_ACCOUNT"]
            
            # إذا كان النص عبارة عن سلسلة نصية (JSON String)
            if isinstance(gee_secret, str):
                # تنظيف الرموز الخاصة وغير المرئية لتجنب خطأ Invalid control character
                cleaned_secret = gee_secret.replace('\r', '').replace('\t', ' ')
                try:
                    key_dict = json.loads(cleaned_secret, strict=False)
                except Exception:
                    # محاولة معالجة السطر الجديد داخل private_key إن وجد
                    key_dict = json.loads(cleaned_secret.replace('\n', '\\n'), strict=False)
            else:
                # إذا تم الحفظ كـ TOML Table (Dictionary)
                key_dict = dict(gee_secret)

            # معالجة private_key في حال استخدام \\n
            if "private_key" in key_dict and isinstance(key_dict["private_key"], str):
                key_dict["private_key"] = key_dict["private_key"].replace('\\n', '\n')

            credentials = ee.ServiceAccountCredentials(
                key_dict["client_email"], 
                key_data=json.dumps(key_dict)
            )
            ee.Initialize(credentials)
            return True, "تم الاتصال بنجاح بخوادم Google Earth Engine!"
        else:
            ee.Initialize()
            return True, "تم الاتصال بالحساب الافتراضي!"
    except Exception as e:
        return False, f"فشل الاتصال: {str(e)}"
