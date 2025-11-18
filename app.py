import streamlit as st
import pandas as pd
import requests

# ---------------------------------
# UI CONFIG
# ---------------------------------

st.set_page_config(
    page_title="CrowdStrike Dashboard",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ CrowdStrike – Executive Dashboard")
st.write("Ferramenta simples e intuitiva para consulta de hosts e análise de CSV.")

st.divider()

# ---------------------------------
# CARREGAR TENANTS DO SECRETS
# -----
