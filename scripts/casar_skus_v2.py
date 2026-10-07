"""Casamento SKUs Universo x insumos SINAPI MG, versao 2.
Combina tres sinais, no espirito do projeto MihVargas/cleansing:
  1) significado (embeddings multilingues, sentence-transformers)
  2) letras (RapidFuzz token_set_ratio)
  3) palavras raras e medidas (TF-IDF, contencao ponderada, conferencia de bitola/amperagem)
Depois aplica regra de decisao: aceitar, revisar ou sem par, olhando a nota e a folga para o 2o colocado.
Saidas: data/universo/casamento_sinapi_v2.csv e data/universo/casamento_v2_log.txt
"""
import re, sys, time, traceback, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

SKUS = 'data/universo/skus_universo_eletrico.csv'
INS = 'data/mg/insumos_mg.csv'
OUT = 'data/universo/casamento_sinapi_v2.csv'
LOG = Path('data/universo/casamento_v2_log.txt')
MODELO = 'paraphrase-multilingual-mpnet-base-v2'

# Pesos e limites (ponto de partida; calibrados depois contra amostra rotulada)
W_EMB, W_LEX, W_TFIDF = 0.45, 0.20, 0.35
LIM_ACEITA, LIM_REVISA, LIM_FAMILIA = 0.80, 0.62, 0.48
FOLGA_MIN = 0.03

logs = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); logs.append(s)

SIN = {r'\bDISJ\b':'DISJUNTOR', r'\bTERM\b':'TERMINAL', r'\bCOND\b':'CONDUTOR', r'\bCONECT\b':'CONECTOR',
       r'\bELETR\b':'ELETRODUTO', r'\bPARAF\b':'PARAFUSO', r'\bGALV\b':'GALVANIZADO', r'\bFLEX\b':'FLEXIVEL',
       r'\bISOL\b':'ISOLADO', r'\bTOM\b':'TOMADA', r'\bINTERR\b':'INTERRUPTOR', r'\bABRAC\b':'ABRACADEIRA',
       r'\bMONOP\b':'MONOPOLAR', r'\bTRIP\b':'TRIPOLAR', r'\bMT\b|\bMTS\b':'M', r'\bPLACA\b':'PLACA ESPELHO',
       r'\bMODULO\b|\bMOD\b':'MODULO'}
STOP = set('DE DA DO DAS DOS PARA COM SEM E EM A O OU NA NO P UM UMA TIPO'.split())
RUIDO = set('BR BRANCO BRANCA PRETO PRETA CINZA CZ PT BC VM VERMELHA VERMELHO AZ AZUL AM AMARELO LEGRAND SOPRANO '
            'INTELLI FRONTEC SEGURIMAX GRAPHITE PLUS ACCIAO VERDE LARANJA MARROM CARRETEL'.split())

def norm(s):
    s = unicodedata.normalize('NFD', str(s)).encode('ascii','ignore').decode().upper()
    s = s.replace('MM²','MM2').replace('²','2').replace('“','"').replace('”','"').replace('″','"')
    for k,v in SIN.items(): s = re.sub(k, v, s)
    s = re.sub(r'(\d),(\d)', r'\1.\2', s)
    s = re.sub(r'(\d+)\.0+(?!\d)', r'\1', s)
    s = re.sub(r'(\d+\.\d*?)0+(?!\d)', r'\1', s)
    if 'FLEXSIL' in s or 'CARRETEL CABO' in s:
        s = s.replace('CARRETEL','').replace('FLEXSIL','CABO COBRE FLEXIVEL')
        s = re.sub(r'750\s*V\s+(\d+(?:\.\d+)?)\b(?!MM)', r'750V \1MM2', s)
    s = re.sub(r'(\d)\s*(MM2|MM|KV|KA|A|V|W|M|CM|KG|L)\b', r'\1\2', s)
    s = re.sub(r'[^A-Z0-9."/ ]', ' ', s)
    return re.sub(r'\s+',' ', s).strip()

def nums(s): return set(re.findall(r'\d+(?:\.\d+)?(?:MM2|MM|KV|KA|A|V|W|M|CM|KG|L)?', s))
def toks(s): return ' '.join(t for t in s.split() if t not in STOP)
def palavras(n): return [t for t in toks(n).split() if re.fullmatch(r'[A-Z]{3,}', t) and t not in RUIDO]

