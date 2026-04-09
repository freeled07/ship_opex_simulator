import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import itertools

# 페이지 설정
st.set_page_config(page_title="Ship Professional Analyzer", layout="wide")

# --- 1. 초기 데이터 설정 (Yard_A: HHI, Yard_B: GSI, Yard_C: SWS) ---
DEFAULT_DATA = {
    "Ballast": {"Yard_B": (4.631056, 2.80), "Yard_A": (3.142178, 2.88), "Yard_C": (4.848109, 2.80)},
    "Design": {"Yard_B": (1.996242, 3.20), "Yard_A": (5.208589, 2.80), "Yard_C": (6.360426, 2.80)}
}
DEFAULT_GEN_POWER = {"Yard_B": 930.029, "Yard_A": 629.262, "Yard_C": 862.601}

# 연료 데이터 (WtW GHG Intensity: gCO2eq/MJ 기준)
FUEL_INFO = {
    "HFO": {"lhv": 40.2, "cf": 3.114, "sfoc": 170, "base_price": 600, "wtw_intensity": 91.6},
    "MGO/LSFO": {"lhv": 42.7, "cf": 3.206, "sfoc": 160, "base_price": 750, "wtw_intensity": 90.3},
    "LNG": {"lhv": 48.0, "cf": 2.750, "sfoc": 140, "base_price": 650, "wtw_intensity": 76.4},
    "Ammonia (NH3)": {"lhv": 18.6, "cf": 0.0, "sfoc": 280, "base_price": 900, "wtw_intensity": 0.0}
}

# FuelEU Maritime Target Intensity
def get_fueleu_target(year):
    if year < 2025: return 91.16
    elif year < 2030: return 89.34
    elif year < 2035: return 85.69
    elif year < 2040: return 77.94
    elif year < 2045: return 62.90
    elif year < 2050: return 34.64
    else: return 18.23

# --- 2. 사이드바: 입력 설정 ---
with st.sidebar:
    st.title("⚙️ Simulation Config")
    v_target = st.slider("Target Speed (knots)", 10.0, 20.0, 14.5, 0.5)
    sailing_ratio = st.slider("Annual Sailing Ratio (%)", 0, 100, 75)
    sim_years = st.slider("Simulation Period (Years)", 5, 30, 20, 1)  
    op_days = 365 * (sailing_ratio / 100)
    fuel = st.selectbox("Fuel Type", list(FUEL_INFO.keys()))

    st.divider()
    st.header("🌍 초기 환경 규제 설정")
    eu_ratio = st.slider("EU 기항 비율 (%)", 0, 100, 30) / 100
    non_eu_ratio = 1.0 - eu_ratio
    st.caption(f"※ EU 규제(ETS, FuelEU) {eu_ratio*100:.0f}% 적용")
    st.caption(f"※ 비-EU 구간({non_eu_ratio*100:.0f}%) IMO 탄소세 적용")
    
    eua_price_base = st.number_input("초기 EU-ETS 탄소단가 ($/ton)", value=82)
    imo_levy_base = st.number_input("초기 IMO 탄소세 ($/ton, 2028 발효)", value=50)

    st.divider()
    st.header("💰 재무 & 금융 모델")
    discount_rate = st.number_input("할인율 (Discount Rate, %)", value=7.0, step=0.5) / 100
    ltv = st.slider("선박 대출 비율 (LTV, %)", 0, 100, 70) / 100
    loan_rate_base = st.number_input("초기 대출 금리 (Loan Rate, %)", value=6.5, step=0.5) / 100
    loan_term = st.number_input("대출 기간 (Years)", value=15, step=1, min_value=1)

    st.divider()
    st.subheader("🚢 Ship A (KOR)")
    a_base = st.selectbox("Base Model A", ["Yard_A", "Yard_B", "Yard_C"], index=0)
    a_capex = st.number_input("CAPEX A ($M)", value=86.0)
    col1, col2 = st.columns(2)
    with col1:
        a_des_a = st.number_input("Design a (A)", value=DEFAULT_DATA["Design"][a_base][0], format="%.6f")
        a_bal_a = st.number_input("Ballast a (A)", value=DEFAULT_DATA["Ballast"][a_base][0], format="%.6f")
    with col2:
        a_des_b = st.number_input("Design b (A)", value=DEFAULT_DATA["Design"][a_base][1], format="%.4f")
        a_bal_b = st.number_input("Ballast b (A)", value=DEFAULT_DATA["Ballast"][a_base][1], format="%.4f")
    a_gen_power = st.number_input("Generator Power A (kW)", value=DEFAULT_GEN_POWER[a_base], format="%.3f")

    st.divider()
    st.subheader("🚢 Ship B (CHN)")
    b_base = st.selectbox("Base Model B", ["Yard_A", "Yard_B", "Yard_C"], index=2)
    b_capex = st.number_input("CAPEX B ($M)", value=80.0)
    col3, col4 = st.columns(2)
    with col3:
        b_des_a = st.number_input("Design a (B)", value=DEFAULT_DATA["Design"][b_base][0], format="%.6f")
        b_bal_a = st.number_input("Ballast a (B)", value=DEFAULT_DATA["Ballast"][b_base][0], format="%.6f")
    with col4:
        b_des_b = st.number_input("Design b (B)", value=DEFAULT_DATA["Design"][b_base][1], format="%.4f")
        b_bal_b = st.number_input("Ballast b (B)", value=DEFAULT_DATA["Ballast"][b_base][1], format="%.4f")
    b_gen_power = st.number_input("Generator Power B (kW)", value=DEFAULT_GEN_POWER[b_base], format="%.3f")

