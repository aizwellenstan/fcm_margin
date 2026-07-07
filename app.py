import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# 設定網頁標題與排版
st.set_page_config(page_title="期貨商保證金存款策略模擬器", layout="wide")
st.title("🏛️ 期貨商（FCM）保證金存款與流動性最佳化模擬器")
st.write(
    "本模擬器專為期貨商財務風控設計，評估在滿足「客戶保證金出金流動性」與「交易所追繳」前提下，如何極大化大額定期存款收益。"
)

# --- 側邊欄：法人級參數設定 ---
st.sidebar.header("⚙️ 財務與風控參數設定")
total_margin = st.sidebar.number_input(
    "管理總保證金規模 (TWD)",
    min_value=100000000,
    value=5000000000,
    step=100000000,
    format="%d",
    help="期貨商目前擁有的客戶保證金與專戶總額（預設50億）",
)

buffer_ratio = st.sidebar.slider(
    "每日活期留存緩衝金比例 (%)",
    min_value=5.0,
    max_value=40.0,
    value=20.0,
    step=2.5,
    help="留在活期專戶以應付每日正常出金與結算作業的資金比例。其餘 (100% - 緩衝比例) 將配置於定存。",
)

stress_scenario = st.sidebar.selectbox(
    "🚨 流動性壓力測試情境 (市場黑天鵝)",
    ["正常市況 (無突發大額出金)", "中度風險 (突發出金 15%)", "極度風險 (斷頭潮/客戶擠兌 35%)"],
)

st.sidebar.subheader("💰 2026 大額定存牌告年利率 (%)")
st.sidebar.caption("註：大額存款（如新台幣五百萬以上）利率通常較一般存款低")
rate_1m = st.sidebar.number_input(
    "1M 大額定存年利率 (%)", value=0.710, format="%.3f"
)
rate_3m = st.sidebar.number_input(
    "3M 大額定存年利率 (%)", value=0.715, format="%.3f"
)
rate_6m = st.sidebar.number_input(
    "6M 大額定存年利率 (%)", value=0.725, format="%.3f"
)
rate_demand = st.sidebar.number_input(
    "活期/儲蓄專戶年利率 (%)", value=0.030, format="%.3f"
)

# --- 核心計算準備 ---
investable_amount = total_margin * (1 - buffer_ratio / 100)
demand_amount = total_margin * (buffer_ratio / 100)

# 壓力測試出金比率映射
stress_mapping = {
    "正常市況 (無突發大額出金)": 0.0,
    "中度風險 (突發出金 15%)": 0.15,
    "極度風險 (斷頭潮/客戶擠兌 35%)": 0.35,
}
outflow_ratio = stress_mapping[stress_scenario]
total_outflow_demand = total_margin * outflow_ratio

# 計算活存是否足以支應突發出金缺口
liquidity_gap = max(0, total_outflow_demand - demand_amount)

# 月利率轉換
r_d = (rate_demand / 100) / 12
r1 = (rate_1m / 100) / 12
r3 = (rate_3m / 100) / 12
r6 = (rate_6m / 100) / 12

# 基礎正常利息收益 (以一季度 3 個月為模擬基準)
interest_demand = demand_amount * ((1 + r_d) ** 3 - 1)

# 策略 A (1M Rolling) 正常利息
interest_A = investable_amount * ((1 + r1) ** 3 - 1) + interest_demand
# 策略 B (3M Rolling) 正常利息
interest_B = investable_amount * ((1 + r3) ** 3 - 1) + interest_demand
# 策略 C (6M Locked) 正常利息
interest_C = investable_amount * (r3 * 3 * 0.8) + interest_demand
# 策略 D (階梯拆單佈局) 正常利息
interest_D = (
    (investable_amount / 3) * ((1 + r1) ** 3 - 1)
    + (investable_amount / 3) * ((1 + r3) ** 3 - 1)
    + (investable_amount / 3) * (r3 * 3 * 0.9)
) + interest_demand

# --- 風險與流動性懲罰計算 (Liquidity Penalty) ---
penalty_A = 0
penalty_B = 0
penalty_C = 0
penalty_D = 0

if liquidity_gap > 0:
    # 策略 A: 1M 每月到期，解約折損最低
    penalty_A = liquidity_gap * r1 * 0.5
    # 策略 B: 3M 一旦未滿期解約，利率退回 1M 並打 8 折
    penalty_B = liquidity_gap * (rate_3m / 100 - (rate_1m / 100) * 0.8) * (2 / 12)
    # 策略 C: 6M 鎖死最嚴重，提前解約懲罰最高
    penalty_C = liquidity_gap * (rate_6m / 100 - (rate_1m / 100) * 0.7) * (3 / 12)
    # 策略 D: 階梯拆單每月有 1/3 自然到期，僅需解約剩餘頭寸
    effective_gap_D = max(0, liquidity_gap - (investable_amount / 3))
    penalty_D = effective_gap_D * (rate_3m / 100 - (rate_1m / 100) * 0.8) * (1 / 12)

