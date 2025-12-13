import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom
import datetime
import re

# --- CONFIGURAÇÕES ---
URL_LISTAGEM = "https://eme.maishm.com.br/imoveis"
ARQUIVO_SAIDA = "HM_SP_FINAL_V14.xml"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

def get_slug(url):
    return url.split('/')[-1] if url else ""

def limpar_texto(texto):
    if not texto: return ""
    return " ".join(texto.split())

def limpar_preco(texto_bruto):
    if not texto_bruto: return "Sob Consulta"
    texto = texto_bruto.lower().replace("simular financiamento", "").replace("saiba mais", "")
    match = re.search(r'r\$\s*[\d.,]+', texto)
    if match: return f"A partir de {match.group(0).upper()}"
    return "Sob Consulta"

def extrair_endereco_exato(soup):
    rotulo = soup.find(lambda tag: tag.name == 'p' and 'endereço da obra' in tag.get_text().lower())
    if rotulo:
        endereco_real = rotulo.find_next_sibling('p')
        if endereco_real:
            return limpar_texto(endereco_real.get_text())
    return ""

def extrair_diferenciais_e_tipologias(soup):
    """
    Extrai itens com ícone e separa em duas listas:
    - Features (Lazer/Comodidades)
    - Typologies (Metragens)
    """
    features = []
    typologies = []
    
    # Regex para identificar metragem (número + m²)
    regex_area = re.compile(r'\d+(?:[.,]\d+)?\s*m[2²]', re.IGNORECASE)

    icones = soup.find_all(class_=lambda x: x and 'icone' in x.lower())
    seen = set()
    
    for icone in icones:
        nome_feature_tag = icone.find_next('p')
        if nome_feature_tag:
            texto = limpar_texto(nome_feature_tag.get_text())
            if texto and texto not in seen:
                # SEPARAÇÃO AQUI
                if regex_area.search(texto):
                    typologies.append(texto)
                else:
                    features.append(texto)
                seen.add(texto)
                
    return features, typologies

def extrair_status(soup):
    badge = soup.find(class_=lambda x: x and 'bg-black/60' in x)
    if badge:
        p_tag = badge.find('p')
        if p_tag: return p_tag.get_text(separator=' ').strip().upper()
    
    termos = ['PRONTO PARA MORAR', 'EM CONSTRUÇÃO', 'BREVE LANÇAMENTO', 'LANÇAMENTO']
    for termo in termos:
        if soup.find(string=lambda t: t and termo in t.upper()): return termo
    return ""

def validar_imagem_smart(src):
    src_lower = src.lower()
    bloqueados = ['.svg', 'logo', 'icon', 'whatsapp', 'facebook', 'instagram', 'avatar', 'user', 'pixel']
    if any(x in src_lower for x in bloqueados): return False
    match_width = re.search(r'w_(\d+)', src_lower)
    if match_width and int(match_width.group(1)) < 600: return False
    return True

def extrair_dados_internos(url):
    dados = {
        "cidade": "SP", "bairro": "", "endereco": "", "dormitorios": "", 
        "metragem": "", "preco": "Sob Consulta", "status": "", "descricao": "", 
        "imagem_capa": "", "galeria": [], "plantas": [], 
        "diferenciais": [], "tipologias": []
    }
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200: return dados
            
        soup = BeautifulSoup(resp.content, 'html.parser')
        texto_pagina = soup.get_text(separator=' ').lower()

        # Preço
        preco_elem = soup.find(class_=re.compile(r'price|preco|valor|value'))
        if preco_elem: dados['preco'] = limpar_preco(preco_elem.get_text())
        else:
            match_preco = re.search(r'r\$\s*[\d.,]+', texto_pagina)
            if match_preco: dados['preco'] = f"A partir de {match_preco.group(0).upper()}"

        # Endereço & Cidade
        dados['endereco'] = extrair_endereco_exato(soup)
        cidades_comuns = ['Campinas', 'Hortolândia', 'Sumaré', 'Paulínia', 'Americana', 
                          'Limeira', 'Jundiaí', 'São Paulo', 'Mogi das Cruzes', 
                          'Santa Bárbara', 'São Carlos', 'Extrema', 'Itapetininga', 
                          'Osasco', 'Salto', 'Valinhos', 'Guarujá', 'Freguesia do Ó']
        texto_busca = (dados['endereco'] + " " + (soup.title.string if soup.title else "")).lower()
        for cidade in cidades_comuns:
            if cidade.lower() in texto_busca:
                dados['cidade'] = cidade
                break

        # Ficha Técnica Básica
        match_dorms = re.search(r'(\d+)\s*(?:e\s*\d+)?\s*(?:dorms|dormitórios|quartos)', texto_pagina)
        if match_dorms: dados['dormitorios'] = match_dorms.group(0).title()
        
        match_area = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:a\s*\d+)?\s*m[2²]', texto_pagina)
        if match_area: dados['metragem'] = match_area.group(0)

        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc: dados['descricao'] = meta_desc.get('content', '')

        # Status
        dados['status'] = extrair_status(soup)
        
        # DIFERENCIAIS E TIPOLOGIAS (Separados)
        dados['diferenciais'], dados['tipologias'] = extrair_diferenciais_e_tipologias(soup)

        # Imagens
        og_image = soup.find('meta', property='og:image')
        if og_image: dados['imagem_capa'] = og_image['content']

        todas_imgs = soup.find_all('img', src=True)
        imgs_processadas = set()
        for img in todas_imgs:
            src = img['src']
            if not src.startswith('http'):
                if src.startswith('//'): src = 'https:' + src
                else: src = 'https://eme.maishm.com.br' + src

            if src in imgs_processadas: continue
            if not validar_imagem_smart(src): continue

            src_lower = src.lower()
            keywords_planta = ['planta', 'implantacao', 'implantação', 'cotas', 'apto1', 'apto_', 'pavimento', 'dimensoes']
            
            is_planta = False
            pai = img.find_parent(class_=lambda c: c and 'planta' in c.lower())
            if any(k in src_lower for k in keywords_planta) or pai: is_planta = True

            is_foto = False
            pai_galeria = img.find_parent(class_=re.compile(r'gallery|slide|carousel|swiper'))
            if (pai_galeria or 'gallery' in src_lower or 'upload' in src_lower) and not is_planta: is_foto = True

            if is_planta:
                if src not in dados['plantas']: dados['plantas'].append(src)
            elif is_foto:
                if src != dados['imagem_capa'] and src not in dados['galeria']: dados['galeria'].append(src)
            imgs_processadas.add(src)

    except Exception as e:
        print(f"   [!] Erro: {e}")
    
    return dados

