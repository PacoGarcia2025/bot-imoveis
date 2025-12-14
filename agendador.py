import schedule
import time
import subprocess
import os
from datetime import datetime

# --- CONFIGURAÇÕES ---
PASTA_PROJETO = os.getcwd() 

# Lista de robôs que serão executados em sequência
SCRIPTS = [
    "scraper_hm.py",            # 1. HM Engenharia
    "scraper.py",               # 2. MRV
    "scraper_cury.py",          # 3. Cury Construtora
    "scraper_direcional.py",    # 4. Direcional
    "scraper_plano.py",         # 5. Plano & Plano
    "scraper_longitude.py",     # 6. Longitude
    "scraper_tegra_campinas.py" # 7. Tegra Campinas (NOVO!)
]

def log(mensagem):
    """Mostra hora e mensagem no terminal"""
    agora = datetime.now().strftime("%H:%M:%S")
    print(f"[{agora}] {mensagem}")

def rodar_git():
    """Envia as atualizações para o GitHub"""
    try:
        log("📦 Iniciando upload para o GitHub...")
        subprocess.run(["git", "add", "."], check=True)
        
        msg = f"Auto Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", msg], check=False)
        
        subprocess.run(["git", "push"], check=True)
        log("✅ GitHub atualizado com sucesso!")
    except Exception as e:
        log(f"❌ Erro no Git: {e}")

def tarefa_principal():
    log("🚀 INICIANDO ROTINA GERAL DE SCRAPING...")
    
    for script in SCRIPTS:
        caminho_script = os.path.join(PASTA_PROJETO, script)
        
        if os.path.exists(caminho_script):
            log(f"--- 🎬 Rodando {script} ---")
            try:
                # Timeout de 25 min por robô para evitar travamentos
                subprocess.run(["python", script], check=True, timeout=1500)
                log(f"✅ {script} finalizado.")
            except subprocess.TimeoutExpired:
                log(f"⚠️ {script} demorou demais e foi pulado.")
            except subprocess.CalledProcessError as e:
                log(f"❌ Erro ao rodar {script}: {e}")
        else:
            log(f"⚠️ ARQUIVO NÃO ENCONTRADO: {script}")

    # Só sobe pro Git no final de tudo
    rodar_git()
    log("💤 Ciclo concluído. Aguardando próximo agendamento...")

# --- AGENDAMENTOS ---
schedule.every(4).hours.do(tarefa_principal)

# --- INÍCIO ---
log(f"🤖 AGENDADOR ATIVO - {len(SCRIPTS)} CONSTRUTORAS NA FILA")
tarefa_principal() # Roda uma vez ao iniciar

while True:
    schedule.run_pending()
    time.sleep(60)