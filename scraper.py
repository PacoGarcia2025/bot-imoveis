print(">>> O SCRIPT V6 (ANTI-CRASH & RESTART) COMEÇOU! <<<")

import time
import re
import os
import subprocess 
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- CONFIGURAÇÃO ---
ARQUIVO_SAIDA = "MRVsp.xml" 
ESTADO_ALVO = "sao-paulo"

def iniciar_driver():
    options = Options()
    # options.add_argument("--headless") # Tire o # para rodar invisível
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    # Estratégia 'eager': carrega assim que o HTML base estiver pronto (mais rápido)
    options.page_load_strategy = 'eager' 
    
    print("--- (Re)Iniciando navegador... ---")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver

def inicializar_arquivo_unico():
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        f.write("<imoveis>\n")
    print(f"Arquivo '{ARQUIVO_SAIDA}' (re)iniciado!")

def adicionar_ao_arquivo_unico(dados):
    if not dados: return 
    
    xml_content = "  <imovel>\n"
    for chave, valor in dados.items():
        if isinstance(valor, list):
            xml_content += f"    <{chave}>\n"
            for item in valor:
                item_limpo = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                xml_content += f"      <item>{item_limpo}</item>\n"
            xml_content += f"    </{chave}>\n"
        else:
            valor_limpo = str(valor).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            xml_content += f"    <{chave}>{valor_limpo}</{chave}>\n"
    xml_content += "  </imovel>\n"
    
    with open(ARQUIVO_SAIDA, "a", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"   -> Salvo no XML.")

def finalizar_arquivo_unico():
    try:
        with open(ARQUIVO_SAIDA, "a", encoding="utf-8") as f:
            f.write("</imoveis>")
        print(f"Arquivo finalizado.")
    except: pass

def atualizar_github():
    print("\n" + "="*40)
    print("UPLOAD GITHUB...")
    try:
        subprocess.run(["git", "add", ARQUIVO_SAIDA], check=True)
        mensagem = f"Auto update {time.strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", mensagem], check=True)
        subprocess.run(["git", "push"], check=True)
        print(">>> SUCESSO! GITHUB ATUALIZADO. <<<")
    except:
        print("Nada novo para enviar ou erro no Git.")

def buscar_links_do_estado(driver, estado):
    url_busca = f"https://www.mrv.com.br/imoveis/{estado}"
    print(f"\n>>> ACESSANDO LISTAGEM: {url_busca}")
    try: driver.get(url_busca)
    except: driver.refresh()
    time.sleep(5)
    
    try: driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
    except: pass

    print("--- Carregando lista (Scroll/Clique)... ---")
    erros = 0
    while True:
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            botao = driver.find_element(By.XPATH, "//button[contains(., 'Carregar') or contains(., 'Ver mais')]")
            if botao.is_displayed():
                driver.execute_script("arguments[0].click();", botao)
                time.sleep(3) 
                print(".", end="", flush=True)
                erros = 0
            else: break
        except: 
            break

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if f"/imoveis/{estado}/" in href and "mapa-do-site" not in href:
            if href.startswith('/'): href = "https://www.mrv.com.br" + href
            links.add(href)
    
    lista = list(links)
    print(f"\n>>> {len(lista)} IMÓVEIS ENCONTRADOS.")
    return lista

