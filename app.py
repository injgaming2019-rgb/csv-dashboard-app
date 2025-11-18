import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
import plotly.io as pio
from PIL import Image

# ----------------------------
# ESTILO / CSS
# ----------------------------
st.set_page_config(page_title="CrowdStrike Premium Dashboard", layout="wide")
st.markdown("""
<style>
body {
    font-family: 'Roboto', sans-serif;
    background-color: #f9f9f9;
}
h1, h2, h3, h4 {
    color: #d32f2f;
}
.css-1aumxhk {
    border-radius: 8px;
}
.stButton>button {
    background-color: #d32f2f;
    color: white;
    border-radius: 10px;
}
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
# DASHBOARD CROWDSTRIKE
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

    # ----------------------------
    # KPI CARDS
    # ----------------------------
    st.subheader("📊 KPIs")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total Hosts", len(df))
    kpi2.metric("Sistemas Operacionais", df["os_version"].nunique() if "os_version" in df else 0)
    kpi3.metric("Versões do Sensor", df["agent_version"].nunique() if "agent_version" in df else 0)
    kpi4.metric("RFM Ativo", df["rfm_enabled"].sum() if "rfm_enabled" in df else 0)
    kpi5.metric("Proteção contra desinstalação", df["tamper_protection_enabled"].sum() if "tamper_protection_enabled" in df else 0)

    st.divider()

    # ----------------------------
    # FILTROS AVANÇADOS COMO TOGGLE
    # ----------------------------
    st.subheader("🎛️ Filtros Avançados")
    col1, col2, col3, col4 = st.columns(4)

    if "tamper_protection_enabled" in df.columns:
        choice = col1.radio("Anti-Tamper", ["Todos", "Sim", "Não"], horizontal=True)
        if choice != "Todos":
            df = df[df["tamper_protection_enabled"] == (choice=="Sim")]

    if "rfm_enabled" in df.columns:
        choice = col2.radio("RFM", ["Todos", "Sim", "Não"], horizontal=True)
        if choice != "Todos":
            df = df[df["rfm_enabled"] == (choice=="Sim")]

    if "os_version" in df.columns:
        so_list = ["Todos"] + sorted(df["os_version"].dropna().unique().tolist())
        choice = col3.selectbox("SO", so_list)
        if choice != "Todos":
            df = df[df["os_version"]==choice]

    if "agent_version" in df.columns:
        agent_list = ["Todos"] + sorted(df["agent_version"].dropna().unique().tolist())
        choice = col4.selectbox("Versão Sensor", agent_list)
        if choice != "Todos":
            df = df[df["agent_version"]==choice]

    st.divider()

    # ----------------------------
    # GRÁFICOS INTERATIVOS
    # ----------------------------
    st.subheader("📈 Gráficos")
    if "agent_version" in df:
        fig1 = px.bar(df["agent_version"].value_counts(), title="Distribuição por Versão do Sensor", color_discrete_sequence=['#d32f2f'])
        st.plotly_chart(fig1, use_container_width=True)
    if "os_version" in df:
        fig2 = px.pie(df, names="os_version", title="Distribuição por Sistema Operacional", color_discrete_sequence=px.colors.sequential.Reds)
        st.plotly_chart(fig2, use_container_width=True)

    # ----------------------------
    # EXPORT PDF ESTILO BI
    # ----------------------------
    def export_pdf():
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Título
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(colors.HexColor("#d32f2f"))
        c.drawString(30, height - 50, f"Dashboard CrowdStrike - {selected_company}")

        # KPIs
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.black)
        c.drawString(30, height - 90, f"Total Hosts: {len(df)}")
        c.drawString(180, height - 90, f"SOs: {df['os_version'].nunique() if 'os_version' in df else 0}")
        c.drawString(320, height - 90, f"Versões Sensor: {df['agent_version'].nunique() if 'agent_version' in df else 0}")
        c.drawString(500, height - 90, f"RFM Ativo: {df['rfm_enabled'].sum() if 'rfm_enabled' in df else 0}")
        c.drawString(30, height - 110, f"Proteção Anti-Desinstalação: {df['tamper_protection_enabled'].sum() if 'tamper_protection_enabled' in df else 0}")

        # Gráfico Agent Version
        if "agent_version" in df:
            fig1.write_image("temp_agent.png", width=600, height=400)
            img = Image.open("temp_agent.png")
            c.drawInlineImage(img, 30, height - 450, width=500, height=300)

        # Gráfico SO
        if "os_version" in df:
            fig2.write_image("temp_os.png", width=600, height=400)
            img2 = Image.open("temp_os.png")
            c.drawInlineImage(img2, 30, height - 780, width=500, height=300)

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    st.download_button(f"📥 Exportar PDF - {selected_company}", data=export_pdf(),
                       file_name=f"{selected_company}_Dashboard.pdf", mime="application/pdf")

# ----------------------------
# UPLOAD CSV EXTERNO
# ----------------------------
st.subheader("📤 Upload CSV Externo")
uploaded_file = st.file_uploader("Envie seu CSV", type="csv")
if uploaded_file:
    df_csv = pd.read_csv(uploaded_file)
    st.write("### Dados Carregados")
    st.dataframe(df_csv, use_container_width=True)

    st.subheader("🎛️ Filtros CSV")
    for col in df_csv.columns:
        if df_csv[col].dtype == bool or df_csv[col].nunique() <= 10:
            choices = ["Todos"] + sorted(df_csv[col].dropna().unique().tolist())
            choice = st.radio(f"{col}", choices, horizontal=True)
            if choice != "Todos":
                df_csv = df_csv[df_csv[col]==choice]

    # Gráficos CSV (opcional)
    st.subheader("📈 Gráficos CSV")
    for col in df_csv.select_dtypes(include="number").columns:
        fig_csv = px.histogram(df_csv, x=col, title=f"Distribuição de {col}", color_discrete_sequence=['#d32f2f'])
        st.plotly_chart(fig_csv, use_container_width=True)

    def export_pdf_csv():
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(colors.HexColor("#d32f2f"))
        c.drawString(30, height - 50, f"Dashboard CSV Externo")

        y = height - 90
        for col in df_csv.columns:
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(colors.black)
            c.drawString(30, y, col)
            y -= 15
            c.setFont("Helvetica", 9)
            for val in df_csv[col].tolist()[:20]:
                c.drawString(35, y, str(val))
                y -= 12
                if y < 50:
                    c.showPage()
                    y = height - 50
            y -= 5

        c.save()
        buffer.seek(0)
        return buffer

    st.download_button("📥 Exportar PDF CSV", data=export_pdf_csv(),
                       file_name=f"{selected_company}_CSV_Dashboard.pdf", mime="application/pdf")
