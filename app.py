import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
from docx import Document
from docx.shared import Inches
import matplotlib.pyplot as plt

# ----------------------------
# Configuração da página e estilo
# ----------------------------
st.set_page_config(page_title="CrowdStrike Dashboard", layout="wide")
st.markdown("""
<style>
body {font-family: 'Roboto', sans-serif; background-color: #f9f9f9;}
h1, h2, h3, h4 {color: #d32f2f;}
.stButton>button {background-color: #d32f2f; color:white; border-radius:10px;}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ CrowdStrike Dashboard")
st.divider()

# ----------------------------
# Carregar tenants do secrets
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
# Funções de API
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
# Filtros avançados
# ----------------------------
def aplicar_filtros(df):
    st.subheader("🎛️ Filtros Avançados")
    filtros = {
        "Sistema Operacional": "os_version",
        "Plataforma": "platform_name",
        "Versão do Sensor": "agent_version",
        "Política Aplicada": "policy_applied",
        "Uninstall Protection": "tamper_protection_enabled",
        "RFM": "rfm_enabled",
        "Duplicada": "is_duplicate"
    }

    df_copy = df.copy()
    for label, col in filtros.items():
        if col not in df_copy.columns:
            continue
        df_copy[col] = df_copy[col].fillna("Desconhecido")
        if df_copy[col].dtype == bool or set(df_copy[col].unique()) <= {True, False}:
            escolha = st.radio(label, ["Todos", "Sim", "Não"], horizontal=True)
            if escolha == "Sim":
                df_copy = df_copy[df_copy[col] == True]
            elif escolha == "Não":
                df_copy = df_copy[df_copy[col] == False]
        else:
            valores = ["Todos"] + sorted(df_copy[col].astype(str).unique().tolist())
            escolha = st.selectbox(label, valores)
            if escolha != "Todos":
                df_copy = df_copy[df_copy[col].astype(str) == escolha]
    return df_copy

# ----------------------------
# Função para gráficos
# ----------------------------
def plot_with_others(df, col, kind="bar", width=4, height=3):
    counts = df[col].value_counts()
    threshold = max(1, int(len(df)*0.01))
    counts_small = counts[counts < threshold]
    counts_large = counts[counts >= threshold]
    counts_final = pd.concat([counts_large, pd.Series({'Outros': counts_small.sum()})])
    
    fig, ax = plt.subplots(figsize=(width, height))
    if kind == "bar":
        counts_final.plot(kind="bar", color="#d32f2f", ax=ax)
    elif kind == "pie":
        counts_final.plot(kind="pie", autopct='%1.1f%%', ax=ax)
    elif kind == "donut":
        counts_final.plot(kind="pie", autopct='%1.1f%%', ax=ax)
        ax.set(aspect="equal")
        centre_circle = plt.Circle((0,0),0.70,fc='white')
        fig.gca().add_artist(centre_circle)
    ax.set_title(col)
    plt.tight_layout()
    return fig

# ----------------------------
# Export Word Executivo
# ----------------------------
def export_word(df, tenant_name):
    doc = Document()
    doc.add_heading(f'Relatório Executivo - {tenant_name}', 0)
    doc.add_paragraph(f'Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}')
    doc.add_paragraph(f'Total Hosts: {len(df)}')

    # KPIs
    doc.add_heading("Principais Indicadores", level=1)
    kpi_table = doc.add_table(rows=2, cols=4)
    kpi_table.style = 'Light Grid Accent 1'
    kpi_table.rows[0].cells[0].text = "Sistemas Operacionais"
    kpi_table.rows[0].cells[1].text = "Versões do Sensor"
    kpi_table.rows[0].cells[2].text = "RFM Ativo"
    kpi_table.rows[0].cells[3].text = "Proteção Anti-Desinstalação"
    kpi_table.rows[1].cells[0].text = str(df['os_version'].nunique() if 'os_version' in df else 0)
    kpi_table.rows[1].cells[1].text = str(df['agent_version'].nunique() if 'agent_version' in df else 0)
    kpi_table.rows[1].cells[2].text = str(df['rfm_enabled'].sum() if 'rfm_enabled' in df else 0)
    kpi_table.rows[1].cells[3].text = str(df['tamper_protection_enabled'].sum() if 'tamper_protection_enabled' in df else 0)

    # Gráficos para Word
    for col in ['agent_version', 'os_version']:
        if col in df.columns:
            fig = plot_with_others(df, col, kind="bar", width=4, height=3)
            fig_path = f"{col}_plot.png"
            fig.savefig(fig_path)
            plt.close(fig)
            doc.add_picture(fig_path, width=Inches(5))
    return doc

# ----------------------------
# Dashboard principal
# ----------------------------
st.subheader("🔍 Dashboard CrowdStrike")
if st.button("Buscar Hosts do Tenant"):
    with st.spinner("Autenticando..."):
        token = get_token(tenant_cfg)
    if not token:
        st.stop()

    with st.spinner("Buscando IDs dos hosts..."):
        ids = get_all_host_ids(token, tenant_cfg)
    if not ids:
        st.warning("Nenhum host encontrado.")
        st.stop()

    with st.spinner("Buscando detalhes dos hosts..."):
        df = get_hosts_details(token, tenant_cfg, ids)
    if df.empty:
        st.warning("Nenhum host retornado.")
        st.stop()

    st.success(f"{len(df)} hosts carregados!")

    # Aplicar filtros avançados
    df_filtered = aplicar_filtros(df)

    # KPIs
    st.subheader("📊 KPIs")
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Total Hosts", len(df_filtered))
    kpi_cols[1].metric("Sistemas Operacionais", df_filtered["os_version"].nunique() if "os_version" in df_filtered else 0)
    kpi_cols[2].metric("Versões do Sensor", df_filtered["agent_version"].nunique() if "agent_version" in df_filtered else 0)
    kpi_cols[3].metric("RFM Ativo", df_filtered["rfm_enabled"].sum() if "rfm_enabled" in df_filtered else 0)
    kpi_cols[4].metric("Proteção Anti-Desinstalação", df_filtered["tamper_protection_enabled"].sum() if "tamper_protection_enabled" in df_filtered else 0)

    st.divider()

    # Gráficos
    st.subheader("📈 Gráficos Interativos")
    for col in ["agent_version","os_version"]:
        if col in df_filtered.columns:
            fig = plot_with_others(df_filtered, col, kind="bar", width=4, height=3)
            st.pyplot(fig)

    # Exportar Word
    word_file = export_word(df_filtered, selected_company)
    st.download_button(
        f"📥 Exportar Word Executivo - {selected_company}",
        data=word_file,
        file_name=f"{selected_company}_Relatorio_Executivo.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

# ----------------------------
# Upload CSV externo
# ----------------------------
st.subheader("📤 Upload CSV Externo")
uploaded_file = st.file_uploader("Envie seu CSV", type="csv")
if uploaded_file:
    df_csv = pd.read_csv(uploaded_file)
    st.write("### Dados Carregados")
    st.dataframe(df_csv, use_container_width=True)

    df_csv_filtered = aplicar_filtros(df_csv)

    st.subheader("📈 Gráficos CSV")
    for col in df_csv_filtered.select_dtypes(include="number").columns:
        fig_csv = plt.figure(figsize=(4,3))
        df_csv_filtered[col].hist(color='#d32f2f')
        plt.title(f"{col}")
        st.pyplot(fig_csv)
