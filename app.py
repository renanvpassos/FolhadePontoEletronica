import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
from io import BytesIO
import pytz
from supabase import create_client, Client

# ==============================================================================
# 1. CONFIGURAÇÕES INICIAIS E CONEXÃO COM O SUPABASE
# ==============================================================================
st.set_page_config(page_title="Sistema de Ponto Eletrônico", page_icon="⏱️", layout="wide")

SUPABASE_URL = "SUA_URL_DO_SUPABASE"
SUPABASE_KEY = "SUA_ANON_KEY_DO_SUPABASE"

@st.cache_resource
def conectar_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = conectar_supabase()
fuso_br = pytz.timezone("America/Sao_Paulo")
agora_br = datetime.now(fuso_br)
hoje = agora_br.date()

# Inicialização dos estados de sessão do Streamlit
if "connected" not in st.session_state:
    st.session_state["connected"] = False
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# ==============================================================================
# 2. FUNÇÕES CORE DE INFRAESTRUTURA E BANCO DE DADOS
# ==============================================================================
def executar_query_supabase(operacao: str, data_dict: dict = None, email: str = None, data_filtro = None, data_fim = None):
    try:
        if operacao == "salvar_ponto":
            res = supabase.table("registro_ponto").upsert(data_dict, on_conflict="email,data").execute()
            return res.data
        elif operacao == "buscar_relatorio":
            res = supabase.table("registro_ponto").select(
                "data, horario_entrada, saida_almoco, retorno_almoco, horario_saida, justificativa_entrada, justificativa_saida"
            ).eq("email", email).gte("data", str(data_filtro)).lte("data", str(data_fim)).order("data", desc=True).execute()
            return res.data
        elif operacao == "buscar_logs":
            res = supabase.table("registro_ponto").select(
                "nome_completo, horario_entrada, saida_almoco, retorno_almoco, horario_saida, data, justificativa_entrada, justificativa_saida"
            ).eq("exibir_no_log", True).order("data", desc=True).execute()
            return res.data
    except Exception as e:
        st.error(f"Erro na operação {operacao}: {e}")
        return None

# ==============================================================================
# 3. VERIFICAÇÃO DO LINK DE RECUPERAÇÃO DE SENHA (URL HASH)
# ==============================================================================
query_params = st.query_params
if "type" in query_params and query_params["type"] == "recovery":
    st.title("🔄 Criar Nova Senha")
    st.subheader("Defina seus novos dados de acesso")
    
    with st.form("form_nova_senha"):
        nova_senha = st.text_input("Nova Senha", type="password", help="Mínimo 6 caracteres")
        confirma_senha = st.text_input("Confirme a Nova Senha", type="password")
        botao_salvar_senha = st.form_submit_button("Atualizar e Entrar", use_container_width=True)
        
        if botao_salvar_senha:
            if len(nova_senha) < 6:
                st.error("A senha deve ter pelo menos 6 caracteres.")
            elif nova_senha != confirma_senha:
                st.error("As senhas digitadas não coincidem.")
            else:
                try:
                    supabase.auth.update_user({"password": nova_senha})
                    st.success("Senha alterada com sucesso!")
                    st.query_params.clear()
                    st.info("Sua senha foi atualizada. Faça login normalmente agora.")
                    st.rerun()
                except Exception as e:
                    st.error("Erro ao atualizar a senha. O link pode ter expirado.")
    st.stop()

# ==============================================================================
# 4. TELA DE ACESSO (LOGIN E CADASTRO) - SEGURANÇA NATIVA
# ==============================================================================
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
                try:
                    res = supabase.auth.sign_in_with_password({"email": email_login, "password": senha_login})
                    if res.user:
                        nome_usuario = res.user.user_metadata.get("nome", "Colaborador")
                        st.session_state["user_info"] = {"email": res.user.email, "name": nome_usuario}
                        st.session_state["connected"] = True
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                except Exception:
                    st.error("E-mail ou senha incorretos (ou conta ainda não confirmada no e-mail).")
            else:
                st.warning("Por favor, preencha todos os campos.")

        st.write("") 
        with st.expander("Esqueci minha senha"):
            st.caption("Insira seu e-mail cadastrado para receber as instruções de redefinição.")
            email_recuperacao = st.text_input("E-mail de Recuperação", key="email_recup")
            botao_recuperar = st.button("Enviar E-mail de Redefinição", use_container_width=True)
            
            if botao_recuperar:
                if not email_recuperacao.strip():
                    st.warning("Por favor, digite o seu e-mail.")
                else:
                    with st.spinner("Enviando link de recuperação..."):
                        try:
                            supabase.auth.reset_password_for_email(
                                email_recuperacao.strip(),
                                {"redirect_to": "http://localhost:8501"} # Mude para a URL do Streamlit Cloud em produção
                            )
                            st.success("🎯 Link enviado! Verifique sua caixa de entrada (e a pasta de Spam).")
                        except Exception:
                            st.error("Erro ao solicitar redefinição. Verifique se o e-mail está digitado corretamente.")

    with aba_cadastro:
        st.subheader("Criar Nova Conta")
        nome_cadastro = st.text_input("Nome Completo", key="cadastro_nome")
        email_cadastro = st.text_input("E-mail Corporativo", key="cadastro_email").strip().lower()
        senha_cadastro = st.text_input("Defina uma Senha", type="password", key="cadastro_senha", help="Mínimo 6 caracteres")
        
        if st.button("Cadastrar Conta", use_container_width=True):
            if nome_cadastro and email_cadastro and senha_cadastro:
                if len(senha_cadastro) < 6:
                    st.error("A senha deve conter no mínimo 6 caracteres.")
                else:
                    with st.spinner("Registrando credenciais seguras..."):
                        try:
                            res_auth = supabase.auth.sign_up({
                                "email": email_cadastro,
                                "password": senha_cadastro,
                                "options": {"data": {"nome": nome_cadastro}}
                            })
                            dados_perfil = {"email": email_cadastro, "nome": nome_cadastro, "cargo": "Colaborador"}
                            supabase.table("usuarios_ponto").insert(dados_perfil).execute()
                            st.success("🎉 Conta criada com sucesso! Verifique seu e-mail para confirmar o cadastro.")
                        except Exception:
                            st.error("Erro ao cadastrar: Verifique se este e-mail já não está em uso.")
            else:
                st.warning("Por favor, preencha todos os campos.")
    st.stop()

