"""
Módulo principal do ETL SINAPI
Orquestra download, extração, transformação e carga
"""
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from .download import SINAPIDownloader
from .extract import SINAPIExtractor
from .transform import SINAPITransformer
from .load import SINAPILoader
from .supabase import SupabaseLoader


class SINAPIETL:
    """Classe principal para orquestrar o processo ETL completo"""
    
    def __init__(self, 
                 download_dir: str = "data/downloads",
                 extract_dir: str = "data/extracted",
                 processed_dir: str = "data/processed",
                 load_to_supabase: bool = False):
        """
        Inicializa o ETL
        
        Args:
            download_dir: Diretório para downloads
            extract_dir: Diretório para arquivos extraídos
            processed_dir: Diretório para dados processados
            load_to_supabase: Se True, carrega dados para Supabase após processamento
        """
        self.downloader = SINAPIDownloader(download_dir)
        self.extractor = SINAPIExtractor(extract_dir)
        self.transformer = SINAPITransformer(processed_dir)
        self.loader = SINAPILoader(processed_dir)
        self.load_to_supabase = load_to_supabase
        self.supabase_loader = None
        
        if load_to_supabase:
            try:
                self.supabase_loader = SupabaseLoader()
            except Exception as e:
                print(f"[AVISO] Não foi possível inicializar Supabase: {e}")
                print("[AVISO] O processo continuará sem carregar dados no Supabase.")
                self.load_to_supabase = False
    
    def run(self, year: int, month: int, output_formats: List[str] = ['json', 'csv'], 
            load_to_supabase: Optional[bool] = None) -> bool:
        """
        Executa o processo ETL completo para um mês/ano específico
        
        Processa apenas o arquivo SINAPI_Referência e as abas:
        - ISD (INSUMOS SEM DESONERAÇÃO)
        - ICD (INSUMOS COM DESONERAÇÃO)
        - CSD (COMPOSIÇÕES SEM DESONERAÇÃO)
        - CCD (COMPOSIÇÕES COM DESONERAÇÃO)
        - Analítico (LISTA DE COMPOSIÇÕES E INSUMOS)
        
        Args:
            year: Ano (ex: 2025)
            month: Mês (ex: 12)
            output_formats: Lista de formatos de saída (padrão: ['json', 'csv'])
            load_to_supabase: Se True, carrega dados para Supabase (sobrescreve configuração do __init__)
            
        Returns:
            True se o processo foi concluído com sucesso
        """
        # Usar parâmetro se fornecido, senão usar configuração do __init__
        should_load_supabase = load_to_supabase if load_to_supabase is not None else self.load_to_supabase
        
        print("=" * 80)
        print("INICIANDO PROCESSO ETL SINAPI")
        print("=" * 80)
        print("Processando apenas: SINAPI_Referencia")
        print("Abas: ISD, ICD, CSD, CCD, Analitico")
        if should_load_supabase:
            print("Carregamento no Supabase: ATIVADO")
        print("=" * 80)
        
        # Criar referência
        month_str = f"{month:02d}"
        reference = f"{year}-{month_str}"
        
        print(f"\nReferencia: {reference}")
        
        try:
            # 1. DOWNLOAD
            print("\n" + "=" * 80)
            print("ETAPA 1: DOWNLOAD")
            print("=" * 80)
            zip_path = self.downloader.download(year, month)
            
            if not zip_path or not zip_path.exists():
                print("[ERRO] Falha no download. Processo interrompido.")
                return False
            
            # 2. EXTRACTION
            print("\n" + "=" * 80)
            print("ETAPA 2: EXTRACAO")
            print("=" * 80)
            extracted_files = self.extractor.extract(zip_path, reference)
            
            if not extracted_files:
                print("[ERRO] Falha na extracao. Processo interrompido.")
                return False
            
            # 3. TRANSFORMATION
            print("\n" + "=" * 80)
            print("ETAPA 3: TRANSFORMACAO")
            print("=" * 80)
            print("[BUSCANDO] Arquivo SINAPI_Referencia...")
            processed_data = self.transformer.process_all_files(extracted_files, reference)
            
            if not processed_data:
                print("[ERRO] Falha na transformacao. Processo interrompido.")
                return False
            
            # 4. SAVE PROCESSED DATA
            print("\n" + "=" * 80)
            print("ETAPA 4: SALVAMENTO")
            print("=" * 80)
            saved_files = self.transformer.save_processed_data(processed_data, reference, output_formats)
            
            if not saved_files:
                print("[ERRO] Falha ao salvar dados processados.")
                return False
            
            # 5. EXPORT METADATA
            print("\n" + "=" * 80)
            print("ETAPA 5: METADADOS")
            print("=" * 80)
            self.loader.export_metadata_json()
            
            # 6. LOAD TO SUPABASE (opcional)
            if should_load_supabase:
                if not self.supabase_loader:
                    print(
                        "\n[AVISO] Supabase não foi inicializado. Verifique SUPABASE_URL e "
                        "SUPABASE_SERVICE_ROLE_KEY (recomendado com RLS) ou SUPABASE_KEY no .env"
                    )
                else:
                    print("\n" + "=" * 80)
                    print("ETAPA 6: CARREGAMENTO NO SUPABASE")
                    print("=" * 80)
                    success = self.supabase_loader.load_from_processed_files(reference, str(self.transformer.output_dir))
                    if not success:
                        print("[AVISO] Falha ao carregar dados no Supabase, mas processo ETL foi concluído.")
            
            print("\n" + "=" * 80)
            print("[SUCESSO] PROCESSO ETL CONCLUIDO COM SUCESSO!")
            print("=" * 80)
            print(f"Arquivos processados: {len(saved_files)}")
            print(f"Dados disponiveis em: {self.transformer.output_dir / reference}")
            print(f"Formatos gerados: {', '.join(output_formats)}")
            
            return True
            
        except Exception as e:
            print(f"\n[ERRO] ERRO NO PROCESSO ETL: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_current_month(self, output_formats: List[str] = ['json', 'csv'], 
                         load_to_supabase: Optional[bool] = None) -> bool:
        """
        Executa o ETL para o mês atual
        
        Args:
            output_formats: Lista de formatos de saída (padrão: ['json', 'csv'])
            load_to_supabase: Se True, carrega dados para Supabase
            
        Returns:
            True se o processo foi concluído com sucesso
        """
        now = datetime.now()
        return self.run(now.year, now.month, output_formats, load_to_supabase)
    
    def run_latest_available(self, output_formats: List[str] = ['json', 'csv'],
                            load_to_supabase: Optional[bool] = None) -> bool:
        """
        Executa o ETL para o arquivo mais recente disponível
        
        Args:
            output_formats: Lista de formatos de saída (padrão: ['json', 'csv'])
            load_to_supabase: Se True, carrega dados para Supabase
            
        Returns:
            True se o processo foi concluído com sucesso
        """
        zip_path = self.downloader.download_latest_available()
        
        if not zip_path:
            return False
        
        # Extrair ano e mês do nome do arquivo
        # Formato: SINAPI-2025-12-formato-xlsx.zip
        parts = zip_path.stem.replace("SINAPI-", "").replace("-formato-xlsx", "").split("-")
        if len(parts) == 2:
            year = int(parts[0])
            month = int(parts[1])
            return self.run(year, month, output_formats, load_to_supabase)
        
        return False
