import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
from io import BytesIO
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Ponto Eletrônico", page_icon="⏱️", layout="centered")

# --- DEFINIÇÃO DO FUSO HORÁRIO DE BRASÍLIA ---
fuso_br = ZoneInfo("America/Sao_Paulo")

def obter_agora_br():
    """Retorna o datetime actual com o fuso horário de Brasília."""
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
        res = supabase.table("registro_ponto").select("horario_entrada, horario_saida").eq("email", email).eq("data", data_filtro).execute()
        return res.data
        
    elif operacao == "salvar_entrada":
        supabase.table("registro_ponto").upsert(data_dict, on_conflict="email,data").execute()
        
    elif operacao == "salvar_saida":
        supabase.table("registro_ponto").update({"horario_saida": data_dict["horario_saida"]}).eq("email", email).eq("data", data_filtro).execute()
        
    elif operacao == "limpar_log":
        supabase.table("registro_ponto").update({"exibir_no_log": False}).lt("data", str(data_filtro)).execute()
        
    elif operacao == "buscar_logs":
        res = supabase.table("registro_ponto").select("nome_completo, horario_entrada, horario_saida, data").eq("exibir_no_log", True).order("data", desc=True).execute()
        return res.data
        
    elif operacao == "buscar_relatorio":
        res = supabase.table("registro_ponto").select("data, horario_entrada, horario_saida").eq("email", email).gte("data", str(data_filtro)).lte("data", str(data_fim)).order("data", desc=True).execute()
        return res.data

# --- EXIBIÇÃO DO LOGOTIPO DA EMPRESA ---
def exibir_logo():
    logo_url = "http://panalpina.golservices.com.br/aplicacoes/imagens/mplogo.png"
    col_logo, col_espaco = st.columns([1, 3])
    with col_logo:
        st.image(logo_url, use_container_width=True)

# --- SISTEMA NATIVO DE LOGIN E CADASTRO ---
def gerenciar_acesso():
    if "connected" not in st.session_state:
        st.session_state["connected"] = False

    if not st.session_state["connected"]:
        # Exibe a logo no topo da tela de login/cadastro
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

opcao = st.sidebar.radio("Menu de Navegação", ["ENTRADA", "SAÍDA", "LOG", "RELATÓRIO"])

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sair / Desconectar"):
    st.session_state.clear()
    st.rerun()

# --- BUSCA HISTÓRICO DE HOJE PARA MANIPULAR OS BOTÕES ---
dados_hoje = executar_query_supabase("buscar_hoje", email=user_email, data_filtro=hoje)
entrada_registrada = dados_hoje[0]["horario_entrada"] if dados_hoje else None
saida_registrada = dados_hoje[0]["horario_saida"] if dados_hoje else None

if entrada_registrada and isinstance(entrada_registrada, str):
    entrada_registrada = datetime.fromisoformat(entrada_registrada).astimezone(fuso_br)
if saida_registrada and isinstance(saida_registrada, str):
    saida_registrada = datetime.fromisoformat(saida_registrada).astimezone(fuso_br)

# --- OPÇÃO: ENTRADA ---
if opcao == "ENTRADA":
    st.subheader("📍 Registrar Entrada")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write(f"**Data de hoje (Brasília):** {hoje.strftime('%d/%m/%Y')}")
        if entrada_registrada:
            st.success(f"✅ Entrada registrada hoje às: **{entrada_registrada.strftime('%H:%M:%S')}**")
        else:
            if st.button("🔴 REGISTRAR ENTRADA", use_container_width=True, type="primary"):
                dados_ponto = {
                    "email": user_email, 
                    "nome_completo": user_name, 
                    "data": str(hoje), 
                    "horario_entrada": agora_br.isoformat() 
                }
                executar_query_supabase("salvar_entrada", data_dict=dados_ponto)
                st.success("Entrada gravada com sucesso!")
                st.rerun()

