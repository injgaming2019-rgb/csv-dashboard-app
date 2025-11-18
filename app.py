import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import streamlit_authenticator as stauth

# ----------------------------
# ESTILO / CSS
# ----------------------------
st.set_page_config(page_title="CrowdStrike Dashboard", layout="wide")
st.markdown("""
<style>
body {
    font-family: 'Roboto', sans-serif;
    background-color: #f9f9f9;
}
h1, h2, h3, h4 {
    color: #d32f2f;
}
.css-1aumxhk {
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ CrowdStrike Executive Dashboard")
st.write("Dashboard intuitivo com filtros, gráficos e exportação PDF.")
st.divider()

# ----------------------------
# AUTENTICAÇÃO DEMO STREAMLIT
# ----------------------------
st.subheader("