# --- 3. 핵심 계산 로직 ---
def calc_total_metrics(v, d_a, d_b, b_a, b_b, gen_p, fuel_type):
    p_me_avg = (d_a * (v ** d_b) + b_a * (v ** b_b)) / 2
    sfoc = FUEL_INFO[fuel_type]['sfoc']
    total_daily_foc = ((p_me_avg + gen_p) * sfoc * 24) / 1e6
    return p_me_avg, total_daily_foc

p_me_a, foc_a = calc_total_metrics(v_target, a_des_a, a_des_b, a_bal_a, a_bal_b, a_gen_power, fuel)
p_me_b, foc_b = calc_total_metrics(v_target, b_des_a, b_des_b, b_bal_a, b_bal_b, b_gen_power, fuel)

co2_a = foc_a * FUEL_INFO[fuel]['cf']
co2_b = foc_b * FUEL_INFO[fuel]['cf']

# --- 4. 시뮬레이션 및 규제, 금융, 할인율 통합 ---
st.title("📊 Ship Efficiency & OPEX Comparison (NPV & Loan Applied)")

# 거시경제 시나리오 통합 데이터프레임 구성 
current_base_price = FUEL_INFO[fuel]['base_price']
scenario_data = pd.DataFrame({
    "Period": ["Year 1-10", "Year 11-20", "Year 21-30"], 
    "Fuel Price ($/ton)": [int(current_base_price), int(current_base_price*(1.02**10)), int(current_base_price*(1.02**20))],
    "EU-ETS Price ($/ton)": [int(eua_price_base), int(eua_price_base*1.3), int(eua_price_base*1.6)],
    "IMO Levy ($/ton)": [int(imo_levy_base), int(imo_levy_base*1.5), int(imo_levy_base*2.0)],
    "Loan Rate (%)": [loan_rate_base*100, max(0.0, loan_rate_base*100-1.0), max(0.0, loan_rate_base*100-1.5)]
})

with st.expander("📈 장기 거시경제 시나리오 (Macro-Economic Scenario) - 수정 가능", expanded=False):
    st.markdown("시간이 지남에 따라 변동하는 연료비, 탄소세, 대출 금리를 10년 단위로 설정합니다. 표 안의 숫자를 더블클릭하여 직접 시나리오를 변경할 수 있습니다.")
    edited_scenario = st.data_editor(scenario_data, use_container_width=True)

# 초기 금융 변수 계산
capex_diff = (a_capex - b_capex) * 1e6
loan_diff = capex_diff * ltv
equity_diff = capex_diff * (1 - ltv)

results = []
cum_pure_saving = 0
cum_nominal_ncf = 0
cum_npv_dcf = 0

bep_year_pure = None
bep_year_npv = None
start_year = 2026

cons_years_a = 0
cons_years_b = 0
EUR_TO_USD = 1.1

# 선박 금융 상환 트래킹 
rem_loan_diff = loan_diff
total_interest_diff = 0
principal_payment = loan_diff / loan_term if loan_term > 0 else 0

