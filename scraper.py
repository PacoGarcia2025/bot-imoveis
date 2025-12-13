print(">>> O SCRIPT 'MRVsp' COMEÇOU! <<<")

import time
import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURAÇÃO DO NOME DO ARQUIVO ---
ARQUIVO_SAIDA = "MRVsp.xml" 
ESTADO_ALVO = "sao-paulo"

def iniciar_driver():
    options = Options()
    # Se quiser ocultar o navegador, tire o # da linha abaixo
    # options.add_argument("--headless") 
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    
    print("--- Iniciando navegador... ---")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def limpar_texto(texto):
    if not texto: return ""
    return re.sub(r'\s+', ' ', texto).strip()

# --- FUNÇÃO: CRIA O ARQUIVO E ABRE A TAG <IMOVEIS> ---
def inicializar_arquivo_unico():
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        f.write("<imoveis>\n")
    print(f"Arquivo '{ARQUIVO_SAIDA}' criado com sucesso!")

# --- FUNÇÃO: GRAVA UM IMÓVEL DENTRO DO ARQUIVO ---
def adicionar_ao_arquivo_unico(dados):
    xml_content = "  <imovel>\n"
    for chave, valor in dados.items():
        if isinstance(valor, list):
            xml_content += f"    <{chave}>\n"
            for item in valor:
                # Limpa caracteres que quebram XML (&, <, >)
                item_limpo = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                xml_content += f"      <item>{item_limpo}</item>\n"
            xml_content += f"    </{chave}>\n"
        else:
            valor_limpo = str(valor).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            xml_content += f"    <{chave}>{valor_limpo}</{chave}>\n"
    xml_content += "  </imovel>\n"
    
    # 'a' significa append (adicionar ao final)
    with open(ARQUIVO_SAIDA, "a", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"   -> Salvo em {ARQUIVO_SAIDA}")

# --- FUNÇÃO: FECHA A TAG </IMOVEIS> NO FINAL ---
def finalizar_arquivo_unico():
    try:
        with open(ARQUIVO_SAIDA, "a", encoding="utf-8") as f:
            f.write("</imoveis>")
        print(f"Arquivo '{ARQUIVO_SAIDA}' finalizado corretamente.")
    except:
        print("Erro ao finalizar arquivo.")

# --- FUNÇÃO: BUSCAR LINKS (COM CLIQUE) ---
def buscar_links_do_estado(driver, estado):
    url_busca = f"https://www.mrv.com.br/imoveis/{estado}"
    print(f"\n>>> ACESSANDO: {url_busca}")
    driver.get(url_busca)
    time.sleep(5)
    
    try:
        driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
    except: pass

    print("--- Buscando imóveis (Carregando lista completa)... ---")
    
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        try:
            botao = driver.find_element(By.XPATH, "//button[contains(., 'Carregar') or contains(., 'Ver mais')]")
            if botao.is_displayed():
                driver.execute_script("arguments[0].click();", botao)
                time.sleep(4) 
                print(".", end="", flush=True)
            else:
                break
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
    print(f"\n>>> SUCESSO! {len(lista)} IMÓVEIS ENCONTRADOS.")
    return lista

# --- FUNÇÃO: EXTRAIR DADOS ---
def extrair_dados_imovel(driver, url):
    driver.get(url)
    time.sleep(3)
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
    if end: dados['endereco'] = limpar_texto(end[0].get_text())

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
        alt = img.get('alt', '').lower()
        if not src or any(b in src.lower() for b in black): continue
        if src.startswith('//'): src = 'https:' + src
        elif src.startswith('/'): src = 'https://www.mrv.com.br' + src
        
        if ('mrv' in src or 'content' in src) and src not in seen:
            seen.add(src)
            if 'planta' in alt or 'planta' in src or 'implantacao' in alt:
                plantas.append(src)
            else:
                fotos.append(src)

    dados['galeria_fotos'] = fotos[:15]
    dados['galeria_plantas'] = plantas[:5]
    return dados

# --- EXECUÇÃO ---
if __name__ == "__main__":
    driver = iniciar_driver()
    
    try:
        inicializar_arquivo_unico()
        links = buscar_links_do_estado(driver, ESTADO_ALVO)
        
        total = len(links)
        for i, link in enumerate(links):
            print(f"[{i+1}/{total}] Processando: {link} ...")
            try:
                dados = extrair_dados_imovel(driver, link)
                adicionar_ao_arquivo_unico(dados)
            except Exception as e:
                print(f"   !!! Erro: {e}")
                continue
                
    except Exception as e:
        print(f"Erro fatal: {e}")
    finally:
        finalizar_arquivo_unico()
        driver.quit()
        print(f"\n>>> PROCESSO CONCLUÍDO! Verifique o arquivo '{ARQUIVO_SAIDA}'.")