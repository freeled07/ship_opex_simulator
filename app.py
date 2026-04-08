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
    st.header("🌍 환경 규제 파라미터")
    eu_ratio = st.slider("EU 기항 비율 (%)", 0, 100, 30) / 100
    non_eu_ratio = 1.0 - eu_ratio
    st.caption(f"※ EU 규제(ETS, FuelEU) {eu_ratio*100:.0f}% 적용")
    st.caption(f"※ 비-EU 구간({non_eu_ratio*100:.0f}%) IMO 탄소세 적용")
    
    eua_price = st.number_input("EU-ETS 탄소단가 ($/ton)", value=100)
    imo_levy = st.number_input("IMO 탄소세 ($/ton, 2028 발효 가정)", value=50)

    st.divider()
    st.subheader("🚢 Ship A (KOR)")
    # HHI -> Yard_A
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
    # SWS -> Yard_C
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

# --- 4. 30년 시뮬레이션 및 규제 페널티 통합 ---
st.title("📊 Ship Efficiency & OPEX Comparison (Incl. Carbon Penalty)")

current_base_price = FUEL_INFO[fuel]['base_price']
price_data = pd.DataFrame({"Period": ["Year 1-10", "Year 11-20", "Year 21-30"], 
                           "Price ($/ton)": [int(current_base_price), int(current_base_price*(1.02**10)), int(current_base_price*(1.02**20))]})
with st.expander("💰 Fuel Price Scenario (Edit to change)", expanded=False):
    edited_price = st.data_editor(price_data, use_container_width=True)

results = []
cum_saving = 0
capex_diff = (a_capex - b_capex) * 1e6
bep_year_idx = None
start_year = 2026

cons_years_a = 0
cons_years_b = 0
EUR_TO_USD = 1.1

for y in range(1, 31):
    cal_year = start_year + y - 1
    price = edited_price.iloc[0 if y<=10 else 1 if y<=20 else 2, 1]
    
    fuel_cost_a = foc_a * op_days * price
    fuel_cost_b = foc_b * op_days * price
    
    ann_co2_a, ann_co2_b = co2_a * op_days, co2_b * op_days
    energy_mj_a = foc_a * op_days * 1000 * FUEL_INFO[fuel]['lhv']
    energy_mj_b = foc_b * op_days * 1000 * FUEL_INFO[fuel]['lhv']
    
    ets_a = ann_co2_a * eu_ratio * eua_price
    ets_b = ann_co2_b * eu_ratio * eua_price
    
    imo_a = ann_co2_a * non_eu_ratio * imo_levy if cal_year >= 2028 else 0
    imo_b = ann_co2_b * non_eu_ratio * imo_levy if cal_year >= 2028 else 0
    
    target_intensity = get_fueleu_target(cal_year)
    actual_intensity = FUEL_INFO[fuel]['wtw_intensity']
    deficit = actual_intensity - target_intensity
    penalty_factor_usd = (2400 * EUR_TO_USD) / (41000 * 91.16) 
    
    if deficit > 0:
        cons_years_a += 1
        multiplier_a = 1.0 + (cons_years_a - 1) * 0.1 
        fueleu_pen_a = (deficit * energy_mj_a) * penalty_factor_usd * multiplier_a * eu_ratio
    else:
        cons_years_a = 0
        fueleu_pen_a = 0
        
    if deficit > 0:
        cons_years_b += 1
        multiplier_b = 1.0 + (cons_years_b - 1) * 0.1
        fueleu_pen_b = (deficit * energy_mj_b) * penalty_factor_usd * multiplier_b * eu_ratio
    else:
        cons_years_b = 0
        fueleu_pen_b = 0
    
    total_penalty_a = ets_a + imo_a + fueleu_pen_a
    total_penalty_b = ets_b + imo_b + fueleu_pen_b
    
    opex_a = fuel_cost_a + total_penalty_a
    opex_b = fuel_cost_b + total_penalty_b
    
    yearly_saving = opex_b - opex_a
    cum_saving += yearly_saving
    net_profit = cum_saving - capex_diff
    
    if bep_year_idx is None and net_profit >= 0:
        bep_year_idx = y
        
    results.append({
        "Calendar_Year": cal_year,
        "Year_Index": y,
        "Net_Profit": net_profit, 
        "FuelEU_Target": target_intensity,
        "ETS_A": ets_a, "IMO_A": imo_a, "FuelEU_A": fueleu_pen_a,
        "ETS_B": ets_b, "IMO_B": imo_b, "FuelEU_B": fueleu_pen_b,
        "Total_Penalty_A": total_penalty_a, "Total_Penalty_B": total_penalty_b
    })

df_res = pd.DataFrame(results)
cal_bep_year = start_year + bep_year_idx - 1 if bep_year_idx else None

# --- 5. UI 메트릭 ---
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("CAPEX 차액 (A-B)", f"$ {capex_diff/1e6:.1f} M")
    payback_text = f"{bep_year_idx} 년" if bep_year_idx else "30년 내 불가"
    st.metric("🎯 예상 페이백 기간", payback_text)
with m2:
    foc_diff_pct = ((foc_a - foc_b) / foc_b) * 100 if foc_b > 0 else 0
    st.metric("Total Daily FOC (Ship A)", f"{foc_a:.2f} mt/d", delta=f"{foc_diff_pct:.1f}%", delta_color="inverse")
    st.metric("Total Daily FOC (Ship B)", f"{foc_b:.2f} mt/d")
with m3:
    co2_diff_pct = ((co2_a - co2_b) / co2_b) * 100 if co2_b > 0 else 0
    st.metric("Daily CO2 (Ship A)", f"{co2_a:.1f} mt/d", delta=f"{co2_diff_pct:.1f}%" if co2_b > 0 else None, delta_color="inverse")
    st.metric("Daily CO2 (Ship B)", f"{co2_b:.1f} mt/d")
with m4:
    total_benefit = df_res['Net_Profit'].iloc[-1]
    st.metric("30년 기대 순수익 (페널티 반영)", f"$ {total_benefit/1e6:.1f} M")

st.divider()

# --- 6. 시각화 (상단 3열) ---
c1, c2, c3 = st.columns([2, 1, 1])

with c1:
    st.subheader("📈 Cumulative Net Profit (Fuel + Penalty)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_res['Calendar_Year'], y=df_res['Net_Profit'], fill='tozeroy', name='Net Benefit', line=dict(color='#00CC96', width=4)))
    if cal_bep_year:
        bep_profit = df_res.loc[df_res['Calendar_Year'] == cal_bep_year, 'Net_Profit'].values[0]
        fig.add_trace(go.Scatter(x=[cal_bep_year], y=[bep_profit], mode='markers+text', name='Break-even',
                                 text=[f"  {bep_year_idx}년 소요"], textposition="top right", marker=dict(color='gold', size=15, symbol='star', line=dict(width=2, color='black'))))
    fig.add_hline(y=0, line_dash="dash", line_color="red")
    fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=30, b=20), xaxis_title="Calendar Year")
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

# --- 7. 하단: 환경 규제 분석 ---
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
