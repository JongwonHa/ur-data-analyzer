# create_sample.py
import pandas as pd
import numpy as np

print("샘플 데이터 생성 중...")

# 10초 데이터, 125Hz 샘플링
n_samples = 1250
time = np.linspace(0, 10, n_samples)

data = {'timestamp': time}

# 6개 관절 데이터 생성
for i in range(6):
    # 관절 속도 (rad/s)
    data[f'actual_qd_{i}'] = np.sin(time * (i+1) * 0.5) * 2.0 + np.random.normal(0, 0.1, n_samples)
    
    # 관절 가속도 (rad/s²)
    data[f'actual_qdd_{i}'] = np.cos(time * (i+1) * 0.5) * 5.0 + np.random.normal(0, 0.2, n_samples)
    
    # 관절 전류 (A)
    data[f'actual_current_{i}'] = np.abs(np.sin(time * 0.3)) * (2.5 - i*0.3) + 0.5 + np.random.normal(0, 0.05, n_samples)
    
    # 관절 온도 (°C)
    base_temp = 45 + i * 3
    data[f'joint_temp_{i}'] = base_temp + np.cumsum(np.random.normal(0.005, 0.002, n_samples))

# TCP 속도 (m/s)
data['actual_TCP_speed'] = np.abs(np.sin(time * 0.5)) * 0.7 + np.random.normal(0, 0.02, n_samples)
data['actual_TCP_speed'] = np.clip(data['actual_TCP_speed'], 0, None)

# TCP 위치
data['actual_TCP_pose_0'] = np.sin(time * 0.3) * 0.3
data['actual_TCP_pose_1'] = np.cos(time * 0.3) * 0.3
data['actual_TCP_pose_2'] = 0.5 + np.sin(time * 0.2) * 0.1

# DataFrame 생성 및 저장
df = pd.DataFrame(data)
df.to_excel('data/sample_ur_data.xlsx', index=False)
df.to_csv('data/sample_ur_data.csv', index=False)

print(f"✅ 샘플 데이터 생성 완료!")
print(f"   - 파일 위치: data/sample_ur_data.xlsx")
print(f"   - 총 {n_samples} 행, {len(df.columns)} 열")
print(f"   - 컬럼: {list(df.columns)}")
