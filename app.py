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
    
    st.caption("📊 모델 정확도 편차 설정 (±%)")
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        a_unc_des = st.slider("Design 오차 (A)", 0.0, 20.0, 5.0, 0.5)
    with col_u2:
        a_unc_bal = st.slider("Ballast 오차 (A)", 0.0, 20.0, 5.0, 0.5)

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
    
    st.caption("📊 모델 정확도 편차 설정 (±%)")
    col_u3, col_u4 = st.columns(2)
    with col_u3:
        b_unc_des = st.slider("Design 오차 (B)", 0.0, 20.0, 5.0, 0.5)
    with col_u4:
        b_unc_bal = st.slider("Ballast 오차 (B)", 0.0, 20.0, 5.0, 0.5)

# --- 3. 핵심 계산 로직 (불확도 통합) ---
def calc_metrics_with_unc(v, d_a, d_b, b_a, b_b, gen_p, fuel_type, unc_d, unc_b):
    p_des = d_a * (v ** d_b)
    p_bal = b_a * (v ** b_b)
    
    p_des_max = p_des * (1 + unc_d/100)
    p_des_min = p_des * (1 - unc_d/100)
    p_bal_max = p_bal * (1 + unc_b/100)
    p_bal_min = p_bal * (1 - unc_b/100)
    
    p_avg_base = (p_des + p_bal) / 2
    p_avg_max = (p_des_max + p_bal_max) / 2
    p_avg_min = (p_des_min + p_bal_min) / 2
    
    sfoc = FUEL_INFO[fuel_type]['sfoc']
    
    foc_base = ((p_avg_base + gen_p) * sfoc * 24) / 1e6
    foc_max = ((p_avg_max + gen_p) * sfoc * 24) / 1e6
    foc_min = ((p_avg_min + gen_p) * sfoc * 24) / 1e6
    
    return p_avg_base, p_avg_min, p_avg_max, foc_base, foc_min, foc_max

p_me_a, p_a_min, p_a_max, foc_a_base, foc_a_min, foc_a_max = calc_metrics_with_unc(v_target, a_des_a, a_des_b, a_bal_a, a_bal_b, a_gen_power, fuel, a_unc_des, a_unc_bal)
p_me_b, p_b_min, p_b_max, foc_b_base, foc_b_min, foc_b_max = calc_metrics_with_unc(v_target, b_des_a, b_des_b, b_bal_a, b_bal_b, b_gen_power, fuel, b_unc_des, b_unc_bal)

co2_a_base = foc_a_base * FUEL_INFO[fuel]['cf']
co2_a_min = foc_a_min * FUEL_INFO[fuel]['cf']
co2_a_max = foc_a_max * FUEL_INFO[fuel]['cf']

co2_b_base = foc_b_base * FUEL_INFO[fuel]['cf']
co2_b_min = foc_b_min * FUEL_INFO[fuel]['cf']
co2_b_max = foc_b_max * FUEL_INFO[fuel]['cf']

# --- 4. 시뮬레이션 및 규제, 금융, 할인율, 오차 통합 ---
st.title("📊 Ship Efficiency & OPEX Comparison (NPV Uncertainty & Confidence Interval)")

current_base_price = FUEL_INFO[fuel]['base_price']
scenario_data = pd.DataFrame({
    "Period": ["Year 1-10", "Year 11-20", "Year 21-30"], 
    "Fuel Price ($/ton)": [int(current_base_price), int(current_base_price*(1.02**10)), int(current_base_price*(1.02**20))],
    "EU-ETS Price ($/ton)": [int(eua_price_base), int(eua_price_base*1.3), int(eua_price_base*1.6)],
    "IMO Levy ($/ton)": [int(imo_levy_base), int(imo_levy_base*1.5), int(imo_levy_base*2.0)],
    "Loan Rate (%)": [loan_rate_base*100, max(0.0, loan_rate_base*100-1.0), max(0.0, loan_rate_base*100-1.5)]
})

