# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys
import os

# 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analyzer import URDataAnalyzer
from src.report_generator import URReportGenerator
from config.robot_specs import ROBOT_SPECS

# 페이지 설정
st.set_page_config(
    page_title="UR 로봇 데이터 분석 AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .status-good { color: #4CAF50; font-weight: bold; }
    .status-warning { color: #FF9800; font-weight: bold; }
    .status-danger { color: #F44336; font-weight: bold; }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# 제목
st.markdown('<p class="main-header">🤖 유니버설로봇 Realtime Data 분석 AI Agent</p>', unsafe_allow_html=True)
st.markdown("---")

# 사이드바
with st.sidebar:
    st.image("https://www.universal-robots.com/media/1823741/ur-logo.png", width=200)
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
    st.caption("Made with ❤️ for UR Robots")

# 메인 영역
st.header("📂 데이터 업로드")

uploaded_file = st.file_uploader(
    "UR Realtime Data 파일을 업로드하세요 (Excel 또는 CSV)",
    type=['xlsx', 'xls', 'csv'],
    help="RTDE에서 추출한 엑셀 또는 CSV 파일"
)

if uploaded_file is not None:
    try:
        # 데이터 로드
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
            st.dataframe(col_df, use_container_width=True)
        
        st.markdown("---")
        
        # 분석 버튼
        if st.button("🔍 분석 시작", type="primary", use_container_width=True):
            
            # 분석 실행
            with st.spinner("🔄 분석 중... 잠시만 기다려주세요"):
                analyzer = URDataAnalyzer(df, robot_model)
                results = analyzer.analyze_all()
                report_gen = URReportGenerator(results)
                summary = report_gen.get_summary_metrics()
            
            st.success("✅ 분석 완료!")
            st.balloons()
            
            # 결과 저장 (세션 스테이트)
            st.session_state['results'] = results
            st.session_state['summary'] = summary
            st.session_state['report_gen'] = report_gen
            st.session_state['analyzed'] = True

# 분석 결과 표시
if st.session_state.get('analyzed', False):
    results = st.session_state['results']
    summary = st.session_state['summary']
    report_gen = st.session_state['report_gen']
    
    st.markdown("---")
    st.header("📈 분석 결과")
    
    # 요약 메트릭
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            label="전체 상태",
            value=summary['overall_status'].split()[0],
            help="전체적인 로봇 상태"
        )
    
    with col2:
        delta_color = "normal" if summary['speed_utilization'] < 85 else "inverse"
        st.metric(
            label="속도 사용률",
            value=f"{summary['speed_utilization']}%",
            delta="정상" if summary['speed_utilization'] < 85 else "주의",
            delta_color=delta_color
        )
    
    with col3:
        delta_color = "normal" if summary['load_ratio'] < 75 else "inverse"
        st.metric(
            label="평균 부하율",
            value=f"{summary['load_ratio']}%",
            delta="정상" if summary['load_ratio'] < 75 else "주의",
            delta_color=delta_color
        )
    
    with col4:
        st.metric(
            label="모션 효율",
            value=f"{summary['motion_efficiency']}%"
        )
    
    with col5:
        st.metric(
            label="발견된 이슈",
            value=f"{summary['issues_count']}건",
            delta=f"높음: {summary['high_priority_issues']}건" if summary['high_priority_issues'] > 0 else None,
            delta_color="inverse" if summary['high_priority_issues'] > 0 else "off"
        )
    
    st.markdown("---")
    
    # 탭으로 상세 결과 표시
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🚀 속도 분석", 
        "⚡ 가속도/부하", 
        "🌡️ 온도", 
        "💡 권장사항", 
        "📄 전체 리포트"
    ])
    
    with tab1:
        st.subheader("🚀 속도 분석 결과")
        
        speed_data = results.get("speed_analysis", {})
        
        # TCP 속도
        if speed_data.get("tcp_speed"):
            tcp = speed_data["tcp_speed"]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("현재 최대 TCP 속도", f"{tcp['current_max']} m/s")
            with col2:
                st.metric("권장 최대 TCP 속도", f"{tcp['recommended']} m/s")
            with col3:
                status_color = "🟢" if tcp['status'] == "정상" else "🟡"
                st.metric("상태", f"{status_color} {tcp['status']}")
        
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
            
            fig.update_layout(
                barmode='group',
                title='관절별 속도 비교 (°/s)',
                xaxis_title='관절',
                yaxis_title='속도 (°/s)',
                height=400
            )
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
    
    with tab2:
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
    
    with tab3:
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
    
    with tab4:
        st.subheader("💡 권장사항")
        recommendations = results.get("recommendations", [])
        
        if recommendations:
            for i, rec in enumerate(recommendations):
                priority_emoji = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(rec["priority"], "⚪")
                
                with st.expander(f"{priority_emoji} **[{rec['priority']}]** {rec['category']} - {rec['target']}", expanded=(rec["priority"] == "높음")):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**📌 문제점:**")
                        st.write(rec['issue'])
                        st.markdown(f"**📍 현재 값:** `{rec['current_value']}`")
                    with col2:
                        st.markdown(f"**✅ 권장 값:** `{rec['recommended_value']}`")
                        st.markdown(f"**💬 권장 조치:**")
                        st.info(rec['recommendation'])
                    st.markdown(f"**🎯 기대 효과:** {rec['benefit']}")
        else:
            st.success("✅ 모든 항목이 정상 범위입니다! 특별한 권장사항이 없습니다.")
    
    with tab5:
        st.subheader("📄 전체 리포트")
        
        text_report = report_gen.generate_text_report()
        
        st.text_area("리포트 내용", text_report, height=500)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 텍스트 리포트 다운로드",
                data=text_report,
                file_name=f"UR_{robot_model}_분석리포트.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col2:
            json_report = report_gen.generate_json_report()
            st.download_button(
                label="📥 JSON 리포트 다운로드",
                data=json_report,
                file_name=f"UR_{robot_model}_분석리포트.json",
                mime="application/json",
                use_container_width=True
            )

