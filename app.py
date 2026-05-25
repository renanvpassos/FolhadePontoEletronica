import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
from io import BytesIO
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Ponto Mult Processing", page_icon="⏱️", layout="centered")

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
        f'<div style="text-align: left; margin-bottom: 20px;">'
        f'<img src="{logo_url}" style="max-width: 180px; height: auto;">'
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
st.sidebar.write(f"Olá, **{user_name}**!")
st.sidebar.caption(user_email)

opcao = st.sidebar.radio("Menu de Navegação", ["ENTRADA", "SAÍDA ALMOÇO", "RETORNO ALMOÇO", "SAÍDA", "LOG", "RELATÓRIO"])

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sair / Desconectar"):
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

# Tradução para persistência correta na coluna do banco
colunas_banco = {
    "ENTRADA": "horario_entrada",
    "SAÍDA ALMOÇO": "saida_almoco",
    "RETORNO ALMOÇO": "retorno_almoco",
    "SAÍDA": "horario_saida"
}

# Converte strings de datas vindas do banco para datetime objetos com timezone
for k, v in pontos.items():
    if v and isinstance(v, str):
        pontos[k] = datetime.fromisoformat(v).astimezone(fuso_br)

# --- GERENCIAMENTO VISUAL DE MARCAÇÕES (ENTRADA, ALMOÇOS, SAÍDA) ---
if opcao in ["ENTRADA", "SAÍDA ALMOÇO", "RETORNO ALMOÇO", "SAÍDA"]:
    st.subheader(f"📍 Registrar {opcao}")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.write(f"**Data de hoje (Brasília):** {hoje.strftime('%d/%m/%Y')}")
        horario_atual_ponto = pontos[opcao]
        
        if horario_atual_ponto:
            st.info(f"Seu ponto de **{opcao}** registrado hoje é às: **{horario_atual_ponto.strftime('%H:%M:%S')}**")
            texto_botao = f"🔄 ALTERAR HORÁRIO DE {opcao}"
        else:
            texto_botao = f"🔴 REGISTRAR {opcao}"
            
        if st.button(texto_botao, use_container_width=True, type="secondary" if horario_atual_ponto else "primary"):
            st.session_state[f'confirmar_{opcao}'] = True
            
        if st.session_state.get(f'confirmar_{opcao}', False):
            st.markdown("---")
            st.warning(f"⚠️ **Confirmação:** Deseja gravar o horário atual (**{agora_br.strftime('%H:%M:%S')}**) para **{opcao}**?")
            
            c1, c2 = st.columns(2)
            if c1.button("Sim, Confirmar", key=f"sim_{opcao}", use_container_width=True):
                dados_ponto = {
                    "email": user_email,
                    "nome_completo": user_name,
                    "data": str(hoje),
                    colunas_banco[opcao]: agora_br.isoformat()
                }
                executar_query_supabase("salvar_ponto", data_dict=dados_ponto)
                st.session_state[f'confirmar_{opcao}'] = False
                st.success(f"{opcao} salvo com sucesso!")
                st.rerun()
                
            if c2.button("Cancelar", key=f"nao_{opcao}", use_container_width=True):
                st.session_state[f'confirmar_{opcao}'] = False
                st.rerun()

# --- OPÇÃO: LOG ---
elif opcao == "LOG":
    st.subheader("📢 Mural de Atividades (Tempo Real)")
    st.caption("Abaixo estão os registros recentes da equipe baseados no horário de Brasília.")
    st.markdown("---")
    
    logs = executar_query_supabase("buscar_logs")
    if not logs:
        st.info("Nenhum registro ativo no mural recente.")
    else:
        for item in logs:
            nome = item["nome_completo"]
            dt_compara = datetime.strptime(item["data"], "%Y-%m-%d").strftime("%d/%m")
            
            acoes = []
            if item["horario_entrada"]:
                ent = datetime.fromisoformat(item["horario_entrada"]).astimezone(fuso_br).strftime("%H:%M")
                acoes.append(f"🟢 Entrou às {ent}")
            if item["saida_almoco"]:
                salm = datetime.fromisoformat(item["saida_almoco"]).astimezone(fuso_br).strftime("%H:%M")
                acoes.append(f"🟡 Almoço saiu às {salm}")
            if item["retorno_almoco"]:
                ralm = datetime.fromisoformat(item["retorno_almoco"]).astimezone(fuso_br).strftime("%H:%M")
                acoes.append(f"🟠 Almoço retornou às {ralm}")
            if item["horario_saida"]:
                sai = datetime.fromisoformat(item["horario_saida"]).astimezone(fuso_br).strftime("%H:%M")
                acoes.append(f"🔵 Saiu às {sai}")
                
            if acoes:
                st.write(f"**{nome}** ({dt_compara}):")
                for acao in acoes:
                    st.write(f"└ {acao}")
                st.markdown("<div style='opacity:0.3; margin:5px 0;'>---</div>", unsafe_allow_html=True)

# --- OPÇÃO: RELATÓRIO ---
elif opcao == "RELATÓRIO":
    st.subheader(f"📊 Relatório Pessoal de Horas")
    st.caption(f"Visualizando os registros de: {user_name}")
    
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data Inicial", hoje - timedelta(days=7))
    with col2:
        data_fim = st.date_input("Data Final", hoje)
        
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
            st.info("Você não possui registros de ponto cadastrados nesse período.")
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
            
            st.dataframe(df, use_container_width=True)
            
            # --- EXPORTAÇÃO PARA EXCEL (.XLSX) ---
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Folha de Ponto')
            
            dados_excel = output.getvalue()
            
            st.download_button(
                label="📥 Baixar Meu Relatório em Excel", 
                data=dados_excel, 
                file_name=f"relatorio_ponto_{user_name.replace(' ', '_')}.xlsx", 
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
