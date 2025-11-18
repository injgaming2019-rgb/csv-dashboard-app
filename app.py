import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# ---------------------------------------------------------
# CONFIGURAÇÃO DO APP
# ---------------------------------------------------------

st.set_page_config(
    page_title="CrowdStrike Executive Dashboard",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ CrowdStrike – Executive Dashboard")
st.write("Dashboard intuitivo para visualização de hosts, filtros avançados e análise gerencial.")

st.divider()

# ---------------------------------------------------------
# CARREGAR TENANTS DO SECRETS
# ---------------------------------------------------------

if "tenants" not in st.secrets:
    st.error("Nenhum tenant configurado no secrets.toml.")
    st.stop()

tenants = st.secrets["tenants"]

tenant_labels = {key: tenants[key]["company_name"] for key in tenants.keys()}
selected_company = st.selectbox("Selecione o Tenant", list(tenant_labels.values()))

selected_key = [k for k, v in tenant_labels.items() if v == selected_company][0]
tenant_cfg = tenants[selected_key]

# ---------------------------------------------------------
# FUNÇÃO: OBTER TOKEN
# ---------------------------------------------------------

def get_token(cfg):
    url = f"{cfg['base_url']}/oauth2/token"
    data = {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"]
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(url, data=data, headers=headers)

    if response.status_code not in [200, 201]:
        return None

    return response.json().get("access_token")

# ---------------------------------------------------------
# FUNÇÃO: BUSCAR IDS (SCROLL)
# ---------------------------------------------------------

def get_all_host_ids(token, cfg):
    url = f"{cfg['base_url']}/devices/queries/devices-scroll/v1"
    headers = {"Authorization": f"Bearer {token}"}
    
    ids = []
    body = {}

    while True:
        response = requests.post(url, headers=headers, json=body)
        if response.status_code != 200:
            st.error(f"Erro ao buscar IDs: {response.text}")
            return []

        data = response.json()
        ids.extend(data.get("resources", []))

        # Verifica próxima página
        scroll = data.get("meta", {}).get("pagination", {}).get("scroll")
        if not scroll:
            break

        body = {"scroll": scroll}

    return ids

# ---------------------------------------------------------
# FUNÇÃO: BUSCAR DETALHES DOS HOSTS
# ---------------------------------------------------------

def get_hosts_details(token, cfg, ids):
    url = f"{cfg['base_url']}/devices/entities/devices/v2"
    headers = {"Authorization": f"Bearer {token}"}

    # API aceita no máximo 500 IDs por requisição
    batches = [ids[i:i+500] for i in range(0, len(ids), 500)]
    all_hosts = []

    for batch in batches:
        response = requests.post(url, headers=headers, json={"ids": batch})
        if response.status_code != 200:
            st.error(f"Erro ao buscar detalhes: {response.text}")
            return pd.DataFrame()

        data = response.json().get("resources", [])
        all_hosts.extend(data)

    df = pd.json_normalize(all_hosts)
    return df

# ---------------------------------------------------------
# BOTÃO DE BUSCAR HOSTS
# ---------------------------------------------------------

st.subheader("🔍 Consultar Hosts")

if st.button("Buscar Hosts do Tenant"):
    with st.spinner("Autenticando..."):
        token = get_token(tenant_cfg)

    if not token:
        st.error("Erro ao obter token.")
        st.stop()

    with st.spinner("Buscando hosts..."):
        ids = get_all_host_ids(token, tenant_cfg)
        df = get_hosts_details(token, tenant_cfg, ids)

    if df.empty:
        st.warning("Nenhum host encontrado.")
        st.stop()

    st.success("Hosts carregados com sucesso!")

    # ---------------------------------------------------------
    # KPI CARDS
    # ---------------------------------------------------------
    st.subheader("📊 Indicadores Gerais")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total de Hosts", len(df))
    col2.metric("Modelos únicos", df["machine_domain"].nunique() if "machine_domain" in df else 0)
    col3.metric("Sistemas Operacionais", df["os_version"].nunique() if "os_version" in df else 0)
    col4.metric("Versões do Sensor", df["agent_version"].nunique() if "agent_version" in df else 0)

    st.divider()

    # ---------------------------------------------------------
    # FILTROS AVANÇADOS (RFM, ANTI-TAMPER, SENSOR, ETC.)
    # ---------------------------------------------------------

    st.subheader("🎛️ Filtros Avançados")