for y in range(1, sim_years + 1):
    cal_year = start_year + y - 1
    
    # 시점(Period)에 따른 거시경제 변수 매핑
    period_idx = 0 if y <= 10 else 1 if y <= 20 else 2
    current_fuel_price = edited_scenario.iloc[period_idx]['Fuel Price ($/ton)']
    current_eua_price = edited_scenario.iloc[period_idx]['EU-ETS Price ($/ton)']
    current_imo_levy = edited_scenario.iloc[period_idx]['IMO Levy ($/ton)']
    current_loan_rate = edited_scenario.iloc[period_idx]['Loan Rate (%)'] / 100
    
    # 1. 유지비(OPEX) 및 탄소 규제 계산
    fuel_cost_a, fuel_cost_b = foc_a * op_days * current_fuel_price, foc_b * op_days * current_fuel_price
    ann_co2_a, ann_co2_b = co2_a * op_days, co2_b * op_days
    energy_mj_a, energy_mj_b = foc_a * op_days * 1000 * FUEL_INFO[fuel]['lhv'], foc_b * op_days * 1000 * FUEL_INFO[fuel]['lhv']
    
    ets_a, ets_b = ann_co2_a * eu_ratio * current_eua_price, ann_co2_b * eu_ratio * current_eua_price
    imo_a = ann_co2_a * non_eu_ratio * current_imo_levy if cal_year >= 2028 else 0
    imo_b = ann_co2_b * non_eu_ratio * current_imo_levy if cal_year >= 2028 else 0
    
    target_intensity = get_fueleu_target(cal_year)
    deficit = FUEL_INFO[fuel]['wtw_intensity'] - target_intensity
    penalty_factor_usd = (2400 * EUR_TO_USD) / (41000 * 91.16) 
    
    fueleu_pen_a = fueleu_pen_b = 0
    if deficit > 0:
        cons_years_a += 1
        cons_years_b += 1
        fueleu_pen_a = (deficit * energy_mj_a) * penalty_factor_usd * (1.0 + (cons_years_a - 1) * 0.1) * eu_ratio
        fueleu_pen_b = (deficit * energy_mj_b) * penalty_factor_usd * (1.0 + (cons_years_b - 1) * 0.1) * eu_ratio
    else:
        cons_years_a = cons_years_b = 0
    
    total_penalty_a = ets_a + imo_a + fueleu_pen_a
    total_penalty_b = ets_b + imo_b + fueleu_pen_b
    
    opex_a = fuel_cost_a + total_penalty_a
    opex_b = fuel_cost_b + total_penalty_b
    
    # 2. 재무 현금흐름(Cash Flow) 및 할인 계산
    pure_saving = opex_b - opex_a  
    cum_pure_saving += pure_saving
    net_profit_pure = cum_pure_saving - capex_diff 
    
    if y <= loan_term:
        interest_payment = rem_loan_diff * current_loan_rate
        loan_payment = principal_payment + interest_payment
        total_interest_diff += interest_payment
        rem_loan_diff -= principal_payment
    else:
        loan_payment = 0
        
    ncf_nominal = pure_saving - loan_payment 
    ncf_dcf = ncf_nominal / ((1 + discount_rate)**y) 
    
    cum_nominal_ncf += ncf_nominal
    cum_npv_dcf += ncf_dcf
    
    net_profit_nominal = cum_nominal_ncf - equity_diff 
    net_profit_npv = cum_npv_dcf - equity_diff         
    
    if bep_year_pure is None and net_profit_pure >= 0:
        bep_year_pure = y
    if bep_year_npv is None and net_profit_npv >= 0:
        bep_year_npv = y
        
    results.append({
        "Calendar_Year": cal_year,
        "Year_Index": y,
        "Net_Profit_Pure": net_profit_pure,
        "Net_Profit_Nominal": net_profit_nominal,
        "Net_Profit_NPV": net_profit_npv,
        "Pure_Saving_Annual": pure_saving,
        "Current_Loan_Rate": current_loan_rate * 100,
        "ETS_Price": current_eua_price,
        "FuelEU_Target": target_intensity,
        "ETS_A": ets_a, "IMO_A": imo_a, "FuelEU_A": fueleu_pen_a,
        "ETS_B": ets_b, "IMO_B": imo_b, "FuelEU_B": fueleu_pen_b
    })

df_res = pd.DataFrame(results)

# --- 5. UI 메트릭 ---
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.metric("총 CAPEX 차액 (A-B)", f"$ {capex_diff/1e6:.1f} M")
with m2:
    st.metric("Power (Ship A)", f"{p_me_a:.1f} kW")
with m3:
    foc_diff_pct = ((foc_a - foc_b) / foc_b) * 100 if foc_b > 0 else 0
    st.metric("Total Daily FOC (Ship A)", f"{foc_a:.2f} mt/d", delta=f"{foc_diff_pct:.1f}%", delta_color="inverse")
with m4:
    co2_diff_pct = ((co2_a - co2_b) / co2_b) * 100 if co2_b > 0 else 0
    st.metric("Daily CO2 (Ship A)", f"{co2_a:.1f} mt/d", delta=f"{co2_diff_pct:.1f}%" if co2_b > 0 else None, delta_color="inverse")
with m5:
    final_npv = df_res['Net_Profit_NPV'].iloc[-1]
    st.metric(f"{sim_years}년 최종 NPV (순현재가치)", f"$ {final_npv/1e6:.1f} M")  

