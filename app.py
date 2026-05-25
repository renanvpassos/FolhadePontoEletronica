import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from streamlit_google_auth import Authenticate
from supabase import create_client, Client # <-- Nova biblioteca simplificada

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Ponto Eletrônico", page_icon="⏱️", layout="centered")

# --- CONEXÃO COM O SUPABASE ---
url: str = st.secrets["supabase"]["url"]
key: str = st.secrets["supabase"]["key"]
supabase: Client = create_client(url, key)

# --- FUNÇÃO DE QUERY REESCRITA PARA O SUPABASE CLIENT ---
def executar_query_supabase(operacao, data_dict=None, email=None, data_filtro=None, data_fim=None, log_ativo=False):
    tabela = supabase.table("registro_ponto")
    
    if operacao == "buscar_hoje":
        res = tabela.select("horario_entrada, horario_saida").eq("email", email).eq("data", data_filtro).execute()
        return res.data
        
    elif operacao == "salvar_entrada":
        # Se já existir, faz update, se não, faz insert
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

# --- AUTENTICAÇÃO GOOGLE ---
auth = Authenticate(
    secret_key=st.secrets["auth"]["secret_key"],
    client_id=st.secrets["auth"]["client_id"],
    client_secret=st.secrets["auth"]["client_secret"],
    redirect_uri=st.secrets["auth"]["redirect_uri"],
    cookie_name="meu_ponto_customizado",       # <-- Personalizado por você
    cookie_key="Chav3DeP0nt016Chr",            # <-- Personalizado por você (EXATAMENTE 16 caracteres)
    cookie_expiry_days=30
)

auth.check_authentification()

if not st.session_state.get("connected", False):
    st.title("⏱️ Sistema de Ponto")
    st.info("Por favor, faça login com sua conta Google para registrar seu ponto.")
    auth.login()
    st.stop()

user_info = st.session_state.get("user_info", {})
user_email = user_info.get("email")
user_name = user_info.get("name", "Colaborador")
hoje = date.today()

# --- LIMPEZA AUTOMÁTICA DO LOG (1 EM 1 MÊS) ---
executar_query_supabase("limpar_log", data_filtro=hoje - timedelta(days=30))

# --- INTERFACE / MENU LATERAL ---
st.sidebar.image(user_info.get("picture", ""), width=70)
st.sidebar.write(f"Olá, **{user_name}**!")
opcao = st.sidebar.radio("Navegação", ["ENTRADA", "SAÍDA", "LOG", "RELATÓRIO"])

st.sidebar.markdown("---")
if st.sidebar.button("Sair / Logout"):
    auth.logout()
    st.rerun()

# --- LÓGICA DAS OPÇÕES ---
dados_hoje = executar_query_supabase("buscar_hoje", email=user_email, data_filtro=hoje)
entrada_registrada = dados_hoje[0]["horario_entrada"] if dados_hoje else None
saida_registrada = dados_hoje[0]["horario_saida"] if dados_hoje else None

if entrada_registrada and isinstance(entrada_registrada, str):
    entrada_registrada = datetime.fromisoformat(entrada_registrada.replace("Z", "+00:00"))
if saida_registrada and isinstance(saida_registrada, str):
    saida_registrada = datetime.fromisoformat(saida_registrada.replace("Z", "+00:00"))

# --- OPÇÃO: ENTRADA ---
if opcao == "ENTRADA":
    st.subheader("📍 Registrar Entrada")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write(f"Data de hoje: {hoje.strftime('%d/%m/%Y')}")
        if entrada_registrada:
            st.success(f"Entrada já registrada hoje às: {entrada_registrada.strftime('%H:%M:%S')}")
        else:
            if st.button("🔴 REGISTRAR ENTRADA", use_container_width=True, type="primary"):
                agora = datetime.now().isoformat()
                dados_ponto = {"email": user_email, "nome_completo": user_name, "data": str(hoje), "horario_entrada": agora}
                executar_query_supabase("salvar_entrada", data_dict=dados_ponto)
                st.success("Entrada registrada com sucesso!")
                st.rerun()

