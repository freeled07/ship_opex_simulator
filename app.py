import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

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
    loan_rate_base = st.number_input("초기 대출 금리 (Loan Rate, %)", value=6.5, step=0.5)
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

# --- 4. 30년 시뮬레이션 및 규제, 금융, 할인율 통합 ---
st.title("📊 Ship Efficiency & OPEX Comparison (NPV & Loan Applied)")

# 거시경제 시나리오 통합 데이터프레임 구성 (10년 단위 고정)
current_base_price = FUEL_INFO[fuel]['base_price']
scenario_data = pd.DataFrame({
    "Period": ["Year 1-10", "Year 11-20", "Year 21-30"], 
    "Fuel Price ($/ton)": [int(current_base_price), int(current_base_price*(1.02**10)), int(current_base_price*(1.02**20))],
    "EU-ETS Price ($/ton)": [int(eua_price_base), int(eua_price_base*1.3), int(eua_price_base*1.6)],
    "IMO Levy ($/ton)": [int(imo_levy_base), int(imo_levy_base*1.5), int(imo_levy_base*2.0)],
    "Loan Rate (%)": [loan_rate_base, max(0.0, loan_rate_base-1.0), max(0.0, loan_rate_base-1.5)]
})

with st.expander("📈 30년 장기 거시경제 시나리오 (Macro-Economic Scenario) - 수정 가능", expanded=False):
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

# 선박 금융 상환 트래킹 (원금균등상환 방식)
rem_loan_diff = loan_diff
total_interest_diff = 0
principal_payment = loan_diff / loan_term if loan_term > 0 else 0

for y in range(1, 31):
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
    pure_saving = opex_b - opex_a  # 순수 연료비+탄소세 절감액
    cum_pure_saving += pure_saving
    net_profit_pure = cum_pure_saving - capex_diff # 단순 이익 (금융/할인 제외)
    
    # 대출 상환 로직 (변동 금리 + 원금균등상환)
    if y <= loan_term:
        interest_payment = rem_loan_diff * current_loan_rate
        loan_payment = principal_payment + interest_payment
        total_interest_diff += interest_payment
        rem_loan_diff -= principal_payment
    else:
        loan_payment = 0
        
    ncf_nominal = pure_saving - loan_payment # 대출 갚고 남은 명목 순수익
    ncf_dcf = ncf_nominal / ((1 + discount_rate)**y) # 할인율이 적용된 현재가치 수익
    
    cum_nominal_ncf += ncf_nominal
    cum_npv_dcf += ncf_dcf
    
    net_profit_nominal = cum_nominal_ncf - equity_diff # 내 돈 빼고 남은 명목 누적이익
    net_profit_npv = cum_npv_dcf - equity_diff         # 내 돈 빼고 남은 NPV 누적이익
    
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

# --- 5. UI 메트릭 (화살표 오차 해결을 위해 상하 분리 배치) ---
# 윗줄 (Row 1): Ship A 및 기준 데이터 (화살표 포함)
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
    st.metric("30년 최종 NPV (순현재가치)", f"$ {final_npv/1e6:.1f} M")

# 여백 약간 확보
st.write("")

# 아랫줄 (Row 2): Ship B 및 결과 데이터 (화살표 없음)
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
    payback_text = f"{bep_year_npv} 년" if bep_year_npv else "불가 (30년 내)"
    st.metric("🎯 실질 페이백 (NPV 기준)", payback_text)

# --- 6. 재무적 손실 요인 가시화 (CSS 높이 절대 고정 패치) ---
st.divider()
st.subheader("💸 대출 이자 및 인플레이션(할인율)에 의한 수익 증발 요약")

# CSS를 주입하여 알림 박스들의 절대 세로 높이를 200px로 완벽 고정
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
st.subheader("🌍 탄소 규제 페널티 추이 분석 (2026 ~ 2055)")

c4, c5 = st.columns(2)

with c4:
    st.markdown("**항목별/연도별 누적 페널티 비용 분석 (이중과세 방지 적용)**")
    fig_pen = go.Figure()
    
    # Ship A
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['ETS_A'], name='EU-ETS (A)', marker_color='#91bceb', offsetgroup=1))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['IMO_A'], name='IMO Levy (A)', marker_color='#1f77b4', offsetgroup=1, base=df_res['ETS_A']))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['FuelEU_A'], name='FuelEU Penalty (A)', marker_color='#08306b', offsetgroup=1, base=df_res['ETS_A']+df_res['IMO_A']))
    
    # Ship B
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['ETS_B'], name='EU-ETS (B)', marker_color='#fdcdac', offsetgroup=2))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['IMO_B'], name='IMO Levy (B)', marker_color='#ff7f0e', offsetgroup=2, base=df_res['ETS_B']))
    fig_pen.add_trace(go.Bar(x=df_res['Calendar_Year'], y=df_res['FuelEU_B'], name='FuelEU Penalty (B)', marker_color='#7f2704', offsetgroup=2, base=df_res['ETS_B']+df_res['IMO_B']))
    
    fig_pen.update_layout(barmode='group', xaxis_title="Calendar Year", yaxis_title="Penalty Cost ($)", hovermode="x unified")
    st.plotly_chart(fig_pen, use_container_width=True)

with c5:
    st.markdown("**온실가스 집약도(GHG Intensity) 규제 한계선**")
    fig_limit = go.Figure()
    fig_limit.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['FuelEU_Target'], 
                                   mode='lines+markers', name='Target Limit', line=dict(color='red', width=3, dash='dash')))
    fig_limit.add_hline(y=FUEL_INFO[fuel]['wtw_intensity'], line_dash="solid", line_color="black", 
                        annotation_text=f"Selected Fuel ({fuel}): {FUEL_INFO[fuel]['wtw_intensity']}", annotation_position="top right")
    fig_limit.update_layout(xaxis_title="Calendar Year", yaxis_title="GHG Intensity (gCO2eq/MJ)")
    st.plotly_chart(fig_limit, use_container_width=True)

with st.expander("📝 Detailed Simulation Data"):
    st.dataframe(df_res.set_index("Calendar_Year").drop(columns=['Year_Index'], errors='ignore'), use_container_width=True)