with st.expander("📈 장기 거시경제 시나리오 (Macro-Economic Scenario)", expanded=False):
    edited_scenario = st.data_editor(scenario_data, use_container_width=True)

capex_diff = (a_capex - b_capex) * 1e6
loan_diff = capex_diff * ltv
equity_diff = capex_diff * (1 - ltv)

results = []
cum_pure_saving_base = cum_pure_saving_best = cum_pure_saving_worst = 0
cum_nominal_ncf_base = 0  # 명목이익 선을 위한 누적 NCF 변수 추가
cum_npv_dcf_base = cum_npv_dcf_best = cum_npv_dcf_worst = 0

bep_year_npv_base = bep_year_npv_best = bep_year_npv_worst = None
start_year = 2026
EUR_TO_USD = 1.1

rem_loan_diff = loan_diff
total_interest_diff = 0
principal_payment = loan_diff / loan_term if loan_term > 0 else 0

cons_years_penalty = 0

def calc_opex_fixed(foc, sim_year, c_f_p, c_e_p, c_i_l, eu_r, non_eu_r, consec_yrs):
    fuel_cost = foc * op_days * c_f_p
    ann_co2 = foc * FUEL_INFO[fuel]['cf'] * op_days
    energy_mj = foc * op_days * 1000 * FUEL_INFO[fuel]['lhv']
    
    ets = ann_co2 * eu_r * c_e_p
    imo = ann_co2 * non_eu_r * c_i_l if sim_year >= 2028 else 0
    
    tgt_int = get_fueleu_target(sim_year)
    defic = FUEL_INFO[fuel]['wtw_intensity'] - tgt_int
    p_f_u = (2400 * EUR_TO_USD) / (41000 * 91.16)
    
    pen = 0
    if defic > 0:
        pen = (defic * energy_mj) * p_f_u * (1.0 + (consec_yrs - 1) * 0.1) * eu_r
        
    return fuel_cost + ets + imo + pen

for y in range(1, sim_years + 1):
    cal_year = start_year + y - 1
    pidx = 0 if y <= 10 else 1 if y <= 20 else 2
    
    c_f_p = edited_scenario.iloc[pidx]['Fuel Price ($/ton)']
    c_e_p = edited_scenario.iloc[pidx]['EU-ETS Price ($/ton)']
    c_i_l = edited_scenario.iloc[pidx]['IMO Levy ($/ton)']
    c_l_r = edited_scenario.iloc[pidx]['Loan Rate (%)'] / 100
    
    tgt_int = get_fueleu_target(cal_year)
    defic = FUEL_INFO[fuel]['wtw_intensity'] - tgt_int
    if defic > 0: cons_years_penalty += 1
    else: cons_years_penalty = 0
    
    opex_a_base = calc_opex_fixed(foc_a_base, cal_year, c_f_p, c_e_p, c_i_l, eu_ratio, non_eu_ratio, cons_years_penalty)
    opex_b_base = calc_opex_fixed(foc_b_base, cal_year, c_f_p, c_e_p, c_i_l, eu_ratio, non_eu_ratio, cons_years_penalty)
    
    opex_a_min = calc_opex_fixed(foc_a_min, cal_year, c_f_p, c_e_p, c_i_l, eu_ratio, non_eu_ratio, cons_years_penalty)
    opex_a_max = calc_opex_fixed(foc_a_max, cal_year, c_f_p, c_e_p, c_i_l, eu_ratio, non_eu_ratio, cons_years_penalty)
    opex_b_min = calc_opex_fixed(foc_b_min, cal_year, c_f_p, c_e_p, c_i_l, eu_ratio, non_eu_ratio, cons_years_penalty)
    opex_b_max = calc_opex_fixed(foc_b_max, cal_year, c_f_p, c_e_p, c_i_l, eu_ratio, non_eu_ratio, cons_years_penalty)
    
    pure_saving_base = opex_b_base - opex_a_base
    pure_saving_best = opex_b_max - opex_a_min
    pure_saving_worst = opex_b_min - opex_a_max
    
    cum_pure_saving_base += pure_saving_base
    
    if y <= loan_term:
        interest_payment = rem_loan_diff * c_l_r
        loan_payment = principal_payment + interest_payment
        total_interest_diff += interest_payment
        rem_loan_diff -= principal_payment
    else:
        loan_payment = 0
        
    ncf_nom_base = pure_saving_base - loan_payment
    cum_nominal_ncf_base += ncf_nom_base
    net_profit_nominal_base = cum_nominal_ncf_base - equity_diff
        
    ncf_dcf_base = ncf_nom_base / ((1 + discount_rate)**y)
    ncf_dcf_best = (pure_saving_best - loan_payment) / ((1 + discount_rate)**y)
    ncf_dcf_worst = (pure_saving_worst - loan_payment) / ((1 + discount_rate)**y)
    
    cum_npv_dcf_base += ncf_dcf_base
    cum_npv_dcf_best += ncf_dcf_best
    cum_npv_dcf_worst += ncf_dcf_worst
    
    npv_base = cum_npv_dcf_base - equity_diff
    npv_best = cum_npv_dcf_best - equity_diff
    npv_worst = cum_npv_dcf_worst - equity_diff
    
    if bep_year_npv_base is None and npv_base >= 0: bep_year_npv_base = y
    if bep_year_npv_best is None and npv_best >= 0: bep_year_npv_best = y
    if bep_year_npv_worst is None and npv_worst >= 0: bep_year_npv_worst = y
        
    results.append({
        "Calendar_Year": cal_year,
        "Net_Profit_Pure": cum_pure_saving_base - capex_diff,
        "Net_Profit_Nominal_Base": net_profit_nominal_base,
        "Net_Profit_NPV_Base": npv_base,
        "Net_Profit_NPV_Best": npv_best,
        "Net_Profit_NPV_Worst": npv_worst
    })

