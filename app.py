import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from datetime import datetime
from PIL import Image
import matplotlib.pyplot as plt

# ----------------------------
# ESTILO / CSS
# ----------------------------
st.set_page_config(page_title="CrowdStrike Premium Dashboard", layout="wide")
st.markdown("""
<style>
body {font-family: 'Roboto', sans-serif; background-color: #f9f9f9;}
h1, h2, h3, h4 {color: #d32f2f;}
.stButton>button {background-color: #d32f2f; color:white; border-radius:10px;}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ CrowdStrike Premium Dashboard")
st.write("Dashboard interativo com KPIs, filtros toggle e exportação PDF estilo BI.")
st.divider()

# ----------------------------
# CARREGAR TENANTS DO SECRETS
# ----------------------------
if "tenants" not in st.secrets:
    st.error("Nenhum tenant configurado no secrets.toml.")
    st.stop()

tenants = st.secrets["tenants"]
tenant_labels = {k: tenants[k]["company_name"] for k in tenants.keys()}
selected_company = st.selectbox("Selecione o Tenant", list(tenant_labels.values()))
selected_key = [k for k, v in tenant_labels.items() if v == selected_company][0]
tenant_cfg = tenants[selected_key]

# ----------------------------
# FUNÇÕES DE API
# ----------------------------
def get_token(cfg):
    url = f"{cfg['base_url']}/oauth2/token"
    data = {"client_id": cfg["client_id"], "client_secret": cfg["client_secret"]}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=data, headers=headers)
    if response.status_code not in [200, 201]:
        st.error(f"Erro ao obter token ({response.status_code}): {response.text}")
        return None
    return response.json().get("access_token")

def get_all_host_ids(token, cfg):
    url = f"{cfg['base_url']}/devices/queries/devices/v1"
    headers = {"Authorization": f"Bearer {token}"}
    all_ids = []
    offset = 0
    limit = 500
    while True:
        params = {"offset": offset, "limit": limit}
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            st.error(f"Erro ao buscar IDs: {resp.text}")
            break
        ids_batch = resp.json().get("resources", [])
        if not ids_batch:
            break
        all_ids.extend(ids_batch)
        offset += limit
    return all_ids

def get_hosts_details(token, cfg, ids):
    url = f"{cfg['base_url']}/devices/entities/devices/v2"
    headers = {"Authorization": f"Bearer {token}"}
    all_hosts = []
    for i in range(0, len(ids), 500):
        batch = ids[i:i+500]
        resp = requests.post(url, headers=headers, json={"ids": batch})
        if resp.status_code != 200:
            st.error(f"Erro ao buscar detalhes: {resp.text}")
            continue
        all_hosts.extend(resp.json().get("resources", []))
    if not all_hosts:
        return pd.DataFrame()
    df = pd.json_normalize(all_hosts)
    return df

# ----------------------------
# FUNÇÃO DE FILTROS AVANÇADOS
# ----------------------------
def aplicar_filtros(df):
    st.subheader("🎛️ Filtros Avançados")

    filtro_map = {
        "Sistema Operacional": "os_version",
        "Plataforma": "platform_name",
        "Versão do Sensor": "agent_version",
        "Política de Prevenção Aplicada": "policy_applied",
        "Uninstall Protection": "tamper_protection_enabled",
        "RFM": "rfm_enabled",
        "Duplicada": "is_duplicate"
    }

    for label, col in filtro_map.items():
        if col not in df.columns:
            continue
        df[col] = df[col].fillna("Desconhecido")
        # Booleans ou sim/não
        if df[col].dtype == bool or set(df[col].unique()) <= {True, False}:
            escolha = st.radio(label, ["Todos", "Sim", "Não"], horizontal=True)
            if escolha == "Sim":
                df = df[df[col] == True]
            elif escolha == "Não":
                df = df[df[col] == False]
        else:
            valores = ["Todos"] + sorted(df[col].astype(str).unique().tolist())
            escolha = st.selectbox(label, valores)
            if escolha != "Todos":
                df = df[df[col].astype(str) == escolha]

    return df

# ----------------------------
# FUNÇÃO PDF EXECUTIVO
# ----------------------------
def export_pdf_executivo(df, tenant_name):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Capa
    c.setFillColor(colors.HexColor("#d32f2f"))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(30, height - 50, f"Relatório Executivo - {tenant_name}")
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.black)
    c.drawString(30, height - 80, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # KPIs
    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, height - 120, "Principais Indicadores")
    c.setFont("Helvetica", 12)
    kpi_y = height - 150
    c.drawString(40, kpi_y, f"Total Hosts: {len(df)}")
    c.drawString(200, kpi_y, f"Sistemas Operacionais: {df['os_version'].nunique() if 'os_version' in df else 0}")
    c.drawString(400, kpi_y, f"Versões do Sensor: {df['agent_version'].nunique() if 'agent_version' in df else 0}")
    kpi_y -= 20
    c.drawString(40, kpi_y, f"RFM Ativo: {df['rfm_enabled'].sum() if 'rfm_enabled' in df else 0}")
    c.drawString(250, kpi_y, f"Proteção Anti-Desinstalação: {df['tamper_protection_enabled'].sum() if 'tamper_protection_enabled' in df else 0}")

    # Gráficos Matplotlib
    c.showPage()
    # Função auxiliar para agrupar valores pequenos como "Outros"
    def agrupar_outros(ser, lim=0.03):
        total = ser.sum()
        threshold = total * lim
        ser = ser.copy()
        outros = ser[ser <= threshold].sum()
        ser = ser[ser > threshold]
        if outros>0:
            ser["Outros"] = outros
        return ser

    # Gráfico Barra - Versão do Sensor
    if "agent_version" in df.columns:
        counts = df["agent_version"].value_counts()
        counts = agrupar_outros(counts)
        fig, ax = plt.subplots(figsize=(6,4))
        counts.plot(kind='bar', color='#d32f2f', ax=ax)
        ax.set_title("Distribuição por Versão do Sensor")
        plt.tight_layout()
        fig_path = "agent_plot.png"
        plt.savefig(fig_path)
        plt.close(fig)
        img = Image.open(fig_path)
        c.drawInlineImage(img, 50, height-450, width=500, height=350)

    # Gráfico Donut - Sistema Operacional
    if "os_version" in df.columns:
        counts2 = df["os_version"].value_counts()
        counts2 = agrupar_outros(counts2)
        fig2, ax2 = plt.subplots(figsize=(6,4))
        wedges, texts, autotexts = ax2.pie(counts2, labels=counts2.index, autopct='%1.1f%%', startangle=140)
        centre_circle = plt.Circle((0,0),0.70,fc='white')
        fig2.gca().add_artist(centre_circle)
        ax2.set_title("Distribuição por Sistema Operacional")
        plt.tight_layout()
        fig_path2 = "os_plot.png"
        plt.savefig(fig_path2)
        plt.close(fig2)
        img2 = Image.open(fig_path2)
        c.drawInlineImage(img2, 50, height-850, width=500, height=350)

    # Tabela resumo (Top 20)
    c.showPage()
    c.setFont("Helvetica-Bold", 16)
    c.drawString(30, height-50, "Resumo Hosts (Top 20)")
    table_data = [df.columns.tolist()] + df.head(20).values.tolist()
    table = Table(table_data, colWidths=[1.5*inch]*len(df.columns))
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#d32f2f")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ])
    table.setStyle(style)
    table.wrapOn(c, width-60, height-100)
    table.drawOn(c, 30, height-400)

    c.save()
    buffer.seek(0)
    return buffer

# ----------------------------
# DASHBOARD PRINCIPAL
# ----------------------------
st.subheader("🔍 Dashboard CrowdStrike")
if st.button("Buscar Hosts do Tenant"):
    with st.spinner("Autenticando..."):
        token = get_token(tenant_cfg)
    if not token:
        st.stop()

    with st.spinner("Buscando todos os IDs dos hosts..."):
        ids = get_all_host_ids(token, tenant_cfg)
    if not ids:
        st.warning("Nenhum host encontrado.")
        st.stop()

    with st.spinner("Buscando detalhes completos dos hosts..."):
        df = get_hosts_details(token, tenant_cfg, ids)
    if df.empty:
        st.warning("Nenhum host retornado.")
        st.stop()

    st.success(f"{len(df)} hosts carregados!")

    # Aplicar filtros avançados fixos
    df = aplicar_filtros(df)

    # KPIs Cards
    st.subheader("📊 KPIs")
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Total Hosts", len(df))
    kpi_cols[1].metric("Sistemas Operacionais", df["os_version"].nunique() if "os_version" in df else 0)
    kpi_cols[2].metric("Versões do Sensor", df["agent_version"].nunique() if "agent_version" in df else 0)
    kpi_cols[3].metric("RFM Ativo", df["rfm_enabled"].sum() if "rfm_enabled" in df else 0)
    kpi_cols[4].metric("Proteção Anti-Desinstalação", df["tamper_protection_enabled"].sum() if "tamper_protection_enabled" in df else 0)

    st.divider()

    # Gráficos interativos - barras
    st.subheader("📈 Gráficos")
    for col in ["agent_version","os_version"]:
        if col in df.columns:
            fig = plt.figure(figsize=(6,3))
            counts = df[col].value_counts()
            counts = counts[counts>max(1,int(len(df)*0.01))]  # classifica valores muito pequenos como Outras
            counts.plot(kind='bar', color='#d32f2f')
            plt.title(f"Distribuição de {col}")
            st.pyplot(fig)

    # Botão PDF Executivo
    st.download_button(
        f"📥 Exportar PDF Executivo - {selected_company}",
        data=export_pdf_executivo(df, selected_company),
        file_name=f"{selected_company}_Relatorio_Executivo.pdf",
        mime="application/pdf"
    )

# ----------------------------
# UPLOAD CSV EXTERNO
# ----------------------------
st.subheader("📤 Upload CSV Externo")
uploaded_file = st.file_uploader("Envie seu CSV", type="csv")
if uploaded_file:
    df_csv = pd.read_csv(uploaded_file)
    st.write("### Dados Carregados")
    st.dataframe(df_csv, use_container_width=True)

    # Aplicar filtros CSV
    df_csv = aplicar_filtros(df_csv)

    # Gráficos CSV
    st.subheader("📈 Gráficos CSV")
    for col in df_csv.select_dtypes(include="number").columns:
        fig_csv = plt.figure(figsize=(6,3))
        df_csv[col].hist(color='#d32f2f')
        plt.title(f"Distribuição de {col}")
        st.pyplot(fig_csv)

    # Export PDF CSV
    def export_pdf_csv():
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        c.setFillColor(colors.HexColor("#d32f2f"))
        c.setFont("Helvetica-Bold", 20)
        c.drawString(30, height-50, f"Dashboard CSV Externo - {selected_company}")
        y = height-90
        for col in df_csv.columns:
            c.setFont("Helvetica-Bold",10)
            c.setFillColor(colors.black)
            c.drawString(30, y, col)
            y-=15
            c.setFont("Helvetica",9)
            for val in df_csv[col].tolist()[:20]:
                c.drawString(35,y,str(val))
                y-=12
                if y<50:
                    c.showPage()
                    y = height-50
            y-=5
        c.save()
        buffer.seek(0)
        return buffer

    st.download_button("📥 Exportar PDF CSV", data=export_pdf_csv(),
                       file_name=f"{selected_company}_CSV_Dashboard.pdf", mime="application/pdf")
