import time
import json
import pandas as pd
import re
import concurrent.futures
import threading
import unicodedata
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from io import StringIO

# --- CONFIGURAÇÃO ---

ALVOS_CUIABA = [
    "COMPUTAÇÃO", "SISTEMAS", "MATEMÁTICA", "FÍSICA", 
    "ESTATÍSTICA", "QUÍMICA", "SANITÁRIA", "AGRONOMIA", 
    "CONTROLE", "MINAS", "GEOLOGIA", "ARQUITETURA", 
    "ELÉTRICA", "FLORESTAL", "ALIMENTOS", "CIÊNCIA"
]

# VG: Não tem lista, pois a regra é LER TUDO.

progresso_atual = 0
total_tarefas = 0
lock_progresso = threading.Lock()

def remover_acentos(texto):
    return "".join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def decifrar_horario(texto_bruto):
    if not texto_bruto or str(texto_bruto).lower() == 'nan': return []
    texto_limpo = remover_acentos(str(texto_bruto).upper().strip())
    resultado = []

    # Tenta código (24M12)
    mapa_dias_cod = {'2': 'SEG', '3': 'TER', '4': 'QUA', '5': 'QUI', '6': 'SEX', '7': 'SAB'}
    horarios_base = {'M': ['07:30','08:30','09:30','10:30','11:30'], 'T': ['13:30','14:30','15:30','16:30','17:30'], 'N': ['19:00','20:00','21:00','22:00','23:00']}
    match_cod = re.search(r'([2-7]+)([MTN])([1-4]+)', texto_limpo)
    if match_cod:
        dias_str, turno, periodos_str = match_cod.groups()
        try:
            h_inicio = horarios_base[turno][int(periodos_str[0]) - 1]
            h_fim = horarios_base[turno][int(periodos_str[-1])]
            for d in dias_str: 
                resultado.append({'dia': mapa_dias_cod.get(d, '?'), 'inicio': h_inicio, 'fim': h_fim})
            return resultado 
        except: pass

    # Tenta extenso (SEGUNDA DAS...)
    padrao_hora = r'(\d{2}:\d{2})'
    horarios_encontrados = re.findall(padrao_hora, texto_limpo)
    if len(horarios_encontrados) >= 2:
        inicio, fim = horarios_encontrados[0], horarios_encontrados[1]
        dias_extenso = {'SEGUNDA': 'SEG', 'TERCA': 'TER', 'QUARTA': 'QUA', 'QUINTA': 'QUI', 'SEXTA': 'SEX', 'SABADO': 'SAB'}
        for nome_dia, sigla in dias_extenso.items():
            if nome_dia in texto_limpo:
                resultado.append({'dia': sigla, 'inicio': inicio, 'fim': fim})
    return resultado

def extrair_tabela(driver, campus_tag, nome_curso_origem):
    try:
        WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        html = driver.page_source
        try: html = StringIO(html)
        except: pass
        
        tabelas = pd.read_html(html)
        if not tabelas: return []
        df = max(tabelas, key=len).fillna("")
        turmas = []
        
        for _, linha in df.iterrows():
            try:
                coluna_baguncada = str(linha.iloc[0]).strip()
                match_dados = re.search(r'^(\d+)\s*-\s*(.+?)(?:,|$)', coluna_baguncada)
                
                if match_dados:
                    codigo_real = match_dados.group(1)
                    nome_real = match_dados.group(2).strip()
                else:
                    codigo_real = coluna_baguncada.split(" ")[0]
                    nome_real = coluna_baguncada
                
                professor_real = str(linha.iloc[1]).strip()
                horario_bruto = str(linha.iloc[4]).strip() if len(linha) > 4 else ""
                
                if not any(c.isdigit() for c in horario_bruto):
                     match_parenteses = re.search(r'\((.*?:\d{2}.*?)\)', coluna_baguncada)
                     if match_parenteses: horario_bruto = match_parenteses.group(1)

                if len(codigo_real) > 4 and codigo_real.isdigit():
                    turmas.append({
                        "codigo": codigo_real,
                        "nome": nome_real,
                        "turma": str(linha.iloc[2]).strip(),
                        "professor": professor_real,
                        "horario_desc": horario_bruto,
                        "horarios": decifrar_horario(horario_bruto),
                        "campus": campus_tag,
                        "curso_origem": nome_curso_origem
                    })
            except: continue
        return turmas
    except: return []

