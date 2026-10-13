import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import BytesIO
import re
import os
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

HAS_MATPLOTLIB = True

# ============================================================
# KONFIGURASI HALAMAN
# ============================================================

st.set_page_config(
    page_title="Pusat Kontrol Kualitas D52B",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# TAMPILAN CSS INDUSTRI RESPONTIF
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
# KONSTANTA DAN KONFIGURASI
# ============================================================

BULAN_LIST = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

ALIAS_BULAN = {
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

JENIS_NG = [
    "Jarak jahitan tidak standar", "Bahan Balap Tidak Standar", "Langkah Jahitan tidak standar",
    "Point tidak center", "Lipatan tidak standar", "Jahitan putus", "Jahitan loncat",
    "Jahitan keriput", "Jahitan gelombang", "Ex jarum", "Benang kendor (Machine)",
    "Benang Pecah", "Jahitan kenceng", "Benang over/ Keluar", "Bahan terlipat/Terjahit",
    "Tepu tidak terpotong", "Takure", "Sampah Benang Terjahit", "Kuncian putus/ Lepas / Tidak ada",
    "Noda bahan", "Part tidak terpasang", "Part terpasang terbalik", "Part salah pasang",
    "Tidak ada sutechi", "Part terpasang Double", "Over part", "Tidak ada Piping", "GAP Bahan Tidak Standar",
    "Arah motif terbalik", "Cacat bahan"
]

FOLDER_DATA_LOKAL = "data_excel"
FILE_DATABASE_JSON = "monthly_data.json"

if not os.path.exists(FOLDER_DATA_LOKAL):
    os.makedirs(FOLDER_DATA_LOKAL)

# ============================================================
# FUNGSI BANTUAN DATA
# ============================================================

def normalisasi_teks(value):
    if value is None: return ""
    text = str(value).strip().lower().replace("\n", " ").replace("\r", " ").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()

def bersihkan_angka(value):
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

def format_angka(value):
    try: return f"{int(round(value)):,}".replace(",", ".")
    except Exception: return "0"

def normalisasi_nama_ng(value):
    text = normalisasi_teks(value)
    pengganti = {
        "benang kendor ( machine )": "Benang kendor (Machine)",
        "benang kendor (machine)": "Benang kendor (Machine)",
        "benang over/ keluar": "Benang over/ Keluar",
        "benang over/keluar": "Benang over/ Keluar",
        "bahan balap tidak standar": "Bahan Balap Tidak Standar",
        "gap bahan tidak standar": "GAP Bahan Tidak Standar"
    }
    if text in pengganti: return pengganti[text]
    for item in JENIS_NG:
        if normalisasi_teks(item) == text: return item
    return str(value).strip()

def deteksi_bulan_dari_teks(text):
    if not text: return None
    value = normalisasi_teks(text)
    for alias, bulan in ALIAS_BULAN.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', value):
            return bulan
    for alias, bulan in ALIAS_BULAN.items():
        if alias in value:
            return bulan
    return None

def deteksi_bulan_dari_dataframe(df, sheet_name=""):
    bulan = deteksi_bulan_dari_teks(sheet_name)
    if bulan: return bulan
    for r in range(min(len(df), 25)):
        for c in range(min(len(df.columns), 15)):
            val = df.iloc[r, c]
            if pd.notna(val):
                m = deteksi_bulan_dari_teks(str(val))
                if m: return m
    return None

def cari_ng_dalam_baris(row):
    for val in row.iloc[:8]:
        if pd.notna(val):
            norm = normalisasi_nama_ng(val)
            if norm in JENIS_NG: return norm
    return None

# ============================================================
# PEMETAAN LEADER SESUAI STRUKTUR D52B (TABEL SEAT)
# ============================================================

def cari_leader_dan_line(part_name=""):
    pn = str(part_name).upper()
    if "FR SEAT BACK" in pn or "71073" in pn or "71074" in pn:
        return "Kiki", "Line FR SEAT BACK (Front Seat Back)"
    elif "FR SEAT CUSHION" in pn or "71071" in pn or "71072" in pn:
        return "Heri", "Line FR SEAT CUSHION (Front Seat Cushion)"
    elif "RR SEAT BACK" in pn or "71077" in pn or "71078" in pn:
        return "Yunita", "Line RR SEAT BACK (Rear Seat Back)"
    elif "RR SEAT CUSHION" in pn or "71075" in pn or "71076" in pn:
        return "Tiara", "Line RR SEAT CUSHION (Rear Seat Cushion)"
    elif "NO 2 SEAT" in pn or "79023" in pn or "79021" in pn:
        return "Rosim", "Line No 2 SEAT (Row 3 Seat Back & Cushion)"
    else:
        return "Leader Line Sewing D52B", "Line Sewing Assembly D52B"

def baca_sheet_d52b(df, sheet_name):
    bulan = deteksi_bulan_dari_dataframe(df, sheet_name)
    hasil_total = {}

    part_name_found = ""
    for r in range(min(10, len(df))):
        for c in range(min(10, len(df.columns))):
            val = str(df.iloc[r, c])
            if "COVER S/A" in val.upper() or "SEAT" in val.upper():
                part_name_found = val
                break

    for idx_baris in range(len(df)):
        baris = df.iloc[idx_baris]
        nama_ng = cari_ng_dalam_baris(baris)
        if not nama_ng or normalisasi_teks(nama_ng) == "total": 
            continue

        total_val = 0
        if len(baris) > 13 and pd.notna(baris.iloc[13]):
            total_val = bersihkan_angka(baris.iloc[13])
        
        if total_val == 0:
            sum_area = 0
            for col_idx in range(3, min(13, len(baris))):
                sum_area += bersihkan_angka(baris.iloc[col_idx])
            total_val = sum_area

        if total_val > 0:
            hasil_total[nama_ng] = total_val

    return {
        "month": bulan,
        "part_name": part_name_found,
        "total_data": hasil_total,
        "success": len(hasil_total) > 0
    }

# ============================================================
# FUNGSI LOKAL DATABASE & AMAN DARI ERROR
# ============================================================

def simpan_database_lokal(data):
    try:
        with open(FILE_DATABASE_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Gagal menyimpan ke penyimpanan lokal: {e}")

def muat_database_lokal():
    if os.path.exists(FILE_DATABASE_JSON):
        try:
            with open(FILE_DATABASE_JSON, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    res = {m: {} for m in BULAN_LIST}
                    for m in BULAN_LIST:
                        if m in loaded and isinstance(loaded[m], dict):
                            res[m] = loaded[m]
                    return res
        except Exception:
            pass
    return {m: {} for m in BULAN_LIST}

def muat_dan_sinkron_file_lokal():
    data_bulanan = {m: {} for m in BULAN_LIST}
    jumlah_file = 0

    if not os.path.exists(FOLDER_DATA_LOKAL):
        return 0

    files = [f for f in os.listdir(FOLDER_DATA_LOKAL) if f.endswith(('.xlsx', '.xls'))]
    if not files:
        return 0

    for file_name in files:
        file_path = os.path.join(FOLDER_DATA_LOKAL, file_name)
        bulan_file = deteksi_bulan_dari_teks(file_name)

        try:
            excel = pd.ExcelFile(file_path)
            target_sheet = None
            for s in excel.sheet_names:
                if "SUMMARY" in s.upper() or "REKAP" in s.upper():
                    target_sheet = s
                    break
            
            if not target_sheet and len(excel.sheet_names) > 0:
                target_sheet = excel.sheet_names[0]

            if target_sheet:
                df_sheet = pd.read_excel(file_path, sheet_name=target_sheet, header=None)
                parsed = baca_sheet_d52b(df_sheet, target_sheet)

                m = bulan_file or parsed.get("month") or deteksi_bulan_dari_teks(target_sheet)

                if m and m in data_bulanan:
                    for ng, total in parsed.get("total_data", {}).items():
                        if ng not in data_bulanan[m]:
                            data_bulanan[m][ng] = 0
                        data_bulanan[m][ng] += total
                    jumlah_file += 1
        except Exception as e:
            st.error(f"Error membaca file {file_name}: {e}")

    simpan_database_lokal(data_bulanan)
    st.session_state.monthly_data = data_bulanan
    return jumlah_file

# ============================================================
# INISIALISASI SESSION STATE & DUMMY DEFAULT
# ============================================================

if "monthly_data" not in st.session_state or not isinstance(st.session_state.monthly_data, dict):
    st.session_state.monthly_data = muat_database_lokal()

# Ambil data aman
def get_monthly_dict():
    data = st.session_state.get("monthly_data", {})
    if not isinstance(data, dict):
        data = {m: {} for m in BULAN_LIST}
        st.session_state.monthly_data = data
    return data

def buat_dataframe_bulan(bulan):
    monthly_dict = get_monthly_dict()
    data = monthly_dict.get(bulan, {})
    if not isinstance(data, dict) or not data:
        return pd.DataFrame(columns=["NG", "Jumlah", "Persentase", "Kumulatif"])

    df = pd.DataFrame(list(data.items()), columns=["NG", "Jumlah"])
    df["Jumlah"] = pd.to_numeric(df["Jumlah"], errors="coerce").fillna(0)
    df = df[df["Jumlah"] > 0].sort_values("Jumlah", ascending=False).reset_index(drop=True)

    if df.empty: return pd.DataFrame(columns=["NG", "Jumlah", "Persentase", "Kumulatif"])

    total = df["Jumlah"].sum()
    df["Persentase"] = (df["Jumlah"] / total * 100) if total > 0 else 0
    df["Kumulatif"] = df["Persentase"].cumsum()
    return df

def buat_dataframe_keseluruhan():
    baris = []
    monthly_dict = get_monthly_dict()
    for m in BULAN_LIST:
        m_data = monthly_dict.get(m, {})
        if isinstance(m_data, dict):
            for ng_name, jmh in m_data.items():
                qty = bersihkan_angka(jmh)
                if qty > 0:
                    baris.append({"Bulan": m, "NG": ng_name, "Jumlah": qty})
    return pd.DataFrame(baris) if baris else pd.DataFrame(columns=["Bulan", "NG", "Jumlah"])

# ============================================================
# GRAFIK PLOTLY
# ============================================================

TEMA_GELAP = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Inter, sans-serif", color="#94a3b8"),
    margin=dict(l=10, r=10, t=40, b=40),
    autosize=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

def buat_grafik_pareto(df, judul):
    if df.empty: return None
    data = df.sort_values("Jumlah", ascending=False).reset_index(drop=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=data["NG"], y=data["Jumlah"], name="Jumlah NG",
            marker_color="#3b82f6", marker_line_color="#1d4ed8", marker_line_width=1,
            text=data["Jumlah"], textposition="outside"
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
        title=dict(text=judul, font=dict(color="#f8fafc", size=14)),
        xaxis=dict(tickangle=-45, gridcolor="#1e293b", showgrid=False),
        yaxis=dict(title="Jumlah NG", gridcolor="#1e293b", showgrid=True),
        yaxis2=dict(title="Kumulatif (%)", range=[0, 105], showgrid=False),
        **TEMA_GELAP
    )
    return fig

def buat_grafik_tren_bulanan(df):
    if df.empty: return None
    monthly_sum = df.groupby("Bulan")["Jumlah"].sum().reindex(BULAN_LIST).fillna(0).reset_index()
    monthly_sum = monthly_sum[monthly_sum["Jumlah"] > 0]

    if monthly_sum.empty: return None

    max_val = monthly_sum["Jumlah"].max()
    warna = ["#ef4444" if v == max_val else "#3b82f6" for v in monthly_sum["Jumlah"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly_sum["Bulan"], y=monthly_sum["Jumlah"],
        text=monthly_sum["Jumlah"], textposition="outside",
        marker_color=warna, textfont=dict(color="#f8fafc")
    ))

    fig.update_layout(
        title=dict(text="Total Defect per Bulan (Tertinggi Diberi Highlight Merah)", font=dict(color="#f8fafc", size=14)),
        xaxis=dict(gridcolor="#1e293b", showgrid=False),
        yaxis=dict(title="Jumlah Defect", gridcolor="#1e293b", showgrid=True),
        height=350,
        **TEMA_GELAP
    )
    return fig

def buat_tabel_top3_bulanan():
    semua_df = buat_dataframe_keseluruhan()
    if semua_df.empty:
        return pd.DataFrame()

    baris = []
    for m in BULAN_LIST:
        df_m = semua_df[semua_df["Bulan"] == m]
        if df_m.empty:
            continue
        top3 = df_m.groupby("NG")["Jumlah"].sum().sort_values(ascending=False).head(3).reset_index()
        for rank, (_, row) in enumerate(top3.iterrows(), 1):
            baris.append({
                "Bulan": m,
                "Peringkat": f"#{rank}",
                "Jenis Defect (NG)": row["NG"],
                "Jumlah": int(row["Jumlah"])
            })
    return pd.DataFrame(baris) if baris else pd.DataFrame()

def buat_grafik_top3_bulanan():
    semua_df = buat_dataframe_keseluruhan()
    if semua_df.empty:
        return None

    rows_top3 = []
    for m in BULAN_LIST:
        df_m = semua_df[semua_df["Bulan"] == m]
        if df_m.empty:
            continue
        top3 = df_m.groupby("NG")["Jumlah"].sum().sort_values(ascending=False).head(3).reset_index()
        for rank, (_, row) in enumerate(top3.iterrows(), 1):
            rows_top3.append({
                "Bulan": m,
                "Rank": f"#{rank}",
                "NG_Lengkap": row["NG"],
                "Jumlah": int(row["Jumlah"])
            })

    if not rows_top3:
        return None

    df_top3 = pd.DataFrame(rows_top3)
    bulan_ada = [m for m in BULAN_LIST if m in df_top3["Bulan"].values]

    warna_rank = {"#1": "#1d4ed8", "#2": "#3b82f6", "#3": "#93c5fd"}
    label_rank = {"#1": "Rank 1 (Tertinggi)", "#2": "Rank 2", "#3": "Rank 3"}

    fig = go.Figure()
    for rank_val in ["#1", "#2", "#3"]:
        df_r = df_top3[df_top3["Rank"] == rank_val]
        fig.add_trace(go.Bar(
            name=label_rank[rank_val],
            x=df_r["Bulan"],
            y=df_r["Jumlah"],
            marker_color=warna_rank[rank_val],
            marker_line_color="rgba(255,255,255,0.08)",
            marker_line_width=1,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Jenis Defect: <b>%{customdata}</b><br>"
                "Jumlah: <b>%{y} pcs</b><extra></extra>"
            ),
            customdata=df_r["NG_Lengkap"]
        ))

    fig.update_layout(
        barmode="group",
        title=dict(text="Top 3 Defect per Bulan", font=dict(color="#f8fafc", size=14, family="Inter, sans-serif")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
        margin=dict(l=10, r=10, t=70, b=40),
        autosize=True,
        xaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=bulan_ada,
            gridcolor="#1e293b",
            showgrid=False,
            tickfont=dict(color="#cbd5e1", size=12)
        ),
        yaxis=dict(
            title="Jumlah Defect (Pcs)",
            gridcolor="#1e293b",
            showgrid=True,
            tickfont=dict(color="#cbd5e1")
        ),
        legend=dict(
            title=dict(text="Peringkat", font=dict(color="#94a3b8")),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#cbd5e1")
        ),
        bargap=0.3,
        bargroupgap=0.06,
        height=420,
    )
    return fig

# ============================================================
# NAVIGASI SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("### D52B Quality Hub")
    st.caption("Dashboard Sewing Assembly")
    st.markdown("---")

    halaman = st.radio(
        "MENU NAVIGASI",
        [
            "Ringkasan Dashboard",
            "Pareto Bulanan",
            "Editor Data",
            "Upload / Sinkronisasi Data",
            "Ekspor Laporan"
        ]
    )

    st.markdown("---")
    st.caption("Penyimpanan Database: **Penyimpanan Lokal Server**")

# ============================================================
# HALAMAN 1: RINGKASAN DASHBOARD
# ============================================================

if halaman == "Ringkasan Dashboard":
    st.title("Ringkasan Eksekutif Kualitas")
    st.caption("Analisis Defect Real-Time Berbasis Penyimpanan Lokal")

    semua_data = buat_dataframe_keseluruhan()
    total_ng_semua = semua_data["Jumlah"].sum() if not semua_data.empty else 0

    if not semua_data.empty:
        grp_bulan = semua_data.groupby("Bulan")["Jumlah"].sum()
        bulan_tertinggi = grp_bulan.idxmax() if not grp_bulan.empty else "-"
        val_tertinggi = grp_bulan.max() if not grp_bulan.empty else 0
        top_ng_semua = semua_data.groupby("NG")["Jumlah"].sum().idxmax()
    else:
        bulan_tertinggi, val_tertinggi, top_ng_semua = "-", 0, "-"

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Volume Defect", format_angka(total_ng_semua))
    with col2: st.metric("Bulan Defect Tertinggi", f"{bulan_tertinggi}", f"{format_angka(val_tertinggi)} NG")
    with col3: st.metric("Jenis Defect Utama", top_ng_semua)
    with col4:
        bulan_aktif = len(semua_data["Bulan"].unique()) if not semua_data.empty else 0
        st.metric("Total Bulan Terrekam", f"{bulan_aktif} Bulan")

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("Perbandingan Defect Antar Bulan")
    if not semua_data.empty:
        fig_trend = buat_grafik_tren_bulanan(semua_data)
        if fig_trend: st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Belum ada data. Silakan lakukan upload di menu 'Upload / Sinkronisasi Data'.")

    st.markdown("---")
    st.subheader("Top 3 Defect per Bulan")
    st.caption("Tepat 3 jenis defect teratas di setiap bulan. Arahkan kursor ke bar untuk melihat nama lengkap.")

    if not semua_data.empty:
        fig_top3 = buat_grafik_top3_bulanan()
        if fig_top3:
            st.plotly_chart(fig_top3, use_container_width=True)

        df_tabel_top3 = buat_tabel_top3_bulanan()
        if not df_tabel_top3.empty:
            with st.expander("Lihat Tabel Ringkasan Top 3 per Bulan"):
                st.dataframe(df_tabel_top3, use_container_width=True, hide_index=True)

        # ============================================================
        # FITUR: PILIH BULAN & ANALISIS POS LEADER
        # ============================================================
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🎯 Analisis Rincian Defect per Bulan (Terurut Besar ke Kecil)")
        
        bulan_tersedia = [m for m in BULAN_LIST if m in semua_data["Bulan"].values]
        if not bulan_tersedia:
            bulan_tersedia = BULAN_LIST

        col_sel1, col_sel2 = st.columns([1, 2])
        with col_sel1:
            bulan_dipilih = st.selectbox("📌 Pilih Bulan Target Analisis", bulan_tersedia, index=0)

        df_bulan_pilihan = buat_dataframe_bulan(bulan_dipilih)

        if not df_bulan_pilihan.empty and df_bulan_pilihan["Jumlah"].sum() > 0:
            fig_p_bulan = buat_grafik_pareto(df_bulan_pilihan, f"Grafik Semua Defect (Terurut Besar ke Kecil) — Bulan {bulan_dipilih}")
            st.plotly_chart(fig_p_bulan, use_container_width=True)

            top_ng_row = df_bulan_pilihan.iloc[0]
            nama_top_ng = top_ng_row["NG"]
            jumlah_top_ng = int(top_ng_row["Jumlah"])
            persen_top_ng = round(top_ng_row["Persentase"], 2)

            leader_nama, line_area = cari_leader_dan_line(nama_top_ng)

            st.info(f"""
            **📌 KETERANGAN RINGKASAN DEFECT (BULAN {bulan_dipilih.upper()}):**
            * **Defect (NG) Terbanyak:** `{nama_top_ng}` sejumlah **{jumlah_top_ng} pcs** ({persen_top_ng}% dari total defect bulan {bulan_dipilih}).
            * **Pos / Area Line Utama:** **{line_area}**.
            * **Leader Penanggung Jawab:** **{leader_nama}**.
            """)
        else:
            st.warning(f"Belum ada data defect untuk bulan **{bulan_dipilih}**.")

    else:
        st.info("Upload data terlebih dahulu untuk melihat grafik tren Top 3.")

# ============================================================
# HALAMAN 2: PARETO BULANAN
# ============================================================

elif halaman == "Pareto Bulanan":
    st.title("Analisis Pareto Bulanan")

    bulan_pilihan = st.selectbox("Pilih Bulan Target", BULAN_LIST, index=0)
    df_bulan = buat_dataframe_bulan(bulan_pilihan)

    if df_bulan.empty:
        st.warning(f"Belum ada data yang dimuat untuk bulan **{bulan_pilihan}**.")
    else:
        total_ng = df_bulan["Jumlah"].sum()
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Total Defect Bulanan", format_angka(total_ng))
        with col2: st.metric("Kategori Defect Tertinggi", df_bulan.iloc[0]["NG"])
        with col3: st.metric("Jumlah Defect Tertinggi", format_angka(df_bulan.iloc[0]["Jumlah"]))

        fig = buat_grafik_pareto(df_bulan, f"Distribus Pareto — {bulan_pilihan}")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Tabel Rincian Defect — {bulan_pilihan}")
        display_df = df_bulan.copy()
        display_df["Persentase"] = display_df["Persentase"].round(2).astype(str) + " %"
        display_df["Kumulatif"] = display_df["Kumulatif"].round(2).astype(str) + " %"
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# ============================================================
# HALAMAN 3: EDITOR DATA
# ============================================================

elif halaman == "Editor Data":
    st.title("Tinjauan Data Manual")
    st.caption("Penyesuaian jumlah defect sesi aktif")

    bulan_edit = st.selectbox("Pilih Bulan yang Ingin Ditinjau", BULAN_LIST)
    data_saat_ini = get_monthly_dict().get(bulan_edit, {})

    baris_editor = [{"Kategori Defect": ng, "Jumlah": data_saat_ini.get(ng, 0)} for ng in JENIS_NG]
    df_editor = pd.DataFrame(baris_editor)

    edited_df = st.data_editor(
        df_editor,
        use_container_width=True,
        hide_index=True,
        column_config={"Jumlah": st.column_config.NumberColumn(min_value=0, step=1)}
    )

    if st.button("Simpan Data Sesi"):
        data_baru = {}
        for _, r in edited_df.iterrows():
            qty = bersihkan_angka(r["Jumlah"])
            if qty > 0: data_baru[str(r["Kategori Defect"])] = qty

        st.session_state.monthly_data[bulan_edit] = data_baru
        simpan_database_lokal(st.session_state.monthly_data)
        st.success(f"Data berhasil diperbarui dan tersimpan untuk bulan {bulan_edit}.")

# ============================================================
# HALAMAN 4: UPLOAD & SINKRONISASI DATA
# ============================================================

elif halaman == "Upload / Sinkronisasi Data":
    st.title("Impor Data Excel & Manajemen File")
    st.caption("Upload file rekap Excel (.xlsx / .xls). Seluruh file akan tersimpan aman di server lokal.")

    st.subheader("📤 Upload File Rekap Excel")
    uploaded_files = st.file_uploader("Pilih File Excel Rekap Bulanan", type=["xlsx", "xls"], accept_multiple_files=True)

    if uploaded_files:
        if st.button("🚀 Upload & Proses Data Excel", type="primary"):
            files_saved = 0
            for uploaded_file in uploaded_files:
                file_path = os.path.join(FOLDER_DATA_LOKAL, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                files_saved += 1
            
            terproses = muat_dan_sinkron_file_lokal()
            st.success(f"Berhasil mengunggah {files_saved} file dan memperbarui database dashboard! ({terproses} file terproses)")
            st.rerun()

    st.markdown("---")
    st.subheader("📁 Daftar File Terimpan di Server Lokal")
    files_lokal = [f for f in os.listdir(FOLDER_DATA_LOKAL) if f.endswith(('.xlsx', '.xls'))]
    
    if files_lokal:
        for f_name in files_lokal:
            col_f1, col_f2 = st.columns([4, 1])
            with col_f1:
                st.write(f"📄 **{f_name}**")
            with col_f2:
                if st.button("🗑️ Hapus", key=f"del_{f_name}"):
                    os.remove(os.path.join(FOLDER_DATA_LOKAL, f_name))
                    muat_dan_sinkron_file_lokal()
                    st.success(f"File {f_name} berhasil dihapus.")
                    st.rerun()
    else:
        st.info("Belum ada file Excel yang di-upload.")

    st.markdown("---")
    st.subheader("🗑️ Bersihkan Seluruh Data")
    st.caption("Gunakan tombol ini jika ingin menghapus seluruh data yang tersimpan.")

    if st.button("🚨 Hapus / Clear Seluruh Data"):
        st.session_state.monthly_data = {m: {} for m in BULAN_LIST}
        if os.path.exists(FILE_DATABASE_JSON):
            os.remove(FILE_DATABASE_JSON)
        for f in os.listdir(FOLDER_DATA_LOKAL):
            if f.endswith(('.xlsx', '.xls')):
                os.remove(os.path.join(FOLDER_DATA_LOKAL, f))
        st.success("Seluruh data berhasil dibersihkan!")
        st.rerun()

# ============================================================
# HALAMAN 5: EKSPOR LAPORAN
# ============================================================

elif halaman == "Ekspor Laporan":
    st.title("Ekspor & Manajemen Data Laporan")
    st.caption("Unduh laporan dalam format file Spreadsheet (Excel) atau Dokumen Ringkasan PDF (Grafik All & Per Bulan).")

    semua_rekap = buat_dataframe_keseluruhan()

    if semua_rekap.empty:
        st.info("Belum ada data yang tersedia untuk diekspor.")
    else:
        col_pdf, col_excel = st.columns(2)

        with col_pdf:
            st.subheader("📄 Laporan PDF (Grafik All & Pareto Per Bulan)")
            st.caption("Mencakup ringkasan metrik utama, grafik perbandingan bulanan, grafik Pareto All, dan Pareto per bulan.")
            if HAS_REPORTLAB and HAS_MATPLOTLIB:
                pdf_data = buat_laporan_pdf()
                if pdf_data:
                    st.download_button(
                        label="📄 Unduh Laporan PDF Dashboard (Lengkap)",
                        data=pdf_data.getvalue(),
                        file_name="Laporan_Kualitas_D52B_Lengkap.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
            else:
                st.warning("Pustaka pembentuk PDF belum siap.")

        with col_excel:
            st.subheader("📊 Laporan Excel (Data Mentah)")
            st.caption("Menyimpan seluruh data tabular rekapitulasi defect untuk keperluan analisis spreadsheet.")
            buffer_excel = BytesIO()
            with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
                semua_rekap.to_excel(writer, sheet_name="Ringkasan Defect", index=False)

            st.download_button(
                label="📊 Unduh Laporan Excel",
                data=buffer_excel.getvalue(),
                file_name="Laporan_Kualitas_D52B.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.markdown("---")
        st.subheader("Tinjauan Data Rekapitulasi")
        st.dataframe(semua_rekap, use_container_width=True, hide_index=True)