def main():
    print(">>> O SCRIPT HM ENGENHARIA (V14 - TYPOLOGY SPLIT) COMEÇOU! <<<")
    
    try:
        response = requests.get(URL_LISTAGEM, headers=HEADERS)
    except Exception as e:
        print(f"ERRO: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    links_brutos = soup.find_all('a', href=lambda h: h and '/imoveis/hm-' in h)
    links_unicos = {l['href']: l for l in links_brutos}
    total = len(links_unicos)
    print(f">>> {total} LINKS ENCONTRADOS.")

    root = ET.Element("listings")
    listings_salvos = 0
    contador = 0

    for url_full, link_elem in links_unicos.items():
        contador += 1
        slug = get_slug(url_full)
        if not url_full.startswith('http'): url_full = "https://eme.maishm.com.br" + url_full

        ignorar = False
        candidate = link_elem
        for _ in range(4):
            if not candidate: break
            if len({get_slug(l['href']) for l in candidate.find_all('a', href=lambda h: h and '/imoveis/hm-' in h)}) > 1: break
            if candidate.find('p', string=lambda t: t and '100% vendido' in t.lower()) or \
               candidate.find(class_=lambda x: x and ('sold' in x.lower() or 'esgotado' in x.lower())):
                ignorar = True
                break
            candidate = candidate.parent
        
        if 'maxi-extrema' in slug: ignorar = True

        if ignorar:
            print(f"[{contador}/{total}] VENDIDO: {slug}")
            continue

        titulo = slug.replace('-', ' ').title()
        print(f"[{contador}/{total}] EXTRAINDO: {titulo} ...")
        
        dados = extrair_dados_internos(url_full)
        
        item = ET.SubElement(root, "listing")
        ET.SubElement(item, "title").text = titulo
        ET.SubElement(item, "link").text = url_full
        ET.SubElement(item, "status").text = dados['status']
        ET.SubElement(item, "city").text = dados['cidade']
        ET.SubElement(item, "neighborhood").text = dados['bairro']
        ET.SubElement(item, "address").text = dados['endereco']
        ET.SubElement(item, "price").text = dados['preco']
        ET.SubElement(item, "bedrooms").text = dados['dormitorios']
        ET.SubElement(item, "area").text = dados['metragem']
        ET.SubElement(item, "description").text = dados['descricao']
        ET.SubElement(item, "cover_image").text = dados['imagem_capa']
        ET.SubElement(item, "date_scraped").text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # FEATURES (Só Lazer)
        features_node = ET.SubElement(item, "features")
        for feat in dados['diferenciais']:
            ET.SubElement(features_node, "feature").text = feat
            
        # TYPOLOGIES (Só Metragens)
        typologies_node = ET.SubElement(item, "typologies")
        for typo in dados['tipologias']:
            ET.SubElement(typologies_node, "typology").text = typo

        galeria_node = ET.SubElement(item, "gallery")
        for img_url in dados['galeria'][:20]: 
            ET.SubElement(galeria_node, "image").text = img_url
            
        plantas_node = ET.SubElement(item, "floor_plans")
        for planta_url in dados['plantas']:
            ET.SubElement(plantas_node, "plan_image").text = planta_url

        print(f"   -> {dados['cidade']} | {len(dados['diferenciais'])} Lazer | {len(dados['tipologias'])} Tipologias")
        listings_salvos += 1

    if listings_salvos > 0:
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")
        with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
            f.write(xml_str)
        print(f"\n>>> SUCESSO! {listings_salvos} imóveis salvos.")

if __name__ == "__main__":
    main()