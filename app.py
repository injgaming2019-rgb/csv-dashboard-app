import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="CrowdStrike Executive Dashboard",
                   layout="wide", initial_sidebar_state="expanded")

st.title("🛡️ Multi-Tenant Executive Dashboard")


# ==========================================
#      LOAD TENANTS WITH CUSTOM NAME
# ==========================================
raw_tenants = st.secrets.get("tenants", {})

tenants = {}
company_names = []

for t_key, t_data in raw_tenants.items():
    company = t_data.get("company_name", t_key)
    tenants[company] = {
        "id": t_key,
        "client_id": t_data.get("client_id"),
        "client_secret": t_data.get("client_secret"),
        "base_url": t_data.get("base_url")
    }
    company_names.append(company)

st.sidebar.header("🌐 Seleção de Empresa")
selected_company = st.sidebar.selectbox("Empresa:", company_names)

tenant_info = tenants[selected_company]


# ==========================================
#      AUTH FUNCTION
# ==========================================
def get_auth_headers(tenant):
    cid = tenant["client_id"]
    secret = tenant["client_secret"]
    base = tenant["base_url"]

    resp = requests.post(
        f"{base}/oauth2/token",
        data={"client_id": cid, "client_secret": secret}
    )
    token = resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}, base


# ==========================================
#      HOST RETRIEVAL (CrowdStrike)
# ==========================================
st.header(f"🖥️ Host Inventory — {selected_company}")

if st.button("🔍 Buscar hosts"):
    headers, base = get_auth_headers(tenant_info)

    url = f"{base}/devices/queries/devices-scroll/v1"
    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        st.error("Erro ao buscar hosts.")
        st.stop()

    ids = resp.json().get("resources", [])
    st.success(f"{len(ids)} hosts encontrados em **{selected_company}**")

    if not ids:
        st.stop()

    details_url = f"{base}/devices/entities/devices/v2?ids=" + "&ids=".join(ids[:400])
    details_resp = requests.get(details_url, headers=headers)

    if details_resp.status_code != 200:
        st.error("Erro ao buscar detalhes dos hosts.")
        st.stop()

    hosts = details_resp.json().get("resources", [])
    df = pd.DataFrame(hosts)

    # Show table
    st.subheader("📊 Tabela completa")
    st.dataframe(df)

    # Filters
    st.subheader("🎛️ Filtros")
    platform = st.multiselect("Plataforma", df.get("platform_name", pd.Series()).dropna().unique())
    version = st.multiselect("Versão do Sensor", df.get("agent_version", pd.Series()).dropna().unique())

    if platform:
        df = df[df["platform_name"].isin(platform)]
    if version:
        df = df[df["agent_version"].isin(version)]

    st.success(f"{df.shape[0]} hosts após filtros")

    # Dashboard
    st.header("📈 Executive Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Hosts", df.shape[0])
    col2.metric("Plataforma Predominante", df["platform_name"].mode()[0] if "platform_name" in df else "N/D")
    col3.metric("Sensor Mais Comum", df["agent_version"].mode()[0] if "agent_version" in df else "N/D")

    if "platform_name" in df:
        st.plotly_chart(px.pie(df, names="platform_name", title="Distribuição por OS"), use_container_width=True)

    if "agent_version" in df:
        st.plotly_chart(px.bar(df["agent_version"].value_counts(), title="Distribuição de Versões"), use_container_width=True)

    # Export
    st.header("📥 Exportar")
    st.download_button("📤 Baixar CSV", df.to_csv(index=False).encode("utf-8"), "hosts.csv")

# ==========================================
#      CSV UPLOAD
# ==========================================
st.header("📁 Upload CSV")
csv = st.file_uploader("Envie um CSV", type=["csv"])

if csv:
    df_csv = pd.read_csv(csv)
    st.dataframe(df_csv)
