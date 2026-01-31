import os
import threading
import time
import json 
from flask import Flask, render_template, request, jsonify
from core import SistemaGrade
from Leitor_PDF import extrair_historico

# Import do Robô
try:
    from robo_automatico import buscar_oferta_ao_vivo
except ImportError:
    def buscar_oferta_ao_vivo(semestre, callback_progresso):
        for i in range(0, 101, 10):
            time.sleep(0.1)
            callback_progresso(i, f"Simulando busca no SIGA... {i}%")

app = Flask(__name__)

# Configurações de Pasta
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('dados', exist_ok=True)


# SISTEMA DE VOTAÇÃO ANÔNIMA 
ARQUIVO_FEEDBACK = os.path.join('dados', 'feedback.json')

def carregar_feedback():
    if not os.path.exists(ARQUIVO_FEEDBACK):
        return {}
    try:
        with open(ARQUIVO_FEEDBACK, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def salvar_voto(professor, tag):
    db = carregar_feedback()
    
    if professor not in db:
        db[professor] = {}
    
    if tag not in db[professor]:
        db[professor][tag] = 0
        
    db[professor][tag] += 1
    
    with open(ARQUIVO_FEEDBACK, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4)


# STATUS GLOBAL DO ROBÔ

STATUS_SISTEMA = {
    "rodando": False,
    "mensagem": "Aguardando...",
    "porcentagem": 0,
    "concluido": False
}

def thread_robo(semestre):
    global STATUS_SISTEMA
    STATUS_SISTEMA = {
        "rodando": True, 
        "mensagem": "Iniciando robô...", 
        "porcentagem": 0, 
        "concluido": False
    }
    
    def atualizar(pct, msg):
        if pct > STATUS_SISTEMA["porcentagem"]:
            STATUS_SISTEMA["porcentagem"] = pct
        STATUS_SISTEMA["mensagem"] = msg
    
    try:
        buscar_oferta_ao_vivo(semestre, callback_progresso=atualizar)
        STATUS_SISTEMA["porcentagem"] = 100
        STATUS_SISTEMA["mensagem"] = "Concluído com sucesso!"
    except Exception as e:
        print(f"Erro na thread: {e}")
        STATUS_SISTEMA["mensagem"] = f"Erro: {str(e)}"
    finally:
        STATUS_SISTEMA["rodando"] = False
        STATUS_SISTEMA["concluido"] = True


# ROTAS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status_progresso')
def status_progresso():
    return jsonify(STATUS_SISTEMA)

@app.route('/iniciar_robo', methods=['POST'])
def iniciar_robo():
    data = request.json
    semestre = data.get('semestre', '2025/2')
    
    if not STATUS_SISTEMA['rodando']:
        t = threading.Thread(target=thread_robo, args=(semestre,))
        t.start()
        return jsonify({"status": "ok", "mensagem": "Robô iniciado"})
    else:
        return jsonify({"status": "erro", "mensagem": "Já está rodando"})

# --- ROTAS NOVAS DE VOTAÇÃO ---
@app.route('/votar', methods=['POST'])
def votar():
    data = request.json
    professor = data.get('professor')
    tag = data.get('tag')
    
    if professor and tag:
        salvar_voto(professor, tag)
        return jsonify({"status": "sucesso", "msg": "Voto computado!"})
    return jsonify({"status": "erro"}), 400

@app.route('/obter_tags', methods=['GET'])
def obter_tags():
    # Retorna os votos reais do arquivo JSON
    return jsonify(carregar_feedback())
# ------------------------------

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "Nenhum arquivo", 400
    
    file = request.files['file']
    if file.filename == '':
        return "Nome vazio", 400

    path = os.path.join(app.config['UPLOAD_FOLDER'], "historico_temp.pdf")
    file.save(path)
    
    # 1. Extrai histórico
    bloqueadas, aprovadas = extrair_historico(path)
    
    # 2. Gera grade
    sistema = SistemaGrade(
        caminho_matriz='dados/matriz_ufmt.json',
        caminho_oferta='dados/oferta.json',
        caminho_equivalencias='dados/equivalencias.json'
    )
    
    grade = sistema.gerar_grade(bloqueadas, aprovadas)
    
    return render_template('resultado.html', grade=grade)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)