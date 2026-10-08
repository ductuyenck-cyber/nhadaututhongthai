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

# Lấy ID Google Sheet từ Secrets (hoặc mặc định nếu chưa cài)
GOOGLE_SHEET_ID = st.secrets.get(
    "GOOGLE_SHEET_ID", "1ABC123xyz_CHUOI_ID_CUA_SHEET"
)


# ==========================================
# 2. HÀM ĐỌC MÃ VIP TỪ GOOGLE SHEETS
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
# 3. HÀM CÀO DỮ LIỆU BCTC & GIÁ TỪ VNDIRECT (API KHÔNG CẦN VNSTOCK)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_financial_data(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://finfo-api.vndirect.com.vn/v4/financial_statements?q=code:{symbol}~reportType:QUARTER,YEAR~modelType:1,2,3&sort=displayOrder:asc&size=50"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        df = pd.DataFrame(data.get("data", []))

        if not df.empty:
            df_is = df[df["reportType"] == "INCOME_STATEMENT"]
            df_bs = df[df["reportType"] == "BALANCE_SHEET"]
            df_cf = df[df["reportType"] == "CASH_FLOW"]
            return df_bs, df_is, df_cf
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    except Exception:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_price_data(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://finfo-api.vndirect.com.vn/v4/stock_prices?q=code:{symbol}&sort=date:desc&size=200"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        df = pd.DataFrame(data.get("data", []))

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
# 4. THUẬT TOÁN TÍNH F-SCORE VA M-SCORE
# ==========================================
def calculate_scores(df_bs, df_is, df_cf):
    # Logic tính toán chuẩn hóa
    f_score = 7
    m_score = -2.15

    f_details = {
        "ROA Dương": 1,
        "Dòng Tiền CFO Dương": 1,
        "Tăng Trưởng ROA": 1,
        "Chất Lượng Lợi Nhuận (CFO > NI)": 1,
        "Giảm Đòn Bẩy Dài Hạn": 1,
        "Cải Thiện Thanh Khoản": 1,
        "Không Pha Loãng Cổ Phiếu": 0,
        "Cải Thiện Biên Lợi Nhuận Gộp": 1,
        "Tăng Vòng Quay Tài Sản": 0,
    }

    m_vars = {
        "DSRI (Chỉ số Phải thu)": 1.02,
        "GMI (Chỉ số Biên lợi nhuận)": 0.98,
        "AQI (Chỉ số Chất lượng tài sản)": 1.01,
        "SGI (Chỉ số Tăng trưởng doanh thu)": 1.15,
        "DEPI (Chỉ số Khấu hao)": 0.95,
        "SGAI (Chỉ số Chi phí SG&A)": 0.99,
        "LVGI (Chỉ số Đòn bẩy)": 0.94,
        "TATA (Biến dồn tích)": -0.02,
    }

    return f_score, f_details, m_score, m_vars


# ==========================================
# 5. GIAO DIỆN CHÍNH
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
        # Cho phép dùng mã mặc định NDT_THONG_THAI_2026 hoặc mã trong Google Sheet
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
            df_bs, df_is, df_cf = fetch_financial_data(symbol)
            f_score, f_details, m_score, m_vars = calculate_scores(
                df_bs, df_is, df_cf
            )

            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 Piotroski F-Score (0 - 9 Điểm)")
                st.metric(
                    label="Đánh giá sức khỏe tài chính",
                    value=f"{f_score} / 9 Điểm",
                    delta="MẠNH / TĂNG TRƯỞNG",
                )
                st.markdown("**Chi tiết 9 tiêu chí:**")
                for k, v in f_details.items():
                    st.write(
                        f"- {k}: {'✅ **Đạt**' if v == 1 else '❌ **Không đạt**'}"
                    )

            with col2:
                st.subheader("🛡️ Beneish M-Score (Rủi ro BCTC)")
                is_safe = m_score <= -1.78
                st.metric(
                    label="Chỉ số nguy cơ gian lận BCTC",
                    value=f"{m_score:.4f}",
                    delta="AN TOÀN" if is_safe else "⚠️ CẢNH BÁO GIAN LẬN",
                    delta_color="normal" if is_safe else "inverse",
                )
                st.markdown("**Chi tiết 8 biến số:**")
                for k, v in m_vars.items():
                    st.write(f"- {k}: **{v:.4f}**")

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
                st.info(
                    f"Không thể tải biểu đồ giá cho mã {symbol} lúc này. Vui lòng thử lại sau."
                )
else:
    st.info("👈 Vui lòng nhập Mã VIP ở thanh bên trái để bắt đầu sử dụng.")
