"""
Módulo para transformação e tratamento dos dados SINAPI
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import re
import json


class SINAPITransformer:
    """Classe para transformar e tratar dados SINAPI"""
    
    # Abas que serão processadas do arquivo SINAPI_Referência
    REQUIRED_SHEETS = ['ISD', 'ICD', 'CSD', 'CCD', 'Analítico']
    
    def __init__(self, output_dir: str = "data/processed"):
        """
        Inicializa o transformador
        
        Args:
            output_dir: Diretório onde os dados processados serão salvos
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process_analitico_sheet(self, df: pd.DataFrame, reference: str, file_name: str) -> pd.DataFrame:
        """
        Processa a aba Analítico de forma especial, estruturando hierarquicamente
        as composições e seus componentes (composições filhas e insumos)
        
        Args:
            df: DataFrame da aba Analítico
            reference: Referência do mês/ano
            file_name: Nome do arquivo origem
            
        Returns:
            DataFrame processado com estrutura hierárquica
        """
        # Limpar nomes de colunas
        df.columns = [self.clean_column_name(col) for col in df.columns]
        
        # Remover linhas completamente vazias
        df = df.dropna(how='all')
        
        # Remover colunas completamente vazias
        df = df.dropna(axis=1, how='all')
        
        # Identificar e remover linhas de cabeçalho/metadados
        # Cabeçalhos geralmente têm unnamed_1 como NaN ou string não numérica
        df = df.copy()
        
        # Converter unnamed_1 para numérico, mantendo NaN onde não for número
        df['unnamed_1'] = pd.to_numeric(df['unnamed_1'], errors='coerce')
        
        # Filtrar apenas linhas onde unnamed_1 é numérico (código de composição)
        df = df[df['unnamed_1'].notna()].copy()
        
        # Renomear colunas de forma mais clara
        column_mapping = {
            'sinapi_sistema_nacional_de_pesquisa_de_custos_e_índices_da_construção_civil': 'categoria',
            'unnamed_1': 'codigo_composicao_mae',
            'unnamed_2': 'tipo_item',
            'unnamed_3': 'codigo_item_filho',
            'unnamed_4': 'descricao',
            'unnamed_5': 'unidade',
            'unnamed_6': 'coeficiente',
            'unnamed_7': 'situacao'
        }
        
        # Renomear apenas colunas que existem
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # Normalizar tipo_item: NaN para composição mãe, manter valores para filhos
        df['tipo_item'] = df['tipo_item'].fillna('COMPOSICAO_MAE')
        
        # Converter tipo_item para string e normalizar
        df['tipo_item'] = df['tipo_item'].astype(str).str.upper().str.strip()
        df.loc[df['tipo_item'] == 'NAN', 'tipo_item'] = 'COMPOSICAO_MAE'
        
        # Converter códigos para inteiro onde possível
        df['codigo_composicao_mae'] = df['codigo_composicao_mae'].astype(int)
        df['codigo_item_filho'] = pd.to_numeric(df['codigo_item_filho'], errors='coerce')
        
        # Adicionar colunas de metadados
        df['referencia'] = reference
        df['arquivo_origem'] = file_name
        df['aba'] = 'Analítico'
        
        # Resetar índice
        df = df.reset_index(drop=True)
        
        return df
    
    def process_custos_sheet(self, df: pd.DataFrame, reference: str, file_name: str, sheet_name: str) -> pd.DataFrame:
        """
        Processa as abas CSD e CCD de forma especial, extraindo custos por localidade
        
        Args:
            df: DataFrame da aba CSD ou CCD
            reference: Referência do mês/ano
            file_name: Nome do arquivo origem
            sheet_name: Nome da aba (CSD ou CCD)
            
        Returns:
            DataFrame processado com custos estruturados
        """
        # Limpar nomes de colunas
        df.columns = [self.clean_column_name(col) for col in df.columns]
        
        # Remover linhas completamente vazias
        df = df.dropna(how='all')
        
        # Encontrar linhas de cabeçalho
        estados_row = None
        localidades_row = None
        
        for idx, row in df.iterrows():
            row_values = [str(v).upper() if pd.notna(v) else '' for v in row.values]
            # Procurar linha com estados (contém "AC", "AL", etc. em colunas específicas)
            if 'AC' in row_values and 'AL' in row_values and 'AM' in row_values:
                estados_row = idx
            # Procurar linha com localidades
            if 'RIO BRANCO' in row_values or 'MACEIO' in row_values or 'LOCALIDADE' in row_values:
                localidades_row = idx
        
        # Mapear estados e localidades
        # Estados estão em colunas pares a partir de unnamed_4 (índice 3)
        # Localidades estão na mesma estrutura
        estados_localidades = {}
        
        if estados_row is not None and localidades_row is not None:
            estados_data = df.iloc[estados_row]
            localidades_data = df.iloc[localidades_row]
            
            # Iterar por todas as colunas para encontrar estados e localidades
            for col_idx in range(len(df.columns)):
                col_name = df.columns[col_idx]
                
                # Pegar valores das linhas de estados e localidades
                estado_val = estados_data.iloc[col_idx] if col_idx < len(estados_data) else None
                localidade_val = localidades_data.iloc[col_idx] if col_idx < len(localidades_data) else None
                
                if pd.notna(estado_val) and pd.notna(localidade_val):
                    estado_str = str(estado_val).strip().upper()
                    localidade_str = str(localidade_val).strip()
                    
                    # Validar estado (2 letras) e localidade (não vazia)
                    if len(estado_str) == 2 and estado_str.isalpha() and localidade_str:
                        estados_localidades[col_name] = {
                            'estado': estado_str,
                            'localidade': localidade_str
                        }
        
        # Remover linhas de cabeçalho (até a linha de localidades + 1)
        start_idx = (localidades_row if localidades_row is not None else estados_row) + 1 if estados_row is not None else 0
        df = df.iloc[start_idx:].copy()
        df = df.reset_index(drop=True)
        
        # Processar linhas de dados
        processed_rows = []
        
        for idx, row in df.iterrows():
            # Verificar se é uma linha de dados (tem descrição e unidade)
            descricao = row.get('unnamed_2', '')
            unidade = row.get('unnamed_3', '')
            
            # Filtrar linhas de cabeçalho
            if pd.isna(descricao) or pd.isna(unidade) or not str(descricao).strip():
                continue
            
            # Filtrar linhas que são claramente cabeçalhos
            descricao_str = str(descricao).strip().upper()
            unidade_str = str(unidade).strip().upper()
            
            # Ignorar linhas de cabeçalho conhecidas
            if (descricao_str in ['DESCRIÇÃO', 'DESCRICAO', 'GRUPO', ''] or 
                unidade_str in ['UNIDADE', ''] or
                descricao_str.startswith('OBSERVAÇÃO') or
                descricao_str.startswith('OBSERVACAO')):
                continue
            
            # Extrair dados da composição
            categoria = row.get('sinapi_sistema_nacional_de_pesquisa_de_custos_e_índices_da_construção_civil', '')
            codigo = row.get('unnamed_1', 0)
            
            # Tentar converter código para número
            try:
                if pd.notna(codigo):
                    codigo = int(float(codigo))
                else:
                    codigo = 0
            except:
                codigo = 0
            
            # Extrair custos por estado (simplificado)
            custos = {}
            
            # Iterar pelas colunas mapeadas
            for col_name, loc_info in estados_localidades.items():
                if col_name in row.index:
                    custo = row[col_name]
                    
                    if pd.notna(custo):
                        try:
                            custo_valor = float(custo)
                            if custo_valor > 0:  # Ignorar zeros
                                estado = loc_info['estado']
                                # Simplificar: apenas estado -> valor (sem localidade)
                                custos[estado] = custo_valor
                        except (ValueError, TypeError):
                            pass
            
            # Criar registro processado
            # Converter código para inteiro ou None
            codigo_final = None
            if codigo > 0:
                try:
                    codigo_final = int(codigo)
                except (ValueError, TypeError):
                    codigo_final = None
            
            processed_row = {
                'codigo': codigo_final,
                'categoria': str(categoria).strip() if pd.notna(categoria) else '',
                'descricao': str(descricao).strip(),
                'unidade': str(unidade).strip(),
                'custos': custos,
                'referencia': reference,
                'arquivo_origem': file_name,
                'aba': sheet_name,
                'tipo_desoneracao': 'SEM DESONERACAO' if sheet_name == 'CSD' else 'COM DESONERACAO'
            }
            
            processed_rows.append(processed_row)
        
        # Criar DataFrame processado
        if processed_rows:
            processed_df = pd.DataFrame(processed_rows)
        else:
            # Se não processou nada, retornar DataFrame vazio com estrutura correta
            processed_df = pd.DataFrame(columns=['codigo', 'categoria', 'descricao', 'unidade', 'custos', 
                                                  'referencia', 'arquivo_origem', 'aba', 'tipo_desoneracao'])
        
        return processed_df
    
    def process_insumos_sheet(self, df: pd.DataFrame, reference: str, file_name: str, sheet_name: str) -> pd.DataFrame:
        """
        Processa as abas ISD e ICD de forma especial, extraindo preços por localidade
        
        Args:
            df: DataFrame da aba ISD ou ICD
            reference: Referência do mês/ano
            file_name: Nome do arquivo origem
            sheet_name: Nome da aba (ISD ou ICD)
            
        Returns:
            DataFrame processado com preços estruturados
        """
        # Limpar nomes de colunas
        df.columns = [self.clean_column_name(col) for col in df.columns]
        
        # Remover linhas completamente vazias
        df = df.dropna(how='all')
        
        # Encontrar linhas de cabeçalho
        estados_row = None
        localidades_row = None
        classificacao_row = None
        
        for idx, row in df.iterrows():
            row_values = [str(v).upper() if pd.notna(v) else '' for v in row.values]
            # Procurar linha com estados (contém "AC", "AL", etc.)
            if 'AC' in row_values and 'AL' in row_values and 'AM' in row_values:
                # Verificar se é a linha de estados (não a de classificação)
                if 'CLASSIFICAÇÃO' not in row_values and 'CODIGO' not in row_values:
                    estados_row = idx
            # Procurar linha com localidades
            if 'RIO BRANCO' in row_values or 'MACEIO' in row_values or 'LOCALIDADE' in row_values:
                localidades_row = idx
            # Procurar linha de classificação (última linha de cabeçalho)
            if 'CLASSIFICAÇÃO' in row_values or 'CODIGO' in row_values:
                classificacao_row = idx
        
        # Mapear estados e localidades
        # Estados e localidades começam em unnamed_5 (índice 4)
        estados_localidades = {}
        
        if estados_row is not None and localidades_row is not None:
            estados_data = df.iloc[estados_row]
            localidades_data = df.iloc[localidades_row]
            
            # Iterar por todas as colunas a partir de unnamed_5
            for col_idx in range(len(df.columns)):
                col_name = df.columns[col_idx]
                
                # Pegar valores das linhas de estados e localidades
                estado_val = estados_data.iloc[col_idx] if col_idx < len(estados_data) else None
                localidade_val = localidades_data.iloc[col_idx] if col_idx < len(localidades_data) else None
                
                if pd.notna(estado_val) and pd.notna(localidade_val):
                    estado_str = str(estado_val).strip().upper()
                    localidade_str = str(localidade_val).strip()
                    
                    # Validar estado (2 letras) e localidade (não vazia)
                    if len(estado_str) == 2 and estado_str.isalpha() and localidade_str:
                        estados_localidades[col_name] = {
                            'estado': estado_str,
                            'localidade': localidade_str
                        }
        
        # Remover linhas de cabeçalho (até a linha de classificação + 1)
        start_idx = (classificacao_row if classificacao_row is not None else localidades_row) + 1 if localidades_row is not None else 0
        df = df.iloc[start_idx:].copy()
        df = df.reset_index(drop=True)
        
        # Processar linhas de dados
        processed_rows = []
        
        for idx, row in df.iterrows():
            # Verificar se é uma linha de dados (tem código e descrição)
            codigo = row.get('unnamed_1', '')
            descricao = row.get('unnamed_2', '')
            unidade = row.get('unnamed_3', '')
            
            # Filtrar linhas de cabeçalho ou vazias
            if pd.isna(codigo) or pd.isna(descricao) or not str(descricao).strip():
                continue
            
            # Tentar converter código para número
            try:
                codigo_int = int(float(codigo)) if pd.notna(codigo) else None
            except (ValueError, TypeError):
                continue  # Se não conseguir converter, não é uma linha de dados válida
            
            if codigo_int is None or codigo_int == 0:
                continue
            
            # Extrair dados do insumo
            categoria = row.get('sinapi_sistema_nacional_de_pesquisa_de_custos_e_índices_da_construção_civil', '')
            origem_preco = row.get('unnamed_4', '')
            
            # Extrair preços por estado (simplificado)
            precos = {}
            
            # Iterar pelas colunas mapeadas
            for col_name, loc_info in estados_localidades.items():
                if col_name in row.index:
                    preco = row[col_name]
                    
                    if pd.notna(preco):
                        try:
                            preco_valor = float(preco)
                            if preco_valor > 0:  # Ignorar zeros
                                estado = loc_info['estado']
                                # Simplificar: apenas estado -> valor (sem localidade)
                                precos[estado] = preco_valor
                        except (ValueError, TypeError):
                            pass
            
            # Criar registro processado
            processed_row = {
                'codigo': codigo_int,
                'categoria': str(categoria).strip() if pd.notna(categoria) else '',
                'descricao': str(descricao).strip(),
                'unidade': str(unidade).strip() if pd.notna(unidade) else '',
                'origem_preco': str(origem_preco).strip() if pd.notna(origem_preco) else '',
                'precos': precos,
                'referencia': reference,
                'arquivo_origem': file_name,
                'aba': sheet_name,
                'tipo_desoneracao': 'SEM DESONERACAO' if sheet_name == 'ISD' else 'COM DESONERACAO'
            }
            
            processed_rows.append(processed_row)
        
        # Criar DataFrame processado
        if processed_rows:
            processed_df = pd.DataFrame(processed_rows)
        else:
            # Se não processou nada, retornar DataFrame vazio com estrutura correta
            processed_df = pd.DataFrame(columns=['codigo', 'categoria', 'descricao', 'unidade', 'origem_preco', 
                                                  'precos', 'referencia', 'arquivo_origem', 'aba', 'tipo_desoneracao'])
        
        return processed_df
    
    def clean_column_name(self, col_name: str) -> str:
        """
        Limpa e padroniza nomes de colunas
        
        Args:
            col_name: Nome da coluna original
            
        Returns:
            Nome da coluna limpo
        """
        # Converter para string e remover espaços extras
        col_name = str(col_name).strip()
        
        # Remover caracteres especiais e substituir espaços por underscore
        col_name = re.sub(r'[^\w\s]', '', col_name)
        col_name = re.sub(r'\s+', '_', col_name)
        
        # Converter para minúsculas
        col_name = col_name.lower()
        
        return col_name
    
    def process_excel_file(self, file_path: Path, reference: str, 
                          required_sheets: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        """
        Processa um arquivo Excel do SINAPI, filtrando apenas as abas especificadas
        
        Args:
            file_path: Caminho do arquivo Excel
            reference: Referência do mês/ano (ex: "2025-12")
            required_sheets: Lista de abas a processar (None = usar REQUIRED_SHEETS)
            
        Returns:
            Dicionário com nome da aba como chave e DataFrame como valor
        """
        if required_sheets is None:
            required_sheets = self.REQUIRED_SHEETS
        
        print(f"[PROCESSANDO] {file_path.name}")
        
        try:
            # Ler todas as abas do Excel
            xls = pd.ExcelFile(file_path)
            available_sheets = xls.sheet_names
            processed_sheets = {}
            
            print(f"   Abas disponiveis: {available_sheets}")
            print(f"   Abas a processar: {required_sheets}")
            
            # Verificar quais abas requeridas estão disponíveis
            sheets_to_process = [s for s in required_sheets if s in available_sheets]
            missing_sheets = [s for s in required_sheets if s not in available_sheets]
            
            if missing_sheets:
                print(f"   [AVISO] Abas nao encontradas: {missing_sheets}")
            
            if not sheets_to_process:
                print(f"   [ERRO] Nenhuma das abas requeridas foi encontrada!")
                return processed_sheets
            
            for sheet_name in sheets_to_process:
                print(f"   Processando aba: {sheet_name}")
                
                try:
                    # Ler aba
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # Processamento especial para abas específicas
                    if sheet_name == 'Analítico':
                        df = self.process_analitico_sheet(df, reference, file_path.name)
                    elif sheet_name in ['CSD', 'CCD']:
                        df = self.process_custos_sheet(df, reference, file_path.name, sheet_name)
                    elif sheet_name in ['ISD', 'ICD']:
                        df = self.process_insumos_sheet(df, reference, file_path.name, sheet_name)
                    else:
                        # Processamento padrão para outras abas
                        # Limpar nomes de colunas
                        df.columns = [self.clean_column_name(col) for col in df.columns]
                        
                        # Remover linhas completamente vazias
                        df = df.dropna(how='all')
                        
                        # Remover colunas completamente vazias
                        df = df.dropna(axis=1, how='all')
                        
                        # Resetar índice
                        df = df.reset_index(drop=True)
                        
                        # Adicionar coluna de referência
                        df['referencia'] = reference
                        
                        # Adicionar coluna de origem
                        df['arquivo_origem'] = file_path.name
                        
                        # Adicionar coluna de aba
                        df['aba'] = sheet_name
                    
                    processed_sheets[sheet_name] = df
                    
                    print(f"      [OK] {len(df)} linhas, {len(df.columns)} colunas processadas")
                    
                except Exception as e:
                    print(f"      [ERRO] Erro ao processar aba {sheet_name}: {e}")
                    continue
            
            return processed_sheets
            
        except Exception as e:
            print(f"   [ERRO] Erro ao processar arquivo: {e}")
            raise
    
    def enrich_custos_with_codes(self, custos_df: pd.DataFrame, analitico_df: pd.DataFrame) -> pd.DataFrame:
        """
        Enriquece os dados de custos com códigos recuperados do arquivo Analítico
        
        Args:
            custos_df: DataFrame com dados de custos (CSD ou CCD)
            analitico_df: DataFrame da aba Analítico
            
        Returns:
            DataFrame enriquecido com códigos
        """
        # Criar mapeamentos do Analítico: (descricao, unidade) -> codigo e descricao -> codigo (fallback)
        descricao_unidade_to_codigo = {}
        descricao_to_codigo = {}
        
        if 'descricao' in analitico_df.columns and 'codigo_composicao_mae' in analitico_df.columns:
            composicoes_mae = analitico_df[analitico_df['tipo_item'] == 'COMPOSICAO_MAE']
            
            for _, row in composicoes_mae.iterrows():
                desc = str(row.get('descricao', '')).strip().upper()
                unidade = str(row.get('unidade', '')).strip().upper()
                codigo = row.get('codigo_composicao_mae')
                if desc and pd.notna(codigo):
                    descricao_unidade_to_codigo[(desc, unidade)] = int(codigo)
                    descricao_to_codigo[desc] = int(codigo)
        
        if 'descricao' in custos_df.columns:
            def get_code(row):
                codigo_atual = row.get('codigo')
                if pd.notna(codigo_atual) and codigo_atual != 0 and codigo_atual != '0':
                    try:
                        codigo_int = int(float(codigo_atual))
                        if codigo_int > 0:
                            return codigo_int
                    except (ValueError, TypeError):
                        pass
                
                desc = str(row.get('descricao', '')).strip().upper()
                unidade = str(row.get('unidade', '')).strip().upper()
                
                # Lookup por (descricao, unidade) para distinguir itens com mesma descricao
                if (desc, unidade) in descricao_unidade_to_codigo:
                    return descricao_unidade_to_codigo[(desc, unidade)]
                
                # Fallback: lookup apenas por descricao
                if desc in descricao_to_codigo:
                    return descricao_to_codigo[desc]
                
                return None
            
            custos_df['codigo'] = custos_df.apply(get_code, axis=1)
            
            custos_df['codigo'] = custos_df['codigo'].apply(
                lambda x: int(x) if pd.notna(x) and x != 0 else None
            )
        
        return custos_df
    
    def process_all_files(self, extracted_files: List[Path], reference: str) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Processa apenas o arquivo SINAPI_Referência dos arquivos extraídos
        
        Args:
            extracted_files: Lista de caminhos dos arquivos extraídos
            reference: Referência do mês/ano
            
        Returns:
            Dicionário com nome do arquivo como chave e dicionário de abas como valor
        """
        all_processed = {}
        
        # Filtrar apenas arquivo SINAPI_Referência
        referencia_files = [
            f for f in extracted_files 
            if f.suffix == '.xlsx' and 'Referência' in f.name or 'Referencia' in f.name
        ]
        
        if not referencia_files:
            print("[AVISO] Arquivo SINAPI_Referencia nao encontrado nos arquivos extraidos!")
            print(f"   Arquivos disponiveis: {[f.name for f in extracted_files if f.suffix == '.xlsx']}")
            return all_processed
        
        # Processar apenas o primeiro arquivo de referência encontrado
        file_path = referencia_files[0]
        print(f"\n[PROCESSANDO] Arquivo de referencia: {file_path.name}")
        
        try:
            processed = self.process_excel_file(file_path, reference)
            if processed:
                # Enriquecer CSD e CCD com códigos do Analítico
                if 'Analítico' in processed:
                    analitico_df = processed['Analítico']
                    
                    for sheet_name in ['CSD', 'CCD']:
                        if sheet_name in processed:
                            print(f"   [ENRIQUECENDO] Recuperando codigos para {sheet_name}...")
                            processed[sheet_name] = self.enrich_custos_with_codes(
                                processed[sheet_name],
                                analitico_df
                            )
                            # Contar quantos códigos foram recuperados
                            codigos_recuperados = processed[sheet_name]['codigo'].notna().sum()
                            total = len(processed[sheet_name])
                            print(f"      [OK] {codigos_recuperados} de {total} codigos recuperados")
                
                all_processed[file_path.stem] = processed
        except Exception as e:
            print(f"[ERRO] Erro ao processar {file_path.name}: {e}")
            import traceback
            traceback.print_exc()
        
        return all_processed
    
    def structure_analitico_hierarchical(self, df: pd.DataFrame) -> List[Dict]:
        """
        Estrutura os dados da aba Analítico de forma hierárquica,
        agrupando composições filhas e insumos dentro de cada composição mãe
        
        Args:
            df: DataFrame da aba Analítico processada
            
        Returns:
            Lista de dicionários com estrutura hierárquica
        """
        hierarchical_data = []
        
        # Agrupar por código da composição mãe
        for codigo_mae, group in df.groupby('codigo_composicao_mae'):
            # Encontrar a linha da composição mãe (tipo_item == 'COMPOSICAO_MAE')
            composicao_mae_rows = group[group['tipo_item'] == 'COMPOSICAO_MAE']
            
            if len(composicao_mae_rows) == 0:
                continue
            
            composicao_mae = composicao_mae_rows.iloc[0]
            
            # Criar estrutura da composição mãe
            composicao = {
                'codigo': int(codigo_mae),
                'categoria': str(composicao_mae.get('categoria', '')) if pd.notna(composicao_mae.get('categoria')) else '',
                'descricao': str(composicao_mae.get('descricao', '')) if pd.notna(composicao_mae.get('descricao')) else '',
                'unidade': str(composicao_mae.get('unidade', '')) if pd.notna(composicao_mae.get('unidade')) else '',
                'situacao': str(composicao_mae.get('situacao', '')) if pd.notna(composicao_mae.get('situacao')) else '',
                'referencia': str(composicao_mae.get('referencia', '')),
                'componentes': []
            }
            
            # Adicionar componentes (composições filhas e insumos)
            # Filtrar apenas itens que não são a composição mãe
            componentes = group[group['tipo_item'].isin(['COMPOSICAO', 'INSUMO'])]
            
            for _, componente in componentes.iterrows():
                item = {
                    'tipo': str(componente['tipo_item']),
                    'codigo': int(componente['codigo_item_filho']) if pd.notna(componente['codigo_item_filho']) else None,
                    'descricao': str(componente.get('descricao', '')) if pd.notna(componente.get('descricao')) else '',
                    'unidade': str(componente.get('unidade', '')) if pd.notna(componente.get('unidade')) else '',
                    'coeficiente': float(componente['coeficiente']) if pd.notna(componente['coeficiente']) else None,
                    'situacao': str(componente.get('situacao', '')) if pd.notna(componente.get('situacao')) else ''
                }
                composicao['componentes'].append(item)
            
            hierarchical_data.append(composicao)
        
        return hierarchical_data
    
    def save_processed_data(self, processed_data: Dict[str, Dict[str, pd.DataFrame]], 
                           reference: str, formats: List[str] = ['json', 'csv']) -> List[Path]:
        """
        Salva os dados processados em arquivos JSON e CSV
        
        Args:
            processed_data: Dados processados
            reference: Referência do mês/ano
            formats: Lista de formatos de saída (padrão: ['json', 'csv'])
            
        Returns:
            Lista de caminhos dos arquivos salvos
        """
        saved_files = []
        reference_dir = self.output_dir / reference
        reference_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[SALVANDO] Dados processados em: {reference_dir}")
        print(f"   Formatos: {', '.join(formats)}")
        
        for file_name, sheets in processed_data.items():
            for sheet_name, df in sheets.items():
                # Criar nome base do arquivo de saída
                safe_sheet_name = re.sub(r'[^\w\s-]', '', sheet_name).replace(' ', '_').lower()
                base_filename = f"{safe_sheet_name}"
                
                # Salvar em cada formato solicitado
                for fmt in formats:
                    if fmt == 'json':
                        output_filename = f"{base_filename}.json"
                        output_path = reference_dir / output_filename
                        
                        try:
                            # Para aba Analítico, usar estrutura hierárquica
                            if sheet_name == 'Analítico':
                                json_data = self.structure_analitico_hierarchical(df)
                            elif sheet_name in ['CSD', 'CCD', 'ISD', 'ICD']:
                                # Para CSD, CCD, ISD e ICD, garantir que códigos sejam inteiros no JSON
                                json_data = df.to_dict(orient='records')
                                # Converter códigos float para int ou None
                                for record in json_data:
                                    if 'codigo' in record:
                                        codigo = record['codigo']
                                        if pd.notna(codigo) and codigo is not None:
                                            try:
                                                record['codigo'] = int(float(codigo))
                                            except (ValueError, TypeError):
                                                record['codigo'] = None
                                        else:
                                            record['codigo'] = None
                            else:
                                # Para outras abas, usar formato padrão
                                json_data = df.to_dict(orient='records')
                            
                            with open(output_path, 'w', encoding='utf-8') as f:
                                json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
                            
                            saved_files.append(output_path)
                            
                            if sheet_name == 'Analítico':
                                print(f"   [OK] {output_filename} ({len(json_data)} composicoes hierarquicas)")
                            else:
                                print(f"   [OK] {output_filename} ({len(json_data)} registros)")
                            
                        except Exception as e:
                            print(f"   [ERRO] Erro ao salvar {output_filename}: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    elif fmt == 'csv':
                        output_filename = f"{base_filename}.csv"
                        output_path = reference_dir / output_filename
                        
                        try:
                            df.to_csv(output_path, index=False, encoding='utf-8-sig')
                            saved_files.append(output_path)
                            print(f"   [OK] {output_filename} ({len(df)} linhas)")
                            
                        except Exception as e:
                            print(f"   [ERRO] Erro ao salvar {output_filename}: {e}")
                    
                    elif fmt == 'parquet':
                        output_filename = f"{base_filename}.parquet"
                        output_path = reference_dir / output_filename
                        
                        try:
                            df.to_parquet(output_path, index=False)
                            saved_files.append(output_path)
                            print(f"   [OK] {output_filename} ({len(df)} linhas)")
                            
                        except Exception as e:
                            print(f"   [ERRO] Erro ao salvar {output_filename}: {e}")
                    
                    elif fmt == 'xlsx':
                        output_filename = f"{base_filename}.xlsx"
                        output_path = reference_dir / output_filename
                        
                        try:
                            df.to_excel(output_path, index=False)
                            saved_files.append(output_path)
                            print(f"   [OK] {output_filename} ({len(df)} linhas)")
                            
                        except Exception as e:
                            print(f"   [ERRO] Erro ao salvar {output_filename}: {e}")
        
        return saved_files
