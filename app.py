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

def converter_para_pdf_individual(df, nome_funcionario, email, mapeamento_celulas):
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, 
        pagesize=landscape(A4), 
        rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15
    )
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TituloPDF', parent=styles['Heading1'], fontSize=14, textColor=colors.HexColor("#1E3A8A"), spaceAfter=10)
    header_style = ParagraphStyle('HeaderPDF', parent=styles['Normal'], fontSize=6.5, textColor=colors.white, fontName="Helvetica-Bold")
    cell_style = ParagraphStyle('CeluaPDF', parent=styles['Normal'], fontSize=9, fontName="Helvetica")
    total_style = ParagraphStyle('TotalPDF', parent=styles['Normal'], fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#1E3A8A"), spaceBefore=5, spaceAfter=5)
    erro_style = ParagraphStyle('ErroStyle', parent=styles['Normal'], fontSize=8, textColor=colors.red, fontName="Helvetica-Bold")
    
    caminho_logo = "logoMult.png"
    logo_existe = os.path.exists(caminho_logo)
    
    def _extrair_minutos(val):
        try:
            if pd.isna(val) or str(val).strip() == "" or ":" not in str(val):
                return 0
            partes = str(val).strip().split(':')
            h, m = int(partes[0]), int(partes[1])
            return h * 60 + m
        except:
            return 0

    def _calcular_minutos_entre_horas(h1, h2):
        try:
            if pd.isna(h1) or pd.isna(h2) or not h1 or not h2:
                return 0
            # Converte HH:MM:SS ou HH:MM para minutos totais desde o início do dia
            t1 = sum(x * int(t) for x, t in zip([60, 1, 0], str(h1).strip().split(':')))
            t2 = sum(x * int(t) for x, t in zip([60, 1, 0], str(h2).strip().split(':')))
            return max(0, t2 - t1)
        except:
            return 0
            
    # === CÁLCULO DE HORAS EXTRAS ===
    total_mins = 0
    if "Hora Extra" in df.columns:
        total_mins = df["Hora Extra"].apply(_extrair_minutos).sum()
    
    horas = total_mins // 60
    minutos = total_mins % 60
    total_horas_str = f"{horas:02d}:{minutos:02d}"

    # === CÁLCULO DE HORAS TRABALHADAS (Com Fallback de Segurança) ===
    total_mins_trab = 0
    # 1ª Tentativa: Pela coluna direta
    if "Horas Trabalhadas" in df.columns and df["Horas Trabalhadas"].apply(_extrair_minutos).sum() > 0:
        total_mins_trab = df["Horas Trabalhadas"].apply(_extrair_minutos).sum()
    # 2ª Tentativa (Fallback): Se a coluna falhar, calcula direto da Entrada -> Saída por linha
    elif "Entrada" in df.columns and "Saída" in df.columns:
        for _, r in df.iterrows():
            total_mins_trab += _calcular_minutos_entre_horas(r.get("Entrada"), r.get("Saída"))
    
    horas_trab = total_mins_trab // 60
    minutos_trab = total_mins_trab % 60
    total_horas_trab_str = f"{horas_trab:02d}:{minutos_trab:02d}"
    
    celula = mapeamento_celulas.get(email, "Não Informada")
    
    if logo_existe:
        try:
            logo_flowable = Image(caminho_logo, width=75, height=25)
            logo_flowable.hAlign = 'RIGHT'
            story.append(logo_flowable)
            story.append(Spacer(1, 8))
        except Exception as img_err:
            story.append(Paragraph(f"[ERRO DE RENDERIZAÇÃO: {img_err}]", erro_style))
    else:
        story.append(Paragraph("[AVISO: Adicione o arquivo logoMult.png no seu GitHub]", erro_style))
        story.append(Spacer(1, 8))
        
    story.append(Paragraph(f"Relatório de Ponto: <font color='red'>{nome_funcionario}</font>", title_style))
    story.append(Paragraph(f"<b>E-mail:</b> {email}", styles['Normal']))
    story.append(Paragraph(f"<b>Célula:</b> {celula}", styles['Normal']))
    
    story.append(Paragraph(f"<b>Total de Horas Extras no Período:</b> <font color='red'>{total_horas_str}</font>", total_style))
    story.append(Paragraph(f"<b>Total de Horas Trabalhadas no Período:</b> <font color='green'>{total_horas_trab_str}</font>", total_style))
    story.append(Spacer(1, 5))
    
    dados_tabela = []
    header_row = [Paragraph(f"<b>{col}</b>", header_style) for col in df.columns]
    dados_tabela.append(header_row)
    
    for _, row in df.iterrows():
        linha = [Paragraph(str(val) if val is not None and not pd.isna(val) else "", cell_style) for val in row]
        dados_tabela.append(linha)
        
    tabela = Table(dados_tabela, repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D5DB")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F9FAFB")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    story.append(tabela)
    
    doc.build(story)
    output.seek(0)
    return output.getvalue()
    
def converter_para_pdf_consolidado(df, mapeamento_celulas, data_inicio, data_fim):
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, 
        pagesize=landscape(A4), 
        rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20
    )
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TituloPDF', parent=styles['Heading1'], fontSize=14, textColor=colors.HexColor("#1E3A8A"), spaceAfter=10)
    header_style = ParagraphStyle('HeaderPDF', parent=styles['Normal'], fontSize=6.5, textColor=colors.white, fontName="Helvetica-Bold")
    cell_style = ParagraphStyle('CeluaPDF', parent=styles['Normal'], fontSize=9, fontName="Helvetica")
    total_style = ParagraphStyle('TotalPDF', parent=styles['Normal'], fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#1E3A8A"), spaceBefore=5, spaceAfter=5)
    erro_style = ParagraphStyle('ErroStyle', parent=styles['Normal'], fontSize=8, textColor=colors.red, fontName="Helvetica-Bold")

    caminho_logo = "logoMult.png"
    logo_existe = os.path.exists(caminho_logo)

    def _extrair_minutos(val):
        try:
            if pd.isna(val) or str(val).strip() == "" or ":" not in str(val):
                return 0
            partes = str(val).strip().split(':')
            h, m = int(partes[0]), int(partes[1])
            return h * 60 + m
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
            
    df_copy = df.copy()
    coluna_data = 'Data'  
    
    if coluna_data in df_copy.columns and not df_copy[coluna_data].empty:
        amostra = str(df_copy[coluna_data].dropna().iloc[0])
        if "/" in amostra:
            df_copy['Data_Datetime'] = pd.to_datetime(df_copy[coluna_data], format='%d/%m/%Y', errors='coerce').dt.normalize()
        else:
            df_copy['Data_Datetime'] = pd.to_datetime(df_copy[coluna_data], errors='coerce').dt.normalize()
    
    min_data = pd.to_datetime(data_inicio).floor('D')
    max_data = pd.to_datetime(data_fim).floor('D')
    periodo_completo = pd.date_range(start=min_data, end=max_data, freq='D')

    # Normalização de segurança para o mapeamento interno
    mapeamento_normalizado = {str(k).strip().lower(): v for k, v in mapeamento_celulas.items()}

    usuarios = df['E-mail'].unique() if 'E-mail' in df.columns else []
    
    for i, email in enumerate(usuarios):
        # Filtro tolerante a variações de caixa alta/baixa
        df_funcionario = df_copy[df_copy['E-mail'].astype(str).str.strip().str.lower() == str(email).strip().lower()]
        if df_funcionario.empty:
            continue
            
        nome_funcionario = df_funcionario['Funcionário'].iloc[0]
        celula = mapeamento_normalizado.get(str(email).strip().lower(), "Não Informada")
        
        # === CÁLCULO DE HORAS EXTRAS ===
        total_mins = 0
        if "Hora Extra" in df_funcionario.columns:
            total_mins = df_funcionario["Hora Extra"].apply(_extrair_minutos).sum()
        
        horas = total_mins // 60
        minutos = total_mins % 60
        total_horas_str = f"{horas:02d}:{minutos:02d}"

        # === CÁLCULO DE HORAS TRABALHADAS (Com Fallback de Segurança) ===
        total_mins_trab = 0
        if "Horas Trabalhadas" in df_funcionario.columns and df_funcionario["Horas Trabalhadas"].apply(_extrair_minutos).sum() > 0:
            total_mins_trab = df_funcionario["Horas Trabalhadas"].apply(_extrair_minutos).sum()
        elif "Entrada" in df_funcionario.columns and "Saída" in df_funcionario.columns:
            for _, r in df_funcionario.iterrows():
                total_mins_trab += _calcular_minutos_entre_horas(r.get("Entrada"), r.get("Saída"))
        
        horas_trab = total_mins_trab // 60
        minutos_trab = total_mins_trab % 60
        total_horas_trab_str = f"{horas_trab:02d}:{minutos_trab:02d}"
        
        if logo_existe:
            try:
                logo_flowable = Image(caminho_logo, width=75, height=25)
                logo_flowable.hAlign = 'RIGHT'
                story.append(logo_flowable)
                story.append(Spacer(1, 8))
            except Exception as img_err:
                story.append(Paragraph(f"[ERRO DE RENDERIZAÇÃO: {img_err}]", erro_style))
        else:
            story.append(Paragraph("[AVISO: Adicione o arquivo logoMult.png no seu GitHub]", erro_style))
            story.append(Spacer(1, 8))
        
        story.append(Paragraph(f"Relatório de Ponto: <font color='red'>{nome_funcionario}</font>", title_style))
        story.append(Paragraph(f"<b>Período:</b> {min_data.strftime('%d/%m/%Y')} até {max_data.strftime('%d/%m/%Y')}", styles['Normal']))
        story.append(Paragraph(f"<b>E-mail:</b> {email}", styles['Normal']))
        story.append(Paragraph(f"<b>Célula:</b> {celula}", styles['Normal']))
        story.append(Paragraph(f"<b>Total de Horas Extras no Período:</b> <font color='red'>{total_horas_str}</font>", total_style))
        story.append(Paragraph(f"<b>Total de Horas Trabalhadas no Período:</b> <font color='green'>{total_horas_trab_str}</font>", total_style))
        story.append(Spacer(1, 5))
        
        df_base_periodo = pd.DataFrame({'Data_Datetime': periodo_completo})
        df_funcionario_completo = pd.merge(df_base_periodo, df_funcionario, on='Data_Datetime', how='left')
        
        df_funcionario_completo[coluna_data] = df_funcionario_completo['Data_Datetime'].dt.strftime('%d/%m/%Y')
        
        if "Dia da Semana" in df.columns:
            dias_semana_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
            df_funcionario_completo["Dia da Semana"] = df_funcionario_completo['Data_Datetime'].dt.weekday.map(
                lambda x: dias_semana_pt[int(x)] if pd.notna(x) else ""
            )
        
        colunas_exibicao = [col for col in df.columns if col not in ["Funcionário", "E-mail", "Data_Datetime"]]
        df_tabela = df_funcionario_completo[colunas_exibicao].fillna("")
        
        dados_tabela = []
        header_row = [Paragraph(f"<b>{col}</b>", header_style) for col in df_tabela.columns]
        dados_tabela.append(header_row)
        
        for _, row in df_tabela.iterrows():
            linha = [Paragraph(str(val).strip() if val != "" else "", cell_style) for val in row]
            dados_tabela.append(linha)
            
        tabela = Table(dados_tabela, repeatRows=1)
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D5DB")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F9FAFB")]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        
        story.append(tabela)
        
        if i < len(usuarios) - 1:
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
        res = supabase.table("registro_ponto").select("data, horario_entrada, saida_almoco, retorno_almoco, horario_saida, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida").eq("email", email).gte("data", str(data_filtro)).lte("data", str(data_fim)).order("data", desc=True).execute()
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
                    
                    # --- TRAVAS DE FLUXO DE PREENCHIMENTO ---
                    if opcao != "ENTRADA" and not pontos["ENTRADA"]:
                        st.error("🛑 Bloqueado: Não é permitido preencher nenhum horário antes de registrar o horário de ENTRADA.")
                        erro_validacao = True
                        
                    elif opcao == "RETORNO ALMOÇO" and not pontos["SAÍDA ALMOÇO"]:
                        st.error("🛑 Bloqueado: Não é permitido preencher o horário de Retorno de Almoço sem ter preenchido o horário de Saída Almoço.")
                        erro_validacao = True
                        
                    elif opcao == "SAÍDA":
                        horarios_faltantes = []
                        if not pontos["ENTRADA"]:
                            horarios_faltantes.append("**ENTRADA**")
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
                        msg_confirmacao = f"Deseja gravar a Saída mesmo sem o ponto de Entrada?"
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
                nova_celula = st.text_input("📍 Célula do Colaborador (Banco de Dados):", value=celula_atual)
                if nova_celula != celula_atual:
                    try:
                        supabase.table("usuarios_ponto").update({"celula": nova_celula}).eq("email", email_busca).execute()
                        st.success(f"Célula de {nome_busca} updated com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar célula: {e}")
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
        
        def_total_minutos_trabalhados = 0
        def_total_minutos_extras = 0

        if dados_pessoais_indicadores:
            for item in dados_pessoais_indicadores:
                val_ent = item.get("horario_entrada")
                val_sai = item.get("horario_saida")
                if val_ent and val_sai:
                    try:
                        st.write()
                        dt_ent = datetime.fromisoformat(val_ent).astimezone(fuso_br)
                        dt_sai = datetime.fromisoformat(val_sai).astimezone(fuso_br)
                        segundos_trab = int((dt_sai - dt_ent).total_seconds())
                        
                        if segundos_trab > 0:
                            jornada_limite = 9 * 3600  # 9 horas em segundos
                            
                            if segundos_trab > jornada_limite:
                                minutos_excedentes = (segundos_trab - jornada_limite) // 60
                                def_total_minutos_trabalhados += (jornada_limite // 60) + minutos_excedentes
                                def_total_minutos_extras += minutos_excedentes
                            else:
                                def_total_minutos_trabalhados += segundos_trab // 60
                    except:
                        pass

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
            
            ordem_individual = ["Dia da Semana", "Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", "Hora Extra", "Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída"]
            ordem_consolidada = ["Funcionário", "E-mail", "Dia da Semana", "Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", "Hora Extra", "Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída"]

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
                    if dt_entrada and dt_saida:
                        segundos_trabalhados = int((dt_saida - dt_entrada).total_seconds())
                        jornada_limite_segundos = 9 * 3600
                        if segundos_trabalhados > jornada_limite_segundos:
                            segundos_extras = segundos_trabalhados - jornada_limite_segundos
                            horas_ext = segundos_extras // 3600
                            minutos_ext = (segundos_extras % 3600) // 60
                            hora_extra_str = f"{horas_ext:02d}:{minutos_ext:02d}"
                    
                    linha["Hora Extra"] = hora_extra_str
                    linha["Justificativa Entrada"] = item.get("justificativa_entrada", "") or ""
                    linha["Justificativa Saída Almoço"] = item.get("justificativa_saida_almoco", "") or ""
                    linha["Justificativa Retorno Almoço"] = item.get("justificativa_retorno_almoco", "") or ""
                    linha["Justificativa Saída"] = item.get("justificativa_saida", "") or ""
                    linhas_processadas.append(linha)
                
                df_res = pd.DataFrame(linhas_processadas)
                return df_res[[c for c in ordem_consolidada if c in df_res.columns]]
            
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
                linha["Justificativa Entrada"] = item.get("justificativa_entrada", "") or ""
                linha["Justificativa Saída Almoço"] = item.get("justificativa_saida_almoco", "") or ""
                linha["Justificativa Retorno Almoço"] = item.get("justificativa_retorno_almoco", "") or ""
                linha["Justificativa Saída"] = item.get("justificativa_saida", "") or ""
                linhas_processadas.append(linha)

            df_res = pd.DataFrame(linhas_processadas)
            return df_res[[c for c in ordem_individual if c in df_res.columns]]
        
        dados_pessoais = executar_query_supabase("buscar_relatorio", email=email_busca, data_filtro=data_inicio, data_fim=data_fim)
        df_visualizacao = processar_dados_ponto(dados_pessoais, data_inicio, data_fim, incluir_usuario_info=False, formatar_data_br=True)
    
        st.markdown(f"##### 📑 Histórico de Registros ({data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')})")
        ordem_colunas_tela = ["Dia da Semana", "Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", "Hora Extra", "Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída"]

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
                    "Saída": st.column_config.TextColumn("Saída")
                },
                key="editor_ponto_gestao"
            )
            
            col_btn, _ = st.columns([1, 1])
            with col_btn:
                caixa_confirmacao = st.popover("💾 Salvar Alterações no Banco", use_container_width=True)
                caixa_confirmacao.warning(f"⚠️ Atenção: Isso alterará permanentemente os dados de {nome_busca}.")
                confirmou_salvar = caixa_confirmacao.button("Sim, confirmar e salvar", type="primary", use_container_width=True)
            
            if confirmou_salvar:
                alteracoes = st.session_state.get("editor_ponto_gestao", {}).get("edited_rows", {})
                
                if not alteracoes:
                    st.info("Nenhuma alteração foi detectada para ser salva.")
                else:
                    sucessos = 0
                    erros = 0
                    
                    mapeamento_colunas_db = {
                        "Entrada": "horario_entrada",
                        "Justificativa Entrada": "justificativa_entrada",
                        "Saída Almoço": "saida_almoco",
                        "Justificativa Saída Almoço": "justificativa_saida_almoco",
                        "Retorno Almoço": "retorno_almoco",
                        "Justificativa Retorno Almoço": "justificativa_retorno_almoco",
                        "Saída": "horario_saida",
                        "Justificativa Saída": "justificativa_saida"
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
                                valor_antigo = "--:--:--"
                            
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
            
            if cargo_usuario == "Master":
                st.caption("Escolha qual célula extrair ou se deseja consolidar todas as células.")
                try:
                    busca_celulas = supabase.table("usuarios_ponto").select("celula").execute()
                    if busca_celulas.data:
                        celulas_disponiveis = sorted(list(set([u["celula"] for u in busca_celulas.data if u.get("celula")])))
                except Exception:
                    pass
                
                opcoes_master = ["Todos os Colaboradores"] + celulas_disponiveis
                opcao_consolidada = st.selectbox("Selecione abaixo a célula desejada ou o relatório consolidado de todos os funcionários por ordem alfabética:", options=opcoes_master)
            else:
                st.caption(f"Gera o arquivo contendo os espelhos de ponto consolidados de sua célula activa: **{celula_usuario}**")
        
            if st.button("📊 Gerar Relatório Consolidado", use_container_width=True, type="primary"):
                dados_gerais_banco = executar_query_supabase("buscar_relatorio_geral", data_filtro=data_inicio, data_fim=data_fim)
                
                if not dados_gerais_banco:
                    st.warning("Não há nenhum registro de ponto de nenhum colaborador no período selecionado.")
                else:
                    df_geral_completo = processar_dados_ponto(dados_gerais_banco, data_inicio, data_fim, incluir_usuario_info=True, formatar_data_br=True)

                    # Correção: força minúsculo e limpa espaços ao mapear para a comparação funcionar perfeitamente
                    df_geral_completo["Celula_Filtro"] = df_geral_completo["E-mail"].astype(str).str.strip().str.lower().map(mapeamento_celulas)
        
                    if cargo_usuario == "Supervisor":
                        df_filtrado = df_geral_completo[df_geral_completo["Celula_Filtro"] == celula_usuario]
                        prefixo_nome = f"Relatorio_Consolidado_Celula_{celula_usuario}"
                    else:  
                        if opcao_consolidada == "Todos os Colaboradores":
                            df_filtrado = df_geral_completo.copy()
                            prefixo_nome = f"Relatorio_Consolidado_Todos_Colaboradores"
                        else:
                            df_filtrado = df_geral_completo[df_geral_completo["Celula_Filtro"] == opcao_consolidada]
                            prefixo_nome = f"Relatorio_Consolidado_Celula_{opcao_consolidada}"
                    
                    if "Celula_Filtro" in df_filtrado.columns:
                        df_filtrado = df_filtrado.drop(columns=["Celula_Filtro"])
        
                    if df_filtrado.empty:
                        st.warning("Nenhum dado localizado para os critérios selecionados.")
                    else:
                        if "Funcionário" in df_filtrado.columns:
                            df_filtrado = df_filtrado.sort_values(
                                by="Funcionário", 
                                key=lambda col: col.str.lower(),
                                kind="mergesort"
                            )

                        dados_excel_multiaba = converter_para_excel_multiaba(df_filtrado)
                        
                        def _extrair_minutos(val):
                            try:
                                h, m = map(int, str(val).split(':'))
                                return h * 60 + m
                            except:
                                return 0
                        
                        total_mins = df_filtrado["Hora Extra"].apply(_extrair_minutos).sum()
                        total_horas_extras_str = f"{total_mins // 60:02d}:{total_mins % 60:02d}"
                        
                        dados_pdf_gerado = converter_para_pdf_consolidado(df_filtrado, mapeamento_celulas, data_inicio, data_fim)
                        
                        st.success("✅ Relatórios gerados com sucesso! Escolha o formato para baixar:")
                        
                        col_down1, col_down2 = st.columns(2)
                        with col_down1:
                            st.download_button(
                                label="📥 Baixar em Excel (.xlsx)",
                                data=dados_excel_multiaba,
                                file_name=f"{prefixo_nome}_{data_inicio}_a_{data_fim}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                        with col_down2:
                            st.download_button(
                                label="📄 Baixar em PDF (.pdf)",
                                data=dados_pdf_gerado,
                                file_name=f"{prefixo_nome}_{data_inicio}_a_{data_fim}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
