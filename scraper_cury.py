import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re
import datetime

# --- CONFIGURAÇÕES ---
ARQUIVO_SAIDA = "Cury_SP.xml"
URL_SITEMAP = "https://www.cury.net/sitemap.xml"

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--log-level=3")
    options.add_argument("--start-maximized")
    # options.add_argument("--headless") # Se quiser rodar sem abrir janela, tire o #
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def pegar_links_sitemap():
    print(">>> BAIXANDO LISTA DE IMÓVEIS (SITEMAP)...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(URL_SITEMAP, headers=headers)
        root = ET.fromstring(resp.content)
        ns = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = root.findall(".//sitemap:loc", ns) or root.findall(".//loc")
        
        links = []
        for url in urls:
            u = url.text
            if '/imovel/' in u and '/SP/' in u:
                links.append(u)
        
        links = list(set(links))
        print(f">>> ENCONTRADOS {len(links)} IMÓVEIS EM SP.")
        return links
    except Exception as e:
        print(f"Erro no sitemap: {e}")
        return []

def limpar_texto(texto):
    if not texto: return ""
    return " ".join(texto.split())

def extrair_dados_pagina(driver, url):
    dados = {
        "titulo": "", "endereco": "", "bairro": "", "cidade": "São Paulo",
        "preco": "Sob Consulta", "dorms": "", "area": "", 
        "status": "", "descricao": "", "imagens": [], "features": [], "plantas": []
    }
    
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. Título (Pega da classe especifica que vimos no HTML)
        h3_nome = soup.find('h3', class_='name-imovel')
        if h3_nome:
            dados['titulo'] = limpar_texto(h3_nome.get_text())
        else:
            # Fallback
            dados['titulo'] = url.split('/')[-1].replace('-', ' ').title()

        # 2. Bairro (Pega da classe 'region')
        p_region = soup.find('p', class_='region')
        if p_region:
            dados['bairro'] = limpar_texto(p_region.get_text())

        # 3. Dormitórios (Dentro da div 'about-imovel')
        div_dorms = soup.find('div', class_='about-imovel')
        if div_dorms:
            p_dorms = div_dorms.find('p')
            if p_dorms:
                texto_dorms = limpar_texto(p_dorms.get_text())
                # Limpa virgulas extras (ex: "1 dorm. , 2 dorms.")
                dados['dorms'] = texto_dorms.replace(' ,', ' e')

        # 4. Status da Obra (Tag 'tag-house')
        div_status = soup.find('div', class_='tag-house')
        if div_status:
            dados['status'] = limpar_texto(div_status.get_text()).upper()

        # 5. Descrição (Dentro de 'product-description' ou 'about-properties')
        div_desc = soup.find(id='about-properties')
        if div_desc:
            # Pega o primeiro parágrafo significativo
            paras = div_desc.find_all('p')
            for p in paras:
                txt = limpar_texto(p.get_text())
                if len(txt) > 50: # Evita titulos curtos
                    dados['descricao'] = txt
                    break

        # 6. Diferenciais (Dentro da div id='diferentials')
        div_dif = soup.find(id='diferentials')
        if div_dif:
            # Pega todos os <p> dentro de <li>
            itens = div_dif.find_all('p')
            for item in itens:
                feat = limpar_texto(item.get_text())
                if feat and feat not in dados['features']:
                    dados['features'].append(feat)

        # 7. Imagens e Plantas (Slideshow Gallery)
        # O HTML mostra que as imagens HQ estão no 'href' dos links dentro de 'uk-slideshow-items'
        listas_slides = soup.find_all('ul', class_='uk-slideshow-items')
        
        for lista in listas_slides:
            links_img = lista.find_all('a', href=True)
            for link in links_img:
                src = link['href']
                if 'http' in src and ('.jpg' in src or '.jpeg' in src or '.png' in src):
                    if 'plants' in src or 'planta' in src:
                        if src not in dados['plantas']: dados['plantas'].append(src)
                    else:
                        if src not in dados['imagens']: dados['imagens'].append(src)

        # 8. Endereço (Busca genérica pois não tem classe especifica no trecho)
        texto_pag = soup.get_text(separator=" | ").lower()
        match_end = re.search(r'(?:rua|av\.|avenida|estrada|rodovia)[^|]+', texto_pag, re.IGNORECASE)
        if match_end:
            dados['endereco'] = limpar_texto(match_end.group(0))

        # 9. Preço (Busca genérica)
        match_preco = re.search(r'r\$\s*[\d.,]+', texto_pag)
        if match_preco:
            dados['preco'] = f"A partir de {match_preco.group(0).upper()}"

    except Exception as e:
        print(f"Erro ao extrair: {e}")

    return dados

def main():
    links = pegar_links_sitemap()
    if not links: return

    driver = setup_driver()
    
    root = ET.Element("listings")
    contador = 0
    total = len(links)

    try:
        for url in links:
            contador += 1
            print(f"[{contador}/{total}] ACESSANDO: {url}")
            
            try:
                driver.get(url)
                time.sleep(4) # Espera o site montar o HTML
                
                dados = extrair_dados_pagina(driver, url)
                
                item = ET.SubElement(root, "listing")
                ET.SubElement(item, "title").text = dados['titulo']
                ET.SubElement(item, "link").text = url
                ET.SubElement(item, "status").text = dados['status']
                ET.SubElement(item, "price").text = dados['preco']
                ET.SubElement(item, "address").text = dados['endereco']
                ET.SubElement(item, "neighborhood").text = dados['bairro']
                ET.SubElement(item, "bedrooms").text = dados['dorms']
                ET.SubElement(item, "description").text = dados['descricao']
                ET.SubElement(item, "date_scraped").text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Diferenciais Limpos
                feats = ET.SubElement(item, "features")
                for f in dados['features']: 
                    ET.SubElement(feats, "feature").text = f
                    
                # Galeria
                gal = ET.SubElement(item, "gallery")
                for img in dados['imagens']:
                    ET.SubElement(gal, "image").text = img
                    
                # Plantas separadas (Opcional, se quiser misturar jogue na galeria)
                plans = ET.SubElement(item, "floor_plans")
                for p in dados['plantas']:
                    ET.SubElement(plans, "plan_image").text = p
                
                print(f"   -> {dados['titulo']} | {len(dados['imagens'])} Fotos | Status: {dados['status']}")
                
            except Exception as e:
                print(f"   [!] Erro na URL: {e}")

    except KeyboardInterrupt:
        print("\n🛑 Interrompido. Salvando XML parcial...")
    finally:
        driver.quit()
        if contador > 0:
            xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")
            with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
                f.write(xml_str)
            print(f"\n✅ SUCESSO! Salvo em {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    main()