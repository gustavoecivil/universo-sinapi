import sys, itertools
sys.path.insert(0,'scripts')
import pandas as pd, numpy as np
import casar_skus_v2 as v2, regras as R
sk=pd.read_csv('data/universo/skus_universo_eletrico.csv',sep=';',encoding='utf-8-sig',dtype=str).fillna('')
skn=dict(zip(sk['SKU (REF)'],sk.Produto.map(v2.norm)))
c=pd.read_csv('data/universo/casamento_sinapi_v2_cand.csv',encoding='utf-8-sig',dtype={'codigo':str,'sku':str})
c['cn']=c.descricao.map(v2.norm); c['sn']=c.sku.map(skn)
c['emb']=pd.to_numeric(c.emb); c['lex']=pd.to_numeric(c.lex)
c['hit2']=[R.hit_medidas(R.pre(a),R.pre(b)) for a,b in zip(c.sn,c.cn)]
c['aj']=[R.ajuste_tipo(R.pre(a),R.pre(b)) for a,b in zip(c.sn,c.cn)]
c.to_pickle('/tmp/cand_feat.pkl')
