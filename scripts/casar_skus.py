"""Casa os SKUs da Universo Eletrico com os insumos SINAPI de MG.
Uso: python scripts/casar_skus.py
Saidas: data/universo/casamento_sinapi.csv
"""
import re, unicodedata
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

SKUS = 'data/universo/skus_universo_eletrico.csv'
INS = 'data/mg/insumos_mg.csv'
OUT = 'data/universo/casamento_sinapi.csv'

SIN = {  # abreviaturas comuns no catalogo da Universo
 r'\bDISJ\b':'DISJUNTOR', r'\bTERM\b':'TERMINAL', r'\bCOND\b':'CONDUTOR', r'\bCONECT\b':'CONECTOR',
 r'\bELETR\b':'ELETRODUTO', r'\bPARAF\b':'PARAFUSO', r'\bGALV\b':'GALVANIZADO', r'\bFLEX\b':'FLEXIVEL',
 r'\bISOL\b':'ISOLADO', r'\bTOM\b':'TOMADA', r'\bINTERR\b':'INTERRUPTOR', r'\bABRAC\b':'ABRACADEIRA',
 r'\bCAIXA DE TOMADA\b':'CAIXA', r'\bBIPOLAR\b':'BIPOLAR', r'\bMONOP\b':'MONOPOLAR', r'\bTRIP\b':'TRIPOLAR',
 r'\bPVC\b':'PVC', r'\bMT\b|\bMTS\b':'M',
}
STOP = set('DE DA DO DAS DOS PARA COM SEM E EM A O OU NA NO P UM UMA TIPO'.split())

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

def nums(s):
    return set(re.findall(r'\d+(?:\.\d+)?(?:MM2|MM|KV|KA|A|V|W|M|CM|KG|L)?', s))

def toks(s):
    return ' '.join(t for t in s.split() if t not in STOP)

ins = pd.read_csv(INS, dtype={'codigo':str})
nd = ins[ins.desonerado.astype(str)=='False'].drop_duplicates('codigo').set_index('codigo')
de = ins[ins.desonerado.astype(str)=='True'].drop_duplicates('codigo').set_index('codigo')
cat = nd.reset_index()[['codigo','descricao','unidade','preco_mediano','mes_referencia']]
cat['preco_desonerado'] = cat.codigo.map(de.preco_mediano)
cat['n'] = cat.descricao.map(norm)

sk = pd.read_csv(SKUS, sep=';', encoding='utf-8-sig', dtype=str).fillna('')
sk['n'] = (sk['Produto']).map(norm)

vec = TfidfVectorizer(analyzer='word', ngram_range=(1,2), token_pattern=r'[A-Z0-9."/]+', sublinear_tf=True,
                      preprocessor=lambda x: toks(x))
M = vec.fit_transform(pd.concat([cat.n, sk.n]))
C, S = M[:len(cat)], M[len(cat):]
sim = linear_kernel(S, C)

cnums = [nums(x) for x in cat.n]
ctok = [set(toks(x).split()) for x in cat.n]
idf = dict(zip(vec.get_feature_names_out(), vec.idf_))
RUIDO = set('BR BRANCO BRANCA PRETO PRETA CINZA CZ PT BC VM VERMELHA VERMELHO AZ AZUL AM AMARELO LEGRAND SOPRANO INTELLI FRONTEC SEGURIMAX GRAPHITE PLUS ACCIAO'.split())
def palavras(n):
    return [t for t in toks(n).split() if re.fullmatch(r'[A-Z]{3,}', t) and t not in RUIDO]

rows = []
for i, r in sk.iterrows():
    sn = nums(r['n'])
    top = sim[i].argsort()[::-1][:15]
    best = None
    pw = palavras(r['n'])
    wtot = sum(idf.get(t,1) for t in pw) or 1
    cand = set(top) | set(sim[i].argsort()[::-1][:60])
    for j in cand:
        cont = sum(idf.get(t,1) for t in pw if t in ctok[j])/wtot
        sc = 0.7*cont + 0.3*sim[i][j]
        cn = cnums[j]
        if sn:
            hit = len(sn & cn)/len(sn)           # fracao das medidas do SKU presentes no insumo
            sc = sc*(0.5 + 0.5*hit)
            if hit == 0: sc *= 0.6
        # regra do substantivo principal: 1a palavra do SKU deve abrir a descricao SINAPI
        head = pw[0] if pw else None
        ct = toks(cat.n.iloc[j]).split()
        if head and head not in ct[:3]: sc *= 0.7
        if best is None or sc > best[0]: best = (sc, j, (len(sn & cn)/len(sn)) if sn else None)
    sc, j, hit = best
    if sc >= (0.75 if hit is None else 0.6) and (hit is None or hit >= 0.99): nivel = 'alta'
    elif sc >= 0.55: nivel = 'media'
    elif sc >= 0.40: nivel = 'baixa'
    else: nivel = 'sem_par'
    c = cat.iloc[j]
    rows.append({'sku':r['SKU (REF)'],'produto':r['Produto'],'marca':r['Marca'],'categoria':r['Categoria'],
                 'nivel':nivel,'score':round(sc,3),'medidas_batem':'' if hit is None else round(hit,2),
                 'sinapi_codigo':c.codigo if nivel!='sem_par' else '',
                 'sinapi_descricao':c.descricao if nivel!='sem_par' else '',
                 'sinapi_unidade':c.unidade if nivel!='sem_par' else '',
                 'preco_nao_desonerado':c.preco_mediano if nivel!='sem_par' else '',
                 'preco_desonerado':c.preco_desonerado if nivel!='sem_par' else '',
                 'mes_referencia':c.mes_referencia if nivel!='sem_par' else '',
                 'url':r['URL']})
out = pd.DataFrame(rows)
out.to_csv(OUT, index=False, encoding='utf-8-sig')
print(out.nivel.value_counts().to_string())
