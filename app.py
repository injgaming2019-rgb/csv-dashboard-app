import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
from docx import Document
from docx.shared import Inches
from PIL import Image
import matplotlib.pyplot as plt

# ----------------------------
# ESTILO / CSS
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
st.write("Dashboard interativo com filtros toggle, gráficos e exportação Word.")
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
# FUNÇÃO DE FILTROS AVANÇADOS
# ----------------------------
def aplicar_filtros(df):
    st.subheader("🎛️ Filtros Avançados")

    filtro_map = {
        "Sistema Operacional": "os_version",
        "Plataforma": "platform_name",
        "Versão do Sensor": "agent_version",
        "Política de Prevenção Aplicada": "policy_applied",
        "Uninstall Protection": "tamper_protection_enabled",
        "RFM": "rfm_enabled",
        "Duplicada": "is_duplicate"
    }

    for label, col in filtro_map.items():
        if col not in df.columns:
            continue
        df[col] = df[col].fillna("Desconhecido")
        if df[col].dtype == bool or set(df[col].unique()) <= {True, False}:
            escolha = st.radio(label, ["Todos", "Sim", "Não"], horizontal=True)
            if escolha == "Sim":
                df = df[df[col] == True]
            elif escolha == "Não":
                df = df[df[col] == False]
        else:
            valores = ["Todos"] + sorted(df[col].astype(str).unique().tolist())
            escolha = st.selectbox(label, valores)
            if escolha != "Todos":
                df = df[df[col].astype(str) == escolha]

    return df

# ----------------------------
# FUNÇÃO WORD EXECUTIVO
# ----------------------------
def export_word_executivo(df, tenant_name):
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

    # Gráficos - barras
    for col in ['agent_version', 'os_version']:
        if col in df.columns:
            fig, ax = plt.subplots(figsize=(4,2))
            counts = df[col].value_counts()
            counts = counts[counts>max(1,int(len(df)*0.01))]
            counts.plot(kind='bar', color='#d32f2f', ax=ax)
            ax.set_title(f"Distribuição de {col}")
            fig_path = f"{col}_plot.png"
            plt.tight_layout()
            plt.savefig(fig_path)
            plt.close(fig)
            doc.add_picture(fig_path, width=Inches(5))

    # Salvar documento
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ----------------------------
# DASHBOARD PRINCIPAL
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

    # Aplicar filtros avançados fixos
    df = aplicar_filtros(df)

    # KPIs Cards
    st.subheader("📊 KPIs")
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Total Hosts", len(df))
    kpi_cols[1].metric("Sistemas Operacionais", df["os_version"].nunique() if "os_version" in df else 0)
    kpi_cols[2].metric("Versões do Sensor", df["agent_version"].nunique() if "agent_version" in df else 0)
    kpi_cols[3].metric("RFM Ativo", df["rfm_enabled"].sum() if "rfm_enabled" in df else 0)
    kpi_cols[4].metric("Proteção Anti-Desinstalação", df["tamper_protection_enabled"].sum() if "tamper_protection_enabled" in df else 0)

    st.divider()

    # Gráficos interativos - barras menores
    st.subheader("📈 Gráficos")
    for col in ["agent_version","os_version"]:
        if col in df.columns:
            fig = plt.figure(figsize=(4,2))
            counts = df[col].value_counts()
            counts = counts[counts>max(1,int(len(df)*0.01))]  # classifica valores muito pequenos como Outras
            counts.plot(kind='bar', color='#d32f2f')
            plt.title(f"Distribuição de {col}")
            st.pyplot(fig)

    # Botão Word Executivo
    st.download_button(
        f"📥 Exportar Word Executivo - {selected_company}",
        data=export_word_executivo(df, selected_company),
        file_name=f"{selected_company}_Relatorio_Executivo.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

# ----------------------------
# UPLOAD CSV EXTERNO
# ----------------------------
st.subheader("📤 Upload CSV Externo")
uploaded_file = st.file_uploader("Envie seu CSV", type="csv")
if uploaded_file:
    df_csv = pd.read_csv(uploaded_file)
    st.write("### Dados Carregados")
    st.dataframe(df_csv, use_container_width=True)

    # Aplicar filtros CSV
    df_csv = aplicar_filtros(df_csv)

    # Gráficos CSV menores
    st.subheader("📈 Gráficos CSV")
    for col in df_csv.select_dtypes(include="number").columns:
        fig_csv = plt.figure(figsize=(4,2))
        df_csv[col].hist(color='#d32f2f')
        plt.title(f"Distribuição de {col}")
        st.pyplot(fig_csv)

    # Export Word CSV
    def export_word_csv():
        doc = Document()
        doc.add_heading(f'Dashboard CSV Externo - {selected_company}', 0)
        for col in df_csv.columns:
            doc.add_heading(col, level=1)
            for val in df_csv[col].tolist()[:50]:
                doc.add_paragraph(str(val))
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    st.download_button("📥 Exportar Word CSV", data=export_word_csv(),
                       file_name=f"{selected_company}_CSV_Dashboard.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
