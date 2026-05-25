import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from google.oauth2 import id_token
from google.auth.transport import requests
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Ponto Eletrônico", page_icon="⏱️", layout="centered")

# --- CONEXÃO COM O SUPABASE ---
url: str = st.secrets["supabase"]["url"]
key: str = st.secrets["supabase"]["key"]
supabase: Client = create_client(url, key)

# --- FUNÇÃO DE AJUSTE DE BANCO (SUPABASE) ---
def executar_query_supabase(operacao, data_dict=None, email=None, data_filtro=None, data_fim=None):
    tabela = supabase.table("registro_ponto")
    
    if operacao == "buscar_hoje":
        res = tabela.select("horario_entrada, horario_saida").eq("email", email).eq("data", data_filtro).execute()
        return res.data
        
    elif operacao == "salvar_entrada":
        tabela.upsert(data_dict, on_conflict="email,data").execute()
        
    elif operacao == "salvar_saida":
        tabela.update({"horario_saida": data_dict["horario_saida"]}).eq("email", email).eq("data", data_filtro).execute()
        
    elif operacao == "limpar_log":
        tabela.update({"exibir_no_log": False}).lt("data", str(data_filtro)).execute()
        
    elif operacao == "buscar_logs":
        res = tabela.select("nome_completo, horario_entrada, horario_saida, data").eq("exibir_no_log", True).order("data", desc=True).execute()
        return res.data
        
    elif operacao == "buscar_relatorio":
        res = tabela.select("data, horario_entrada, horario_saida").eq("email", email).gte("data", str(data_filtro)).lte("data", str(data_fim)).order("data", desc=True).execute()
        return res.data

# --- AUTENTICAÇÃO GOOGLE (NATIVA OFICIAL) ---
def verificar_login_google():
    # Verifica se há um token de login vindo na URL do redirecionamento
    query_params = st.query_params
    if "id_token" in query_params:
        try:
            token = query_params["id_token"]
            client_id = st.secrets["auth"]["client_id"]
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
            
            # Salva o usuário logado na sessão
            st.session_state["user_info"] = idinfo
            st.session_state["connected"] = True
            
            # Limpa o token da URL para o visual ficar limpo
            st.query_params.clear()
            st.rerun()
        except Exception:
            st.error("Erro ao validar login do Google. Tente novamente.")

    # Se não estiver conectado, mostra a tela de login
    if not st.session_state.get("connected", False):
        st.title("⏱️ Sistema de Ponto Eletrônico")
        st.write("---")
        st.info("Por favor, conecte-se com sua conta Google para registrar seu ponto.")
        
        client_id = st.secrets["auth"]["client_id"]
        redirect_uri = st.secrets["auth"]["redirect_uri"]
        
        # URL de Autenticação do Google OpenID Connect (AJUSTADA PARA LOGIN INTERNO)
        login_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=id_token&scope=openid%20email%20profile&nonce=ponto_nonce&prompt=consent"
        
        # Botão personalizado estilizado do Google
        st.markdown(
            f'<a href="{login_url}" target="_self" style="text-decoration:none;">'
            f'<button style="background-color:#4285F4;color:white;border:none;padding:12px 24px;'
            f'border-radius:4px;cursor:pointer;font-weight:bold;font-size:16px;width:100%;">'
            f'🔵 Entrar com a Conta Google</button></a>', 
            unsafe_allow_html=True
        )
        st.stop()

# Executa o controle de portaria/login
verificar_login_google()

# --- CONFIGURAÇÃO DE USUÁRIO LOGADO ---
user_info = st.session_state.get("user_info", {})
user_email = user_info.get("email")
user_name = user_info.get("name", "Colaborador")
hoje = date.today()

# --- LIMPEZA AUTOMÁTICA DO LOG (1 EM 1 MÊS) ---
# Altera a flag para sumir do log geral, mas mantém guardado de forma segura para os relatórios
executar_query_supabase("limpar_log", data_filtro=hoje - timedelta(days=30))

# --- INTERFACE / MENU LATERAL ---
if user_info.get("picture"):
    st.sidebar.image(user_info.get("picture"), width=70)
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

