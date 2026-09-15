"""
Módulo para integração com Supabase
Carrega dados processados do ETL para o banco de dados Supabase
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
from supabase import create_client, Client
from dotenv import load_dotenv
from postgrest.exceptions import APIError

# Carregar variáveis de ambiente
load_dotenv()


def resolve_supabase_credentials(
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    URL e API key para operações server-side (ETL, scripts).

    Com RLS ativo, a chave **anon** falha em INSERT/UPDATE/DELETE sem políticas
    permissivas. A documentação do Supabase recomenda a **service_role** só
    em backend seguro — ela contorna RLS.

    Ordem: parâmetro `supabase_key` explícito; depois SUPABASE_SERVICE_ROLE_KEY;
    por último SUPABASE_KEY (compatível com projetos antigos).

    Returns:
        (url, key, usou_service_role_env) — o terceiro é True apenas quando a key
        veio de SUPABASE_SERVICE_ROLE_KEY (não quando foi passada no construtor).
    """
    url = supabase_url or os.getenv("SUPABASE_URL")
    if supabase_key:
        return url, supabase_key, False
    svc = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if svc:
        return url, svc, True
    return url, os.getenv("SUPABASE_KEY"), False


def resolve_supabase_schema(schema: Optional[str] = None) -> str:
    """
    Schema PostgreSQL das tabelas SINAPI.

    Ordem: parâmetro explícito; depois SUPABASE_SCHEMA; padrão ``public``.
    """
    if schema:
        return schema
    return os.getenv("SUPABASE_SCHEMA", "public")


