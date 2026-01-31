import pdfplumber
import re

def extrair_historico(caminho_pdf):
    # AGORA BLOQUEADAS TAMBÉM É DICIONÁRIO {codigo: nome}
    # Isso permite bloquear matérias matriculadas pelo NOME no Core
    bloqueadas = {} 
    aprovadas = {} 
    
    KEYS_APROVADO = ['APROVADO', 'APR', 'DISPENSA', 'DIS', 'APROVEITAMENTO', 'AE', 'AP']
    KEYS_MATRICULADO = ['MATRICULADO', 'MAT', 'MA', 'CURSANDO']
    KEYS_REPROVADO = ['REPROVADO', 'REP', 'TRANCADO', 'TRANC', 'RF', 'RM', 'RMF']

    print("\n" + "="*60)
    print("🕵️  LEITOR PDF: Modo Híbrido (Extraindo nomes de TUDO)")
    print("="*60)

    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = ""
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto: texto_completo += texto + "\n"

            linhas = texto_completo.split('\n')
            
            for linha in linhas:
                linha_upper = linha.upper().strip()
                if len(linha_upper) < 10: continue

                codigo_final = None
                nome_final = None
                status_final = None

                # 1. TENTA CÓDIGO NUMÉRICO
                match_codigos = re.findall(r'\b(\d{3,10})\b', linha_upper)
                codigos_candidatos = []
                for c in match_codigos:
                    if c.startswith("20") and len(c) in [4, 5]: continue
                    if c in ['030', '032', '060', '064', '072', '090', '096', '128']: continue
                    if len(c) < 3: continue
                    codigos_candidatos.append(c)

                if codigos_candidatos:
                    codigo_final = max(codigos_candidatos, key=len)
                
                # 2. SE NÃO ACHOU, TENTA PELO NOME (Para linhas tipo AE ou Matriculado sem código)
                if not codigo_final:
                    # Procura: Ano + Texto + Numero(Horas)
                    match_nome = re.search(r'^\d{4,5}\s+(.+?)\s+\d{2,3}\b', linha_upper)
                    if match_nome:
                        nome_extraido = match_nome.group(1).strip()
                        nome_final = nome_extraido
                        codigo_final = "NOMINAL_" + re.sub(r'\s+', '_', nome_final)[:15]
                
                if not codigo_final: continue

                # 3. IDENTIFICA STATUS
                palavras_linha = linha_upper.split()
                if any(k in palavras_linha for k in KEYS_APROVADO):
                    status_final = "APROVADO"
                elif any(k in palavras_linha for k in KEYS_MATRICULADO):
                    status_final = "MATRICULADO"
                elif any(k in palavras_linha for k in KEYS_REPROVADO):
                    status_final = "REPROVADO"
                else: continue 

                # 4. LIMPA O NOME (Se ainda não tiver)
                if not nome_final:
                    nome_final = linha_upper
                    for item in match_codigos + KEYS_APROVADO + KEYS_MATRICULADO + KEYS_REPROVADO:
                        nome_final = nome_final.replace(str(item), "")
                    nome_final = re.sub(r'[^\w\s]', '', nome_final).strip()

                # DEBUG VISUAL
                if any(x in linha_upper for x in ["ALGORITMOS", "CALCULO", "METODOLOGIA", "INSTRUMENTACAO", "FISICA", "QUIMICA", "SINAIS"]):
                    print(f"👀 [{status_final}] {nome_final[:30]}...")

                # 5. SALVA ( salva nome nas bloqueadas também!)
                if status_final == "APROVADO":
                    bloqueadas[codigo_final] = nome_final
                    aprovadas[codigo_final] = nome_final
                elif status_final == "MATRICULADO":
                    bloqueadas[codigo_final] = nome_final 

    except Exception as e:
        print(f" Erro Crítico: {e}")
        return [], {}

    print("-" * 60)
    print(f" RESUMO: {len(bloqueadas)} matérias bloqueadas (Feitas + Cursando).")
    print("-" * 60 + "\n")

    return bloqueadas, aprovadas