def extrair_dados_imovel(driver, url):
    # Tenta 2 vezes (Normal e Refresh)
    for tentativa in range(2):
        try:
            if tentativa == 0: driver.get(url)
            else: 
                print("   [Auto-F5] Recarregando...")
                driver.refresh()
            break
        except TimeoutException:
            if tentativa == 1: 
                print("   [Timeout] Pulei.")
                driver.execute_script("window.stop();")
                return None
        except Exception:
            return None # Erro de conexão grave, retorna None para reiniciar driver

    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    texto_pagina = soup.get_text(" | ") 

    dados = {
        'titulo': '', 'link': url, 'cidade': '', 'descricao': '', 
        'endereco': '', 'dormitorios': '', 'area_privativa': '', 
        'vagas': '', 'itens_lazer': [], 'galeria_fotos': [], 'galeria_plantas': []
    }

    try:
        partes = url.split('/')
        if ESTADO_ALVO in partes:
            dados['cidade'] = partes[partes.index(ESTADO_ALVO) + 1].replace('-', ' ').title()
    except: pass

    dados['titulo'] = url.split('/')[-1].replace('apartamentos-', '').replace('-', ' ').title()

    end = soup.find_all(['p', 'span', 'div'], string=lambda t: t and ('Rua' in t or 'Avenida' in t) and len(t) < 100)
    if end: 
        txt = re.sub(r'\s+', ' ', end[0].get_text()).strip()
        dados['endereco'] = txt

    dorms = re.search(r'(\d+\s*a\s*\d+|\d+)\s*quartos', texto_pagina, re.IGNORECASE)
    if dorms: dados['dormitorios'] = dorms.group(1)

    areas = re.findall(r'(\d{2,3}[.,]?\d{0,2})\s*m²', texto_pagina, re.IGNORECASE)
    validas = [float(a.replace(',', '.')) for a in areas if 20 < float(a.replace(',', '.')) < 200]
    if validas:
        mi, ma = min(validas), max(validas)
        dados['area_privativa'] = f"{mi} a {ma} m²".replace('.', ',') if mi != ma else f"{mi} m²".replace('.', ',')

    if "vaga" in texto_pagina.lower() or "garagem" in texto_pagina.lower():
        dados['vagas'] = "1"
        v = re.search(r'(\d+)\s*vaga', texto_pagina, re.IGNORECASE)
        if v: dados['vagas'] = v.group(1)

    lazer_list = ['Piscina', 'Churrasqueira', 'Playground', 'Pet Place', 'Salão de Festas', 'Bicicletário', 'Pomar', 'Fitness']
    dados['itens_lazer'] = [i for i in lazer_list if i.lower() in texto_pagina.lower()]

    paras = soup.find_all('p')
    longest = ""
    for p in paras:
        t = p.get_text(strip=True)
        if len(t) > len(longest) and "cookie" not in t.lower(): longest = t
    if len(longest) > 50: dados['descricao'] = longest

    fotos, plantas, seen = [], [], set()
    black = ['logo', 'icon', 'facebook', 'instagram', 'mia', 'home_work']
    for img in soup.find_all('img'):
        src = img.get('src')
        if not src or any(b in src.lower() for b in black): continue
        if src.startswith('//'): src = 'https:' + src
        elif src.startswith('/'): src = 'https://www.mrv.com.br' + src
        
        if ('mrv' in src or 'content' in src) and src not in seen:
            seen.add(src)
            if 'planta' in img.get('alt','').lower() or 'planta' in src:
                plantas.append(src)
            else:
                fotos.append(src)

    dados['galeria_fotos'] = fotos[:15]
    dados['galeria_plantas'] = plantas[:5]
    return dados

# --- BLOCO PRINCIPAL COM REINICIALIZAÇÃO DO DRIVER ---
if __name__ == "__main__":
    driver = iniciar_driver()
    
    try:
        inicializar_arquivo_unico()
        
        # Pega a lista de links
        links = buscar_links_do_estado(driver, ESTADO_ALVO)
        total = len(links)
        
        # Fecha driver inicial e abre um novo limpo para começar a extração
        driver.quit()
        driver = iniciar_driver()

        for i, link in enumerate(links):
            print(f"[{i+1}/{total}] Processando: {link} ...")
            
            # REGRA DO PIT STOP: A cada 20 imóveis, reinicia o navegador
            if i > 0 and i % 20 == 0:
                print("--- PIT STOP: Reiniciando navegador para limpar memória... ---")
                driver.quit()
                time.sleep(2)
                driver = iniciar_driver()
            
            try:
                dados = extrair_dados_imovel(driver, link)
                if dados:
                    adicionar_ao_arquivo_unico(dados)
                else:
                    # Se retornou None, pode ter sido crash. Reinicia por segurança.
                    raise Exception("Dados vazios/Crash")
                    
            except Exception as e:
                print(f"   !!! Erro de conexão ou Crash ({e}). Reiniciando Driver...")
                try:
                    driver.quit()
                except: pass
                time.sleep(2)
                driver = iniciar_driver()
                continue # Vai para o próximo imóvel

    except Exception as e:
        print(f"Erro Fatal Geral: {e}")
    finally:
        finalizar_arquivo_unico()
        try: driver.quit()
        except: pass
        atualizar_github()