st.write("")

m6, m7, m8, m9, m10 = st.columns(5)
with m6:
    st.metric("자기자본 투입 차액", f"$ {equity_diff/1e6:.1f} M")
with m7:
    st.metric("Power (Ship B)", f"{p_me_b:.1f} kW")
with m8:
    st.metric("Total Daily FOC (Ship B)", f"{foc_b:.2f} mt/d")
with m9:
    st.metric("Daily CO2 (Ship B)", f"{co2_b:.1f} mt/d")
with m10:
    payback_text = f"{bep_year_npv} 년" if bep_year_npv else f"불가 ({sim_years}년 내)"  
    st.metric("🎯 실질 페이백 (NPV 기준)", payback_text)

# --- 6. 재무적 손실 요인 가시화 ---
st.divider()
st.subheader("💸 대출 이자 및 인플레이션(할인율)에 의한 수익 증발 요약")

st.markdown("""
<style>
div[data-testid="stAlert"] {
    height: 200px; 
    display: flex;
    flex-direction: column;
    justify-content: center;
}
</style>
""", unsafe_allow_html=True)

fm1, fm2, fm3 = st.columns(3)
with fm1:
    st.info(f"**1. 이자 지출액 (변동금리)**\n\n비싼 선박을 구매하며 추가로 발생한 대출 이자의 누적액입니다.\n\n### - $ {total_interest_diff/1e6:.1f} M")
with fm2:
    discount_loss = df_res['Net_Profit_Nominal'].iloc[-1] - df_res['Net_Profit_NPV'].iloc[-1]
    st.warning(f"**2. 시간가치 하락분 (할인율)**\n\n미래에 발생할 절감액을 현재 가치로 할인했을 때 증발한 금액입니다.\n\n### - $ {discount_loss/1e6:.1f} M")
with fm3:
    pure_profit = df_res['Net_Profit_Pure'].iloc[-1]
    st.success(f"**3. 실질 순이익 (최종 NPV)**\n\n단순 절감액에서 이자 비용과 시간가치 하락분을 뺀 진짜 이익입니다.\n\n### $ {final_npv/1e6:.1f} M")

st.divider()

# --- 7. 시각화 (상단 3열) ---
c1, c2, c3 = st.columns([2, 1, 1])

with c1:
    st.subheader("📈 Profit Curve: 단순이익 vs 명목이익 vs 현재가치(NPV)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit_Pure'], mode='lines', name='단순 OPEX 누적이익', line=dict(color='gray', width=2, dash='dash')))
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit_Nominal'], mode='lines', name='명목 이익 (대출이자 차감)', line=dict(color='#82C59D', width=2)))
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit_NPV'], fill='tozeroy', name='최종 NPV (순현재가치)', line=dict(color='#00CC96', width=4)))
    
    cal_bep_year_npv = start_year + bep_year_npv - 1 if bep_year_npv else None
    if cal_bep_year_npv:
        bep_profit = df_res.loc[df_res['Calendar_Year'] == cal_bep_year_npv, 'Net_Profit_NPV'].values[0]
        fig.add_trace(go.Scatter(x=[cal_bep_year_npv], y=[bep_profit], mode='markers+text', name='NPV Break-even',
                                 text=[f"  {bep_year_npv}년 소요"], textposition="top right", marker=dict(color='gold', size=15, symbol='star', line=dict(width=2, color='black'))))
    fig.add_hline(y=0, line_dash="solid", line_color="red")
    fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=30, b=20), xaxis_title="Calendar Year", yaxis_title="Cumulative Net Profit ($)")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("⚡ Speed-Power Curves")
    v_range = np.linspace(10, 20, 50)
    fig_curve = go.Figure()
    fig_curve.add_trace(go.Scatter(x=v_range, y=a_des_a*(v_range**a_des_b), name="Des(A)", line=dict(color='#1f77b4', dash='dash')))
    fig_curve.add_trace(go.Scatter(x=v_range, y=a_bal_a*(v_range**a_bal_b), name="Bal(A)", line=dict(color='#1f77b4')))
    fig_curve.add_trace(go.Scatter(x=v_range, y=b_des_a*(v_range**b_des_b), name="Des(B)", line=dict(color='#ff7f0e', dash='dash')))
    fig_curve.add_trace(go.Scatter(x=v_range, y=b_bal_a*(v_range**b_bal_b), name="Bal(B)", line=dict(color='#ff7f0e')))
    fig_curve.add_vline(x=v_target, line_color="gray", line_dash="dot")
    fig_curve.update_layout(margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_curve, use_container_width=True)

