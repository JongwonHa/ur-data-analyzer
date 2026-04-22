# src/urscript_analyzer.py
import re
import math
from typing import Dict, List, Tuple, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.robot_specs import ROBOT_SPECS, SAFETY_MARGINS


class URScriptAnalyzer:
    """URScript 파일 분석기 - 변수 파싱 및 거리 기반 정밀 분석 지원"""
    
    def __init__(self, script_content: str, robot_model: str = "UR10e"):
        self.script = script_content
        self.robot_model = robot_model
        self.specs = ROBOT_SPECS.get(robot_model, ROBOT_SPECS["UR10e"])
        self.margins = SAFETY_MARGINS
        self.waypoints = []
        self.variables = {}  # 변수 저장소
        
    def parse(self) -> List[Dict]:
        """URScript에서 웨이포인트(이동 명령어) 추출"""
        
        # 1단계: 변수 정의 파싱
        self._parse_variables()
        
        # 2단계: 이동 명령어 파싱
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
        
        # 거리 계산
        self._calculate_distances()
        
        return self.waypoints
    
    def _parse_variables(self):
        """스크립트에서 변수 정의 파싱"""
        self.variables = {}
        
        # 패턴 1: var_name = p[x, y, z, rx, ry, rz] (TCP 좌표)
        tcp_pattern = r'(\w+)\s*=\s*p\s*\[\s*([\d.,\s\-e]+)\s*\]'
        for match in re.finditer(tcp_pattern, self.script, re.IGNORECASE):
            var_name = match.group(1)
            try:
                values = [float(x.strip()) for x in match.group(2).split(',')]
                self.variables[var_name] = {
                    "type": "tcp",
                    "values": values
                }
            except:
                pass
        
        # 패턴 2: var_name = [q0, q1, q2, q3, q4, q5] (관절 각도)
        joint_pattern = r'(\w+)\s*=\s*\[\s*([\d.,\s\-e]+)\s*\]'
        for match in re.finditer(joint_pattern, self.script, re.IGNORECASE):
            var_name = match.group(1)
            # 이미 TCP로 파싱된 변수는 스킵
            if var_name in self.variables:
                continue
            try:
                values = [float(x.strip()) for x in match.group(2).split(',')]
                # 6개 값이면 관절 각도로 간주
                if len(values) == 6:
                    self.variables[var_name] = {
                        "type": "joint",
                        "values": values
                    }
            except:
                pass
        
        # 패턴 3: pose_trans, pose_add 등 함수 결과 (분석 어려움 - 표시만)
        pose_func_pattern = r'(\w+)\s*=\s*(pose_trans|pose_add|pose_inv)\s*\('
        for match in re.finditer(pose_func_pattern, self.script, re.IGNORECASE):
            var_name = match.group(1)
            if var_name not in self.variables:
                self.variables[var_name] = {
                    "type": "computed",
                    "values": None,
                    "note": f"{match.group(2)}() 함수 결과 - 런타임 계산"
                }
        
        # 패턴 4: get_actual_tcp_pose() 등 런타임 함수
        runtime_pattern = r'(\w+)\s*=\s*(get_actual_tcp_pose|get_actual_joint_positions|get_target_tcp_pose)\s*\(\s*\)'
        for match in re.finditer(runtime_pattern, self.script, re.IGNORECASE):
            var_name = match.group(1)
            if var_name not in self.variables:
                self.variables[var_name] = {
                    "type": "runtime",
                    "values": None,
                    "note": f"{match.group(2)}() - 런타임에 결정됨"
                }
    
    def _parse_params(self, param_str: str, move_type: str) -> Dict:
        """이동 명령어의 파라미터 파싱 (변수 지원)"""
        result = {
            "position": None,
            "position_values": None,
            "position_type": None,
            "position_source": None,  # "direct" 또는 "variable"
            "variable_name": None,
            "velocity": None,
            "acceleration": None,
            "blend_radius": None,
            "time": None
        }
        
        # URScript 기본값
        defaults = {
            "movej": {"a": 1.4, "v": 1.05},
            "movel": {"a": 1.2, "v": 0.25},
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
        
        # ========== 위치 데이터 추출 (변수 지원) ==========
        
        # 방법 1: 직접 TCP 좌표 p[x, y, z, rx, ry, rz]
        tcp_match = re.search(r'p\s*\[\s*([\d.,\s\-e]+)\s*\]', param_str)
        if tcp_match:
            result["position"] = f"p[{tcp_match.group(1)}]"
            result["position_type"] = "tcp"
            result["position_source"] = "direct"
            try:
                values = [float(x.strip()) for x in tcp_match.group(1).split(',')]
                result["position_values"] = values
            except:
                pass
        
        # 방법 2: 직접 관절 좌표 [q0, q1, ...]
        elif re.search(r'\[\s*([\d.,\s\-e]+)\s*\]', param_str):
            joint_match = re.search(r'\[\s*([\d.,\s\-e]+)\s*\]', param_str)
            if joint_match:
                result["position"] = f"[{joint_match.group(1)}]"
                result["position_type"] = "joint"
                result["position_source"] = "direct"
                try:
                    values = [float(x.strip()) for x in joint_match.group(1).split(',')]
                    result["position_values"] = values
                except:
                    pass
        
        # 방법 3: 변수 사용
        else:
            # 첫 번째 파라미터에서 변수명 추출
            # movej(var_name, a=1.2, v=0.5) 형식
            first_param_match = re.match(r'\s*([a-zA-Z_]\w*)', param_str)
            if first_param_match:
                var_name = first_param_match.group(1)
                
                # 예약어 제외
                reserved = ['a', 'v', 't', 'r', 'time', 'rad']
                if var_name.lower() not in reserved:
                    result["variable_name"] = var_name
                    result["position_source"] = "variable"
                    result["position"] = f"${var_name}"  # 변수 표시
                    
                    # 변수 테이블에서 값 조회
                    if var_name in self.variables:
                        var_info = self.variables[var_name]
                        result["position_type"] = var_info["type"]
                        result["position_values"] = var_info.get("values")
                        
                        if var_info["type"] == "tcp":
                            result["position"] = f"${var_name} → p[...]"
                        elif var_info["type"] == "joint":
                            result["position"] = f"${var_name} → [...]"
                        elif var_info["type"] in ["computed", "runtime"]:
                            result["position"] = f"${var_name} ({var_info.get('note', '런타임 계산')})"
                    else:
                        result["position"] = f"${var_name} (정의를 찾을 수 없음)"
                        result["position_type"] = "unknown"
        
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
            wp["distance_note"] = None
            
            if i == 0:
                wp["distance_note"] = "시작점"
                continue
            
            prev_wp = self.waypoints[i - 1]
            
            # 위치 값이 있는 경우만 거리 계산
            curr_values = wp.get("position_values")
            prev_values = prev_wp.get("position_values")
            curr_type = wp.get("position_type")
            prev_type = prev_wp.get("position_type")
            
            if curr_values and prev_values and curr_type == prev_type:
                if curr_type == "tcp" and len(curr_values) >= 3 and len(prev_values) >= 3:
                    # TCP 좌표: 유클리드 거리
                    distance = math.sqrt(
                        (curr_values[0] - prev_values[0])**2 +
                        (curr_values[1] - prev_values[1])**2 +
                        (curr_values[2] - prev_values[2])**2
                    )
                    wp["distance"] = round(distance, 4)
                    wp["distance_unit"] = "m"
                    
                elif curr_type == "joint" and len(curr_values) >= 6 and len(prev_values) >= 6:
                    # 관절 좌표: 최대 관절 변화량
                    joint_diffs = [abs(curr_values[j] - prev_values[j]) for j in range(6)]
                    wp["distance"] = round(max(joint_diffs), 4)
                    wp["distance_unit"] = "rad"
                    wp["joint_distances"] = [round(d, 4) for d in joint_diffs]
            else:
                # 거리 계산 불가 사유
                if wp.get("position_source") == "variable":
                    if wp.get("position_type") == "unknown":
                        wp["distance_note"] = f"변수 '{wp.get('variable_name')}' 정의 없음"
                    elif wp.get("position_type") in ["computed", "runtime"]:
                        wp["distance_note"] = "런타임 계산 위치"
                    elif not curr_values:
                        wp["distance_note"] = "변수값 파싱 실패"
                elif prev_wp.get("position_source") == "variable" and not prev_values:
                    wp["distance_note"] = "이전 위치 불명"
                elif curr_type != prev_type:
                    wp["distance_note"] = "좌표 타입 불일치"
                else:
                    wp["distance_note"] = "위치 정보 없음"
    
    def _calculate_motion_profile(self, distance: float, target_velocity: float,
                                   acceleration: float) -> Dict:
        """모션 프로파일 상세 분석"""
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
        
        # 목표 속도 도달을 위한 최소 거리
        d_min_for_target = (target_velocity ** 2) / acceleration
        
        if distance >= d_min_for_target:
            # 사다리꼴 프로파일
            profile_type = "trapezoidal"
            reachable_velocity = target_velocity
            
            t_acc = target_velocity / acceleration
            s_acc = (target_velocity ** 2) / (2 * acceleration)
            s_const = distance - (2 * s_acc)
            t_const = s_const / target_velocity
            estimated_time = 2 * t_acc + t_const
            efficiency = 100.0
        else:
            # 삼각형 프로파일
            profile_type = "triangle"
            reachable_velocity = v_triangle_peak
            estimated_time = 2 * math.sqrt(distance / acceleration)
            efficiency = (reachable_velocity / target_velocity) * 100
        
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
            "variables_found": len(self.variables),
            "variables": {k: v["type"] for k, v in self.variables.items()},
            "summary": {
                "total_waypoints": len(self.waypoints),
                "movej_count": sum(1 for w in self.waypoints if w["type"] == "movej"),
                "movel_count": sum(1 for w in self.waypoints if w["type"] == "movel"),
                "movep_count": sum(1 for w in self.waypoints if w["type"] == "movep"),
                "movec_count": sum(1 for w in self.waypoints if w["type"] == "movec"),
                "other_count": sum(1 for w in self.waypoints if w["type"] not in ["movej", "movel", "movep", "movec"]),
                "direct_position_count": sum(1 for w in self.waypoints if w.get("position_source") == "direct"),
                "variable_position_count": sum(1 for w in self.waypoints if w.get("position_source") == "variable"),
                "distance_calculated_count": sum(1 for w in self.waypoints if w.get("distance") is not None),
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
        
        results["recommendations"] = self._generate_recommendations(results)
        
        return results
    
    def _analyze_waypoint(self, wp: Dict) -> Dict:
        """개별 웨이포인트 분석"""
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
            "position_source": wp.get("position_source"),
            "variable_name": wp.get("variable_name"),
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
            max_v = max_v_deg * (math.pi / 180)
            max_a = self.specs["max_joint_accel"] * (math.pi / 180)
        else:
            max_v = self.specs["max_tcp_speed"]
            max_a = 1.5
        
        recommended_v = max_v * self.margins["speed"]
        recommended_a = max_a * self.margins["accel"]
        
        analysis["max_velocity"] = round(max_v, 4)
        analysis["recommended_velocity"] = round(recommended_v, 4)
        analysis["max_acceleration"] = round(max_a, 4)
        analysis["recommended_acceleration"] = round(recommended_a, 4)
        
        # 속도 체크
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
        
        # 거리 기반 분석
        if wp.get("distance") and wp["velocity"] and wp["acceleration"]:
            motion_profile = self._calculate_motion_profile(
                wp["distance"], 
                wp["velocity"], 
                wp["acceleration"]
            )
            analysis["motion_profile"] = motion_profile
            
            if motion_profile["efficiency"] and motion_profile["efficiency"] < 80:
                if analysis["status"] == "정상":
                    analysis["status"] = "비효율"
                
                analysis["issues"].append({
                    "waypoint_id": wp["id"],
                    "line": wp["line"],
                    "severity": "주의",
                    "category": "효율성",
                    "message": f"Line {wp['line']}: 거리 {wp['distance']}{wp.get('distance_unit', 'm')}에서 "
                              f"설정 속도의 {motion_profile['efficiency']}%만 도달 가능",
                    "current": wp["velocity"],
                    "reachable": motion_profile["reachable_velocity"],
                    "optimal": motion_profile["optimal_velocity"],
                    "efficiency": motion_profile["efficiency"],
                    "profile_type": motion_profile["profile_type"]
                })
            
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
        
        # 효율성 이슈
        efficiency_issues = [i for i in results["issues"] if i["category"] == "효율성"]
        if efficiency_issues:
            recommendations.append({
                "priority": "중간",
                "category": "속도 효율성 (거리 기반)",
                "issue_count": len(efficiency_issues),
                "message": f"{len(efficiency_issues)}개 웨이포인트에서 설정 속도에 도달하지 못합니다.",
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
        
        # 변수 사용으로 인한 분석 제한 알림
        variable_count = results["summary"]["variable_position_count"]
        distance_calc_count = results["summary"]["distance_calculated_count"]
        
        if variable_count > 0 and distance_calc_count < results["summary"]["total_waypoints"] - 1:
            uncalculated = results["summary"]["total_waypoints"] - 1 - distance_calc_count
            recommendations.append({
                "priority": "낮음",
                "category": "분석 제한 (변수 사용)",
                "issue_count": uncalculated,
                "message": f"{uncalculated}개 웨이포인트의 거리를 계산할 수 없습니다. "
                          f"(변수 사용 또는 런타임 계산 위치)",
                "action": "정확한 거리 기반 분석을 위해 위치를 직접 좌표로 입력하거나, "
                         "변수 정의를 스크립트에 포함해주세요.",
                "affected_lines": [w["line"] for w in results["waypoints"] 
                                  if w.get("distance") is None and w["id"] > 1]
            })
        
        # 블렌드 반경
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
        lines.append("=" * 75)
        lines.append("      URScript 웨이포인트 분석 리포트 (변수 파싱 + 거리 기반 분석)")
        lines.append("=" * 75)
        lines.append(f"\n🤖 로봇 모델: {self.robot_model}")
        lines.append(f"📊 총 웨이포인트: {results['summary']['total_waypoints']}개")
        lines.append(f"   ├─ movej: {results['summary']['movej_count']}개")
        lines.append(f"   ├─ movel: {results['summary']['movel_count']}개")
        lines.append(f"   └─ 기타: {results['summary']['other_count']}개")
        
        lines.append(f"\n📍 위치 지정 방식:")
        lines.append(f"   ├─ 직접 좌표: {results['summary']['direct_position_count']}개")
        lines.append(f"   └─ 변수 사용: {results['summary']['variable_position_count']}개")
        
        if results["variables_found"] > 0:
            lines.append(f"\n📦 발견된 변수: {results['variables_found']}개")
            for var_name, var_type in results["variables"].items():
                lines.append(f"   - {var_name}: {var_type}")
        
        lines.append(f"\n📏 거리 계산: {results['summary']['distance_calculated_count']}/"
                    f"{results['summary']['total_waypoints']-1}개 성공")
        lines.append(f"📏 총 이동 거리: {results['summary']['total_distance']} m")
        lines.append(f"⏱️ 예상 총 시간: {results['summary']['estimated_total_time']} s")
        
        lines.append(f"\n⚠️ 발견된 이슈: {results['summary']['issues_count']}개")
        lines.append(f"   ├─ 경고: {results['summary']['warning_count']}개")
        lines.append(f"   ├─ 주의: {results['summary']['caution_count']}개")
        lines.append(f"   └─ 비효율: {results['summary']['inefficient_count']}개")
        
        # 웨이포인트 테이블
        lines.append(f"\n{'─' * 75}")
        lines.append("【 📍 웨이포인트 분석 결과 】")
        lines.append(f"{'─' * 75}")
        
        header = f"{'ID':<3} {'Line':<5} {'Type':<6} {'위치소스':<10} {'거리':<12} {'설정속도':<10} {'도달가능':<10} {'효율':<8} {'상태':<6}"
        lines.append(header)
        lines.append("-" * 75)
        
        for wp in results["waypoints"]:
            status_icon = {"정상": "✅", "주의": "⚠️", "경고": "🔴", "비효율": "📉"}.get(wp["status"], "")
            
            # 위치 소스
            if wp.get("position_source") == "variable":
                src = f"${wp.get('variable_name', '?')}"
            else:
                src = "직접입력"
            
            # 거리
            if wp.get("distance"):
                dist = f"{wp['distance']}{wp.get('distance_unit', '')}"
            elif wp.get("distance_note"):
                dist = f"({wp['distance_note'][:8]})"
            else:
                dist = "-"
            
            # 도달 가능 속도
            reachable = wp.get('reachable_velocity') or wp.get('motion_profile', {}).get('reachable_velocity')
            reach_str = f"{reachable}" if reachable else "-"
            
            # 효율
            eff = wp.get('motion_profile', {}).get('efficiency')
            eff_str = f"{eff}%" if eff else "-"
            
            lines.append(f"{wp['id']:<3} {wp['line']:<5} {wp['type']:<6} {src:<10} {dist:<12} {wp['velocity']:<10} {reach_str:<10} {eff_str:<8} {status_icon}")
        
        # 이슈 상세
        if results["issues"]:
            lines.append(f"\n{'─' * 75}")
            lines.append("【 ⚠️ 발견된 이슈 상세 】")
            lines.append(f"{'─' * 75}")
            
            for issue in results["issues"]:
                icon = "🔴" if issue["severity"] == "경고" else "⚠️" if issue["severity"] == "주의" else "📉"
                lines.append(f"\n{icon} [{issue['severity']}] {issue['message']}")
                
                if issue["category"] == "효율성":
                    lines.append(f"   설정: {issue['current']} → 실제: {issue['reachable']} → 최적: {issue['optimal']}")
                else:
                    lines.append(f"   현재: {issue['current']} → 권장: {issue['recommended']}")
        
        # 권장사항
        lines.append(f"\n{'=' * 75}")
        lines.append("【 💡 권장사항 】")
        lines.append(f"{'=' * 75}")
        
        if results["recommendations"]:
            for rec in results["recommendations"]:
                icon = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(rec["priority"], "")
                lines.append(f"\n{icon} [{rec['priority']}] {rec['category']}")
                lines.append(f"   {rec['message']}")
                lines.append(f"   → {rec['action']}")
        else:
            lines.append("\n✅ 모든 웨이포인트가 적정 범위 내에 있습니다!")
        
        lines.append(f"\n{'=' * 75}")
        
        return "\n".join(lines)


# 테스트
if __name__ == "__main__":
    test_script = """
# 변수 정의
home_pos = p[0.3, 0.1, 0.4, 0, 3.14, 0]
work_pos_1 = p[0.5, 0.2, 0.3, 0, 3.14, 0]
work_pos_2 = p[0.52, 0.21, 0.3, 0, 3.14, 0]
work_pos_3 = p[0.6, 0.3, 0.3, 0, 3.14, 0]
joint_home = [0, -1.57, 1.57, 0, 1.57, 0]

# 런타임 변수
current_pos = get_actual_tcp_pose()

def main_program():
    # 홈 위치로 이동 (변수 사용)
    movej(joint_home, a=1.4, v=1.05)
    
    # 작업 시작점 (변수 사용)
    movel(home_pos, a=1.2, v=0.5)
    
    # 작업 위치 1 (변수 사용)
    movel(work_pos_1, a=1.2, v=0.5)
    
    # 작업 위치 2 - 짧은 거리, 높은 속도 (비효율!)
    movel(work_pos_2, a=1.2, v=1.0)
    
    # 작업 위치 3 (변수 사용)
    movel(work_pos_3, a=1.2, v=0.25, r=0.02)
    
    # 직접 좌표 입력
    movel(p[0.8, 0.5, 0.4, 0, 3.14, 0], a=1.2, v=0.5)
    
    # 런타임 위치로 이동 (분석 불가)
    movel(current_pos, a=1.2, v=0.25)
    
    # 홈 복귀
    movej(joint_home, a=1.4, v=1.05)
end
    """
    
    analyzer = URScriptAnalyzer(test_script, "UR10e")
    print(analyzer.generate_report())
