import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from supabase import create_client, Client

# --- FUSO HORÁRIO DE BRASÍLIA ---
fuso_br = ZoneInfo("America/Sao_Paulo")

# --- CONEXÕES E CREDENCIAIS ---
URL_SUPABASE = os.environ.get("SUPABASE_URL", "https://cgulxnvzoclmyckqxguj.supabase.co")
KEY_SUPABASE = os.environ.get("SUPABASE_KEY", "sb_publishable_V1u7wkR3Ng33jYV5OiFOGA_CyTopglE")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "renan.veloso@multprocessing.com.br")
SMTP_SENHA = os.environ.get("SMTP_SENHA", "bfgd hksy wvdm yurv")

supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)

def enviar_email_alerta(destinatario, nome_colaborador, horario_entrada, horario_fim_jornada):
    """Envia o e-mail de lembrete utilizando o SMTP do Gmail."""
    assunto = f"⏱️ {nome_colaborador}, sua jornada de trabalho está terminando!"
    
    corpo_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e9ecef; padding: 20px; border-radius: 8px;">
                <h2 style="color: #4D96FF;">Olá, {nome_colaborador}! ⏱️</h2>
                <p>Identificamos que você registrou sua entrada hoje às <b>{horario_entrada}</b>.</p>
                <p style="font-size: 1.1em;">Sua jornada padrão de 9 horas (com intervalos inclusos) encerra às <span style="color: #ff4d4d; font-weight: bold;">{horario_fim_jornada}</span>.</p>
                
                <div style="background-color: #f8f9fa; border-left: 4px solid #4D96FF; padding: 15px; margin: 20px 0; border-radius: 4px;">
                    <p style="margin: 0; font-weight: bold;">⚠️ Lembretes Importantes:</p>
                    <ul style="margin-top: 5px; margin-bottom: 0;">
                        <li>Não se esqueça de <b>bater o seu ponto de saída</b> no sistema eletrônico.</li>
                        <li>Caso precise realizar <b>hora extra</b>, lembre-se de avisar previamente o seu <b>gestor de célula</b>.</li>
                    </ul>
                </div>
                
                <p style="font-size: 0.9em; color: #6c757d;">Este é um e-mail automático gerado pelo Sistema de Ponto Eletrônico.</p>
            </div>
        </body>
    </html>
    """
    
    msg = MIMEText(corpo_html, 'html', 'utf-8')
    msg['Subject'] = assunto
    msg['From'] = SMTP_EMAIL
    msg['To'] = destinatario

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_SENHA)
            server.send_message(msg)
        print(f"✅ Alerta de fim de jornada enviado para {destinatario}")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail para {destinatario}: {e}")

def verificar_e_disparar_alertas():
    hoje_str = datetime.now(fuso_br).strftime("%Y-%m-%d")
    agora = datetime.now(fuso_br)

    print(f"[{agora.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando checagem de jornadas...")

    # 1. Busca os registros do Supabase criados hoje que já tenham Entrada, mas ainda NÃO tenham Saída marcada
    try:
        res = supabase.table("registro_ponto")\
            .select("email, nome_completo, horario_entrada, alerta_enviado")\
            .eq("data", hoje_str)\
            .not_.is_("horario_entrada", "null")\
            .is_("horario_saida", "null")\
            .execute()
        
        registros = res.data
    except Exception as e:
        print(f"❌ Erro ao consultar Supabase: {e}")
        return

    for registro in registros:
        # Se um alerta já foi enviado hoje para essa linha, ignora para não floodar a caixa do usuário
        if registro.get("alerta_enviado") == True:
            continue
            
        entrada_iso = registro["horario_entrada"]
        try:
            # Converte a string ISO do banco de volta para datetime com fuso BR
            dt_entrada = datetime.fromisoformat(entrada_iso).astimezone(fuso_br)
        except ValueError:
            continue

        # Calcula o momento exato em que a jornada de 9 horas se completa
        dt_fim_jornada = dt_entrada + timedelta(hours=9)
        
        # Define uma janela de aviso (Ex: Faltando 15 minutos para acabar a jornada até o momento exato do fim)
        momento_alerta_inicio = dt_fim_jornada - timedelta(minutes=15)

        # Se o horário do servidor estiver dentro da janela de aviso de 15 minutos
        if momento_alerta_inicio <= agora <= dt_fim_jornada:
            email_usuario = registro["email"]
            nome_usuario = registro["nome_completo"]
            
            str_entrada = dt_entrada.strftime("%H:%M")
            str_fim = dt_fim_jornada.strftime("%H:%M")

            # Dispara o e-mail
            enviar_email_alerta(email_usuario, nome_usuario, str_entrada, str_fim)

            # Atualiza o banco marcando que o alerta já foi enviado (evita duplicidade no próximo loop)
            try:
                supabase.table("registro_ponto")\
                    .update({"alerta_enviado": True})\
                    .eq("email", email_usuario)\
                    .eq("data", hoje_str)\
                    .execute()
            except Exception as e:
                print(f"⚠️ Erro ao atualizar status de alerta no banco para {email_usuario}: {e}")

if __name__ == "__main__":
    verificar_e_disparar_alertas()
