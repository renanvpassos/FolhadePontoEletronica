import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
from io import BytesIO
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Ponto Eletrônico", page_icon="⏱️", layout="centered")

# --- ESTILIZAÇÃO CSS CUSTOMIZADA PARA DEIXAR A INTERFACE MODERNA ---
st.markdown("""
    <style>
        /* Estilização dos blocos e containers */
        .card-ponto {
            background-color: #f8f9fa;
            padding: 25px;
            border-radius: 12px;
            border-left: 5px solid #4D96FF;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }
        .card-log {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }
        /* Ajuste do botão lateral de Sair */
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
        res = supabase.table("registro_ponto").select("nome_completo, horario_entrada, saida_almoco, retorno_almoco, horario_saida, data").eq("exibir_no_log", True).order("data", desc=True).execute()
        return res.data
        
    elif operacao == "buscar_relatorio":
        res = supabase.table("registro_ponto").select("data, horario_entrada, saida_almoco, retorno_almoco, horario_saida").eq("email", email).gte("data", str(data_filtro)).lte("data", str(data_fim)).order("data", desc=True).execute()
        return res.data

# --- EXIBIÇÃO DO LOGOTIPO DA EMPRESA ---
def exibir_logo():
    logo_url = "http://panalpina.golservices.com.br/aplicacoes/imagens/mplogo.png"
    st.markdown(
        f'<div style="text-align: left; margin-bottom: 25px;">'
        f'<img src="{logo_url}" style="max-width: 160px; height: auto;">'
        f'</div>',
        unsafe_allow_html=True
    )

# --- SISTEMA NATIVO DE LOGIN E CADASTRO ---
def gerenciar_acesso():
    if "connected" not in st.session_state:
        st.session_state["connected"] = False

    if not st.session_state["connected"]:
        exibir_logo()
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

# --- LIMPEZA AUTOMÁTICA DO LOG (1 EM 1 MÊS) ---
executar_query_supabase("limpar_log", data_filtro=hoje - timedelta(days=30))

# --- EXIBIÇÃO DO LOGOTIPO NA ÁREA LOGADA ---
exibir_logo()

# --- INTERFACE / MENU LATERAL ---
st.sidebar.markdown(f"### 👤 Usuário Ativo")
st.sidebar.write(f"Olá, **{user_name}**")
st.sidebar.caption(user_email)
st.sidebar.markdown("---")

st.sidebar.markdown("### 📋 Navegação")
opcao = st.sidebar.radio("Selecione a ação:", ["ENTRADA", "SAÍDA ALMOÇO", "RETORNO ALMOÇO", "SAÍDA", "LOG", "RELATÓRIO"], label_visibility="collapsed")

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

# --- MENU: REGISTRO DE HORÁRIOS (ENTRADA, ALMOÇOS, SAÍDA) ---
if opcao in ["ENTRADA", "SAÍDA ALMOÇO", "RETORNO ALMOÇO", "SAÍDA"]:
    st.title(f"📍 Registro de {opcao.title()}")
    
    # Grid de informações superiores (Cards de Metadados)
    c_data, c_hora = st.columns(2)
    with c_data:
        st.metric(label="🗓️ Data Oficial", value=hoje.strftime('%d/%m/%Y'))
    with c_hora:
        st.metric(label="⏱️ Horário do Servidor (Brasília)", value=agora_br.strftime('%H:%M'))
        
    st.write("")
    
    # Bloco / Container Principal de Ação
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
        
        # Centralização do Botão de Ponto
        col_btn_1, col_btn_2, col_btn_3 = st.columns([1, 2, 1])
        with col_btn_2:
            if st.button(texto_botao, use_container_width=True, type="secondary" if horario_atual_ponto else "primary"):
                st.session_state[f'confirmar_{opcao}'] = True
                
        # Container de Confirmação de Segurança
        if st.session_state.get(f'confirmar_{opcao}', False):
            st.write("")
            with st.expander("⚠️ CONFIRMAÇÃO DE SEGURANÇA", expanded=True):
                st.warning(f"Deseja gravar o horário atual (**{agora_br.strftime('%H:%M:%S')}**) na opção **{opcao}**?")
                c1, c2 = st.columns(2)
                if c1.button("Confirmar Marcação", key=f"sim_{opcao}", use_container_width=True, type="primary"):
                    dados_ponto = {
                        "email": user_email,
                        "nome_completo": user_name,
                        "data": str(hoje),
                        colunas_banco[opcao]: agora_br.isoformat()
                    }
                    executar_query_supabase("salvar_ponto", data_dict=dados_ponto)
                    st.session_state[f'confirmar_{opcao}'] = False
                    st.success(f"Horário gravado com sucesso!")
                    st.rerun()
                    
                if c2.button("Cancelar", key=f"nao_{opcao}", use_container_width=True):
                    st.session_state[f'confirmar_{opcao}'] = False
                    st.rerun()

# --- MENU: LOG (MURAL CRONOLÓGICO RENDERIZADO EM CARDS) ---
elif opcao == "LOG":
    st.title("📢 Mural de Atividades")
    st.caption("Linha do tempo das batidas eletrônicas registradas pela equipe hoje (Ordem Cronológica).")
    st.write("---")
    
    logs_banco = executar_query_supabase("buscar_logs")
    if not logs_banco:
        st.info("Nenhuma atividade registrada no mural recente.")
    else:
        lista_eventos = []
        labels_acoes = {
            "horario_entrada": "🟢 realizou ENTRADA",
            "saida_almoco": "🟡 saiu para o ALMOÇO",
            "retorno_almoco": "🟠 RETORNOU do almoço",
            "horario_saida": "🔵 realizou SAÍDA"
        }
        
        for item in logs_banco:
            nome = item["nome_completo"]
            dt_compara = datetime.strptime(item["data"], "%Y-%m-%d").strftime("%d/%m")
            
            for coluna, label in labels_acoes.items():
                valor_hora = item.get(coluna)
                if valor_hora:
                    dt_objeto = datetime.fromisoformat(valor_hora).astimezone(fuso_br)
                    lista_eventos.append({
                        "nome": nome,
                        "data_str": dt_compara,
                        "acao": label,
                        "hora_str": dt_objeto.strftime("%H:%M:%S"),
                        "objeto_tempo": dt_objeto 
                    })
        
        if not lista_eventos:
            st.info("Nenhum registro encontrado.")
        else:
            lista_eventos.sort(key=lambda x: x["objeto_tempo"], reverse=False)
            
            # Container do Mural de Atividades formatado em Listagem Limpa
            with st.container():
                for evento in lista_eventos:
                    st.markdown(
                        f'<div class="card-log">'
                        f'⏱️ <b>{evento["hora_str"]}</b> - <b>{evento["nome"]}</b> {evento["acao"]} <span style="float: right; color: gray; font-size: 0.85em;">📅 {evento["data_str"]}</span>'
                        f'</div>', 
                        unsafe_allow_html=True
                    )

# --- MENU: RELATÓRIO PESSAL FORMATADO ---
elif opcao == "RELATÓRIO":
    st.title("📊 Espelho de Ponto Pessoal")
    st.caption(f"Filtro e exportação de folhas e históricos para o colaborador: **{user_name}**")
    st.write("")
    
    # Card com filtros de busca
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("🗓️ Data Inicial", hoje - timedelta(days=7))
        with col2:
            data_fim = st.date_input("🗓️ Data Final", hoje)
        
    st.write("---")
    
    if data_inicio > data_fim:
        st.error("Erro: A data inicial não pode ser maior que a data final.")
    else:
        dados_relatorio = executar_query_supabase(
            "buscar_relatorio", 
            email=user_email, 
            data_filtro=data_inicio, 
            data_fim=data_fim
        )
        
        if not dados_relatorio:
            st.info("Você não possui registros de ponto cadastrados nesse período selecionado.")
        else:
            df = pd.DataFrame(dados_relatorio)
            df.columns = ["Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída"]
            
            def formata_hora(x):
                if not x: return "-"
                try:
                    return datetime.fromisoformat(x).astimezone(fuso_br).strftime('%H:%M:%S')
                except:
                    return "-"

            df["Data"] = df["Data"].apply(lambda x: datetime.strptime(x, "%Y-%m-%d").strftime('%d/%m/%Y'))
            df["Entrada"] = df["Entrada"].apply(formata_hora)
            df["Saída Almoço"] = df["Saída Almoço"].apply(formata_hora)
            df["Retorno Almoço"] = df["Retorno Almoço"].apply(formata_hora)
            df["Saída"] = df["Saída"].apply(formata_hora)
            
            # Tabela Estilizada Ocupando Tela Cheia
            st.dataframe(df, use_container_width=True)
            
            # --- EXPORTAÇÃO EXCEL COM BOTÃO DESTACADO ---
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Folha de Ponto')
            
            dados_excel = output.getvalue()
            
            st.write("")
            st.download_button(
                label="📥 Baixar Planilha Oficial (.xlsx)", 
                data=dados_excel, 
                file_name=f"relatorio_ponto_{user_name.replace(' ', '_')}.xlsx", 
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True
            )
