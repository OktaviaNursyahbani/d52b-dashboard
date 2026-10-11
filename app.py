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

PEMETAAN_AREA_LEADER = {
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

NAMA_AREA = list(PEMETAAN_AREA_LEADER.keys())

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

def normalisasi_area(value):
    text = normalisasi_teks(value)
    alias = {a.lower(): a for a in NAMA_AREA}
    return alias.get(text)

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

def baca_sheet_d52b(df, sheet_name):
    bulan = deteksi_bulan_dari_dataframe(df, sheet_name)
    hasil_total = {}

    for idx_baris in range(len(df)):
        baris = df.iloc[idx_baris]
        nama_ng = cari_ng_dalam_baris(baris)
        if not nama_ng or normalisasi_teks(nama_ng) == "total": 
            continue

        # 1. Baca dari kolom Total (Kolom 13 / M pada SUMMARY D52B)
        total_val = 0
        if len(baris) > 13 and pd.notna(baris.iloc[13]):
            total_val = bersihkan_angka(baris.iloc[13])
        
        # 2. Jika kolom 13 kosong, hitung dari penjumlahan kolom area (kolom 3-12)
        if total_val == 0:
            sum_area = 0
            for col_idx in range(3, min(13, len(baris))):
                sum_area += bersihkan_angka(baris.iloc[col_idx])
            total_val = sum_area

        if total_val > 0:
            hasil_total[nama_ng] = total_val

    return {"month": bulan, "area_data": {}, "total_data": hasil_total, "success": len(hasil_total) > 0}

# ============================================================
# FUNGSI DATABASE GOOGLE DRIVE
# ============================================================

def buat_koneksi_drive():
    try:
        creds_info = dict(st.secrets.get("connections", {}).get("gsheets", {}))
        if not creds_info: creds_info = dict(st.secrets)

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

def unggah_file_ke_drive(file_bytes, file_name, folder_id):
    service = buat_koneksi_drive()
    if not service: return False

    try:
        clean_folder_id = str(folder_id).strip().strip("'\"")
        file_metadata = {'name': file_name, 'parents': [clean_folder_id]}
        media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True
    except Exception as e:
        st.error(f"Gagal mengunggah file ke Google Drive: {e}")
        return False

def sinkronkan_data_dari_drive(folder_id):
    service = buat_koneksi_drive()
    if not service: return 0

    try:
        clean_folder_id = str(folder_id).strip().strip("'\"")
        query = f"'{clean_folder_id}' in parents and (mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or mimeType='application/vnd.ms-excel') and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        if not files: return 0

        # Reset data sesi awal
        st.session_state.monthly_data = {m: {} for m in BULAN_LIST}
        jumlah_file = 0

        for file in files:
            file_name = file.get('name', '')
            bulan_file = deteksi_bulan_dari_teks(file_name)

            request = service.files().get_media(fileId=file['id'])
            file_stream = BytesIO(request.execute())
            excel = pd.ExcelFile(file_stream)

            # PRIORITAS HANYA BACA SHEET SUMMARY D52B (Mencegah Double Counting)
            target_sheet = None
            for s in excel.sheet_names:
                if "SUMMARY" in s.upper() or "REKAP" in s.upper():
                    target_sheet = s
                    break
            
            if not target_sheet and len(excel.sheet_names) > 0:
                target_sheet = excel.sheet_names[0]

            if target_sheet:
                df_sheet = pd.read_excel(file_stream, sheet_name=target_sheet, header=None)
                parsed = baca_sheet_d52b(df_sheet, target_sheet)

                # Prioritas bulan dari nama file atau isi sheet
                m = bulan_file or parsed.get("month") or deteksi_bulan_dari_teks(target_sheet)

                if m:
                    for ng, total in parsed.get("total_data", {}).items():
                        if ng not in st.session_state.monthly_data[m]:
                            st.session_state.monthly_data[m][ng] = 0
                        st.session_state.monthly_data[m][ng] += total
                    jumlah_file += 1

        return jumlah_file
    except Exception as e:
        st.error(f"Error membaca dari Google Drive: {e}")
        return 0

# ============================================================
# INISIALISASI SESSION STATE
# ============================================================

if "monthly_data" not in st.session_state:
    st.session_state.monthly_data = {m: {} for m in BULAN_LIST}

DEFAULT_FOLDER_ID = str(st.secrets.get("folder_id", "1XcgufwfNDrkOtdrXH34W6nybJkG3jX3U")).strip()

def buat_dataframe_bulan(bulan):
    data = st.session_state.monthly_data.get(bulan, {})
    if not data: return pd.DataFrame(columns=["NG", "Jumlah", "Persentase", "Kumulatif"])

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
    for m in BULAN_LIST:
        for ng_name, jmh in st.session_state.monthly_data.get(m, {}).items():
            if jmh > 0: baris.append({"Bulan": m, "NG": ng_name, "Jumlah": jmh})
    return pd.DataFrame(baris) if baris else pd.DataFrame(columns=["Bulan", "NG", "Jumlah"])

# ============================================================
# GRAFIK PLOTLY RESPONTIF
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

def buat_grafik_tren_top3_bulanan():
    semua_df = buat_dataframe_keseluruhan()
    if semua_df.empty:
        return None

    # Filter Top 3 per bulan untuk Januari - September
    top3_per_bulan = []
    for m in BULAN_LIST[:9]:
        df_m = semua_df[semua_df["Bulan"] == m]
        if not df_m.empty:
            top3 = df_m.sort_values("Jumlah", ascending=False).head(3)
            top3_per_bulan.append(top3)

    if not top3_per_bulan:
        return None

    df_top3_concat = pd.concat(top3_per_bulan)
    jenis_ng_top3 = df_top3_concat["NG"].unique()

    # Ambil tren pergerakan untuk semua jenis NG yang pernah masuk Top 3
    df_filtered = semua_df[semua_df["NG"].isin(jenis_ng_top3)].copy()

    fig = px.line(
        df_filtered,
        x="Bulan",
        y="Jumlah",
        color="NG",
        markers=True,
        category_orders={"Bulan": BULAN_LIST[:9]},
        title="<b>Tren Pergerakan Defect Top 3 per Bulan (Januari – September)</b>"
    )

    fig.update_layout(
        xaxis=dict(title="Bulan", gridcolor="#1e293b", showgrid=False),
        yaxis=dict(title="Jumlah Defect (Pcs)", gridcolor="#1e293b", showgrid=True),
        height=420,
        **TEMA_GELAP
    )
    return fig

# ============================================================
# NAVIGASI SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("### ⚡ Quality Hub D52B")
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
    st.caption("Penyimpanan Database: **Google Drive Folder**")

# ============================================================
# HALAMAN 1: RINGKASAN DASHBOARD
# ============================================================

if halaman == "Ringkasan Dashboard":
    st.title("Ringkasan Eksekutif Kualitas")
    st.caption("Analisis Defect Real-Time Berbasis Folder Google Drive")

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
        st.info("Belum ada data. Silakan lakukan sinkronisasi dari Google Drive di menu 'Upload / Sinkronisasi Data'.")

    st.markdown("---")
    st.subheader("📊 Grafik Tren Top 3 Defect (Januari – September)")
    st.caption("Menampilkan tren pergerakan khusus untuk jenis defect yang paling sering masuk 3 besar di setiap bulan.")

    if not semua_data.empty:
        fig_top3 = buat_grafik_tren_top3_bulanan()
        if fig_top3:
            st.plotly_chart(fig_top3, use_container_width=True)
        else:
            st.info("Data belum cukup untuk menampilkan grafik Top 3.")
    else:
        st.info("Sinkronkan data terlebih dahulu untuk melihat grafik tren Top 3.")

    st.markdown("---")
    c1, c2 = st.columns([2, 1])
    with c1: st.subheader("Analisis Pareto Defect")
    with c2: periode = st.selectbox("Filter Periode", ["Semua Bulan"] + BULAN_LIST)

    if periode == "Semua Bulan":
        df_periode = semua_data.groupby("NG")["Jumlah"].sum().reset_index() if not semua_data.empty else pd.DataFrame()
    else:
        df_periode = semua_data[semua_data["Bulan"] == periode].groupby("NG")["Jumlah"].sum().reset_index() if not semua_data.empty else pd.DataFrame()

    if not df_periode.empty and df_periode["Jumlah"].sum() > 0:
        total_p = df_periode["Jumlah"].sum()
        df_periode["Persentase"] = (df_periode["Jumlah"] / total_p * 100)
        df_periode = df_periode.sort_values("Jumlah", ascending=False).reset_index(drop=True)
        df_periode["Kumulatif"] = df_periode["Persentase"].cumsum()

        fig_pareto = buat_grafik_pareto(df_periode, f"Analisis Pareto — {periode}")
        st.plotly_chart(fig_pareto, use_container_width=True)
    else:
        st.warning(f"Tidak ada data ditemukan untuk periode: {periode}")

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
    data_saat_ini = st.session_state.monthly_data.get(bulan_edit, {})

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
        st.success(f"Data sesi berhasil diperbarui untuk bulan {bulan_edit}.")

# ============================================================
# HALAMAN 4: UPLOAD & SINKRONISASI DATA
# ============================================================

elif halaman == "Upload / Sinkronisasi Data":
    st.title("Impor Data & Sinkronisasi")
    st.caption("Seluruh file Excel yang di-upload akan tersimpan otomatis ke Folder Google Drive.")

    tab1, tab2 = st.tabs(["📁 Metode 1: Auto Sync Google Drive", "📤 Metode 2: Upload File Manual"])

    with tab1:
        st.subheader("Baca Otomatis Folder Google Drive")
        st.info("Sistem akan memindai folder Google Drive dan memproses seluruh file Excel di dalamnya.")
        
        folder_input = st.text_input("ID Folder Google Drive", value=DEFAULT_FOLDER_ID)

        if st.button("🔄 Sync Data dari Google Drive", type="primary"):
            with st.spinner("Membaca dan memproses file dari Google Drive..."):
                synced_count = sinkronkan_data_dari_drive(folder_input)
                if synced_count > 0:
                    st.success(f"Berhasil membaca {synced_count} file rekap dari Google Drive!")
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

                    if unggah_file_ke_drive(file_bytes, file_name, folder_input):
                        st.success(f"File **{file_name}** berhasil tersimpan di Google Drive!")
                        
                        synced = sinkronkan_data_dari_drive(folder_input)
                        st.success(f"Dashboard berhasil disinkronkan dari Google Drive! ({synced} file terproses)")

    st.markdown("---")
    st.subheader("🗑️ Bersihkan Data Sesi")
    st.caption("Gunakan tombol ini jika ingin menghapus seluruh data yang tampil di dashboard dan memulai dari awal.")

    if st.button("🚨 Hapus / Clear Seluruh Data Dashboard"):
        st.session_state.monthly_data = {m: {} for m in BULAN_LIST}
        st.success("Seluruh data dashboard berhasil dibersihkan!")
        st.rerun()

# ============================================================
# HALAMAN 5: EKSPOR LAPORAN
# ============================================================

elif halaman == "Ekspor Laporan":
    st.title("Ekspor & Manajemen Data")

    semua_rekap = buat_dataframe_keseluruhan()

    if semua_rekap.empty:
        st.info("Belum ada data yang tersedia untuk diekspor.")
    else:
        st.dataframe(semua_rekap, use_container_width=True, hide_index=True)

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            semua_rekap.to_excel(writer, sheet_name="Ringkasan Defect", index=False)

        st.download_button(
            "Unduh Laporan Excel",
            data=buffer.getvalue(),
            file_name="Laporan_Kualitas_D52B.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )