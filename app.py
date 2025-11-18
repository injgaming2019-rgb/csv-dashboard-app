import streamlit as st
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ==============================
# Sessão com Retry (anti erro 429/500)
# ==============================
def requests_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    return session


# ==============================
# Autenticação CrowdStrike
# ==============================
def get_token(base_url, client_id, client_secret):
    url = f"{base_url}/oauth2/token"
    session = requests_session()

    resp = session.post(url, data={
        "client_id": client_id,
        "client_secret": client_secret
    }, timeout=20)

    if resp.status_code != 200:
        raise Exception(f"Erro ao obter token ({resp.status_code}): {resp.text}")

    token = resp.json().get("access_token")
    if not token:
        raise Exception("Token não retornado pela API.")

    return token


# ==============================
# Buscar IDs dos hosts
# ==============================
def get_device_ids(base_url, token):
    url = f"{base_url}/devices/queries/devices/v1"
    headers = {"Authorization": f"Bearer {token}"}
    session = requests_session()

    resp = session.get(url, headers=headers, timeout=20)

   if response.status_code not in [200, 201]:
        raise Exception(f"Erro ao buscar IDs ({resp.status_code}): {resp.text}")

    return resp.json().get("resources", [])


# ==============================
# Buscar detalhes dos hosts (até 400 por chamada)
# ==============================
def get_device_details(base_url, token, ids):
    headers = {"Authorization": f"Bearer {token}"}
    session = requests_session()

    chunks = [ids[i:i+400] for i in range(0, len(ids), 400)]
    all_resources = []

    for chunk in chunks:
        ids_param = ",".join(chunk)
        url = f"{base_url}/devices/entities/devices/v2?ids={ids_param}"

        resp = session.get(url, headers=headers, timeout=30)

        if resp.status_code != 200:
            raise Exception(f"Erro ao buscar detalhes ({resp.status_code}): {resp.text}")

        resources = resp.json().get("resources", [])
        all_resources.extend(resources)

    return pd.json_normalize(all_resources)


# ==============================
# Interface Streamlit
# ==============================
st.set_page_config(page_title="Host Dashboard – CrowdStrike", layout="wide")

st.title("📊 CrowdStrike Executive Host Dashboard")
st.markdown("Selecione o cliente abaixo para carregar o relatório.")


# ==============================
# Carregar tenants do Streamlit Secrets
# ==============================
tenants = st.secrets["tenants"]

tenant_names = {cfg["company_name"]: key for key, cfg in tenants.items()}
selected_company = st.selectbox("Selecione o Cliente", list(tenant_names.keys()))

selected_key = tenant_names[selected_company]
tenant_cfg = tenants[selected_key]

base_url = tenant_cfg["base_url"]
client_id = tenant_cfg["client_id"]
client_secret = tenant_cfg["client_secret"]


# ==============================
# Botão principal
# ==============================
if st.button("🔎 Carregar Hosts"):
    try:
        st.info("Obtendo token...")
        token = get_token(base_url, client_id, client_secret)

        st.info("Buscando IDs dos hosts...")
        ids = get_device_ids(base_url, token)

        if not ids:
            st.warning("Nenhum host retornado para este tenant.")
            st.stop()

        st.info(f"Total de IDs obtidos: {len(ids)}")

        st.info("Carregando detalhes dos hosts...")
        df = get_device_details(base_url, token, ids)

        st.success(f"Hosts carregados: {len(df)}")

        # ------------------------------
        # Métricas rápidas
        # ------------------------------
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Hosts", len(df))
        col2.metric("Windows", len(df[df["platform_name"] == "Windows"]))
        col3.metric("Linux", len(df[df["platform_name"] == "Linux"]))

        # ------------------------------
        # Botões de filtro
        # ------------------------------
        st.subheader("Filtros Rápidos")

        filtro = st.radio(
            "Escolha um filtro:",
            ["Todos", "Windows", "Linux", "Sensor Online", "Sensor Offline"],
            horizontal=True
        )

        df_filtered = df.copy()

        if filtro == "Windows":
            df_filtered = df[df["platform_name"] == "Windows"]
        elif filtro == "Linux":
            df_filtered = df[df["platform_name"] == "Linux"]
        elif filtro == "Sensor Online":
            df_filtered = df[df["status"] == "normal"]
        elif filtro == "Sensor Offline":
            df_filtered = df[df["status"] != "normal"]

        st.dataframe(df_filtered, use_container_width=True)

    except Exception as e:
        st.error(f"Erro encontrado: {e}")
        with st.expander("📄 Mostrar detalhes técnicos"):
            st.code(str(e))
