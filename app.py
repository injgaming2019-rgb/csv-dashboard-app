import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="CrowdStrike Executive Dashboard",
                   layout="wide",
                   initial_sidebar_state="expanded")

st.title("🛡️ CrowdStrike Executive Dashboard")
st.write("Dashboard intuitivo para análise de hosts, filtros inteligentes e relatórios executivos.")

# ==========================================
#      TENANT SELECTION
# ==========================================
tenants = st.secrets.get("tenants", {})
tenant_names = list(tenants.keys())

st.sidebar.header("🌐 Seleção de Tenant")
selected_tenant = st.sidebar.selectbox("Selecione o Tenant (Company)", tenant_names)

def get_auth_headers(tenant_key):
    """Retorna headers com Bearer Token para o tenant."""
    tenant_info = tenants[tenant_key]

    cid = tenant_info["client_id"]
    secret = tenant_info["client_secret"]
    base = tenant_info["base_url"]

    resp = requests.post(
        f"{base}/oauth2/token",
        data={"client_id": cid, "client_secret": secret}
    )

    token = resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}, base


# ==========================================
#      HOST RETRIEVAL
# ==========================================
st.header("🖥️ Host Inventory")

if st.button("🔍 Buscar hosts do tenant selecionado"):
    headers, base = get_auth_headers(selected_tenant)

    # Query hosts
    url = f"{base}/devices/queries/devices-scroll/v1"
    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        st.error("Erro ao buscar hosts.")
    else:
        ids = resp.json().get("resources", [])

        st.success(f"{len(ids)} hosts encontrados no tenant **{selected_tenant}**.")

        if len(ids) == 0:
            st.stop()

        # GET HOST DETAILS
        detail_url = f"{base}/devices/entities/devices/v2?ids=" + "&ids=".join(ids[:400])  # limit safety
        detail_resp = requests.get(detail_url, headers=headers)

        if detail_resp.status_code != 200:
            st.error("Erro ao buscar detalhes dos hosts.")
            st.stop()

        hosts = detail_resp.json().get("resources", [])
        df = pd.DataFrame(hosts)

        st.subheader("📊 Tabela completa")
        st.dataframe(df)

        # ==========================================
        #          FILTER BUTTONS
        # ==========================================

        st.subheader("🎛️ Filtros Inteligentes")

        if "Platform" in df.columns:
            platform_filter = st.multiselect("SO / Plataforma", df["platform_name"].dropna().unique())
        else:
            platform_filter = []

        if "agent_version" in df.columns:
            version_filter = st.multiselect("Versão do Sensor", df["agent_version"].dropna().unique())
        else:
            version_filter = []

        if len(platform_filter) > 0:
            df = df[df["platform_name"].isin(platform_filter)]

        if len(version_filter) > 0:
            df = df[df["agent_version"].isin(version_filter)]

        st.success(f"{df.shape[0]} hosts após filtros")

        # ==========================================
        #        EXECUTIVE DASHBOARD
        # ==========================================
        st.header("📈 Executive Dashboard")

        col1, col2, col3 = st.columns(3)

        col1.metric("Total de Hosts", df.shape[0])
        
        if "platform_name" in df.columns:
            top_os = df["platform_name"].value_counts().idxmax()
            col2.metric("Plataforma Predominante", top_os)
        else:
            col2.metric("Plataforma Predominante", "N/D")

        if "agent_version" in df.columns:
            top_ver = df["agent_version"].value_counts().idxmax()
            col3.metric("Sensor Mais Comum", top_ver)
        else:
            col3.metric("Sensor Mais Comum", "N/D")

        # ---------- gráfico de plataformas ----------
        if "platform_name" in df.columns:
            fig_os = px.pie(df, names="platform_name", title="Distribuição por Sistema Operacional")
            st.plotly_chart(fig_os, use_container_width=True)

        # ---------- gráfico de versão ----------
        if "agent_version" in df.columns:
            fig_ver = px.bar(df["agent_version"].value_counts(), title="Versões do Sensor")
            st.plotly_chart(fig_ver, use_container_width=True)

        # DOWNLOAD BUTTON
        st.header("📥 Exportar Relatório")
        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "📤 Baixar relatório em CSV",
            csv,
            "hosts_filtrados.csv",
            "text/csv"
        )

# ==========================================
#       CSV IMPORT SECTION
# ==========================================
st.header("📁 Upload de CSV para Dashboard Local")

csv_file = st.file_uploader("Upload CSV", type=["csv"])

if csv_file:
    df_csv = pd.read_csv(csv_file)

    st.subheader("Visualização do CSV")
    st.dataframe(df_csv)

    st.subheader("Filtro Rápido no CSV")
    col = st.selectbox("Coluna para filtro", df_csv.columns)
    text = st.text_input("Texto a filtrar")

    if st.button("Aplicar Filtro no CSV"):
        st.dataframe(df_csv[df_csv[col].astype(str).str.contains(text, case=False, na=False)])