df_res = pd.DataFrame(results)

# --- 5. UI 메트릭 ---
def render_range_html(min_v, max_v, fmt="%.1f", unit=""):
    return f"<div style='font-size: 13px; color: #808495; margin-top: -3px;'>📉 범위: {fmt % min_v}{unit} ~ {fmt % max_v}{unit}</div>"

def render_empty_html():
    return "<div style='font-size: 13px; color: #808495; margin-top: -3px;'>&nbsp;</div>"

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.metric("총 CAPEX 차액 (A-B)", f"$ {capex_diff/1e6:.1f} M")
    st.markdown(render_empty_html(), unsafe_allow_html=True)
with m2:
    st.metric("Power Base (Ship A)", f"{p_me_a:.1f} kW")
    st.markdown(render_range_html(p_a_min, p_a_max, "%.1f", " kW"), unsafe_allow_html=True)
with m3:
    foc_diff_pct = ((foc_a_base - foc_b_base) / foc_b_base) * 100 if foc_b_base > 0 else 0
    st.metric("Total Daily FOC (Ship A)", f"{foc_a_base:.2f} mt/d", delta=f"{foc_diff_pct:.1f}%", delta_color="inverse")
    st.markdown(render_range_html(foc_a_min, foc_a_max, "%.2f", " mt/d"), unsafe_allow_html=True)
with m4:
    co2_diff_pct = ((co2_a_base - co2_b_base) / co2_b_base) * 100 if co2_b_base > 0 else 0
    st.metric("Daily CO2 (Ship A)", f"{co2_a_base:.1f} mt/d", delta=f"{co2_diff_pct:.1f}%" if co2_b_base > 0 else None, delta_color="inverse")
    st.markdown(render_range_html(co2_a_min, co2_a_max, "%.1f", " mt/d"), unsafe_allow_html=True)
with m5:
    final_npv_base = df_res['Net_Profit_NPV_Base'].iloc[-1]
    final_npv_best = df_res['Net_Profit_NPV_Best'].iloc[-1]
    final_npv_worst = df_res['Net_Profit_NPV_Worst'].iloc[-1]
    st.metric(f"🎯 {sim_years}년 최종 NPV", f"$ {final_npv_base/1e6:.1f} M")
    st.markdown(render_range_html(final_npv_worst/1e6, final_npv_best/1e6, "%.1f", " M"), unsafe_allow_html=True)

