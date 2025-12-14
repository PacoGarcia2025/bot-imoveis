import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def limpar_texto(texto):
    if texto:
        return " ".join(texto.split())
    return "N/A"

# Função para validar se é uma característica real ou lixo (contato/email/etc)
def validar_detalhe(texto):
    texto_lower = texto.lower()
    
    # 1. Lista de palavras proíbidas (Blacklist)
    termos_proibidos = [
        "whatsapp", "e-mail", "email", "fale conosco", "receba mais", 
        "outros assuntos", "política", "privacidade", "contato", 
        "ligamos", "agende", "chat", "facebook", "instagram", 
        "implantação", "voltar", "topo"
    ]
    
    # Se tiver qualquer termo proibido, descarta
    if any(termo in texto_lower for termo in termos_proibidos):
        return False
        
    # 2. Verifica se é número de telefone (Padrão XX XXXX-XXXX)
    # A regex procura: 2 digitos, espaço, 4 ou 5 digitos, traço, 4 digitos
    padrao_telefone = r"\d{2}\s\d{4,5}-\d{4}"
    if re.search(padrao_telefone, texto):
        return False
        
    return True

print("--- INICIANDO ROBÔ: TEGRA CAMPINAS (VERSÃO LIMPEZA) ---")

options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

dados_imoveis = []

try:
    url = "https://www.tegraincorporadora.com.br/busca?cidade=Campinas"
    driver.get(url)
    time.sleep(8) 

    elementos = driver.find_elements(By.TAG_NAME, "a")
    links_imoveis = set()

    for link in elementos:
        href = link.get_attribute("href")
        if href and "/sp/campinas/" in href:
            links_imoveis.add(href)

    print(f"Encontrei {len(links_imoveis)} imóveis.")

    for link_atual in links_imoveis:
        print(f"--> Processando: {link_atual}")
        driver.get(link_atual)
        time.sleep(5)

        imovel = {
            "Link": link_atual,
            "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # --- NOME ---
        try:
            imovel["Nome"] = driver.find_element(By.TAG_NAME, "h1").text
        except:
            imovel["Nome"] = "N/A"

        # --- ENDEREÇO ---
        try:
            endereco = "N/A"
            titulos_h2 = driver.find_elements(By.TAG_NAME, "h2")
            for h2 in titulos_h2:
                txt = h2.text
                if "," in txt and any(c.isdigit() for c in txt):
                    endereco = limpar_texto(txt)
                    break
            
            if endereco == "N/A":
                paragrafos = driver.find_elements(By.TAG_NAME, "p")
                for p in paragrafos:
                    txt = p.text
                    if "Campinas" in txt and "," in txt and len(txt) < 100:
                         if "Relacionamento" not in txt:
                            endereco = limpar_texto(txt)
                            break
            imovel["Endereco"] = endereco
        except:
            imovel["Endereco"] = "N/A"

        # --- PREÇO ---
        try:
            paragrafos = driver.find_elements(By.TAG_NAME, "p")
            preco = "Sob Consulta"
            for p in paragrafos:
                if "R$" in p.text:
                    preco = p.text
                    break
            imovel["Preco"] = preco
        except:
            imovel["Preco"] = "N/A"

        # --- CARACTERÍSTICAS (COM FILTRO DE LIMPEZA) ---
        try:
            feats = []
            
            # Pega itens de lista (li)
            lis = driver.find_elements(By.TAG_NAME, "li")
            for li in lis:
                txt = limpar_texto(li.text)
                if txt and validar_detalhe(txt):
                    if "m²" in txt or "Dorm" in txt or "Sala" in txt or "Vaga" in txt:
                        feats.append(txt)

            # Pega itens de amenidades (font-light)
            itens_lazer = driver.find_elements(By.CLASS_NAME, "font-light")
            for item in itens_lazer:
                txt = limpar_texto(item.text)
                # Valida se não é lixo e tem tamanho razoável
                if txt and len(txt) > 3 and len(txt) < 40:
                    if validar_detalhe(txt):
                        feats.append(txt)

            # Remove duplicatas e junta
            imovel["Detalhes"] = " | ".join(list(set(feats)))
        except:
            imovel["Detalhes"] = ""

        # --- IMAGENS ---
        try:
            imgs = driver.find_elements(By.TAG_NAME, "img")
            lista_src = []
            for img in imgs:
                src = img.get_attribute("src")
                if src and "http" in src:
                    if "icon" not in src and "logo" not in src and ".svg" not in src:
                        lista_src.append(src)
            imovel["Imagens"] = " | ".join(list(set(lista_src))[:5])
        except:
            imovel["Imagens"] = ""

        dados_imoveis.append(imovel)
        print(f"    Salvo: {imovel['Nome']}")

except Exception as e:
    print(f"Erro: {e}")

finally:
    driver.quit()

# GERA O XML
if dados_imoveis:
    root = ET.Element("Imoveis_Tegra_Campinas")
    for dado in dados_imoveis:
        item = ET.SubElement(root, "Imovel")
        for chave, valor in dado.items():
            child = ET.SubElement(item, chave)
            child.text = str(valor)

    tree = ET.ElementTree(root)
    tree.write("tegra_campinas.xml", encoding="utf-8", xml_declaration=True)
    print("\n--- SUCESSO! XML LIMPO GERADO. ---")
else:
    print("Nenhum dado capturado.")