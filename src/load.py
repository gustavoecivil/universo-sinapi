"""
Módulo para disponibilização dos dados processados
"""
import pandas as pd
import json
from pathlib import Path
from typing import List, Optional, Dict


class SINAPILoader:
    """Classe para disponibilizar dados SINAPI processados"""
    
    def __init__(self, data_dir: str = "data/processed"):
        """
        Inicializa o loader
        
        Args:
            data_dir: Diretório onde os dados processados estão armazenados
        """
        self.data_dir = Path(data_dir)
    
    def list_available_references(self) -> List[str]:
        """
        Lista todas as referências (meses/anos) disponíveis
        
        Returns:
            Lista de referências disponíveis
        """
        if not self.data_dir.exists():
            return []
        
        references = [d.name for d in self.data_dir.iterdir() if d.is_dir()]
        return sorted(references)
    
    def load_data(self, reference: str, file_pattern: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """
        Carrega dados processados de uma referência específica
        
        Args:
            reference: Referência do mês/ano (ex: "2025-12")
            file_pattern: Padrão para filtrar arquivos (ex: "*mao_de_obra*")
            
        Returns:
            Dicionário com nome do arquivo como chave e DataFrame como valor
        """
        reference_dir = self.data_dir / reference
        
        if not reference_dir.exists():
            raise FileNotFoundError(f"Referência não encontrada: {reference}")
        
        # Buscar arquivos
        if file_pattern:
            files = list(reference_dir.glob(file_pattern))
        else:
            files = list(reference_dir.glob("*.*"))
        
        data = {}
        
        for file_path in files:
            try:
                if file_path.suffix == '.parquet':
                    df = pd.read_parquet(file_path)
                elif file_path.suffix == '.csv':
                    df = pd.read_csv(file_path, encoding='utf-8-sig')
                elif file_path.suffix == '.json':
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    df = pd.DataFrame(json_data)
                elif file_path.suffix == '.xlsx':
                    df = pd.read_excel(file_path)
                else:
                    continue
                
                data[file_path.stem] = df
                
            except Exception as e:
                print(f"[ERRO] Erro ao carregar {file_path.name}: {e}")
        
        return data
    
    def get_metadata(self, reference: str) -> Dict:
        """
        Obtém metadados sobre os dados de uma referência
        
        Args:
            reference: Referência do mês/ano
            
        Returns:
            Dicionário com metadados
        """
        reference_dir = self.data_dir / reference
        
        if not reference_dir.exists():
            return {}
        
        files = list(reference_dir.glob("*.*"))
        
        metadata = {
            'reference': reference,
            'files_count': len(files),
            'files': []
        }
        
        for file_path in files:
            try:
                file_info = {
                    'name': file_path.name,
                    'size_mb': file_path.stat().st_size / (1024 * 1024),
                    'extension': file_path.suffix
                }
                
                # Tentar obter número de linhas
                if file_path.suffix == '.parquet':
                    df = pd.read_parquet(file_path)
                    file_info['rows'] = len(df)
                    file_info['columns'] = list(df.columns)
                
                metadata['files'].append(file_info)
                
            except Exception as e:
                file_info['error'] = str(e)
                metadata['files'].append(file_info)
        
        return metadata
    
    def export_metadata_json(self, output_path: Optional[Path] = None) -> Path:
        """
        Exporta metadados de todas as referências para JSON
        
        Args:
            output_path: Caminho do arquivo JSON de saída
            
        Returns:
            Caminho do arquivo gerado
        """
        if output_path is None:
            output_path = self.data_dir / "metadata.json"
        
        references = self.list_available_references()
        all_metadata = {
            'references': [self.get_metadata(ref) for ref in references],
            'total_references': len(references)
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Metadados exportados: {output_path}")
        return output_path
