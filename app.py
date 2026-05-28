import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
from io import BytesIO
from supabase import create_client, Client
import re

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
        res = supabase.table("registro_ponto").select("nome_completo, horario_entrada, saida_almoco, retorno_almoco, horario_saida, data, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida, data_registro_horario_entrada, data_saida_almoco, data_retorno_almoco, data_horario_saida").eq("exibir_no_log", True).order("data", desc=True).execute()
        return res.data
        
    elif operacao == "buscar_relatorio":
        res = supabase.table("registro_ponto").select("data, horario_entrada, saida_almoco, retorno_almoco, horario_saida, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida").eq("email", email).gte("data", str(data_filtro)).lte("data", str(data_fim)).order("data", desc=True).execute()
        return res.data

    elif operacao == "buscar_relatorio_geral":
        res = supabase.table("registro_ponto").select("nome_completo, email, data, horario_entrada, saida_almoco, retorno_almoco, horario_saida, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida").gte("data", str(data_filtro)).lte("data", str(data_fim)).order("nome_completo", desc=False).order("data", desc=True).execute()
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
        # Agrupa os dados pelo e-mail do funcionário para isolar as jornadas
        for email, group in df_geral.groupby("E-mail"):
            # Obtem o nome do funcionário baseado no grupo para dar título à aba
            nome_colaborador = group["Funcionário"].iloc[0]
            
            # Limpa caracteres inválidos ou muito longos que quebram abas do Excel (máx 31 caracteres)
            nome_aba = re.sub(r'[\\/*?:\[\]]', '', nome_colaborador)[:30]
            
            # Remove as colunas de controle do funcionário para que a aba fique limpa como a individual
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