else:
    # 업로드 전 안내
    st.info("👆 위에서 UR Realtime Data 파일을 업로드해주세요.")
    
    with st.expander("📖 사용 가이드", expanded=True):
        st.markdown("""
        ### 🚀 사용 방법
        
        1. **로봇 모델 선택**: 왼쪽 사이드바에서 분석할 UR 로봇 모델을 선택하세요
        2. **파일 업로드**: RTDE에서 추출한 Excel 또는 CSV 파일을 업로드하세요
        3. **분석 시작**: '분석 시작' 버튼을 클릭하세요
        4. **결과 확인**: 각 탭에서 상세 분석 결과를 확인하세요
        5. **리포트 다운로드**: 필요시 분석 리포트를 다운로드하세요
        
        ---
        
        ### 📊 분석 항목
        
        | 항목 | 설명 |
        |------|------|
        | **속도 분석** | 관절별/TCP 속도 분석 및 권장 속도 제안 |
        | **가속도 분석** | 관절별 가속도 분석 및 권장 가속도 제안 |
        | **부하 분석** | 관절별 전류 사용률 및 부하율 분석 |
        | **온도 분석** | 관절별 온도 모니터링 |
        | **효율성 분석** | 모션 효율, 유휴 시간 분석 |
        
        ---
        
        ### 📁 필요한 데이터 컬럼 (예시)
        
        - `timestamp` 또는 `time`: 시간 데이터
        - `actual_qd_0` ~ `actual_qd_5`: 관절 속도 (rad/s 또는 deg/s)
        - `actual_qdd_0` ~ `actual_qdd_5`: 관절 가속도
        - `actual_current_0` ~ `actual_current_5`: 관절 전류 (A)
        - `joint_temp_0` ~ `joint_temp_5`: 관절 온도 (°C)
        - `actual_TCP_speed`: TCP 속도 (m/s)
        """)
    
    with st.expander("🧪 샘플 데이터로 테스트하기"):
        st.markdown("""
        실제 RTDE 데이터가 없다면, 아래 코드로 샘플 데이터를 생성할 수 있습니다:
        """)
        
        st.code("""
import pandas as pd
import numpy as np

# 샘플 데이터 생성
n = 1250  # 10초, 125Hz
t = np.linspace(0, 10, n)

data = {'timestamp': t}

for i in range(6):
    data[f'actual_qd_{i}'] = np.sin(t * (i+1) * 0.5) * 2.0 + np.random.normal(0, 0.1, n)
    data[f'actual_qdd_{i}'] = np.cos(t * (i+1) * 0.5) * 5.0 + np.random.normal(0, 0.2, n)
    data[f'actual_current_{i}'] = np.abs(np.sin(t * 0.3)) * (2.5 - i*0.3) + 0.5
    data[f'joint_temp_{i}'] = 45 + i * 3 + np.random.normal(0, 1, n)

data['actual_TCP_speed'] = np.abs(np.sin(t * 0.5)) * 0.7

df = pd.DataFrame(data)
df.to_excel('sample_ur_data.xlsx', index=False)
print("샘플 데이터 생성 완료!")
        """, language="python")