class SupabaseLoader:
    """Classe para carregar dados SINAPI processados no Supabase"""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        """
        Inicializa o loader do Supabase

        Args:
            supabase_url: URL do projeto Supabase (ou usa SUPABASE_URL do .env)
            supabase_key: Chave explícita; se omitida, usa SUPABASE_SERVICE_ROLE_KEY
                ou SUPABASE_KEY (ver resolve_supabase_credentials).
            schema: Schema PostgreSQL (padrão: public ou SUPABASE_SCHEMA).
        """
        self.SCHEMA = resolve_supabase_schema(schema)
        self.supabase_url, self.supabase_key, used_service_from_env = resolve_supabase_credentials(
            supabase_url, supabase_key
        )

        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "Credenciais do Supabase não encontradas. "
                "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY (recomendado com RLS) "
                "ou SUPABASE_KEY no .env, ou passe url/key ao construtor."
            )

        if not supabase_key and not used_service_from_env:
            print(
                "[SUPABASE] Aviso: defina SUPABASE_SERVICE_ROLE_KEY no .env para o ETL. "
                "A chave anon costuma falhar com RLS (erro 42501)."
            )

        # Criar cliente Supabase
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Cache de IDs para evitar consultas repetidas
        self._referencia_cache: Dict[str, str] = {}
        self._insumo_cache: Dict[tuple, str] = {}  # (codigo, unidade, referencia_id) -> id
        self._composicao_cache: Dict[tuple, str] = {}  # (codigo, unidade, referencia_id) -> id
    
    def _table(self, table_name: str):
        """
        Retorna a referência da tabela no schema correto
        
        Args:
            table_name: Nome da tabela sem o schema
            
        Returns:
            Referência da tabela no schema configurado (padrão: public)
        """
        # Usar .schema() para especificar o schema antes de .table()
        return self.client.schema(self.SCHEMA).table(table_name)
    
    def get_or_create_referencia(self, referencia: str, data_publicacao: Optional[date] = None) -> str:
        """
        Obtém ou cria uma referência SINAPI
        
        Args:
            referencia: String de referência (ex: "2025-12")
            data_publicacao: Data de publicação (opcional)
            
        Returns:
            UUID da referência
        """
        # Verificar cache
        if referencia in self._referencia_cache:
            return self._referencia_cache[referencia]
        
        # Buscar referência existente
        response = self._table('sinapi_referencias').select('id').eq('referencia', referencia).execute()
        
        if response.data:
            referencia_id = response.data[0]['id']
            self._referencia_cache[referencia] = referencia_id
            return referencia_id
        
        # Criar nova referência
        data = {
            'referencia': referencia,
            'data_publicacao': data_publicacao.isoformat() if data_publicacao else None
        }
        
        response = self._table('sinapi_referencias').insert(data).execute()
        
        if not response.data:
            raise Exception(f"Erro ao criar referência {referencia}")
        
        referencia_id = response.data[0]['id']
        self._referencia_cache[referencia] = referencia_id
        return referencia_id
    
    def load_insumos(self, referencia: str, isd_data: List[Dict], icd_data: List[Dict]) -> Dict[tuple, str]:
        """
        Carrega insumos (ISD e ICD) no banco de dados
        
        Args:
            referencia: Referência do mês/ano
            isd_data: Lista de insumos sem desoneração
            icd_data: Lista de insumos com desoneração
            
        Returns:
            Dicionário mapeando (codigo, unidade, referencia_id) -> insumo_id
        """
        referencia_id = self.get_or_create_referencia(referencia)
        
        # Combinar ISD e ICD, removendo duplicatas por (codigo, unidade)
        insumos_map: Dict[tuple, Dict] = {}
        
        for item in isd_data + icd_data:
            codigo = item.get('codigo')
            unidade = item.get('unidade', '')
            key = (codigo, unidade)
            if codigo and key not in insumos_map:
                insumos_map[key] = {
                    'codigo': int(codigo),
                    'categoria': item.get('categoria', ''),
                    'descricao': item.get('descricao', ''),
                    'unidade': unidade,
                    'referencia_id': referencia_id
                }
        
        # Verificar quais insumos já existem (em lotes para evitar limite de query)
        codigos = list(set(int(codigo) for codigo, unidade in insumos_map.keys()))
        existing_map = {}
        insumo_id_map = {}
        
        # Consultar em lotes de 100 códigos por vez (limite seguro para PostgREST)
        query_batch_size = 100
        for i in range(0, len(codigos), query_batch_size):
            codigos_batch = codigos[i:i + query_batch_size]
            try:
                existing_response = self._table('insumos').select('id, codigo, unidade').eq('referencia_id', referencia_id).in_('codigo', codigos_batch).execute()
                
                for insumo in existing_response.data:
                    codigo = insumo['codigo']
                    unidade = insumo.get('unidade', '')
                    existing_map[(codigo, unidade)] = insumo['id']
                    insumo_id_map[(codigo, unidade, referencia_id)] = insumo['id']
                    self._insumo_cache[(codigo, unidade, referencia_id)] = insumo['id']
            except Exception as e:
                print(f"   [AVISO] Erro ao verificar insumos existentes (lote {i//query_batch_size + 1}): {e}")
                # Continuar mesmo se houver erro em um lote
        
        # Filtrar apenas insumos novos
        novos_insumos = [
            insumo for insumo in insumos_map.values() 
            if (insumo['codigo'], insumo['unidade']) not in existing_map
        ]
        
        if novos_insumos:
            # Inserir em lotes de 1000 para evitar problemas de tamanho
            batch_size = 1000
            
            for i in range(0, len(novos_insumos), batch_size):
                batch = novos_insumos[i:i + batch_size]
                response = self._table('insumos').insert(batch).execute()
                
                for insumo in response.data:
                    codigo = insumo['codigo']
                    unidade = insumo.get('unidade', '')
                    insumo_id_map[(codigo, unidade, referencia_id)] = insumo['id']
                    self._insumo_cache[(codigo, unidade, referencia_id)] = insumo['id']
        
        total = len(insumo_id_map)
        novos = len(novos_insumos)
        existentes = total - novos
        
        if novos > 0:
            print(f"   [OK] {total} insumos ({novos} novos, {existentes} já existentes)")
        else:
            print(f"   [OK] {total} insumos (todos já existentes)")
        
        return insumo_id_map
    
    def load_insumo_custos(self, referencia: str, isd_data: List[Dict], icd_data: List[Dict], 
                          insumo_id_map: Dict[tuple, str]):
        """
        Carrega custos de insumos por UF e tipo de desoneração
        
        Args:
            referencia: Referência do mês/ano
            isd_data: Lista de insumos sem desoneração
            icd_data: Lista de insumos com desoneração
            insumo_id_map: Mapa de (codigo, unidade, referencia_id) -> insumo_id
        """
        referencia_id = self.get_or_create_referencia(referencia)
        custos_list = []
        
        # Processar ISD (SEM DESONERAÇÃO)
        for item in isd_data:
            codigo = item.get('codigo')
            if not codigo:
                continue
            
            unidade = item.get('unidade', '')
            insumo_id = insumo_id_map.get((int(codigo), unidade, referencia_id))
            if not insumo_id:
                continue
            
            precos = item.get('precos', {})
            for uf, custo in precos.items():
                if custo is not None:
                    custos_list.append({
                        'insumo_id': insumo_id,
                        'uf': uf,
                        'tipo_desoneracao': 'SEM',
                        'custo': float(custo)
                    })
        
        # Processar ICD (COM DESONERAÇÃO)
        for item in icd_data:
            codigo = item.get('codigo')
            if not codigo:
                continue
            
            unidade = item.get('unidade', '')
            insumo_id = insumo_id_map.get((int(codigo), unidade, referencia_id))
            if not insumo_id:
                continue
            
            precos = item.get('precos', {})
            for uf, custo in precos.items():
                if custo is not None:
                    custos_list.append({
                        'insumo_id': insumo_id,
                        'uf': uf,
                        'tipo_desoneracao': 'COM',
                        'custo': float(custo)
                    })
        
        # Remover duplicatas dentro da lista (manter o último valor em caso de duplicata)
        # Usar uma chave composta (insumo_id, tipo_desoneracao, uf)
        custos_dedup = {}
        for custo in custos_list:
            key = (custo['insumo_id'], custo['tipo_desoneracao'], custo['uf'])
            custos_dedup[key] = custo
        
        custos_list = list(custos_dedup.values())
        
        # Inserir em lotes (usar upsert para evitar duplicatas)
        if custos_list:
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(custos_list), batch_size):
                batch = custos_list[i:i + batch_size]
                
                # Garantir que não há duplicatas dentro do batch
                batch_dedup = {}
                for custo in batch:
                    key = (custo['insumo_id'], custo['tipo_desoneracao'], custo['uf'])
                    batch_dedup[key] = custo
                
                batch = list(batch_dedup.values())
                
                if batch:  # Só inserir se houver itens após deduplicação
                    # Usar upsert para atualizar se já existir ou inserir se não existir
                    self._table('insumo_custos').upsert(batch, on_conflict='insumo_id,tipo_desoneracao,uf').execute()
                    total_inserted += len(batch)
            
            print(f"   [OK] {total_inserted} custos de insumos inseridos/atualizados")
    
    def load_composicoes(self, referencia: str, csd_data: List[Dict], ccd_data: List[Dict]) -> Dict[tuple, str]:
        """
        Carrega composições (CSD e CCD) no banco de dados
        
        Args:
            referencia: Referência do mês/ano
            csd_data: Lista de composições sem desoneração
            ccd_data: Lista de composições com desoneração
            
        Returns:
            Dicionário mapeando (codigo, unidade, referencia_id) -> composicao_id
        """
        referencia_id = self.get_or_create_referencia(referencia)
        
        # Combinar CSD e CCD, removendo duplicatas por (codigo, unidade)
        composicoes_map: Dict[tuple, Dict] = {}
        
        for item in csd_data + ccd_data:
            codigo = item.get('codigo')
            unidade = item.get('unidade', '')
            key = (codigo, unidade)
            if codigo and key not in composicoes_map:
                composicoes_map[key] = {
                    'codigo': int(codigo),
                    'categoria': item.get('categoria', ''),
                    'descricao': item.get('descricao', ''),
                    'unidade': unidade,
                    'referencia_id': referencia_id
                }
        
        # Verificar quais composições já existem (em lotes para evitar limite de query)
        codigos = list(set(int(codigo) for codigo, unidade in composicoes_map.keys()))
        existing_map = {}
        composicao_id_map = {}
        
        # Consultar em lotes de 100 códigos por vez (limite seguro para PostgREST)
        query_batch_size = 100
        for i in range(0, len(codigos), query_batch_size):
            codigos_batch = codigos[i:i + query_batch_size]
            try:
                existing_response = self._table('composicoes').select('id, codigo, unidade').eq('referencia_id', referencia_id).in_('codigo', codigos_batch).execute()
                
                for composicao in existing_response.data:
                    codigo = composicao['codigo']
                    unidade = composicao.get('unidade', '')
                    existing_map[(codigo, unidade)] = composicao['id']
                    composicao_id_map[(codigo, unidade, referencia_id)] = composicao['id']
                    self._composicao_cache[(codigo, unidade, referencia_id)] = composicao['id']
            except Exception as e:
                print(f"   [AVISO] Erro ao verificar composições existentes (lote {i//query_batch_size + 1}): {e}")
                # Continuar mesmo se houver erro em um lote
        
        # Filtrar apenas composições novas
        novas_composicoes = [
            comp for comp in composicoes_map.values() 
            if (comp['codigo'], comp['unidade']) not in existing_map
        ]
        
        if novas_composicoes:
            # Inserir em lotes de 1000
            batch_size = 1000
            
            for i in range(0, len(novas_composicoes), batch_size):
                batch = novas_composicoes[i:i + batch_size]
                response = self._table('composicoes').insert(batch).execute()
                
                for composicao in response.data:
                    codigo = composicao['codigo']
                    unidade = composicao.get('unidade', '')
                    composicao_id_map[(codigo, unidade, referencia_id)] = composicao['id']
                    self._composicao_cache[(codigo, unidade, referencia_id)] = composicao['id']
        
        total = len(composicao_id_map)
        novas = len(novas_composicoes)
        existentes = total - novas
        
        if novas > 0:
            print(f"   [OK] {total} composições ({novas} novas, {existentes} já existentes)")
        else:
            print(f"   [OK] {total} composições (todas já existentes)")
        
        return composicao_id_map
    
    def load_composicao_custos(self, referencia: str, csd_data: List[Dict], ccd_data: List[Dict],
                               composicao_id_map: Dict[tuple, str]):
        """
        Carrega custos de composições por UF e tipo de desoneração
        
        Args:
            referencia: Referência do mês/ano
            csd_data: Lista de composições sem desoneração
            ccd_data: Lista de composições com desoneração
            composicao_id_map: Mapa de (codigo, unidade, referencia_id) -> composicao_id
        """
        referencia_id = self.get_or_create_referencia(referencia)
        custos_list = []
        
        # Processar CSD (SEM DESONERAÇÃO)
        for item in csd_data:
            codigo = item.get('codigo')
            if not codigo:
                continue
            
            unidade = item.get('unidade', '')
            composicao_id = composicao_id_map.get((int(codigo), unidade, referencia_id))
            if not composicao_id:
                continue
            
            custos = item.get('custos', {})
            for uf, custo in custos.items():
                if custo is not None:
                    custos_list.append({
                        'composicao_id': composicao_id,
                        'uf': uf,
                        'tipo_desoneracao': 'SEM',
                        'custo': float(custo)
                    })
        
        # Processar CCD (COM DESONERAÇÃO)
        for item in ccd_data:
            codigo = item.get('codigo')
            if not codigo:
                continue
            
            unidade = item.get('unidade', '')
            composicao_id = composicao_id_map.get((int(codigo), unidade, referencia_id))
            if not composicao_id:
                continue
            
            custos = item.get('custos', {})
            for uf, custo in custos.items():
                if custo is not None:
                    custos_list.append({
                        'composicao_id': composicao_id,
                        'uf': uf,
                        'tipo_desoneracao': 'COM',
                        'custo': float(custo)
                    })
        
        # Remover duplicatas dentro da lista (manter o último valor em caso de duplicata)
        # Usar uma chave composta (composicao_id, tipo_desoneracao, uf)
        custos_dedup = {}
        for custo in custos_list:
            key = (custo['composicao_id'], custo['tipo_desoneracao'], custo['uf'])
            custos_dedup[key] = custo
        
        custos_list = list(custos_dedup.values())
        
        # Inserir em lotes (usar upsert para evitar duplicatas)
        if custos_list:
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(custos_list), batch_size):
                batch = custos_list[i:i + batch_size]
                
                # Garantir que não há duplicatas dentro do batch
                batch_dedup = {}
                for custo in batch:
                    key = (custo['composicao_id'], custo['tipo_desoneracao'], custo['uf'])
                    batch_dedup[key] = custo
                
                batch = list(batch_dedup.values())
                
                if batch:  # Só inserir se houver itens após deduplicação
                    # Usar upsert para atualizar se já existir ou inserir se não existir
                    self._table('composicao_custos').upsert(batch, on_conflict='composicao_id,tipo_desoneracao,uf').execute()
                    total_inserted += len(batch)
            
            print(f"   [OK] {total_inserted} custos de composições inseridos/atualizados")
    
    def load_composicao_analitico(self, referencia: str, analitico_data: List[Dict],
                                  insumo_id_map: Dict[tuple, str],
                                  composicao_id_map: Dict[tuple, str]):
        """
        Carrega relacionamentos analíticos entre composições e seus componentes
        
        Args:
            referencia: Referência do mês/ano
            analitico_data: Lista de composições com seus componentes
            insumo_id_map: Mapa de (codigo, unidade, referencia_id) -> insumo_id
            composicao_id_map: Mapa de (codigo, unidade, referencia_id) -> composicao_id
        """
        referencia_id = self.get_or_create_referencia(referencia)
        analitico_list = []
        
        for composicao in analitico_data:
            codigo_pai = composicao.get('codigo')
            if not codigo_pai:
                continue
            
            unidade_pai = composicao.get('unidade', '').strip()
            composicao_pai_id = composicao_id_map.get((int(codigo_pai), unidade_pai, referencia_id))
            if not composicao_pai_id:
                continue
            
            componentes = composicao.get('componentes', [])
            for componente in componentes:
                tipo = componente.get('tipo', '').upper().strip()
                codigo_filho = componente.get('codigo')
                
                if not codigo_filho:
                    continue
                
                # Validar tipo (deve ser 'INSUMO' ou 'COMPOSICAO')
                if tipo not in ['INSUMO', 'COMPOSICAO']:
                    continue
                
                codigo_filho_int = int(codigo_filho)
                coeficiente = componente.get('coeficiente')
                unidade = componente.get('unidade', '').strip()
                
                # Garantir que coeficiente não seja None (tabela exige NOT NULL)
                if coeficiente is None:
                    coeficiente = 0.0
                else:
                    try:
                        coeficiente = float(coeficiente)
                    except (ValueError, TypeError):
                        coeficiente = 0.0
                
                # Garantir que unidade não seja vazia (tabela exige NOT NULL)
                if not unidade:
                    continue
                
                if tipo == 'INSUMO':
                    insumo_id = insumo_id_map.get((codigo_filho_int, unidade, referencia_id))
                    if insumo_id:
                        analitico_list.append({
                            'composicao_pai_id': composicao_pai_id,
                            'insumo_id': insumo_id,
                            'composicao_filha_id': None,
                            'tipo_componente': 'INSUMO',
                            'unidade': unidade,
                            'coeficiente': coeficiente
                        })
                
                elif tipo == 'COMPOSICAO':
                    composicao_filha_id = composicao_id_map.get((codigo_filho_int, unidade, referencia_id))
                    if composicao_filha_id:
                        analitico_list.append({
                            'composicao_pai_id': composicao_pai_id,
                            'insumo_id': None,
                            'composicao_filha_id': composicao_filha_id,
                            'tipo_componente': 'COMPOSICAO',
                            'unidade': unidade,
                            'coeficiente': coeficiente
                        })
        
        # Remover duplicatas (mesma composição pai, mesmo componente, mesmo tipo)
        # Usar uma chave composta (composicao_pai_id, tipo_componente, insumo_id ou composicao_filha_id)
        analitico_dedup = {}
        for item in analitico_list:
            # Criar chave única baseada no tipo e no ID do componente
            if item['tipo_componente'] == 'INSUMO':
                key = (item['composicao_pai_id'], 'INSUMO', item['insumo_id'])
            else:  # COMPOSICAO
                key = (item['composicao_pai_id'], 'COMPOSICAO', item['composicao_filha_id'])
            analitico_dedup[key] = item
        
        analitico_list = list(analitico_dedup.values())
        
        # Inserir em lotes
        if analitico_list:
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(analitico_list), batch_size):
                batch = analitico_list[i:i + batch_size]
                self._table('composicao_analitico').insert(batch).execute()
                total_inserted += len(batch)
            
            print(f"   [OK] {total_inserted} relacionamentos analíticos inseridos")
    
    def load_from_processed_files(self, reference: str, processed_dir: str = "data/processed") -> bool:
        """
        Carrega dados processados do diretório para o Supabase
        
        Args:
            reference: Referência do mês/ano (ex: "2025-12")
            processed_dir: Diretório onde os dados processados estão salvos
            
        Returns:
            True se o processo foi concluído com sucesso
        """
        processed_path = Path(processed_dir) / reference
        
        if not processed_path.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {processed_path}")
        
        print(f"\n[SUPABASE] Carregando dados de {reference} para o Supabase...")
        
        try:
            # Carregar arquivos JSON
            isd_path = processed_path / "isd.json"
            icd_path = processed_path / "icd.json"
            csd_path = processed_path / "csd.json"
            ccd_path = processed_path / "ccd.json"
            analitico_path = processed_path / "analítico.json"
            
            if not all(p.exists() for p in [isd_path, icd_path, csd_path, ccd_path, analitico_path]):
                raise FileNotFoundError("Arquivos JSON processados não encontrados")
            
            print("[SUPABASE] Carregando arquivos JSON...")
            with open(isd_path, 'r', encoding='utf-8') as f:
                isd_data = json.load(f)
            with open(icd_path, 'r', encoding='utf-8') as f:
                icd_data = json.load(f)
            with open(csd_path, 'r', encoding='utf-8') as f:
                csd_data = json.load(f)
            with open(ccd_path, 'r', encoding='utf-8') as f:
                ccd_data = json.load(f)
            with open(analitico_path, 'r', encoding='utf-8') as f:
                analitico_data = json.load(f)
            
            print(f"[SUPABASE] Dados carregados:")
            print(f"   ISD: {len(isd_data)} insumos")
            print(f"   ICD: {len(icd_data)} insumos")
            print(f"   CSD: {len(csd_data)} composições")
            print(f"   CCD: {len(ccd_data)} composições")
            print(f"   Analítico: {len(analitico_data)} composições")
            
            # 1. Criar/obter referência
            print("\n[SUPABASE] Criando/obtendo referência...")
            referencia_id = self.get_or_create_referencia(reference)
            print(f"   [OK] Referência {reference} (ID: {referencia_id})")
            
            # 2. Carregar insumos
            print("\n[SUPABASE] Carregando insumos...")
            insumo_id_map = self.load_insumos(reference, isd_data, icd_data)
            
            # 3. Carregar custos de insumos
            print("\n[SUPABASE] Carregando custos de insumos...")
            self.load_insumo_custos(reference, isd_data, icd_data, insumo_id_map)
            
            # 4. Carregar composições
            print("\n[SUPABASE] Carregando composições...")
            composicao_id_map = self.load_composicoes(reference, csd_data, ccd_data)
            
            # 5. Carregar custos de composições
            print("\n[SUPABASE] Carregando custos de composições...")
            self.load_composicao_custos(reference, csd_data, ccd_data, composicao_id_map)
            
            # 6. Carregar relacionamentos analíticos
            print("\n[SUPABASE] Carregando relacionamentos analíticos...")
            self.load_composicao_analitico(reference, analitico_data, insumo_id_map, composicao_id_map)
            
            print("\n" + "=" * 80)
            print("[SUCESSO] Dados carregados no Supabase com sucesso!")
            print("=" * 80)
            
            return True
            
        except Exception as e:
            print(f"\n[ERRO] Erro ao carregar dados no Supabase: {e}")
            if isinstance(e, APIError) and getattr(e, "code", None) == "42501":
                print(
                    "[SUPABASE] Política RLS bloqueou a operação. Use SUPABASE_SERVICE_ROLE_KEY "
                    "no .env (nunca no browser) ou ajuste as policies para o role adequado."
                )
            import traceback
            traceback.print_exc()
            return False
