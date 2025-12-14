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
ARQUIVO_SAIDA = "Longitude_SP.xml"
URL_BUSCA = "https://www.longitude.com.br/imoveis"

# Filtro de imagens (para não pegar ícones e avatares)
BLACKLIST_IMAGENS = [
    'icon', 'logo', 'svg', 'facebook', 'instagram', 'whatsapp', 'banner', 
    'user', 'pin', 'check', 'arrow', 'mobile', 'desktop', 'google', 
    'transparencia', 'selo', 'play', 'video', 'tour-virtual', 'maps'
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
        btn = driver.find_element(By.XPATH, "//button[contains(., 'Aceitar') or contains(., 'Concordo') or contains(., 'Fechar')]")
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(1)
    except: pass

def coletar_links_reais(driver):
    print(f">>> ACESSANDO: {URL_BUSCA}")
    driver.get(URL_BUSCA)
    time.sleep(5)
    fechar_cookies(driver)

    print(">>> ROLANDO ATÉ O FIM (INFINITE SCROLL)...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    # Loop de rolagem
    while True:
        current = driver.execute_script("return window.pageYOffset;")
        target = last_height
        # Desce suavemente
        while current < target:
            current += 600
            driver.execute_script(f"window.scrollTo(0, {current});")
            time.sleep(0.1)
        
        time.sleep(3)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            # Tenta desbloquear caso tenha travado
            driver.execute_script("window.scrollBy(0, -300);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            if driver.execute_script("return document.body.scrollHeight") == last_height:
                print("   [i] Fim da página atingido.")
                break
        
        last_height = new_height

    # Extração dos links
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links = []
    
    tags_a = soup.find_all('a', href=True)
    print("\n>>> FILTRANDO LINKS DE IMÓVEIS...")
    
    for a in tags_a:
        href = a['href']
        # Filtro corrigido para o padrão: /imoveis/cidade/tipo/nome
        if '/imoveis/' in href:
            full_link = href if 'http' in href else f"https://www.longitude.com.br{href}"
            
            # Garante que não é a própria página de busca (conta as barras /)
            # Ex: /imoveis/sumare/apartamento/evo tem 4 ou 5 barras
            parts = full_link.split('/')
            if len(parts) >= 6 and full_link not in links:
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
        "titulo": "", "endereco": "", "cidade": "São Paulo", # Default SP, mas tentaremos extrair a cidade real
        "preco": "Sob Consulta", "status": "", "dorms": "", 
        "area": "", "descricao": "Consulte detalhes com a construtora.", 
        "imagens": [], "features": []
    }
    
    try:
        driver.get(url)
        # Tenta esperar um elemento chave
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        except: pass
        
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. Título
        # Tenta pegar do breadcrumb primeiro, pois o H1 pode ser slogan
        # Ex URL: .../sumare/apartamento/evo -> Título: Evo
        try:
            parts = url.strip('/').split('/')
            nome_url = parts[-1].replace('-', ' ').title()
            dados['titulo'] = nome_url
        except:
            if soup.title: dados['titulo'] = soup.title.string.split('-')[0].strip()

        # 2. Localização (Baseado no seu HTML)
        # <i class="icon icon-location"></i> Sumaré
        icon_loc = soup.find('i', class_='icon-location')
        if icon_loc and icon_loc.parent:
            dados['endereco'] = limpar_texto(icon_loc.parent.get_text())
            dados['cidade'] = dados['endereco'] # Geralmente é a cidade que aparece ali

        # 3. Dormitórios e Vagas
        # <i class="icon icon-dorms"></i> 2 dorms.
        list_items = soup.find_all('li', class_='nav-item')
        for li in list_items:
            txt = limpar_texto(li.get_text())
            if 'dorm' in txt.lower(): dados['dorms'] = txt
            if 'Lançamento' in txt or 'Obras' in txt or 'Pronto' in txt:
                dados['status'] = txt

        # 4. Preço
        # <span class="price"><strong class="fw-bold">R$ 896,06</strong>
        span_price = soup.find('span', class_='price')
        if span_price:
            dados['preco'] = limpar_texto(span_price.get_text())

        # 5. Diferenciais (Features)
        # <span class="icon ... icon-differential-..."></span> <strong>...</strong>
        divs_diff = soup.find_all('div', class_='d-flex flex-wrap gap-3')
        for div in divs_diff:
            strongs = div.find_all('strong')
            for s in strongs:
                t = limpar_texto(s.get_text())
                if t and t not in dados['features']:
                    dados['features'].append(t)

        # 6. Lazer (Recreation Attributes)
        # <section class="recreation-atributtes"> ... <div class="fs-5 ...">
        section_lazer = soup.find('section', class_='recreation-atributtes')
        if section_lazer:
            itens = section_lazer.find_all('div', class_=lambda x: x and 'fs-5' in x)
            for item in itens:
                t = limpar_texto(item.get_text())
                if t and t not in dados['features']:
                    dados['features'].append(t)

        # 7. Imagens (Fancybox e Swiper)
        # Prioriza links de galeria (alta qualidade)
        links_gal = soup.find_all('a', attrs={'data-fancybox': True})
        for a in links_gal:
            src = a.get('href')
            if validar_imagem(src):
                if src not in dados['imagens']:
                    dados['imagens'].append(src)
        
        # Se não achou galeria, pega imagens normais
        if not dados['imagens']:
            imgs = soup.find_all('img')
            for img in imgs:
                src = img.get('src') or img.get('data-src')
                if validar_imagem(src):
                    if src not in dados['imagens']:
                        dados['imagens'].append(src)

    except Exception as e:
        print(f"   [!] Erro: {e}")
        return None

    return dados

def main():
    driver = setup_driver()
    root = ET.Element("listings")
    
    try:
        links = coletar_links_reais(driver)
        
        if not links:
            print("❌ 0 links encontrados. Verifique o padrão da URL.")
            return

        total = len(links)
        print(f"\n🚀 PROCESSANDO {total} IMÓVEIS...")

        for i, url in enumerate(links):
            print(f"[{i+1}/{total}] {url}")
            dados = extrair_dados_pagina(driver, url)
            
            if dados and dados['titulo']:
                item = ET.SubElement(root, "listing")
                ET.SubElement(item, "title").text = dados['titulo']
                ET.SubElement(item, "link").text = url
                ET.SubElement(item, "status").text = dados['status']
                ET.SubElement(item, "price").text = dados['preco']
                ET.SubElement(item, "address").text = dados['endereco']
                ET.SubElement(item, "city").text = dados['cidade']
                ET.SubElement(item, "bedrooms").text = dados['dorms']
                ET.SubElement(item, "description").text = dados['descricao']
                ET.SubElement(item, "date_scraped").text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                feats = ET.SubElement(item, "features")
                for f in dados['features']:
                    ET.SubElement(feats, "feature").text = f

                gal = ET.SubElement(item, "gallery")
                count_img = 0
                for img in dados['imagens']:
                    if count_img >= 15: break
                    ET.SubElement(gal, "image").text = img
                    count_img += 1
                
                print(f"   -> OK: {dados['titulo']} | Lazer: {len(dados['features'])}")
            else:
                print("   -> Erro na leitura.")

    except KeyboardInterrupt:
        print("\n🛑 Parando...")
    finally:
        driver.quit()
        if 'links' in locals() and len(links) > 0:
            xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")
            with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
                f.write(xml_str)
            print(f"\n✅ XML Salvo: {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    main()