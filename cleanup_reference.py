"""
Script para limpar dados de uma referência no Supabase (em lotes para evitar timeout)
Uso: python3 cleanup_reference.py 2026-02
"""
import sys
import time
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client
from postgrest.exceptions import APIError

from src.supabase import resolve_supabase_credentials, resolve_supabase_schema

load_dotenv()

SCHEMA = resolve_supabase_schema()
# Lotes pequenos: DELETE em tabelas grandes no Supabase costuma estourar statement_timeout.
BATCH_SIZE = 25
COMPOSICOES_BATCH_SIZE = 8


def fetch_all_ids(table_fn, table_name, column, value):
    ids = []
    offset = 0
    while True:
        r = table_fn(table_name).select('id').eq(column, value).range(offset, offset + 999).execute()
        if not r.data:
            break
        ids.extend([x['id'] for x in r.data])
        offset += len(r.data)
    return ids


def _is_statement_timeout(err: BaseException) -> bool:
    if isinstance(err, APIError):
        return getattr(err, "code", None) == "57014" or (
            "statement timeout" in (getattr(err, "message", "") or "").lower()
        )
    msg = str(err).lower()
    return "57014" in msg or "statement timeout" in msg


def _execute_delete(table_fn, table_name: str, column: str, batch: list):
    """DELETE WHERE column IN (batch). batch não vazio."""
    if len(batch) == 1:
        table_fn(table_name).delete().eq(column, batch[0]).execute()
    else:
        table_fn(table_name).delete().in_(column, batch).execute()


def _delete_with_split(table_fn, table_name: str, column: str, batch: list, retries_single: int = 6):
    """
    Apaga um lote; em statement timeout divide o lote ou repete com backoff (1 linha).
    """
    if not batch:
        return
    try:
        _execute_delete(table_fn, table_name, column, batch)
    except Exception as e:
        if not _is_statement_timeout(e):
            raise
        if len(batch) > 1:
            mid = len(batch) // 2
            _delete_with_split(table_fn, table_name, column, batch[:mid], retries_single)
            _delete_with_split(table_fn, table_name, column, batch[mid:], retries_single)
            return
        last_err = e
        for attempt in range(retries_single):
            wait = min(60, 2 ** (attempt + 1))
            print(f"\n       Timeout em 1 linha, nova tentativa em {wait}s...")
            time.sleep(wait)
            try:
                _execute_delete(table_fn, table_name, column, batch)
                return
            except Exception as e2:
                last_err = e2
                if not _is_statement_timeout(e2):
                    raise
        raise last_err


def delete_in_batches(table_fn, table_name, column, ids, label="", batch_size: Optional[int] = None):
    total = len(ids)
    if total == 0:
        return
    size = batch_size if batch_size is not None else BATCH_SIZE
    deleted = 0
    for i in range(0, total, size):
        batch = ids[i : i + size]
        _delete_with_split(table_fn, table_name, column, batch)
        deleted += len(batch)
        print(f"       {label} {deleted}/{total}", end="\r")
    print(f"       {label} {total}/{total} OK")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 cleanup_reference.py <referencia>")
        print("Exemplo: python3 cleanup_reference.py 2026-02")
        sys.exit(1)

    referencia = sys.argv[1]
    url, key, used_svc = resolve_supabase_credentials()
    if not url or not key:
        print(
            "Erro: defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY (recomendado) ou SUPABASE_KEY no .env."
        )
        sys.exit(1)
    if not used_svc:
        print(
            "[AVISO] Sem SUPABASE_SERVICE_ROLE_KEY: com RLS ativo os DELETEs podem falhar (42501). "
            "Prefira a service role só neste script local."
        )
    client = create_client(url, key)

    def table(name):
        return client.schema(SCHEMA).table(name)

    resp = table('sinapi_referencias').select('id').eq('referencia', referencia).execute()
    if not resp.data:
        print(f"Referência '{referencia}' não encontrada no banco.")
        sys.exit(0)

    ref_id = resp.data[0]['id']
    print(f"Referência: {referencia} (ID: {ref_id})\n")

    # 1. Buscar IDs de composições
    print("[1/7] Buscando composições...")
    comp_ids = fetch_all_ids(table, 'composicoes', 'referencia_id', ref_id)
    print(f"       {len(comp_ids)} composições encontradas")

    # 2. Deletar composicao_analitico por composicao_pai_id
    print("[2/7] Deletando composicao_analitico (pai)...")
    delete_in_batches(table, 'composicao_analitico', 'composicao_pai_id', comp_ids, "analitico_pai")

    # 3. Deletar composicao_analitico por composicao_filha_id
    print("[3/7] Deletando composicao_analitico (filha)...")
    delete_in_batches(table, 'composicao_analitico', 'composicao_filha_id', comp_ids, "analitico_filha")

    # 4. Deletar composicao_custos
    print("[4/7] Deletando composicao_custos...")
    delete_in_batches(table, 'composicao_custos', 'composicao_id', comp_ids, "custos_comp")

    # 5. Deletar composições (mais sensível a timeout no Postgres)
    print("[5/7] Deletando composições...")
    delete_in_batches(
        table,
        "composicoes",
        "id",
        comp_ids,
        "composicoes",
        batch_size=COMPOSICOES_BATCH_SIZE,
    )

    # 6. Buscar e deletar insumos
    print("[6/8] Buscando insumos...")
    insumo_ids = fetch_all_ids(table, 'insumos', 'referencia_id', ref_id)
    print(f"       {len(insumo_ids)} insumos encontrados")

    if insumo_ids:
        print("[7/8] Deletando composicao_analitico (insumo_id)...")
        delete_in_batches(table, 'composicao_analitico', 'insumo_id', insumo_ids, "analitico_ins")
        print("       Deletando insumo_custos...")
        delete_in_batches(table, 'insumo_custos', 'insumo_id', insumo_ids, "custos_ins")
        print("       Deletando insumos...")
        delete_in_batches(table, 'insumos', 'id', insumo_ids, "insumos")
    else:
        print("[7/8] Nenhum insumo para deletar")

    # 8. Deletar referência
    print("[8/8] Deletando referência...")
    table('sinapi_referencias').delete().eq('id', ref_id).execute()
    print("       OK")

    print(f"\n[SUCESSO] Referência {referencia} removida completamente!")


if __name__ == "__main__":
    main()
