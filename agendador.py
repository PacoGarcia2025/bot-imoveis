import schedule
import time
import subprocess
import os
from datetime import datetime

# --- CONFIGURAÇÕES ---
PASTA_PROJETO = os.getcwd() 

# Lista de robôs que serão executados em sequência
# A ordem importa: se um falhar, o script tenta o próximo
SCRIPTS = [
    "scraper_hm.py",        # 1. HM Engenharia
    "scraper.py",           # 2. MRV
    "scraper_cury.py",      # 3. Cury Construtora
    "scraper_direcional.py",# 4. Direcional Engenharia
    "scraper_plano.py"      # 5. Plano & Plano (FINALIZADO!)
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
                # O timeout evita que um robô travado pare tudo (max 20 min por robô)
                subprocess.run(["python", script], check=True, timeout=1200)
                log(f"✅ {script} finalizado.")
            except subprocess.TimeoutExpired:
                log(f"⚠️ {script} demorou demais e foi pulado.")
            except subprocess.CalledProcessError as e:
                log(f"❌ Erro ao rodar {script}: {e}")
        else:
            log(f"⚠️ ARQUIVO NÃO ENCONTRADO: {script}")

    # Só sobe pro Git depois de tentar rodar todos
    rodar_git()
    log("💤 Ciclo concluído. Aguardando próximo agendamento...")

# --- AGENDAMENTOS ---
# Roda a cada 4 horas
schedule.every(4).hours.do(tarefa_principal)

# --- INÍCIO ---
log("🤖 SISTEMA DE MONITORAMENTO DE IMÓVEIS - ATIVO")
log(f"📋 Robôs na fila: {len(SCRIPTS)}")

# Executa uma vez agora para testar
tarefa_principal()

while True:
    schedule.run_pending()
    time.sleep(60)