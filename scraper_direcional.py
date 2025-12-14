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
import json
import datetime

# --- CONFIGURAÇÕES ---
ARQUIVO_SAIDA = "Direcional_SP.xml"
URL_BUSCA_SP = "https://www.direcional.com.br/encontre-seu-apartamento/?estado=SP"

# Filtros para ignorar imagens inúteis
BLACKLIST_IMAGENS = [
    'button', 'icon', 'logo', 'theme', 'share', 'facebook', 'instagram', 
    'whatsapp', 'youtube', 'lazer-completo', 'espaco-gourmet', 'piscina-1',
    'qualidade-de-vida', 'opcoes-na-planta', 'espaco-kids', 'hospital', 
    'faculdade', 'proximities', 'selo', 'badge', 'shopping', 'escola',
    'check-blue', 'in-progress', 'complete-'
]

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--log-level=3")
    options.add_argument("--start-maximized")
    # options.add_argument("--headless") 
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def coletar_links_sp(driver):
    print(f">>> ACESSANDO FILTRO SP: {URL_BUSCA_SP}")
    driver.get(URL_BUSCA_SP)
    time.sleep(5)

    print(">>> EXPANDINDO A LISTA...")
    tentativas_sem_sucesso = 0
    
    while True:
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            btn_carregar = driver.find_element(By.XPATH, "//button[contains(., 'Carregar')] | //a[contains(., 'Carregar')] | //div[contains(., 'Carregar') and @role='button']")
            
            if btn_carregar.is_displayed():
                print("   [+] Clicando em 'Carregar mais'...")
                driver.execute_script("arguments[0].click();", btn_carregar)
                time.sleep(4)
                tentativas_sem_sucesso = 0
            else:
                break 
        except Exception:
            tentativas_sem_sucesso += 1
            if tentativas_sem_sucesso > 2:
                print("   [i] Fim da lista.")
                break
            time.sleep(1)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links_encontrados = []
    
    tags_a = soup.find_all('a', href=True)
    for a in tags_a:
        link = a['href']
        if '/empreendimentos/' in link and 'encontre-seu-apartamento' not in link:
            if link not in links_encontrados and 'facebook' not in link and '.jpg' not in link:
                links_encontrados.append(link)
    
    links_encontrados = [k for k in links_encontrados if len(k) > 40]
    print(f">>> ENCONTRADOS {len(links_encontrados)} IMÓVEIS.")
    return links_encontrados

def limpar_texto(texto):
    if not texto: return ""
    return " ".join(texto.split())

def validar_imagem(src):
    if not src: return False
    s = src.lower()
    if 'http' not in s: return False
    if not ('.jpg' in s or '.png' in s or '.jpeg' in s or '.webp' in s): return False
    
    for termo in BLACKLIST_IMAGENS:
        if termo in s: return False
    return True

def extrair_dados_imovel(driver, url):
    dados = {
        "titulo": "", "endereco": "", "cidade": "São Paulo", "estado": "SP",
        "preco": "Sob Consulta", "status": "", "dorms": "", 
        "area": "", "descricao": "", "imagens": [], "features": []
    }
    
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        time.sleep(3) # Tempo extra para carregar as features
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. Título
        h1 = soup.find('h1')
        if h1: dados['titulo'] = limpar_texto(h1.get_text())
        else: dados['titulo'] = soup.title.string.split('|')[0].strip()

        # 2. Status (NOVA LÓGICA BASEADA NO SEU CÓDIGO)
        # Procura o <p class="text-status"> que indica o estágio atual
        status_ativo = soup.find('p', class_='text-status')
        if status_ativo:
            dados['status'] = limpar_texto(status_ativo.get_text())
        else:
            # Fallback: Procura na lista inline se não achar a timeline
            status_items = soup.find_all('li', class_=lambda x: x and 'list-inline-item' in x)
            for item in status_items:
                txt = limpar_texto(item.get_text())
                if txt not in ['Direcional', 'Riva', 'Brazil', 'SP']:
                    dados['status'] = txt
                    break
        
        if not dados['status']: dados['status'] = "Em Vendas"

        # 3. Diferenciais (NOVA LÓGICA BASEADA NO SEU CÓDIGO)
        # Procura a seção .competitive-edges e pega os h3 dentro dela
        section_features = soup.find('section', class_='competitive-edges')
        if section_features:
            feats = section_features.find_all('h3')
            for f in feats:
                txt_feat = limpar_texto(f.get_text())
                if txt_feat and txt_feat not in dados['features']:
                    dados['features'].append(txt_feat)

        # 4. Endereço
        encontrou_end = False
        scripts_json = soup.find_all('script', type='application/ld+json')
        for script in scripts_json:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and '@graph' in data: data = data['graph']
                if isinstance(data, list):
                    for item in data:
                        if 'address' in item and isinstance(item['address'], dict):
                            addr = item['address']
                            rua = addr.get('streetAddress', '')
                            bairro = addr.get('addressLocality', '')
                            if rua or bairro:
                                dados['endereco'] = f"{rua} - {bairro}"
                                encontrou_end = True
            except: pass
        
        if not encontrou_end:
            texto_pag = soup.get_text(separator=" | ")
            match_end = re.search(r'(?:Rua|Av\.|Avenida|Estrada)[^|]+(?:SP|RJ|MG)', texto_pag, re.IGNORECASE)
            if match_end:
                dados['endereco'] = limpar_texto(match_end.group(0))

        # 5. Specs
        textos_specs = soup.find_all(string=re.compile(r'\d'))
        for t in textos_specs:
            txt = t.strip().lower()
            if ('quarto' in txt or 'dorm' in txt) and len(txt) < 20:
                dados['dorms'] = txt
            if 'm²' in txt and len(txt) < 15:
                dados['area'] = txt

        # 6. Imagens
        imgs = soup.find_all('img')
        for img in imgs:
            src = img.get('src', '') or img.get('data-src') or img.get('data-lazy-src')
            if validar_imagem(src):
                if src not in dados['imagens']:
                    dados['imagens'].append(src)

        # 7. Descrição
        desc = soup.find('div', class_=re.compile(r'content|description'))
        if desc:
            dados['descricao'] = limpar_texto(desc.get_text())[:400] + "..."

    except Exception as e:
        print(f"   [!] Erro na extração: {e}")

    return dados

def main():
    driver = setup_driver()
    root = ET.Element("listings")
    contador = 0

    try:
        links = coletar_links_sp(driver)
        
        if not links:
            print("❌ Nenhum link encontrado.")
            return

        total = len(links)
        print(f"\n🚀 PROCESSANDO {total} IMÓVEIS...")

        for url in links:
            contador += 1
            print(f"[{contador}/{total}] {url}")
            
            dados = extrair_dados_imovel(driver, url)
            
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
            
            # Adiciona as Features no XML
            feats = ET.SubElement(item, "features")
            for f in dados['features']:
                ET.SubElement(feats, "feature").text = f

            gal = ET.SubElement(item, "gallery")
            count_img = 0
            for img in dados['imagens']:
                if count_img >= 15: break
                ET.SubElement(gal, "image").text = img
                count_img += 1
            
            print(f"   -> OK: {dados['titulo']} | Status: {dados['status']} | Features: {len(dados['features'])}")

    except KeyboardInterrupt:
        print("\n🛑 Parando...")
    finally:
        driver.quit()
        if contador > 0:
            xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")
            with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
                f.write(xml_str)
            print(f"\n✅ CONCLUÍDO! Salvo em {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    main()