import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
from io import BytesIO
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Ponto Eletrônico", page_icon="⏱️", layout="centered")

# --- ESTILIZAÇÃO CSS CUSTOMIZADA ---
st.markdown("""
    <style>
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

# --- LIMPEZA AUTOMÁTICA DO LOG (1 EM 1 MÊS) ---
executar_query_supabase("limpar_log", data_filtro=hoje - timedelta(days=30))

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

# --- MENU: REGISTRO DE HORÁRIOS ---
# --- MENU: REGISTRO DE HORÁRIOS (DIGITAÇÃO MANUAL E JUSTIFICATIVA) ---
if opcao in ["ENTRADA", "SAÍDA ALMOÇO", "RETORNO ALMOÇO", "SAÍDA"]:
    st.title(f"📍 Registro de {opcao.title()}")
    
    c_data, c_hora = st.columns(2)
    with c_data:
        st.metric(label="🗓️ Data Oficial", value=hoje.strftime('%d/%m/%Y'))
    with c_hora:
        st.metric(label="⏱️ Horário do Servidor (Brasília)", value=agora_br.strftime('%H:%M'))
        
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
                
                if opcao in ["ENTRADA", "SAÍDA"]:
                    st.markdown("##### 📝 Ajuste Manual do Registro")
                    
                    # Campo de texto obrigando a digitação manual no formato HH:mm
                    hora_digitada = st.text_input(
                        "Digite o horário do ponto (Formato obrigatório HH:mm):", 
                        value=agora_br.strftime('%H:%M'),
                        max_chars=5,
                        key=f"input_manual_{opcao}"
                    ).strip()
                    
                    # Validação estrita do formato HH:mm (Horas de 00 a 23, Minutos de 00 a 59)
                    import re
                    padrao_hora = re.compile(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$")
                    
                    if not padrao_hora.match(hora_digitada):
                        st.error("🛑 Formato de horário inválido! Digite um horário real entre 00:00 e 23:59 utilizando duas partes separadas por dois pontos (Exemplo: 08:30).")
                        erro_validacao = True
                    else:
                        # Se o formato estiver válido, converte a string para um objeto datetime válido
                        h_partes = list(map(int, hora_digitada.split(":")))
                        hora_manual_objeto = datetime.time(h_partes[0], h_partes[1])
                        horario_final_gravacao = datetime.combine(hoje, hora_manual_objeto).replace(tzinfo=fuso_br)
                    
                    # Verifica se o horário digitado é diferente do horário atual do servidor (ignora segundos)
                    foi_alterado = hora_digitada != agora_br.strftime('%H:%M')
                    
                    label_justificativa = "Justificativa da marcação:" if not foi_alterado else "Justificativa (OBRIGATÓRIA para horários alterados manualmente):"
                    justificativa = st.text_area(label_justificativa, key=f"just_{opcao}").strip()
                
                # --- LÓGICA DE EXIBIÇÃO DA JORNADA EXCLUSIVA PARA A OPÇÃO "SAÍDA" ---
                if opcao == "SAÍDA" and not erro_validacao:
                    if not pontos["ENTRADA"]:
                        st.error("⚠️ Não é possível calcular a jornada porque a **ENTRADA** de hoje não foi registrada.")
                        msg_confirmacao = f"Deseja gravar a Saída mesmo sem o ponto de Entrada?"
                    else:
                        t_entrada = pontos["ENTRADA"]
                        t_saida_alm = pontos["SAÍDA ALMOÇO"]
                        t_retorno_alm = pontos["RETORNO ALMOÇO"]
                        t_saida_atual = horario_final_gravacao
                        
                        tempo_total = t_saida_atual - t_entrada
                        total_segundos = int(tempo_total.total_seconds())
                        
                        segundos_almoco = 0
                        if t_saida_alm and t_retorno_alm:
                            if t_retorno_alm > t_saida_alm:
                                segundos_almoco = int((t_retorno_alm - t_saida_alm).total_seconds())
                        
                        segundos_trabalhados = total_segundos - segundos_almoco
                        if segundos_trabalhados < 0:
                            segundos_trabalhados = 0
                            
                        horas_trab = segundos_trabalhados // 3600
                        minutos_trab = (segundos_trabalhados % 3600) // 60
                        
                        jornada_padrao_segundos = 8 * 3600 
                        
                        msg_extra = "Não houve hora extra."
                        if segundos_trabalhados > jornada_padrao_segundos:
                            segundos_extras = segundos_trabalhados - jornada_padrao_segundos
                            horas_ext = segundos_extras // 3600
                            minutos_ext = (segundos_extras % 3600) // 60
                            msg_extra = f"🔥 **{horas_ext:02d}h {minutos_ext:02d}min** de hora extra."
                            
                        st.info(f"📊 **Resumo da Jornada Calculada:**\n\n"
                                f"⏱️ Tempo Líquido Trabalhado: **{horas_trab:02d}h {minutos_trab:02d}min**\n\n"
                                f"🚀 Banco de Horas: {msg_extra}")
                                
                        msg_confirmacao = f"Confirmar gravação do horário de Saída como **{horario_final_gravacao.strftime('%H:%M:%S')}**?"
                else:
                    msg_confirmacao = f"Deseja gravar o horário **{horario_final_gravacao.strftime('%H:%M:%S')}** na opção **{opcao}**?"
                
                if not erro_validacao:
                    st.warning(msg_confirmacao)
                
                c1, c2 = st.columns(2)
                
                # Regras para bloquear o botão de envio
                bloquear_confirmacao = erro_validacao
                if opcao in ["ENTRADA", "SAÍDA"] and not erro_validacao:
                    if foi_alterado and not justificativa:
                        bloquear_confirmacao = True
                        st.error("🛑 Você alterou o horário manualmente. Digite uma justificativa para poder confirmar.")
                
                if c1.button("Confirmar Marcação", key=f"sim_{opcao}", use_container_width=True, type="primary", disabled=bloquear_confirmacao):
                    dados_ponto = {
                        "email": user_email,
                        "nome_completo": user_name,
                        "data": str(hoje),
                        colunas_banco[opcao]: horario_final_gravacao.isoformat()
                    }
                    
                    if opcao == "ENTRADA" and justificativa:
                        dados_ponto["justificativa_entrada"] = justificativa
                    elif opcao == "SAÍDA" and justificativa:
                        dados_ponto["justificativa_saida"] = justificativa
                        
                    executar_query_supabase("salvar_ponto", data_dict=dados_ponto)
                    st.session_state[f'confirmar_{opcao}'] = False
                    st.success(f"Horário gravado com sucesso!")
                    st.rerun()
                    
                if c2.button("Cancelar", key=f"nao_{opcao}", use_container_width=True):
                    st.session_state[f'confirmar_{opcao}'] = False
                    st.rerun()

# --- MENU: LOG ---
elif opcao == "LOG":
    st.title("📢 Mural de Atividades")
    st.caption("Log de atividades da equipe.")
    st.write("---")
    
    logs_banco = executar_query_supabase("buscar_logs")
    if not logs_banco:
        st.info("Nenhuma atividade registrada no mural recente.")
    else:
        lista_eventos = []
        labels_acoes = {
            "horario_entrada": "🟢 ENTROU",
            "saida_almoco": "🟡 saiu para o ALMOÇO",
            "retorno_almoco": " 🔵 retornou do almoço",
            "horario_saida": "🟠 SAIU"
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
            
            with st.container():
                for evento in lista_eventos:
                    st.markdown(
                        f'<div class="card-log">'
                        f'⏱️ <b>{evento["hora_str"]}</b> - <b>{evento["nome"]}</b> {evento["acao"]} <span style="float: right; color: gray; font-size: 0.85em;">📅 {evento["data_str"]}</span>'
                        f'</div>', 
                        unsafe_allow_html=True
                    )

# --- MENU: RELATÓRIO CORRIGIDO PARA FORMATO BRASILEIRO NATIVO (TELA + EXCEL) ---
elif opcao == "RELATÓRIO":
    st.title("📊 Espelho de Ponto Pessoal")
    
    # 1. Definição dos e-mails administrativos que possuem acesso total
    admins_permitidos = [
        "renan.veloso@multprocessing.com.br",
        "marcello@multprocessing.com.br"
    ]
    
    # 2. Inicializa as variáveis de escopo da busca
    email_busca = user_email
    nome_busca = user_name
    
    # 3. Se o usuário logado for admin, liberamos o container de seleção de funcionários
    if user_email in admins_permitidos:
        st.markdown("### 🔑 Painel de Gestão (Administrador)")
        
        # Buscamos a lista de todos os usuários cadastrados no banco para alimentar o menu suspenso
        try:
            usuarios_banco = supabase.table("usuarios_ponto").select("email, nome").execute()
            if usuarios_banco.data:
                # Criamos um dicionário amigável para o selectbox: "Nome Completo (email@...)"
                opcoes_usuarios = {f"{u['nome']} ({u['email']})": u for u in usuarios_banco.data}
                
                usuario_selecionado_str = st.selectbox(
                    "Selecione o colaborador que deseja consultar:",
                    options=list(opcoes_usuarios.keys())
                )
                
                # Sobrescrevemos as variáveis de busca com o funcionário escolhido no menu suspenso
                colaborador_escolhido = opcoes_usuarios[usuario_selecionado_str]
                email_busca = colaborador_escolhido["email"]
                nome_busca = colaborador_escolhido["nome"]
        except Exception as e:
            st.error("Erro ao carregar a lista de funcionários.")
            
    st.caption(f"Filtro e exportação de folhas e históricos para: **{nome_busca}**")
    st.write("")
    
    # Container de filtros por Data
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input(
                "🗓️ Data Inicial", 
                hoje - timedelta(days=7),
                format="DD/MM/YYYY"
            )
        with col2:
            data_fim = st.date_input(
                "🗓️ Data Final", 
                hoje,
                format="DD/MM/YYYY"
            )
        
    st.write("---")
    
    if data_inicio > data_fim:
        st.error("Erro: A data inicial não pode ser maior que a data final.")
    else:
        # A query agora utiliza a variável dinâmica 'email_busca'
        dados_relatorio = executar_query_supabase(
            "buscar_relatorio", 
            email=email_busca, 
            data_filtro=data_inicio, 
            data_fim=data_fim
        )
        
        if not dados_relatorio:
            st.info(f"Não foram encontrados registros de ponto para {nome_busca} no período selecionado.")
        else:
            df = pd.DataFrame(dados_relatorio)
            df.columns = ["Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída"]
            
            def formata_hora(x):
                if not x: return "-"
                try:
                    return datetime.fromisoformat(x).astimezone(fuso_br).strftime('%H:%M:%S')
                except:
                    return "-"

            # Aplica a formatação de horários nas colunas
            df["Entrada"] = df["Entrada"].apply(formata_hora)
            df["Saída Almoço"] = df["Saída Almoço"].apply(formata_hora)
            df["Retorno Almoço"] = df["Retorno Almoço"].apply(formata_hora)
            df["Saída"] = df["Saída"].apply(formata_hora)
            
            # Criamos uma cópia para renderizar na tela com a data convertida para String BR
            df_tela = df.copy()
            df_tela["Data"] = pd.to_datetime(df_tela["Data"]).dt.strftime('%d/%m/%Y')
            
            # Exibe na tela com o formato DD/MM/AAAA garantido
            st.dataframe(df_tela, use_container_width=True)
            
            # --- EXPORTAÇÃO EXCEL PROCESSADA ---
            output = BytesIO()
            df_excel = df.copy()
            df_excel["Data"] = pd.to_datetime(df_excel["Data"]).dt.strftime('%d/%m/%Y')
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_excel.to_excel(writer, index=False, sheet_name='Folha de Ponto')
            
            dados_excel = output.getvalue()
            
            st.write("")
            st.download_button(
                label=f"📥 Baixar Planilha de {nome_busca} (.xlsx)", 
                data=dados_excel, 
                file_name=f"relatorio_ponto_{nome_busca.replace(' ', '_')}.xlsx", 
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True
            )
