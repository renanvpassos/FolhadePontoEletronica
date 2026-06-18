import streamlit as st
import os
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
from io import BytesIO
from supabase import create_client, Client
import re
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from collections import defaultdict
import streamlit.components.v1 as components

# --- BLOQUEIO DE DISPOSITIVOS MÓVEIS ---
components.html("""
<!DOCTYPE html>
<html>
<head>
<style>
  #bloqueio-mobile {
    display: none;
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    background-color: #f0f4ff;
    z-index: 999999;
    justify-content: center;
    align-items: center;
    flex-direction: column;
    font-family: 'Segoe UI', sans-serif;
    text-align: center;
    padding: 30px;
    box-sizing: border-box;
  }
  #bloqueio-mobile .icone { font-size: 64px; margin-bottom: 16px; }
  #bloqueio-mobile h1 { color: #1E3A8A; font-size: 22px; margin-bottom: 10px; }
  #bloqueio-mobile p  { color: #4B5563; font-size: 15px; line-height: 1.6; max-width: 340px; }
</style>
</head>
<body>
<div id="bloqueio-mobile">
  <div class="icone">🚫📱</div>
  <h1>Acesso não permitido</h1>
  <p>Este sistema está disponível <strong>apenas para computadores</strong>.<br><br>
     Por favor, acesse pelo navegador de um <strong>desktop ou notebook</strong>.</p>
</div>

<script>
  function isMobile() {
    // 1. User-Agent (cobre a maioria dos casos, inclusive "modo desktop" de alguns navegadores)
    var ua = navigator.userAgent || navigator.vendor || window.opera;
    var uaMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile|tablet/i.test(ua);

    // 2. Largura real da tela física (independe do zoom ou modo desktop)
    var larguraFisica = window.screen.width;
    var telaPequena = larguraFisica < 1024;

    // 3. Suporte a toque (verdadeiro em dispositivos touch, mesmo com UA de desktop)
    var temTouch = (('ontouchstart' in window) || (navigator.maxTouchPoints > 0));

    // 4. Orientação típica de celular (portrait com tela pequena)
    var orientacaoMobile = (window.screen.height > window.screen.width) && telaPequena;

    // Bloqueia se: UA mobile OU (tela pequena E touch) OU orientação portrait pequena
    return uaMobile || (telaPequena && temTouch) || orientacaoMobile;
  }

  if (isMobile()) {
    var bloqueio = document.getElementById('bloqueio-mobile');
    bloqueio.style.display = 'flex';

    // Propaga o bloqueio para o frame pai (a página real do Streamlit)
    try {
      window.parent.document.body.style.overflow = 'hidden';
      var overlay = window.parent.document.createElement('div');
      overlay.id = 'overlay-mobile-block';
      overlay.style.cssText = [
        'position:fixed', 'top:0', 'left:0',
        'width:100vw', 'height:100vh',
        'background:#f0f4ff',
        'z-index:999999',
        'display:flex',
        'flex-direction:column',
        'justify-content:center',
        'align-items:center',
        'font-family:Segoe UI,sans-serif',
        'text-align:center',
        'padding:30px',
        'box-sizing:border-box'
      ].join(';');
      overlay.innerHTML = `
        <div style="font-size:64px;margin-bottom:16px">🚫📱</div>
        <h1 style="color:#1E3A8A;font-size:22px;margin-bottom:10px">Acesso não permitido</h1>
        <p style="color:#4B5563;font-size:15px;line-height:1.6;max-width:340px">
          Este sistema está disponível <strong>apenas para computadores</strong>.<br><br>
          Por favor, acesse pelo navegador de um <strong>desktop ou notebook</strong>.
        </p>
      `;
      // Remove overlay anterior se já existir (evita duplicatas em reruns)
      var anterior = window.parent.document.getElementById('overlay-mobile-block');
      if (anterior) anterior.remove();
      window.parent.document.body.appendChild(overlay);
    } catch(e) {
      // Fallback: se não conseguir acessar o parent (cross-origin), o bloqueio interno já cobre
    }
  }
</script>
</body>
</html>
""", height=0)

def converter_para_csv_integracao(df):
    """
    Gera o CSV de integração a partir de um DataFrame de relatório (individual ou consolidado).
    Remove automaticamente todas as colunas de Justificativa, preservando a ordem das demais colunas.
    """
    if df is None or df.empty:
        return "".encode("utf-8-sig")

    colunas_validas = [c for c in df.columns if "Justificativa" not in c]
    df_csv = df[colunas_validas].copy()

    # separador ";" e BOM (utf-8-sig) para abrir corretamente no Excel em pt-BR
    return df_csv.to_csv(index=False, sep=";").encode("utf-8-sig")

def converter_para_pdf_individual(df, nome_funcionario, email, mapeamento_celulas):
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, 
        pagesize=landscape(A4), 
        rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15
    )
    story = []
    styles = getSampleStyleSheet()
    
    # === CONFIGURAÇÃO DE FERIADOS (Adicione novas datas aqui) ===
    feriados = ["04/06/2026", "24/12/2026"]
    
    # Estilos
    title_style = ParagraphStyle('TituloPDF', parent=styles['Heading1'], fontSize=13, textColor=colors.HexColor("#1E3A8A"), spaceAfter=4)
    header_style = ParagraphStyle('HeaderPDF', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName="Helvetica-Bold", alignment=1)
    cell_style = ParagraphStyle('CeluaPDF', parent=styles['Normal'], fontSize=9.5, leading=9, fontName="Helvetica", alignment=1)
    cell_bold_style = ParagraphStyle('CelulaNegritoPDF', parent=styles['Normal'], fontSize=9.5, leading=9, fontName="Helvetica-Bold", alignment=1)
    total_style = ParagraphStyle('TotalPDF', parent=styles['Normal'], fontSize=9.5, fontName="Helvetica-Bold", textColor=colors.HexColor("#1E3A8A"), spaceBefore=2, spaceAfter=2)
    erro_style = ParagraphStyle('ErroStyle', parent=styles['Normal'], fontSize=8, textColor=colors.red, fontName="Helvetica-Bold")
    
    caminho_logo = "logoMult.png"
    logo_existe = os.path.exists(caminho_logo)
    
    def _extrair_minutos(val):
        try:
            if pd.isna(val) or str(val).strip() == "" or ":" not in str(val): return 0
            partes = str(val).strip().split(':')
            return int(partes[0]) * 60 + int(partes[1])
        except: return 0

    # === REGRA ESPECIAL: FERIADOS ===
    df = df.copy()  # Evita modificar o DataFrame original fora da função
    
    # Identifica a coluna que contém o total trabalhado
    coluna_total = None
    for col in df.columns:
        if col.lower() in ["total", "total trabalhado", "tempo trabalhado", "total horas"]:
            coluna_total = col
            break
            
    # Se a coluna de total existir, copia o valor para 'Hora Extra' nos dias de feriado
    if "Data" in df.columns and "Hora Extra" in df.columns and coluna_total:
        eh_feriado = df["Data"].astype(str).str.strip().isin(feriados)
        df.loc[eh_feriado, "Hora Extra"] = df.loc[eh_feriado, coluna_total]

    # === CÁLCULO DA JORNADA DE TRABALHO NO PERÍODO ===
    total_jornada_mins = 0
    col_entrada = next((c for c in df.columns if c.lower() == 'entrada'), None)
    col_saida = next((c for c in df.columns if c.lower() in ['saida', 'saída']), None)
    
    if coluna_total:
        total_jornada_mins = df[coluna_total].apply(_extrair_minutos).sum()
    else:
        if col_entrada and col_saida:
            for _, row in df.iterrows():
                ent = _extrair_minutos(row[col_entrada])
                sai = _extrair_minutos(row[col_saida])
                if sai > ent:
                    total_jornada_mins += (sai - ent)

    total_jornada_str = f"{total_jornada_mins // 60:02d}:{total_jornada_mins % 60:02d}"

    # === CÁLCULOS DE HORAS EXTRAS (Geral, 75% e 100%) ===
    total_mins = df["Hora Extra"].apply(_extrair_minutos).sum() if "Hora Extra" in df.columns else 0
    total_horas_str = f"{total_mins // 60:02d}:{total_mins % 60:02d}"

    mins_75 = 0
    mins_100 = 0

    if "Hora Extra" in df.columns:
        for _, row in df.iterrows():
            data_str = str(row.get("Data", "")).strip()
            dia_semana_str = str(row.get("Dia da Semana", "")).upper()
            he_mins = _extrair_minutos(row["Hora Extra"])
            
            eh_100 = (data_str in feriados) or ("SÁBADO" in dia_semana_str) or ("SABADO" in dia_semana_str) or ("DOMINGO" in dia_semana_str)
            
            if eh_100:
                mins_100 += he_mins
            else:
                mins_75 += he_mins

    horas_75_str = f"{mins_75 // 60:02d}:{mins_75 % 60:02d}"
    horas_100_str = f"{mins_100 // 60:02d}:{mins_100 % 60:02d}"

    # === CONSTRUÇÃO DO DOCUMENTO ===
    celula = mapeamento_celulas.get(email, "Não Informada")
    
    if logo_existe:
        logo_flowable = Image(caminho_logo, width=75, height=25)
        logo_flowable.hAlign = 'RIGHT'
        story.append(logo_flowable)
        story.append(Spacer(1, 8))
        
    story.append(Paragraph(f"Relatório de Ponto: <font color='red'>{nome_funcionario}</font>", title_style))
    story.append(Paragraph(f"<b>E-mail:</b> {email}", styles['Normal']))
    story.append(Paragraph(f"<b>Célula:</b> {celula}", styles['Normal']))
    story.append(Spacer(1, 4))
    
    totais_dados = [
        [
            Paragraph(f"<b>Total de Horas de Trabalho no Período:</b> <font color='green'>{total_jornada_str}</font>", total_style),
            "", 
            ""  
        ],
        [
            Paragraph(f"<b>Total de Horas Extras no Período:</b> <font color='red'>{total_horas_str}</font>", total_style),
            Paragraph(f"<b>Total de Horas Extras 75% no Período:</b> <font color='red'>{horas_75_str}</font>", total_style),
            Paragraph(f"<b>Total de Horas Extras 100% no Período:</b> <font color='red'>{horas_100_str}</font>", total_style)
        ]
    ]
    
    tabela_totais = Table(totais_dados, colWidths=[270, 270, 270])
    tabela_totais.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(tabela_totais)
    story.append(Spacer(1, 5))
    
    # === TRATAMENTO DAS COLUNAS ===
    df_pdf = df.copy()
    
    indices_feriado = []
    if "Data" in df_pdf.columns:
        indices_feriado = df_pdf[df_pdf["Data"].astype(str).str.strip().isin(feriados)].index.tolist()

    if "Data" in df_pdf.columns and "Dia da Semana" in df_pdf.columns:
      # Removemos o .split('/')[0] para manter a data inteira
      conteudo_combinado = [f"{str(row['Data'])}<br/>{row['Dia da Semana']}" for _, row in df_pdf.iterrows()]
      df_pdf.insert(0, "Data / Dia", conteudo_combinado)
      df_pdf = df_pdf.drop(columns=["Data", "Dia da Semana"])

    colunas_manter = [c for c in df_pdf.columns if "justificativa" not in c.lower()]
    df_filtrado = df_pdf[colunas_manter]
    
    idx_hora_extra = list(df_filtrado.columns).index("Hora Extra") if "Hora Extra" in df_filtrado.columns else -1
    colunas_obrigatorias = [c for c in df_filtrado.columns if 'observação' not in c.lower()]
    
    # Identifica colunas locais para validação de preenchimento na listagem
    col_entrada_fil = next((c for c in df_filtrado.columns if c.lower() == 'entrada'), None)
    col_saida_fil = next((c for c in df_filtrado.columns if c.lower() in ['saida', 'saída']), None)

    # === CRIAÇÃO DA TABELA ===
    dados_tabela = [[Paragraph(f"<b>{col}</b>", header_style) for col in df_filtrado.columns]]
    estilos_tabela = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#D1D5DB")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F9FAFB")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]
    
    for r_idx, (orig_idx, row) in enumerate(df_filtrado.iterrows(), start=1):
        texto_data = str(row.get("Data / Dia", "")).upper()
        
        eh_fds = "DOMINGO" in texto_data or "SÁBADO" in texto_data or "SABADO" in texto_data
        eh_feriado = orig_idx in indices_feriado
        
        # Verifica se Entrada e Saída estão especificamente preenchidas
        val_entrada = str(row.get(col_entrada_fil, "")).strip() if col_entrada_fil else ""
        val_saida = str(row.get(col_saida_fil, "")).strip() if col_saida_fil else ""
        horarios_preenchidos = val_entrada not in ["", "nan", "0", "0.0", "00:00"] and val_saida not in ["", "nan", "0", "0.0", "00:00"]
        
        linha_completa = all(str(row.get(col, "")).strip() not in ["", "nan", "0", "0.0"] for col in colunas_obrigatorias)
        
        # DEFINIÇÃO DE DESTAQUE DA LINHA (Pintar apenas se houver preenchimento dos horários)
        deve_destacar = (eh_feriado and horarios_preenchidos) or (eh_fds and linha_completa)
        
        if deve_destacar:
            estilos_tabela.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#FEF08A")))
        
        val_he = str(row.get("Hora Extra", "")).strip()
        if idx_hora_extra != -1 and val_he not in ["", "0", "0.0", "00:00"]:
            estilos_tabela.append(('BACKGROUND', (idx_hora_extra, r_idx), (idx_hora_extra, r_idx), colors.HexColor("#FEF08A")))

        linha = []
        for col_nome, val in row.items():
            valor_str = "" if (col_nome == "Hora Extra" and val in ["00:00", "0", "0.0", ""]) else str(val)
            # Aplica negrito apenas se a linha foi de fato destacada por atividade
            linha.append(Paragraph(valor_str, cell_bold_style if deve_destacar else cell_style))
            
        dados_tabela.append(linha)
    
    tabela = Table(dados_tabela, repeatRows=1)
    tabela.setStyle(TableStyle(estilos_tabela))
    story.append(tabela)
    
    doc.build(story)
    output.seek(0)
    return output.getvalue()
    
