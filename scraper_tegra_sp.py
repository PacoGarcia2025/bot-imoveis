import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def limpar_texto(texto):
    if texto:
        return " ".join(texto.split())
    return "N/A"

def validar_detalhe(texto):
    texto_lower = texto.lower()
    termos_proibidos = [
        "whatsapp", "e-mail", "email", "fale conosco", "receba mais", 
        "outros assuntos", "política", "privacidade", "contato", 
        "ligamos", "agende", "chat", "facebook", "instagram", 
        "implantação", "voltar", "topo", "trace sua rota"
    ]
    if any(termo in texto_lower for termo in termos_proibidos):
        return False
    padrao_telefone = r"\d{2}\s\d{4,5}-\d{4}"
    if re.search(padrao_telefone, texto):
        return False
    return True

print("--- INICIANDO ROBÔ: TEGRA SÃO PAULO (FINAL BLINDADO) ---")

options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

dados_imoveis = []

try:
    url = "https://www.tegraincorporadora.com.br/busca?cidade=S%C3%A3o+Paulo"
    driver.get(url)
    print("Acessando página de SP...")
    time.sleep(5)

    print("Iniciando carregamento (Clique Infinito)...")
    while True:
        try:
            # Procura o botão e clica
            botao = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Exibir mais')]"))
            )
            driver.execute_script("arguments[0].scrollIntoView();", botao)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", botao)
            time.sleep(4)
        except Exception:
            print("Todos os imóveis carregados (fim da lista).")
            break

    print("Coletando links...")
    elementos = driver.find_elements(By.TAG_NAME, "a")
    links_imoveis = set()

    for link in elementos:
        href = link.get_attribute("href")
        if href and "/sp/sao-paulo/" in href:
            links_imoveis.add(href)

    print(f"Encontrei {len(links_imoveis)} imóveis em SP.")

    for i, link_atual in enumerate(links_imoveis):
        print(f"[{i+1}/{len(links_imoveis)}] Processando: {link_atual}")
        
        try:
            driver.get(link_atual)
            time.sleep(4)

            imovel = {
                "Link": link_atual,
                "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # --- NOME ---
            try:
                imovel["Nome"] = driver.find_element(By.TAG_NAME, "h1").text
            except:
                imovel["Nome"] = "N/A"

            # --- ENDEREÇO (CORREÇÃO AVANÇADA) ---
            try:
                endereco = "N/A"
                # Tenta pegar no H2
                titulos_h2 = driver.find_elements(By.TAG_NAME, "h2")
                for h2 in titulos_h2:
                    txt = h2.text
                    if "," in txt and any(c.isdigit() for c in txt):
                        endereco = limpar_texto(txt)
                        break
                
                # Se não achou, tenta no parágrafo
                if endereco == "N/A":
                    paragrafos = driver.find_elements(By.TAG_NAME, "p")
                    for p in paragrafos:
                        txt = p.text
                        if ("São Paulo" in txt or "SP" in txt) and "," in txt and len(txt) < 120:
                            if "Relacionamento" not in txt:
                                endereco = limpar_texto(txt)
                                break
                
                # LIMPEZA DO SLOGAN (Lógica do Split)
                # Corta o texto tudo que vier antes de ", o novo endereço"
                if "o novo endereço" in endereco:
                    endereco = endereco.split(", o novo")[0]
                    endereco = endereco.split(" o novo")[0] # Prevenção extra

                imovel["Endereco"] = endereco.strip()
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

            # --- DETALHES ---
            try:
                feats = []
                # Itens de lista
                lis = driver.find_elements(By.TAG_NAME, "li")
                for li in lis:
                    txt = limpar_texto(li.text)
                    if txt and validar_detalhe(txt):
                        if "m²" in txt or "Dorm" in txt or "Sala" in txt or "Vaga" in txt:
                            feats.append(txt)
                
                # Itens de lazer (font-light)
                itens_lazer = driver.find_elements(By.CLASS_NAME, "font-light")
                for item in itens_lazer:
                    txt = limpar_texto(item.text)
                    if txt and len(txt) > 3 and len(txt) < 40 and validar_detalhe(txt):
                        feats.append(txt)

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
            print(f"    -> Salvo: {imovel['Nome']}")
        
        except Exception as e:
            print(f"    Erro ao ler imóvel: {e}")
            continue

except Exception as e:
    print(f"Erro Geral: {e}")

finally:
    driver.quit()

# GERA O XML
if dados_imoveis:
    root = ET.Element("Imoveis_Tegra_SP")
    for dado in dados_imoveis:
        item = ET.SubElement(root, "Imovel")
        for chave, valor in dado.items():
            child = ET.SubElement(item, chave)
            child.text = str(valor)

    tree = ET.ElementTree(root)
    tree.write("tegra_sp.xml", encoding="utf-8", xml_declaration=True)
    print("\n--- SUCESSO! Arquivo 'tegra_sp.xml' gerado com endereços limpos. ---")
else:
    print("Nenhum dado capturado.")