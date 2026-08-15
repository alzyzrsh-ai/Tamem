import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 1. إدخال بيانات الجسة (VES No. 2) من واقع الجدول
data_ves2 = {
    'MN/2': [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 10, 0.5, 10, 10, 
             10, 10, 10, 50, 10, 50, 50, 50, 50, 50, 50, 50],
    'AB/2': [1.5, 2.5, 4, 6, 8, 10, 15, 20, 30, 40, 40, 50, 
             75, 100, 160, 150, 200, 200, 300, 400, 500, 600, 700, 800],
    'Rho_a': [428.3, 382.6, 369.5, 319.8, 330.0, 349.3, 342.8, 315.4, 311.3, 302.2, 
              245.3, 210.0, 166.7, 135.8, 68.2, 73.0, 50.0, 38.1, 15.2, 14.9, 16.5, 25.1, 10.6, 22.4]
}

df = pd.DataFrame(data_ves2)

# 2. رسم منحنى الجسة Log-Log Plot
plt.figure(figsize=(8, 5))
plt.loglog(df['AB/2'], df['Rho_a'], 'ro-', label='VES No. 2 Measured')
plt.xlabel('Half Electrode Spacing AB/2 (m)')
plt.ylabel('Apparent Resistivity $\\rho_a$ (Ohm.m)')
plt.title('Sounding Curve - VES No. 2 (UTM: 330407, 1558564)')
plt.grid(True, which="both", ls="--")
plt.legend()
plt.show()

# 3. القيمة المشتقة للنطاق المشبع (العميق) لاستخدامها في نموذج الذكاء الاصطناعي
deep_aquifer_resistivity = df[df['AB/2'] >= 200]['Rho_a'].mean()
print(f"متوسط المقاومية الكهربائية للنطاق العميق المشبع: {deep_aquifer_resistivity:.2f} Ohm.m")
