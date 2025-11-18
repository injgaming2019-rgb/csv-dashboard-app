import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="CrowdStrike Dashboard", layout="wide")

st.title("🔍 CrowdStrike Dashboard Inteligente")
st.write("Upload CSV, filtre hosts e consulte múltiplos tenants via API.")

# ------------------------------
# Leitura dos tenants do Streamlit Secrets
# ------------------------------
tenants = st.secrets.get("tenants", {})

tenant_names = list(tenants.keys())

st.sidebar.header("Tenants disponíveis")
selected_tenant = st.sidebar.selectbox("Selecione o tenant:", tenant_names)

def get_auth_headers(tenant):
    """Gera o token OAuth2 para o tenant selecionado."""
    tenant_data = tenants[tenant]

    cid = tenant_data["client_id"]
    secret = tenant_data["client_secret"]
    base = tenant_data["base_url"]

    auth_url = f"{base}/oauth2/token"

    resp = requests.post(
        auth_url,
        data={"client_id": cid, "client_secret": secret}
    )

    token = resp.json().get("access_token")

    return {"Authorization": f"Bearer {token}"}, base

# ------------------------------
# Upload de CSV
# ------------------------------
st.header("📁 Upload de Arquivo CSV")
uploaded = st.file_uploader("Selecione o arquivo CSV", type=["csv"])

if uploaded:
    df = pd.read_csv(uploaded)
    st.success("CSV carregado com sucesso!")

    st.subheader("📊 Visualização")
    st.dataframe(df)

    # Filtros automáticos
    st.subheader("🎛️ Filtros")
    col = st.selectbox("Selecione a coluna para filtrar", df.columns)
    val = st.text_input("Valor a filtrar")

    if st.button("Aplicar filtro"):
        st.dataframe(df[df[col].astype(str).str.contains(val, case=False, na=False)])

# ------------------------------
# Consultar hosts via API
# ------------------------------
st.header("🖥️ Consultar Hosts do CrowdStrike")

if st.button("Buscar hosts do tenant selecionado"):
    headers, base = get_auth_headers(selected_tenant)

    url = f"{base}/devices/queries/devices-scroll/v1"

    resp = requests.get(url, headers=headers)

    if resp.status_code == 200:
        host_ids = resp.json().get("resources", [])
        st.success(f"{len(host_ids)} hosts encontrados.")

        st.write(host_ids)
    else:
        st.error("Erro ao consultar a API.")
