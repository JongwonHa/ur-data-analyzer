# src/urscript_analyzer.py
import re
import math
from typing import Dict, List, Tuple, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.robot_specs import ROBOT_SPECS, SAFETY_MARGINS


class URScriptAnalyzer:
    """URScript 파일 분석기 - 거리 기반 정밀 분석 지원"""
    
    def __init__(self, script_content: str, robot_model: str = "UR10e"):
        self.script = script_content
        self.robot_model = robot_model
        self.specs = ROBOT_SPECS.get(robot_model, ROBOT_SPECS["UR10e"])
        self.margins = SAFETY_MARGINS
        self.waypoints = []
        
    def parse(self) -> List[Dict]:
        """URScript에서 웨이포인트(이동 명령어) 추출"""
        
        patterns = {
            "movej": r'movej\s*\(\s*([^)]+)\)',
            "movel": r'movel\s*\(\s*([^)]+)\)',
            "movep": r'movep\s*\(\s*([^)]+)\)',
            "movec": r'movec\s*\(\s*([^)]+)\)',
            "speedl": r'speedl\s*\(\s*([^)]+)\)',
            "speedj": r'speedj\s*\(\s*([^)]+)\)',
        }
        
        self.waypoints = []
        
        for move_type, pattern in patterns.items():
            matches = re.finditer(pattern, self.script, re.IGNORECASE)
            
            for match in matches:
                params = self._parse_params(match.group(1), move_type)
                line_num = self.script[:match.start()].count('\n') + 1
                
                self.waypoints.append({
                    "line": line_num,
                    "type": move_type,
                    "raw": match.group(0),
                    **params
                })
        
        # 라인 순서로 정렬
        self.waypoints.sort(key=lambda x: x["line"])
        
        # ID 할당
        for i, wp in enumerate(self.waypoints):
            wp["id"] = i + 1
        
        # 거리 계산 (이전 웨이포인트와의 거리)
        self._calculate_distances()
        
        return self.waypoints
    
    def _parse_params(self, param_str: str, move_type: str) -> Dict:
        """이동 명령어의 파라미터 파싱"""
        result = {
            "position": None,
            "position_values": None,
            "velocity": None,
            "acceleration": None,
            "blend_radius": None,
            "time": None
        }
        
        # URScript 기본값
        defaults = {
            "movej": {"a": 1.4, "v": 1.05},      # rad/s², rad/s
            "movel": {"a": 1.2, "v": 0.25},      # m/s², m/s
            "movep": {"a": 1.2, "v": 0.25},
            "movec": {"a": 1.2, "v": 0.25},
            "speedl": {"a": 0.5, "v": 0.25},
            "speedj": {"a": 0.5, "v": 0.25},
        }
        
        # 명명된 파라미터 추출
        a_match = re.search(r'a\s*=\s*([\d.]+)', param_str)
        v_match = re.search(r'v\s*=\s*([\d.]+)', param_str)
        t_match = re.search(r't\s*=\s*([\d.]+)', param_str)
        r_match = re.search(r'r\s*=\s*([\d.]+)', param_str)
        
        # 가속도
        if a_match:
            result["acceleration"] = float(a_match.group(1))
            result["acceleration_is_default"] = False
        else:
            result["acceleration"] = defaults.get(move_type, {}).get("a", 1.0)
            result["acceleration_is_default"] = True
            
        # 속도
        if v_match:
            result["velocity"] = float(v_match.group(1))
            result["velocity_is_default"] = False
        else:
            result["velocity"] = defaults.get(move_type, {}).get("v", 0.5)
            result["velocity_is_default"] = True
            
        # 시간
        if t_match:
            result["time"] = float(t_match.group(1))
            
        # 블렌드 반경
        if r_match:
            result["blend_radius"] = float(r_match.group(1))
        
        # 위치 데이터 추출
        # p[x, y, z, rx, ry, rz] 형식 (TCP 좌표)
        tcp_match = re.search(r'p\s*\[\s*([\d.,\s\-e]+)\s*\]', param_str)
        if tcp_match:
            result["position"] = f"p[{tcp_match.group(1)}]"
            result["position_type"] = "tcp"
            try:
                values = [float(x.strip()) for x in tcp_match.group(1).split(',')]
                result["position_values"] = values
            except:
                pass
        else:
            # [q0, q1, q2, q3, q4, q5] 형식 (관절 각도)
            joint_match = re.search(r'\[\s*([\d.,\s\-e]+)\s*\]', param_str)
            if joint_match:
                result["position"] = f"[{joint_match.group(1)}]"
                result["position_type"] = "joint"
                try:
                    values = [float(x.strip()) for x in joint_match.group(1).split(',')]
                    result["position_values"] = values
                except:
                    pass
        
        # 단위 설정
        if move_type in ["movej", "speedj"]:
            result["velocity_unit"] = "rad/s"
            result["acceleration_unit"] = "rad/s²"
            result["is_joint_move"] = True
        else:
            result["velocity_unit"] = "m/s"
            result["acceleration_unit"] = "m/s²"
            result["is_joint_move"] = False
        
        return result
    
    def _calculate_distances(self):
        """웨이포인트 간 거리 계산"""
        for i, wp in enumerate(self.waypoints):
            wp["distance"] = None
            wp["distance_unit"] = None
            
            if i == 0:
                # 첫 번째 웨이포인트는 이전 위치를 알 수 없음
                wp["distance_note"] = "시작점 (이전 위치 불명)"
                continue
            
            prev_wp = self.waypoints[i - 1]
            
            # 같은 좌표 타입인 경우만 거리 계산
            if (wp.get("position_values") and prev_wp.get("position_values") and
                wp.get("position_type") == prev_wp.get("position_type")):
                
                curr_pos = wp["position_values"]
                prev_pos = prev_wp["position_values"]
                
                if wp.get("position_type") == "tcp":
                    # TCP 좌표: x, y, z만 사용하여 유클리드 거리 계산
                    if len(curr_pos) >= 3 and len(prev_pos) >= 3:
                        distance = math.sqrt(
                            (curr_pos[0] - prev_pos[0])**2 +
                            (curr_pos[1] - prev_pos[1])**2 +
                            (curr_pos[2] - prev_pos[2])**2
                        )
                        wp["distance"] = round(distance, 4)
                        wp["distance_unit"] = "m"
                        
                elif wp.get("position_type") == "joint":
                    # 관절 좌표: 관절 각도 변화량의 최대값 (가장 많이 움직이는 관절 기준)
                    if len(curr_pos) >= 6 and len(prev_pos) >= 6:
                        joint_diffs = [abs(curr_pos[j] - prev_pos[j]) for j in range(6)]
                        max_joint_diff = max(joint_diffs)
                        wp["distance"] = round(max_joint_diff, 4)
                        wp["distance_unit"] = "rad"
                        wp["joint_distances"] = [round(d, 4) for d in joint_diffs]
            else:
                # 좌표 타입이 다르거나 위치 정보 없음
                if wp.get("position_type") != prev_wp.get("position_type"):
                    wp["distance_note"] = "좌표 타입 불일치"
                else:
                    wp["distance_note"] = "위치 정보 없음"
    
    def _calculate_reachable_velocity(self, distance: float, acceleration: float, 
                                       is_joint: bool = False) -> Dict:
        """
        주어진 거리와 가속도에서 도달 가능한 최대 속도 계산
        
        사다리꼴 프로파일 가정:
        - 가속 구간: v² = 2 * a * s_acc
        - 감속 구간: v² = 2 * a * s_dec
        - 등속 구간 없이 삼각형일 경우: v_max = √(a * d)
        - 등속 구간 있으면 설정 속도 도달 가능
        """
        if distance is None or distance <= 0:
            return {
                "reachable_velocity": None,
                "profile_type": "unknown",
                "note": "거리 정보 없음"
            }
        
        # 가속+감속에 필요한 최소 거리 (등속 구간 없이)
        # 삼각형 프로파일: v_peak = √(a * d)
        # 여기서 d = s_acc + s_dec = v²/(2a) + v²/(2a) = v²/a
        # 따라서 v = √(a * d)
        
        v_max_reachable = math.sqrt(acceleration * distance)
        
        return {
            "reachable_velocity": round(v_max_reachable, 4),
            "min_distance_for_target": None,  # 나중에 계산
            "profile_type": "triangle",  # 기본적으로 삼각형 가정
        }
    
    def _calculate_motion_profile(self, distance: float, target_velocity: float,
                                   acceleration: float) -> Dict:
        """
        모션 프로파일 상세 분석
        
        Returns:
            - profile_type: 'triangle' (삼각형) 또는 'trapezoidal' (사다리꼴)
            - reachable_velocity: 실제 도달 가능 최대 속도
            - estimated_time: 예상 이동 시간
            - efficiency: 속도 설정 효율성 (%)
            - optimal_velocity: 권장 최적 속도
        """
        if distance is None or distance <= 0:
            return {
                "profile_type": "unknown",
                "reachable_velocity": None,
                "estimated_time": None,
                "efficiency": None,
                "optimal_velocity": None,
                "note": "거리 정보 없음"
            }
        
        # 삼각형 프로파일의 최대 도달 속도
        v_triangle_peak = math.sqrt(acceleration * distance)
        
        # 목표 속도에 도달하기 위한 최소 거리
        # 등속 구간 없이 가속+감속만 할 때: d_min = v² / a
        d_min_for_target = (target_velocity ** 2) / acceleration
        
        if distance >= d_min_for_target:
            # 사다리꼴 프로파일: 목표 속도 도달 가능
            profile_type = "trapezoidal"
            reachable_velocity = target_velocity
            
            # 가속/감속 시간: t_acc = v / a
            t_acc = target_velocity / acceleration
            # 가속/감속 거리: s_acc = v² / (2a)
            s_acc = (target_velocity ** 2) / (2 * acceleration)
            # 등속 거리
            s_const = distance - (2 * s_acc)
            # 등속 시간
            t_const = s_const / target_velocity
            # 총 시간
            estimated_time = 2 * t_acc + t_const
            
            efficiency = 100.0  # 목표 속도 도달
            
        else:
            # 삼각형 프로파일: 목표 속도 도달 불가
            profile_type = "triangle"
            reachable_velocity = v_triangle_peak
            
            # 삼각형 프로파일 시간: t = 2 * √(d / a)
            estimated_time = 2 * math.sqrt(distance / acceleration)
            
            # 효율성: 실제 도달 속도 / 목표 속도
            efficiency = (reachable_velocity / target_velocity) * 100
        
        # 최적 속도 제안 (거리의 80%에서 등속 구간 시작 가정)
        # 적당한 가감속 여유를 두고 계산
        optimal_velocity = math.sqrt(acceleration * distance) * 0.9
        
        return {
            "profile_type": profile_type,
            "reachable_velocity": round(reachable_velocity, 4),
            "min_distance_for_target": round(d_min_for_target, 4),
            "estimated_time": round(estimated_time, 3),
            "efficiency": round(efficiency, 1),
            "optimal_velocity": round(optimal_velocity, 4),
        }
    
    def analyze(self) -> Dict:
        """전체 분석 실행"""
        if not self.waypoints:
            self.parse()
        
        results = {
            "robot_model": self.robot_model,
            "summary": {
                "total_waypoints": len(self.waypoints),
                "movej_count": sum(1 for w in self.waypoints if w["type"] == "movej"),
                "movel_count": sum(1 for w in self.waypoints if w["type"] == "movel"),
                "movep_count": sum(1 for w in self.waypoints if w["type"] == "movep"),
                "movec_count": sum(1 for w in self.waypoints if w["type"] == "movec"),
                "other_count": sum(1 for w in self.waypoints if w["type"] not in ["movej", "movel", "movep", "movec"]),
                "total_distance": 0,
                "estimated_total_time": 0,
            },
            "waypoints": [],
            "issues": [],
            "recommendations": []
        }
        
        total_distance = 0
        total_time = 0
        
        for wp in self.waypoints:
            analysis = self._analyze_waypoint(wp)
            results["waypoints"].append(analysis)
            
            if analysis.get("issues"):
                results["issues"].extend(analysis["issues"])
            
            # 총 거리/시간 누적
            if analysis.get("distance"):
                total_distance += analysis["distance"]
            if analysis.get("motion_profile", {}).get("estimated_time"):
                total_time += analysis["motion_profile"]["estimated_time"]
        
        results["summary"]["total_distance"] = round(total_distance, 4)
        results["summary"]["estimated_total_time"] = round(total_time, 2)
        results["summary"]["issues_count"] = len(results["issues"])
        results["summary"]["warning_count"] = sum(1 for i in results["issues"] if i["severity"] == "경고")
        results["summary"]["caution_count"] = sum(1 for i in results["issues"] if i["severity"] == "주의")
        results["summary"]["inefficient_count"] = sum(1 for i in results["issues"] if i["category"] == "효율성")
        
        # 권장사항 생성
        results["recommendations"] = self._generate_recommendations(results)
        
        return results
    
    def _analyze_waypoint(self, wp: Dict) -> Dict:
        """개별 웨이포인트 분석 (거리 기반 포함)"""
        analysis = {
            "id": wp["id"],
            "line": wp["line"],
            "type": wp["type"],
            "velocity": wp["velocity"],
            "velocity_unit": wp.get("velocity_unit", ""),
            "velocity_is_default": wp.get("velocity_is_default", False),
            "acceleration": wp["acceleration"],
            "acceleration_unit": wp.get("acceleration_unit", ""),
            "acceleration_is_default": wp.get("acceleration_is_default", False),
            "blend_radius": wp["blend_radius"],
            "position": wp.get("position", ""),
            "distance": wp.get("distance"),
            "distance_unit": wp.get("distance_unit"),
            "distance_note": wp.get("distance_note"),
            "raw": wp["raw"],
            "status": "정상",
            "issues": []
        }
        
        # 로봇 스펙 한계값
        if wp.get("is_joint_move", False):
            max_v_deg = max(self.specs["max_joint_speed"])
            max_v = max_v_deg * (math.pi / 180)  # rad/s
            max_a = self.specs["max_joint_accel"] * (math.pi / 180)
        else:
            max_v = self.specs["max_tcp_speed"]
            max_a = 1.5  # TCP 가속도 기본값
        
        recommended_v = max_v * self.margins["speed"]
        recommended_a = max_a * self.margins["accel"]
        
        analysis["max_velocity"] = round(max_v, 4)
        analysis["recommended_velocity"] = round(recommended_v, 4)
        analysis["max_acceleration"] = round(max_a, 4)
        analysis["recommended_acceleration"] = round(recommended_a, 4)
        
        # ========== 1. 기본 속도/가속도 체크 ==========
        if wp["velocity"] and wp["velocity"] > max_v:
            analysis["status"] = "경고"
            analysis["issues"].append({
                "waypoint_id": wp["id"],
                "line": wp["line"],
                "severity": "경고",
                "category": "속도",
                "message": f"Line {wp['line']}: 속도 {wp['velocity']}이 최대 허용치({round(max_v, 3)})를 초과!",
                "current": wp["velocity"],
                "recommended": round(recommended_v, 4),
                "max_allowed": round(max_v, 4)
            })
        elif wp["velocity"] and wp["velocity"] > recommended_v:
            if analysis["status"] == "정상":
                analysis["status"] = "주의"
            analysis["issues"].append({
                "waypoint_id": wp["id"],
                "line": wp["line"],
                "severity": "주의",
                "category": "속도",
                "message": f"Line {wp['line']}: 속도 {wp['velocity']}이 권장치({round(recommended_v, 3)})를 초과",
                "current": wp["velocity"],
                "recommended": round(recommended_v, 4),
                "max_allowed": round(max_v, 4)
            })
        
        # 가속도 체크
        if wp["acceleration"] and wp["acceleration"] > max_a:
            analysis["status"] = "경고"
            analysis["issues"].append({
                "waypoint_id": wp["id"],
                "line": wp["line"],
                "severity": "경고",
                "category": "가속도",
                "message": f"Line {wp['line']}: 가속도 {wp['acceleration']}이 최대 허용치({round(max_a, 3)})를 초과!",
                "current": wp["acceleration"],
                "recommended": round(recommended_a, 4),
                "max_allowed": round(max_a, 4)
            })
        elif wp["acceleration"] and wp["acceleration"] > recommended_a:
            if analysis["status"] == "정상":
                analysis["status"] = "주의"
            analysis["issues"].append({
                "waypoint_id": wp["id"],
                "line": wp["line"],
                "severity": "주의",
                "category": "가속도",
                "message": f"Line {wp['line']}: 가속도 {wp['acceleration']}이 권장치({round(recommended_a, 3)})를 초과",
                "current": wp["acceleration"],
                "recommended": round(recommended_a, 4),
                "max_allowed": round(max_a, 4)
            })
        
        # ========== 2. 거리 기반 분석 ==========
        if wp.get("distance") and wp["velocity"] and wp["acceleration"]:
            motion_profile = self._calculate_motion_profile(
                wp["distance"], 
                wp["velocity"], 
                wp["acceleration"]
            )
            analysis["motion_profile"] = motion_profile
            
            # 효율성 체크: 목표 속도에 도달하지 못하는 경우
            if motion_profile["efficiency"] and motion_profile["efficiency"] < 80:
                if analysis["status"] == "정상":
                    analysis["status"] = "비효율"
                
                analysis["issues"].append({
                    "waypoint_id": wp["id"],
                    "line": wp["line"],
                    "severity": "주의",
                    "category": "효율성",
                    "message": f"Line {wp['line']}: 거리 {wp['distance']}{wp.get('distance_unit', 'm')}에서 "
                              f"설정 속도 {wp['velocity']}의 {motion_profile['efficiency']}%만 도달 가능",
                    "current": wp["velocity"],
                    "reachable": motion_profile["reachable_velocity"],
                    "optimal": motion_profile["optimal_velocity"],
                    "efficiency": motion_profile["efficiency"],
                    "profile_type": motion_profile["profile_type"]
                })
            
            # 최적 속도 제안
            analysis["optimal_velocity"] = motion_profile["optimal_velocity"]
            analysis["reachable_velocity"] = motion_profile["reachable_velocity"]
            analysis["estimated_time"] = motion_profile["estimated_time"]
        
        return analysis
    
    def _generate_recommendations(self, results: Dict) -> List[Dict]:
        """권장사항 생성"""
        recommendations = []
        
        # 속도 이슈
        speed_issues = [i for i in results["issues"] if i["category"] == "속도"]
        if speed_issues:
            recommendations.append({
                "priority": "높음" if any(i["severity"] == "경고" for i in speed_issues) else "중간",
                "category": "속도 설정",
                "issue_count": len(speed_issues),
                "message": f"{len(speed_issues)}개 웨이포인트의 속도가 권장치를 초과합니다.",
                "action": "해당 라인의 v(속도) 파라미터 값을 낮춰주세요.",
                "affected_lines": [i["line"] for i in speed_issues]
            })
        
        # 가속도 이슈
        accel_issues = [i for i in results["issues"] if i["category"] == "가속도"]
        if accel_issues:
            recommendations.append({
                "priority": "높음" if any(i["severity"] == "경고" for i in accel_issues) else "중간",
                "category": "가속도 설정",
                "issue_count": len(accel_issues),
                "message": f"{len(accel_issues)}개 웨이포인트의 가속도가 권장치를 초과합니다.",
                "action": "해당 라인의 a(가속도) 파라미터 값을 낮춰주세요.",
                "affected_lines": [i["line"] for i in accel_issues]
            })
        
        # 🆕 효율성 이슈 (거리 기반)
        efficiency_issues = [i for i in results["issues"] if i["category"] == "효율성"]
        if efficiency_issues:
            recommendations.append({
                "priority": "중간",
                "category": "속도 효율성 (거리 기반)",
                "issue_count": len(efficiency_issues),
                "message": f"{len(efficiency_issues)}개 웨이포인트에서 설정 속도에 도달하지 못합니다. "
                          f"거리가 짧아 가감속만으로 이동이 완료됩니다.",
                "action": "아래 최적 속도로 변경하면 동일한 시간에 더 부드러운 동작이 가능합니다.",
                "affected_lines": [i["line"] for i in efficiency_issues],
                "details": [
                    {
                        "line": i["line"],
                        "current_v": i["current"],
                        "reachable_v": i["reachable"],
                        "optimal_v": i["optimal"],
                        "efficiency": i["efficiency"]
                    }
                    for i in efficiency_issues
                ]
            })
        
        # 블렌드 반경 체크
        no_blend = [w for w in results["waypoints"] 
                   if w.get("blend_radius") in [None, 0] and w["type"] in ["movel", "movej"]]
        if len(no_blend) > 3 and len(results["waypoints"]) > 5:
            recommendations.append({
                "priority": "낮음",
                "category": "블렌드 설정",
                "issue_count": len(no_blend),
                "message": f"{len(no_blend)}개 웨이포인트에 블렌드 반경(r)이 없습니다.",
                "action": "연속 동작 시 r=0.01~0.05 추가로 부드러운 궤적 생성 가능",
                "affected_lines": [w["line"] for w in no_blend]
            })
        
        return recommendations
    
    def generate_report(self) -> str:
        """텍스트 리포트 생성"""
        results = self.analyze()
        
        lines = []
        lines.append("=" * 70)
        lines.append("        URScript 웨이포인트 분석 리포트 (거리 기반 정밀 분석)")
        lines.append("=" * 70)
        lines.append(f"\n🤖 로봇 모델: {self.robot_model}")
        lines.append(f"📊 총 웨이포인트: {results['summary']['total_waypoints']}개")
        lines.append(f"   ├─ movej: {results['summary']['movej_count']}개")
        lines.append(f"   ├─ movel: {results['summary']['movel_count']}개")
        lines.append(f"   └─ 기타: {results['summary']['other_count']}개")
        lines.append(f"\n📏 총 이동 거리: {results['summary']['total_distance']} m (TCP 기준)")
        lines.append(f"⏱️ 예상 총 시간: {results['summary']['estimated_total_time']} 초")
        
        lines.append(f"\n⚠️ 발견된 이슈: {results['summary']['issues_count']}개")
        lines.append(f"   ├─ 경고: {results['summary']['warning_count']}개")
        lines.append(f"   ├─ 주의: {results['summary']['caution_count']}개")
        lines.append(f"   └─ 비효율: {results['summary']['inefficient_count']}개")
        
        # 웨이포인트 상세
        lines.append(f"\n{'─' * 70}")
        lines.append("【 📍 웨이포인트 분석 (거리 기반) 】")
        lines.append(f"{'─' * 70}")
        
        header = f"{'ID':<3} {'Line':<5} {'Type':<6} {'거리':<10} {'설정속도':<10} {'도달가능':<10} {'효율':<8} {'상태':<6}"
        lines.append(header)
        lines.append("-" * 70)
        
        for wp in results["waypoints"]:
            status_icon = {"정상": "✅", "주의": "⚠️", "경고": "🔴", "비효율": "📉"}.get(wp["status"], "")
            
            dist_str = f"{wp['distance']}{wp.get('distance_unit', '')}" if wp.get('distance') else "-"
            v_str = f"{wp['velocity']}"
            
            reachable = wp.get('reachable_velocity') or wp.get('motion_profile', {}).get('reachable_velocity')
            reach_str = f"{reachable}" if reachable else "-"
            
            eff = wp.get('motion_profile', {}).get('efficiency')
            eff_str = f"{eff}%" if eff else "-"
            
            lines.append(f"{wp['id']:<3} {wp['line']:<5} {wp['type']:<6} {dist_str:<10} {v_str:<10} {reach_str:<10} {eff_str:<8} {status_icon}")
        
        # 이슈 상세
        if results["issues"]:
            lines.append(f"\n{'─' * 70}")
            lines.append("【 ⚠️ 발견된 이슈 상세 】")
            lines.append(f"{'─' * 70}")
            
            for issue in results["issues"]:
                icon = "🔴" if issue["severity"] == "경고" else "⚠️" if issue["severity"] == "주의" else "📉"
                lines.append(f"\n{icon} [{issue['severity']}] {issue['message']}")
                
                if issue["category"] == "효율성":
                    lines.append(f"   설정: {issue['current']} → 실제 도달: {issue['reachable']} → 최적: {issue['optimal']}")
                else:
                    lines.append(f"   현재: {issue['current']} → 권장: {issue['recommended']}")
        
        # 권장사항
        lines.append(f"\n{'=' * 70}")
        lines.append("【 💡 권장사항 】")
        lines.append(f"{'=' * 70}")
        
        if results["recommendations"]:
            for rec in results["recommendations"]:
                icon = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(rec["priority"], "")
                lines.append(f"\n{icon} [{rec['priority']}] {rec['category']}")
                lines.append(f"   {rec['message']}")
                lines.append(f"   → {rec['action']}")
                
                # 효율성 이슈는 상세 정보 추가
                if rec["category"] == "속도 효율성 (거리 기반)" and "details" in rec:
                    lines.append(f"\n   {'Line':<6} {'현재속도':<10} {'도달가능':<10} {'최적속도':<10} {'효율':<8}")
                    lines.append(f"   {'-' * 50}")
                    for d in rec["details"][:10]:  # 최대 10개만 표시
                        lines.append(f"   {d['line']:<6} {d['current_v']:<10} {d['reachable_v']:<10} {d['optimal_v']:<10} {d['efficiency']}%")
        else:
            lines.append("\n✅ 모든 웨이포인트가 적정 범위 내에 있습니다!")
        
        lines.append(f"\n{'=' * 70}")
        
        return "\n".join(lines)


# 테스트 코드
if __name__ == "__main__":
    test_script = """
def main_program():
    # 초기 위치
    movej([0.1, -1.5, 1.2, 0, 1.57, 0], a=1.4, v=1.05)
    
    # 작업 시작점으로 이동 (긴 거리)
    movel(p[0.5, 0.2, 0.3, 0, 3.14, 0], a=1.2, v=0.5)
    
    # 짧은 거리 이동 - 속도 너무 높음 (비효율 예상)
    movel(p[0.52, 0.21, 0.3, 0, 3.14, 0], a=1.2, v=1.0)
    
    # 적절한 속도
    movel(p[0.6, 0.3, 0.3, 0, 3.14, 0], a=1.2, v=0.25, r=0.02)
    
    # 긴 거리, 높은 속도 (가능)
    movel(p[0.8, 0.5, 0.4, 0, 3.14, 0], a=1.2, v=0.8)
    
    # 홈 위치
    movej([0, -1.57, 1.57, 0, 1.57, 0], a=1.4, v=1.05)
end
    """
    
    analyzer = URScriptAnalyzer(test_script, "UR10e")
    print(analyzer.generate_report())