st.write("")

m6, m7, m8, m9, m10 = st.columns(5)
with m6:
    st.metric("자기자본 투입 차액", f"$ {equity_diff/1e6:.1f} M")
    st.markdown(render_empty_html(), unsafe_allow_html=True)
with m7:
    st.metric("Power Base (Ship B)", f"{p_me_b:.1f} kW")
    st.markdown(render_range_html(p_b_min, p_b_max, "%.1f", " kW"), unsafe_allow_html=True)
with m8:
    st.metric("Total Daily FOC (Ship B)", f"{foc_b_base:.2f} mt/d")
    st.markdown(render_range_html(foc_b_min, foc_b_max, "%.2f", " mt/d"), unsafe_allow_html=True)
with m9:
    st.metric("Daily CO2 (Ship B)", f"{co2_b_base:.1f} mt/d")
    st.markdown(render_range_html(co2_b_min, co2_b_max, "%.1f", " mt/d"), unsafe_allow_html=True)
with m10:
    payback_text = f"{bep_year_npv_base} 년" if bep_year_npv_base else f"불가 ({sim_years}년 내)"  
    st.metric("🎯 Base 페이백 (NPV 기준)", payback_text)
    best_str = f"{bep_year_npv_best}년" if bep_year_npv_best else "불가"
    worst_str = f"{bep_year_npv_worst}년" if bep_year_npv_worst else "불가"
    st.markdown(f"<div style='font-size: 13px; color: #808495; margin-top: -3px;'>📉 범위: {best_str} ~ {worst_str}</div>", unsafe_allow_html=True)

# --- 재무적 손실 요인 가시화 ---
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
    discount_loss = df_res['Net_Profit_Nominal_Base'].iloc[-1] - df_res['Net_Profit_NPV_Base'].iloc[-1]
    st.warning(f"**2. 시간가치 하락분 (할인율)**\n\n미래에 발생할 절감액을 현재 가치로 할인했을 때 증발한 금액입니다.\n\n### - $ {discount_loss/1e6:.1f} M")
with fm3:
    pure_profit = df_res['Net_Profit_Pure'].iloc[-1]
    st.success(f"**3. 실질 순이익 (최종 NPV)**\n\n단순 절감액에서 이자 비용과 시간가치 하락분을 뺀 진짜 이익입니다.\n\n### $ {final_npv_base/1e6:.1f} M")

# 불확실성 범위 강조 박스 추가
st.divider()
st.subheader("💡 선속-마력 모델 정확도를 반영한 수익 편차 (Uncertainty Range)")
st.info(f"**최종 예상 NPV (평균): $ {final_npv_base/1e6:.1f} M**\n\n설정하신 모델 피팅 오차를 고려할 때, 이 투자 프로젝트의 실제 수익은 최악의 경우 **$ {final_npv_worst/1e6:.1f} M** 에서 최상의 경우 **$ {final_npv_best/1e6:.1f} M** 사이에서 형성될 확률이 높습니다.")

st.divider()

# --- 6. 시각화 (상단 오차 밴드 그림자 그래프 + 명목이익 선 부활) ---
c1, c2, c3 = st.columns([2, 1, 1])

