import json
import unicodedata
import re
import random 
from difflib import SequenceMatcher

class SistemaGrade:
    def __init__(self, caminho_matriz, caminho_oferta, caminho_equivalencias=None):
        self.matriz = {}
        self.oferta = []
        self.equivalencias = {} 
        self.carregar_dados(caminho_matriz, caminho_oferta, caminho_equivalencias)

    def normalizar_texto(self, texto):
        if not texto: return ""
        
        # 1. REMOVE CÓDIGOS DE TURMA DO SIGA
        texto = re.sub(r'^[A-Z]{1,3}\d?\s+', '', str(texto))
        
        # Normaliza acentos
        nfkd = unicodedata.normalize('NFKD', texto)
        sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)]).upper().strip()
        
        # 2. REMOVE PALAVRAS INÚTEIS
        palavras_inuteis = [
            "INTRODUCAO A ", "INTRODUCAO AO ", "INTRODUCAO AS ", "INTRODUCAO ",
            "NOCOES DE ", "NOCOES ",
            "FUNDAMENTOS DE ", "FUNDAMENTOS DA ", "FUNDAMENTOS DO ", "FUNDAMENTOS ",
            "PRINCIPIOS DE ", "PRINCIPIOS ",
            "LABORATORIO DE ", "LABORATORIO ", "LAB "
        ]
        
        for lixo in palavras_inuteis:
            if lixo in sem_acento:
                sem_acento = sem_acento.replace(lixo, "")

        # 3. PADRONIZAÇÃO FINAL
        substituicoes = [
            (" VIII", " 8"), (" VII", " 7"), (" VI", " 6"),
            (" III", " 3"), (" II", " 2"), (" IV", " 4"),
            (" V", " 5"), (" IX", " 9"), (" I", " 1"),
            ("CALCULO", "CALCULO"), ("CÁLCULO", "CALCULO"),
            ("ALGEBRA", "ALGEBRA"), ("ÁLGEBRA", "ALGEBRA"),
            ("COMPUTACAO", "COMPUTACAO"), ("COMPUTAÇÃO", "COMPUTACAO"),
            ("SISTES", "SISTEMAS"), ("SIST ", "SISTEMAS ")
        ]
        
        for antigo, novo in substituicoes:
            if antigo in sem_acento:
                sem_acento = sem_acento.replace(antigo, novo)
            elif sem_acento.endswith(antigo.strip()):
                 sem_acento = sem_acento.replace(antigo.strip(), novo.strip())
                 
        return re.sub(r'\s+', ' ', sem_acento).strip()

    def limpar_codigo(self, codigo):
        return "".join(filter(str.isdigit, str(codigo)))

    def extrair_numeros(self, texto):
        return [int(s) for s in texto.split() if s.isdigit()]

    def verificar_similaridade(self, nome1, nome2):
        n1 = self.normalizar_texto(nome1)
        n2 = self.normalizar_texto(nome2)
        
        if n1 == n2: return True
        
        nums1 = self.extrair_numeros(n1)
        nums2 = self.extrair_numeros(n2)
        if nums1 and nums2 and set(nums1) != set(nums2): return False

        if n1 in n2 or n2 in n1: return True

        ratio = SequenceMatcher(None, n1, n2).ratio()
        if ratio > 0.85: return True
        
        if ratio > 0.7 and len(n1) > 5 and len(n2) > 5: return True

        return False

    def carregar_dados(self, caminho_m, caminho_o, caminho_e):
        try:
            with open(caminho_m, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                for d in dados:
                    chave = self.limpar_codigo(d['codigo'])
                    d['nome_norm'] = self.normalizar_texto(d['nome'])
                    self.matriz[chave] = d
        except: pass
        try:
            with open(caminho_o, 'r', encoding='utf-8') as f: self.oferta = json.load(f)
        except: self.oferta = []
        try:
            with open(caminho_e, 'r', encoding='utf-8') as f:
                raw_eq = json.load(f)
                for k, v in raw_eq.items():
                    cod_k = self.limpar_codigo(k)
                    if cod_k not in self.equivalencias: self.equivalencias[cod_k] = []
                    for val in v: self.equivalencias[cod_k].append(self.limpar_codigo(val))
        except: self.equivalencias = {}

    # ---  GERADOR DE TAGS ---
    def gerar_tags_professor(self, nome_prof):
        if not nome_prof or nome_prof == "A DEFINIR": return []
        
        # Lista de Tags Possíveis (Texto, Ícone FontAwesome, Cor Tailwind)
        tags_pool = [
            {"texto": "Cobra Presença", "icone": "fa-user-check", "cor": "red"},
            {"texto": "Seminários", "icone": "fa-users-line", "cor": "blue"},
            {"texto": "Listas Valem Nota", "icone": "fa-list-check", "cor": "green"},
            {"texto": "Prova Difícil", "icone": "fa-brain", "cor": "purple"},
            {"texto": "Didático", "icone": "fa-chalkboard-user", "cor": "indigo"},
            {"texto": "Trabalho em Grupo", "icone": "fa-people-group", "cor": "orange"},
            {"texto": "Gosta de Debates", "icone": "fa-comments", "cor": "pink"},
            {"texto": "Aceita Atraso", "icone": "fa-clock", "cor": "teal"}
        ]
        
        # Semente fixa baseada no nome: O mesmo professor sempre terá as mesmas tags!
        random.seed(nome_prof) 
        
        # Escolhe de 1 a 3 tags aleatórias para esse professor
        qtd_tags = random.randint(1, 3)
        return random.sample(tags_pool, qtd_tags)

    def gerar_grade(self, bloqueadas_input, aprovadas_dict):
        sugestao = []
        
        # PREPARAÇÃO DOS DADOS
        if isinstance(bloqueadas_input, dict):
            meus_codigos_bloqueados = set(self.limpar_codigo(c) for c in bloqueadas_input.keys())
            meus_nomes_bloqueados = [self.normalizar_texto(n) for n in bloqueadas_input.values()]
        else:
            meus_codigos_bloqueados = set(self.limpar_codigo(c) for c in bloqueadas_input)
            meus_nomes_bloqueados = []

        # Aprovadas (para pré-requisitos)
        meus_codigos_aprovados = set(self.limpar_codigo(c) for c in aprovadas_dict.keys())
        meus_nomes_aprovados = [self.normalizar_texto(n) for n in aprovadas_dict.values()]

        print("\n🔎 CORE: Analisando com 'Triturador de Nomes' + Tags...")

        oferta_ordenada = sorted(self.oferta, key=lambda x: x.get('nome', ''))

        for turma in oferta_ordenada:
            cod_ofertado = self.limpar_codigo(turma.get('codigo', ''))
            nome_ofertado_norm = self.normalizar_texto(turma.get('nome', ''))
            curso_origem = str(turma.get('curso_origem', '')).upper()
            
            # --- DEBUG ---
            eh_alvo = any(x in nome_ofertado_norm for x in ["DIREITO", "CALCULO", "SISTEMAS"])
            msg_debug = f"🧐 VISTO: {nome_ofertado_norm}" if eh_alvo else ""

            if "TRABALHO DE CONCLUSAO" in nome_ofertado_norm or "ESTAGIO" in nome_ofertado_norm:
                if "COMPUTACAO" not in curso_origem and "COMPUTAÇÃO" not in curso_origem: continue 

            # 1. Identifica se a matéria existe na grade
            codigo_grade_match = None
            eh_equivalente = False
            
            if cod_ofertado in self.matriz:
                codigo_grade_match = cod_ofertado
            elif not codigo_grade_match:
                for cod_grade, lista_equi in self.equivalencias.items():
                    if cod_ofertado in lista_equi:
                        codigo_grade_match = cod_grade
                        eh_equivalente = True
                        break
            if not codigo_grade_match:
                for cod_grade, dados_matriz in self.matriz.items():
                    if self.verificar_similaridade(dados_matriz['nome_norm'], nome_ofertado_norm):
                        codigo_grade_match = cod_grade
                        eh_equivalente = True
                        break

            if not codigo_grade_match: continue

            # 2. BLOQUEIO 
            
            # A. Pelo Código
            if codigo_grade_match in meus_codigos_bloqueados:
                if eh_alvo: print(f"{msg_debug} -> ❌ BLOQUEADO (Código {codigo_grade_match} detectado)")
                continue
            
            # B. Pelo Nome
            nome_da_grade = self.matriz[codigo_grade_match]['nome_norm']
            bloqueio_por_nome = False
            for meu_nome in meus_nomes_bloqueados:
                if self.verificar_similaridade(nome_da_grade, meu_nome):
                    bloqueio_por_nome = True
                    break
            
            if bloqueio_por_nome:
                if eh_alvo: print(f"{msg_debug} -> ❌ BLOQUEADO (Já tem matéria similar: '{meu_nome}')")
                continue

            # 3. Pré-Requisitos
            disciplina_info = self.matriz.get(codigo_grade_match)
            pode_fazer = True
            
            for req in disciplina_info.get('pre_requisitos', []):
                req_limpo = self.limpar_codigo(req)
                
                if req_limpo in meus_codigos_aprovados: continue
                lista_equi_req = self.equivalencias.get(req_limpo, [])
                if any(eq in meus_codigos_aprovados for eq in lista_equi_req): continue

                nome_req = self.matriz.get(req_limpo, {}).get('nome_norm', '')
                tem_pelo_nome = False
                for meu_nome in meus_nomes_aprovados:
                    if self.verificar_similaridade(nome_req, meu_nome):
                        tem_pelo_nome = True
                        break
                
                if not tem_pelo_nome:
                    pode_fazer = False
                    if eh_alvo: print(f"{msg_debug} -> ❌ Falta Pré-Req: {nome_req}")
                    break
            
            if pode_fazer:
                if eh_alvo: print(f"{msg_debug} -> ✅ APROVADO PARA SUGESTÃO!")
                turma['semestre_ideal'] = disciplina_info.get('semestre_ideal', 0)
                turma['nome_original'] = disciplina_info.get('nome')
                turma['eh_equivalente'] = eh_equivalente
                turma['nome_curso_origem'] = curso_origem
                turma['tags'] = self.gerar_tags_professor(turma.get('professor'))
                
                sugestao.append(turma)

        return sugestao