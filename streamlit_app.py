import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from vnstock import FinancialReport, stock_historical_data

# ------------------------------------------
# 1. CẤU HÌNH TRANG WEB
# ------------------------------------------
st.set_page_config(
    page_title="Hệ Thống Phân Tích BCTC & TA - VIP",
    page_icon="📈",
    layout="wide",
)

# Lấy ID Google Sheet từ st.secrets hoặc mặc định
GOOGLE_SHEET_ID = st.secrets.get(
    "GOOGLE_SHEET_ID", "1ABC123xyz_CHUOI_ID_CUA_SHEET"
)


# ------------------------------------------
# 2. XÁC THỰC MÃ VIP TỪ GOOGLE SHEETS
# ------------------------------------------
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


def get_val(df, keywords, year_idx=-1):
    if df is None or df.empty:
        return 0.0
    for col in df.columns:
        for kw in keywords:
            if kw.lower() in str(col).lower():
                try:
                    val = df[col].iloc[year_idx]
                    return float(val) if pd.notnull(val) else 0.0
                except:
                    pass
    return 0.0


# ------------------------------------------
# 3. TÍNH PIOTROSKI F-SCORE (9 TIÊU CHÍ)
# ------------------------------------------
def calculate_f_score(bs, is_, cf):
    try:
        ni_t = get_val(is_, ["Lợi nhuận sau thuế", "net_income"], -1)
        ni_t1 = get_val(is_, ["Lợi nhuận sau thuế", "net_income"], -2)

        ta_t = get_val(bs, ["Tổng tài sản", "total_assets"], -1)
        ta_t1 = get_val(bs, ["Tổng tài sản", "total_assets"], -2)
        ta_t2 = get_val(bs, ["Tổng tài sản", "total_assets"], -3)

        avg_assets_t = (
            (ta_t + ta_t1) / 2 if (ta_t + ta_t1) > 0 else (ta_t if ta_t > 0 else 1)
        )
        avg_assets_t1 = (
            (ta_t1 + ta_t2) / 2
            if (ta_t1 + ta_t2) > 0
            else (ta_t1 if ta_t1 > 0 else 1)
        )

        roa_t = ni_t / avg_assets_t
        roa_t1 = ni_t1 / avg_assets_t1

        cfo_t = get_val(
            cf, ["Lưu chuyển tiền thuần từ hoạt động kinh doanh", "cfo"], -1
        )

        ltd_t = get_val(
            bs, ["Vay và nợ thuê tài chính dài hạn", "long_term_debt"], -1
        )
        ltd_t1 = get_val(
            bs, ["Vay và nợ thuê tài chính dài hạn", "long_term_debt"], -2
        )

        ca_t = get_val(bs, ["Tài sản ngắn hạn", "current_assets"], -1)
        cl_t = get_val(bs, ["Nợ ngắn hạn", "current_liabilities"], -1)
        cr_t = ca_t / cl_t if cl_t > 0 else 0

        ca_t1 = get_val(bs, ["Tài sản ngắn hạn", "current_assets"], -2)
        cl_t1 = get_val(bs, ["Nợ ngắn hạn", "current_liabilities"], -2)
        cr_t1 = ca_t1 / cl_t1 if cl_t1 > 0 else 0

        shares_t = get_val(
            bs, ["Vốn góp của chủ sở hữu", "charter_capital"], -1
        )
        shares_t1 = get_val(
            bs, ["Vốn góp của chủ sở hữu", "charter_capital"], -2
        )

        gp_t = get_val(is_, ["Lợi nhuận gộp", "gross_profit"], -1)
        rev_t = get_val(is_, ["Doanh thu thuần", "revenue"], -1)
        gm_t = gp_t / rev_t if rev_t > 0 else 0

        gp_t1 = get_val(is_, ["Lợi nhuận gộp", "gross_profit"], -2)
        rev_t1 = get_val(is_, ["Doanh thu thuần", "revenue"], -2)
        gm_t1 = gp_t1 / rev_t1 if rev_t1 > 0 else 0

        at_t = rev_t / avg_assets_t
        at_t1 = rev_t1 / avg_assets_t1

        f1 = 1 if roa_t > 0 else 0
        f2 = 1 if cfo_t > 0 else 0
        f3 = 1 if roa_t > roa_t1 else 0
        f4 = 1 if cfo_t > ni_t else 0
        f5 = 1 if ltd_t <= ltd_t1 else 0
        f6 = 1 if cr_t > cr_t1 else 0
        f7 = 1 if shares_t <= shares_t1 else 0
        f8 = 1 if gm_t > gm_t1 else 0
        f9 = 1 if at_t > at_t1 else 0

        f_score = sum([f1, f2, f3, f4, f5, f6, f7, f8, f9])
        details = {
            "ROA Dương": f1,
            "Dòng Tiền CFO Dương": f2,
            "Tăng Trưởng ROA": f3,
            "Chất Lượng Lợi Nhuận (CFO > NI)": f4,
            "Giảm Đòn Bẩy Dài Hạn": f5,
            "Cải Thiện Thanh Khoản": f6,
            "Không Pha Loãng Cổ Phiếu": f7,
            "Cải Thiện Biên Lợi Nhuận Gộp": f8,
            "Tăng Vòng Quay Tài Sản": f9,
        }
        return f_score, details
    except Exception:
        return 0, {}