with c1:
    st.subheader("📈 Profit Curve: 모델 신뢰 구간(Confidence Interval) 포함")
    fig = go.Figure()
    
    # 1. 단순 OPEX 누적이익 (점선)
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit_Pure'], mode='lines', name='단순 OPEX 누적이익', line=dict(color='gray', width=2, dash='dash')))
    
    # 2. 명목 이익 (연두색 실선 - 부활)
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit_Nominal_Base'], mode='lines', name='명목 이익 (대출이자 차감)', line=dict(color='#82C59D', width=2)))
    
    # 3. NPV 불확도 범위 (그림자 밴드)
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit_NPV_Worst'], mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit_NPV_Best'], mode='lines', fill='tonexty', fillcolor='rgba(0, 204, 150, 0.2)', line=dict(width=0), name='NPV 예상 편차범위 (Range)'))
    
    # 4. 최종 NPV Base (진한 녹색 실선)
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit_NPV_Base'], mode='lines', name='최종 NPV (순현재가치)', line=dict(color='#00CC96', width=4)))
    
    # Break-even 별표 마커
    if bep_year_npv_base:
        cal_bep_year = start_year + bep_year_npv_base - 1
        bep_profit = df_res.loc[df_res['Calendar_Year'] == cal_bep_year, 'Net_Profit_NPV_Base'].values[0]
        fig.add_trace(go.Scatter(x=[cal_bep_year], y=[bep_profit], mode='markers+text', name='NPV Break-even', text=[f"  {bep_year_npv_base}년 소요"], textposition="top left", marker=dict(color='gold', size=15, symbol='star', line=dict(width=2, color='black'))))
        
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

# --- 7. 하단: 환경 규제 분석 (Base 기준) ---
st.divider()
end_year = start_year + sim_years - 1
st.subheader(f"🌍 탄소 규제 페널티 추이 분석 ({start_year} ~ {end_year}, Base 기준)")

c4, c5 = st.columns(2)
with c4:
    fig_pen = go.Figure()
    ann_co2_a_base = foc_a_base * FUEL_INFO[fuel]['cf'] * op_days
    ann_co2_b_base = foc_b_base * FUEL_INFO[fuel]['cf'] * op_days
    e_m_a_base = foc_a_base * op_days * 1000 * FUEL_INFO[fuel]['lhv']
    e_m_b_base = foc_b_base * op_days * 1000 * FUEL_INFO[fuel]['lhv']
    
    res_env = []
    cy_pen = 0
    for y in range(1, sim_years + 1):
        cal_yr = start_year + y - 1
        pidx = 0 if y <= 10 else 1 if y <= 20 else 2
        c_e_p = edited_scenario.iloc[pidx]['EU-ETS Price ($/ton)']
        c_i_l = edited_scenario.iloc[pidx]['IMO Levy ($/ton)']
        
        ets_a = ann_co2_a_base * eu_ratio * c_e_p
        imo_a = ann_co2_a_base * non_eu_ratio * c_i_l if cal_yr >= 2028 else 0
        ets_b = ann_co2_b_base * eu_ratio * c_e_p
        imo_b = ann_co2_b_base * non_eu_ratio * c_i_l if cal_yr >= 2028 else 0
        
        tgt = get_fueleu_target(cal_yr)
        dfc = FUEL_INFO[fuel]['wtw_intensity'] - tgt
        pfu = (2400 * 1.1) / (41000 * 91.16)
        
        p_a = p_b = 0
        if dfc > 0:
            cy_pen += 1
            p_a = (dfc * e_m_a_base) * pfu * (1.0 + (cy_pen - 1) * 0.1) * eu_ratio
            p_b = (dfc * e_m_b_base) * pfu * (1.0 + (cy_pen - 1) * 0.1) * eu_ratio
        else:
            cy_pen = 0
            
        res_env.append({"CY": cal_yr, "EA": ets_a, "IA": imo_a, "FA": p_a, "EB": ets_b, "IB": imo_b, "FB": p_b, "TGT": tgt})
        
    df_env = pd.DataFrame(res_env)

    fig_pen.add_trace(go.Bar(x=df_env['CY'], y=df_env['EA'], name='EU-ETS (A)', marker_color='#91bceb', offsetgroup=1))
    fig_pen.add_trace(go.Bar(x=df_env['CY'], y=df_env['IA'], name='IMO Levy (A)', marker_color='#1f77b4', offsetgroup=1, base=df_env['EA']))
    fig_pen.add_trace(go.Bar(x=df_env['CY'], y=df_env['FA'], name='FuelEU Penalty (A)', marker_color='#08306b', offsetgroup=1, base=df_env['EA']+df_env['IA']))
    fig_pen.add_trace(go.Bar(x=df_env['CY'], y=df_env['EB'], name='EU-ETS (B)', marker_color='#fdcdac', offsetgroup=2))
    fig_pen.add_trace(go.Bar(x=df_env['CY'], y=df_env['IB'], name='IMO Levy (B)', marker_color='#ff7f0e', offsetgroup=2, base=df_env['EB']))
    fig_pen.add_trace(go.Bar(x=df_env['CY'], y=df_env['FB'], name='FuelEU Penalty (B)', marker_color='#7f2704', offsetgroup=2, base=df_env['EB']+df_env['IB']))
    fig_pen.update_layout(barmode='group', xaxis_title="Calendar Year", yaxis_title="Penalty Cost ($)", hovermode="x unified")
    st.plotly_chart(fig_pen, use_container_width=True)

