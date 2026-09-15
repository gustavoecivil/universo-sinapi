"""
Exemplos de uso do ETL SINAPI
"""
from pathlib import Path
from src.etl import SINAPIETL
from src.download import SINAPIDownloader
from src.extract import SINAPIExtractor
from src.transform import SINAPITransformer
from src.load import SINAPILoader

def example_full_etl():
    """Exemplo: Executar ETL completo"""
    print("=" * 80)
    print("EXEMPLO 1: ETL Completo")
    print("=" * 80)
    
    etl = SINAPIETL()
    success = etl.run(2025, 12, output_format='parquet')
    
    if success:
        print("\n✅ ETL executado com sucesso!")
    else:
        print("\n❌ ETL falhou!")


def example_download_only():
    """Exemplo: Apenas download"""
    print("=" * 80)
    print("EXEMPLO 2: Apenas Download")
    print("=" * 80)
    
    downloader = SINAPIDownloader()
    zip_path = downloader.download(2025, 12)
    
    if zip_path:
        print(f"\n✅ Arquivo baixado: {zip_path}")


def example_extract_and_transform():
    """Exemplo: Extrair e transformar arquivo já baixado"""
    print("=" * 80)
    print("EXEMPLO 3: Extração e Transformação")
    print("=" * 80)
    
    # Assumindo que já temos um arquivo baixado
    zip_path = Path("data/downloads/SINAPI-2025-12-formato-xlsx.zip")
    
    if zip_path.exists():
        # Extrair
        extractor = SINAPIExtractor()
        extracted_files = extractor.extract(zip_path, "2025-12")
        
        # Transformar
        transformer = SINAPITransformer()
        processed_data = transformer.process_all_files(extracted_files, "2025-12")
        
        # Salvar
        saved_files = transformer.save_processed_data(processed_data, "2025-12", "parquet")
        
        print(f"\n✅ {len(saved_files)} arquivos processados e salvos!")
    else:
        print(f"\n❌ Arquivo não encontrado: {zip_path}")


def example_load_data():
    """Exemplo: Carregar dados processados"""
    print("=" * 80)
    print("EXEMPLO 4: Carregar Dados Processados")
    print("=" * 80)
    
    loader = SINAPILoader()
    
    # Listar referências disponíveis
    references = loader.list_available_references()
    print(f"\n📊 Referências disponíveis: {references}")
    
    if references:
        # Carregar dados da primeira referência
        reference = references[0]
        print(f"\n📥 Carregando dados de: {reference}")
        
        data = loader.load_data(reference)
        print(f"\n✅ {len(data)} arquivos carregados:")
        
        for file_name, df in data.items():
            print(f"   - {file_name}: {len(df)} linhas, {len(df.columns)} colunas")
        
        # Obter metadados
        metadata = loader.get_metadata(reference)
        print(f"\n📋 Metadados:")
        print(f"   - Total de arquivos: {metadata.get('files_count', 0)}")


def example_process_existing_files():
    """Exemplo: Processar arquivos já extraídos (da pasta de exemplo)"""
    print("=" * 80)
    print("EXEMPLO 5: Processar Arquivos Existentes")
    print("=" * 80)
    
    extracted_path = Path("SINAPI TABLE DOWNLOADED EXAMPLE/extracted")
    
    if not extracted_path.exists():
        print(f"\n❌ Pasta não encontrada: {extracted_path}")
        return
    
    # Listar arquivos Excel
    excel_files = list(extracted_path.glob("*.xlsx"))
    
    if not excel_files:
        print(f"\n❌ Nenhum arquivo Excel encontrado em: {extracted_path}")
        return
    
    print(f"\n📁 Encontrados {len(excel_files)} arquivos Excel")
    
    # Transformar
    transformer = SINAPITransformer()
    processed_data = transformer.process_all_files(excel_files, "2025-12")
    
    # Salvar
    saved_files = transformer.save_processed_data(processed_data, "2025-12", "parquet")
    
    print(f"\n✅ {len(saved_files)} arquivos processados e salvos em data/processed/2025-12/")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example_num = int(sys.argv[1])
    else:
        example_num = 5  # Padrão: processar arquivos existentes
    
    examples = {
        1: example_full_etl,
        2: example_download_only,
        3: example_extract_and_transform,
        4: example_load_data,
        5: example_process_existing_files
    }
    
    if example_num in examples:
        examples[example_num]()
    else:
        print(f"Exemplo {example_num} não encontrado. Use 1-5.")
