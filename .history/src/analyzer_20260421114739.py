# src/analyzer.py
import pandas as pd
import numpy as np
from typing import Dict, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.robot_specs import ROBOT_SPECS, SAFETY_MARGINS


class URDataAnalyzer:
    """UR 로봇 데이터 분석기 - 실제 RTDE 데이터 형식 지원"""
    
    def __init__(self, df: pd.DataFrame, robot_model: str = "UR10e"):
        self.df = df.copy()
        self.robot_model = robot_model
        self.specs = ROBOT_SPECS.get(robot_model, ROBOT_SPECS["UR10e"])
        self.margins = SAFETY_MARGINS
        self.analysis_results = {}
        
        # 컬럼 매핑 (실제 RTDE 형식)
        self.column_mapping = self._detect_columns()
        
        # TCP 속도 계산 (x, y, z 성분으로부터)
        self._calculate_tcp_speed()
        
    def _detect_columns(self) -> Dict:
        """실제 UR RTDE 데이터 컬럼 감지"""
        mapping = {
            "timestamp": None,
            "joint_speed": [],      # Actual velocity j0~j5
            "joint_accel": [],      # Target acceleration j0~j5
            "joint_current": [],    # Actual current j0~j5
            "joint_temp": [],       # Temperature j0~j5
            "tcp_speed": None,      # 계산됨
            "tcp_speed_x": None,
            "tcp_speed_y": None,
            "tcp_speed_z": None,
            "tcp_pose": [],
            "speed_scaling": None,
            "payload_mass": None,
            "safety_mode": None,
            "robot_mode": None
        }
        
        columns = self.df.columns.tolist()
        
        for col in columns:
            col_lower = col.lower()
            
            # 타임스탬프
            if 'timestamp' in col_lower:
                mapping["timestamp"] = col
            
            # 관절 속도 (Actual velocity j0 [rad/s])
            if 'actual velocity' in col_lower and 'tcp' not in col_lower:
                mapping["joint_speed"].append(col)
            
            # 관절 가속도 (Target acceleration j0 [rad/s^2])
            # 실제 데이터에 Actual acceleration이 없으면 Target 사용
            if 'acceleration' in col_lower and 'tcp' not in col_lower:
                mapping["joint_accel"].append(col)
            
            # 관절 전류 (Actual current j0 [A])
            if 'actual current' in col_lower:
                mapping["joint_current"].append(col)
            
            # 관절 온도 (Temperature j0 [C])
            if 'temperature' in col_lower and 'j' in col_lower:
                mapping["joint_temp"].append(col)
            
            # TCP 속도 성분
            if 'actual tcp velocity x' in col_lower:
                mapping["tcp_speed_x"] = col
            if 'actual tcp velocity y' in col_lower:
                mapping["tcp_speed_y"] = col
            if 'actual tcp velocity z' in col_lower:
                mapping["tcp_speed_z"] = col
            
            # TCP 위치
            if 'actual tcp pose' in col_lower:
                mapping["tcp_pose"].append(col)
            
            # Speed scaling
            if 'speed scaling' in col_lower:
                mapping["speed_scaling"] = col
            
            # Payload
            if 'payload mass' in col_lower:
                mapping["payload_mass"] = col
            
            # Safety mode
            if 'safety mode' in col_lower:
                mapping["safety_mode"] = col
            
            # Robot mode
            if col_lower == 'robot mode':
                mapping["robot_mode"] = col
        
        # 정렬 (j0, j1, j2... 순서로)
        for key in ["joint_speed", "joint_accel", "joint_current", "joint_temp"]:
            mapping[key] = sorted(mapping[key], key=lambda x: x.lower())
        
        return mapping
    
    def _calculate_tcp_speed(self):
        """TCP 속도 계산 (x, y, z 성분으로부터)"""
        x_col = self.column_mapping["tcp_speed_x"]
        y_col = self.column_mapping["tcp_speed_y"]
        z_col = self.column_mapping["tcp_speed_z"]
        
        if x_col and y_col and z_col:
            # 총 TCP 속도 = sqrt(vx² + vy² + vz²)
            self.df['_calculated_tcp_speed'] = np.sqrt(
                self.df[x_col]**2 + 
                self.df[y_col]**2 + 
                self.df[z_col]**2
            )
            self.column_mapping["tcp_speed"] = '_calculated_tcp_speed'
        
    def analyze_all(self) -> Dict:
        """전체 분석 실행"""
        self.analysis_results = {
            "robot_model": self.robot_model,
            "data_summary": self._get_data_summary(),
            "speed_analysis": self.analyze_speed(),
            "acceleration_analysis": self.analyze_acceleration(),
            "load_analysis": self.analyze_load(),
            "temperature_analysis": self.analyze_temperature(),
            "efficiency_analysis": self.analyze_efficiency(),
            "additional_info": self.analyze_additional(),
            "recommendations": []
        }
        
        self.analysis_results["recommendations"] = self.generate_recommendations()
        
        return self.analysis_results
    
    def _get_data_summary(self) -> Dict:
        """데이터 요약"""
        ts_col = self.column_mapping["timestamp"]
        
        if ts_col:
            duration = self.df[ts_col].max() - self.df[ts_col].min()
            sample_rate = len(self.df) / duration if duration > 0 else 500
        else:
            duration = len(self.df) * 0.002  # 500Hz 기본
            sample_rate = 500
        
        return {
            "total_samples": len(self.df),
            "duration_seconds": round(duration, 2),
            "sample_rate_hz": round(sample_rate, 1),
            "detected_columns": {
                "timestamp": self.column_mapping["timestamp"],
                "joint_speed_count": len(self.column_mapping["joint_speed"]),
                "joint_accel_count": len(self.column_mapping["joint_accel"]),
                "joint_current_count": len(self.column_mapping["joint_current"]),
                "joint_temp_count": len(self.column_mapping["joint_temp"]),
                "tcp_speed": "계산됨" if self.column_mapping["tcp_speed"] else "없음"
            }
        }
    
    def analyze_speed(self) -> Dict:
        """속도 분석"""
        results = {
            "joint_speed": {},
            "tcp_speed": {},
            "overall_status": "정상"
        }
        
        # 관절 속도 분석
        speed_cols = self.column_mapping["joint_speed"]
        for i, col in enumerate(speed_cols[:6]):
            speed_rad = np.abs(self.df[col])
            speed_deg = speed_rad * (180 / np.pi)  # rad/s → deg/s
            
            max_allowed = self.specs["max_joint_speed"][i] if i < len(self.specs["max_joint_speed"]) else 180
            recommended = max_allowed * self.margins["speed"]
            
            current_max = round(float(speed_deg.max()), 2)
            utilization = round((current_max / max_allowed) * 100, 1)
            
            status = "정상"
            if current_max > max_allowed:
                status = "경고"
                results["overall_status"] = "경고"
            elif current_max > recommended:
                status = "주의"
                if results["overall_status"] == "정상":
                    results["overall_status"] = "주의"
            
            results["joint_speed"][f"Joint_{i}"] = {
                "current_max": current_max,
                "current_avg": round(float(speed_deg.mean()), 2),
                "current_max_rad": round(float(speed_rad.max()), 4),
                "max_allowed": max_allowed,
                "recommended": round(recommended, 2),
                "utilization": utilization,
                "status": status,
                "unit": "°/s"
            }
        
        # TCP 속도 분석
        tcp_col = self.column_mapping["tcp_speed"]
        if tcp_col:
            tcp_speed = self.df[tcp_col]
            max_tcp = self.specs["max_tcp_speed"]
            recommended_tcp = max_tcp * self.margins["speed"]
            
            current_max = round(float(tcp_speed.max()), 4)
            utilization = round((current_max / max_tcp) * 100, 1)
            
            status = "정상"
            if current_max > max_tcp:
                status = "경고"
            elif current_max > recommended_tcp:
                status = "주의"
            
            results["tcp_speed"] = {
                "current_max": current_max,
                "current_avg": round(float(tcp_speed.mean()), 4),
                "max_allowed": max_tcp,
                "recommended": round(recommended_tcp, 4),
                "utilization": utilization,
                "status": status,
                "unit": "m/s"
            }
        
        return results
    
    def analyze_acceleration(self) -> Dict:
        """가속도 분석"""
        results = {
            "joint_acceleration": {},
            "overall_status": "정상"
        }
        
        accel_cols = self.column_mapping["joint_accel"]
        max_allowed = self.specs["max_joint_accel"]
        recommended = max_allowed * self.margins["accel"]
        
        for i, col in enumerate(accel_cols[:6]):
            accel_rad = np.abs(self.df[col])
            accel_deg = accel_rad * (180 / np.pi)  # rad/s² → deg/s²
            
            current_max = round(float(accel_deg.max()), 2)
            utilization = round((current_max / max_allowed) * 100, 1)
            
            status = "정상"
            if current_max > max_allowed:
                status = "경고"
                results["overall_status"] = "경고"
            elif current_max > recommended:
                status = "주의"
                if results["overall_status"] == "정상":
                    results["overall_status"] = "주의"
            
            results["joint_acceleration"][f"Joint_{i}"] = {
                "current_max": current_max,
                "current_avg": round(float(accel_deg.mean()), 2),
                "current_max_rad": round(float(accel_rad.max()), 4),
                "max_allowed": max_allowed,
                "recommended": round(recommended, 2),
                "utilization": utilization,
                "status": status,
                "unit": "°/s²"
            }
        
        return results
    
    def analyze_load(self) -> Dict:
        """부하(전류) 분석"""
        results = {
            "joint_current": {},
            "total_load_ratio": 0,
            "peak_load_ratio": 0,
            "overall_status": "정상"
        }
        
        current_cols = self.column_mapping["joint_current"]
        utilizations = []
        
        for i, col in enumerate(current_cols[:6]):
            current_data = np.abs(self.df[col])
            nominal = self.specs["nominal_current"][i] if i < len(self.specs["nominal_current"]) else 2.0
            recommended = nominal * self.margins["current"]
            
            current_max = round(float(current_data.max()), 3)
            utilization = round((current_max / nominal) * 100, 1)
            utilizations.append(utilization)
            
            status = "정상"
            if current_max > nominal:
                status = "경고"
                results["overall_status"] = "경고"
            elif current_max > recommended:
                status = "주의"
                if results["overall_status"] == "정상":
                    results["overall_status"] = "주의"
            
            results["joint_current"][f"Joint_{i}"] = {
                "current_max": current_max,
                "current_avg": round(float(current_data.mean()), 3),
                "nominal": nominal,
                "recommended_max": round(recommended, 3),
                "utilization": utilization,
                "status": status,
                "unit": "A"
            }
        
        if utilizations:
            results["total_load_ratio"] = round(np.mean(utilizations), 1)
            results["peak_load_ratio"] = round(max(utilizations), 1)
        
        return results
    
    def analyze_temperature(self) -> Dict:
        """온도 분석"""
        results = {
            "joint_temperatures": {},
            "max_temp": 0,
            "avg_temp": 0,
            "overall_status": "정상"
        }
        
        temp_cols = self.column_mapping["joint_temp"]
        max_allowed = self.specs["max_temp"]
        recommended = max_allowed * self.margins["temp"]
        temps = []
        
        for i, col in enumerate(temp_cols[:6]):
            temp_data = self.df[col]
            current_max = round(float(temp_data.max()), 1)
            temps.append(current_max)
            
            status = "정상"
            if current_max > max_allowed:
                status = "경고"
                results["overall_status"] = "경고"
            elif current_max > recommended:
                status = "주의"
                if results["overall_status"] == "정상":
                    results["overall_status"] = "주의"
            
            results["joint_temperatures"][f"Joint_{i}"] = {
                "current_max": current_max,
                "current_avg": round(float(temp_data.mean()), 1),
                "current_min": round(float(temp_data.min()), 1),
                "max_allowed": max_allowed,
                "recommended_max": round(recommended, 1),
                "status": status,
                "unit": "°C"
            }
        
        if temps:
            results["max_temp"] = max(temps)
            results["avg_temp"] = round(np.mean(temps), 1)
        
        return results
    
    def analyze_efficiency(self) -> Dict:
        """효율성 분석"""
        results = {
            "motion_efficiency": 0,
            "idle_time_ratio": 0,
            "smooth_motion_score": 0,
            "speed_scaling_avg": 100
        }
        
        # TCP 속도 기반 모션 효율
        tcp_col = self.column_mapping["tcp_speed"]
        if tcp_col:
            tcp_speed = self.df[tcp_col]
            moving_threshold = 0.001  # 1mm/s 이상이면 움직이는 중
            moving = (tcp_speed > moving_threshold).sum()
            total = len(tcp_speed)
            results["motion_efficiency"] = round((moving / total) * 100, 1) if total > 0 else 0
            results["idle_time_ratio"] = round(100 - results["motion_efficiency"], 1)
        
        # Speed Scaling 분석
        scaling_col = self.column_mapping["speed_scaling"]
        if scaling_col:
            results["speed_scaling_avg"] = round(float(self.df[scaling_col].mean() * 100), 1)
        
        # 부드러운 모션 점수 (저크 기반)
        accel_cols = self.column_mapping["joint_accel"]
        if accel_cols:
            jerk_values = []
            for col in accel_cols[:6]:
                jerk = np.abs(self.df[col].diff()).mean()
                jerk_values.append(jerk)
            avg_jerk = np.mean(jerk_values)
            results["smooth_motion_score"] = round(max(0, min(100, 100 - (avg_jerk * 2))), 1)
        
        return results
    
    def analyze_additional(self) -> Dict:
        """추가 정보 분석"""
        results = {}
        
        # 페이로드
        payload_col = self.column_mapping["payload_mass"]
        if payload_col:
            payload = self.df[payload_col].iloc[-1] if len(self.df) > 0 else 0
            results["payload_mass"] = {
                "value": round(float(payload), 2),
                "max_allowed": self.specs["max_payload"],
                "utilization": round((payload / self.specs["max_payload"]) * 100, 1),
                "unit": "kg"
            }
        
        # Safety mode 분석
        safety_col = self.column_mapping["safety_mode"]
        if safety_col:
            safety_modes = self.df[safety_col].value_counts().to_dict()
            results["safety_mode_distribution"] = safety_modes
        
        return results
    
    def generate_recommendations(self) -> List[Dict]:
        """권장사항 생성"""
        recommendations = []
        
        # 속도 권장사항
        speed = self.analysis_results.get("speed_analysis", {})
        for joint, data in speed.get("joint_speed", {}).items():
            if data.get("status") in ["주의", "경고"]:
                recommendations.append({
                    "category": "속도",
                    "priority": "높음" if data["status"] == "경고" else "중간",
                    "target": joint,
                    "issue": f"현재 최대 속도 {data['current_max']}°/s가 {'최대치' if data['status'] == '경고' else '권장치'} 초과",
                    "current_value": f"{data['current_max']} °/s",
                    "recommended_value": f"{data['recommended']} °/s 이하",
                    "recommendation": f"속도를 {data['recommended']}°/s 이하로 설정하세요",
                    "benefit": "관절 수명 연장 및 안전성 향상"
                })
        
        # TCP 속도 권장사항
        tcp = speed.get("tcp_speed", {})
        if tcp.get("status") in ["주의", "경고"]:
            recommendations.append({
                "category": "TCP 속도",
                "priority": "높음" if tcp["status"] == "경고" else "중간",
                "target": "TCP",
                "issue": f"TCP 속도 {tcp['current_max']} m/s가 권장치 초과",
                "current_value": f"{tcp['current_max']} m/s",
                "recommended_value": f"{tcp['recommended']} m/s 이하",
                "recommendation": f"TCP 속도를 {tcp['recommended']} m/s 이하로 설정하세요",
                "benefit": "정밀도 향상 및 안전성 확보"
            })
        
        # 가속도 권장사항
        accel = self.analysis_results.get("acceleration_analysis", {})
        for joint, data in accel.get("joint_acceleration", {}).items():
            if data.get("status") in ["주의", "경고"]:
                recommendations.append({
                    "category": "가속도",
                    "priority": "높음" if data["status"] == "경고" else "중간",
                    "target": joint,
                    "issue": f"가속도 {data['current_max']}°/s²가 권장치 초과",
                    "current_value": f"{data['current_max']} °/s²",
                    "recommended_value": f"{data['recommended']} °/s² 이하",
                    "recommendation": f"가속도를 {data['recommended']}°/s² 이하로 낮추세요",
                    "benefit": "진동 감소 및 정밀도 향상"
                })
        
        # 부하 권장사항
        load = self.analysis_results.get("load_analysis", {})
        if load.get("peak_load_ratio", 0) > 80:
            recommendations.append({
                "category": "부하",
                "priority": "높음" if load["peak_load_ratio"] > 100 else "중간",
                "target": "전체 시스템",
                "issue": f"피크 부하율 {load['peak_load_ratio']}%로 높음",
                "current_value": f"{load['peak_load_ratio']}%",
                "recommended_value": "75% 이하",
                "recommendation": "페이로드 검토 및 가감속 설정 완화",
                "benefit": "모터 과부하 방지 및 수명 연장"
            })
        
        # 온도 권장사항
        temp = self.analysis_results.get("temperature_analysis", {})
        if temp.get("max_temp", 0) > self.specs["max_temp"] * 0.85:
            recommendations.append({
                "category": "온도",
                "priority": "높음" if temp["max_temp"] > self.specs["max_temp"] * 0.95 else "중간",
                "target": "관절 냉각",
                "issue": f"최대 온도 {temp['max_temp']}°C로 높음",
                "current_value": f"{temp['max_temp']}°C",
                "recommended_value": f"{round(self.specs['max_temp'] * 0.85, 1)}°C 이하",
                "recommendation": "작업 간 휴식 시간 추가 또는 환경 온도 확인",
                "benefit": "과열 방지 및 장비 수명 연장"
            })
        
        # 효율성 권장사항
        eff = self.analysis_results.get("efficiency_analysis", {})
        if eff.get("idle_time_ratio", 0) > 40:
            recommendations.append({
                "category": "효율성",
                "priority": "낮음",
                "target": "프로그램 최적화",
                "issue": f"유휴 시간 비율 {eff['idle_time_ratio']}%",
                "current_value": f"{eff['idle_time_ratio']}%",
                "recommended_value": "40% 이하",
                "recommendation": "경로 최적화 및 블렌딩 반경 조정",
                "benefit": "사이클 타임 단축 및 생산성 향상"
            })
        
        # 우선순위 정렬
        priority_order = {"높음": 0, "중간": 1, "낮음": 2}
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))
        
        return recommendations