with c3:
    st.subheader("🔋 Generator Power")
    gen_data = sorted([{'ship': 'Ship A', 'power': a_gen_power, 'color': '#1f77b4'}, {'ship': 'Ship B', 'power': b_gen_power, 'color': '#ff7f0e'}], key=lambda x: x['power'])
    fig_bar = go.Figure(data=[go.Bar(x=[d['ship'] for d in gen_data], y=[d['power'] for d in gen_data], marker_color=[d['color'] for d in gen_data], text=[f"{d['power']:.1f} kW" for d in gen_data], textposition='auto')])
    fig_bar.update_layout(margin=dict(l=20, r=20, t=30, b=20), yaxis_title="Power (kW)")
    st.plotly_chart(fig_bar, use_container_width=True)

# --- 8. 하단: 환경 규제 분석 ---
st.divider()
end_year = start_year + sim_years - 1
st.subheader(f"🌍 탄소 규제 페널티 추이 분석 ({start_year} ~ {end_year})")

c4, c5 = st.columns(2)

with c4:
    st.markdown("**항목별/연도별 누적 페널티 비용 분석 (이중과세 방지 적용)**")
    fig_pen = go.Figure()
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['ETS_A'], name='EU-ETS (A)', marker_color='#91bceb', offsetgroup=1))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['IMO_A'], name='IMO Levy (A)', marker_color='#1f77b4', offsetgroup=1, base=df_res['ETS_A']))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['FuelEU_A'], name='FuelEU Penalty (A)', marker_color='#08306b', offsetgroup=1, base=df_res['ETS_A']+df_res['IMO_A']))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['ETS_B'], name='EU-ETS (B)', marker_color='#fdcdac', offsetgroup=2))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['IMO_B'], name='IMO Levy (B)', marker_color='#ff7f0e', offsetgroup=2, base=df_res['ETS_B']))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['FuelEU_B'], name='FuelEU Penalty (B)', marker_color='#7f2704', offsetgroup=2, base=df_res['ETS_B']+df_res['IMO_B']))
    fig_pen.update_layout(barmode='group', xaxis_title="Calendar Year", yaxis_title="Penalty Cost ($)", hovermode="x unified")
    st.plotly_chart(fig_pen, use_container_width=True)

with c5:
    st.markdown("**온실가스 집약도(GHG Intensity) 규제 한계선**")
    fig_limit = go.Figure()
    fig_limit.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['FuelEU_Target'], mode='lines+markers', name='Target Limit', line=dict(color='red', width=3, dash='dash')))
    fig_limit.add_hline(y=FUEL_INFO[fuel]['wtw_intensity'], line_dash="solid", line_color="black", annotation_text=f"Selected Fuel ({fuel}): {FUEL_INFO[fuel]['wtw_intensity']}", annotation_position="top right")
    fig_limit.update_layout(xaxis_title="Calendar Year", yaxis_title="GHG Intensity (gCO2eq/MJ)")
    st.plotly_chart(fig_limit, use_container_width=True)

with st.expander("📝 Detailed Simulation Data"):
    st.dataframe(df_res.set_index("Calendar_Year").drop(columns=['Year_Index'], errors='ignore'), use_container_width=True)

# --- 9. 민감도 분석 (Batch 시뮬레이션 확장판: 1D & 2D) ---
st.divider()
st.header("🔄 민감도 분석 (Batch 시뮬레이션 확장판)")
st.markdown("선박 효율, 금융, 규제 등 핵심 파라미터 조합이 **원하는 출력 지표**에 미치는 영향을 시뮬레이션합니다. (2개 변수 선택 시 2D 히트맵 생성)")

def get_def_str(p_name):
    if p_name == "Target Speed (knots)": return "13.0, 14.0, 14.5, 15.0, 16.0"
    elif p_name == "Annual Sailing Ratio (%)": return "60, 70, 75, 80, 90"
    elif p_name == "Simulation Period (Years)": return "10, 15, 20, 25, 30"
    elif p_name == "EU 기항 비율 (%)": return "0, 30, 50, 70, 100"
    elif p_name == "초기 EU-ETS 탄소단가 ($/ton)": return "50, 82, 100, 150, 200"
    elif p_name == "초기 IMO 탄소세 ($/ton)": return "0, 50, 100, 150, 200"
    elif p_name == "할인율 (Discount Rate, %)": return "5.0, 6.0, 7.0, 8.0, 10.0"
    elif p_name == "선박 대출 비율 (LTV, %)": return "0, 50, 70, 80, 100"
    elif p_name == "초기 대출 금리 (Loan Rate, %)": return "4.0, 5.0, 6.5, 8.0, 10.0"
    elif p_name == "대출 기간 (Years)": return "5, 10, 15, 20"
    elif p_name == "CAPEX A ($M)": return f"{a_capex-4}, {a_capex-2}, {a_capex}, {a_capex+2}, {a_capex+4}"
    elif p_name == "CAPEX B ($M)": return f"{b_capex-4}, {b_capex-2}, {b_capex}, {b_capex+2}, {b_capex+4}"
    elif p_name == "Generator Power A (kW)": return "500, 600, 629, 700"
    elif p_name == "Generator Power B (kW)": return "700, 800, 862, 950"
    return "0, 1, 2"