# ==============================================================================
# 5. ÁREA LOGADA DO SISTEMA (MENU PRINCIPAL)
# ==============================================================================
user_email = st.session_state["user_info"]["email"]
user_name = st.session_state["user_info"]["name"]

st.sidebar.title(f"👋 Olá, {user_name.split(' ')[0]}")
opcao = st.sidebar.radio("Navegação", ["BATER PONTO", "RELATÓRIO", "LOG", "SAIR"])

if opcao == "SAIR":
    supabase.auth.sign_out()
    st.session_state["connected"] = False
    st.session_state["user_info"] = None
    st.rerun()

# ==============================================================================
# MENU: BATER PONTO (Espaço para manter sua lógica atual de marcações)
# ==============================================================================
elif opcao == "BATER PONTO":
    st.title("⏱️ Registro de Ponto Ativo")
    st.write(f"Colaborador logado: **{user_name}** ({user_email})")
    st.info("Aqui fica o seu formulário padrão com os botões normais de bater ponto.")

# ==============================================================================
# MENU: RELATÓRIO (COM CARGOS, EDICAO DATA_EDITOR E MULTI-ABAS)
# ==============================================================================
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
        def processar_dados_ponto(dados):
            if not dados:
                return pd.DataFrame(columns=["Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", "Justificativa Entrada", "Justificativa Saída"])
            df_temp = pd.DataFrame(dados)
            df_temp.columns = ["Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída", "Justificativa Entrada", "Justificativa Saída"]
            
            def formata_hora(x):
                if not x: return "-"
                try: return datetime.fromisoformat(x).astimezone(fuso_br).strftime('%H:%M:%S')
                except: return "-"

            for c in ["Entrada", "Saída Almoço", "Retorno Almoço", "Saída"]:
                df_temp[c] = df_temp[c].apply(formata_hora)
            df_temp["Justificativa Entrada"] = df_temp["Justificativa Entrada"].fillna("-").replace("", "-")
            df_temp["Justificativa Saída"] = df_temp["Justificativa Saída"].fillna("-").replace("", "-")
            return df_temp

        dados_relatorio = executar_query_supabase("buscar_relatorio", email=email_busca, data_filtro=data_inicio, data_fim=data_fim)
        
        if not dados_relatorio:
            st.info(f"Não foram encontrados registros de ponto para {nome_busca} no período selecionado.")
        else:
            df = processar_dados_ponto(dados_relatorio)
            df_tela = df.copy()
            df_tela["Data"] = pd.to_datetime(df_tela["Data"]).dt.strftime('%d/%m/%Y')
            
            if cargo_usuario == "Supervisor":
                st.markdown("📝 **Modo Edição Ativado:** Dê um duplo clique em qualquer célula para alterar.")
                df_editado = st.data_editor(df_tela, use_container_width=True, disabled=["Data"], key="editor_pontos_supervisor")
                
                if st.button("💾 Confirmar Alterações e Salvar no Banco de Dados", use_container_width=True, type="primary"):
                    colunas_reversas = {
                        "Entrada": "horario_entrada", "Saída Almoço": "saida_almoco",
                        "Retorno Almoço": "retorno_almoco", "Saída": "horario_saida",
                        "Justificativa Entrada": "justificativa_entrada", "Justificativa Saída": "justificativa_saida"
                    }
                    
                    with st.spinner("Salvando alterações..."):
                        for idx, row in df_editado.iterrows():
                            data_original = dados_relatorio[idx]["data"]
                            dados_update = {"email": email_busca, "nome_completo": nome_busca, "data": data_original}
                            
                            for col_tela, col_banco in colunas_reversas.items():
                                valor_celula = str(row[col_tela]).strip()
                                if col_banco in ["justificativa_entrada", "justificativa_saida"]:
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
                                                st.stop()
                                                
                                            dados_update[col_banco] = dt_combinado.isoformat()
                                        except Exception:
                                            st.error(f"🛑 Erro no formato do horário '{valor_celula}'. Use HH:MM:SS.")
                                            st.stop()
                                            
                            executar_query_supabase("salvar_ponto", data_dict=dados_update)
                    st.success("Alterações integradas com sucesso!")
                    st.rerun()
            else:
                st.dataframe(df_tela, use_container_width=True)
            
            # Exportação individual (.xlsx)
            output_ind = BytesIO()
            df_excel_ind = df.copy()
            df_excel_ind["Data"] = pd.to_datetime(df_excel_ind["Data"]).dt.strftime('%d/%m/%Y')
            with pd.ExcelWriter(output_ind, engine='openpyxl') as writer:
                df_excel_ind.to_excel(writer, index=False, sheet_name='Folha de Ponto')
            
            st.download_button(label=f"📥 Baixar Planilha de {nome_busca} (.xlsx)", data=output_ind.getvalue(), file_name=f"ponto_{nome_busca.replace(' ', '_')}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

        if cargo_usuario == "Supervisor" and lista_todos_usuarios:
            st.write("---")
            st.markdown("##### 🗂️ Exportação Avançada")
            if st.button("📊 Gerar Relatório Consolidado de Todos os Funcionários", use_container_width=True):
                with st.spinner("Gerando abas..."):
                    output_geral = BytesIO()
                    with pd.ExcelWriter(output_geral, engine='openpyxl') as writer:
                        for colab in lista_todos_usuarios:
                            dados_c = executar_query_supabase("buscar_relatorio", email=colab["email"], data_filtro=data_inicio, data_fim=data_fim)
                            df_c = processar_dados_ponto(dados_c)
                            df_c["Data"] = pd.to_datetime(df_c["Data"]).dt.strftime('%d/%m/%Y')
                            nome_aba = (colab["nome"].split(" ")[0] + " " + (colab["nome"].split(" ")[-1] if len(colab["nome"].split(" ")) > 1 else ""))[:30]
                            df_c.to_excel(writer, index=False, sheet_name=nome_aba)
                    st.success("Planilha consolidada pronta!")
                    st.download_button(label="📥 Baixar Planilha Geral (.xlsx)", data=output_geral.getvalue(), file_name="relatorio_equipe.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

# ==============================================================================
# MENU: LOG (MURAL DE ATIVIDADES COLETANDO JUSTIFICATIVAS)
# ==============================================================================
elif opcao == "LOG":
    st.title("📢 Mural de Atividades")
    st.caption("Linha do tempo das batidas eletrônicas da equipe.")
    st.write("---")
    
    logs_banco = executar_query_supabase("buscar_logs")
    if not logs_banco:
        st.info("Nenhuma atividade registrada recente.")
    else:
        lista_eventos = []
        labels_acoes = {"horario_entrada": "🟢 ENTRADA", "saida_almoco": "🟡 ALMOÇO", "retorno_almoco": "🟠 RETORNO ALMOÇO", "horario_saida": "🔵 SAÍDA"}
        
        for item in logs_banco:
            nome = item["nome_completo"]
            dt_compara = datetime.strptime(item["data"], "%Y-%m-%d").strftime("%d/%m")
            for coluna, label in labels_acoes.items():
                valor_hora = item.get(coluna)
                if valor_hora:
                    dt_objeto = datetime.fromisoformat(valor_hora).astimezone(fuso_br)
                    just_texto = item["justificativa_entrada"] if coluna == "horario_entrada" else (item["justificativa_saida"] if coluna == "horario_saida" else None)
                    
                    lista_eventos.append({
                        "nome": nome, "data_str": dt_compara, "acao": label,
                        "hora_str": dt_objeto.strftime("%H:%M:%S"), "objeto_tempo": dt_objeto, "justificativa": just_texto
                    })
                    
        if lista_eventos:
            lista_eventos.sort(key=lambda x: x["objeto_tempo"])
            for ev in lista_eventos:
                html_log = f'<div style="padding: 10px; border-bottom: 1px solid #eee;">⏱️ <b>{ev["hora_str"]}</b> - <b>{ev["nome"]}</b> {ev["acao"]} <span style="float: right; color: gray;">📅 {ev["data_str"]}</span>'
                if ev["justificativa"] and ev["justificativa"] != "-":
                    html_log += f'<br><span style="color: #6c757d; font-style: italic; padding-left: 20px;">💬 Justificativa: {ev["justificativa"]}</span>'
                html_log += '</div>'
                st.markdown(html_log, unsafe_allow_html=True)
