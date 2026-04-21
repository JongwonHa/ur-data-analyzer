# src/analyzer.py
import pandas as pd
import numpy as np
from typing import Dict, List
import sys
import os

# 상위 디렉토리를 path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.robot_specs import ROBOT_SPECS, SAFETY_MARGINS


class URDataAnalyzer:
    """UR 로봇 데이터 분석기"""
    
    def __init__(self, df: pd.DataFrame, robot_model: str = "UR10e"):
        self.df = df
        self.robot_model = robot_model
        self.specs = ROBOT_SPECS.get(robot_model, ROBOT_SPECS["UR10e"])
        self.margins = SAFETY_MARGINS
        self.analysis_results = {}
        
        # 컬럼 이름 자동 매핑
        self.column_mapping = self._detect_columns()
        
    def _detect_columns(self) -> Dict:
        """데이터프레임의 컬럼을 자동으로 감지"""
        mapping = {
            "timestamp": None,
            "joint_speed": [],
            "joint_accel": [],
            "joint_current": [],
            "joint_temp": [],
            "tcp_speed": None,
            "tcp_pose": []
        }
        
        columns = self.df.columns.tolist()
        
        for col in columns:
            col_lower = col.lower()
            
            # 타임스탬프
            if 'time' in col_lower or 'timestamp' in col_lower:
                mapping["timestamp"] = col
            
            # 관절 속도
            if any(x in col_lower for x in ['qd', 'joint_speed', 'velocity']):
                if 'qdd' not in col_lower:  # 가속도 제외
                    mapping["joint_speed"].append(col)
            
            # 관절 가속도
            if 'qdd' in col_lower or 'accel' in col_lower:
                mapping["joint_accel"].append(col)
            
            # 관절 전류
            if 'current' in col_lower:
                mapping["joint_current"].append(col)
            
            # 관절 온도
            if 'temp' in col_lower:
                mapping["joint_temp"].append(col)
            
            # TCP 속도
            if 'tcp' in col_lower and 'speed' in col_lower:
                mapping["tcp_speed"] = col
            
            # TCP 위치
            if 'tcp' in col_lower and ('pose' in col_lower or 'position' in col_lower):
                mapping["tcp_pose"].append(col)
        
        return mapping
        
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
            "recommendations": []
        }
        
        # 권장사항 생성
        self.analysis_results["recommendations"] = self.generate_recommendations()
        
        return self.analysis_results
    
    def _get_data_summary(self) -> Dict:
        """데이터 요약 정보"""
        duration = len(self.df) * 0.008  # 125Hz 가정
        
        if self.column_mapping["timestamp"]:
            ts_col = self.column_mapping["timestamp"]
            duration = self.df[ts_col].max() - self.df[ts_col].min()
        
        return {
            "total_samples": len(self.df),
            "duration_seconds": round(duration, 2),
            "detected_columns": {k: v for k, v in self.column_mapping.items() if v}
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
        for i, col in enumerate(speed_cols[:6]):  # 최대 6개 관절
            speed_data = np.abs(self.df[col])
            
            # rad/s인 경우 deg/s로 변환 (값이 작으면 rad/s로 간주)
            if speed_data.max() < 10:
                speed_data = speed_data * (180 / np.pi)
            
            max_allowed = self.specs["max_joint_speed"][i] if i < len(self.specs["max_joint_speed"]) else 180
            recommended = max_allowed * self.margins["speed"]
            
            current_max = round(float(speed_data.max()), 2)
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
                "current_avg": round(float(speed_data.mean()), 2),
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
            
            results["tcp_speed"] = {
                "current_max": round(float(tcp_speed.max()), 4),
                "current_avg": round(float(tcp_speed.mean()), 4),
                "max_allowed": max_tcp,
                "recommended": round(recommended_tcp, 4),
                "utilization": round((tcp_speed.max() / max_tcp) * 100, 1),
                "status": "정상" if tcp_speed.max() <= recommended_tcp else "주의",
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
            accel_data = np.abs(self.df[col])
            
            # rad/s²인 경우 deg/s²로 변환
            if accel_data.max() < 20:
                accel_data = accel_data * (180 / np.pi)
            
            current_max = round(float(accel_data.max()), 2)
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
                "current_avg": round(float(accel_data.mean()), 2),
                "max_allowed": max_allowed,
                "recommended": round(recommended, 2),
                "utilization": utilization,
                "status": status,
                "unit": "°/s²"
            }
        
        return results
    
    def analyze_load(self) -> Dict:
        """부하율(전류) 분석"""
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
            "smooth_motion_score": 0
        }
        
        # TCP 속도 기반 모션 효율
        tcp_col = self.column_mapping["tcp_speed"]
        if tcp_col:
            tcp_speed = self.df[tcp_col]
            moving = (tcp_speed > 0.001).sum()
            total = len(tcp_speed)
            results["motion_efficiency"] = round((moving / total) * 100, 1) if total > 0 else 0
            results["idle_time_ratio"] = round(100 - results["motion_efficiency"], 1)
        
        # 부드러운 모션 점수 (저크 기반)
        accel_cols = self.column_mapping["joint_accel"]
        if accel_cols:
            jerk_values = []
            for col in accel_cols[:6]:
                jerk = np.abs(self.df[col].diff()).mean()
                jerk_values.append(jerk)
            avg_jerk = np.mean(jerk_values)
            results["smooth_motion_score"] = round(max(0, min(100, 100 - (avg_jerk * 5))), 1)
        
        return results
    
    def generate_recommendations(self) -> List[Dict]:
        """권장사항 생성"""
        recommendations = []
        
        # 속도 관련
        speed_results = self.analysis_results.get("speed_analysis", {})
        for joint, data in speed_results.get("joint_speed", {}).items():
            if data.get("status") in ["주의", "경고"]:
                recommendations.append({
                    "category": "속도",
                    "priority": "높음" if data["status"] == "경고" else "중간",
                    "target": joint,
                    "issue": f"현재 최대 속도 {data['current_max']}°/s가 {'최대치' if data['status'] == '경고' else '권장치'}를 초과",
                    "current_value": f"{data['current_max']} °/s",
                    "recommended_value": f"{data['recommended']} °/s 이하",
                    "recommendation": f"속도를 {data['recommended']}°/s 이하로 설정하세요",
                    "benefit": "관절 수명 연장 및 안전성 향상"
                })
        
        # 부하 관련
        load_results = self.analysis_results.get("load_analysis", {})
        if load_results.get("peak_load_ratio", 0) > 80:
            recommendations.append({
                "category": "부하",
                "priority": "높음" if load_results["peak_load_ratio"] > 100 else "중간",
                "target": "전체 시스템",
                "issue": f"피크 부하율 {load_results['peak_load_ratio']}%로 높음",
                "current_value": f"{load_results['peak_load_ratio']}%",
                "recommended_value": "75% 이하",
                "recommendation": "페이로드 검토 및 가감속 설정 완화",
                "benefit": "모터 과부하 방지 및 에너지 효율 개선"
            })
        
        # 가속도 관련
        accel_results = self.analysis_results.get("acceleration_analysis", {})
        for joint, data in accel_results.get("joint_acceleration", {}).items():
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
        
        # 온도 관련
        temp_results = self.analysis_results.get("temperature_analysis", {})
        if temp_results.get("max_temp", 0) > self.specs["max_temp"] * 0.85:
            recommendations.append({
                "category": "온도",
                "priority": "중간",
                "target": "냉각 시스템",
                "issue": f"최대 온도 {temp_results['max_temp']}°C로 높음",
                "current_value": f"{temp_results['max_temp']}°C",
                "recommended_value": f"{self.specs['max_temp'] * 0.85}°C 이하",
                "recommendation": "작업 간 휴식 시간 추가 또는 환경 온도 확인",
                "benefit": "과열 방지 및 장비 수명 연장"
            })
        
        # 효율성 관련
        efficiency = self.analysis_results.get("efficiency_analysis", {})
        if efficiency.get("idle_time_ratio", 0) > 30:
            recommendations.append({
                "category": "효율성",
                "priority": "낮음",
                "target": "프로그램 최적화",
                "issue": f"유휴 시간 비율 {efficiency['idle_time_ratio']}%",
                "current_value": f"{efficiency['idle_time_ratio']}%",
                "recommended_value": "30% 이하",
                "recommendation": "경로 최적화 및 블렌딩 반경 조정",
                "benefit": "사이클 타임 단축 및 생산성 향상"
            })
        
        # 우선순위로 정렬
        priority_order = {"높음": 0, "중간": 1, "낮음": 2}
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))
        
        return recommendations
