"""
Módulo para extração de arquivos ZIP do SINAPI
"""
import zipfile
from pathlib import Path
from typing import List, Optional


class SINAPIExtractor:
    """Classe para extrair arquivos ZIP do SINAPI"""
    
    def __init__(self, extract_dir: str = "data/extracted"):
        """
        Inicializa o extrator
        
        Args:
            extract_dir: Diretório onde os arquivos serão extraídos
        """
        self.extract_dir = Path(extract_dir)
        self.extract_dir.mkdir(parents=True, exist_ok=True)
    
    def extract(self, zip_path: Path, reference: Optional[str] = None) -> List[Path]:
        """
        Extrai o arquivo ZIP do SINAPI
        
        Args:
            zip_path: Caminho do arquivo ZIP
            reference: Referência do mês/ano (ex: "2025-12") para criar subpasta
            
        Returns:
            Lista de caminhos dos arquivos extraídos
        """
        if not zip_path.exists():
            raise FileNotFoundError(f"Arquivo ZIP não encontrado: {zip_path}")
        
        # Criar subpasta com a referência se fornecida
        if reference:
            extract_path = self.extract_dir / reference
        else:
            # Tentar extrair referência do nome do arquivo
            extract_path = self.extract_dir / zip_path.stem.replace("SINAPI-", "").replace("-formato-xlsx", "")
        
        extract_path.mkdir(parents=True, exist_ok=True)
        
        print(f"[EXTRAINDO] {zip_path.name}")
        print(f"   Para: {extract_path}")
        
        extracted_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Listar arquivos no ZIP
                file_list = zip_ref.namelist()
                print(f"   Arquivos no ZIP: {len(file_list)}")
                
                # Extrair todos os arquivos
                zip_ref.extractall(extract_path)
                
                # Listar arquivos extraídos
                for file_name in file_list:
                    extracted_file = extract_path / file_name
                    if extracted_file.exists():
                        extracted_files.append(extracted_file)
                        print(f"   [OK] {file_name}")
                
                print(f"[OK] Extracao concluida: {len(extracted_files)} arquivos")
                return extracted_files
                
        except zipfile.BadZipFile:
            raise ValueError(f"Arquivo ZIP inválido: {zip_path}")
        except Exception as e:
            raise Exception(f"Erro ao extrair ZIP: {e}")
