"""
Script principal para executar o ETL SINAPI

Processa apenas o arquivo SINAPI_Referência com as abas:
- ISD (INSUMOS SEM DESONERAÇÃO)
- ICD (INSUMOS COM DESONERAÇÃO)
- CSD (COMPOSIÇÕES SEM DESONERAÇÃO)
- CCD (COMPOSIÇÕES COM DESONERAÇÃO)
- Analítico (LISTA DE COMPOSIÇÕES E INSUMOS)
"""
import argparse
from datetime import datetime
from src.etl import SINAPIETL


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description='ETL para dados SINAPI - Processa apenas SINAPI_Referência (ISD, ICD, CSD, CCD, Analítico)'
    )
    
    parser.add_argument(
        '--year',
        type=int,
        help='Ano da referência (ex: 2025)'
    )
    
    parser.add_argument(
        '--month',
        type=int,
        help='Mês da referência (ex: 12)'
    )
    
    parser.add_argument(
        '--current',
        action='store_true',
        help='Processar mês atual'
    )
    
    parser.add_argument(
        '--latest',
        action='store_true',
        help='Processar arquivo mais recente disponível'
    )
    
    parser.add_argument(
        '--formats',
        type=str,
        nargs='+',
        default=['json', 'csv'],
        choices=['json', 'csv', 'parquet', 'xlsx'],
        help='Formatos de saída dos dados processados (padrão: json csv)'
    )
    
    parser.add_argument(
        '--supabase',
        action='store_true',
        help='Carregar dados processados no Supabase após o processamento'
    )
    
    args = parser.parse_args()
    
    # Criar instância do ETL
    etl = SINAPIETL(load_to_supabase=args.supabase)
    
    # Executar conforme argumentos
    if args.latest:
        print("[PROCESSANDO] Arquivo mais recente disponivel...")
        success = etl.run_latest_available(args.formats, args.supabase)
    elif args.current:
        print("[PROCESSANDO] Mes atual...")
        success = etl.run_current_month(args.formats, args.supabase)
    elif args.year and args.month:
        success = etl.run(args.year, args.month, args.formats, args.supabase)
    else:
        # Padrão: mês atual
        print("[PROCESSANDO] Mes atual (padrao)...")
        success = etl.run_current_month(args.formats, args.supabase)
    
    if success:
        print("\n[SUCESSO] Processo concluido com sucesso!")
        return 0
    else:
        print("\n[ERRO] Processo falhou!")
        return 1


if __name__ == "__main__":
    exit(main())