with c5:
    st.markdown("**온실가스 집약도(GHG Intensity) 규제 한계선**")
    fig_limit = go.Figure()
    fig_limit.add_trace(go.Scatter(x=df_env['CY'], y=df_env['TGT'], mode='lines+markers', name='Target Limit', line=dict(color='red', width=3, dash='dash')))
    fig_limit.add_hline(y=FUEL_INFO[fuel]['wtw_intensity'], line_dash="solid", line_color="black", annotation_text=f"Selected Fuel ({fuel}): {FUEL_INFO[fuel]['wtw_intensity']}", annotation_position="top right")
    fig_limit.update_layout(xaxis_title="Calendar Year", yaxis_title="GHG Intensity (gCO2eq/MJ)")
    st.plotly_chart(fig_limit, use_container_width=True)

# --- 8. 민감도 분석 (Batch 시뮬레이션 확장판: 1D & 2D) ---
st.divider()
st.header("🔄 민감도 분석 (Batch 시뮬레이션 확장판)")
st.markdown("선박 효율, 금융, 규제 등 핵심 파라미터 조합이 **원하는 출력 지표**에 미치는 영향을 시뮬레이션합니다. (Base 모델 기준 적용)")

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
                
                _, _, _, s_foc_a, _, _ = calc_metrics_with_unc(sp["v_target"], a_des_a, a_des_b, a_bal_a, a_bal_b, sp["a_gen"], fuel, a_unc_des, a_unc_bal)
                _, _, _, s_foc_b, _, _ = calc_metrics_with_unc(sp["v_target"], b_des_a, b_des_b, b_bal_a, b_bal_b, sp["b_gen"], fuel, b_unc_des, b_unc_bal)
                
                s_co2_a = s_foc_a * FUEL_INFO[fuel]['cf']
                s_co2_b = s_foc_b * FUEL_INFO[fuel]['cf']
                
                c_diff = (sp["a_capex"] - sp["b_capex"]) * 1e6
                l_diff = c_diff * sp["ltv"]
                e_diff = c_diff * (1 - sp["ltv"])
                
                rem_l = l_diff
                tot_int = 0
                prin_pay = l_diff / sp["loan_term"] if sp["loan_term"] > 0 else 0
                
                cum_pure_sav = 0
                cum_npv_dcf = 0
                s_bep = None
                cy_p = 0
                
                for y in range(1, sp["sim_years"] + 1):
                    cal_yr = start_year + y - 1
                    pidx = 0 if y <= 10 else 1 if y <= 20 else 2
                    
                    c_f_p = edited_scenario.iloc[pidx]['Fuel Price ($/ton)']
                    c_e_p = sp["eua_price"] * (1.0 if pidx==0 else 1.3 if pidx==1 else 1.6) if sp["eua_price"] is not None else edited_scenario.iloc[pidx]['EU-ETS Price ($/ton)']
                    c_i_l = sp["imo_levy"] * (1.0 if pidx==0 else 1.5 if pidx==1 else 2.0) if sp["imo_levy"] is not None else edited_scenario.iloc[pidx]['IMO Levy ($/ton)']
                    c_l_r = max(0.0, sp["loan_rate"] - (0.01 if pidx==1 else 0.015 if pidx==2 else 0.0)) if sp["loan_rate"] is not None else edited_scenario.iloc[pidx]['Loan Rate (%)'] / 100
                        
                    f_c_a, f_c_b = s_foc_a * sim_op_days * c_f_p, s_foc_b * sim_op_days * c_f_p
                    a_c_a, a_c_b = s_co2_a * sim_op_days, s_co2_b * sim_op_days
                    e_m_a, e_m_b = s_foc_a * sim_op_days * 1000 * FUEL_INFO[fuel]['lhv'], s_foc_b * sim_op_days * 1000 * FUEL_INFO[fuel]['lhv']
                    
                    e_a, e_b = a_c_a * sp["eu_ratio"] * c_e_p, a_c_b * sp["eu_ratio"] * c_e_p
                    i_a = a_c_a * sim_non_eu_ratio * c_i_l if cal_yr >= 2028 else 0
                    i_b = a_c_b * sim_non_eu_ratio * c_i_l if cal_yr >= 2028 else 0
                    
                    tgt_int = get_fueleu_target(cal_yr)
                    defic = FUEL_INFO[fuel]['wtw_intensity'] - tgt_int
                    p_f_u = (2400 * EUR_TO_USD) / (41000 * 91.16)
                    
                    pen_a = pen_b = 0
                    if defic > 0:
                        cy_p += 1
                        pen_a = (defic * e_m_a) * p_f_u * (1.0 + (cy_p - 1) * 0.1) * sp["eu_ratio"]
                        pen_b = (defic * e_m_b) * p_f_u * (1.0 + (cy_p - 1) * 0.1) * sp["eu_ratio"]
                    else:
                        cy_p = 0
                        
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
                    if s_bep is None and npv_n >= 0:
                        s_bep = y
                
                res_dict = {f"{batch_param1}": val1}
                if is_2d: res_dict[f"{batch_param2}"] = val2
                res_dict["최종 NPV ($M)"] = round(npv_n / 1e6, 2)
                res_dict["단순 누적 이익 ($M)"] = round((cum_pure_sav - c_diff) / 1e6, 2)
                res_dict["총 대출이자 지출 ($M)"] = round(tot_int / 1e6, 2)
                res_dict["Daily FOC_A (mt/d)"] = round(s_foc_a, 2)
                res_dict["Daily CO2_A (mt/d)"] = round(s_co2_a, 2)
                res_dict["페이백(년)"] = s_bep if s_bep else "불가"
                
                return res_dict
            
            # 모든 시나리오 계산 수행
            batch_results = [run_single_sim(v1, v2) for v1, v2 in combinations]
            df_batch = pd.DataFrame(batch_results)
            
            if target_metric in ["최종 NPV ($M)", "단순 누적 이익 ($M)"]:
                c_scale = 'RdYlGn'
                c_map_1d = ['#ff4b4b' if val < 0 else '#00CC96' for val in df_batch[target_metric]]
                txt_template = "%{text:.2f}"
            elif target_metric == "페이백(년)":
                c_scale = 'RdYlGn_r'  
                c_map_1d = ['#ff4b4b' if str(val) == "불가" else '#00CC96' for val in df_batch[target_metric]]
                txt_template = "%{text}"
            else:
                c_scale = 'Reds' if target_metric == "총 대출이자 지출 ($M)" else 'Blues'
                c_map_1d = ['#1f77b4'] * len(df_batch)  
                txt_template = "%{text:.2f}"
            
            if not is_2d:
                st.markdown(f"**✅ '{batch_param1}' 변화에 따른 [{target_metric}] 비교**")
                st.dataframe(df_batch, use_container_width=True)
                
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
                st.markdown(f"**✅ '{batch_param1}' & '{batch_param2}' 조합 시나리오 [{target_metric}] 히트맵**")
                
                pivot_df = df_batch.pivot(index=f"{batch_param2}", columns=f"{batch_param1}", values=target_metric)
                z_vals = pivot_df.replace("불가", 999).values if target_metric == "페이백(년)" else pivot_df.values
                
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
