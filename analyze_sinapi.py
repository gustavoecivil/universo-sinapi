"""
Script para analisar a estrutura dos arquivos SINAPI
"""
import zipfile
import pandas as pd
import os
from pathlib import Path

def analyze_sinapi_files():
    """Analisa os arquivos SINAPI extraídos"""
    
    extracted_path = Path("SINAPI TABLE DOWNLOADED EXAMPLE/extracted")
    
    if not extracted_path.exists():
        print("Pasta extraída não encontrada!")
        return
    
    files = list(extracted_path.glob("*.xlsx"))
    
    print("=" * 80)
    print("ANÁLISE DOS ARQUIVOS SINAPI")
    print("=" * 80)
    
    for file in files:
        print(f"\n📄 Arquivo: {file.name}")
        print("-" * 80)
        
        try:
            # Ler todas as abas do Excel
            xls = pd.ExcelFile(file)
            print(f"Abas encontradas: {xls.sheet_names}")
            
            # Analisar cada aba
            for sheet_name in xls.sheet_names:
                print(f"\n  📊 Aba: {sheet_name}")
                df = pd.read_excel(file, sheet_name=sheet_name)
                
                print(f"    - Linhas: {len(df)}")
                print(f"    - Colunas: {len(df.columns)}")
                print(f"    - Colunas: {list(df.columns)}")
                
                # Mostrar primeiras linhas
                print(f"\n    Primeiras 3 linhas:")
                print(df.head(3).to_string())
                print()
                
        except Exception as e:
            print(f"    ❌ Erro ao processar: {e}")

if __name__ == "__main__":
    analyze_sinapi_files()
