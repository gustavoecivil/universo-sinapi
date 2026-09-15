"""
Script de teste do ETL com arquivos já extraídos
"""
from pathlib import Path
from src.extract import SINAPIExtractor
from src.transform import SINAPITransformer

def test_with_extracted_files():
    """Testa o ETL com arquivos já extraídos"""
    print("=" * 80)
    print("TESTE DO ETL - Arquivos Extraidos")
    print("=" * 80)
    
    # Caminho dos arquivos extraídos
    extracted_path = Path("SINAPI TABLE DOWNLOADED EXAMPLE/extracted")
    
    if not extracted_path.exists():
        print(f"ERRO: Pasta nao encontrada: {extracted_path}")
        return False
    
    # Listar arquivos Excel
    excel_files = list(extracted_path.glob("*.xlsx"))
    
    if not excel_files:
        print(f"ERRO: Nenhum arquivo Excel encontrado em: {extracted_path}")
        return False
    
    print(f"\nEncontrados {len(excel_files)} arquivos Excel")
    for f in excel_files:
        print(f"  - {f.name}")
    
    # Referência
    reference = "2025-12"
    
    # Transformar
    print("\n" + "=" * 80)
    print("ETAPA: TRANSFORMACAO")
    print("=" * 80)
    
    transformer = SINAPITransformer()
    processed_data = transformer.process_all_files(excel_files, reference)
    
    if not processed_data:
        print("ERRO: Nenhum dado processado!")
        return False
    
    # Salvar
    print("\n" + "=" * 80)
    print("ETAPA: SALVAMENTO")
    print("=" * 80)
    
    saved_files = transformer.save_processed_data(processed_data, reference, ['json', 'csv'])
    
    if not saved_files:
        print("ERRO: Nenhum arquivo salvo!")
        return False
    
    print("\n" + "=" * 80)
    print("SUCESSO! ETL CONCLUIDO")
    print("=" * 80)
    print(f"Arquivos processados: {len(saved_files)}")
    print(f"Local: data/processed/{reference}/")
    
    # Listar arquivos gerados
    print("\nArquivos gerados:")
    for f in saved_files:
        print(f"  - {f.name} ({f.stat().st_size / 1024:.2f} KB)")
    
    return True

if __name__ == "__main__":
    success = test_with_extracted_files()
    exit(0 if success else 1)
