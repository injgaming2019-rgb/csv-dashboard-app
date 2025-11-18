import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

# ----------------------------
# ESTILO / CSS
# ----------------------------
st.set_page_config(page_title="CrowdStrike Dashboard", layout="wide")
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
</style>
""", unsafe_allow_html=True)

st.title("🛡️ CrowdStrike Executive Dashboard")
st.write("Dashboard interativo com filtros, gráficos e exportação PDF estilo BI.")
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
    """Retorna todos os IDs de hosts usando paginação"""
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
    """Busca detalhes de todos os hosts sem filtrar nada"""
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
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Hosts", len(df))
    col2.metric("Sistemas Operacionais", df["os_version"].nunique() if "os_version" in df else 0)
    col3.metric("Versões do Sensor", df["agent_version"].nunique() if "agent_version" in df else 0)
    col4.metric("RFM Ativo", df["rfm_enabled"].sum() if "rfm_enabled" in df else 0)
    st.divider()

    # ----------------------------
    # FILTROS COMO TOGGLE / BOTÕES
    # ----------------------------
    st.subheader("🎛️ Filtros Avançados")
    filter1, filter2, filter3 = st.columns(3)

    if "tamper_protection_enabled" in df.columns:
        choice = filter1.radio("Anti-Tamper", ["Todos", "Sim", "Não"], horizontal=True)
        if choice != "Todos":
            df = df[df["tamper_protection_enabled"] == (choice=="Sim")]

    if "rfm_enabled" in df.columns:
        choice = filter2.radio("RFM", ["Todos", "Sim", "Não"], horizontal=True)
        if choice != "Todos":
            df = df[df["rfm_enabled"] == (choice=="Sim")]

    if "os_version" in df.columns:
        so_list = ["Todos"] + sorted(df["os_version"].dropna().unique().tolist())
        choice = filter3.selectbox("SO", so_list)
        if choice != "Todos":
            df = df[df["os_version"]==choice]

    st.divider()

    # ----------------------------
    # GRÁFICOS INTERATIVOS
    # ----------------------------
    st.subheader("📈 Gráficos")
    if "agent_version" in df:
        fig1 = px.bar(df["agent_version"].value_counts(), title="Distribuição por Versão do Sensor")
        st.plotly_chart(fig1, use_container_width=True)
    if "os_version" in df:
        fig2 = px.pie(df, names="os_version", title="Distribuição por Sistema Operacional")
        st.plotly_chart(fig2, use_container_width=True)

    # ----------------------------
    # TABELA E PDF BI
    # ----------------------------
    st.subheader("📄 Tabela")
    cols = st.multiselect("Colunas", df.columns.tolist(), default=df.columns.tolist())
    st.dataframe(df[cols], use_container_width=True)

    def export_pdf():
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Título e KPIs
        c.setFont("Helvetica-Bold", 18)
        c.drawString(30, height - 50, f"Dashboard CrowdStrike - {selected_company}")
        c.setFont("Helvetica", 12)
        c.drawString(30, height - 80, f"Total Hosts: {len(df)}")
        c.drawString(200, height - 80, f"SOs: {df['os_version'].nunique() if 'os_version' in df else 0}")
        c.drawString(350, height - 80, f"Versões Sensor: {df['agent_version'].nunique() if 'agent_version' in df else 0}")
        c.drawString(520, height - 80, f"RFM Ativo: {df['rfm_enabled'].sum() if 'rfm_enabled' in df else 0}")

        y = height - 120
        for col in cols:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(30, y, f"{col}")
            y -= 15
            c.setFont("Helvetica", 9)
            for val in df[col].tolist()[:20]:
                c.drawString(40, y, str(val))
                y -= 12
                if y < 50:
                    c.showPage()
                    y = height - 50
            y -= 5

        c.save()
        buffer.seek(0)
        return buffer

    st.download_button("📥 Exportar PDF BI", data=export_pdf(), file_name="dashboard_bi.pdf", mime="application/pdf")

st.divider()

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

    cols_csv = st.multiselect("Colunas CSV", df_csv.columns.tolist(), default=df_csv.columns.tolist())
    st.dataframe(df_csv[cols_csv], use_container_width=True)

    def export_pdf_csv():
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 18)
        c.drawString(30, height - 50, "Dashboard CSV Externo")

        y = height - 80
        for col in cols_csv:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(30, y, f"{col}")
            y -= 15
            c.setFont("Helvetica", 9)
            for val in df_csv[col].tolist()[:20]:
                c.drawString(40, y, str(val))
                y -= 12
                if y < 50:
                    c.showPage()
                    y = height - 50
            y -= 5

        c.save()
        buffer.seek(0)
        return buffer

    st.download_button("📥 Exportar PDF CSV", data=export_pdf_csv(), file_name="dashboard_csv_bi.pdf", mime="application/pdf")