param_list = [
    "Target Speed (knots)", "Annual Sailing Ratio (%)", "Simulation Period (Years)",
    "EU 기항 비율 (%)", "초기 EU-ETS 탄소단가 ($/ton)", "초기 IMO 탄소세 ($/ton)",
    "할인율 (Discount Rate, %)", "선박 대출 비율 (LTV, %)", "초기 대출 금리 (Loan Rate, %)",
    "대출 기간 (Years)", "CAPEX A ($M)", "CAPEX B ($M)", "Generator Power A (kW)", "Generator Power B (kW)"
]

# 출력 변수 리스트 (페이백 년도 추가됨!)
target_metrics_list = [
    "최종 NPV ($M)", 
    "페이백(년)", 
    "단순 누적 이익 ($M)", 
    "총 대출이자 지출 ($M)", 
    "Daily FOC_A (mt/d)", 
    "Daily CO2_A (mt/d)"
]

b_col1, b_col2 = st.columns([1, 2.5])

with b_col1:
    batch_param1 = st.selectbox("📌 비교할 변수 1 (X축)", param_list, index=0)
    test_values_str1 = st.text_input("변수 1 테스트 값 (쉼표로 구분)", get_def_str(batch_param1))
    
    st.write("")
    
    batch_param2 = st.selectbox("📌 비교할 변수 2 (Y축, 선택사항)", ["선택 안함"] + param_list, index=0)
    if batch_param2 != "선택 안함":
        test_values_str2 = st.text_input("변수 2 테스트 값 (쉼표로 구분)", get_def_str(batch_param2))
    
    st.markdown("---")
    target_metric = st.selectbox("🎯 결과 그래프에 표시할 출력 지표", target_metrics_list, index=0)
    
    st.write("")
    run_batch = st.button("배치(Batch) 실행", type="primary", use_container_width=True)

