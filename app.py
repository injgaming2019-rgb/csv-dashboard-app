import streamlit as st
import pandas as pd
import requests

# ---------------------------------
# UI CONFIG
# ---------------------------------

st.set_page_config(
    page_title="CrowdStrike Dashboard",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ CrowdStrike – Executive Dashboard")
st.write("Ferramenta simples e intuitiva para consulta de hosts e análise de CSV.")

st.divider()

# ---------------------------------
# CARREGAR TENANTS DO SECRETS
# ---------------------------------

if "tenants" not in st.secrets:
    st.error("Nenhum tenant configurado no secrets.toml.")
    st.stop()

tenants = st.secrets["tenants"]

tenant_keys = list(tenants.keys())
tenant_display_names = {key: tenants[key]["company_name"] for key in tenant_keys}

selected_label = st.selectbox(
    "Selecione o tenant",
    options=list(tenant_display_names.values())
)

# Mapeia de volta para o tenant real
selected_tenant_key = [
    key for key, name in tenant_display_names.items() if name == selected_label
][0]

tenant_cfg = tenants[selected_tenant_key]

# ---------------------------------
# FUNÇÃO: OBTER TOKEN
# ---------------------------------

def get_token(tenant_config):
    url = f"{tenant_config['base_url']}/oauth2/token"
    data = {
        "client_id": tenant_config["client_id"],
        "client_secret": tenant_config["client_secret"]
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(url, data=data, headers=headers)

    # Aceitar 200 ou 201
    if response.status_code not in [200, 201]:
        st.error(f"Erro ao obter token ({response.status_code}): {response.text}")
        return None

    return response.json().get("access_token")

# ---------------------------------
# FUNÇÃO: OBTER HOSTS
# ---------------------------------

def get_hosts(token, tenant_config):
    url = f"{tenant_config['base_url']}/devices/queries/devices-scroll/v1"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        st.error(f"Erro ao obter hosts ({response.status_code}): {response.text}")
        return None

    data = response.json()
    host_ids = data.get("resources", [])

    if not host_ids:
        st.warning("Nenhum host encontrado.")
        return pd.DataFrame()

    # Buscar detalhes
    details_url = f"{tenant_config['base_url']}/devices/entities/devices/v2"
    response = requests.post(details_url, headers=headers, json={"ids": host_ids})

    if response.status_code != 200:
        st.error("Erro ao buscar detalhes dos hosts.")
        return pd.DataFrame()

    hosts_info = response.json().get("resources", [])
    return pd.json_normalize(hosts_info)

# ---------------------------------
# BOTÃO PARA BUSCAR HOSTS
# ---------------------------------

st.subheader("🔍 Consultar Hosts do Tenant")

if st.button("Buscar Hosts"):
    with st.spinner("Obtendo token..."):
        token = get_token(tenant_cfg)

    if token:
        with st.spinner("Consultando hosts..."):
            df_hosts = get_hosts(token, tenant_cfg)

        if df_hosts is not None and not df_hosts.empty:
            st.success("Dados carregados com sucesso!")

            # Filtros
            st.subheader("🔎 Filtros")
            columns = df_hosts.columns.tolist()
            selected_columns = st.multiselect("Colunas a exibir", columns, default=columns)

            st.dataframe(df_hosts[selected_columns], use_container_width=True)

            st.download_button(
                "📥 Download Hosts em CSV",
                df_hosts.to_csv(index=False),
                "hosts.csv",
                "text/csv"
            )

st.divider()

# ---------------------------------
# UPLOAD CSV OPCIONAL
# ---------------------------------

st.subheader("📤 Importar CSV para Dashboard")

uploaded_file = st.file_uploader("Envie seu CSV", type="csv")

if uploaded_file:
    df_csv = pd.read_csv(uploaded_file)

    st.write("### Dados Carregados")
    st.dataframe(df_csv, use_container_width=True)

    cols = df_csv.columns.tolist()
    selected_cols_csv = st.multiselect("Filtrar colunas", cols, default=cols)

    st.dataframe(df_csv[selected_cols_csv], use_container_width=True)

    st.download_button(
        "📥 Download CSV Filtrado",
        df_csv[selected_cols_csv].to_csv(index=False),
        "csv_filtrado.csv",
        "text/csv"
    )

