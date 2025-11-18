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
with st.contain