with b_col2:
    if run_batch:
        try:
            vals1 = [float(v.strip()) for v in test_values_str1.split(',')]
            is_2d = batch_param2 != "선택 안함"
            vals2 = [float(v.strip()) for v in test_values_str2.split(',')] if is_2d else [None]
            
            combinations = list(itertools.product(vals1, vals2))
            
            def run_single_sim(val1, val2):
                sim_params = {
                    "v_target": v_target, "sailing_ratio": sailing_ratio, "sim_years": sim_years,
                    "eu_ratio": eu_ratio, "eua_price": None, "imo_levy": None,
                    "discount_rate": discount_rate, "ltv": ltv, "loan_rate": None,
                    "loan_term": loan_term, "a_capex": a_capex, "b_capex": b_capex,
                    "a_gen": a_gen_power, "b_gen": b_gen_power
                }
                
                def apply_override(p_name, p_val):
                    if p_name == "Target Speed (knots)": sim_params["v_target"] = p_val
                    elif p_name == "Annual Sailing Ratio (%)": sim_params["sailing_ratio"] = p_val
                    elif p_name == "Simulation Period (Years)": sim_params["sim_years"] = int(p_val)
                    elif p_name == "EU 기항 비율 (%)": sim_params["eu_ratio"] = p_val / 100.0
                    elif p_name == "초기 EU-ETS 탄소단가 ($/ton)": sim_params["eua_price"] = p_val
                    elif p_name == "초기 IMO 탄소세 ($/ton)": sim_params["imo_levy"] = p_val
                    elif p_name == "할인율 (Discount Rate, %)": sim_params["discount_rate"] = p_val / 100.0
                    elif p_name == "선박 대출 비율 (LTV, %)": sim_params["ltv"] = p_val / 100.0
                    elif p_name == "초기 대출 금리 (Loan Rate, %)": sim_params["loan_rate"] = p_val / 100.0
                    elif p_name == "대출 기간 (Years)": sim_params["loan_term"] = int(p_val)
                    elif p_name == "CAPEX A ($M)": sim_params["a_capex"] = p_val
                    elif p_name == "CAPEX B ($M)": sim_params["b_capex"] = p_val
                    elif p_name == "Generator Power A (kW)": sim_params["a_gen"] = p_val
                    elif p_name == "Generator Power B (kW)": sim_params["b_gen"] = p_val

                apply_override(batch_param1, val1)
                if is_2d: apply_override(batch_param2, val2)
                
                sp = sim_params
                sim_op_days = 365 * (sp["sailing_ratio"] / 100)
                sim_non_eu_ratio = 1.0 - sp["eu_ratio"]
                
                _, sim_foc_a = calc_total_metrics(sp["v_target"], a_des_a, a_des_b, a_bal_a, a_bal_b, sp["a_gen"], fuel)
                _, sim_foc_b = calc_total_metrics(sp["v_target"], b_des_a, b_des_b, b_bal_a, b_bal_b, sp["b_gen"], fuel)
                
                sim_co2_a = sim_foc_a * FUEL_INFO[fuel]['cf']
                sim_co2_b = sim_foc_b * FUEL_INFO[fuel]['cf']
                
                c_diff = (sp["a_capex"] - sp["b_capex"]) * 1e6
                l_diff = c_diff * sp["ltv"]
                e_diff = c_diff * (1 - sp["ltv"])
                
                rem_l = l_diff
                tot_int = 0
                prin_pay = l_diff / sp["loan_term"] if sp["loan_term"] > 0 else 0
                
                cum_pure_sav = 0
                cum_npv_dcf = 0
                sim_bep_npv = None
                c_y_a, c_y_b = 0, 0
                
                for y in range(1, sp["sim_years"] + 1):
                    cal_yr = start_year + y - 1
                    pidx = 0 if y <= 10 else 1 if y <= 20 else 2
                    
                    c_f_p = edited_scenario.iloc[pidx]['Fuel Price ($/ton)']
                    c_e_p = sp["eua_price"] * (1.0 if pidx==0 else 1.3 if pidx==1 else 1.6) if sp["eua_price"] is not None else edited_scenario.iloc[pidx]['EU-ETS Price ($/ton)']
                    c_i_l = sp["imo_levy"] * (1.0 if pidx==0 else 1.5 if pidx==1 else 2.0) if sp["imo_levy"] is not None else edited_scenario.iloc[pidx]['IMO Levy ($/ton)']
                    c_l_r = max(0.0, sp["loan_rate"] - (0.01 if pidx==1 else 0.015 if pidx==2 else 0.0)) if sp["loan_rate"] is not None else edited_scenario.iloc[pidx]['Loan Rate (%)'] / 100
                        
                    f_c_a, f_c_b = sim_foc_a * sim_op_days * c_f_p, sim_foc_b * sim_op_days * c_f_p
                    a_c_a, a_c_b = sim_co2_a * sim_op_days, sim_co2_b * sim_op_days
                    e_m_a, e_m_b = sim_foc_a * sim_op_days * 1000 * FUEL_INFO[fuel]['lhv'], sim_foc_b * sim_op_days * 1000 * FUEL_INFO[fuel]['lhv']
                    
                    e_a, e_b = a_c_a * sp["eu_ratio"] * c_e_p, a_c_b * sp["eu_ratio"] * c_e_p
                    i_a = a_c_a * sim_non_eu_ratio * c_i_l if cal_yr >= 2028 else 0
                    i_b = a_c_b * sim_non_eu_ratio * c_i_l if cal_yr >= 2028 else 0
                    
                    tgt_int = get_fueleu_target(cal_yr)
                    defic = FUEL_INFO[fuel]['wtw_intensity'] - tgt_int
                    p_f_u = (2400 * EUR_TO_USD) / (41000 * 91.16)
                    
                    pen_a = pen_b = 0
                    if defic > 0:
                        c_y_a += 1; c_y_b += 1
                        pen_a = (defic * e_m_a) * p_f_u * (1.0 + (c_y_a - 1) * 0.1) * sp["eu_ratio"]
                        pen_b = (defic * e_m_b) * p_f_u * (1.0 + (c_y_b - 1) * 0.1) * sp["eu_ratio"]
                    else:
                        c_y_a = c_y_b = 0
                        
                    p_sav = (f_c_b + e_b + i_b + pen_b) - (f_c_a + e_a + i_a + pen_a)
                    cum_pure_sav += p_sav
                    
                    if y <= sp["loan_term"]:
                        i_pay = rem_l * c_l_r
                        l_pay = prin_pay + i_pay
                        tot_int += i_pay
                        rem_l -= prin_pay
                    else:
                        l_pay = 0
                        
                    ncf_nom = p_sav - l_pay
                    ncf_dcf = ncf_nom / ((1 + sp["discount_rate"])**y)
                    cum_npv_dcf += ncf_dcf
                    
                    npv_n = cum_npv_dcf - e_diff
                    if sim_bep_npv is None and npv_n >= 0:
                        sim_bep_npv = y
                
                res_dict = {f"{batch_param1}": val1}
                if is_2d: res_dict[f"{batch_param2}"] = val2
                res_dict["최종 NPV ($M)"] = round(npv_n / 1e6, 2)
                res_dict["단순 누적 이익 ($M)"] = round((cum_pure_sav - c_diff) / 1e6, 2)
                res_dict["총 대출이자 지출 ($M)"] = round(tot_int / 1e6, 2)
                res_dict["Daily FOC_A (mt/d)"] = round(sim_foc_a, 2)
                res_dict["Daily CO2_A (mt/d)"] = round(sim_co2_a, 2)
                res_dict["페이백(년)"] = sim_bep_npv if sim_bep_npv else "불가"
                
                return res_dict
            
            # 모든 시나리오 계산 수행
            batch_results = [run_single_sim(v1, v2) for v1, v2 in combinations]
            df_batch = pd.DataFrame(batch_results)
            
            # 지표별 색상 및 텍스트 포맷 설정
            if target_metric in ["최종 NPV ($M)", "단순 누적 이익 ($M)"]:
                c_scale = 'RdYlGn'
                c_map_1d = ['#ff4b4b' if val < 0 else '#00CC96' for val in df_batch[target_metric]]
                txt_template = "%{text:.2f}"
            elif target_metric == "페이백(년)":
                c_scale = 'RdYlGn_r'  # 페이백은 짧을수록(낮을수록) 좋으므로 Reverse 컬러맵 적용
                c_map_1d = ['#ff4b4b' if str(val) == "불가" else '#00CC96' for val in df_batch[target_metric]]
                txt_template = "%{text}"
            else:
                c_scale = 'Reds' if target_metric == "총 대출이자 지출 ($M)" else 'Blues'
                c_map_1d = ['#1f77b4'] * len(df_batch)  
                txt_template = "%{text:.2f}"
            
            if not is_2d:
                # --- 1D 막대 그래프 ---
                st.markdown(f"**✅ '{batch_param1}' 변화에 따른 [{target_metric}] 비교**")
                st.dataframe(df_batch, use_container_width=True)
                
                # "불가" 문자열이 섞여있을 때 Plotly 바 차트 오류 방지를 위해 임시로 Y값을 0으로 치환 (라벨은 그대로 유지)
                y_vals = df_batch[target_metric].replace("불가", 0) if target_metric == "페이백(년)" else df_batch[target_metric]
                
                fig_batch = go.Figure()
                fig_batch.add_trace(go.Bar(
                    x=[str(v) for v in df_batch[f"{batch_param1}"]], 
                    y=y_vals, 
                    text=df_batch[target_metric],
                    texttemplate=txt_template,
                    textposition='auto', marker_color=c_map_1d, name=target_metric
                ))
                fig_batch.update_layout(title=f"'{batch_param1}' 변화에 따른 {target_metric} 비교",
                                        xaxis_title=batch_param1, yaxis_title=target_metric)
                st.plotly_chart(fig_batch, use_container_width=True)
            
            else:
                # --- 2D 히트맵 ---
                st.markdown(f"**✅ '{batch_param1}' & '{batch_param2}' 조합 시나리오 [{target_metric}] 히트맵**")
                
                # 피벗 테이블 생성 (Y축: 변수2, X축: 변수1)
                pivot_df = df_batch.pivot(index=f"{batch_param2}", columns=f"{batch_param1}", values=target_metric)
                
                # "불가" 문자열은 렌더링 시 최악의 색상(빨간색)을 띄도록 999로 치환
                z_vals = pivot_df.replace("불가", 999).values if target_metric == "페이백(년)" else pivot_df.values
                
                # 히트맵 그리기
                fig_heat = go.Figure(data=go.Heatmap(
                    z=z_vals,
                    x=[str(c) for c in pivot_df.columns],
                    y=[str(r) for r in pivot_df.index],
                    colorscale=c_scale, 
                    text=pivot_df.values,
                    texttemplate=txt_template, 
                    showscale=True,
                    colorbar=dict(title="")
                ))
                
                fig_heat.update_layout(
                    title=f"[{target_metric}] 민감도 분석: {batch_param1} vs {batch_param2}",
                    xaxis_title=batch_param1,
                    yaxis_title=batch_param2,
                    margin=dict(l=20, r=20, t=40, b=20)
                )
                st.plotly_chart(fig_heat, use_container_width=True)
                
                with st.expander("결과 데이터 표(Table)로 전체 항목 보기"):
                    st.dataframe(pivot_df, use_container_width=True)
            
        except Exception as e:
            st.error("입력값이 올바르지 않거나 중복된 변수를 선택했습니다. 쉼표(,)와 숫자를 올바르게 입력하고, 서로 다른 두 변수를 선택해 주세요.")