# =====================================================================
# --- MENU: REGISTRO DE HORÁRIOS ---
# =====================================================================
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
                            if horario_final_gravacao < agora_br_sem_segundos:
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
                        # MAPEAMENTO DE GRAVAÇÃO DO SISTEMA
                        mapeamento_registro_sistema = {
                            "ENTRADA": "data_registro_horario_entrada",
                            "SAÍDA ALMOÇO": "data_saida_almoco",
                            "RETORNO ALMOÇO": "data_retorno_almoco",
                            "SAÍDA": "data_horario_saida" # Espaço mantido conforme sua tabela
                        }

                        dados_ponto = {
                            "email": user_email,
                            "nome_completo": user_name,
                            "data": str(hoje),
                            colunas_banco[opcao]: horario_final_gravacao.isoformat(),
                            # Grava dinamicamente na coluna de auditoria correspondente ao menu aberto
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

        # Dicionário interno para mapear o fundo correto baseado no label da ação
        cores_background = {
            "Entrou": "rgba(40, 167, 69, 0.15)",       # VERDE suave
            "saiu para o almoço": "rgba(255, 193, 7, 0.15)", # AMARELO suave
            "retornou do almoço": "rgba(0, 123, 255, 0.15)", # AZUL suave
            "Saiu": "rgba(255, 106, 106, 0.15)"        # LARANJA suave
        }

        # VÍNCULOS ESTRITOS PARA EXIBIÇÃO: Mapeia a coluna do ponto do banco com a sua coluna de auditoria
        mapeamento_colunas_registro = {
            "horario_entrada": "data_registro_horario_entrada",
            "saida_almoco": "data_saida_almoco",
            "retorno_almoco": "data_retorno_almoco",
            "horario_saida": "data_horario_saida" # Espaço mantido estritamente conforme o banco
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
                    
                    # Identifica qual é a coluna de auditoria do sistema vinculada a esta batida
                    coluna_registro = mapeamento_colunas_registro.get(coluna)
                    data_registro_banco = item.get(coluna_registro)
                    
                    # REGRA SOLICITADA: Puxa única e exclusivamente o horário da respectiva coluna de auditoria
                    if data_registro_banco and str(data_registro_banco).strip() != "":
                        dt_sistema = datetime.fromisoformat(str(data_registro_banco)).astimezone(fuso_br)
                        hora_sistema_gravada = dt_sistema.strftime("%H:%M:%S")
                    else:
                        # Se a coluna de auditoria estiver nula no banco, exibe estritamente os traços
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
                    
                    # Captura a cor de fundo com base na ação atual
                    cor_fundo = cores_background.get(evento["acao"], "transparent")
                    
                    html_justificativa = ""
                    if evento.get("justificativa"):
                        html_justificativa = (
                            f'<br><span style="color: #6c757d; font-size: 0.9em; font-style: italic; '
                            f'padding-left: 28px; display: inline-block; margin-top: 4px;">'
                            f'💬 Justificativa: {evento["justificativa"]}'
                            f'</span>'
                        )
                    
                    # Aplicado o background dinâmico, padding interno e cantos arredondados (border-radius)
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
            
# --- MENU: RELATÓRIO ---
elif opcao == "RELATÓRIO":
    st.title("📊 Espelho de Ponto Pessoal")
    email_busca = user_email
    nome_busca = user_name
    
    cargo_usuario = "Colaborador"
    try:
        dados_usuario_logado = supabase.table("usuarios_ponto").select("cargo").eq("email", user_email).execute()
        if dados_usuario_logado.data:
            cargo_usuario = dados_usuario_logado.data[0].get("cargo", "Colaborador")
    except Exception:
        st.error("Erro ao verificar nível de acesso do usuário.")

    lista_todos_usuarios = []
    
    if cargo_usuario == "Supervisor":
        st.markdown("### 🔑 Painel de Gestão (Supervisor)")
        try:
            usuarios_banco = supabase.table("usuarios_ponto").select("email, nome").execute()
            if usuarios_banco.data:
                lista_todos_usuarios = usuarios_banco.data
                opcoes_usuarios = {f"{u['nome']} ({u['email']})": u for u in usuarios_banco.data}
                usuario_selecionado_str = st.selectbox("Selecione o colaborador que deseja consultar na tela:", options=list(opcoes_usuarios.keys()))
                colaborador_escolhido = opcoes_usuarios[usuario_selecionado_str]
                email_busca = colaborador_escolhido["email"]
                nome_busca = colaborador_escolhido["nome"]
        except Exception:
            st.error("Erro ao carregar a lista de funcionários.")
            
    st.caption(f"Filtro e exportação de folhas e históricos para: **{nome_busca}**")
    
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("🗓️ Data Inicial", hoje - timedelta(days=7), format="DD/MM/YYYY")
    with col2:
        data_fim = st.date_input("🗓️ Data Final", hoje, format="DD/MM/YYYY")
        
    st.write("---")
    
    if data_inicio > data_fim:
        st.error("Erro: A data inicial não pode ser maior que a data final.")
    else:
        def processar_dados_ponto(dados, incluir_usuario_info=False, formatar_data_br=False):
            if not dados:
                colunas_vazias = []
                if incluir_usuario_info:
                    colunas_vazias.extend(["Funcionário", "E-mail"])
                colunas_vazias.extend([
                    "Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", 
                    "Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída"
                ])
                return pd.DataFrame(columns=colunas_vazias)
                
            df_temp = pd.DataFrame(dados)
            
            mapeamento_colunas = {
                "data": "Data",
                "horario_entrada": "Entrada",
                "saida_almoco": "Saída Almoço",
                "retorno_almoco": "Retorno Almoço",
                "horario_saida": "Saída",
                "justificativa_entrada": "Justificativa Entrada",
                "justificativa_saida_almoco": "Justificativa Saída Almoço",
                "justificativa_retorno_almoco": "Justificativa Retorno Almoço",
                "justificativa_saida": "Justificativa Saída"
            }
            
            if incluir_usuario_info:
                mapeamento_colunas["nome_completo"] = "Funcionário"
                mapeamento_colunas["email"] = "E-mail"
            
            df_temp = df_temp.rename(columns=mapeamento_colunas)
            
            for col_esperada in mapeamento_colunas.values():
                if col_esperada not in df_temp.columns:
                    df_temp[col_esperada] = None

            ordem_colunas = []
            if incluir_usuario_info:
                ordem_colunas.extend(["Funcionário", "E-mail"])
            ordem_colunas.extend([
                "Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", 
                "Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída"
            ])
            df_temp = df_temp[ordem_colunas]
            
            def formata_hora(x):
                if not x: return "-"
                try: return datetime.fromisoformat(x).astimezone(fuso_br).strftime('%H:%M:%S')
                except: return "-"

            for c in ["Entrada", "Saída Almoço", "Retorno Almoço", "Saída"]:
                df_temp[c] = df_temp[c].apply(formata_hora)
                
            colunas_justificativas = ["Justificativa Entrada", "Justificativa Saída Almoço", "Justificativa Retorno Almoço", "Justificativa Saída"]
            for c_just in colunas_justificativas:
                df_temp[c_just] = df_temp[c_just].fillna("-").replace("", "-")
            
            if formatar_data_br:
                try:
                    df_temp["Data"] = pd.to_datetime(df_temp["Data"]).dt.strftime('%d/%m/%Y')
                except Exception:
                    pass
                
            return df_temp

        dados_relatorio = executar_query_supabase("buscar_relatorio", email=email_busca, data_filtro=data_inicio, data_fim=data_fim)
        
        # --- ZONA DE EXPORTAÇÃO EXCEL ---
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            if dados_relatorio:
                df_excel_individual = processar_dados_ponto(dados_relatorio, incluir_usuario_info=False, formatar_data_br=True)
                excel_individual_bytes = converter_para_excel_individual(df_excel_individual)
                
                st.download_button(
                    label=f"📥 Baixar Excel de {nome_busca.split()[0]}",
                    data=excel_individual_bytes,
                    file_name=f"ponto_{nome_busca.replace(' ', '_').lower()}_{data_inicio}_a_{data_fim}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.button(f"📥 Baixar Excel de {nome_busca.split()[0]}", disabled=True, use_container_width=True)
                
        with col_exp2:
            if cargo_usuario == "Supervisor":
                dados_gerais = executar_query_supabase("buscar_relatorio_geral", data_filtro=data_inicio, data_fim=data_fim)
                if dados_gerais:
                    df_excel_geral = processar_dados_ponto(dados_gerais, incluir_usuario_info=True, formatar_data_br=True)
                    excel_geral_bytes = converter_para_excel_multiaba(df_excel_geral)
                    
                    st.download_button(
                        label="📥 Baixar Excel de TODOS Funcionários",
                        data=excel_geral_bytes,
                        file_name=f"ponto_geral_equipe_{data_inicio}_a_{data_fim}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary"
                    )
                else:
                    st.button("📥 Baixar Excel de TODOS Funcionários", disabled=True, use_container_width=True)
            else:
                st.empty()
                
        st.write("")
        
        # --- EXIBIÇÃO EM TELA / EDIÇÃO ---
        if not dados_relatorio:
            st.info(f"Não foram encontrados registros de ponto para {nome_busca} no período selecionado.")
        else:
            df = processar_dados_ponto(dados_relatorio, incluir_usuario_info=False)
            df_tela = df.copy()
            df_tela["Data"] = pd.to_datetime(df_tela["Data"]).dt.strftime('%d/%m/%Y')
            
            if cargo_usuario == "Supervisor":
                st.markdown("📝 **Modo Edição Ativado:** Dê um duplo clique em qualquer célula para alterar.")
                df_editado = st.data_editor(df_tela, use_container_width=True, disabled=["Data"], key="editor_pontos_supervisor")
                
                if st.button("💾 Confirmar Alterações e Salvar no Banco de Dados", use_container_width=True, type="secondary"):
                    colunas_reversas = {
                        "Entrada": "horario_entrada", 
                        "Saída Almoço": "saida_almoco",
                        "Retorno Almoço": "retorno_almoco", 
                        "Saída": "horario_saida",
                        "Justificativa Entrada": "justificativa_entrada",
                        "Justificativa Saída Almoço": "justificativa_saida_almoco",
                        "Justificativa Retorno Almoço": "justificativa_retorno_almoco",
                        "Justificativa Saída": "justificativa_saida"
                    }
                    
                    with st.spinner("Salvando alterações..."):
                        for idx, row in df_editado.iterrows():
                            data_original = dados_relatorio[idx]["data"]
                            dados_update = {"email": email_busca, "nome_completo": nome_busca, "data": data_original}
                            
                            for col_tela, col_banco in colunas_reversas.items():
                                valor_celula = str(row[col_tela]).strip()
                                if col_banco in ["justificativa_entrada", "justificativa_saida_almoco", "justificativa_retorno_almoco", "justificativa_saida"]:
                                    dados_update[col_banco] = None if valor_celula == "-" else valor_celula
                                else:
                                    if valor_celula == "-":
                                        dados_update[col_banco] = None
                                    else:
                                        try:
                                            if len(valor_celula) == 5:
                                                hora_objeto = datetime.strptime(valor_celula, "%H:%M").time()
                                            else:
                                                hora_objeto = datetime.strptime(valor_celula, "%H:%M:%S").time()
                                                
                                            data_objeto = datetime.strptime(data_original, "%Y-%m-%d").date()
                                            dt_combinado = datetime.combine(data_objeto, hora_objeto).replace(tzinfo=fuso_br)
                                            
                                            if dt_combinado > agora_br:
                                                st.error(f"🛑 Horário '{valor_celula}' no dia {data_original} está no futuro. Cancelado.")
                                            else:
                                                dados_update[col_banco] = dt_combinado.isoformat()
                                        except Exception:
                                            pass
                            
                            executar_query_supabase("salvar_ponto", data_dict=dados_update)
                        st.success("Alterações salvas com sucesso!")
                        st.rerun()
            else:
                st.dataframe(df_tela, use_container_width=True)