# --- OPÇÃO: SAÍDA ---
elif opcao == "SAÍDA":
    st.subheader("📍 Registrar Saída")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not entrada_registrada:
            st.warning("Você precisa registrar a ENTRADA antes de registrar a saída.")
        else:
            st.write(f"Sua Entrada hoje foi às: {entrada_registrada.strftime('%H:%M:%S')}")
            if saida_registrada:
                st.info(f"Sua saída atual está marcada para: {saida_registrada.strftime('%H:%M:%S')}")
                texto_botao = "🔄 ALTERAR HORÁRIO DE SAÍDA"
            else:
                texto_botao = "🔵 REGISTRAR SAÍDA"

            if st.button(texto_botao, use_container_width=True, type="secondary" if saida_registrada else "primary"):
                st.session_state['confirmar_saida'] = True

            if st.session_state.get('confirmar_saida', False):
                agora = datetime.now()
                formato_entrada = entrada_registrada.replace(tzinfo=None)
                tempo_trabalhado = agora - formato_entrada
                total_segundos = int(tempo_trabalhado.total_seconds())
                horas = total_segundos // 3600
                minutos = (total_segundos % 3600) // 60
                
                jornada_padrao = 9 * 3600
                if total_segundos > jornada_padrao:
                    segundos_extras = total_segundos - jornada_padrao
                    horas_ext = segundos_extras // 3600
                    minutos_ext = (segundos_extras % 3600) // 60
                    msg_extra = f" e fez {horas_ext:02d} horas e {minutos_ext:02d} minutos de hora extra."
                else:
                    msg_extra = "."

                st.warning(f"⚠️ **Confirmação:**\n\nSua jornada foi de: {horas:02d} horas e {minutos:02d} minutos{msg_extra}")
                c1, c2 = st.columns(2)
                if c1.button("Sim, Confirmar", use_container_width=True):
                    executar_query_supabase("salvar_saida", data_dict={"horario_saida": agora.isoformat()}, email=user_email, data_filtro=hoje)
                    st.session_state['confirmar_saida'] = False
                    st.success("Saída gravada com sucesso!")
                    st.rerun()
                if c2.button("Cancelar", use_container_width=True):
                    st.session_state['confirmar_saida'] = False
                    st.rerun()

# --- OPÇÃO: LOG ---
elif opcao == "LOG":
    st.subheader("📢 Mural de Atividades (Tempo Real)")
    logs = executar_query_supabase("buscar_logs")
    if not logs:
        st.info("Nenhum registro no log recentemente.")
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
            st.markdown("---")

# --- OPÇÃO: RELATÓRIO ---
elif opcao == "RELATÓRIO":
    st.subheader(f"📊 Relatório de Horas - {user_name}")
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data Inicial", hoje - timedelta(days=7))
    with col2:
        data_fim = st.date_input("Data Final", hoje)
        
    if data_inicio > data_fim:
        st.error("A data inicial não pode ser maior que a data final.")
    else:
        dados_relatorio = executar_query_supabase("buscar_relatorio", email=user_email, data_filtro=data_inicio, data_fim=data_fim)
        if not dados_relatorio:
            st.info("Nenhum ponto registrado no período selecionado.")
        else:
            df = pd.DataFrame(dados_relatorio)
            df.columns = ["Data", "Horário Entrada", "Horário Saída"]
            df["Data"] = df["Data"].apply(lambda x: datetime.strptime(x, "%Y-%m-%d").strftime('%d/%m/%Y'))
            df["Horário Entrada"] = df["Horário Entrada"].apply(lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")).strftime('%H:%M:%S') if x else "-")
            df["Horário Saída"] = df["Horário Saída"].apply(lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")).strftime('%H:%M:%S') if x else "-")
            
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Baixar Relatório em CSV", data=csv, file_name=f"relatorio_{user_name.replace(' ', '_')}.csv", mime='text/csv')