def converter_para_pdf_consolidado(df, mapeamento_celulas, data_inicio, data_fim):
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, 
        pagesize=landscape(A4), 
        rightMargin=15, leftMargin=15, topMargin=10, bottomMargin=10
    )
    story = []
    styles = getSampleStyleSheet()
    
    # === CONFIGURAÇÃO DE FERIADOS (Adicione novas datas aqui) ===
    feriados = ["04/06/2026", "24/12/2026"]
    
    # Estilos
    title_style = ParagraphStyle('TituloPDF', parent=styles['Heading1'], fontSize=13, textColor=colors.HexColor("#1E3A8A"), spaceAfter=4)
    header_style = ParagraphStyle('HeaderPDF', parent=styles['Normal'], fontSize=9.5, leading=12, textColor=colors.white, fontName="Helvetica-Bold", alignment=1)
    
    cell_style = ParagraphStyle('CeluaPDF', parent=styles['Normal'], fontSize=8.5, leading=11, fontName="Helvetica", alignment=1)
    cell_bold_style = ParagraphStyle('CelulaNegritoPDF', parent=styles['Normal'], fontSize=8.5, leading=11, fontName="Helvetica-Bold", alignment=1)
    
    total_style = ParagraphStyle('TotalPDF', parent=styles['Normal'], fontSize=9.5, fontName="Helvetica-Bold", textColor=colors.HexColor("#1E3A8A"), spaceBefore=2, spaceAfter=2)
    erro_style = ParagraphStyle('ErroStyle', parent=styles['Normal'], fontSize=8, textColor=colors.red, fontName="Helvetica-Bold")

    caminho_logo = "logoMult.png"
    logo_existe = os.path.exists(caminho_logo)

    def _extrair_minutos(val):
        try:
            if pd.isna(val) or str(val).strip() == "" or ":" not in str(val):
                return 0
            partes = str(val).strip().split(':')
            return int(partes[0]) * 60 + int(partes[1])
        except:
            return 0

    def _calcular_minutos_entre_horas(h1, h2):
        try:
            if pd.isna(h1) or pd.isna(h2) or not h1 or not h2:
                return 0
            t1 = sum(x * int(t) for x, t in zip([60, 1, 0], str(h1).strip().split(':')))
            t2 = sum(x * int(t) for x, t in zip([60, 1, 0], str(h2).strip().split(':')))
            return max(0, t2 - t1)
        except:
            return 0
            
    def _extrair_apenas_o_dia(val):
        if pd.isna(val) or str(val).strip() == "":
            return ""
        s = str(val).strip()
        if "/" in s:
            return s.split("/")[0]
        if "-" in s:
            return s.split("-")[-1]
        try:
            return pd.to_datetime(val).strftime('%d')
        except:
            return s
            
    df_copy = df.copy()
    
    novas_colunas = {}
    for col in df_copy.columns:
        col_clean = str(col).strip().lower()
        if col_clean in ['e-mail', 'email']:
            novas_colunas[col] = 'E-mail'
        elif col_clean in ['funcionário', 'funcionario']:
            novas_colunas[col] = 'Funcionário'
    df_copy = df_copy.rename(columns=novas_colunas)
    
    if 'Funcionário' in df_copy.columns:
        df_copy = df_copy.sort_values(by='Funcionário', key=lambda col: col.str.lower(), kind="mergesort")
        
    usuarios_emails = df_copy['E-mail'].dropna().unique() if 'E-mail' in df_copy.columns else []
    
    for i, email in enumerate(usuarios_emails):
        df_funcionario = df_copy[df_copy['E-mail'].astype(str).str.strip().str.lower() == str(email).strip().lower()].copy()
        if df_funcionario.empty:
            continue
            
        nome_funcionario = df_funcionario['Funcionário'].iloc[0] if 'Funcionário' in df_funcionario.columns else "Colaborador"
        celula = mapeamento_celulas.get(str(email).strip().lower(), "Não Informada")
        
        # === REGRA ESPECIAL DE FERIADOS: OVERRIDE DA HORA EXTRA ===
        coluna_total_regra = None
        for col in df_funcionario.columns:
            if col.lower().strip() in ["total", "total trabalhado", "tempo trabalhado", "total horas", "horas trabalhadas"]:
                coluna_total_regra = col
                break
        
        if "Data" in df_funcionario.columns and "Hora Extra" in df_funcionario.columns and coluna_total_regra:
            eh_feriado_regra = df_funcionario["Data"].astype(str).str.strip().isin(feriados)
            df_funcionario.loc[eh_feriado_regra, "Hora Extra"] = df_funcionario.loc[eh_feriado_regra, coluna_total_regra]

        # === CÁLCULO DA JORNADA DE TRABALHO NO PERÍODO ===
        total_mins_trab = 0
        if coluna_total_regra and df_funcionario[coluna_total_regra].apply(_extrair_minutos).sum() > 0:
            total_mins_trab = df_funcionario[coluna_total_regra].apply(_extrair_minutos).sum()
        elif "Entrada" in df_funcionario.columns and ("Saída" in df_funcionario.columns or "Saia" in df_funcionario.columns):
            col_s = "Saída" if "Saída" in df_funcionario.columns else "Saida"
            for _, r in df_funcionario.iterrows():
                total_mins_trab += _calcular_minutos_entre_horas(r.get("Entrada"), r.get(col_s))
        
        horas_trab = total_mins_trab // 60
        minutos_trab = total_mins_trab % 60
        total_horas_trab_str = f"{horas_trab:02d}:{minutos_trab:02d}"

        # === CÁLCULOS DE HORAS EXTRAS (Geral, 75% e 100%) ===
        total_mins = 0
        if "Hora Extra" in df_funcionario.columns:
            total_mins = df_funcionario["Hora Extra"].apply(_extrair_minutos).sum()
        
        horas = total_mins // 60
        minutos = total_mins % 60
        total_horas_str = f"{horas:02d}:{minutos:02d}"

        mins_75 = 0
        mins_100 = 0

        if "Hora Extra" in df_funcionario.columns:
            for _, row in df_funcionario.iterrows():
                data_str = str(row.get("Data", "")).strip()
                dia_semana_str = str(row.get("Dia da Semana", "")).upper()
                he_mins = _extrair_minutos(row["Hora Extra"])
                
                eh_100 = (data_str in feriados) or ("SÁBADO" in dia_semana_str) or ("SABADO" in dia_semana_str) or ("DOMINGO" in dia_semana_str)
                
                if eh_100:
                    mins_100 += he_mins
                else:
                    mins_75 += he_mins

        horas_75_str = f"{mins_75 // 60:02d}:{mins_75 % 60:02d}"
        horas_100_str = f"{mins_100 // 60:02d}:{mins_100 % 60:02d}"
        
        # === RENDERIZAÇÃO DO CABEÇALHO DO COLABORADOR ===
        if logo_existe:
            try:
                logo_flowable = Image(caminho_logo, width=76, height=22)
                logo_flowable.hAlign = 'RIGHT'
                story.append(logo_flowable)
                story.append(Spacer(1, 2))
            except Exception as img_err:
                story.append(Paragraph(f"[ERRO DE RENDERIZAÇÃO: {img_err}]", erro_style))
        else:
            story.append(Paragraph("[AVISO: Adicione o arquivo logoMult.png no seu GitHub]", erro_style))
            story.append(Spacer(1, 2))
        
        story.append(Paragraph(f"Relatório de Ponto: <font color='red'>{nome_funcionario}</font>", title_style))
        story.append(Paragraph(f"<b>E-mail:</b> {email} | <b>Célula:</b> {celula}", styles['Normal']))
        story.append(Spacer(1, 4))
        
        # === TABELA DE TOTAIS ALINHADA (Duas linhas perfeitamente estruturadas) ===
        totais_dados = [
            [
                Paragraph(f"<b>Total de Horas de Trabalho no Período:</b> <font color='green'>{total_horas_trab_str}</font>", total_style),
                "", 
                ""  
            ],
            [
                Paragraph(f"<b>Total de Horas Extras no Período:</b> <font color='red'>{total_horas_str}</font>", total_style),
                Paragraph(f"<b>Total de Horas Extras 75% no Período:</b> <font color='red'>{horas_75_str}</font>", total_style),
                Paragraph(f"<b>Total de Horas Extras 100% no Período:</b> <font color='red'>{horas_100_str}</font>", total_style)
            ]
        ]
        
        tabela_totais = Table(totais_dados, colWidths=[270, 270, 270])
        tabela_totais.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(tabela_totais)
        story.append(Spacer(1, 5))
        
        # === ESTRUTURAÇÃO DA TABELA DE PONTOS ===
        colunas_remover = ['funcionário', 'funcionario', 'e-mail', 'email', 'celula', 'célula']
        colunas_exibicao = [
            col for col in df_funcionario.columns 
            if col.lower().strip() not in colunas_remover and 'justificativa' not in col.lower().strip()
        ]
        
        tem_dia_semana = "Dia da Semana" in colunas_exibicao
        tem_data = "Data" in colunas_exibicao
        
        if tem_dia_semana: colunas_exibicao.remove("Dia da Semana")
        if tem_data: colunas_exibicao.remove("Data")
            
        df_tabela = df_funcionario[colunas_exibicao].fillna("").copy()
        
        if tem_dia_semana or tem_data:
          coluna_combinada = []
          for _, row in df_funcionario.iterrows():
              dia_sem = str(row.get("Dia da Semana", "")).strip() if tem_dia_semana else ""
              
              # Modificado: Pegamos a data completa em vez de usar a função que extraía apenas o dia
              data_valor = row.get("Data", "")
              data_completa = str(data_valor).strip() if tem_data and data_valor else ""
              
              if dia_sem and data_completa:
                  texto_celula = f"{data_completa}<br/>{dia_sem}"
              else:
                  texto_celula = data_completa or dia_sem
              coluna_combinada.append(texto_celula)
              
          df_tabela.insert(0, "Dia / Data", coluna_combinada)
        
        dados_tabela = []
        header_row = [Paragraph(f"<b>{col}</b>", header_style) for col in df_tabela.columns]
        dados_tabela.append(header_row)
        
        idx_hora_extra = list(df_tabela.columns).index("Hora Extra") if "Hora Extra" in df_tabela.columns else -1
        col_entrada_fil = next((c for c in df_tabela.columns if c.lower().strip() == 'entrada'), None)
        col_saida_fil = next((c for c in df_tabela.columns if c.lower().strip() in ['saida', 'saída']), None)
        
        estilos_celulas_dinamicos = []

        for r_idx, (_, row) in enumerate(df_tabela.iterrows(), start=1):
            orig_row = df_funcionario.iloc[r_idx - 1]
            dia_sem_orig = str(orig_row.get("Dia da Semana", "")).strip().lower()
            data_orig = str(orig_row.get("Data", "")).strip()
            
            is_fim_de_semana = dia_sem_orig in ["sábado", "sabado", "domingo"]
            is_feriado = data_orig in feriados

            # Nova Validação Condicional: Verifica se Entrada e Saída estão de fato registradas
            val_entrada = str(row.get(col_entrada_fil, "")).strip() if col_entrada_fil else ""
            val_saida = str(row.get(col_saida_fil, "")).strip() if col_saida_fil else ""
            horarios_preenchidos = val_entrada not in ["", "nan", "0", "0.0", "00:00"] and val_saida not in ["", "nan", "0", "0.0", "00:00"]

            # Tanto feriado quanto fim de semana só destacam a linha toda se houver batimento de ponto válido
            deve_destacar_linha = (is_feriado and horarios_preenchidos) or (is_fim_de_semana and horarios_preenchidos)

            linha = []
            for col_name in df_tabela.columns:
                val = row[col_name]
                val_str = str(val) if val is not None and not pd.isna(val) else ""
                val_str = val_str.strip()
                
                if col_name == "Hora Extra" and val_str == "00:00":
                    val_str = ""
                
                # Aplicação de Negrito Condicional com base nas regras de destaque
                if deve_destacar_linha or col_name == "Hora Extra" or (is_fim_de_semana and col_name == "Dia / Data"):
                    linha.append(Paragraph(val_str, cell_bold_style))
                else:
                    linha.append(Paragraph(val_str, cell_style))
                
            dados_tabela.append(linha)
            
            # Pintura de Fundo Condicional
            if deve_destacar_linha:
                estilos_celulas_dinamicos.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#FEF08A")))
            elif not is_fim_de_semana and idx_hora_extra != -1:
                val_hora_extra = str(row.iloc[idx_hora_extra]).strip()
                if val_hora_extra != "" and val_hora_extra != "00:00":
                    estilos_celulas_dinamicos.append(('BACKGROUND', (idx_hora_extra, r_idx), (idx_hora_extra, r_idx), colors.HexColor("#FEF08A")))
            
        tabela = Table(dados_tabela, repeatRows=1)
        tabela.hAlign = 'CENTER'
        
        estilos_base = [
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D5DB")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F9FAFB")]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 3.0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3.0),
        ]
        
        estilos_base.extend(estilos_celulas_dinamicos)
        tabela.setStyle(TableStyle(estilos_base))
        story.append(tabela)
        
        if i < len(usuarios_emails) - 1:
            story.append(PageBreak())
            
    doc.build(story)
    output.seek(0)
    return output.getvalue()
    
# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Ponto Eletrônico", page_icon="⏱️", layout="centered")

# --- ESTILIZAÇÃO CSS CUSTOMIZADA ---
st.markdown("""
    <style>
        .card-log {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }
        .stButton>button {
            border-radius: 8px;
        }
    </style>
""", unsafe_allow_html=True)

# --- DEFINIÇÃO DO FUSO HORÁRIO DE BRASÍLIA ---
fuso_br = ZoneInfo("America/Sao_Paulo")

def obter_agora_br():
    """Retorna o datetime atual com o fuso horário de Brasília."""
    return datetime.now(fuso_br)

def obter_hoje_br():
    """Retorna a data atual com base no fuso horário de Brasília."""
    return obter_agora_br().date()

# --- CONEXÃO COM O SUPABASE ---
url: str = st.secrets["supabase"]["url"]
key: str = st.secrets["supabase"]["key"]
supabase: Client = create_client(url, key)

# --- FUNÇÃO PARA CRIPTOGRAFAR SENHAS ---
def criptografar_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# --- FUNÇÕES DO BANCO DE DADOS (SUPABASE) ---
def executar_query_supabase(operacao, data_dict=None, email=None, data_filtro=None, data_fim=None):
    if operacao == "buscar_hoje":
        res = supabase.table("registro_ponto").select("horario_entrada, saida_almoco, retorno_almoco, horario_saida").eq("email", email).eq("data", data_filtro).execute()
        return res.data
        
    elif operacao == "salvar_ponto":
        supabase.table("registro_ponto").upsert(data_dict, on_conflict="email,data").execute()
        
    elif operacao == "limpar_log":
        supabase.table("registro_ponto").update({"exibir_no_log": False}).lt("data", str(data_filtro)).execute()
        
    elif operacao == "buscar_logs":
        res = supabase.table("registro_ponto").select("nome_completo, horario_entrada, saida_almoco, retorno_almoco, horario_saida, data, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida, data_registro_horario_entrada, data_saida_almoco, data_retorno_almoco, data_horario_saida").eq("exibir_no_log", True).order("data", desc=True).execute()
        return res.data
        
    elif operacao == "buscar_relatorio":
        res = supabase.table("registro_ponto").select("data, horario_entrada, saida_almoco, retorno_almoco, horario_saida, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida", "observacao").eq("email", email).gte("data", str(data_filtro)).lte("data", str(data_fim)).order("data", desc=True).execute()
        return res.data

    elif operacao == "buscar_relatorio_geral":
        res = supabase.table("registro_ponto").select("nome_completo, email, data, horario_entrada, saida_almoco, retorno_almoco, horario_saida, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida").gte("data", str(data_filtro)).lte("data", str(data_fim)).order("nome_completo", desc=False).order("data", desc=True).execute()
        return res.data
    
    elif operacao == "salvar_log_interno":
        supabase.table("log_interno").insert(data_dict).execute()
        
    elif operacao == "buscar_logs_internos":
        res = supabase.table("log_interno").select("*").order("data_alteracao", desc=True).execute()
        return res.data

# --- FUNÇÕES AUXILIARES PARA GERAR EXCEL ---
def converter_para_excel_individual(df_dados):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_dados.to_excel(writer, index=False, sheet_name='Espelho de Ponto')
    return output.getvalue()

def converter_para_excel_multiaba(df_geral):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for email, group in df_geral.groupby("E-mail"):
            nome_colaborador = group["Funcionário"].iloc[0]
            nome_aba = re.sub(r'[\\/*?:\[\]]', '', nome_colaborador)[:30]
            dados_aba = group.drop(columns=["Funcionário", "E-mail"])
            dados_aba.to_excel(writer, index=False, sheet_name=nome_aba)
    return output.getvalue()

# --- SISTEMA NATIVO DE LOGIN E CADASTRO ---
def gerenciar_acesso():
    if "connected" not in st.session_state:
        st.session_state["connected"] = False

    if not st.session_state["connected"]:
        st.title("⏱️ Sistema de Ponto Eletrônico")
        st.write("Por favor, faça o acesso ou crie uma conta para registrar suas jornadas.")
        st.write("---")
        
        aba_login, aba_cadastro = st.tabs(["🔒 Acessar Sistema", "📝 Criar Cadastro"])
        
        with aba_login:
            st.subheader("Login")
            email_login = st.text_input("E-mail corporativo", key="login_email").strip().lower()
            senha_login = st.text_input("Senha", type="password", key="login_senha")
            
            if st.button("Entrar", type="primary", use_container_width=True):
                if email_login and senha_login:
                    senha_hash = criptografar_senha(senha_login)
                    res = supabase.table("usuarios_ponto").select("*").eq("email", email_login).eq("senha", senha_hash).execute()
                    
                    if res.data:
                        st.session_state["user_info"] = {
                            "email": res.data[0]["email"],
                            "name": res.data[0]["nome"]
                        }
                        st.session_state["connected"] = True
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("E-mail ou senha incorretos.")
                else:
                    st.warning("Por favor, preencha todos os campos.")
                    
        with aba_cadastro:
            st.subheader("Novo Colaborador")
            nome_cad = st.text_input("Nome Completo", key="cad_nome")
            email_cad = st.text_input("E-mail para cadastro", key="cad_email").strip().lower()
            senha_cad = st.text_input("Crie uma Senha", type="password", key="cad_senha")
            
            if st.button("Cadastrar Novo Usuário", use_container_width=True):
                if nome_cad and email_cad and senha_cad:
                    existe = supabase.table("usuarios_ponto").select("email").eq("email", email_cad).execute()
                    if existe.data:
                        st.error("Este e-mail já está cadastrado no sistema.")
                    else:
                        senha_segura = criptografar_senha(senha_cad)
                        dados_usuario = {"email": email_cad, "nome": nome_cad, "senha": senha_segura}
                        supabase.table("usuarios_ponto").insert(dados_usuario).execute()
                        st.success("Cadastro realizado! Agora faça o login na aba ao lado.")
                else:
                    st.warning("Preencha todos os campos para realizar o cadastro.")
        st.stop()

gerenciar_acesso()

# --- CONFIGURAÇÃO DE USUÁRIO LOGADO ---
user_info = st.session_state.get("user_info", {})
user_email = user_info.get("email")
user_name = user_info.get("name", "Colaborador")

hoje = obter_hoje_br() 
agora_br = obter_agora_br() 

# --- DETECÇÃO PRÉVIA DO CARGO DO USUÁRIO LOGADO ---
cargo_usuario = "Colaborador"
celula_usuario = None
try:
    dados_usuario_logado = supabase.table("usuarios_ponto").select("cargo, celula").eq("email", user_email).execute()
    if dados_usuario_logado.data:
        cargo_usuario = dados_usuario_logado.data[0].get("cargo", "Colaborador")
        celula_usuario = dados_usuario_logado.data[0].get("celula")
except Exception:
    pass

# --- INTERFACE / MENU LATERAL ---
st.sidebar.markdown(f"### 👤 Usuário Ativo")
st.sidebar.write(f"Olá, **{user_name}**")
st.sidebar.caption(user_email)
st.sidebar.markdown("---")

st.sidebar.markdown("### 📋 Navegação")

# Definição dinâmica das opções com base nas permissões do cargo Master
opcoes_menu = ["ENTRADA", "SAÍDA ALMOÇO", "RETORNO ALMOÇO", "SAÍDA", "LOG", "RELATÓRIO"]
if cargo_usuario == "Master":
    opcoes_menu.insert(opcoes_menu.index("LOG") + 1, "LOG INTERNO")

opcao = st.sidebar.radio("Selecione a ação:", opcoes_menu, label_visibility="collapsed")

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sair / Desconectar", use_container_width=True, type="secondary"):
    st.session_state.clear()
    st.rerun()

# --- BUSCA HISTÓRICO DE HOJE ---
dados_hoje = executar_query_supabase("buscar_hoje", email=user_email, data_filtro=hoje)

pontos = {
    "ENTRADA": dados_hoje[0]["horario_entrada"] if dados_hoje else None,
    "SAÍDA ALMOÇO": dados_hoje[0]["saida_almoco"] if dados_hoje else None,
    "RETORNO ALMOÇO": dados_hoje[0]["retorno_almoco"] if dados_hoje else None,
    "SAÍDA": dados_hoje[0]["horario_saida"] if dados_hoje else None
}

