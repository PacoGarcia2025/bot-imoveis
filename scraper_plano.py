import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import re
import datetime

# --- CONFIGURAÇÕES ---
ARQUIVO_SAIDA = "Plano_SP.xml"
URL_BUSCA = "https://www.planoeplano.com.br/imoveis"

BLACKLIST_IMAGENS = [
    'icon', 'logo', 'svg', 'facebook', 'instagram', 'whatsapp', 'banner', 
    'user', 'pin', 'check', 'arrow', 'mobile', 'desktop', 'google', 
    'transparencia', 'selo', 'play', 'video'
]

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--log-level=3")
    options.add_argument("--start-maximized")
    # options.add_argument("--headless") 
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def fechar_cookies(driver):
    try:
        btn = driver.find_element(By.XPATH, "//button[contains(., 'Aceitar') or contains(., 'Concordo')]")
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(1)
    except: pass

def coletar_links_reais(driver):
    print(f">>> ACESSANDO: {URL_BUSCA}")
    driver.get(URL_BUSCA)
    time.sleep(5)
    fechar_cookies(driver)

    print(">>> ROLANDO SUAVEMENTE...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        current = driver.execute_script("return window.pageYOffset;")
        target = last_height
        while current < target:
            current += 600
            driver.execute_script(f"window.scrollTo(0, {current});")
            time.sleep(0.2) 
        
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            driver.execute_script("window.scrollBy(0, -300);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            if driver.execute_script("return document.body.scrollHeight") == last_height:
                print("   [i] Chegamos ao fim da página.")
                break
        
        last_height = new_height

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links = []
    tags_a = soup.find_all('a', href=True)
    
    print("\n>>> FILTRANDO LINKS VÁLIDOS...")
    for a in tags_a:
        href = a['href']
        if '/apartamentos/' in href:
            full_link = href if 'http' in href else f"https://www.planoeplano.com.br{href}"
            if full_link not in links and 'facebook' not in full_link:
                links.append(full_link)

    print(f">>> {len(links)} IMÓVEIS ENCONTRADOS.")
    return links

def limpar_texto(texto):
    if not texto: return ""
    return " ".join(texto.split())

def validar_imagem(src):
    if not src: return False
    s = src.lower()
    if 'http' not in s: return False
    if '.svg' in s: return False
    for termo in BLACKLIST_IMAGENS:
        if termo in s: return False
    return True

def extrair_dados_pagina(driver, url):
    dados = {
        "titulo": "", "endereco": "", "bairro": "", "cidade": "São Paulo",
        "preco": "Sob Consulta", "status": "", "dorms": "", 
        "area": "", "descricao": "Entre em contato para mais detalhes.", 
        "imagens": [], "features": []
    }
    
    try:
        driver.get(url)
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        except: return None

        time.sleep(2)
        
        # Tenta clicar no botão "Ver mais" do lazer se ele existir (para expandir itens ocultos)
        try:
            btn_ver_mais = driver.find_element(By.CSS_SELECTOR, ".recreation-atributtes .toggle-button")
            if btn_ver_mais.is_displayed():
                driver.execute_script("arguments[0].click();", btn_ver_mais)
                time.sleep(1)
        except:
            pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. Título
        h2 = soup.find(class_='enterprise-about--subtitle') or soup.find(class_='enterprise-about--title')
        if h2: dados['titulo'] = limpar_texto(h2.get_text())
        else: dados['titulo'] = soup.title.string.split('|')[0].strip()

        # 2. Status
        status_tag = soup.find(class_='text-construction')
        if status_tag: dados['status'] = limpar_texto(status_tag.get_text())

        # 3. Endereço
        addr_p = soup.find(class_='enterprise-about--address')
        if addr_p:
            span = addr_p.find('span', class_='fw-600') or addr_p
            dados['endereco'] = limpar_texto(span.get_text())

        # 4. Specs
        list_items = soup.find_all('li', class_='nav-item')
        for li in list_items:
            txt = limpar_texto(li.get_text()).lower()
            if 'dorm' in txt: dados['dorms'] = txt
            if 'm²' in txt: dados['area'] = txt

        # 5. Preço
        txt_geral = soup.get_text(separator=" | ")
        match_preco = re.search(r'R\$\s*[\d.,]+', txt_geral)
        if match_preco:
            dados['preco'] = f"A partir de {match_preco.group(0)}"
        
        # 6. Descrição (Ignorada propositalmente conforme pedido)
        # Mantém o texto padrão definido no início

        # 7. Imagens
        imgs = soup.find_all('img')
        for img in imgs:
            src = img.get('src') or img.get('data-src')
            if validar_imagem(src):
                if src not in dados['imagens']:
                    dados['imagens'].append(src)

        # 8. Features (Lógica baseada no seu HTML)
        # Procura a seção específica de atributos de recreação
        section_lazer = soup.find('section', class_='recreation-atributtes')
        if section_lazer:
            # Os itens estão em divs com a classe fs-5
            itens = section_lazer.find_all('div', class_='fs-5')
            for item in itens:
                txt_feature = limpar_texto(item.get_text())
                if txt_feature and txt_feature not in dados['features']:
                    dados['features'].append(txt_feature)
        
        # Fallback: Se não achou na classe específica, tenta lógica genérica
        if not dados['features']:
            sections = soup.find_all('section')
            for sec in sections:
                if 'diferenciais' in str(sec.get('class', [])).lower():
                    itens = sec.find_all(['h3', 'strong', 'p'])
                    for i in itens:
                        t = limpar_texto(i.get_text())
                        if 3 < len(t) < 30 and t not in dados['features']:
                            dados['features'].append(t)

    except Exception:
        return None

    return dados

def main():
    driver = setup_driver()
    root = ET.Element("listings")
    
    try:
        links = coletar_links_reais(driver)
        if not links: return

        total = len(links)
        print(f"\n🚀 PROCESSANDO {total} IMÓVEIS...")

        for i, url in enumerate(links):
            print(f"[{i+1}/{total}] {url}")
            dados = extrair_dados_pagina(driver, url)
            
            if dados and dados['titulo'] and "Não Encontrada" not in dados['titulo']:
                item = ET.SubElement(root, "listing")
                ET.SubElement(item, "title").text = dados['titulo']
                ET.SubElement(item, "link").text = url
                ET.SubElement(item, "status").text = dados['status']
                ET.SubElement(item, "price").text = dados['preco']
                ET.SubElement(item, "address").text = dados['endereco']
                ET.SubElement(item, "bedrooms").text = dados['dorms']
                ET.SubElement(item, "area").text = dados['area']
                ET.SubElement(item, "description").text = dados['descricao']
                ET.SubElement(item, "date_scraped").text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                feats = ET.SubElement(item, "features")
                for f in dados['features']: # Salva todos os diferenciais encontrados
                    ET.SubElement(feats, "feature").text = f

                gal = ET.SubElement(item, "gallery")
                count_img = 0
                for img in dados['imagens']:
                    if count_img >= 15: break
                    ET.SubElement(gal, "image").text = img
                    count_img += 1
                
                print(f"   -> OK: {dados['titulo']} | Lazer: {len(dados['features'])} itens")
            else:
                print("   -> Pulei.")

    except KeyboardInterrupt:
        print("\n🛑 Parando...")
    finally:
        driver.quit()
        if 'links' in locals() and len(links) > 0:
            xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")
            with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
                f.write(xml_str)
            print(f"\n✅ SUCESSO FINAL! XML Salvo: {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    main()