import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from streamlit_google_auth import Authenticate
from sqlalchemy import text # <-- Adicione esta linha nova aqui em cima

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Ponto Eletrônico", page_icon="⏱️", layout="centered")

# --- CONEXÃO NATIVA DO STREAMLIT ---
conn = st.connection("postgres", type="sql")

def executar_query(query, params=(), fetch=False):
    # Transforma a string SQL em um objeto de texto executável pelo SQLAlchemy
    query_formatada = text(query)
    
    with conn.session as session:
        # Se os parâmetros forem passados como tupla (ex: (user_email, hoje)), 
        # o SQLAlchemy prefere que convertamos para dicionário ou usemos mapeamento posicional.
        # Para manter seu código simples, convertemos os parâmetros caso existam:
        result = session.execute(query_formatada, params)
        
        if fetch:
            return result.fetchall()
        session.commit()


# --- AUTENTICAÇÃO GOOGLE ---
# As credenciais devem ser colocadas no st.secrets do Streamlit Cloud
auth = Authenticate(
    secret_key=st.secrets["auth"]["secret_key"],
    client_id=st.secrets["auth"]["client_id"],
    client_secret=st.secrets["auth"]["client_secret"],
    redirect_uri=st.secrets["auth"]["redirect_uri"],
    cookie_name="ponto_google_auth",
    cookie_key="chave_secreta_cookie",
    cookie_expiry_days=30
)

# Renderiza o botão de login se não estiver autenticado
auth.check_authentification()

if not st.session_state.get("connected", False):
    st.title("⏱️ Sistema de Ponto")
    st.info("Por favor, faça login com sua conta Google para registrar seu ponto.")
    auth.login()
    st.stop()

# --- USUÁRIO LOGADO ---
user_info = st.session_state.get("user_info", {})
user_email = user_info.get("email")
user_name = user_info.get("name", "Colaborador")  # Retorna Nome e Sobrenome do Google
hoje = date.today()

# --- LIMPEZA AUTOMÁTICA DO LOG (1 EM 1 MÊS) ---
# Oculta do log registros com mais de 30 dias, mas mantém no banco para relatórios
executar_query("UPDATE registro_ponto SET exibir_no_log = FALSE WHERE data < %s", (hoje - timedelta(days=30),))

# --- INTERFACE / MENU LATERAL ---
st.sidebar.image(user_info.get("picture", ""), width=70)
st.sidebar.write(f"Olá, **{user_name}**!")

opcao = st.sidebar.radio("Navegação", ["ENTRADA", "SAÍDA", "LOG", "RELATÓRIO"])

st.sidebar.markdown("---")
if st.sidebar.button("Sair / Logout"):
    auth.logout()
    st.rerun()

# --- LÓGICA DAS OPÇÕES ---

# Buscar dados de hoje do usuário para controle dos botões
dados_hoje = executar_query(
    "SELECT horario_entrada, horario_saida FROM registro_ponto WHERE email = %s AND data = %s",
    (user_email, hoje), fetch=True
)

entrada_registrada = dados_hoje[0][0] if dados_hoje else None
saida_registrada = dados_hoje[0][1] if dados_hoje else None

