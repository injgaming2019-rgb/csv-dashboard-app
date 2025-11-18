from datetime import datetime
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

def export_pdf_executivo(df, tenant_name):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ----------------------------
    # Capa
    # ----------------------------
    c.setFillColor(colors.HexColor("#d32f2f"))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(30, height - 50, f"Relatório Executivo - {tenant_name}")
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.black)
    c.drawString(30, height - 80, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # ----------------------------
    # KPIs
    # ----------------------------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, height - 120, "Principais Indicadores")
    c.setFont("Helvetica", 12)
    kpi_y = height - 150
    c.drawString(40, kpi_y, f"Total Hosts: {len(df)}")
    c.drawString(200, kpi_y, f"Sistemas Operacionais: {df['os_version'].nunique() if 'os_version' in df else 0}")
    c.drawString(450, kpi_y, f"Versões do Sensor: {df['agent_version'].nunique() if 'agent_version' in df else 0}")
    kpi_y -= 20
    c.drawString(40, kpi_y, f"RFM Ativo: {df['rfm_enabled'].sum() if 'rfm_enabled' in df else 0}")
    c.drawString(250, kpi_y, f"Proteção Anti-Desinstalação: {df['tamper_protection_enabled'].sum() if 'tamper_protection_enabled' in df else 0}")

    # ----------------------------
    # Gráficos
    # ----------------------------
    c.showPage()  # Nova página para gráficos

    # Gráfico 1 - Agent Version
    if "agent_version" in df:
        fig1 = px.bar(df["agent_version"].value_counts(), title="Distribuição por Versão do Sensor", color_discrete_sequence=['#d32f2f'])
        fig1_path = "temp_agent.png"
        fig1.write_image(fig1_path, width=600, height=400)
        img1 = Image.open(fig1_path)
        c.drawInlineImage(img1, 50, height - 450, width=500, height=350)

    # Gráfico 2 - OS Distribution
    if "os_version" in df:
        fig2 = px.pie(df, names="os_version", title="Distribuição por Sistema Operacional", color_discrete_sequence=px.colors.sequential.Reds)
        fig2_path = "temp_os.png"
        fig2.write_image(fig2_path, width=600, height=400)
        img2 = Image.open(fig2_path)
        c.drawInlineImage(img2, 50, height - 850, width=500, height=350)

    c.showPage()  # Nova página para tabela resumo

    # ----------------------------
    # Tabela resumo (top 20 hosts)
    # ----------------------------
    c.setFont("Helvetica-Bold", 16)
    c.drawString(30, height - 50, "Resumo Hosts (Top 20)")

    table_data = [df.columns.tolist()] + df.head(20).values.tolist()
    table = Table(table_data, colWidths=[1.5*inch]*len(df.columns))
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#d32f2f")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ])
    table.setStyle(style)

    table.wrapOn(c, width-60, height-100)
    table.drawOn(c, 30, height - 400)

    c.save()
    buffer.seek(0)
    return buffer