colunas_banco = {
    "ENTRADA": "horario_entrada",
    "SAÍDA ALMOÇO": "saida_almoco",
    "RETORNO ALMOÇO": "retorno_almoco",
    "SAÍDA": "horario_saida"
}

for k, v in pontos.items():
    if v and isinstance(v, str):
        pontos[k] = datetime.fromisoformat(v).astimezone(fuso_br)

# =====================================================================
# --- MENU: REGISTRO DE HORÁRIOS ---
# =====================================================================
if opcao in ["ENTRADA", "SAÍDA ALMOÇO", "RETORNO ALMOÇO", "SAÍDA"]:
    st.title(f"📍 Registro de {opcao.title()}")
    
    c_data, c_hora = st.columns(2)
    with c_data:
        st.metric(label="🗓️ Data Atual", value=hoje.strftime('%d/%m/%Y'))
    with c_hora:
        st.metric(label="⏱️ Horário atual", value=agora_br.strftime('%H:%M'))
        
    st.write("")
    
    with st.container():
        st.markdown('<div class="card-ponto">', unsafe_allow_html=True)
        horario_atual_ponto = pontos[opcao]
        
        if horario_atual_ponto:
            st.success(f"✅ Seu ponto de **{opcao}** de hoje já está registrado: **{horario_atual_ponto.strftime('%H:%M:%S')}**")
            texto_botao = f"🔄 Alterar Horário de {opcao.title()}"
        else:
            st.info(f"ℹ️ Você ainda não marcou sua **{opcao.title()}** para o dia de hoje.")
            texto_botao = f"🔴 Registrar {opcao.title()}"
            
        st.markdown('</div>', unsafe_allow_html=True)
        
        col_btn_1, col_btn_2, col_btn_3 = st.columns([1, 2, 1])
        with col_btn_2:
            if st.button(texto_botao, use_container_width=True, type="secondary" if horario_atual_ponto else "primary"):
                st.session_state[f'confirmar_{opcao}'] = True
                
        if st.session_state.get(f'confirmar_{opcao}', False):
            st.write("")
            with st.expander("⚠️ CONFIGURAÇÃO E CONFIRMAÇÃO DO PONTO", expanded=True):
                
                horario_final_gravacao = agora_br
                justificativa = None
                erro_validacao = False
                justificativa_obrigatoria = False
                
                st.markdown("##### 📝 Ajuste Manual do Registro")
                
                hora_digitada = st.text_input(
                    "Digite o horário do ponto (Formato obrigatório HH:mm):", 
                    value=agora_br.strftime('%H:%M'),
                    max_chars=5,
                    key=f"input_manual_{opcao}"
                ).strip()
                
                padrao_hora = re.compile(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$")
                
                if not padrao_hora.match(hora_digitada):
                    st.error("🛑 Formato de horário inválido! Digite um horário real entre 00:00 e 23:59 (Exemplo: 08:30).")
                    erro_validacao = True
                else:
                    hora_manual_objeto = datetime.strptime(hora_digitada, "%H:%M").time()
                    horario_final_gravacao = datetime.combine(hoje, hora_manual_objeto).replace(tzinfo=fuso_br)
                    
                    # --- VERIFICAÇÃO DE FINAL DE SEMANA OU FERIADO ---
                    # weekday() retorna 5 para sábado e 6 para domingo
                    is_fim_de_semana = hoje.weekday() in [5, 6]
                    is_feriado = hoje.strftime('%d/%m/%Y') in ["04/06/2026", "24/12/2026"]
                    dispensa_almoco = is_fim_de_semana or is_feriado
                    
                    # --- TRAVAS DE FLUXO DE PREENCHIMENTO ---
                    if opcao != "ENTRADA" and not pontos["ENTRADA"]:
                        st.error("🛑 Bloqueado: Não é permitido preencher nenhum horário antes de registrar o horário de ENTRADA.")
                        erro_validacao = True
                        
                    elif opcao == "RETORNO ALMOÇO" and not dispensa_almoco and not pontos["SAÍDA ALMOÇO"]:
                        st.error("🛑 Bloqueado: Não é permitido preencher o horário de Retorno de Almoço sem ter preenchido o horário de Saída Almoço.")
                        erro_validacao = True
                        
                    elif opcao == "SAÍDA":
                        horarios_faltantes = []
                        if not pontos["ENTRADA"]:
                            horarios_faltantes.append("**ENTRADA**")
                        
                        # Só exige almoço se NÃO for fim de semana ou feriado configurado
                        if not dispensa_almoco:
                            if not pontos["SAÍDA ALMOÇO"]:
                                horarios_faltantes.append("**SAÍDA ALMOÇO**")
                            if not pontos["RETORNO ALMOÇO"]:
                                horarios_faltantes.append("**RETORNO ALMOÇO**")
                        
                        if horarios_faltantes:
                            st.error(f"🛑 Bloqueado: Não é permitido preencher o horário de Saída sem ter preenchido todos os horários anteriores. Horários pendentes: {', '.join(horarios_faltantes)}.")
                            erro_validacao = True

                    agora_br_sem_segundos = agora_br.replace(second=0, microsecond=0)
                    
                    # --- REGRAS DE OBRIGATORIEDADE E TRAVAS ---
                    if not erro_validacao:
                        if opcao == "ENTRADA":
                            horario_com_tolerancia = horario_final_gravacao + timedelta(minutes=10)
                            if horario_com_tolerancia < agora_br_sem_segundos:
                                justificativa_obrigatoria = True
                                
                        elif opcao == "RETORNO ALMOÇO":
                            if pontos["SAÍDA ALMOÇO"]:
                                t_saida_alm = pontos["SAÍDA ALMOÇO"]
                                tempo_almoco_segundos = int((horario_final_gravacao - t_saida_alm).total_seconds())
                                limite_almoco = (1 * 3600) + (10 * 60)
                                
                                if tempo_almoco_segundos > limite_almoco:
                                    justificativa_obrigatoria = True
                                    
                        elif opcao == "SAÍDA":
                            if horario_final_gravacao > agora_br_sem_segundos:
                                st.error(f"🛑 Horário inválido! Você não pode registrar uma Saída maior do que o horário atual ({agora_br_sem_segundos.strftime('%H:%M')}).")
                                erro_validacao = True
                            
                            elif pontos["ENTRADA"]:
                                t_entrada = pontos["ENTRADA"]
                                t_saida_atual = horario_final_gravacao
                                
                                tempo_total_segundos = int((t_saida_atual - t_entrada).total_seconds())
                                limite_inferior = 9 * 3600
                                limite_superior = (9 * 3600) + (10 * 60) + 59
                                
                                if tempo_total_segundos < limite_inferior or tempo_total_segundos > limite_superior:
                                    justificativa_obrigatoria = True
                            else:
                                if horario_final_gravacao != agora_br_sem_segundos:
                                    justificativa_obrigatoria = True

                if justificativa_obrigatoria:
                    label_justificativa = "📝 Justificativa (OBRIGATÓRIA - Mínimo 3 caracteres):"
                else:
                    label_justificativa = "📝 Justificativa da marcação (Opcional):"
                    
                justificativa = st.text_area(label_justificativa, key=f"just_{opcao}").strip()
                justificativa_limpa = justificativa.strip() if justificativa else ""
                
                if opcao == "SAÍDA" and not erro_validacao:
                    if not pontos["ENTRADA"]:
                        st.error("⚠️ Não é possível calcular a jornada porque a **ENTRADA** de hoje não foi registrada.")
                        msg_confirmacao = f"Deseja gravar a Saída mesmo sem o point de Entrada?"
                    else:
                        t_entrada = pontos["ENTRADA"]
                        t_saida_atual = horario_final_gravacao
                        
                        segundos_trabalhados = int((t_saida_atual - t_entrada).total_seconds())
                        if segundos_trabalhados < 0:
                            segundos_trabalhados = 0
                            
                        horas_trab = segundos_trabalhados // 3600
                        minutos_trab = (segundos_trabalhados % 3600) // 60
                        
                        jornada_padrao_segundos = 9 * 3600 
                        
                        msg_extra = "Não houve hora extra."
                        if segundos_trabalhados > jornada_padrao_segundos:
                            segundos_extras = segundos_trabalhados - jornada_padrao_segundos
                            horas_ext = segundos_extras // 3600
                            minutos_ext = (segundos_extras % 3600) // 60
                            msg_extra = f"🔥 **{horas_ext:02d}h {minutos_ext:02d}min** de hora extra."
                            
                        st.info(f"📊 **Resumo da Jornada Calculada (Entrada ➔ Saída):**\n\n"
                                f"⏱️ Tempo Líquido Trabalhado: **{horas_trab:02d}h {minutos_trab:02d}min**\n\n"
                                f"🚀 Banco de Horas: {msg_extra}")
                                
                        msg_confirmacao = f"Confirmar gravação do horário de Saída como **{horario_final_gravacao.strftime('%H:%M:%S')}**?"
                else:
                    msg_confirmacao = f"Deseja gravar o horário **{horario_final_gravacao.strftime('%H:%M:%S')}** na opção **{opcao}**?"
                
                if not erro_validacao:
                    st.warning(msg_confirmacao)
                
                c1, c2 = st.columns(2)
                bloquear_confirmacao = erro_validacao
                atende_tamanho_minimo = len(justificativa_limpa) >= 3
                
                if justificativa_obrigatoria and not atende_tamanho_minimo:
                    bloquear_confirmacao = True
                    if not justificativa_limpa:
                        st.error("🛑 Atenção: A justificativa é obrigatória para este horário.")
                    else:
                        st.error(f"🛑 A justificativa precisa ter pelo menos 3 caracteres. (Atual: {len(justificativa_limpa)})")
                
                if c1.button("Confirmar Marcação", key=f"sim_{opcao}", use_container_width=True, type="primary", disabled=bloquear_confirmacao):
                    
                    if justificativa_obrigatoria and (not justificativa_limpa or len(justificativa_limpa) < 3):
                        st.error("🛑 Erro: Gravação impedida! Preencha a justificativa com no mínimo 3 caracteres.")
                        st.session_state[f'confirmar_{opcao}'] = True 
                    
                    elif erro_validacao:
                        st.error("🛑 Erro: Corrija as inconsistências de fluxo ou horário antes de confirmar.")
                        
                    else:
                        mapeamento_registro_sistema = {
                            "ENTRADA": "data_registro_horario_entrada",
                            "SAÍDA ALMOÇO": "data_saida_almoco",
                            "RETORNO ALMOÇO": "data_retorno_almoco",
                            "SAÍDA": "data_horario_saida"
                        }

                        dados_ponto = {
                            "email": user_email,
                            "nome_completo": user_name,
                            "data": str(hoje),
                            colunas_banco[opcao]: horario_final_gravacao.isoformat(),
                            mapeamento_registro_sistema[opcao]: agora_br.isoformat()
                        }
                        
                        if opcao == "ENTRADA":
                            momento_alerta = horario_final_gravacao + timedelta(hours=8, minutes=45)
                            dados_ponto["horario_alerta"] = momento_alerta.isoformat()
                            dados_ponto["alerta_enviado"] = False
                        
                        if justificativa_limpa:
                            if opcao == "ENTRADA":
                                dados_ponto["justificativa_entrada"] = justificativa_limpa
                            elif opcao == "SAÍDA ALMOÇO":
                                dados_ponto["justificativa_saida_almoco"] = justificativa_limpa
                            elif opcao == "RETORNO ALMOÇO":
                                dados_ponto["justificativa_retorno_almoco"] = justificativa_limpa
                            elif opcao == "SAÍDA":
                                dados_ponto["justificativa_saida"] = justificativa_limpa
                        
                        executar_query_supabase("salvar_ponto", data_dict=dados_ponto)
                        st.session_state[f'confirmar_{opcao}'] = False
                        st.success(f"Horário gravado com sucesso!")
                        st.rerun()
                        
                if c2.button("Cancelar", key=f"nao_{opcao}", use_container_width=True):
                    st.session_state[f'confirmar_{opcao}'] = False
                    st.rerun()

# =====================================================================
# --- MENU: LOG ---
# =====================================================================
elif opcao == "LOG":
    st.title("📢 Mural de Atividades")
    st.caption("Linha do tempo das batidas eletrônicas registradas pela equipe hoje (Ordem Cronológica).")
    st.write("---")
    
    logs_banco = executar_query_supabase("buscar_logs")
    if not logs_banco:
        st.info("Nenhuma atividade registrada no mural recente.")
    else:
        hoje = datetime.now(fuso_br)
        hoje_ano = hoje.year
        hoje_mes = hoje.month
        hoje_dia = hoje.day
        
        lista_eventos = []
        labels_acoes = {
            "horario_entrada": "Entrou",
            "saida_almoco": "saiu para o almoço",
            "retorno_almoco": "retornou do almoço",
            "horario_saida": "Saiu"
        }

        cores_background = {
            "Entrou": "rgba(40, 167, 69, 0.15)",
            "saiu para o almoço": "rgba(255, 193, 7, 0.15)",
            "retornou do almoço": "rgba(0, 123, 255, 0.15)",
            "Saiu": "rgba(238, 99, 99, 0.15)"
        }

        mapeamento_colunas_registro = {
            "horario_entrada": "data_registro_horario_entrada",
            "saida_almoco": "data_saida_almoco",
            "retorno_almoco": "data_retorno_almoco",
            "horario_saida": "data_horario_saida"
        }
        
        for item in logs_banco:
            nome = item["nome_completo"]
            
            for coluna, label in labels_acoes.items():
                valor_hora = item.get(coluna)
                if valor_hora:
                    dt_objeto = datetime.fromisoformat(valor_hora).astimezone(fuso_br)
                    
                    if not (dt_objeto.year == hoje_ano and dt_objeto.month == hoje_mes and dt_objeto.day == hoje_dia):
                        continue
                    
                    dt_compara = dt_objeto.strftime("%d/%m")
                    just_texto = None
                    if coluna == "horario_entrada" and item.get("justificativa_entrada"):
                        just_texto = item["justificativa_entrada"]
                    elif coluna == "saida_almoco" and item.get("justificativa_saida_almoco"):
                        just_texto = item["justificativa_saida_almoco"]
                    elif coluna == "retorno_almoco" and item.get("justificativa_retorno_almoco"):
                        just_texto = item["justificativa_retorno_almoco"]
                    elif coluna == "horario_saida" and item.get("justificativa_saida"):
                        just_texto = item["justificativa_saida"]
                    
                    coluna_registro = mapeamento_colunas_registro.get(coluna)
                    data_registro_banco = item.get(coluna_registro)
                    
                    if data_registro_banco and str(data_registro_banco).strip() != "":
                        dt_sistema = datetime.fromisoformat(str(data_registro_banco)).astimezone(fuso_br)
                        hora_sistema_gravada = dt_sistema.strftime("%H:%M:%S")
                    else:
                        hora_sistema_gravada = "--:--:--"
                    
                    lista_eventos.append({
                        "nome": nome,
                        "data_str": dt_compara,
                        "acao": label,
                        "hora_str": dt_objeto.strftime("%H:%M:%S"),
                        "objeto_tempo": dt_objeto,
                        "justificativa": just_texto,
                        "hora_sistema_salva": hora_sistema_gravada  
                    })
        
        if not lista_eventos:
            st.info("Nenhum registro encontrado para o dia de hoje.")
        else:
            lista_eventos.sort(key=lambda x: x["objeto_tempo"], reverse=False)
            
            with st.container(height=450):
                for evento in lista_eventos:
                    hora_sistema = evento["hora_sistema_salva"]
                    cor_fundo = cores_background.get(evento["acao"], "transparent")
                    
                    html_justificativa = ""
                    if evento.get("justificativa"):
                        html_justificativa = (
                            f'<br><span style="color: #6c757d; font-size: 0.9em; font-style: italic; '
                            f'padding-left: 28px; display: inline-block; margin-top: 4px;">'
                            f'💬 Justificativa: {evento["justificativa"]}'
                            f'</span>'
                        )
                    
                    html_log = (
                        f'<div class="card-log" style="position: relative; margin-bottom: 10px; '
                        f'background-color: {cor_fundo}; padding: 10px; border-radius: 6px;">'
                        f'<span style="float: right; color: gray; font-size: 0.85em; text-align: right; line-height: 1.2;">'
                        f'📅 {evento["data_str"]}<br>{hora_sistema}'
                        f'</span>'
                        f'⏱️ <b>{evento["hora_str"]}</b> - <b>{evento["nome"]}</b> {evento["acao"]}'
                        f'{html_justificativa}'
                        f'</div>'
                    )
                    
                    st.markdown(html_log, unsafe_allow_html=True)
            
            st.components.v1.html(
                """
                <script>
                    setTimeout(function() {
                        var containers = window.parent.document.querySelectorAll('[data-testid="stDocstring"] + div, [data-testid="stVerticalBlockBorderWrapper"]');
                        containers.forEach(function(el) {
                            if (el.scrollHeight > el.clientHeight) {
                                el.scrollTop = el.scrollHeight;
                            }
                        });
                    }, 300);
                </script>
                """,
                height=0
            )

# =====================================================================
# --- MENU: LOG INTERNO (EXCLUSIVO MASTER) ---
# =====================================================================
elif opcao == "LOG INTERNO":
    if cargo_usuario != "Master":
        st.error("Acesso negado. Apenas usuários com nível Master possuem acesso a esta tela.")
        st.stop()
        
    st.title("🔒 Log Interno de Auditoria")
    st.caption("Monitoramento detalhado de alterações e correções feitas manualmente nos registros de ponto.")
    st.write("---")
    
    logs_internos = executar_query_supabase("buscar_logs_internos")
    
    if not logs_internos:
        st.info("Nenhuma alteração manual registrada até o momento.")
    else:
        with st.container(height=500):
            for log in logs_internos:
                dt_alteracao = datetime.fromisoformat(log["data_alteracao"]).astimezone(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
                
                html_log_interno = (
                    f'<div class="card-log" style="border-left: 4px solid #cc0000; background-color: #000000; padding: 12px; margin-bottom: 8px; border-radius: 4px;">'
                    f'<span style="float: right; color: #64748b; font-size: 0.85em;">📅 {dt_alteracao}</span>'
                    f'🛠️ <span style="color:#ffffff;"><b>Gestor:</b> {log["quem_alterou"]}</span><br>'
                    f'👤 <span style="color:#ffffff;"><b>Alvo:</b> {log["usuario_afetado"]} (<span>{log["email_afetado"]}</span>)</span><br>'
                    f'<b style="color: #0043e1;">Operação:</b> <span style="color: #0f172a; font-family: monospace; background: #e2e8f0; padding: 2px 6px; border-radius: 4px;">{log["descricao"]}</span>'
                    f'</div>'
                )
                st.markdown(html_log_interno, unsafe_allow_html=True)

# --- MENU: RELATÓRIO ---
elif opcao == "RELATÓRIO":
    st.title("📊 Espelho de Ponto Pessoal")
    email_busca = user_email
    nome_busca = user_name
    
    mapeamento_celulas = {}
    try:
        busca_mapeamento = supabase.table("usuarios_ponto").select("email, celula").execute()
        if busca_mapeamento.data:
            # Correção: força minúsculo e remove espaços nas pontas dos e-mails mapeados
            mapeamento_celulas = {str(u['email']).strip().lower(): u.get('celula') for u in busca_mapeamento.data}
    except Exception:
        st.warning("Não foi possível carregar o mapeamento completo de células.")

    lista_todos_usuarios = []
    
    if cargo_usuario == "Master":
        st.markdown("### 🔑 Painel de Gestão (Master)")
        try:
            usuarios_banco = supabase.table("usuarios_ponto").select("email, nome, celula").execute()
            if usuarios_banco.data:
                lista_todos_usuarios = sorted(usuarios_banco.data, key=lambda x: x.get("nome", "").lower())
                opcoes_usuarios = {f"{u['nome']} ({u['email']}) - Célula: {u.get('celula') or 'Sem célula'}": u for u in lista_todos_usuarios}
    
                usuario_selecionado_str = st.selectbox("Selecione o colaborador que deseja consultar na tela:", options=list(opcoes_usuarios.keys()))
                colaborador_escolhido = opcoes_usuarios[usuario_selecionado_str]
                email_busca = colaborador_escolhido["email"]
                nome_busca = colaborador_escolhido["nome"]
                celula_busca = colaborador_escolhido.get("celula")
    
                celula_atual = celula_busca or ""
                nova_celula = st.text_input(
                    "📍 Célula do Colaborador (Banco de Dados):",
                    value=celula_atual,
                    key=f"celula_input_{email_busca}"  # garante que o campo reseta ao trocar de colaborador
                )
    
                houve_alteracao = nova_celula != celula_atual
    
                if st.button("✅ Confirmar alteração", disabled=not houve_alteracao):
                    try:
                        supabase.table("usuarios_ponto").update({"celula": nova_celula}).eq("email", email_busca).execute()
                        st.success(f"Célula de {nome_busca} atualizada com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar célula: {e}")
                elif houve_alteracao:
                    st.info("Alteração pendente — clique em **Confirmar alteração** para salvar.")
        except Exception:
            st.error("Erro ao carregar a lista completa de funcionários.")
    
    elif cargo_usuario == "Supervisor":
        st.markdown("### 🔑 Painel de Gestão (Supervisor)")
        if celula_usuario:
            st.info(f"📍 Sua Célula atual: **{celula_usuario}**")
        if not celula_usuario:
            st.warning("Você é Supervisor, mas não está vinculado a nenhuma célula no banco de dados.")
        else:
            try:
                usuarios_banco = supabase.table("usuarios_ponto").select("email, nome, celula").eq("celula", celula_usuario).execute()
                if usuarios_banco.data:
                    lista_todos_usuarios = sorted(usuarios_banco.data, key=lambda x: x.get("nome", "").lower())
                    opcoes_usuarios = {f"{u['nome']} ({u['email']})": u for u in lista_todos_usuarios}
                    
                    usuario_selecionado_str = st.selectbox("Selecione o colaborador que deseja consultar na tela:", options=list(opcoes_usuarios.keys()))
                    colaborador_escolhido = opcoes_usuarios[usuario_selecionado_str]
                    email_busca = colaborador_escolhido["email"]
                    nome_busca = colaborador_escolhido["nome"]
            except Exception:
                st.error("Erro ao carregar a lista de funcionários da sua célula.")
                
    elif cargo_usuario == "Colaborador":
        if celula_usuario:
            st.info(f"📍 Sua Célula atual: **{celula_usuario}**")
                
    st.caption(f"Filtro e exportação de folhas e históricos para: **{nome_busca}**")
     
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("🗓️ Data Inicial", hoje - timedelta(days=14), format="DD/MM/YYYY")
    with col2:
        data_fim = st.date_input("🗓️ Data Final", hoje, format="DD/MM/YYYY")

    # --- NOVO BLOCO: CÁLCULO E EXIBIÇÃO DE TOTAIS EM TEMPO REAL ---
    if data_inicio <= data_fim:
        dados_pessoais_indicadores = executar_query_supabase("buscar_relatorio", email=email_busca, data_filtro=data_inicio, data_fim=data_fim)
        
        total_segundos_trabalhados = 0
        total_segundos_extras = 0
        
        # Dicionário para acumular as horas trabalhadas agrupadas por data (ex: "2026-06-16")
        segundos_por_dia = defaultdict(int)
    
        if dados_pessoais_indicadores:
            for item in dados_pessoais_indicadores:
                val_ent = item.get("horario_entrada")
                val_sai = item.get("horario_saida")
                
                if val_ent and val_sai:
                    try:
                        dt_ent = datetime.fromisoformat(val_ent).astimezone(fuso_br)
                        dt_sai = datetime.fromisoformat(val_sai).astimezone(fuso_br)
                        
                        segundos_trab = int((dt_sai - dt_ent).total_seconds())
                        
                        if segundos_trab > 0:
                            # Agrupa pelo dia da entrada
                            dia_str = dt_ent.strftime("%d-%m-%Y")
                            segundos_por_dia[dia_str] += segundos_trab
                    except:
                        pass
    
            # --- APLICAÇÃO DA REGRA DE NEGÓCIO POR DIA ---
            jornada_limite = 9 * 3600  # 9 horas em segundos
            
            # 💡 ADICIONE AQUI AS NOVAS DATAS (Formato: "AAAA-MM-DD")
            datas_especiais = {
                "04-06-2026",  # 04/06/2026
                "24-12-2026",  # 24/12/2026
                # "2026-12-25",  # Exemplo de como adicionar mais datas
            }
            
            for dia_str, segundos_totais_do_dia in segundos_por_dia.items():
                # Acumula o total bruto trabalhado no período (independente de ser extra ou não)
                total_segundos_trabalhados += segundos_totais_do_dia
                
                # Descobre o dia da semana a partir da data (0=Segunda, 5=Sábado, 6=Domingo)
                dt_dia = datetime.strptime(dia_str, "%d-%m-%Y")
                dia_da_semana = dt_dia.weekday()
                
                # REGRA SÁBADO, DOMINGO OU DATAS ESPECIAIS: Todo o tempo trabalhado vira hora extra
                if dia_da_semana in (5, 6) or dia_str in datas_especiais:
                    total_segundos_extras += segundos_totais_do_dia
                
                # REGRA DIA DE SEMANA COMUM: Apenas o que passar de 9 horas vira hora extra
                else:
                    if segundos_totais_do_dia > jornada_limite:
                        total_segundos_extras += (segundos_totais_do_dia - jornada_limite)
    
        # Conversão dos totais acumulados para minutos
        def_total_minutos_trabalhados = total_segundos_trabalhados // 60
        def_total_minutos_extras = total_segundos_extras // 60
    
        # Formatação das strings de exibição
        horas_trab_totais = f"{def_total_minutos_trabalhados // 60:02d}h {def_total_minutos_trabalhados % 60:02d}m"
        horas_ext_totais = f"{def_total_minutos_extras // 60:02d}h {def_total_minutos_extras % 60:02d}m"
    
        st.write("")
        col_tot1, col_tot2 = st.columns(2)
        with col_tot1:
            st.metric(label="⏱️ Total de Horas Trabalhadas no Período", value=horas_trab_totais)
        with col_tot2:
            st.metric(label="🚀 Total de Horas Extras no Período", value=horas_ext_totais, 
                      delta=horas_ext_totais if def_total_minutos_extras > 0 else None, delta_color="normal")
    # --- FIM DO NOVO BLOCO ---
        
    st.write("---")
     
    if data_inicio > data_fim:
        st.error("Erro: A data inicial não pode ser maior que a data final.")
    else:
        def processar_dados_ponto(dados, dt_inicio, dt_fim, incluir_usuario_info=False, formatar_data_br=False):
            dias_semana = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
            
            ordem_individual = ["Dia da Semana", "Data", "Entrada", "Saída", "Hora Extra", "Saída Almoço", "Retorno Almoço", "Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída", "OBSERVAÇÃO"]
            ordem_consolidada = ["Funcionário", "E-mail", "Dia da Semana", "Data", "Entrada", "Saída", "Hora Extra", "Saída Almoço", "Retorno Almoço", "Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída", "OBSERVAÇÃO"]
            
            # Lista global de datas 100% dentro da função (Formato: DD/MM/AAAA)
            datas_100_porcento = ["04/06/2026", "24/12/2026"]
        
            # --- FLUXO 1: CONSOLIDADO (incluir_usuario_info = True) ---
            if incluir_usuario_info:
                if not dados:
                    return pd.DataFrame()
                dados_ordenados = sorted(dados, key=lambda x: str(x.get("data", "")))
                linhas_processadas = []
                for item in dados_ordenados:
                    linha = {}
                    linha["Funcionário"] = item.get("nome_completo", "")
                    linha["E-mail"] = item.get("email", "")
                    
                    data_banco = item.get("data", "")
                    dia_semana_str = ""
                    dt_obj = None 
                    if data_banco:
                        try:
                            if isinstance(data_banco, str):
                                dt_obj = datetime.strptime(data_banco[:10], "%Y-%m-%d")
                            elif hasattr(data_banco, "weekday"):
                                dt_obj = data_banco
                            else:
                                dt_obj = datetime.strptime(str(data_banco)[:10], "%Y-%m-%d")
                            dia_semana_str = dias_semana[dt_obj.weekday()]
                        except Exception:
                            pass
                    
                    linha["Dia da Semana"] = dia_semana_str
                    
                    if formatar_data_br and data_banco:
                        try:
                            if isinstance(data_banco, str):
                                dt_obj_for = datetime.strptime(data_banco[:10], "%Y-%m-%d")
                            elif hasattr(data_banco, "strftime"):
                                dt_obj_for = data_banco
                            else:
                                dt_obj_for = datetime.strptime(str(data_banco)[:10], "%Y-%m-%d")
                            linha["Data"] = dt_obj_for.strftime("%d/%m/%Y")
                        except Exception:
                            linha["Data"] = str(data_banco)
                    else:
                        if isinstance(data_banco, str):
                            linha["Data"] = data_banco[:10]
                        elif hasattr(data_banco, "strftime"):
                            linha["Data"] = data_banco.strftime("%Y-%m-%d")
                        else:
                            linha["Data"] = str(data_banco)[:10] if data_banco else ""
        
                    dt_entrada, dt_saida = None, None
                    for col_banco, col_df in [
                        ("horario_entrada", "Entrada"),
                        ("saida_almoco", "Saída Almoço"),
                        ("retorno_almoco", "Retorno Almoço"),
                        ("horario_saida", "Saída")
                    ]:
                        valor = item.get(col_banco)
                        if valor:
                            try:
                                dt_objeto = datetime.fromisoformat(valor).astimezone(fuso_br)
                                linha[col_df] = dt_objeto.strftime("%H:%M:%S")
                                if col_banco == "horario_entrada":
                                    dt_entrada = dt_objeto
                                elif col_banco == "horario_saida":
                                    dt_saida = dt_objeto
                            except Exception:
                                linha[col_df] = ""
                        else:
                            linha[col_df] = ""
        
                    hora_extra_str = "00:00"
                    if dt_entrada and dt_saida and dt_obj:
                        segundos_trabalhados = int((dt_saida - dt_entrada).total_seconds())
                        dia_da_semana_numero = dt_obj.weekday()
                        data_atual_str = dt_obj.strftime("%d/%m/%Y")
                        
                        if dia_da_semana_numero in [5, 6] or data_atual_str in datas_100_porcento:
                            segundos_extras = segundos_trabalhados
                        else:
                            jornada_limite_segundos = 9 * 3600
                            segundos_extras = max(0, segundos_trabalhados - jornada_limite_segundos)
                        
                        if segundos_extras > 0:
                            horas_ext = segundos_extras // 3600
                            minutos_ext = (segundos_extras % 3600) // 60
                            hora_extra_str = f"{horas_ext:02d}:{minutos_ext:02d}"
                    
                    linha["Hora Extra"] = hora_extra_str
                    linha["Justificativa Entrada"] = item.get("justificativa_entrada", "") or ""
                    linha["Justificativa Saída Almoço"] = item.get("justificativa_saida_almoco", "") or ""
                    linha["Justificativa Retorno Almoço"] = item.get("justificativa_retorno_almoco", "") or ""
                    linha["Justificativa Saída"] = item.get("justificativa_saida", "") or ""
                    linha["OBSERVAÇÃO"] = item.get("observacao", "") or ""
                    linhas_processadas.append(linha)
                
                df_res = pd.DataFrame(linhas_processadas)
                return df_res[[c for c in ordem_consolidada if c in df_res.columns]]
        
            # --- FLUXO 2: INDIVIDUAL / TELA (incluir_usuario_info = False) ---
            lista_datas = []
            curr_date = dt_inicio
            while curr_date <= dt_fim:
                lista_datas.append(curr_date)
                curr_date += timedelta(days=1)
        
            dados_por_data = {}
            if dados:
                for item in dados:
                    dt_banco = item.get("data")
                    if dt_banco:
                        if isinstance(dt_banco, str):
                            dt_key = dt_banco[:10]
                        elif hasattr(dt_banco, "strftime"):
                            dt_key = dt_banco.strftime("%Y-%m-%d")
                        else:
                            dt_key = str(dt_banco)[:10]
                        dados_por_data[dt_key] = item
        
            linhas_processadas = []
            for dt in lista_datas: 
                data_iso = dt.strftime("%Y-%m-%d")
                data_atual_str = dt.strftime("%d/%m/%Y") # Formato para cruzar com datas_100_porcento
                item = dados_por_data.get(data_iso, {})
        
                linha = {}
                dia_da_semana_numero = dt.weekday()
                linha["Dia da Semana"] = dias_semana[dia_da_semana_numero]
                
                if formatar_data_br:
                    linha["Data"] = data_atual_str
                else:
                    linha["Data"] = data_iso
        
                dt_entrada, dt_saida = None, None
                for col_banco, col_df in [
                    ("horario_entrada", "Entrada"),
                    ("saida_almoco", "Saída Almoço"),
                    ("retorno_almoco", "Retorno Almoço"),
                    ("horario_saida", "Saída")
                ]:
                    valor = item.get(col_banco)
                    if valor:
                        try:
                            dt_objeto = datetime.fromisoformat(valor).astimezone(fuso_br)
                            linha[col_df] = dt_objeto.strftime("%H:%M:%S")
                            if col_banco == "horario_entrada":
                                dt_entrada = dt_objeto
                            elif col_banco == "horario_saida":
                                dt_saida = dt_objeto
                        except Exception:
                            linha[col_df] = ""
                    else:
                        linha[col_df] = ""
        
                hora_extra_str = "00:00"
                if dt_entrada and dt_saida:
                    segundos_trabalhados = int((dt_saida - dt_entrada).total_seconds())
                    
                    # CORREÇÃO AQUI: Adicionado a validação de data especial para a visualização individual da tela
                    if dia_da_semana_numero in [5, 6] or data_atual_str in datas_100_porcento:
                        segundos_extras = segundos_trabalhados
                    else:
                        jornada_limite_segundos = 9 * 3600
                        segundos_extras = max(0, segundos_trabalhados - jornada_limite_segundos)
                    
                    if segundos_extras > 0:
                        horas_ext = segundos_extras // 3600
                        minutos_ext = (segundos_extras % 3600) // 60
                        hora_extra_str = f"{horas_ext:02d}:{minutos_ext:02d}"
                
                linha["Hora Extra"] = hora_extra_str
                linha["Justificativa Entrada"] = item.get("justificativa_entrada", "") or ""
                linha["Justificativa Saída Almoço"] = item.get("justificativa_saida_almoco", "") or ""
                linha["Justificativa Retorno Almoço"] = item.get("justificativa_retorno_almoco", "") or ""
                linha["Justificativa Saída"] = item.get("justificativa_saida", "") or ""
                linha["OBSERVAÇÃO"] = item.get("observacao", "") or ""
                linhas_processadas.append(linha)
        
            df_res = pd.DataFrame(linhas_processadas)
            return df_res[[c for c in ordem_individual if c in df_res.columns]]
            
            lista_datas = []
            curr_date = dt_inicio
            while curr_date <= dt_fim:
                lista_datas.append(curr_date)
                curr_date += timedelta(days=1)
        
            dados_por_data = {}
            if dados:
                for item in dados:
                    dt_banco = item.get("data")
                    if dt_banco:
                        if isinstance(dt_banco, str):
                            dt_key = dt_banco[:10]
                        elif hasattr(dt_banco, "strftime"):
                            dt_key = dt_banco.strftime("%Y-%m-%d")
                        else:
                            dt_key = str(dt_banco)[:10]
                        dados_por_data[dt_key] = item
        
            linhas_processadas = []
            for dt in lista_datas:
                data_iso = dt.strftime("%Y-%m-%d")
                item = dados_por_data.get(data_iso, {})
        
                linha = {}
                linha["Dia da Semana"] = dias_semana[dt.weekday()]
                
                if formatar_data_br:
                    linha["Data"] = dt.strftime("%d/%m/%Y")
                else:
                    linha["Data"] = data_iso
        
                dt_entrada, dt_saida = None, None
                for col_banco, col_df in [
                    ("horario_entrada", "Entrada"),
                    ("saida_almoco", "Saída Almoço"),
                    ("retorno_almoco", "Retorno Almoço"),
                    ("horario_saida", "Saída")
                ]:
                    valor = item.get(col_banco)
                    if valor:
                        try:
                            dt_objeto = datetime.fromisoformat(valor).astimezone(fuso_br)
                            linha[col_df] = dt_objeto.strftime("%H:%M:%S")
                            if col_banco == "horario_entrada":
                                dt_entrada = dt_objeto
                            elif col_banco == "horario_saida":
                                dt_saida = dt_objeto
                        except Exception:
                            linha[col_df] = ""
                    else:
                        linha[col_df] = ""
        
                hora_extra_str = "00:00"
                if dt_entrada and dt_saida:
                    segundos_trabalhados = int((dt_saida - dt_entrada).total_seconds())
                    jornada_limite_segundos = 9 * 3600
                    if segundos_trabalhados > jornada_limite_segundos:
                        segundos_extras = segundos_trabalhados - jornada_limite_segundos
                        horas_ext = segundos_extras // 3600
                        minutos_ext = (segundos_extras % 3600) // 60
                        hora_extra_str = f"{horas_ext:02d}:{minutos_ext:02d}"
                
                linha["Hora Extra"] = hora_extra_str
                
                # 2. Capturando a observação do banco de dados no fluxo individual
                
                linha["Justificativa Entrada"] = item.get("justificativa_entrada", "") or ""
                linha["Justificativa Saída Almoço"] = item.get("justificativa_saida_almoco", "") or ""
                linha["Justificativa Retorno Almoço"] = item.get("justificativa_retorno_almoco", "") or ""
                linha["Justificativa Saída"] = item.get("justificativa_saida", "") or ""
                linha["OBSERVAÇÃO"] = item.get("observacao", "") or ""
                linhas_processadas.append(linha)
        
            df_res = pd.DataFrame(linhas_processadas)
            return df_res[[c for c in ordem_individual if c in df_res.columns]]
        
        dados_pessoais = executar_query_supabase("buscar_relatorio", email=email_busca, data_filtro=data_inicio, data_fim=data_fim)
        df_visualizacao = processar_dados_ponto(dados_pessoais, data_inicio, data_fim, incluir_usuario_info=False, formatar_data_br=True)
        
        st.markdown(f"##### 📑 Histórico de Registros ({data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')})")
        
        # 1. Adicionado 'OBSERVAÇÃO' após 'Retorno Almoço' na visualização da tela
        ordem_colunas_tela = ["Dia da Semana", "Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", "Hora Extra", "Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída", "OBSERVAÇÃO"]
        
        if cargo_usuario in ["Supervisor", "Master"]:
            st.warning("⚠️ **Atenção:** Confirme as alterações antes de salvar.")
            
            df_editado = st.data_editor(
                df_visualizacao, 
                use_container_width=True, 
                hide_index=True,
                disabled=["Dia da Semana", "Data", "Hora Extra"],  
                column_order=ordem_colunas_tela,
                column_config={
                    "Dia da Semana": st.column_config.TextColumn("Dia da Semana"),
                    "Data": st.column_config.TextColumn("Data"),
                    "Entrada": st.column_config.TextColumn("Entrada"),
                    "Saída Almoço": st.column_config.TextColumn("Saída Almoço"),
                    "Retorno Almoço": st.column_config.TextColumn("Retorno Almoço"),
                    "Saída": st.column_config.TextColumn("Saída"),
                    "OBSERVAÇÃO": st.column_config.TextColumn("OBSERVAÇÃO")
                },
                key="editor_ponto_gestao"
            )
            
            col_btn, col_csv_integ = st.columns(2)
            with col_btn:
                caixa_confirmacao = st.popover("💾 Salvar Alterações no Banco", use_container_width=True)
                caixa_confirmacao.warning(f"⚠️ Atenção: Isso alterará permanentemente os dados de {nome_busca}.")
                confirmou_salvar = caixa_confirmacao.button("Sim, confirmar e salvar", type="primary", use_container_width=True)

            with col_csv_integ:
                gerar_csv_integracao = st.button("🗳️ Gerar CSV Integração", use_container_width=True)

            if gerar_csv_integracao:
                with st.spinner("Gerando CSV(s) de integração..."):
                    # --- CSV INDIVIDUAL (colaborador atualmente selecionado na tela) ---
                    df_csv_ind = processar_dados_ponto(dados_pessoais, data_inicio, data_fim, incluir_usuario_info=False, formatar_data_br=True)
                    st.session_state.csv_integ_individual = converter_para_csv_integracao(df_csv_ind)
                    st.session_state.csv_integ_individual_nome = f"CSV_Integracao_{nome_busca.replace(' ', '_')}_{data_inicio}_a_{data_fim}.csv"

                    # --- CSV CONSOLIDADO (Supervisor -> própria célula | Master -> todos os colaboradores) ---
                    todos_usuarios_csv = []
                    inicio_pag, passo_pag = 0, 1000
                    while True:
                        try:
                            pagina = supabase.table("usuarios_ponto").select("email, nome, celula").range(inicio_pag, inicio_pag + passo_pag - 1).execute()
                            if not pagina.data:
                                break
                            todos_usuarios_csv.extend(pagina.data)
                            if len(pagina.data) < passo_pag:
                                break
                            inicio_pag += passo_pag
                        except Exception as e:
                            st.error(f"Erro ao buscar colaboradores para o CSV consolidado: {e}")
                            break

                    if cargo_usuario == "Supervisor":
                        target_celula_csv = str(celula_usuario).strip().lower()
                        usuarios_alvo_csv = [u for u in todos_usuarios_csv if str(u.get("celula", "")).strip().lower() == target_celula_csv]
                        nome_arquivo_consolidado = f"CSV_Integracao_Consolidado_Celula_{celula_usuario.replace(' ', '_')}_{data_inicio}_a_{data_fim}.csv"
                    else:
                        usuarios_alvo_csv = todos_usuarios_csv
                        nome_arquivo_consolidado = f"CSV_Integracao_Consolidado_Todos_Colaboradores_{data_inicio}_a_{data_fim}.csv"

                    str_inicio_csv = data_inicio.strftime("%Y-%m-%d") if hasattr(data_inicio, "strftime") else str(data_inicio)
                    str_fim_csv = data_fim.strftime("%Y-%m-%d") if hasattr(data_fim, "strftime") else str(data_fim)

                    dfs_equipe_csv = []
                    for u in usuarios_alvo_csv:
                        u_email_csv = str(u["email"]).strip().lower()
                        u_nome_csv = str(u.get("nome", "Sem Nome")).strip()

                        dados_user_csv = []
                        try:
                            resposta_csv = supabase.table("registro_ponto").select("*").eq("email", u_email_csv).execute()
                            if resposta_csv.data:
                                for r in resposta_csv.data:
                                    data_crua_csv = str(r.get("data") or r.get("data_registro") or "")
                                    data_linha_csv = data_crua_csv[:10]
                                    if str_inicio_csv <= data_linha_csv <= str_fim_csv:
                                        dados_user_csv.append(r)
                        except Exception as db_err:
                            st.error(f"Erro ao buscar dados no banco para {u_nome_csv} ({u_email_csv}): {db_err}")
                            continue

                        df_user_csv = processar_dados_ponto(dados_user_csv, data_inicio, data_fim, incluir_usuario_info=False, formatar_data_br=True)
                        if df_user_csv is not None and not df_user_csv.empty:
                            df_user_csv.insert(0, "E-mail", u_email_csv)
                            df_user_csv.insert(0, "Funcionário", u_nome_csv)
                            dfs_equipe_csv.append(df_user_csv)

                    if dfs_equipe_csv:
                        df_consolidado_csv = pd.concat(dfs_equipe_csv, ignore_index=True)
                        df_consolidado_csv = df_consolidado_csv.sort_values(by="Funcionário", key=lambda col: col.str.lower(), kind="mergesort")
                        st.session_state.csv_integ_consolidado = converter_para_csv_integracao(df_consolidado_csv)
                    else:
                        st.session_state.csv_integ_consolidado = None

                    st.session_state.csv_integ_consolidado_nome = nome_arquivo_consolidado
                    st.session_state.csv_integracao_pronto = True

            if st.session_state.get("csv_integracao_pronto"):
                st.success("✅ CSV(s) de integração gerados com sucesso!")
                col_csv_d1, col_csv_d2 = st.columns(2)
                with col_csv_d1:
                    st.download_button(
                        label="📥 Baixar CSV Individual",
                        data=st.session_state.csv_integ_individual,
                        file_name=st.session_state.csv_integ_individual_nome,
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_csv_d2:
                    if st.session_state.csv_integ_consolidado is not None:
                        st.download_button(
                            label="📥 Baixar CSV Consolidado",
                            data=st.session_state.csv_integ_consolidado,
                            file_name=st.session_state.csv_integ_consolidado_nome,
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.info("Nenhum dado consolidado encontrado para o período selecionado.")
            
            if confirmou_salvar:
                alteracoes = st.session_state.get("editor_ponto_gestao", {}).get("edited_rows", {})
                
                if not alteracoes:
                    st.info("Nenhuma alteração foi detectada para ser salva.")
                else:
                    sucessos = 0
                    erros = 0
                    
                    # 3. Mapeando a coluna para a tabela do Supabase ('observacao')
                    mapeamento_colunas_db = {
                        "Entrada": "horario_entrada",
                        "Justificativa Entrada": "justificativa_entrada",
                        "Saída Almoço": "saida_almoco",
                        "Justificativa Saída Almoço": "justificativa_saida_almoco",
                        "Retorno Almoço": "retorno_almoco",
                        "Justificativa Retorno Almoço": "justificativa_retorno_almoco",
                        "Saída": "horario_saida",
                        "Justificativa Saída": "justificativa_saida",
                        "OBSERVAÇÃO": "observacao"
                    }
                    
                    datas_com_registro = {item.get("data") for item in dados_pessoais if item.get("data")}
                    
                    for idx_linha_str, colunas_alteradas in alteracoes.items():
                        idx_linha = int(idx_linha_str)
                        
                        try:
                            data_br = df_visualizacao.iloc[idx_linha]["Data"]
                            data_str = datetime.strptime(data_br, "%d/%m/%Y").strftime("%Y-%m-%d")
                        except Exception:
                            st.error(f"Erro ao sincronizar índice da linha {idx_linha + 1} com o banco de dados.")
                            erros += 1
                            continue
                            
                        update_dict = {}
                        logs_internos_para_salvar = []
                        
                        for col_df, novo_valor in colunas_alteradas.items():
                            col_banco = mapeamento_colunas_db.get(col_df)
                            if not col_banco:
                                continue
                            
                            valor_antigo = df_visualizacao.iloc[idx_linha].get(col_df, "")
                            if pd.isna(valor_antigo) or valor_antigo is None:
                                valor_antigo = "--:--:--" if col_banco in ["horario_entrada", "saida_almoco", "retorno_almoco", "horario_saida"] else ""
                            
                            if col_banco in ["horario_entrada", "saida_almoco", "retorno_almoco", "horario_saida"]:
                                if novo_valor is None:
                                    update_dict[col_banco] = None
                                    descricao_log = f'Limpou o campo "{col_df}" do dia {data_br} (Valor antigo era {valor_antigo})'
                                    logs_internos_para_salvar.append(descricao_log)
                                    continue
                                    
                                hora_nova = str(novo_valor).strip()
                                
                                if hora_nova == "" or hora_nova.lower() == "none":
                                    update_dict[col_banco] = None
                                    descricao_log = f'Limpou o campo "{col_df}" do dia {data_br} (Valor antigo era {valor_antigo})'
                                    logs_internos_para_salvar.append(descricao_log)
                                    continue
                                
                                padrao_hhmmss = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$")
                                
                                if not padrao_hhmmss.match(hora_nova):
                                    st.error(f"❌ Erro na linha {idx_linha + 1}, coluna '{col_df}': O valor '{hora_nova}' é inválido. Use estritamente o formato HH:MM:SS (Ex: 12:30:00).")
                                    erros += 1
                                    continue
                                
                                try:
                                    partes_hora = hora_nova.split(":")
                                    h, m, s = int(partes_hora[0]), int(partes_hora[1]), int(partes_hora[2])
                                    
                                    partes_data = data_str.split("-")
                                    ano, mes, dia = int(partes_data[0]), int(partes_data[1]), int(partes_data[2][:2])
                                    
                                    dt_combinado = datetime(ano, mes, dia, h, m, s)
                                    dt_fuso = dt_combinado.replace(tzinfo=fuso_br)
                                    update_dict[col_banco] = dt_fuso.isoformat()
                                    
                                    descricao_log = f'Alterou a informação "{col_df}" do dia {data_br} de: {valor_antigo} para {hora_nova}.'
                                    logs_internos_para_salvar.append(descricao_log)
                                    
                                except Exception as e:
                                    st.error(f"❌ Erro na linha {idx_linha + 1}, coluna '{col_df}': {str(e)}")
                                    erros += 1
                            else:
                                update_dict[col_banco] = novo_valor
                                descricao_log = f'Alterou a "{col_df}" do dia {data_br} de: "{valor_antigo}" para "{novo_valor}".'
                                logs_internos_para_salvar.append(descricao_log)
                        
                        if update_dict and erros == 0:
                            try:
                                if data_str in datas_com_registro:
                                    supabase.table("registro_ponto").update(update_dict).eq("email", email_busca).eq("data", data_str).execute()
                                else:
                                    insert_dict = {
                                        "email": email_busca,
                                        "data": data_str,
                                        "nome_completo": nome_busca
                                    }
                                    insert_dict.update(update_dict)
                                    supabase.table("registro_ponto").insert(insert_dict).execute()
                                
                                for desc_ativ in logs_internos_para_salvar:
                                    dados_log_auditoria = {
                                        "quem_alterou": user_name,
                                        "usuario_afetado": nome_busca,
                                        "email_afetado": email_busca,
                                        "descricao": desc_ativ
                                    }
                                    executar_query_supabase("salvar_log_interno", data_dict=dados_log_auditoria)
                                    
                                sucessos += 1
                            except Exception as e:
                                st.error(f"Erro ao salvar alteração de {nome_busca} (Linha {idx_linha + 1}): {e}")
                                erros += 1
                    
                    if sucessos > 0 and erros == 0:
                        st.success(f"✅ Sucesso! Foram atualizadas as alterações de {sucessos} linha(s) para {nome_busca}.")
                        st.rerun()
        else:
            # 4. Caso o usuário NÃO seja Supervisor/Master, renderiza apenas um DataFrame comum (Sem opção de edição)
            st.dataframe(df_visualizacao, use_container_width=True, hide_index=True, column_order=ordem_colunas_tela)
        
        # --- PROCESSAMENTO E EXPORTAÇÃO INDIVIDUAL ---
        df_exportar_ind = processar_dados_ponto(dados_pessoais, data_inicio, data_fim, incluir_usuario_info=False, formatar_data_br=True)
        dados_excel_ind = converter_para_excel_individual(df_exportar_ind)
        dados_pdf_ind = converter_para_pdf_individual(df_exportar_ind, nome_busca, email_busca, mapeamento_celulas)
        
        col_down_ind1, col_down_ind2 = st.columns(2)
        
        with col_down_ind1:
            st.download_button(
                label="📥 Baixar Espelho de Ponto (Excel)",
                data=dados_excel_ind,
                file_name=f"Espelho_Ponto_{nome_busca.replace(' ', '_')}_{data_inicio}_a_{data_fim}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        with col_down_ind2:
            st.download_button(
                label="📄 Baixar Espelho de Ponto (PDF)",
                data=dados_pdf_ind,
                file_name=f"Espelho_Ponto_{nome_busca.replace(' ', '_')}_{data_inicio}_a_{data_fim}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        # --- SEÇÃO DE EXPORTAÇÃO CONSOLIDADA POR CARGOS GESTORES ---
        if cargo_usuario in ["Supervisor", "Master"]:
            st.write("---")
            st.markdown("### 🗂️ Exportação Geral da Equipe (Consolidada)")
            
            opcao_consolidada = "Minha Célula"
            celulas_disponiveis = []
            
            # 1. BUSCA PAGINADA DE USUÁRIOS (Evita que a própria lista de funcionários corte em 1000)
            todos_usuarios_banco = []
            inicio_user = 0
            passo_user = 1000
            
            while True:
                try:
                    busca_page = supabase.table("usuarios_ponto").select("email, nome, celula").range(inicio_user, inicio_user + passo_user - 1).execute()
                    if not busca_page.data:
                        break
                    todos_usuarios_banco.extend(busca_page.data)
                    if len(busca_page.data) < passo_user:
                        break
                    inicio_user += passo_user
                except Exception as e:
                    st.error(f"Erro ao validar lista de colaboradores no banco de dados: {e}")
                    break
                
            mapeamento_celulas_db = {
                str(u["email"]).strip().lower(): str(u.get("celula", "")).strip()
                for u in todos_usuarios_banco if u.get("email")
            }
                
            if cargo_usuario == "Master":
                st.caption("Escolha qual célula extrair ou se deseja consolidar todas as células.")
                if todos_usuarios_banco:
                    celulas_disponiveis = sorted(list(set([str(u["celula"]).strip() for u in todos_usuarios_banco if u.get("celula")])))
                
                opcoes_master = ["Todos os Colaboradores"] + celulas_disponiveis
                opcao_consolidada = st.selectbox("Selecione abaixo a célula desejada:", options=opcoes_master)
            else:
                st.caption(f"Gera o arquivo contendo os espelhos de ponto consolidados de sua célula ativa: **{celula_usuario}**")
        
            if "dados_excel_consolidado" not in st.session_state:
                st.session_state.dados_excel_consolidado = None
            if "dados_pdf_consolidado" not in st.session_state:
                st.session_state.dados_pdf_consolidado = None
            if "nome_arquivo_base" not in st.session_state:
                st.session_state.nome_arquivo_base = ""
            if "processamento_concluido" not in st.session_state:
                st.session_state.processamento_concluido = False
        
            if st.button("📊 Processar e Gerar Relatório Consolidado", use_container_width=True, type="primary"):
                with st.spinner("Processando dados e compilando relatórios da equipe..."):
                    
                    # Filtragem inicial de quais usuários devem ser processados nesta rodada
                    if cargo_usuario == "Supervisor":
                        target_celula = str(celula_usuario).strip().lower()
                        usuarios_alvo = [u for u in todos_usuarios_banco if str(u.get("celula", "")).strip().lower() == target_celula]
                        prefixo_nome = f"Relatorio_Consolidado_Celula_{celula_usuario.replace(' ', '_')}"
                    else:  
                        if opcao_consolidada == "Todos os Colaboradores":
                            usuarios_alvo = todos_usuarios_banco
                            target_celula = "todos"
                            prefixo_nome = "Relatorio_Consolidado_Todos_Colaboradores"
                        else:
                            target_celula = str(opcao_consolidada).strip().lower()
                            usuarios_alvo = [u for u in todos_usuarios_banco if str(u.get("celula", "")).strip().lower() == target_celula]
                            prefixo_nome = f"Relatorio_Consolidado_Celula_{opcao_consolidada.replace(' ', '_')}"
        
                    dfs_equipe = []
                    
                    # 2. SEGREDO DO DRIBLE: Buscamos os pontos individualmente por funcionário (Igual à tela individual)
                    for u in usuarios_alvo:
                        u_email = str(u["email"]).strip().lower()
                        u_nome = str(u.get("nome", "Sem Nome")).strip()
                        
                        dados_pessoais_user = []
                        try:
                            resposta_direta = supabase.table("registro_ponto").select("*").eq("email", u_email).execute()
                            
                            if resposta_direta.data:
                                # 1. Padroniza as datas do Streamlit para string (YYYY-MM-DD)
                                str_inicio = data_inicio.strftime("%Y-%m-%d") if hasattr(data_inicio, "strftime") else str(data_inicio)
                                str_fim = data_fim.strftime("%Y-%m-%d") if hasattr(data_fim, "strftime") else str(data_fim)
                                
                                # 2. Filtra comparando strings de forma segura
                                for r in resposta_direta.data:
                                    # Captura o campo de data e garante que pegamos apenas os 10 primeiros caracteres (YYYY-MM-DD)
                                    data_crua = str(r.get("data") or r.get("data_registro") or "")
                                    data_linha = data_crua[:10] 
                                    
                                    if str_inicio <= data_linha <= str_fim:
                                        dados_pessoais_user.append(r)
                                        
                        except Exception as db_err:
                            st.error(f"Erro ao buscar dados no banco para {u_nome} ({u_email}): {db_err}")
                            continue
        
                        # Roda a mesma esteira de tratamento do relatório individual
                        df_user_limpo = processar_dados_ponto(dados_pessoais_user, data_inicio, data_fim, incluir_usuario_info=False, formatar_data_br=True)
                        
                        if df_user_limpo is not None and not df_user_limpo.empty:
                            # Injeta as colunas de controle essenciais para a montagem e ordenação do PDF estruturado
                            df_user_limpo["Funcionário"] = u_nome
                            df_user_limpo["E-mail"] = u_email
                            dfs_equipe.append(df_user_limpo)
                    
                    if not dfs_equipe:
                        st.warning("Nenhum dado de ponto localizado para os critérios e período selecionados.")
                        st.session_state.processamento_concluido = False
                    else:
                        df_filtrado = pd.concat(dfs_equipe, ignore_index=True)
                        
                        # Ordenação alfabética final garantida antes de ir para os arquivos
                        df_filtrado = df_filtrado.sort_values(by="Funcionário", key=lambda col: col.str.lower(), kind="mergesort")
                        
                        st.session_state.dados_excel_consolidado = converter_para_excel_multiaba(df_filtrado)
                        st.session_state.dados_pdf_consolidado = converter_para_pdf_consolidado(df_filtrado, mapeamento_celulas_db, data_inicio, data_fim)
                        st.session_state.nome_arquivo_base = prefixo_nome
                        st.session_state.processamento_concluido = True
        
            if st.session_state.processamento_concluido:
                st.success("✅ Relatórios consolidados gerados com sucesso! Escolha o formato para baixar:")
                
                col_down1, col_down2 = st.columns(2)
                with col_down1:
                    st.download_button(
                        label="📥 Baixar em Excel (.xlsx)",
                        data=st.session_state.dados_excel_consolidado,
                        file_name=f"{st.session_state.nome_arquivo_base}_{data_inicio}_a_{data_fim}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                with col_down2:
                    st.download_button(
                        label="📄 Baixar em PDF (.pdf)",
                        data=st.session_state.dados_pdf_consolidado,
                        file_name=f"{st.session_state.nome_arquivo_base}_{data_inicio}_a_{data_fim}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
