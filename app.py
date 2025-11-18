import streamlit as st
import pandas as pd
import io
import base64
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
import tempfile

# ------------------------------
# CONFIGURAÇÃO DO APP
# ------------------------------
st.set_page_config(
    page_title="Dashboard Automático",
    layout="wide"
)

st.markdown("""
    <style>
        .main {background-color: #f8f9fa;}
        .block-container {padding-top: 2rem;}
        .stButton>button {
            width: 100%;
            border-radius: 10px;
            background-color: #222;
            color: white;
            height: 3rem;
        }
    </style>
""", unsafe_allow_html=True)

# ------------------------------
# CABEÇALHO
# ------------------------------
st.title("📊 Dashboard Automático")
st.caption("Upload • Filtros • Relatório em PDF • Interface minimalista")

# ------------------------------
# UPLOAD DO CSV
# ------------------------------
with st.container():
    st.subheader("📁 Upload do arquivo CSV")
    uploaded_file = st.file_uploader("", type=["csv"], label_visibility="collapsed")

df = None
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        st.success("Arquivo carregado com sucesso!")
        st.dataframe(df.head(), use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao carregar o CSV: {e}")

# --------------------------------------
# BOTÃO PARA HABILITAR FILTROS
# --------------------------------------
filtros_ativos = False
if df is not None:
    with st.container():
        st.subheader("🎛️ Controles")
        filtros_ativos = st.toggle("Ativar filtros avançados")

# --------------------------------------
# SEÇÃO DE FILTROS (SÓ APARECE SE ATIVADO)
# --------------------------------------
if df is not None and filtros_ativos:
    st.markdown("### 🔍 Filtros")
    
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(include="object").columns.tolist()

    col1, col2 = st.columns(2)

    filtros = {}

    # Filtro numérico
    with col1:
        if numeric_cols:
            col_num = st.selectbox("Coluna numérica", ["Nenhum"] + numeric_cols)
            if col_num != "Nenhum":
                min_val, max_val = st.slider(
                    f"Filtrar {col_num}",
                    float(df[col_num].min()),
                    float(df[col_num].max()),
                    (float(df[col_num].min()), float(df[col_num].max()))
                )
                filtros[col_num] = (min_val, max_val)

    # Filtro categórico
    with col2:
        if categorical_cols:
            col_cat = st.selectbox("Coluna categórica", ["Nenhum"] + categorical_cols)
            if col_cat != "Nenhum":
                categorias = st.multiselect(
                    f"Valores de {col_cat}",
                    df[col_cat].unique().tolist()
                )
                if categorias:
                    filtros[col_cat] = categorias

    aplicar = st.button("Aplicar filtros")

    if aplicar:
        df_filtrado = df.copy()
        for coluna, condição in filtros.items():
            if isinstance(condição, tuple):  # numérico
                df_filtrado = df_filtrado[df_filtrado[coluna].between(condição[0], condição[1])]
            else:  # categórico
                df_filtrado = df_filtrado[df_filtrado[coluna].isin(condição)]
        df = df_filtrado
        st.success("Filtros aplicados!")
        st.dataframe(df, use_container_width=True)

# ------------------------------
# FUNÇÕES AUXILIARES
# ------------------------------
def fig_to_png_bytes(fig):
    buf = io.BytesIO()
    fig.write_image(buf, format="png")
    buf.seek(0)
    return buf.read()

def gerar_pdf(df, imagens):
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(temp_pdf.name, pagesize=A4)

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Relatório Automático", styles["Title"]))
    story.append(Spacer(1,12))
    story.append(Paragraph(f"Linhas: {len(df)} — Colunas: {len(df.columns)}", styles["Normal"]))
    story.append(Spacer(1,12))

    story.append(Paragraph("Colunas:", styles["Heading2"]))
    story.append(Paragraph(", ".join(df.columns), styles["Normal"]))
    story.append(Spacer(1,12))

    for img_bytes in imagens:
        tmp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp_img.write(img_bytes)
        tmp_img.flush()
        story.append(Image(tmp_img.name, width=480, height=280))
        story.append(Spacer(1, 12))

    doc.build(story)

    with open(temp_pdf.name, "rb") as f:
        return f.read()

# ------------------------------
# GERAR RELATÓRIO FINAL
# ------------------------------
if df is not None:
    st.subheader("📄 Relatório")
    if st.button("Gerar Relatório PDF"):
        try:
            charts = []

            numeric = df.select_dtypes(include="number").columns.tolist()
            categorical = df.select_dtypes(include="object").columns.tolist()

            st.subheader("📊 Dashboard")

            # gráfico numérico
            if numeric:
                fig = px.histogram(df[numeric], title="Distribuição Numérica")
                st.plotly_chart(fig, use_container_width=True)
                charts.append(fig_to_png_bytes(fig))

            # gráfico categórico
            if categorical:
                col = categorical[0]
                fig2 = px.pie(df, names=col, title=f"Distribuição de {col}")
                st.plotly_chart(fig2, use_container_width=True)
                charts.append(fig_to_png_bytes(fig2))

            # gerar PDF
            pdf_bytes = gerar_pdf(df, charts)

            b64 = base64.b64encode(pdf_bytes).decode()
            link = f'<a href="data:application/pdf;base64,{b64}" download="relatorio.pdf">📥 Baixar PDF</a>'
            st.markdown(link, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Erro ao gerar o relatório: {e}")