# ------------------------------------------
# 4. TÍNH BENEISH M-SCORE (8 BIẾN SỐ)
# ------------------------------------------
def calculate_m_score(bs, is_, cf):
    try:
        rev_t = get_val(is_, ["Doanh thu thuần", "revenue"], -1)
        rev_t1 = get_val(is_, ["Doanh thu thuần", "revenue"], -2)

        rec_t = get_val(bs, ["Phải thu ngắn hạn", "receivables"], -1)
        rec_t1 = get_val(bs, ["Phải thu ngắn hạn", "receivables"], -2)

        gp_t = get_val(is_, ["Lợi nhuận gộp", "gross_profit"], -1)
        gp_t1 = get_val(is_, ["Lợi nhuận gộp", "gross_profit"], -2)

        ta_t = get_val(bs, ["Tổng tài sản", "total_assets"], -1)
        ta_t1 = get_val(bs, ["Tổng tài sản", "total_assets"], -2)

        ppe_t = get_val(bs, ["Tài sản cố định", "fixed_assets"], -1)
        ppe_t1 = get_val(bs, ["Tài sản cố định", "fixed_assets"], -2)

        dep_t = get_val(
            cf, ["Khấu hao tài sản cố định", "depreciation"], -1
        )
        dep_t1 = get_val(
            cf, ["Khấu hao tài sản cố định", "depreciation"], -2
        )

        sga_t = get_val(
            is_, ["Chi phí bán hàng", "selling_expense"], -1
        ) + get_val(is_, ["Chi phí quản lý", "admin_expense"], -1)
        sga_t1 = get_val(
            is_, ["Chi phí bán hàng", "selling_expense"], -2
        ) + get_val(is_, ["Chi phí quản lý", "admin_expense"], -2)

        tl_t = get_val(bs, ["Nợ phải trả", "liabilities"], -1)
        tl_t1 = get_val(bs, ["Nợ phải trả", "liabilities"], -2)

        ni_t = get_val(is_, ["Lợi nhuận sau thuế", "net_income"], -1)
        cfo_t = get_val(
            cf, ["Lưu chuyển tiền thuần từ hoạt động kinh doanh", "cfo"], -1
        )

        dsri = (rec_t / rev_t) / (rec_t1 / rev_t1) if rev_t * rev_t1 > 0 else 1.0
        gmi = ((gp_t1 / rev_t1) / (gp_t / rev_t)) if gp_t * rev_t > 0 else 1.0
        aqi = (
            ((1 - (ppe_t / ta_t)) / (1 - (ppe_t1 / ta_t1)))
            if ta_t * ta_t1 > 0
            else 1.0
        )
        sgi = rev_t / rev_t1 if rev_t1 > 0 else 1.0

        dep_rate_t = dep_t / (ppe_t + dep_t) if (ppe_t + dep_t) > 0 else 0.01
        dep_rate_t1 = (
            dep_t1 / (ppe_t1 + dep_t1) if (ppe_t1 + dep_t1) > 0 else 0.01
        )
        depi = dep_rate_t1 / dep_rate_t if dep_rate_t > 0 else 1.0

        sgai = (
            ((sga_t / rev_t) / (sga_t1 / rev_t1)) if rev_t * rev_t1 > 0 else 1.0
        )
        lvgi = (tl_t / ta_t) / (tl_t1 / ta_t1) if ta_t * ta_t1 > 0 else 1.0
        tata = (ni_t - cfo_t) / ta_t if ta_t > 0 else 0.0

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

        vars_dict = {
            "DSRI (Chỉ số Phải thu)": dsri,
            "GMI (Chỉ số Biên lợi nhuận)": gmi,
            "AQI (Chỉ số Chất lượng tài sản)": aqi,
            "SGI (Chỉ số Tăng trưởng doanh thu)": sgi,
            "DEPI (Chỉ số Khấu hao)": depi,
            "SGAI (Chỉ số Chi phí SG&A)": sgai,
            "LVGI (Chỉ số Đòn bẩy)": lvgi,
            "TATA (Biến dồn tích)": tata,
        }
        return m_score, vars_dict
    except Exception:
        return -99.0, {}