# --- OPÇÃO: ENTRADA ---
if opcao == "ENTRADA":
    st.subheader("📍 Registrar Entrada")

    # Centralizar botão na tela
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write(f"Data de hoje: {hoje.strftime('%d/%m/%Y')}")
        if entrada_registrada:
            st.success(f"Entrada já registrada hoje às: {entrada_registrada.strftime('%H:%M:%S')}")
        else:
            if st.button("🔴 REGISTRAR ENTRADA", use_container_width=True, type="primary"):
                agora = datetime.now()
                executar_query(
                    """INSERT INTO registro_ponto (email, nome_completo, data, horario_entrada) 
                       VALUES (%s, %s, %s, %s) ON CONFLICT (email, data) DO UPDATE SET horario_entrada = %s""",
                    (user_email, user_name, hoje, agora, agora)
                )
                st.success(f"Entrada registrada com sucesso às {agora.strftime('%H:%M:%S')}!")
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

            # Janela/Aviso de confirmação com cálculo de horas
            if st.session_state.get('confirmar_saida', False):
                agora = datetime.now()

                # Cálculo da jornada
                formato_entrada = entrada_registrada.replace(tzinfo=None)
                tempo_trabalhado = agora - formato_entrada
                total_segundos = int(tempo_trabalhado.total_seconds())
                horas = total_segundos // 3600
                minutos = (total_segundos % 3600) // 60

                # Regra de hora extra (Passou de 9 horas)
                jornada_padrao_segundos = 9 * 3600
                if total_segundos > jornada_padrao_segundos:
                    segundos_extras = total_segundos - jornada_padrao_segundos
                    horas_ext = segundos_extras // 3600
                    minutos_ext = (segundos_extras % 3600) // 60
                    msg_extra = f" e fez {horas_ext:02d} horas e {minutos_ext:02d} minutos de hora extra."
                else:
                    msg_extra = "."

                st.warning(
                    f"⚠️ **Confirmação de Registro:**\n\nSua jornada de hoje foi de: {horas:02d} horas e {minutos:02d} minutos{msg_extra}")

                c1, c2 = st.columns(2)
                if c1.button("Sim, Confirmar", use_container_width=True):
                    executar_query(
                        "UPDATE registro_ponto SET horario_saida = %s WHERE email = %s AND data = %s",
                        (agora, user_email, hoje)
                    )
                    st.session_state['confirmar_saida'] = False
                    st.success("Saída gravada com sucesso!")
                    st.rerun()

                if c2.button("Cancelar", use_container_width=True):
                    st.session_state['confirmar_saida'] = False
                    st.rerun()

# --- OPÇÃO: LOG (TEMPO REAL) ---
elif opcao == "LOG":
    st.subheader("📢 Mural de Atividades (Tempo Real)")
    st.caption("Mostra as entradas e saídas dos últimos 30 dias.")

    # Busca logs ativos ordenados pelo horário mais recente
    logs = executar_query(
        """SELECT nome_completo, horario_entrada, horario_saida, data 
           FROM registro_ponto WHERE exibir_no_log = TRUE ORDER BY data DESC, horario_entrada DESC""",
        fetch=True
    )

    if not logs:
        st.info("Nenhum registro no log recentemente.")
    else:
        for nome, entrada, saida, dt in logs:
            data_formatada = dt.strftime('%d/%m')
            if entrada:
                st.write(f"🟢 **{nome}** entrou às {entrada.strftime('%H:%M')} ({data_formatada})")
            if saida:
                st.write(f"🔵 **{nome}** saiu às {saida.strftime('%H:%M')} ({data_formatada})")
            st.markdown("---")

# --- OPÇÃO: RELATÓRIO ---
elif opcao == "RELATÓRIO":
    st.subheader(f"📊 Relatório de Horas - {user_name}")

    # Filtro por Calendário
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data Inicial", hoje - timedelta(days=7))
    with col2:
        data_fim = st.date_input("Data Final", hoje)

    if data_inicio > data_fim:
        st.error("A data inicial não pode ser maior que a data final.")
    else:
        # Busca apenas os dados do usuário logado (mesmo se exibir_no_log for False)
        dados_relatorio = executar_query(
            """SELECT data, horario_entrada, horario_saida 
               FROM registro_ponto 
               WHERE email = %s AND data BETWEEN %s AND %s 
               ORDER BY data DESC""",
            (user_email, data_inicio, data_fim), fetch=True
        )

        if not dados_relatorio:
            st.info("Nenhum ponto registrado no período selecionado.")
        else:
            # Organizar dados em um DataFrame para exibição bonita
            df = pd.DataFrame(dados_relatorio, columns=["Data", "Horário Entrada", "Horário Saída"])

            # Formatação de datas e horas para exibição
            df["Data"] = df["Data"].apply(lambda x: x.strftime('%d/%m/%Y'))
            df["Horário Entrada"] = df["Horário Entrada"].apply(lambda x: x.strftime('%H:%M:%S') if x else "-")
            df["Horário Saída"] = df["Horário Saída"].apply(lambda x: x.strftime('%H:%M:%S') if x else "-")

            st.dataframe(df, use_container_width=True)

            # Opção de exportar para CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Relatório em CSV",
                data=csv,
                file_name=f"relatorio_ponto_{user_name.replace(' ', '_')}.csv",
                mime='text/csv',
            )
