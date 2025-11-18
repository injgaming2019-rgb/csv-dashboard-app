import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# ----------------------------
# CONFIGURAÇÃO DO APP
# ----------------------------
st.set_page_config(page_title="CrowdStrike Dashboard", layout="wide")
st.title("🛡️ CrowdStrike Executive Dashboard")
st.write("Dashboard intuitivo para análise de hosts e upload de CSV externo.")
st.divider()

# ----------------------------
# AUTENTICAÇÃO GOOGLE (placeholder)
# ----------------------------
st.subheader("🔐 Login Opcional")
st.info("Autenticação Google/MFA futura. Por enquanto acesso aberto.")

# ----------------------------
# CARREGAR TENANTS DO SECRETS
# ----------------------------
if "tenants" not in st.secrets:
    st.error("Nenhum tenant configurado no secrets.toml.")
    st.stop()

tenants = st.secrets["tenants"]
tenant_labels = {key: tenants[key]["company_name"] for key in tenants.keys()}

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
    return response.json().get("resources", [])

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
    return pd.json_normalize(all_hosts)

# ----------------------------
# DASHBOARD CROWDSTRIKE
# ----------------------------
st.subheader("🔍 Dashboard CrowdStrike")

if st.button("Buscar Hosts do Tenant"):
    with st.spinner("Obtendo token..."):
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
    # FILTROS AVANÇADOS
    # ----------------------------
    st.subheader("🎛️ Filtros Avançados")
    filter1, filter2, filter3 = st.columns(3)

    # Anti-Tamper
    if "tamper_protection_enabled" in df.columns:
        opt = ["Todos", "Sim", "Não"]
        choice = filter1.selectbox("Anti-Tamper", opt)
        if choice != "Todos":
            df = df[df["tamper_protection_enabled"] == (choice=="Sim")]

    # RFM
    if "rfm_enabled" in df.columns:
        opt = ["Todos", "Sim", "Não"]
        choice = filter2.selectbox("RFM", opt)
        if choice != "Todos":
            df = df[df["rfm_enabled"] == (choice=="Sim")]

    # Sistema Operacional
    if "os_version" in df.columns:
        opt = ["Todos"] + sorted(df["os_version"].dropna().unique().tolist())
        choice = filter3.selectbox("SO", opt)
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
    # TABELA E DOWNLOAD
    # ----------------------------
    st.subheader("📄 Tabela")
    cols = st.multiselect("Colunas", df.columns.tolist(), default=df.columns.tolist())
    st.dataframe(df[cols], use_container_width=True)
    st.download_button("📥 Baixar CSV", df.to_csv(index=False), "hosts_filtrados.csv", "text/csv")

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
    cols_csv = st.multiselect("Filtrar colunas", df_csv.columns.tolist(), default=df_csv.columns.tolist())
    st.dataframe(df_csv[cols_csv], use_container_width=True)
    st.download_button("📥 Baixar CSV Filtrado", df_csv[cols_csv].to_csv(index=False), "csv_filtrado.csv", "text/csv")