# ------------------------------------------
# 5. GIAO DIỆN CHÍNH STREAMLIT
# ------------------------------------------
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
        with st.spinner(f"Đang tải và xử lý dữ liệu cổ phiếu {symbol}..."):
            try:
                report = FinancialReport(
                    symbol=symbol, report_type="annual", limit=3
                )
                bs = report.balance_sheet()
                is_ = report.income_statement()
                cf = report.cash_flow()

                if "year" in bs.columns:
                    bs = bs.sort_values(by="year").reset_index(drop=True)
                    is_ = is_.sort_values(by="year").reset_index(drop=True)
                    cf = cf.sort_values(by="year").reset_index(drop=True)

                f_score, f_details = calculate_f_score(bs, is_, cf)
                m_score, m_vars = calculate_m_score(bs, is_, cf)

                st.markdown("---")
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("📊 Piotroski F-Score (0 - 9 Điểm)")
                    st.metric(
                        label="Đánh giá sức khỏe tài chính",
                        value=f"{f_score} / 9 Điểm",
                        delta="MẠNH / TĂNG TRƯỞNG"
                        if f_score >= 7
                        else ("TRUNG BÌNH" if f_score >= 5 else "YẾU/CẢNH BÁO"),
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
                        delta="AN TOÀN" if is_safe else "⚠️ CẢNH BÁO GIÀN LẬN",
                        delta_color="normal" if is_safe else "inverse",
                    )

                    st.markdown("**Chi tiết 8 biến số:**")
                    for k, v in m_vars.items():
                        st.write(f"- {k}: **{v:.4f}**")

                st.markdown("---")
                st.subheader(f"📈 Biểu Đồ Kỹ Thuật & Giá Cổ Phiếu {symbol}")

                df_price = stock_historical_data(
                    symbol=symbol,
                    start_date="2025-01-01",
                    end_date="2026-10-08",
                )
                if not df_price.empty:
                    fig = go.Figure()
                    fig.add_trace(
                        go.Candlestick(
                            x=df_price["time"],
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

            except Exception as e:
                st.error(
                    f"Không thể xử lý dữ liệu cho cổ phiếu {symbol}. Chi tiết lỗi: {e}"
                )
else:
    st.info("👈 Vui lòng nhập Mã VIP ở thanh bên trái để sử dụng công cụ.")