# --- OPÇÃO: SAÍDA ---
elif opcao == "SAÍDA":
    st.subheader("📍 Registrar Saída")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not entrada_registrada:
            st.warning("⚠️ Você precisa registrar o ponto de ENTRADA antes de registrar a saída.")
        else:
            st.write(f"Horário da sua Entrada hoje: **{entrada_registrada.strftime('%H:%M:%S')}**")
            
            if saida_registrada:
                st.info(f"Sua saída registrada atualmente é: **{saida_registrada.strftime('%H:%M:%S')}**")
                texto_botao = "🔄 ALTERAR HORÁRIO DE SAÍDA"
            else:
                texto_botao = "🔵 REGISTRAR SAÍDA"

            if st.button(texto_botao, use_container_width=True, type="secondary" if saida_registrada else "primary"):
                st.session_state['confirmar_saida'] = True

            if st.session_state.get('confirmar_saida', False):
                tempo_trabalhado = agora_br - entrada_registrada
                total_segundos = int(tempo_trabalhado.total_seconds())
                horas = total_segundos // 3600
                minutos = (total_segundos % 3600) // 60
                
                jornada_padrao = 9 * 3600
                if total_segundos > jornada_padrao:
                    segundos_extras = total_segundos - jornada_padrao
                    horas_ext = segundos_extras // 3600
                    minutos_ext = (segundos_extras % 3600) // 60
                    msg_extra = f" e fez {horas_ext:02d} hours e {minutos_ext:02d} minutos de hora extra."
                else:
                    msg_extra = "."

                st.markdown("---")
                st.warning(f"⚠️ **Confirmação de Ponto:**\n\nSua jornada de hoje foi de: **{horas:02d} horas e {minutos:02d} minutos**{msg_extra}")
                
                c1, c2 = st.columns(2)
                if c1.button("Sim, Confirmar", use_container_width=True):
                    executar_query_supabase(
                        "salvar_saida", 
                        data_dict={"horario_saida": agora_br.isoformat()}, 
                        email=user_email, 
                        data_filtro=hoje
                    )
                    st.session_state['confirmar_saida'] = False
                    st.success("Saída salva com sucesso!")
                    st.rerun()
                if c2.button("Cancelar", use_container_width=True):
                    st.session_state['confirmar_saida'] = False
                    st.rerun()

# --- OPÇÃO: LOG ---
elif opcao == "LOG":
    st.subheader("📢 Mural de Atividades (Tempo Real)")
    st.caption("Abaixo estão as entradas e saídas recentes da equipe baseadas no horário de Brasília.")
    st.markdown("---")
    
    logs = executar_query_supabase("buscar_logs")
    if not logs:
        st.info("Nenhum registro ativo no mural recente.")
    else:
        for item in logs:
            nome = item["nome_completo"]
            dt_compara = datetime.strptime(item["data"], "%Y-%m-%d").strftime("%d/%m")
            
            if item["horario_entrada"]:
                ent = datetime.fromisoformat(item["horario_entrada"]).astimezone(fuso_br).strftime("%H:%M")
                st.write(f"🟢 **{nome}** entrou às {ent} ({dt_compara})")
            if item["horario_saida"]:
                sai = datetime.fromisoformat(item["horario_saida"]).astimezone(fuso_br).strftime("%H:%M")
                st.write(f"🔵 **{nome}** saiu às {sai} ({dt_compara})")
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
            df.columns = ["Data", "Horário Entrada", "Horário Saída"]
            
            df["Data"] = df["Data"].apply(lambda x: datetime.strptime(x, "%Y-%m-%d").strftime('%d/%m/%Y'))
            df["Horário Entrada"] = df["Horário Entrada"].apply(lambda x: datetime.fromisoformat(x).astimezone(fuso_br).strftime('%H:%M:%S') if x else "-")
            df["Horário Saída"] = df["Horário Saída"].apply(lambda x: datetime.fromisoformat(x).astimezone(fuso_br).strftime('%H:%M:%S') if x else "-")
            
            st.dataframe(df, use_container_width=True)
            
            # --- LÓGICA DE EXPORTAÇÃO PARA EXCEL (.XLSX) ---
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
