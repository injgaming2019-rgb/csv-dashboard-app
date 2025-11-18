import streamlit as st
import pandas as pd
import io
import base64
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
import tempfile

st.set_page_config(page_title="Dashboard Automático", layout="wide")

st.title("📊 Criador Automático de Dashboard")
st.write("Faça upload de um arquivo CSV e gere relatório com um clique.")

uploaded_file = st.file_uploader("📁 Upload CSV", type=["csv"])

df = None
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        st.success("CSV carregado com sucesso!")
        st.dataframe(df.head(), use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao ler CSV: {e}")

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

if df is not None:
    if st.button("📄 GERAR RELATÓRIO"):
        try:
            charts = []

            numeric = df.select_dtypes(include="number").columns.tolist()
            categorical = df.select_dtypes(include="object").columns.tolist()

            st.subheader("📊 Gráficos Automáticos")

            if numeric:
                fig = px.histogram(df[numeric], title="Distribuição Numérica")
                st.plotly_chart(fig, use_container_width=True)
                charts.append(fig_to_png_bytes(fig))

            if categorical:
                col = categorical[0]
                fig2 = px.pie(df, names=col, title=f"Distribuição de {col}")
                st.plotly_chart(fig2, use_container_width=True)
                charts.append(fig_to_png_bytes(fig2))

            pdf_bytes = gerar_pdf(df, charts)

            b64 = base64.b64encode(pdf_bytes).decode()
            link = f'<a href="data:application/pdf;base64,{b64}" download="relatorio.pdf">📥 Baixar PDF</a>'
            st.markdown(link, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Erro ao gerar relatório: {e}")
