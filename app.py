import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import BytesIO
import re
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="D52B Quality Control Hub",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# RESPONSIVE INDUSTRIAL CSS
# ============================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }

    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #1f2937;
    }

    div[data-testid="stMetric"] {
        background: #161e2e;
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        margin-bottom: 10px;
    }

    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    div[data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-size: 1.4rem !important;
        font-weight: 700 !important;
    }

    h1 { font-size: 1.6rem !important; color: #f8fafc !important; font-weight: 700 !important; }
    h2 { font-size: 1.3rem !important; color: #f8fafc !important; }
    h3 { font-size: 1.1rem !important; color: #cbd5e1 !important; }

    .stDataFrame {
        border: 1px solid #2d3748;
        border-radius: 8px;
        overflow-x: auto;
    }

    @media (max-width: 768px) {
        h1 { font-size: 1.3rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }
        div[data-testid="stMetric"] { padding: 10px; }
        .stButton > button { width: 100% !important; }
    }

    .stButton > button {
        border-radius: 6px !important;
        font-weight: 600 !important;
        background-color: #2563eb !important;
        color: #ffffff !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background-color: #1d4ed8 !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONSTANTS & CONFIG
# ============================================================

MONTHS = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

MONTH_ALIASES = {
    "jan": "Januari", "january": "Januari", "januari": "Januari",
    "feb": "Februari", "february": "Februari", "februari": "Februari",
    "mar": "Maret", "march": "Maret", "maret": "Maret",
    "apr": "April", "april": "April",
    "may": "Mei", "mei": "Mei",
    "jun": "Juni", "june": "Juni", "juni": "Juni",
    "jul": "Juli", "july": "Juli", "juli": "Juli",
    "aug": "Agustus", "august": "Agustus", "agustus": "Agustus",
    "sep": "September", "sept": "September", "september": "September",
    "oct": "Oktober", "okt": "Oktober", "oktober": "Oktober",
    "nov": "November", "november": "November",
    "dec": "Desember", "des": "Desember", "desember": "Desember"
}

NG_TYPES = [
    "Jarak jahitan tidak standar", "Bahan Balap Tidak Standar", "Langkah Jahitan tidak standar",
    "Point tidak center", "Lipatan tidak standar", "Jahitan putus", "Jahitan loncat",
    "Jahitan keriput", "Jahitan gelombang", "Ex jarum", "Benang kendor (Machine)",
    "Benang Pecah", "Jahitan kenceng", "Benang over/ Keluar", "Bahan terlipat/Terjahit",
    "Tepu tidak terpotong", "Takure", "Sampah Benang Terjahit", "Kuncian putus/ Lepas / Tidak ada",
    "Noda bahan", "Part tidak terpasang", "Part terpasang terbalik", "Part salah pasang",
    "Tidak ada sutechi", "Part terpasang Double", "Over part", "Tidak ada Piping", "GAP Bahan Tidak Standar"
]

AREA_LEADER_MAP = {
    "FB RH": {"nama_area": "Front Back RH", "leader": "Bu Kiki"},
    "FB LH": {"nama_area": "Front Back LH", "leader": "Bu Kiki"},
    "FC RH": {"nama_area": "Front Cushion RH", "leader": "Pak Heri"},
    "FC LH": {"nama_area": "Front Cushion LH", "leader": "Pak Heri"},
    "R1B RH": {"nama_area": "Rear 1 Back RH", "leader": "Bu Yunita"},
    "R1B LH": {"nama_area": "Rear 1 Back LH", "leader": "Bu Yunita"},
    "R1C RH": {"nama_area": "Rear 1 Cushion RH", "leader": "Bu Tiara"},
    "R1C LH": {"nama_area": "Rear 1 Cushion LH", "leader": "Bu Tiara"},
    "R2B": {"nama_area": "Rear 2 Back", "leader": "Pak Rosim"},
    "R2C": {"nama_area": "Rear 2 Cushion", "leader": "Pak Rosim"}
}

AREA_NAMES = list(AREA_LEADER_MAP.keys())

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_text(value):
    if value is None: return ""
    text = str(value).strip().lower().replace("\n", " ").replace("\r", " ").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()

def clean_number(value):
    if value is None: return 0
    if isinstance(value, (int, np.integer)): return int(value)
    if isinstance(value, (float, np.floating)): return 0 if np.isnan(value) else int(round(value))
    text = str(value).strip()
    if text == "" or text.lower() in ["none", "nan", "-", "–", "—"]: return 0
    text = text.replace(" ", "")
    try: return int(float(text))
    except Exception: pass
    text = text.replace(".", "").replace(",", ".")
    try: return int(float(text))
    except Exception: return 0

def format_int(value):
    try: return f"{int(round(value)):,}".replace(",", ".")
    except Exception: return "0"

def normalize_ng_name(value):
    text = normalize_text(value)
    replacements = {
        "benang kendor ( machine )": "Benang kendor (Machine)",
        "benang kendor (machine)": "Benang kendor (Machine)",
        "benang over/ keluar": "Benang over/ Keluar",
        "benang over/keluar": "Benang over/ Keluar",
        "bahan balap tidak standar": "Bahan Balap Tidak Standar",
        "gap bahan tidak standar": "GAP Bahan Tidak Standar"
    }
    if text in replacements: return replacements[text]
    for item in NG_TYPES:
        if normalize_text(item) == text: return item
    return str(value).strip()

def normalize_area(value):
    text = normalize_text(value)
    aliases = {a.lower(): a for a in AREA_NAMES}
    return aliases.get(text)

def detect_month_from_text(text):
    if not text: return None
    value = normalize_text(text)
    pattern = r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|okt|nov|dec|des)[\s\-_\/]*\d{2,4}\b"
    match = re.search(pattern, value)
    if match: return MONTH_ALIASES.get(match.group(1))
    for alias, month in MONTH_ALIASES.items():
        if alias in value: return month
    return None

def detect_month_from_dataframe(df, sheet_name=""):
    month = detect_month_from_text(sheet_name)
    if month: return month
    for r in range(min(len(df), 25)):
        for c in range(min(len(df.columns), 15)):
            val = df.iloc[r, c]
            if pd.notna(val):
                m = detect_month_from_text(str(val))
                if m: return m
    return None

def find_area_columns(df):
    found = {}
    for r in range(min(len(df), 30)):
        for c in range(len(df.columns)):
            val = df.iloc[r, c]
            if pd.notna(val):
                area = normalize_area(val)
                if area and area not in found: found[area] = c
    return found

def find_total_column(df):
    for c, col in enumerate(df.columns):
        if normalize_text(col) == "total": return c
    for r in range(min(len(df), 20)):
        for c in range(len(df.columns)):
            val = df.iloc[r, c]
            if pd.notna(val) and normalize_text(val) == "total": return c
    return None

def find_ng_in_row(row):
    for val in row.iloc[:8]:
        if pd.notna(val):
            norm = normalize_ng_name(val)
            if norm in NG_TYPES: return norm
    return None

def parse_d52b_sheet(df, sheet_name):
    month = detect_month_from_dataframe(df, sheet_name)
    area_columns = find_area_columns(df)
    result_area, result_total = {}, {}

    if len(area_columns) >= 2:
        total_col = find_total_column(df)
        for row_index in range(len(df)):
            row = df.iloc[row_index]
            ng_name = find_ng_in_row(row)
            if not ng_name or normalize_text(ng_name) == "total": continue

            area_values = {area: clean_number(df.iloc[row_index, area_columns[area]]) if area in area_columns else 0 for area in AREA_NAMES}
            total_from_area = sum(area_values.values())

            if total_from_area == 0 and total_col is not None:
                total_val = clean_number(df.iloc[row_index, total_col])
                if total_val > 0: result_total[ng_name] = total_val
            else:
                result_total[ng_name] = total_from_area

            if ng_name not in result_area: result_area[ng_name] = {a: 0 for a in AREA_NAMES}
            for area in AREA_NAMES: result_area[ng_name][area] += area_values[area]

        return {"month": month, "area_data": result_area, "total_data": result_total, "success": len(result_area) > 0}

    total_col = find_total_column(df)
    fallback_total = {}
    for row_index in range(len(df)):
        row = df.iloc[row_index]
        ng_name = find_ng_in_row(row)
        if not ng_name: continue
        if total_col is not None:
            fallback_total[ng_name] = clean_number(df.iloc[row_index, total_col])

    return {"month": month, "area_data": {}, "total_data": fallback_total, "success": len(fallback_total) > 0}

# ============================================================
# GOOGLE DRIVE DATABASE FUNCTIONS
# ============================================================

def get_drive_service():
    """Membuat koneksi ke Google Drive Service Account"""
    try:
        # Menggunakan kredensial dari gsheets/service_account di Secrets
        creds_info = dict(st.secrets.get("connections", {}).get("gsheets", {}))
        
        if not creds_info:
            creds_info = dict(st.secrets)

        if "private_key" in creds_info:
            pk = str(creds_info["private_key"]).strip().strip("'\"").replace("\\n", "\n")
            if "-----BEGIN PRIVATE KEY-----" in pk and "-----END PRIVATE KEY-----" in pk:
                core_key = pk.split("-----BEGIN PRIVATE KEY-----")[1].split("-----END PRIVATE KEY-----")[0].strip()
                core_key = "".join(core_key.split())
                pk = f"-----BEGIN PRIVATE KEY-----\n{core_key}\n-----END PRIVATE KEY-----\n"
            creds_info["private_key"] = pk

        scopes = ['https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Koneksi Google Drive Gagal: {e}")
        return None

def upload_file_to_gdrive(file_bytes, file_name, folder_id):
    """Mengunggah file Excel dari pengguna langsung ke Folder Google Drive"""
    service = get_drive_service()
    if not service: return False

    try:
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return True
    except Exception as e:
        st.error(f"Gagal upload file ke Google Drive: {e}")
        return False

def sync_data_from_gdrive(folder_id):
    """Membaca seluruh file Excel di Google Drive sebagai sumber database utama"""
    service = get_drive_service()
    if not service: return 0

    try:
        query = f"'{folder_id}' in parents and (mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or mimeType='application/vnd.ms-excel') and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        if not files:
            return 0

        # Reset session state sebelum reload data dari Drive
        st.session_state.monthly_data = {m: {} for m in MONTHS}
        count = 0

        for file in files:
            request = service.files().get_media(fileId=file['id'])
            file_stream = BytesIO(request.execute())
            excel = pd.ExcelFile(file_stream)

            for sheet_name in excel.sheet_names:
                df_sheet = pd.read_excel(file_stream, sheet_name=sheet_name, header=None)
                parsed = parse_d52b_sheet(df_sheet, sheet_name)

                m = parsed.get("month") or detect_month_from_text(sheet_name)
                if m:
                    for ng, total in parsed.get("total_data", {}).items():
                        if ng not in st.session_state.monthly_data[m]:
                            st.session_state.monthly_data[m][ng] = 0
                        st.session_state.monthly_data[m][ng] += total
                    count += 1

        return count
    except Exception as e:
        st.error(f"Error membaca dari Google Drive: {e}")
        return 0

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

if "monthly_data" not in st.session_state:
    st.session_state.monthly_data = {m: {} for m in MONTHS}

DEFAULT_FOLDER_ID = st.secrets.get("folder_id", "1XcgufwfNDrkOtdrXH34W6nybJKG3jX3U")

def build_month_dataframe(month):
    data = st.session_state.monthly_data.get(month, {})
    if not data: return pd.DataFrame(columns=["NG", "Jumlah", "Persentase", "Kumulatif"])

    df = pd.DataFrame(list(data.items()), columns=["NG", "Jumlah"])
    df["Jumlah"] = pd.to_numeric(df["Jumlah"], errors="coerce").fillna(0)
    df = df[df["Jumlah"] > 0].sort_values("Jumlah", ascending=False).reset_index(drop=True)

    if df.empty: return pd.DataFrame(columns=["NG", "Jumlah", "Persentase", "Kumulatif"])

    total = df["Jumlah"].sum()
    df["Persentase"] = (df["Jumlah"] / total * 100) if total > 0 else 0
    df["Kumulatif"] = df["Persentase"].cumsum()
    return df

def build_overall_dataframe():
    rows = []
    for m in MONTHS:
        for ng_name, jmh in st.session_state.monthly_data.get(m, {}).items():
            if jmh > 0: rows.append({"Bulan": m, "NG": ng_name, "Jumlah": jmh})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Bulan", "NG", "Jumlah"])

# ============================================================
# RESPONSIVE PLOTLY CHARTS
# ============================================================

DARK_THEME_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Inter, sans-serif", color="#94a3b8"),
    margin=dict(l=10, r=10, t=40, b=40),
    autosize=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

def create_pareto_chart(df, title):
    if df.empty: return None
    data = df.sort_values("Jumlah", ascending=False).reset_index(drop=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=data["NG"], y=data["Jumlah"], name="Jumlah NG",
            marker_color="#3b82f6", marker_line_color="#1d4ed8", marker_line_width=1
        ),
        secondary_y=False
    )
    fig.add_trace(
        go.Scatter(
            x=data["NG"], y=data["Kumulatif"], name="Kumulatif (%)",
            mode="lines+markers", line=dict(color="#f59e0b", width=2),
            marker=dict(size=6, color="#f59e0b")
        ),
        secondary_y=True
    )
    fig.add_hline(y=80, line_dash="dash", line_color="#ef4444", secondary_y=True)

    fig.update_layout(
        title=dict(text=title, font=dict(color="#f8fafc", size=14)),
        xaxis=dict(tickangle=-45, gridcolor="#1e293b", showgrid=False),
        yaxis=dict(title="Jumlah NG", gridcolor="#1e293b", showgrid=True),
        yaxis2=dict(title="Kumulatif (%)", range=[0, 105], showgrid=False),
        **DARK_THEME_LAYOUT
    )
    return fig

def create_monthly_trend_chart(df):
    if df.empty: return None
    monthly_sum = df.groupby("Bulan")["Jumlah"].sum().reindex(MONTHS).fillna(0).reset_index()
    monthly_sum = monthly_sum[monthly_sum["Jumlah"] > 0]

    if monthly_sum.empty: return None

    max_val = monthly_sum["Jumlah"].max()
    colors = ["#ef4444" if v == max_val else "#3b82f6" for v in monthly_sum["Jumlah"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly_sum["Bulan"], y=monthly_sum["Jumlah"],
        text=monthly_sum["Jumlah"], textposition="outside",
        marker_color=colors, textfont=dict(color="#f8fafc")
    ))

    fig.update_layout(
        title=dict(text="Total Defect Volume per Month (Highest Highlighted)", font=dict(color="#f8fafc", size=14)),
        xaxis=dict(gridcolor="#1e293b", showgrid=False),
        yaxis=dict(title="Defect Count", gridcolor="#1e293b", showgrid=True),
        height=350,
        **DARK_THEME_LAYOUT
    )
    return fig

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:
    st.markdown("### ⚡ D52B Quality Hub")
    st.caption("Sewing Assembly Dashboard")
    st.markdown("---")

    page = st.radio(
        "MENU NAVIGASI",
        [
            "Dashboard Overview",
            "Pareto Bulanan",
            "Data Grid Editor",
            "Upload / Sync Data",
            "Export Reports"
        ]
    )

    st.markdown("---")
    st.caption("Database Storage: **Google Drive Folder**")

# ============================================================
# PAGE 1: DASHBOARD OVERVIEW
# ============================================================

if page == "Dashboard Overview":
    st.title("Quality Executive Summary")
    st.caption("Real-time Defect Analytics Driven by Google Drive Storage")

    all_data = build_overall_dataframe()

    total_ng_all = all_data["Jumlah"].sum() if not all_data.empty else 0

    if not all_data.empty:
        monthly_grp = all_data.groupby("Bulan")["Jumlah"].sum()
        highest_month = monthly_grp.idxmax() if not monthly_grp.empty else "-"
        highest_month_val = monthly_grp.max() if not monthly_grp.empty else 0
        top_ng_overall = all_data.groupby("NG")["Jumlah"].sum().idxmax()
    else:
        highest_month, highest_month_val, top_ng_overall = "-", 0, "-"

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Defect Volume", format_int(total_ng_all))
    with col2: st.metric("Peak Defect Month", f"{highest_month}", f"{format_int(highest_month_val)} NG")
    with col3: st.metric("Primary Defect Type", top_ng_overall)
    with col4:
        active_months = len(all_data["Bulan"].unique()) if not all_data.empty else 0
        st.metric("Recorded Months", f"{active_months} Months")

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("Monthly Defect Comparison")
    if not all_data.empty:
        fig_trend = create_monthly_trend_chart(all_data)
        if fig_trend: st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Belum ada data. Silakan sync dari Google Drive di menu 'Upload / Sync Data'.")

    st.markdown("---")
    c1, c2 = st.columns([2, 1])
    with c1: st.subheader("Defect Pareto Breakdown")
    with c2: scope = st.selectbox("Filter Period", ["All Months"] + MONTHS)

    if scope == "All Months":
        scope_df = all_data.groupby("NG")["Jumlah"].sum().reset_index() if not all_data.empty else pd.DataFrame()
    else:
        scope_df = all_data[all_data["Bulan"] == scope].groupby("NG")["Jumlah"].sum().reset_index() if not all_data.empty else pd.DataFrame()

    if not scope_df.empty and scope_df["Jumlah"].sum() > 0:
        total_scope = scope_df["Jumlah"].sum()
        scope_df["Persentase"] = (scope_df["Jumlah"] / total_scope * 100)
        scope_df = scope_df.sort_values("Jumlah", ascending=False).reset_index(drop=True)
        scope_df["Kumulatif"] = scope_df["Persentase"].cumsum()

        fig_pareto = create_pareto_chart(scope_df, f"Pareto Analysis — {scope}")
        st.plotly_chart(fig_pareto, use_container_width=True)
    else:
        st.warning(f"No records found for period: {scope}")

# ============================================================
# PAGE 2: PARETO BULANAN
# ============================================================

elif page == "Pareto Bulanan":
    st.title("Monthly Pareto Analytics")

    selected_month = st.selectbox("Select Target Month", MONTHS, index=0)
    df_month = build_month_dataframe(selected_month)

    if df_month.empty:
        st.warning(f"No dataset loaded for **{selected_month}**.")
    else:
        total_ng = df_month["Jumlah"].sum()
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Total Monthly Defect", format_int(total_ng))
        with col2: st.metric("Top Defect Category", df_month.iloc[0]["NG"])
        with col3: st.metric("Top Category Count", format_int(df_month.iloc[0]["Jumlah"]))

        fig = create_pareto_chart(df_month, f"Pareto Distribution — {selected_month}")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Detailed Defect Table — {selected_month}")
        display_df = df_month.copy()
        display_df["Persentase"] = display_df["Persentase"].round(2).astype(str) + " %"
        display_df["Kumulatif"] = display_df["Kumulatif"].round(2).astype(str) + " %"
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# ============================================================
# PAGE 3: DATA GRID EDITOR
# ============================================================

elif page == "Data Grid Editor":
    st.title("Manual Data Review")
    st.caption("Review active session defect numbers")

    edit_month = st.selectbox("Select Month to Review", MONTHS)
    current_data = st.session_state.monthly_data.get(edit_month, {})

    rows = [{"Defect Category": ng, "Quantity": current_data.get(ng, 0)} for ng in NG_TYPES]
    df_edit = pd.DataFrame(rows)

    edited_df = st.data_editor(
        df_edit,
        use_container_width=True,
        hide_index=True,
        column_config={"Quantity": st.column_config.NumberColumn(min_value=0, step=1)}
    )

    if st.button("Update Session Data"):
        new_data = {}
        for _, r in edited_df.iterrows():
            qty = clean_number(r["Quantity"])
            if qty > 0: new_data[str(r["Defect Category"])] = qty

        st.session_state.monthly_data[edit_month] = new_data
        st.success(f"Session data updated for {edit_month}.")

# ============================================================
# PAGE 4: HYBRID IMPORT (AUTO DRIVE SYNC & DIRECT UPLOAD)
# ============================================================

elif page == "Upload / Sync Data":
    st.title("Data Import & Google Drive Sync")
    st.caption("Seluruh file Excel yang di-upload akan tersimpan otomatis ke Folder Google Drive.")

    tab1, tab2 = st.tabs(["📁 Sync dari Google Drive", "📤 Upload File ke Google Drive"])

    with tab1:
        st.subheader("Baca Folder Google Drive")
        st.info("Sistem akan memindai folder Google Drive dan memproses seluruh file Excel di dalamnya.")
        
        folder_input = st.text_input("Google Drive Folder ID", value=DEFAULT_FOLDER_ID)

        if st.button("🔄 Sync Data dari Google Drive", type="primary"):
            with st.spinner("Membaca dan memproses file dari Google Drive..."):
                synced_count = sync_data_from_gdrive(folder_input)
                if synced_count > 0:
                    st.success(f"Berhasil membaca {synced_count} sheet data dari Google Drive!")
                else:
                    st.warning("Tidak ada file Excel yang ditemukan di folder ini atau folder tidak dapat diakses.")

    with tab2:
        st.subheader("Upload File Excel Langsung ke Google Drive")
        uploaded_file = st.file_uploader("Pilih File Excel (.xlsx)", type=["xlsx", "xls"])

        if uploaded_file is not None:
            if st.button("🚀 Upload File & Sync Dashboard", type="primary"):
                with st.spinner("Mengunggah file ke Google Drive..."):
                    file_bytes = uploaded_file.getvalue()
                    file_name = uploaded_file.name

                    # 1. Upload file fisik langsung ke Google Drive
                    if upload_file_to_gdrive(file_bytes, file_name, DEFAULT_FOLDER_ID):
                        st.success(f"File **{file_name}** berhasil disimpan di Google Drive!")
                        
                        # 2. Re-sync data dari Google Drive
                        synced = sync_data_from_gdrive(DEFAULT_FOLDER_ID)
                        st.success(f"Dashboard berhasil disinkronkan dari Google Drive! ({synced} sheet terproses)")

# ============================================================
# PAGE 5: EXPORT REPORTS
# ============================================================

elif page == "Export Reports":
    st.title("Export & Data Management")

    overall = build_overall_dataframe()

    if overall.empty:
        st.info("No current data available for export.")
    else:
        st.dataframe(overall, use_container_width=True, hide_index=True)

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            overall.to_excel(writer, sheet_name="Defect Summary", index=False)

        st.download_button(
            "Download Excel Report",
            data=buffer.getvalue(),
            file_name="D52B_Quality_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )