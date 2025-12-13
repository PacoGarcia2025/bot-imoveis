import schedule
import time
import subprocess
import os
from datetime import datetime

# --- CONFIGURAÇÕES ---
PASTA_PROJETO = os.getcwd() # Pega a pasta atual
SCRIPTS = [
    "scraper_hm.py",
    # "scraper_mrv.py" # Descomente quando tiver o script da MRV aqui
]

def log(mensagem):
    """Função simples para mostrar hora e mensagem no terminal"""
    agora = datetime.now().strftime("%H:%M:%S")
    print(f"[{agora}] {mensagem}")

def rodar_git():
    """Envia as atualizações para o GitHub automaticamente"""
    try:
        log("📦 Iniciando upload para o GitHub...")
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Auto Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=False)
        subprocess.run(["git", "push"], check=True)
        log("✅ GitHub atualizado com sucesso!")
    except Exception as e:
        log(f"❌ Erro no Git: {e}")

def tarefa_principal():
    log("🚀 INICIANDO ROTINA DE SCRAPING...")
    
    for script in SCRIPTS:
        caminho_script = os.path.join(PASTA_PROJETO, script)
        
        if os.path.exists(caminho_script):
            log(f"--- Rodando {script} ---")
            # Executa o script e espera terminar
            try:
                subprocess.run(["python", script], check=True)
                log(f"✅ {script} finalizado.")
            except subprocess.CalledProcessError as e:
                log(f"❌ Erro ao rodar {script}: {e}")
        else:
            log(f"⚠️ Script não encontrado: {script}")

    # Depois de rodar todos os scrapers, sobe pro GitHub
    rodar_git()
    log("💤 Tarefa concluída. Aguardando próximo agendamento...")

# --- AGENDAMENTOS ---
# Aqui você define a frequência. Exemplos:

# Opção 1: Rodar a cada 4 horas
schedule.every(4).hours.do(tarefa_principal)

# Opção 2: Rodar todo dia em horário específico (ex: 09:00 e 17:00)
# schedule.every().day.at("09:00").do(tarefa_principal)
# schedule.every().day.at("17:00").do(tarefa_principal)

# Opção 3: Rodar a cada 10 minutos (bom para testar agora)
# schedule.every(10).minutes.do(tarefa_principal)

# --- EXECUÇÃO IMEDIATA (Teste ao abrir) ---
log("🤖 AGENDADOR INICIADO!")
tarefa_principal() # Roda uma vez assim que abre pra testar

# --- LOOP INFINITO ---
while True:
    schedule.run_pending()
    time.sleep(60) # Verifica a cada 1 minuto se tem tarefa