# 計算最終淨收益
net_A = max(0, interest_A - penalty_A)
net_B = max(0, interest_B - penalty_B)
net_C = max(0, interest_C - penalty_C)
net_D = max(0, interest_D - penalty_D)

# --- UI 數據指標呈現 ---
col1, col2, col3 = st.columns(3)
col1.metric("💰 專戶定存水位 (可優化資產)", f"${investable_amount:,.0f} TWD")
col2.metric("💧 每日活期留存現金", f"${demand_amount:,.0f} TWD")
col3.metric(
    "🚨 突發最大出金需求",
    f"${total_outflow_demand:,.0f} TWD",
    delta=f"缺口: ${liquidity_gap:,.0f}" if liquidity_gap > 0 else "活存足夠",
    delta_color="inverse",
)

st.write("---")
st.subheader(f"📊 各配置策略於一季度 (3個月) 的收益與風控表現 ({stress_scenario})")

df_fcm = pd.DataFrame(
    {
        "FCM 存款配置策略": [
            "策略 A：全押 1M 滾存 (極高流動性)",
            "策略 B：全押 3M 定存 (一般法人最愛)",
            "策略 C：全押 6M 定存 (盲目追求高利)",
            "策略 D：1M/3M/6M 階梯式動態拆單 (風控最佳解)",
        ],
        "理論利息收益 (TWD)": [interest_A, interest_B, interest_C, interest_D],
        "被迫提前解約利息折損 (TWD)": [
            penalty_A,
            penalty_B,
            penalty_C,
            penalty_D,
        ],
        "預估淨利息收益 (TWD)": [net_A, net_B, net_C, net_D]
    }
)

# 格式化 DataFrame 顯示數值
df_display = df_fcm.copy()
for c in [
    "理論利息收益 (TWD)",
    "被迫提前解約利息折損 (TWD)",
    "預估淨利息收益 (TWD)",
]:
    df_display[c] = df_display[c].map("{:,.0f}".format)

st.dataframe(df_display, use_container_width=True)

# --- 視覺化圖表 (徹底解決 Linux 豆腐字問題) ---
st.subheader("📈 Net Yield & Liquidity Penalty Comparison")

fig, ax = plt.subplots(figsize=(10, 4))

y_pos = np.arange(len(df_fcm))

# 建立堆疊橫向條形圖
p1 = ax.barh(
    y_pos,
    df_fcm["預估淨利息收益 (TWD)"],
    label="Net Yield (Expected Net Interest)",
    color="#1D3557",
)
p2 = ax.barh(
    y_pos,
    df_fcm["被迫提前解約利息折損 (TWD)"],
    left=df_fcm["預估淨利息收益 (TWD)"],
    label="Liquidity Penalty (Early Breakage Cost)",
    color="#E63946",
)

# 使用純英文標籤渲染軸心，繞過雲端 Linux 無中文字型的限制
strategy_labels_en = [
    "Strat A: 1M",
    "Strat B: 3M",
    "Strat C: 6M",
    "Strat D: Dynamic Ladder",
]

ax.set_yticks(y_pos)
ax.set_yticklabels(strategy_labels_en, fontsize=10, fontweight="bold")
ax.set_xlabel("Amount (TWD)", fontsize=10)
ax.legend(loc="lower right")
ax.xaxis.grid(True, linestyle="--", alpha=0.5)

st.pyplot(fig)

# --- FCM 專業決策指引 ---
st.subheader("💡 財務處風控合規指引（FCM Treasury Guidance）")
if liquidity_gap > 0:
    st.warning(
        f"⚠️ **警訊**：在當前設定的【{stress_scenario}】下，期貨商的活期留存現金不敷出金需求，"
        f"有 **${liquidity_gap:,.0f} TWD** 的缺口必須強行解約定存！此時「全押高利定存（策略C）」會因為利息打折，導致總收益嚴重縮水。 "
        f"建議調高緩衝金比例，或採用**策略 D（階梯式拆單）**來抵禦黑天鵝。"
    )
else:
    st.success(
        "✅ **安全**：目前活期留存金相當充足，足以應付突發出金。可以安心進行大額定存佈局以套取利差。"
    )

with st.expander("📌 期貨商保證金管理的財務操作精髓"):
    st.markdown(
        """
    * **階梯式展期（Rolling Forward）**：將資金切為 3 或 6 等份，使每個月都有定存單準時到期。到期的資金若無急用，直接續存最高利的 3M 或 6M。如此一來，既能享有長天期的高利，又能確保**每個月都有大筆頭寸解凍**，完美匹配期貨業的動態風險流。
    """
    )
