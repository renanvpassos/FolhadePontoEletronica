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
        res = supabase.table("registro_ponto").select("nome_completo, horario_entrada, saida_almoco, retorno_almoco, horario_saida, data, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida").eq("exibir_no_log", True).order("data", desc=True).execute()
        return res.data
        
    elif operacao == "buscar_relatorio":
        res = supabase.table("registro_ponto").select("data, horario_entrada, saida_almoco, retorno_almoco, horario_saida, justificativa_entrada, justificativa_saida_almoco, justificativa_retorno_almoco, justificativa_saida").eq("email", email).gte("data", str(data_filtro)).lte("data", str(data_fim)).order("data", desc=True).execute()
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
                                    justifycativa_obrigatoria = True
                                    
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
                        dados_ponto = {
                            "email": user_email,
                            "nome_completo": user_name,
                            "data": str(hoje),
                            colunas_banco[opcao]: horario_final_gravacao.isoformat()
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

# --- MENU: LOG ---
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
            "horario_entrada": "🟢 Entrou",
            "saida_almoco": "🟡 saiu para o almoço",
            "retorno_almoco": "🔵 retornou do almoço",
            "horario_saida": "🟠 Saiu"
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
                    
                    lista_eventos.append({
                        "nome": nome,
                        "data_str": dt_compara,
                        "acao": label,
                        "hora_str": dt_objeto.strftime("%H:%M:%S"),
                        "objeto_tempo": dt_objeto,
                        "justificativa": just_texto
                    })
        
        if not lista_eventos:
            st.info("Nenhum registro encontrado para o dia de hoje.")
        else:
            lista_eventos.sort(key=lambda x: x["objeto_tempo"], reverse=False)
            
            with st.container(height=450):
                for evento in lista_eventos:
                    hora_sistema = datetime.now().strftime("%H:%M:%S")
                    
                    html_log = (
                        f'<div class="card-log">'
                        f'⏱️ <b>{evento["hora_str"]}</b> - <b>{evento["nome"]}</b> {evento["acao"]}'
                        f'<span style="float: right; color: gray; font-size: 0.85em; text-align: right;">'
                        f'📅 {evento["data_str"]}<br>💻 {hora_sistema}'
                        f'</span>'
                        f'</div>'
                    )
                    
                    if evento["justificativa"]:
                        html_log += f'<br><span style="color: #6c757d; font-size: 0.9em; font-style: italic; padding-left: 24px; display: inline-block; margin-top: 5px;">💬 Justificativa: {evento["justificativa"]}</span>'
                    
                    html_log += '</div>'
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
                lista_todos_usuarios = sorted(usuarios_banco.data, key=lambda x: x['nome'].lower())
                opces_usuarios = {f"{u['nome']} ({u['email']})": u for u in lista_todos_usuarios}
                
                usuario_selecionado_str = st.selectbox(
                    "Selecione o colaborador que deseja consultar na tela:",
                    options=list(opces_usuarios.keys())
                )
                
                colaborador_escolhido = opces_usuarios[usuario_selecionado_str]
                email_busca = colaborador_escolhido["email"]
                nome_busca = colaborador_escolhido["nome"]
        except Exception:
            st.error("Erro ao carregar a lista de funcionários.")
            
    st.caption(f"Filtro e exportação de folhas e históricos para: **{nome_busca}**")
    st.write("")
    
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("🗓️ Data Inicial", hoje - timedelta(days=7), format="DD/MM/YYYY")
        with col2:
            data_fim = st.date_input("🗓️ Data Final", hoje, format="DD/MM/YYYY")
        
    st.write("---")
    
    if data_inicio > data_fim:
        st.error("Erro: A data inicial não pode ser maior que a data final.")
    else:
        def processar_dados_ponto(dados):
            colunas_completas = [
                "Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", 
                "Justificativa Entrada", "Justificativa Saída Almoço", 
                "Justificativa Retorno Almoço", "Justificativa Saída"
            ]
            
            if not dados:
                return pd.DataFrame(columns=colunas_completas)
                
            df_temp = pd.DataFrame(dados)
            df_temp.columns = colunas_completas
            
            def formata_hora(x):
                if not x: return "-"
                try:
                    return datetime.fromisoformat(x).astimezone(fuso_br).strftime('%H:%M:%S')
                except:
                    return "-"

            df_temp["Entrada"] = df_temp["Entrada"].apply(formata_hora)
            df_temp["Saída Almoço"] = df_temp["Saída Almoço"].apply(formata_hora)
            df_temp["Retorno Almoço"] = df_temp["Retorno Almoço"].apply(formata_hora)
            df_temp["Saída"] = df_temp["Saída"].apply(formata_hora)
            
            df_temp["Justificativa Entrada"] = df_temp["Justificativa Entrada"].fillna("-").replace("", "-")
            df_temp["Justificativa Saída Almoço"] = df_temp["Justificativa Saída Almoço"].fillna("-").replace("", "-")
            df_temp["Justificativa Retorno Almoço"] = df_temp["Justificativa Retorno Almoço"].fillna("-").replace("", "-")
            df_temp["Justificativa Saída"] = df_temp["Justificativa Saída"].fillna("-").replace("", "-")
            
            return df_temp

        dados_relatorio = executar_query_supabase("buscar_relatorio", email=email_busca, data_filtro=data_inicio, data_fim=data_fim)
        
        if not dados_relatorio:
            st.info(f"Não foram encontrados registros de ponto para {nome_busca} no período selecionado.")
        else:
            df = processar_dados_ponto(dados_relatorio)
            df_tela = df.copy()
            df_tela["Data"] = pd.to_datetime(df_tela["Data"]).dt.strftime('%d/%m/%Y')
            
            st.dataframe(df_tela, use_container_width=True)