def principal():
    t0 = time.time()
    ins = pd.read_csv(INS, dtype={'codigo':str})
    nd = ins[ins.desonerado.astype(str)=='False'].drop_duplicates('codigo')
    de = ins[ins.desonerado.astype(str)=='True'].drop_duplicates('codigo').set_index('codigo')
    cat = nd[['codigo','descricao','unidade','preco_mediano','mes_referencia']].reset_index(drop=True)
    cat['preco_desonerado'] = cat.codigo.map(de.preco_mediano)
    cat['n'] = cat.descricao.map(norm)
    sk = pd.read_csv(SKUS, sep=';', encoding='utf-8-sig', dtype=str).fillna('')
    sk['n'] = sk['Produto'].map(norm)
    log(f'SKUs: {len(sk)}  insumos SINAPI: {len(cat)}')

    # 1) significado
    emb = None
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(MODELO)
        A = m.encode(sk.n.tolist(), batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        B = m.encode(cat.n.tolist(), batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        emb = np.clip(A @ B.T, 0, 1)
        log('embeddings ok, modelo', MODELO, f'({time.time()-t0:.0f}s)')
    except Exception as e:
        log('AVISO: embeddings indisponiveis, seguindo sem eles:', repr(e))
    # 2) letras
    try:
        from rapidfuzz import process, fuzz
        lex = process.cdist(sk.n.tolist(), cat.n.tolist(), scorer=fuzz.token_set_ratio, workers=-1)/100.0
        log(f'rapidfuzz ok ({time.time()-t0:.0f}s)')
    except Exception as e:
        log('AVISO: rapidfuzz indisponivel:', repr(e)); lex = None
    # 3) palavras raras e medidas
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    vec = TfidfVectorizer(ngram_range=(1,2), token_pattern=r'[A-Z0-9."/]+', sublinear_tf=True, preprocessor=toks)
    M = vec.fit_transform(pd.concat([cat.n, sk.n]))
    cos = linear_kernel(M[len(cat):], M[:len(cat)])
    idf = dict(zip(vec.get_feature_names_out(), vec.idf_))
    ctok = [set(toks(x).split()) for x in cat.n]
    cnums = [nums(x) for x in cat.n]

    pesos = {'emb': W_EMB if emb is not None else 0, 'lex': W_LEX if lex is not None else 0, 'tf': W_TFIDF}
    tot = sum(pesos.values()); pesos = {k: v/tot for k, v in pesos.items()}
    log('pesos efetivos:', {k: round(v,2) for k, v in pesos.items()})

    rows = []
    for i, r in sk.iterrows():
        pw = palavras(r['n']); wtot = sum(idf.get(t,1) for t in pw) or 1
        sn = nums(r['n'])
        base = pesos['tf']*cos[i]
        if emb is not None: base = base + pesos['emb']*emb[i]
        if lex is not None: base = base + pesos['lex']*lex[i]
        pre = np.argsort(base)[::-1][:40]
        pontos = []
        for j in pre:
            cont = sum(idf.get(t,1) for t in pw if t in ctok[j])/wtot
            sc = 0.8*base[j] + 0.2*cont
            hit = None
            if sn:
                hit = len(sn & cnums[j])/len(sn)
                sc *= (0.5 + 0.5*hit)
                if hit == 0: sc *= 0.6
            head = pw[0] if pw else None
            if head and head not in toks(cat.n.iloc[j]).split()[:3]: sc *= 0.85
            pontos.append((sc, j, hit))
        pontos.sort(reverse=True)
        (s1, j1, h1), (s2, j2, _), (s3, j3, _) = pontos[0], pontos[1], pontos[2]
        folga = s1 - s2
        medidas_ok = h1 is None or h1 >= 0.99
        if s1 >= LIM_ACEITA and folga >= FOLGA_MIN and medidas_ok: nivel = 'alta'
        elif s1 >= LIM_REVISA and medidas_ok: nivel = 'media'
        elif s1 >= LIM_FAMILIA: nivel = 'baixa'
        else: nivel = 'sem_par'
        c = cat.iloc[j1]; ok = nivel != 'sem_par'
        rows.append({'sku':r['SKU (REF)'],'produto':r['Produto'],'marca':r['Marca'],'categoria':r['Categoria'],
          'nivel':nivel,'score':round(s1,3),'folga':round(folga,3),'medidas_batem':'' if h1 is None else round(h1,2),
          'sinapi_codigo':c.codigo if ok else '','sinapi_descricao':c.descricao if ok else '',
          'sinapi_unidade':c.unidade if ok else '','preco_nao_desonerado':c.preco_mediano if ok else '',
          'preco_desonerado':c.preco_desonerado if ok else '','mes_referencia':c.mes_referencia if ok else '',
          'alt2_codigo':cat.codigo.iloc[j2],'alt2_descricao':cat.descricao.iloc[j2],'alt2_score':round(s2,3),
          'alt3_codigo':cat.codigo.iloc[j3],'alt3_descricao':cat.descricao.iloc[j3],'alt3_score':round(s3,3),
          'url':r['URL']})
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False, encoding='utf-8-sig')
    log('distribuicao:', out.nivel.value_counts().to_dict())
    log(f'tempo total {time.time()-t0:.0f}s')

if __name__ == '__main__':
    try:
        principal()
    except Exception:
        log('ERRO:', traceback.format_exc())
        LOG.write_text('\n'.join(logs), encoding='utf-8'); sys.exit(1)
    LOG.write_text('\n'.join(logs), encoding='utf-8')
