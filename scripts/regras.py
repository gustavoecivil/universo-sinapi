"""Regras de medidas e de tipo usadas no casamento SKU x SINAPI (v3).
Funcoes puras, sem rede, para rodar no Actions e na calibracao offline."""
import re

CODIGO = re.compile(r'\b(?:\d{5,}[A-Z]*(?:\.\d+)?|[A-Z]{1,4}\d{3,}[A-Z0-9]*|[A-Z]{2,}-\d+(?:-\d+)*)\b')

def limpa_codigos(n):
    """Tira codigos de catalogo (680173, JA4803M0JW, 00003.016, CO8X1) que nao sao medida."""
    return re.sub(r'\s+', ' ', CODIGO.sub(' ', n)).strip()

def pre(n):
    """Padroniza placas (postos, 4X2/4X4) e polos antes de comparar."""
    n = re.sub(r'(\d)\s*\+\s*(\d)\s*POSTOS?', lambda m: f'{int(m[1])+int(m[2])} POSTOS', n)
    n = re.sub(r'(\d)\s*\+\s*(\d)\s*\+\s*(\d)\s*POSTOS?', lambda m: f'{int(m[1])+int(m[2])+int(m[3])} POSTOS', n)
    n = re.sub(r'\b(4)"?\s*X\s*(2|4)"?(?![\d.]|\s*(?:MM|CM))', r'\1X\2', n)
    n = re.sub(r'\b1M\b', ' ', n)  # 1 modulo, nao e medida
    return n

POLOS = {'MONOPOLAR':1, 'UNIPOLAR':1, 'BIPOLAR':2, 'TRIPOLAR':3, 'TETRAPOLAR':4}
def polos(n):
    for k, v in POLOS.items():
        if k in n: return v
    m = re.search(r'\b(\d) POLOS\b', n)
    return int(m[1]) if m else None

def postos(n):
    if 'CEGA' in n: return 0
    m = re.search(r'\b(\d)\s*POSTOS?\b', n)
    return int(m[1]) if m else None

def tam_placa(n):
    m = re.search(r'\b(4X2|4X4)\b', n)
    return m[1] if m else None

def amperagens(n):
    return [float(x) for x in re.findall(r'(?<![\d.])(\d+(?:\.\d+)?)\s*A\b', n)]

def faixas(n):
    return [(float(a), float(b)) for a, b in re.findall(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*A\b', n)]

def ajuste_tipo(sku_n, cand_n):
    """Multiplicador (0..1) por regras de tipo. 1 = sem objecao."""
    f = conflito(sku_n, cand_n)
    ps, pc = polos(sku_n), polos(cand_n)
    if ps and pc and ps != pc: f *= 0.5
    if ('DISJUNTOR' in sku_n) and ('DISPOSITIVO DR' in cand_n or 'CONTATOR' in cand_n): f *= 0.5
    if 'PLACA' in sku_n or 'ESPELHO' in sku_n:
        a, b = postos(sku_n), postos(cand_n)
        if 'ESPELHO' in cand_n or 'PLACA' in cand_n:
            if a is not None and b is not None and a != b: f *= 0.45
            ta, tb = tam_placa(sku_n), tam_placa(cand_n)
            if ta and tb and ta != tb: f *= 0.6
        else: f *= 0.5
    ma, mc = ('APENAS MODULO' in cand_n), ('CONJUNTO MONTADO' in cand_n)
    if re.search(r'\bMODULO\b', sku_n) and mc: f *= 0.9
    if re.search(r'\bCABO\b', sku_n):
        x = re.search(r'\b(\d)X\d', sku_n)  # multipolar 5X4
        if x and int(x[1]) > 1 and '1 CONDUTOR' in cand_n: f *= 0.35
    return f

NUM = re.compile(r'(?<![\d.])\d+(?:\.\d+)?')
def hit_medidas(sku_n, cand_n):
    """Fracao dos numeros do SKU presentes no candidato (sem olhar unidade); faixa 'X - Y A' conta como presente."""
    s = limpa_codigos(sku_n)
    nums = set(NUM.findall(s)) - {'750', '1'}   # classe de tensao e quantidade nao discriminam
    if not nums: return None
    cn = set(NUM.findall(cand_n))
    fx = faixas(cand_n)
    ok = sum(1 for x in nums if x in cn or any(a <= float(x) <= b for a, b in fx))
    return ok / len(nums)

CONFLITOS = [('VERTICAL','HORIZONTAL'), ('EMBUTIR','SOBREPOR'), ('INTERNA','EXTERNA'), ('INTERNO','EXTERNO'),
             ('MONOFASICO','TRIFASICO'), ('SEM BARRAMENTO','COM BARRAMENTO')]
def conflito(sku_n, cand_n):
    f = 1.0
    for a, b in CONFLITOS:
        if (a in sku_n and b in cand_n and a not in cand_n) or (b in sku_n and a in cand_n and b not in cand_n): f *= 0.55
    if sku_n.startswith('KIT ') and not cand_n.startswith('KIT'): f *= 0.7
    return f
