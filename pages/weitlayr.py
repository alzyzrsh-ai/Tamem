import numpy as np


def generate_drilling_decision(
    radar_band, thermal_band, moisture_band, mineral_mask
):
    # 1. تطبيع البيانات إلى نطاق موحد (0 - 1)
    norm_radar = (radar_band - np.nanmin(radar_band)) / (
        np.nanmax(radar_band) - np.nanmin(radar_band)
    )
    norm_thermal = 1.0 - (
        (thermal_band - np.nanmin(thermal_band))
        / (np.nanmax(thermal_band) - np.nanmin(thermal_band))
    )  # عكس الحرارة: الأبرد هو الأفضل
    norm_moisture = (moisture_band - np.nanmin(moisture_band)) / (
        np.nanmax(moisture_band) - np.nanmin(moisture_band)
    )

    # 2. إعطاء أوزان هيدرولوجية للطبقات (Weighting Scheme)
    # الرادار (40%) + الحرارة (35%) + الرطوبة (25%)
    suitability_index = (
        (norm_radar * 0.40) + (norm_thermal * 0.35) + (norm_moisture * 0.25)
    )

    # 3. تطبيق القناع لعزل التشويش المعدني
    suitability_index[mineral_mask > 0] = 0

    return suitability_index
