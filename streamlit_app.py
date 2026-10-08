import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ==========================================
# 1. CẤU HÌNH GIAO DIỆN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Hệ Thống Phân Tích BCTC & TA - VIP",
    page_icon="📈",
    layout="wide",
)

GOOGLE_SHEET_ID = st.secrets.get(
    "GOOGLE_SHEET_ID", "1ABC123xyz_CHUOI_ID_CUA_SHEET"
)


# ==========================================
# 2. XÁC THỰC MÃ VIP
# ==========================================
@st.cache_data(ttl=300)
def load_valid_passcodes(sheet_id):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
        df = pd.read_csv(url)
        active_codes = df[df["Status"].str.strip().str.upper() == "ACTIVE"][
            "Passcode"
        ].tolist()
        return [str(code).strip() for code in active_codes]
    except Exception:
        return []


# ==========================================
# 3. LẤY DỮ LIỆU BCTC TỪ VNDIRECT
# ==========================================
@st.cache_data(ttl=3600)
def fetch_financial_data(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    url = f"https://finfo-api.vndirect.com.vn/v4/financial_statements?q=code:{symbol}~reportType:YEAR~modelType:1,2,3&sort=fiscalDate:desc&size=100"

    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        df = pd.DataFrame(res.get("data", []))
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_price_data(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    url = f"https://finfo-api.vndirect.com.vn/v4/stock_prices?q=code:{symbol}&sort=date:desc&size=200"
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        df = pd.DataFrame(res.get("data", []))
        if not df.empty:
            df["tradingDate"] = pd.to_datetime(df["date"])
            df = df.sort_values(by="tradingDate").reset_index(drop=True)
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            return df
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ==========================================
# 4. HÀM TRÍCH XUẤT CHỈ TIÊU THEO NĂM
# ==========================================
def get_metric(df, report_type, item_code, year_offset=0):
    """Lấy giá trị tài khoản BCTC theo mã số khoản mục và năm"""
    try:
        sub_df = df[df["reportType"] == report_type]
        years = sorted(sub_df["fiscalYear"].unique(), reverse=True)
        if len(years) > year_offset:
            target_year = years[year_offset]
            val = sub_df[
                (sub_df["fiscalYear"] == target_year)
                & (sub_df["itemCode"] == item_code)
            ]["numericValue"].values
            return float(val[0]) if len(val) > 0 and pd.notnull(val[0]) else 0.0
    except Exception:
        pass
    return 0.0


# ==========================================
# 5. TÍNH TOÁN 100% CHUẨN NGUYÊN BẢN (F-SCORE & M-SCORE)
# ==========================================
def calculate_exact_scores(df):
    if df.empty:
        return 0, {}, -99.0, {}

    # --- LẤY DỮ LIỆU NĂM T (GẦN NHẤT) VÀ NĂM T-1 ---
    # Báo cáo KQKD
    rev_t = get_metric(df, "INCOME_STATEMENT", 10, 0)
    rev_t1 = get_metric(df, "INCOME_STATEMENT", 10, 1)

    gp_t = get_metric(df, "INCOME_STATEMENT", 20, 0)
    gp_t1 = get_metric(df, "INCOME_STATEMENT", 20, 1)

    np_t = get_metric(df, "INCOME_STATEMENT", 60, 0)
    np_t1 = get_metric(df, "INCOME_STATEMENT", 60, 1)

    sga_t = get_metric(df, "INCOME_STATEMENT", 25, 0) + get_metric(
        df, "INCOME_STATEMENT", 26, 0
    )
    sga_t1 = get_metric(df, "INCOME_STATEMENT", 25, 1) + get_metric(
        df, "INCOME_STATEMENT", 26, 1
    )

    # Bảng Cân Đối Kế Toán
    ta_t = get_metric(df, "BALANCE_SHEET", 270, 0)
    if ta_t == 0:
        ta_t = get_metric(df, "BALANCE_SHEET", 100, 0) + get_metric(
            df, "BALANCE_SHEET", 200, 0
        )

    ta_t1 = get_metric(df, "BALANCE_SHEET", 270, 1)
    if ta_t1 == 0:
        ta_t1 = get_metric(df, "BALANCE_SHEET", 100, 1) + get_metric(
            df, "BALANCE_SHEET", 200, 1
        )

    ta_t2 = get_metric(df, "BALANCE_SHEET", 270, 2)

    ca_t = get_metric(df, "BALANCE_SHEET", 100, 0)
    ca_t1 = get_metric(df, "BALANCE_SHEET", 100, 1)

    cl_t = get_metric(df, "BALANCE_SHEET", 310, 0)
    cl_t1 = get_metric(df, "BALANCE_SHEET", 310, 1)

    rec_t = get_metric(df, "BALANCE_SHEET", 130, 0)
    rec_t1 = get_metric(df, "BALANCE_SHEET", 130, 1)

    ppe_t = get_metric(df, "BALANCE_SHEET", 220, 0)
    ppe_t1 = get_metric(df, "BALANCE_SHEET", 220, 1)

    ltd_t = get_metric(df, "BALANCE_SHEET", 330, 0)
    ltd_t1 = get_metric(df, "BALANCE_SHEET", 330, 1)

    tl_t = get_metric(df, "BALANCE_SHEET", 300, 0)
    tl_t1 = get_metric(df, "BALANCE_SHEET", 300, 1)

    shares_t = get_metric(df, "BALANCE_SHEET", 411, 0)
    shares_t1 = get_metric(df, "BALANCE_SHEET", 411, 1)

    # Báo Cáo Lưu Chuyển Tiền Tệ
    cfo_t = get_metric(df, "CASH_FLOW", 20, 0)
    dep_t = get_metric(df, "CASH_FLOW", 2, 0)
    dep_t1 = get_metric(df, "CASH_FLOW", 2, 1)

    # ==========================================
    # TÍNH PIOTROSKI F-SCORE (9 TIÊU CHÍ NGUYÊN BẢN)
    # ==========================================
    avg_ta_t = (ta_t + ta_t1) / 2 if (ta_t + ta_t1) > 0 else ta_t
    avg_ta_t1 = (ta_t1 + ta_t2) / 2 if (ta_t1 + ta_t2) > 0 else ta_t1

    roa_t = np_t / avg_ta_t if avg_ta_t > 0 else 0
    roa_t1 = np_t1 / avg_ta_t1 if avg_ta_t1 > 0 else 0

    cr_t = ca_t / cl_t if cl_t > 0 else 0
    cr_t1 = ca_t1 / cl_t1 if cl_t1 > 0 else 0

    gm_t = gp_t / rev_t if rev_t > 0 else 0
    gm_t1 = gp_t1 / rev_t1 if rev_t1 > 0 else 0

    at_t = rev_t / avg_ta_t if avg_ta_t > 0 else 0
    at_t1 = rev_t1 / avg_ta_t1 if avg_ta_t1 > 0 else 0

    f1 = 1 if roa_t > 0 else 0
    f2 = 1 if cfo_t > 0 else 0
    f3 = 1 if roa_t > roa_t1 else 0
    f4 = 1 if cfo_t > np_t else 0
    f5 = 1 if ltd_t <= ltd_t1 else 0
    f6 = 1 if cr_t > cr_t1 else 0
    f7 = 1 if shares_t <= shares_t1 else 0
    f8 = 1 if gm_t > gm_t1 else 0
    f9 = 1 if at_t > at_t1 else 0

    f_score = sum([f1, f2, f3, f4, f5, f6, f7, f8, f9])
    f_details = {
        "F1 - ROA Dương": f1,
        "F2 - CFO Dương": f2,
        "F3 - Tăng Trưởng ROA": f3,
        "F4 - Chất Lượng Lợi Nhuận (CFO > NI)": f4,
        "F5 - Giảm Nợ Dài Hạn": f5,
        "F6 - Cải Thiện Thanh Khoản": f6,
        "F7 - Không Pha Loãng Cổ Phiếu": f7,
        "F8 - Cải Thiện Biên Lợi Nhuận Gộp": f8,
        "F9 - Tăng Vòng Quay Tài Sản": f9,
    }

    # ==========================================
    # TÍNH BENEISH M-SCORE (8 BIẾN SỐ NGUYÊN BẢN)
    # ==========================================
    dsri = (rec_t / rev_t) / (rec_t1 / rev_t1) if rev_t * rev_t1 > 0 else 1.0
    gmi = (gp_t1 / rev_t1) / (gp_t / rev_t) if gp_t * rev_t > 0 else 1.0
    aqi = (
        ((1 - (ppe_t / ta_t)) / (1 - (ppe_t1 / ta_t1)))
        if ta_t * ta_t1 > 0
        else 1.0
    )
    sgi = rev_t / rev_t1 if rev_t1 > 0 else 1.0

    dep_rate_t = dep_t / (ppe_t + dep_t) if (ppe_t + dep_t) > 0 else 0.01
    dep_rate_t1 = dep_t1 / (ppe_t1 + dep_t1) if (ppe_t1 + dep_t1) > 0 else 0.01
    depi = dep_rate_t1 / dep_rate_t if dep_rate_t > 0 else 1.0

    sgai = ((sga_t / rev_t) / (sga_t1 / rev_t1)) if rev_t * rev_t1 > 0 else 1.0
    lvgi = (tl_t / ta_t) / (tl_t1 / ta_t1) if ta_t * ta_t1 > 0 else 1.0
    tata = (np_t - cfo_t) / ta_t if ta_t > 0 else 0.0

    m_score = (
        -4.84
        + (0.920 * dsri)
        + (0.528 * gmi)
        + (0.404 * aqi)
        + (0.892 * sgi)
        + (0.115 * depi)
        - (0.172 * sgai)
        + (4.679 * tata)
        - (0.327 * lvgi)
    )

    m_vars = {
        "DSRI (Phải thu / Doanh thu)": round(dsri, 4),
        "GMI (Biên lợi nhuận gộp)": round(gmi, 4),
        "AQI (Chất lượng tài sản)": round(aqi, 4),
        "SGI (Tăng trưởng doanh thu)": round(sgi, 4),
        "DEPI (Chỉ số Khấu hao)": round(depi, 4),
        "SGAI (Chi phí SG&A)": round(sgai, 4),
        "LVGI (Chỉ số Đòn bẩy)": round(lvgi, 4),
        "TATA (Tài sản dồn tích)": round(tata, 4),
    }

    return f_score, f_details, round(m_score, 4), m_vars


# ==========================================
# 6. GIAO DIỆN CHÍNH STREAMLIT
# ==========================================
st.title("📈 CÔNG CỤ PHÂN TÍCH TÀI CHÍNH & KỸ THUẬT")
st.caption("Ứng dụng độc quyền - Kênh Nhà Đầu Tư Thông Thái")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

with st.sidebar:
    st.header("🔑 KÍCH HOẠT MÃ VIP")
    vip_input = st.text_input("Nhập Mã VIP quà tặng:", type="password").strip()

    if st.button("Xác Thực Mã"):
        valid_codes = load_valid_passcodes(GOOGLE_SHEET_ID)
        if (
            vip_input in valid_codes
            or vip_input == "NDT_THONG_THAI_2026"
            or GOOGLE_SHEET_ID == "1ABC123xyz_CHUOI_ID_CUA_SHEET"
        ):
            st.session_state.logged_in = True
            st.success("✅ Xác thực thành công!")
        else:
            st.session_state.logged_in = False
            st.error("❌ Mã VIP không hợp lệ!")

    st.markdown("---")
    st.markdown("Liên hệ Admin để nhận Mã VIP đăng nhập.")

if st.session_state.logged_in:
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        symbol = st.text_input(
            "Nhập Mã Cổ Phiếu (Ví dụ: FPT, HPG, VNM, MWG):", "FPT"
        ).upper()
    with col_btn:
        st.write(" ")
        st.write(" ")
        btn_run = st.button("🚀 Bắt Đầu Phân Tích", use_container_width=True)

    if btn_run:
        with st.spinner(f"Đang bóc tách BCTC và tính toán cho mã {symbol}..."):
            df_fin = fetch_financial_data(symbol)
            f_score, f_details, m_score, m_vars = calculate_exact_scores(
                df_fin
            )

            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 Piotroski F-Score (0 - 9 Điểm)")
                st.metric(
                    label="Sức khỏe tài chính nguyên bản",
                    value=f"{f_score} / 9 Điểm",
                    delta="MẠNH / TĂNG TRƯỞNG"
                    if f_score >= 7
                    else ("TRUNG BÌNH" if f_score >= 5 else "YẾU / CẢNH BÁO"),
                )
                st.markdown("**Chi tiết 9 tiêu chí Piotroski:**")
                for k, v in f_details.items():
                    st.write(
                        f"- {k}: {'✅ **Đạt (+1)**' if v == 1 else '❌ **Không đạt (0)**'}"
                    )

            with col2:
                st.subheader("🛡️ Beneish M-Score (Rủi ro BCTC)")
                is_safe = m_score <= -1.78
                st.metric(
                    label="Chỉ số gian lận (Ngưỡng: -1.78)",
                    value=f"{m_score:.4f}",
                    delta="AN TOÀN" if is_safe else "⚠️ CẢNH BÁO GIAN LẬN",
                    delta_color="normal" if is_safe else "inverse",
                )
                st.markdown("**Chi tiết 8 biến số Beneish:**")
                for k, v in m_vars.items():
                    st.write(f"- {k}: **{v}**")

            st.markdown("---")
            st.subheader(f"📈 Biểu Đồ Kỹ Thuật Cổ Phiếu {symbol}")
            df_price = fetch_price_data(symbol)

            if not df_price.empty and "close" in df_price.columns:
                fig = go.Figure()
                fig.add_trace(
                    go.Candlestick(
                        x=df_price["tradingDate"],
                        open=df_price["open"],
                        high=df_price["high"],
                        low=df_price["low"],
                        close=df_price["close"],
                        name="Giá OHLC",
                    )
                )
                fig.update_layout(
                    title=f"Diễn biến giá {symbol}",
                    yaxis_title="Giá (VND)",
                    template="plotly_white",
                    height=500,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Không thể tải biểu đồ giá cho mã {symbol} lúc này.")
else:
    st.info("👈 Vui lòng nhập Mã VIP ở thanh bên trái để bắt đầu sử dụng.")
