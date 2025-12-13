from flask import Flask, render_template
import xmltodict
import os

app = Flask(__name__)

def carregar_imoveis():
    arquivo = 'MRVsp.xml'
    if not os.path.exists(arquivo):
        return []
    
    with open(arquivo, 'r', encoding='utf-8') as f:
        # Lê o XML e transforma em dicionário Python
        try:
            conteudo = f.read()
            # xmltodict transforma <imoveis>... em um dicionário
            dados = xmltodict.parse(conteudo)
            
            # Pega a lista de imóveis (ajuste para caso tenha só 1 ou vários)
            lista = dados.get('imoveis', {}).get('imovel', [])
            
            # Se tiver só um imóvel, o xmltodict não retorna lista, retorna dict. Corrigimos:
            if isinstance(lista, dict):
                lista = [lista]
                
            return lista
        except Exception as e:
            print(f"Erro ao ler XML: {e}")
            return []

@app.route('/')
def home():
    imoveis = carregar_imoveis()
    # Conta quantos imóveis tem
    total = len(imoveis)
    return render_template('index.html', imoveis=imoveis, total=total)

@app.route('/imovel/<int:id_imovel>')
def detalhe(id_imovel):
    imoveis = carregar_imoveis()
    # Como não temos ID no XML, vamos usar a posição na lista (0, 1, 2...)
    if 0 <= id_imovel < len(imoveis):
        imovel = imoveis[id_imovel]
        return render_template('detalhe.html', imovel=imovel)
    return "Imóvel não encontrado"

if __name__ == '__main__':
    print("--- SITE RODANDO! ---")
    print("Acesse no seu navegador: http://127.0.0.1:5000")
    app.run(debug=True)