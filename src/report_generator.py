# src/report_generator.py
from datetime import datetime
from typing import Dict
import json


class URReportGenerator:
    """분석 결과 리포트 생성기"""
    
    def __init__(self, analysis_results: Dict):
        self.results = analysis_results
        self.report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.robot_model = analysis_results.get("robot_model", "Unknown")
        
    def generate_text_report(self) -> str:
        """텍스트 형식 리포트 생성"""
        lines = []
        
        # 헤더
        lines.append("=" * 70)
        lines.append("        유니버설로봇 (UR) Realtime Data 분석 리포트")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"📅 분석 일시: {self.report_date}")
        lines.append(f"🤖 로봇 모델: {self.robot_model}")
        
        # 데이터 요약
        summary = self.results.get("data_summary", {})
        lines.append(f"📊 총 샘플 수: {summary.get('total_samples', 'N/A')}")
        lines.append(f"⏱️ 기록 시간: {summary.get('duration_seconds', 'N/A')} 초")
        
        # 전체 상태
        lines.append("")
        lines.append("-" * 70)
        overall = self._get_overall_status()
        lines.append(f"📋 전체 상태: {overall}")
        lines.append("-" * 70)
        
        # 속도 분석
        lines.append("")
        lines.append("【 🚀 속도 분석 】")
        lines.append("-" * 50)
        speed = self.results.get("speed_analysis", {})
        
        if speed.get("tcp_speed"):
            tcp = speed["tcp_speed"]
            lines.append(f"  TCP 속도:")
            lines.append(f"    - 현재 최대: {tcp.get('current_max', 'N/A')} m/s")
            lines.append(f"    - 권장 최대: {tcp.get('recommended', 'N/A')} m/s")
            lines.append(f"    - 사용률: {tcp.get('utilization', 'N/A')}%")
            lines.append(f"    - 상태: {tcp.get('status', 'N/A')}")
        
        lines.append("")
        lines.append("  관절별 속도 (°/s):")
        lines.append(f"  {'관절':<10} {'현재최대':>10} {'권장최대':>10} {'사용률':>10} {'상태':>8}")
        lines.append("  " + "-" * 48)
        
        for joint, data in speed.get("joint_speed", {}).items():
            lines.append(f"  {joint:<10} {data['current_max']:>10.1f} {data['recommended']:>10.1f} {data['utilization']:>9.1f}% {data['status']:>8}")
        
        # 가속도 분석
        lines.append("")
        lines.append("【 ⚡ 가속도 분석 】")
        lines.append("-" * 50)
        accel = self.results.get("acceleration_analysis", {})
        
        lines.append(f"  {'관절':<10} {'현재최대':>10} {'권장최대':>10} {'사용률':>10} {'상태':>8}")
        lines.append("  " + "-" * 48)
        
        for joint, data in accel.get("joint_acceleration", {}).items():
            lines.append(f"  {joint:<10} {data['current_max']:>10.1f} {data['recommended']:>10.1f} {data['utilization']:>9.1f}% {data['status']:>8}")
        
        # 부하 분석
        lines.append("")
        lines.append("【 🔋 부하(전류) 분석 】")
        lines.append("-" * 50)
        load = self.results.get("load_analysis", {})
        
        lines.append(f"  평균 부하율: {load.get('total_load_ratio', 'N/A')}%")
        lines.append(f"  피크 부하율: {load.get('peak_load_ratio', 'N/A')}%")
        lines.append("")
        lines.append(f"  {'관절':<10} {'현재최대(A)':>12} {'정격(A)':>10} {'사용률':>10} {'상태':>8}")
        lines.append("  " + "-" * 50)
        
        for joint, data in load.get("joint_current", {}).items():
            lines.append(f"  {joint:<10} {data['current_max']:>12.3f} {data['nominal']:>10.2f} {data['utilization']:>9.1f}% {data['status']:>8}")
        
        # 온도 분석
        lines.append("")
        lines.append("【 🌡️ 온도 분석 】")
        lines.append("-" * 50)
        temp = self.results.get("temperature_analysis", {})
        
        lines.append(f"  최대 온도: {temp.get('max_temp', 'N/A')}°C")
        lines.append(f"  평균 온도: {temp.get('avg_temp', 'N/A')}°C")
        
        if temp.get("joint_temperatures"):
            lines.append("")
            lines.append(f"  {'관절':<10} {'현재최대':>10} {'권장최대':>10} {'상태':>8}")
            lines.append("  " + "-" * 40)
            
            for joint, data in temp.get("joint_temperatures", {}).items():
                lines.append(f"  {joint:<10} {data['current_max']:>9.1f}°C {data['recommended_max']:>9.1f}°C {data['status']:>8}")
        
        # 효율성 분석
        lines.append("")
        lines.append("【 📈 효율성 분석 】")
        lines.append("-" * 50)
        eff = self.results.get("efficiency_analysis", {})
        
        lines.append(f"  모션 효율: {eff.get('motion_efficiency', 'N/A')}%")
        lines.append(f"  유휴 시간 비율: {eff.get('idle_time_ratio', 'N/A')}%")
        lines.append(f"  부드러운 모션 점수: {eff.get('smooth_motion_score', 'N/A')}/100")
        
        # 권장사항
        lines.append("")
        lines.append("=" * 70)
        lines.append("【 💡 권장사항 】")
        lines.append("=" * 70)
        
        recommendations = self.results.get("recommendations", [])
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                priority_icon = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(rec["priority"], "⚪")
                lines.append("")
                lines.append(f"{i}. {priority_icon} [{rec['priority']}] {rec['category']} - {rec['target']}")
                lines.append(f"   📌 문제: {rec['issue']}")
                lines.append(f"   📍 현재값: {rec['current_value']}")
                lines.append(f"   ✅ 권장값: {rec['recommended_value']}")
                lines.append(f"   💬 권장 조치: {rec['recommendation']}")
                lines.append(f"   🎯 기대 효과: {rec['benefit']}")
        else:
            lines.append("")
            lines.append("  ✅ 모든 항목이 정상 범위입니다!")
            lines.append("  현재 설정을 유지하시면 됩니다.")
        
        # 푸터
        lines.append("")
        lines.append("=" * 70)
        lines.append("                    [ 리포트 끝 ]")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def _get_overall_status(self) -> str:
        """전체 상태 계산"""
        recommendations = self.results.get("recommendations", [])
        high_count = sum(1 for r in recommendations if r.get("priority") == "높음")
        medium_count = sum(1 for r in recommendations if r.get("priority") == "중간")
        
        if high_count >= 2:
            return "⚠️ 주의 필요 (긴급 점검 권장)"
        elif high_count == 1:
            return "⚠️ 주의 필요"
        elif medium_count >= 2:
            return "📝 양호 (일부 개선 권장)"
        elif medium_count == 1 or len(recommendations) > 0:
            return "📝 양호 (경미한 개선 가능)"
        else:
            return "✅ 우수 (최적 상태)"
    
    def generate_json_report(self) -> str:
        """JSON 형식 리포트"""
        report_data = {
            "report_info": {
                "generated_at": self.report_date,
                "robot_model": self.robot_model,
                "overall_status": self._get_overall_status()
            },
            "analysis_results": self.results
        }
        return json.dumps(report_data, indent=2, ensure_ascii=False)
    
    def get_summary_metrics(self) -> Dict:
        """대시보드용 요약 메트릭"""
        speed = self.results.get("speed_analysis", {})
        load = self.results.get("load_analysis", {})
        eff = self.results.get("efficiency_analysis", {})
        
        return {
            "overall_status": self._get_overall_status(),
            "speed_utilization": speed.get("tcp_speed", {}).get("utilization", 0),
            "load_ratio": load.get("total_load_ratio", 0),
            "peak_load": load.get("peak_load_ratio", 0),
            "motion_efficiency": eff.get("motion_efficiency", 0),
            "issues_count": len(self.results.get("recommendations", [])),
            "high_priority_issues": sum(1 for r in self.results.get("recommendations", []) 
                                        if r.get("priority") == "높음")
        }