def listar_cursos_do_campus(nome_campus, filtros):
    """
    Lista cursos.
    SE FOR VG: Pega TUDO.
    SE FOR CUIABÁ: Aplica o filtro.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--blink-settings=imagesEnabled=false")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    cursos_aprovados = []
    
    try:
        driver.get("https://academico-siga.ufmt.br/ufmt.portalacademico/ConsultaOferta")
        sel_campus = Select(driver.find_elements(By.TAG_NAME, "select")[0])
        op = next((o for o in sel_campus.options if nome_campus.upper() in o.text.upper()), None)
        
        if op:
            sel_campus.select_by_visible_text(op.text)
            time.sleep(2)
            
            sel_curso = Select(driver.find_elements(By.TAG_NAME, "select")[1])
            todos_cursos = [o.text for o in sel_curso.options if o.text.strip() != ""]
            
            # --- LÓGICA DE SELEÇÃO ---
            if "VÁRZEA" in nome_campus.upper():
                # REGRA 1: VG LÊ TUDO (Menos a opção padrão "escolha o curso")
                for curso in todos_cursos:
                    if "ESCOLHA" not in curso.upper():
                        cursos_aprovados.append(curso)
            else:
                # REGRA 2: CUIABÁ LÊ SÓ OS COMPATÍVEIS
                for curso in todos_cursos:
                    if "ESCOLHA" in curso.upper(): continue
                    if any(k in curso.upper() for k in filtros):
                        cursos_aprovados.append(curso)
           

    except Exception as e: pass
    finally: driver.quit()
    return cursos_aprovados

def worker_robo(id_robo, nome_campus, lista_cursos, semestre_alvo, callback_progresso=None):
    global progresso_atual
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--blink-settings=imagesEnabled=false")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    ofertas_locais = []
    tag = "VG" if "VÁRZEA" in nome_campus.upper() else "CUIABA"

    try:
        driver.get("https://academico-siga.ufmt.br/ufmt.portalacademico/ConsultaOferta")
        sel_campus = Select(driver.find_elements(By.TAG_NAME, "select")[0])
        op = next((o for o in sel_campus.options if nome_campus.upper() in o.text.upper()), None)
        if op:
            sel_campus.select_by_visible_text(op.text)
            time.sleep(1.5)

            for curso in lista_cursos:
                # Atualiza Barra
                with lock_progresso:
                    progresso_atual += 1
                    pct = min(int((progresso_atual / total_tarefas) * 95), 99)
                    msg = f"[{progresso_atual}/{total_tarefas}] R{id_robo}: {curso[:15]}..."
                
                if callback_progresso: callback_progresso(pct, msg)
                
                try:
                    Select(driver.find_elements(By.TAG_NAME, "select")[1]).select_by_visible_text(curso)
                    time.sleep(0.5)

                    selects = driver.find_elements(By.TAG_NAME, "select")
                    if len(selects) > 2:
                        sel_sem = Select(selects[2])
                        op_sem = next((o for o in sel_sem.options if semestre_alvo in o.text), None)
                        
                        if op_sem:
                            sel_sem.select_by_visible_text(op_sem.text)
                            
                            try: driver.find_element(By.ID, "btnBuscar").click()
                            except: driver.find_element(By.XPATH, "//input[@value='Buscar']").click()
                            
                            # --- PAGINAÇÃO INSISTENTE ---
                            pag = 1
                            conteudo_anterior = None
                            
                            while True:
                                # 1. Lê a tabela
                                novas = extrair_tabela(driver, tag, curso)
                                
                                # Verifica se travou (igual anterior)
                                if novas == conteudo_anterior: 
                                    break 
                                
                                conteudo_anterior = novas
                                if novas: 
                                    ofertas_locais.extend(novas)
                                    if pag > 1 and callback_progresso:
                                        callback_progresso(pct, f"R{id_robo}: {curso[:10]}... (Pág {pag})")

                                # 2. Clica no Próximo
                                try:
                                    btns = driver.find_elements(By.XPATH, "//a[contains(text(), '>') or contains(text(), 'Próximo')]")
                                    clicou = False
                                    for btn in btns:
                                        if "disabled" not in btn.get_attribute("class"):
                                            driver.execute_script("arguments[0].click();", btn)
                                            time.sleep(2.0) 
                                            clicou = True
                                            pag += 1
                                            break
                                    if not clicou: break
                                except: break
                           
                except: pass
    except Exception as e:
        print(f"Erro Robô {id_robo}: {e}")
    finally:
        driver.quit()
        
    return ofertas_locais

def buscar_oferta_ao_vivo(semestre_alvo, callback_progresso=None):
    global progresso_atual, total_tarefas
    progresso_atual = 0
    
    if callback_progresso: callback_progresso(1, "Planejando rota...")

   
    # VG = Lista todos (ignora filtro)
    cursos_vg = listar_cursos_do_campus("VÁRZEA GRANDE", []) 
    # Cuiabá = Aplica filtro ALVOS_CUIABA
    cursos_cuiaba = listar_cursos_do_campus("CUIABÁ", ALVOS_CUIABA)
    
    total_tarefas = len(cursos_vg) + len(cursos_cuiaba)
    if total_tarefas == 0: total_tarefas = 1

    # Divide Tarefas
    meio_vg = len(cursos_vg) // 2
    lote_vg_1 = cursos_vg[:meio_vg]
    lote_vg_2 = cursos_vg[meio_vg:]
    
    meio_cba = len(cursos_cuiaba) // 2
    lote_cba_1 = cursos_cuiaba[:meio_cba]
    lote_cba_2 = cursos_cuiaba[meio_cba:]
    
    oferta_total = []

    if callback_progresso: callback_progresso(5, f"Iniciando varredura em {total_tarefas} cursos...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        if lote_vg_1: futures.append(executor.submit(worker_robo, 1, "VÁRZEA GRANDE", lote_vg_1, semestre_alvo, callback_progresso))
        if lote_vg_2: futures.append(executor.submit(worker_robo, 2, "VÁRZEA GRANDE", lote_vg_2, semestre_alvo, callback_progresso))
        if lote_cba_1: futures.append(executor.submit(worker_robo, 3, "CUIABÁ", lote_cba_1, semestre_alvo, callback_progresso))
        if lote_cba_2: futures.append(executor.submit(worker_robo, 4, "CUIABÁ", lote_cba_2, semestre_alvo, callback_progresso))
        
        for f in concurrent.futures.as_completed(futures):
            oferta_total.extend(f.result())

    if callback_progresso: callback_progresso(99, "Salvando dados...")
    
    # Salva sem filtro de duplicatas (RAW DATA)
    print(f" Concluído. Total de turmas salvas: {len(oferta_total)}")
    with open('dados/oferta.json', 'w', encoding='utf-8') as f:
        json.dump(oferta_total, f, indent=4, ensure_ascii=False)
        
    return oferta_total