# Conversão de fuso horário UTC vindo do Supabase para datetime do Python
if entrada_registrada and isinstance(entrada_registrada, str):
    entrada_registrada = datetime.fromisoformat(entrada_registrada.replace("Z", "+00:00"))
if saida_registrada and isinstance(saida_registrada, str):
    saida_registrada = datetime.fromisoformat(saida_registrada.replace("Z", "+00:00"))

# --- OPÇÃO: ENTRADA ---
if opcao == "ENTRADA":
    st.subheader("📍 Registrar Entrada")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write(f"**Data de hoje:** {hoje.strftime('%d/%m/%Y')}")
        if entrada_registrada:
            st.success(f"✅ Entrada registrada hoje às: **{entrada_registrada.strftime('%H:%M:%S')}**")
        else:
            if st.button("🔴 REGISTRAR ENTRADA", use_container_width=True, type="primary"):
                agora = datetime.now().isoformat()
                dados_ponto = {
                    "email": user_email, 
                    "nome_completo": user_name, 
                    "data": str(hoje), 
                    "horario_entrada": agora
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

            # Modal de confirmação e cálculo de horas de jornada
            if st.session_state.get('confirmar_saida', False):
                agora = datetime.now()
                formato_entrada = entrada_registrada.replace(tzinfo=None)
                
                tempo_trabalhado = agora - formato_entrada
                total_segundos = int(tempo_trabalhado.total_seconds())
                horas = total_segundos // 3600
                minutos = (total_segundos % 3600) // 60
                
                # Regra de horas extras (Acima de 9 horas de expediente)
                jornada_padrao = 9 * 3600
                if total_segundos > jornada_padrao:
                    segundos_extras = total_segundos - jornada_padrao
                    horas_ext = segundos_extras // 3600
                    minutos_ext = (segundos_extras % 3600) // 60
                    msg_extra = f" e fez {horas_ext:02d} horas e {minutos_ext:02d} minutos de hora extra."
                else:
                    msg_extra = "."

                st.markdown("---")
                st.warning(f"⚠️ **Confirmação de Ponto:**\n\nSua jornada de hoje foi de: **{horas:02d} horas e {minutos:02d} minutos**{msg_extra}")
                
                c1, c2 = st.columns(2)
                if c1.button("Sim, Confirmar", use_container_width=True):
                    executar_query_supabase(
                        "salvar_saida", 
                        data_dict={"horario_saida": agora.isoformat()}, 
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
    st.caption("Abaixo estão as entradas e saídas recentes da equipe.")
    st.markdown("---")
    
    logs = executar_query_supabase("buscar_logs")
    if not logs:
        st.info("Nenhum registro ativo no mural recente.")
    else:
        for item in logs:
            nome = item["nome_completo"]
            dt_compara = datetime.strptime(item["data"], "%Y-%m-%d").strftime("%d/%m")
            
            if item["horario_entrada"]:
                ent = datetime.fromisoformat(item["horario_entrada"].replace("Z", "+00:00")).strftime("%H:%M")
                st.write(f"🟢 **{nome}** entrou às {ent} ({dt_compara})")
            if item["horario_saida"]:
                sai = datetime.fromisoformat(item["horario_saida"].replace("Z", "+00:00")).strftime("%H:%M")
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
            # Estrutura a tabela visual usando o Pandas DataFrame
            df = pd.DataFrame(dados_relatorio)
            df.columns = ["Data", "Horário Entrada", "Horário Saída"]
            
            # Formatações amigáveis de datas e horas para exibição na tela
            df["Data"] = df["Data"].apply(lambda x: datetime.strptime(x, "%Y-%m-%d").strftime('%d/%m/%Y'))
            df["Horário Entrada"] = df["Horário Entrada"].apply(lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")).strftime('%H:%M:%S') if x else "-")
            df["Horário Saída"] = df["Horário Saída"].apply(lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")).strftime('%H:%M:%S') if x else "-")
            
            st.dataframe(df, use_container_width=True)
            
            # Geração do arquivo estruturado para download em planilhas (CSV)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Meu Relatório em CSV", 
                data=csv, 
                file_name=f"relatorio_ponto_{user_name.replace(' ', '_')}.csv", 
                mime='text/csv'
            )
