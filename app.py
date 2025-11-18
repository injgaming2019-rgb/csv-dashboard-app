import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import streamlit_authenticator as stauth

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
st.write("Dashboard intuitivo com filtros, gráficos e exportação PDF.")
st.divider()

# ----------------------------
# AUTENTICAÇÃO DEMO STREAMLIT
# ----------------------------
st.subheader("🔐 Login obrigatório (Demo Google/MFA)")

credentials = {
    "usernames": {
        "demo_user": {
            "name": "Demo User",
            "email": "user@example.com",
            "password": "123"  # demo, em produção usar hash
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    "demo_cookie_name",
    "demo_signature_key",
    cookie_expiry_days=1
)

name, authentication_status, username = authenticator.login("Login", "main")
if not authentication_status:
    st.stop()

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

def get_host_ids(token, cfg):
    url = f"{cfg['base_url']}/devices/queries/devices/v1"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        st.error(f"Erro ao buscar IDs: {response.text}")
        return []
    ids = response.json().get("resources", [])
    return ids

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
    df = df[df["agent_version"].notnull()]  # apenas hosts com sensor
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
    with st.spinner("Buscando IDs dos hosts..."):
        ids = get_host_ids(token, tenant_cfg)
    if not ids:
        st.warning("Nenhum host encontrado.")
        st.stop()
    with st.spinner("Buscando detalhes dos hosts..."):
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

    # Anti-Tamper toggle
    if "tamper_protection_enabled" in df.columns:
        choice = filter1.radio("Anti-Tamper", ["Todos", "Sim", "Não"], horizontal=True)
        if choice != "Todos":
            df = df[df["tamper_protection_enabled"] == (choice=="Sim")]

    # RFM toggle
    if "rfm_enabled" in df.columns:
        choice = filter2.radio("RFM", ["Todos", "Sim", "Não"], horizontal=True)
        if choice != "Todos":
            df = df[df["rfm_enabled"] == (choice=="Sim")]

    # Sistema Operacional
    if "os_version" in df.columns:
        so_list = ["Todos"] + sorted(df["os_version"].dropna().unique().tolist())
        choice = filter3.selectbox("SO", so_list)
        if choice != "Todos":
            df = df[df["os_version"]==choice]

    st.divider()

    # ----------------------------
    # GRÁFICOS
    # ----------------------------
    st.subheader("📈 Gráficos")
    if "agent_version" in df:
        fig1 = px.bar(df["agent_version"].value_counts(), title="Distribuição por Versão do Sensor")
        st.plotly_chart(fig1, use_container_width=True)
    if "os_version" in df:
        fig2 = px.pie(df, names="os_version", title="Distribuição por Sistema Operacional")
        st.plotly_chart(fig2, use_container_width=True)

    # ----------------------------
    # TABELA E PDF
    # ----------------------------
    st.subheader("📄 Tabela")
    cols = st.multiselect("Colunas", df.columns.tolist(), default=df.columns.tolist())
    st.dataframe(df[cols], use_container_width=True)

    def export_pdf():
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(30, 750, f"Dashboard CrowdStrike - {selected_company}")
        c.setFont("Helvetica", 10)
        y = 700
        for col in cols:
            c.drawString(30, y, f"{col}: {df[col].tolist()[:10]}")
            y -= 15
            if y < 50:
                c.showPage()
                y = 750
        c.save()
        buffer.seek(0)
        return buffer

    st.download_button("📥 Exportar PDF", data=export_pdf(), file_name="dashboard.pdf", mime="application/pdf")

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

    # Filtros toggle para CSV
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
        c.setFont("Helvetica-Bold", 16)
        c.drawString(30, 750, "Dashboard CSV Externo")
        c.setFont("Helvetica", 10)
        y = 700
        for col in cols_csv:
            c.drawString(30, y, f"{col}: {df_csv[col].tolist()[:10]}")
            y -= 15
            if y < 50:
                c.showPage()
                y = 750
        c.save()
        buffer.seek(0)
        return buffer

    st.download_button("📥 Exportar PDF CSV", data=export_pdf_csv(), file_name="dashboard_csv.pdf", mime="application/pdf")

