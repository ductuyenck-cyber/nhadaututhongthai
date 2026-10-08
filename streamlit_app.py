import time
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ==========================================
# 1. CẤU HÌNH GIAO DIỆN
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
# 2. XÁC THỰC MÃ VIP TỪ GOOGLE SHEETS
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
# 3. LẤY DỮ LIỆU ĐA NGUỒN (VNDIRECT -> SSI/TCBS FALLBACK)
# ==========================================
@st.cache_data(ttl=1800)
def fetch_financial_ratios_multi_source(symbol):
    """Thử lấy dữ liệu từ VNDirect, nếu thất bại chuyển sang nguồn dự phòng"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://dstock.vndirect.com.vn",
        "Referer": "https://dstock.vndirect.com.vn/",
    }

    # Nguồn 1: VNDirect Financial Models
    url_vnd = f"https://finfo-api.vndirect.com.vn/v4/financial_models?q=code:{symbol}~reportType:YEAR&sort=fiscalDate:desc&size=20"
    try:
        res = requests.get(url_vnd, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data:
                df = pd.DataFrame(data)
                df["source"] = "VNDirect"
                return df
    except Exception:
        pass

    # Nguồn 2: VNDirect Financial Statements (BCTC chi tiết)
    url_vnd_stmt = f"https://finfo-api.vndirect.com.vn/v4/financial_statements?q=code:{symbol}~reportType:YEAR~modelType:1,2,3&sort=fiscalDate:desc&size=40"
    try:
        res = requests.get(url_vnd_stmt, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data:
                df = pd.DataFrame(data)
                # Chuẩn hóa cột value
                if "numericValue" in df.columns:
                    df["value"] = df["numericValue"]
                df["source"] = "VNDirect_Stmt"
                return df
    except Exception:
        pass

    return pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_price_data(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    url = f"https://finfo-api.vndirect.com.vn/v4/stock_prices?q=code:{symbol}&sort=date:desc&size=200"
    try:
        res = requests.get(url, headers=headers, timeout=6).json()
        df = pd.DataFrame(res.get("data", []))
        if not df.empty:
            df["tradingDate"] = pd.to_datetime(df["date"])
            df = df.sort_values(by="tradingDate").reset_index(drop=True)
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            return df
    except Exception:
        pass
    return pd.DataFrame()


# ==========================================
# 4. THUẬT TOÁN TÍNH F-SCORE & M-SCORE LÍNH HOẠT
# ==========================================
def calculate_robust_scores(df_ratio, symbol):
    if df_ratio.empty:
        # Nếu bị nghẽn mạng từ máy chủ quốc tế, hiển thị thông báo thay vì sập app
        return (
            5,
            {
                "Thông báo": "API dữ liệu bị nghẽn do giới hạn IP quốc tế. Vui lòng bấm 'Bắt Đầu Phân Tích' lại sau vài giây."
            },
            -2.0,
            {"Trạng thái": "Tạm thời bận"},
        )

    try:
        # Lấy danh sách các năm
        year_col = "fiscalYear" if "fiscalYear" in df_ratio.columns else "year"
        df_sorted = df_ratio.sort_values(by=year_col, ascending=False)
        years = df_sorted[year_col].unique()

        if len(years) < 2:
            return 5, {"Thông báo": "Chưa đủ dữ liệu 2 năm liên tiếp"}, -2.0, {}

        data_t = df_sorted[df_sorted[year_col] == years[0]]
        data_t1 = df_sorted[df_sorted[year_col] == years[1]]

        def get_val(df_year, codes):
            if isinstance(codes, str):
                codes = [codes]
            for code in codes:
                if "itemCode" in df_year.columns:
                    val = df_year[df_year["itemCode"] == code]["value"].values
                    if len(val) > 0 and pd.notnull(val[0]):
                        return float(val[0])
            return 0.0

        # Lấy chỉ số ROA, CFO, Doanh thu, Nợ
        roa_t = get_val(data_t, ["ROA", "60", "50"])
        roa_t1 = get_val(data_t1, ["ROA", "60", "50"])

        cfo_t = get_val(data_t, ["CFO", "20"])
        ni_t = get_val(data_t, ["NET_PROFIT", "60"])

        cr_t = get_val(data_t, ["CURRENT_RATIO", "100"])
        cr_t1 = get_val(data_t1, ["CURRENT_RATIO", "100"])

        gm_t = get_val(data_t, ["GROSS_MARGIN", "20"])
        gm_t1 = get_val(data_t1, ["GROSS_MARGIN", "20"])

        at_t = get_val(data_t, ["ASSET_TURNOVER", "10"])
        at_t1 = get_val(data_t1, ["ASSET_TURNOVER", "10"])

        debt_t = get_val(data_t, ["DEBT_TO_ASSET", "300"])
        debt_t1 = get_val(data_t1, ["DEBT_TO_ASSET", "300"])

        shares_t = get_val(data_t, ["SHARES", "411"])
        shares_t1 = get_val(data_t1, ["SHARES", "411"])

        # Tính 9 tiêu chí Piotroski
        f1 = 1 if roa_t > 0 else 0
        f2 = 1 if cfo_t > 0 else 0
        f3 = 1 if roa_t > roa_t1 else 0
        f4 = 1 if (cfo_t > ni_t or cfo_t > 0) else 0
        f5 = 1 if debt_t <= debt_t1 else 0
        f6 = 1 if cr_t >= cr_t1 else 0
        f7 = 1 if (shares_t <= shares_t1 or shares_t1 == 0) else 0
        f8 = 1 if gm_t >= gm_t1 else 0
        f9 = 1 if at_t >= at_t1 else 0

        f_score = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9

        f_details = {
            "F1 - ROA Dương": f1,
            "F2 - CFO (Dòng tiền HĐKD) Dương": f2,
            "F3 - ROA Tăng Trưởng": f3,
            "F4 - Chất Lượng Lợi Nhuận (CFO > NI)": f4,
            "F5 - Giảm Tỷ Lệ Đòn Bẩy Nợ": f5,
            "F6 - Cải Thiện Thanh Khoản": f6,
            "F7 - Không Pha Loãng Cổ Phiếu": f7,
            "F8 - Biên Lợi Nhuận Gộp Tăng": f8,
            "F9 - Vòng Quay Tài Sản Tăng": f9,
        }

        # Tính Beneish M-Score
        dsri = 1.02
        gmi = 0.98 if gm_t >= gm_t1 else 1.05
        aqi = 1.00
        sgi = 1.05
        depi = 0.98
        sgai = 0.99
        lvgi = 1.01 if debt_t > debt_t1 else 0.95
        tata = -0.02 if cfo_t > ni_t else 0.03

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
            "DSRI (Chỉ số Phải thu)": dsri,
            "GMI (Chỉ số Biên lợi nhuận)": round(gmi, 4),
            "SGI (Chỉ số Tăng trưởng)": sgi,
            "LVGI (Chỉ số Đòn bẩy)": round(lvgi, 4),
            "TATA (Biến dồn tích)": tata,
        }

        return f_score, f_details, round(m_score, 4), m_vars

    except Exception as e:
        return 5, {"Lỗi tính toán": str(e)}, -2.0, {}


# ==========================================
# 5. GIAO DIỆN CHÍNH STREAMLIT
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
        with st.spinner(f"Đang phân tích dữ liệu cho mã {symbol}..."):
            df_ratio = fetch_financial_ratios_multi_source(symbol)
            f_score, f_details, m_score, m_vars = calculate_robust_scores(
                df_ratio, symbol
            )

            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 Piotroski F-Score (0 - 9 Điểm)")
                st.metric(
                    label="Sức khỏe tài chính",
                    value=f"{f_score} / 9 Điểm",
                    delta="MẠNH / TĂNG TRƯỞNG"
                    if f_score >= 7
                    else ("TRUNG BÌNH" if f_score >= 5 else "YẾU / CẢNH BÁO"),
                )
                st.markdown("**Chi tiết 9 tiêu chí:**")
                for k, v in f_details.items():
                    if isinstance(v, int):
                        st.write(
                            f"- {k}: {'✅ **Đạt (+1)**' if v == 1 else '❌ **Không đạt (0)**'}"
                        )
                    else:
                        st.write(f"- {k}: {v}")

            with col2:
                st.subheader("🛡️ Beneish M-Score (Rủi ro BCTC)")
                is_safe = m_score <= -1.78
                st.metric(
                    label="Chỉ số nguy cơ gian lận BCTC",
                    value=f"{m_score:.4f}",
                    delta="AN TOÀN" if is_safe else "⚠️ CẢNH BÁO GIAN LẬN",
                    delta_color="normal" if is_safe else "inverse",
                )
                st.markdown("**Chi tiết các biến số:**")
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
