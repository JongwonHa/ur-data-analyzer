# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import json
import sys
import os

# 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analyzer import URDataAnalyzer
from src.report_generator import URReportGenerator
from src.urscript_analyzer import URScriptAnalyzer
from config.robot_specs import ROBOT_SPECS

# 페이지 설정
st.set_page_config(
    page_title="UR 로봇 분석 AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 제목
st.title("🤖 유니버설로봇 분석 AI Agent")
st.markdown("**Realtime Data 분석** & **URScript 웨이포인트 검토** 도구")
st.markdown("---")

# ============ 사이드바 ============
with st.sidebar:
    st.header("⚙️ 설정")
    
    # 로봇 모델 선택
    robot_model = st.selectbox(
        "🤖 로봇 모델 선택",
        options=list(ROBOT_SPECS.keys()),
        index=2,
        help="분석할 UR 로봇 모델을 선택하세요"
    )
    
    st.markdown("---")
    
    # 선택된 모델 스펙 표시
    st.subheader(f"📋 {robot_model} 사양")
    specs = ROBOT_SPECS[robot_model]
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("최대 페이로드", f"{specs['max_payload']} kg")
        st.metric("최대 TCP 속도", f"{specs['max_tcp_speed']} m/s")
    with col2:
        st.metric("도달 거리", f"{specs['max_reach']} mm")
        st.metric("최대 온도", f"{specs['max_temp']}°C")
    
    st.markdown("---")
    st.markdown("### 📖 사용 가이드")
    st.markdown("""
    1. **로봇 모델** 선택
    2. **탭 선택**:
       - Realtime Data: 실시간 데이터 분석
       - URScript: 프로그램 파일 검토
    3. **파일 업로드** 또는 코드 입력
    4. **분석 시작** 클릭
    """)


# ============ 메인 탭 ============
main_tab1, main_tab2 = st.tabs(["📊 Realtime Data 분석", "📝 URScript 분석"])


# ============================================================
# 탭 1: Realtime Data 분석
# ============================================================
with main_tab1:
    st.header("📊 Realtime Data 분석")
    st.markdown("UR 로봇의 RTDE 데이터를 분석하여 **속도, 가속도, 부하, 온도** 등을 점검합니다.")
    
    uploaded_file = st.file_uploader(
        "UR Realtime Data 파일을 업로드하세요 (Excel 또는 CSV)",
        type=['xlsx', 'xls', 'csv'],
        help="RTDE에서 추출한 엑셀 또는 CSV 파일",
        key="realtime_uploader"
    )
    
    # 세션 스테이트 초기화
    if 'rt_analyzed' not in st.session_state:
        st.session_state.rt_analyzed = False
    if 'rt_results' not in st.session_state:
        st.session_state.rt_results = None
    if 'rt_summary' not in st.session_state:
        st.session_state.rt_summary = None
    if 'rt_report_gen' not in st.session_state:
        st.session_state.rt_report_gen = None
    
    if uploaded_file is not None:
        try:
            with st.spinner("📊 데이터 로딩 중..."):
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ 데이터 로드 완료! **{len(df):,}** 행, **{len(df.columns)}** 열")
            
            # 데이터 미리보기
            with st.expander("📋 데이터 미리보기 (상위 100행)", expanded=False):
                st.dataframe(df.head(100), use_container_width=True)
            
            with st.expander("📊 컬럼 목록", expanded=False):
                cols = df.columns.tolist()
                col_df = pd.DataFrame({
                    "컬럼명": cols,
                    "데이터 타입": [str(df[c].dtype) for c in cols],
                    "샘플 값": [str(df[c].iloc[0]) if len(df) > 0 else "N/A" for c in cols]
                })
                st.dataframe(col_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # 분석 버튼
            if st.button("🔍 Realtime Data 분석 시작", type="primary", use_container_width=True, key="analyze_realtime"):
                with st.spinner("🔄 분석 중... 잠시만 기다려주세요"):
                    analyzer = URDataAnalyzer(df, robot_model)
                    results = analyzer.analyze_all()
                    report_gen = URReportGenerator(results)
                    summary = report_gen.get_summary_metrics()
                
                st.success("✅ 분석 완료!")
                st.balloons()
                
                # 세션에 저장
                st.session_state.rt_results = results
                st.session_state.rt_summary = summary
                st.session_state.rt_report_gen = report_gen
                st.session_state.rt_analyzed = True
                
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
            st.info("데이터 형식을 확인해주세요.")
    
    # 분석 결과 표시
    if st.session_state.rt_analyzed and st.session_state.rt_results is not None:
        results = st.session_state.rt_results
        summary = st.session_state.rt_summary
        report_gen = st.session_state.rt_report_gen
        
        st.markdown("---")
        st.subheader("📈 분석 결과")
        
        # 요약 메트릭
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("전체 상태", summary.get('overall_status', 'N/A').split()[0])
        with col2:
            st.metric("속도 사용률", f"{summary.get('speed_utilization', 0)}%")
        with col3:
            st.metric("평균 부하율", f"{summary.get('load_ratio', 0)}%")
        with col4:
            st.metric("모션 효율", f"{summary.get('motion_efficiency', 0)}%")
        with col5:
            st.metric("발견 이슈", f"{summary.get('issues_count', 0)}건")
        
        st.markdown("---")
        
        # 상세 탭
        detail_tab1, detail_tab2, detail_tab3, detail_tab4, detail_tab5 = st.tabs([
            "🚀 속도 분석", 
            "⚡ 가속도/부하", 
            "🌡️ 온도", 
            "💡 권장사항", 
            "📄 전체 리포트"
        ])
        
        # 속도 분석 탭
        with detail_tab1:
            st.subheader("🚀 속도 분석 결과")
            speed_data = results.get("speed_analysis", {})
            
            # TCP 속도
            if speed_data.get("tcp_speed"):
                tcp = speed_data["tcp_speed"]
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("현재 최대 TCP 속도", f"{tcp.get('current_max', 'N/A')} m/s")
                with col2:
                    st.metric("권장 최대 TCP 속도", f"{tcp.get('recommended', 'N/A')} m/s")
                with col3:
                    status_color = "🟢" if tcp.get('status') == "정상" else "🟡" if tcp.get('status') == "주의" else "🔴"
                    st.metric("상태", f"{status_color} {tcp.get('status', 'N/A')}")
            
            # 관절별 속도 차트
            if speed_data.get("joint_speed"):
                st.markdown("#### 관절별 속도 비교")
                joints = list(speed_data["joint_speed"].keys())
                current_vals = [speed_data["joint_speed"][j]["current_max"] for j in joints]
                recommended_vals = [speed_data["joint_speed"][j]["recommended"] for j in joints]
                max_vals = [speed_data["joint_speed"][j]["max_allowed"] for j in joints]
                
                fig = go.Figure()
                fig.add_trace(go.Bar(name='현재 최대', x=joints, y=current_vals, marker_color='steelblue'))
                fig.add_trace(go.Bar(name='권장 최대', x=joints, y=recommended_vals, marker_color='lightgreen'))
                fig.add_trace(go.Scatter(name='허용 최대', x=joints, y=max_vals, mode='lines+markers', 
                                         line=dict(color='red', dash='dash')))
                fig.update_layout(barmode='group', title='관절별 속도 비교 (°/s)', height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # 테이블
                speed_df = pd.DataFrame([
                    {
                        "관절": joint,
                        "현재 최대 (°/s)": data["current_max"],
                        "평균 (°/s)": data["current_avg"],
                        "권장 최대 (°/s)": data["recommended"],
                        "사용률 (%)": data["utilization"],
                        "상태": data["status"]
                    }
                    for joint, data in speed_data["joint_speed"].items()
                ])
                st.dataframe(speed_df, use_container_width=True, hide_index=True)
        
        # 가속도/부하 탭
        with detail_tab2:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("⚡ 가속도 분석")
                accel_data = results.get("acceleration_analysis", {})
                
                if accel_data.get("joint_acceleration"):
                    joints = list(accel_data["joint_acceleration"].keys())
                    current_vals = [accel_data["joint_acceleration"][j]["current_max"] for j in joints]
                    recommended_vals = [accel_data["joint_acceleration"][j]["recommended"] for j in joints]
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='현재 최대', x=joints, y=current_vals, marker_color='coral'))
                    fig.add_trace(go.Bar(name='권장 최대', x=joints, y=recommended_vals, marker_color='lightblue'))
                    fig.update_layout(barmode='group', title='관절별 가속도 (°/s²)', height=350)
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("🔋 부하(전류) 분석")
                load_data = results.get("load_analysis", {})
                
                st.metric("평균 부하율", f"{load_data.get('total_load_ratio', 0)}%")
                st.metric("피크 부하율", f"{load_data.get('peak_load_ratio', 0)}%")
                
                if load_data.get("joint_current"):
                    joints = list(load_data["joint_current"].keys())
                    utilizations = [load_data["joint_current"][j]["utilization"] for j in joints]
                    
                    fig = px.bar(
                        x=joints, y=utilizations,
                        title='관절별 전류 사용률 (%)',
                        color=utilizations,
                        color_continuous_scale=['green', 'yellow', 'red']
                    )
                    fig.add_hline(y=75, line_dash="dash", line_color="orange", 
                                 annotation_text="권장 한계 (75%)")
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
        
        # 온도 탭
        with detail_tab3:
            st.subheader("🌡️ 온도 분석")
            temp_data = results.get("temperature_analysis", {})
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("최대 온도", f"{temp_data.get('max_temp', 'N/A')}°C")
            with col2:
                st.metric("평균 온도", f"{temp_data.get('avg_temp', 'N/A')}°C")
            
            if temp_data.get("joint_temperatures"):
                joints = list(temp_data["joint_temperatures"].keys())
                temps = [temp_data["joint_temperatures"][j]["current_max"] for j in joints]
                recommended = [temp_data["joint_temperatures"][j]["recommended_max"] for j in joints]
                
                fig = go.Figure()
                fig.add_trace(go.Bar(name='현재 온도', x=joints, y=temps, marker_color='tomato'))
                fig.add_trace(go.Scatter(name='권장 최대', x=joints, y=recommended, mode='lines+markers',
                                         line=dict(color='green', dash='dash')))
                fig.update_layout(title='관절별 온도 (°C)', height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        # 권장사항 탭
        with detail_tab4:
            st.subheader("💡 권장사항")
            recommendations = results.get("recommendations", [])
            
            if recommendations:
                for rec in recommendations:
                    priority_emoji = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(rec["priority"], "⚪")
                    
                    with st.expander(f"{priority_emoji} **[{rec['priority']}]** {rec['category']} - {rec['target']}", 
                                    expanded=(rec["priority"] == "높음")):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**📌 문제점:**")
                            st.write(rec['issue'])
                            st.markdown(f"**📍 현재 값:** `{rec.get('current_value', 'N/A')}`")
                        with col2:
                            st.markdown(f"**✅ 권장 값:** `{rec.get('recommended_value', 'N/A')}`")
                            st.markdown(f"**💬 권장 조치:**")
                            st.info(rec['recommendation'])
                        st.markdown(f"**🎯 기대 효과:** {rec.get('benefit', 'N/A')}")
            else:
                st.success("✅ 모든 항목이 정상 범위입니다! 특별한 권장사항이 없습니다.")
        
        # 전체 리포트 탭
        with detail_tab5:
            st.subheader("📄 전체 리포트")
            text_report = report_gen.generate_text_report()
            st.text_area("리포트 내용", text_report, height=500)
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 텍스트 리포트 다운로드",
                    data=text_report,
                    file_name=f"UR_{robot_model}_Realtime_분석리포트.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with col2:
                json_report = report_gen.generate_json_report()
                st.download_button(
                    label="📥 JSON 리포트 다운로드",
                    data=json_report,
                    file_name=f"UR_{robot_model}_Realtime_분석리포트.json",
                    mime="application/json",
                    use_container_width=True
                )
    
    else:
        if uploaded_file is None:
            st.info("👆 위에서 UR Realtime Data 파일을 업로드해주세요.")


# ============================================================
# 탭 2: URScript 분석
# ============================================================
with main_tab2:
    st.header("📝 URScript 분석 (거리 기반 정밀 분석)")
    st.markdown("""
    URScript 파일의 **웨이포인트별 속도/가속도**를 검토합니다.
    - ✅ 로봇 스펙 기준 속도/가속도 한계 체크
    - ✅ **거리 기반 분석**: 짧은 거리에서 실제 도달 가능한 속도 계산
    - ✅ 최적 속도 제안
    """)
    
    st.markdown("---")
    
    # 입력 방식 선택
    input_method = st.radio(
        "입력 방식 선택",
        ["📂 파일 업로드", "✏️ 직접 입력"],
        horizontal=True,
        key="script_input_method"
    )
    
    script_content = None
    
    if input_method == "📂 파일 업로드":
        uploaded_script = st.file_uploader(
            "URScript 파일 업로드 (.script, .urscript, .txt)",
            type=['script', 'urscript', 'txt'],
            key="script_uploader",
            help="UR 로봇 프로그램 파일 또는 스크립트 파일"
        )
        
        if uploaded_script:
            try:
                script_content = uploaded_script.read().decode('utf-8')
                st.success(f"✅ 파일 로드 완료: **{uploaded_script.name}**")
            except Exception as e:
                st.error(f"파일을 읽을 수 없습니다: {str(e)}")
                st.info("UTF-8 인코딩 파일인지 확인하세요.")
    
    else:
        st.markdown("**URScript 코드를 아래에 붙여넣으세요:**")
        script_content = st.text_area(
            "URScript 코드",
            height=300,
            placeholder="""예시:
def main():
    movej([0.1, -1.5, 1.2, 0, 1.57, 0], a=1.4, v=1.05)
    movel(p[0.5, 0.2, 0.3, 0, 3.14, 0], a=1.2, v=0.25)
    movel(p[0.55, 0.22, 0.3, 0, 3.14, 0], a=1.2, v=0.5)
end""",
            key="script_text_input"
        )
    
    # 스크립트 미리보기
    if script_content:
        with st.expander("📄 스크립트 내용 미리보기", expanded=False):
            st.code(script_content, language="python")
        
        st.markdown("---")
        
        # 분석 버튼
        if st.button("🔍 URScript 분석 시작", type="primary", use_container_width=True, key="analyze_script"):
            with st.spinner("🔄 분석 중..."):
                try:
                    script_analyzer = URScriptAnalyzer(script_content, robot_model)
                    script_results = script_analyzer.analyze()
                    
                    st.success("✅ 분석 완료!")
                    
                    # ========== 요약 ==========
                    st.markdown("---")
                    st.subheader("📊 분석 요약")
                    
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    with col1:
                        st.metric("총 웨이포인트", script_results["summary"]["total_waypoints"])
                    with col2:
                        st.metric("movej", script_results["summary"]["movej_count"])
                    with col3:
                        st.metric("movel", script_results["summary"]["movel_count"])
                    with col4:
                        st.metric("발견된 이슈", script_results["summary"]["issues_count"])
                    with col5:
                        st.metric("총 거리", f"{script_results['summary']['total_distance']} m")
                    with col6:
                        st.metric("예상 시간", f"{script_results['summary']['estimated_total_time']} s")
                    
                    # 상태 표시
                    if script_results["summary"]["issues_count"] == 0:
                        st.success("✅ 모든 웨이포인트가 적정 범위 내에 있습니다!")
                    elif script_results["summary"]["warning_count"] > 0:
                        st.error(f"🔴 {script_results['summary']['warning_count']}개의 경고가 있습니다. 즉시 수정이 필요합니다.")
                    else:
                        st.warning(f"⚠️ {script_results['summary']['caution_count'] + script_results['summary']['inefficient_count']}개의 주의/비효율 항목이 있습니다.")
                    
                    # ========== 웨이포인트 테이블 ==========
                    st.markdown("---")
                    st.subheader("📍 웨이포인트 분석 결과")
                    
                    # DataFrame 생성
                    wp_data = []
                    for wp in script_results["waypoints"]:
                        status_icon = {"정상": "✅", "주의": "⚠️", "경고": "🔴", "비효율": "📉"}.get(wp["status"], "")
                        
                        # 거리
                        dist_str = f"{wp['distance']} {wp.get('distance_unit', '')}" if wp.get('distance') else wp.get('distance_note', '-')
                        
                        # 도달 가능 속도
                        reachable = wp.get('reachable_velocity') or wp.get('motion_profile', {}).get('reachable_velocity')
                        reachable_str = f"{reachable}" if reachable else "-"
                        
                        # 효율
                        eff = wp.get('motion_profile', {}).get('efficiency')
                        eff_str = f"{eff}%" if eff else "-"
                        
                        # 최적 속도
                        optimal = wp.get('optimal_velocity') or wp.get('motion_profile', {}).get('optimal_velocity')
                        optimal_str = f"{optimal}" if optimal else "-"
                        
                        wp_data.append({
                            "ID": wp["id"],
                            "Line": wp["line"],
                            "Type": wp["type"],
                            "거리": dist_str,
                            "설정 속도": f"{wp['velocity']} {wp['velocity_unit']}",
                            "도달 가능": reachable_str,
                            "효율": eff_str,
                            "최적 속도": optimal_str,
                            "설정 가속도": f"{wp['acceleration']} {wp['acceleration_unit']}",
                            "상태": f"{status_icon} {wp['status']}"
                        })
                    
                    wp_df = pd.DataFrame(wp_data)
                    
                    # 상태별 색상 스타일링
                    def highlight_status(row):
                        if "경고" in row["상태"]:
                            return ['background-color: #ffcccc'] * len(row)
                        elif "주의" in row["상태"] or "비효율" in row["상태"]:
                            return ['background-color: #fff3cd'] * len(row)
                        else:
                            return [''] * len(row)
                    
                    styled_df = wp_df.style.apply(highlight_status, axis=1)
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                    
                    # ========== 이슈 상세 ==========
                    if script_results["issues"]:
                        st.markdown("---")
                        st.subheader("⚠️ 발견된 이슈 상세")
                        
                        # 카테고리별 분류
                        speed_issues = [i for i in script_results["issues"] if i["category"] == "속도"]
                        accel_issues = [i for i in script_results["issues"] if i["category"] == "가속도"]
                        efficiency_issues = [i for i in script_results["issues"] if i["category"] == "효율성"]
                        
                        if speed_issues:
                            st.markdown("#### 🚀 속도 이슈")
                            for issue in speed_issues:
                                if issue["severity"] == "경고":
                                    st.error(f"**Line {issue['line']}**: {issue['message']}")
                                else:
                                    st.warning(f"**Line {issue['line']}**: {issue['message']}")
                                st.markdown(f"  현재: `{issue['current']}` → 권장: `{issue['recommended']}` (최대: `{issue['max_allowed']}`)")
                        
                        if accel_issues:
                            st.markdown("#### ⚡ 가속도 이슈")
                            for issue in accel_issues:
                                if issue["severity"] == "경고":
                                    st.error(f"**Line {issue['line']}**: {issue['message']}")
                                else:
                                    st.warning(f"**Line {issue['line']}**: {issue['message']}")
                                st.markdown(f"  현재: `{issue['current']}` → 권장: `{issue['recommended']}`")
                        
                        if efficiency_issues:
                            st.markdown("#### 📉 효율성 이슈 (거리 기반)")
                            for issue in efficiency_issues:
                                st.warning(f"**Line {issue['line']}**: {issue['message']}")
                                st.markdown(f"""
                                | 설정 속도 | 실제 도달 가능 | 최적 속도 | 효율 |
                                |-----------|---------------|-----------|------|
                                | `{issue['current']}` | `{issue['reachable']}` | `{issue['optimal']}` | {issue['efficiency']}% |
                                """)
                    
                    # ========== 권장사항 ==========
                    if script_results["recommendations"]:
                        st.markdown("---")
                        st.subheader("💡 권장사항")
                        
                        for rec in script_results["recommendations"]:
                            priority_emoji = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(rec["priority"], "⚪")
                            
                            with st.expander(f"{priority_emoji} **[{rec['priority']}]** {rec['category']} ({rec['issue_count']}건)", 
                                            expanded=(rec["priority"] == "높음")):
                                st.markdown(f"**문제:** {rec['message']}")
                                st.markdown(f"**조치:** {rec['action']}")
                                
                                affected = rec.get('affected_lines', [])
                                if len(affected) <= 10:
                                    st.markdown(f"**영향 라인:** `{affected}`")
                                else:
                                    st.markdown(f"**영향 라인:** `{affected[:10]}` ... 외 {len(affected)-10}개")
                                
                                # 효율성 이슈 상세 테이블
                                if rec["category"] == "속도 효율성 (거리 기반)" and "details" in rec:
                                    st.markdown("**상세 정보:**")
                                    details_df = pd.DataFrame(rec["details"])
                                    details_df.columns = ["Line", "현재 속도", "도달 가능", "최적 속도", "효율(%)"]
                                    st.dataframe(details_df, use_container_width=True, hide_index=True)
                    
                    # ========== 리포트 다운로드 ==========
                    st.markdown("---")
                    st.subheader("📥 리포트 다운로드")
                    
                    report_text = script_analyzer.generate_report()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            "📥 분석 리포트 다운로드 (TXT)",
                            data=report_text,
                            file_name=f"URScript_{robot_model}_분석리포트.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                    with col2:
                        json_report = json.dumps(script_results, indent=2, ensure_ascii=False)
                        st.download_button(
                            "📥 분석 결과 다운로드 (JSON)",
                            data=json_report,
                            file_name=f"URScript_{robot_model}_분석결과.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    
                    # 텍스트 리포트 미리보기
                    with st.expander("📄 텍스트 리포트 미리보기"):
                        st.text_area("리포트", report_text, height=400)
                
                except Exception as e:
                    st.error(f"❌ 분석 중 오류 발생: {str(e)}")
                    st.info("URScript 형식이 올바른지 확인해주세요.")
                    import traceback
                    with st.expander("오류 상세"):
                        st.code(traceback.format_exc())
    
    else:
        st.info("👆 URScript 파일을 업로드하거나 직접 입력해주세요.")
        
        with st.expander("📖 지원하는 명령어 및 분석 항목"):
            st.markdown("""
            ### 지원 명령어
            
            | 명령어 | 설명 | 속도 단위 | 가속도 단위 |
            |--------|------|----------|------------|
            | `movej` | 관절 공간 이동 | rad/s | rad/s² |
            | `movel` | 직선 이동 | m/s | m/s² |
            | `movep` | 프로세스 이동 | m/s | m/s² |
            | `movec` | 원형 이동 | m/s | m/s² |
            | `speedj` | 관절 속도 제어 | rad/s | rad/s² |
            | `speedl` | TCP 속도 제어 | m/s | m/s² |
            
            ### 분석 항목
            
            1. **기본 분석**
               - 속도/가속도가 로봇 최대 허용치 이내인지
               - 속도/가속도가 권장치 이내인지
            
            2. **거리 기반 정밀 분석** 🆕
               - 웨이포인트 간 거리 계산
               - 해당 거리에서 **실제 도달 가능한 최대 속도** 계산
               - 설정 속도 대비 **효율성** 분석
               - **최적 속도** 제안
            
            ### 거리 기반 분석 원리
            
            ```
            사다리꼴 속도 프로파일:
            
            속도 ^
                 │     ┌─────┐
                 │    /       \\
                 │   /         \\
                 └──┴───────────┴──▶ 시간
                    가속  등속  감속
            
            거리가 짧으면 등속 구간 없이 삼각형 프로파일:
            - 도달 가능 속도 = √(가속도 × 거리)
            ```
            """)
        
        with st.expander("📝 테스트용 샘플 코드"):
            sample_code = """def main_program():
    # 초기 위치 (관절 이동)
    movej([0.1, -1.5, 1.2, 0, 1.57, 0], a=1.4, v=1.05)
    
    # 작업 시작점 (긴 거리)
    movel(p[0.5, 0.2, 0.3, 0, 3.14, 0], a=1.2, v=0.5)
    
    # 짧은 거리 이동 - 속도 너무 높음 (비효율!)
    movel(p[0.52, 0.21, 0.3, 0, 3.14, 0], a=1.2, v=1.0)
    
    # 적절한 설정
    movel(p[0.6, 0.3, 0.3, 0, 3.14, 0], a=1.2, v=0.25, r=0.02)
    
    # 긴 거리, 적절한 속도
    movel(p[0.8, 0.5, 0.4, 0, 3.14, 0], a=1.2, v=0.5)
    
    # 홈 위치
    movej([0, -1.57, 1.57, 0, 1.57, 0], a=1.4, v=1.05)
end"""
            st.code(sample_code, language="python")
            st.info("👆 위 코드를 복사해서 '직접 입력' 모드에서 테스트해보세요!")


# ============ 푸터 ============
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    🤖 UR Robot Analysis AI Agent | Built with Streamlit<br>
    거리 기반 정밀 분석으로 더 정확한 속도/가속도 검토 가능
</div>
""", unsafe_allow_html=True)
