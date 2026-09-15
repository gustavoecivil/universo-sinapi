"""
Módulo para download automático dos arquivos SINAPI
"""
import requests
from pathlib import Path
from typing import Optional
from datetime import datetime
import urllib3

# Desabilitar avisos de SSL para tentativas alternativas
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SINAPIDownloader:
    """Classe para realizar download dos arquivos SINAPI"""
    
    BASE_URL = "https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais"
    
    def _validate_zip_file(self, filepath: Path) -> bool:
        """
        Valida se o arquivo é um ZIP válido
        
        Args:
            filepath: Caminho do arquivo a validar
            
        Returns:
            True se válido, False caso contrário
        """
        try:
            import zipfile
            with zipfile.ZipFile(filepath, 'r') as zip_ref:
                zip_ref.testzip()
            return True
        except Exception as e:
            print(f"   [ERRO] Arquivo ZIP invalido ou corrompido: {e}")
            return False
    
    def __init__(self, download_dir: str = "data/downloads"):
        """
        Inicializa o downloader
        
        Args:
            download_dir: Diretório onde os arquivos serão baixados
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def download(self, year: int, month: int) -> Optional[Path]:
        """
        Baixa o arquivo ZIP do SINAPI para o mês/ano especificado
        
        Args:
            year: Ano (ex: 2025)
            month: Mês (ex: 12)
            
        Returns:
            Path do arquivo baixado ou None em caso de erro
        """
        # Formatar mês com zero à esquerda
        month_str = f"{month:02d}"
        
        # Construir nome do arquivo
        filename = f"SINAPI-{year}-{month_str}-formato-xlsx.zip"
        url = f"{self.BASE_URL}/{filename}"
        
        # Caminho completo do arquivo
        filepath = self.download_dir / filename
        
        # Verificar se o arquivo já existe e é válido
        if filepath.exists() and filepath.stat().st_size > 0:
            print(f"[INFO] Arquivo ja existe: {filepath}")
            print(f"   Tamanho: {filepath.stat().st_size / (1024*1024):.2f} MB")
            # Verificar se é um ZIP válido
            if self._validate_zip_file(filepath):
                print(f"[OK] Arquivo existente e valido, usando cache")
                return filepath
            else:
                print(f"[AVISO] Arquivo existente parece corrompido, baixando novamente...")
                filepath.unlink()
        
        print(f"[BAIXANDO] {filename}")
        print(f"   URL: {url}")
        
        try:
            # Headers para simular navegador e evitar bloqueios
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/zip,application/octet-stream,application/x-zip-compressed,*/*;q=0.9',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.caixa.gov.br/',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Cache-Control': 'max-age=0'
            }
            
            # Configurar sessão com cookies persistentes
            session = requests.Session()
            session.headers.update(headers)
            
            # Primeiro, fazer uma requisição à página principal para obter cookies
            try:
                session.get('https://www.caixa.gov.br/', timeout=10, verify=True)
            except:
                pass  # Ignorar erros na requisição inicial
            
            # Fazer requisição com allow_redirects e timeout maior
            # Usar adapter para aumentar limite de redirecionamentos
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # Configurar retry strategy
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # Fazer requisição
            response = session.get(url, stream=True, timeout=90, allow_redirects=True, verify=True)
            response.raise_for_status()
            
            # Verificar se o arquivo existe (status 200)
            if response.status_code == 200:
                # Salvar arquivo
                total_size = int(response.headers.get('content-length', 0))
                
                with open(filepath, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                print(f"\r   Progresso: {percent:.1f}%", end='', flush=True)
                
                print(f"\n[OK] Download concluido: {filepath}")
                print(f"   Tamanho: {filepath.stat().st_size / (1024*1024):.2f} MB")
                
                # Validar arquivo ZIP
                if not self._validate_zip_file(filepath):
                    filepath.unlink()
                    return None
                
                return filepath
            else:
                print(f"[ERRO] Arquivo nao encontrado (Status {response.status_code})")
                return None
                
        except requests.exceptions.TooManyRedirects as e:
            print(f"[ERRO] Muitos redirecionamentos detectados.")
            print(f"   Tentando seguir redirecionamentos manualmente...")
            
            # Tentar seguir redirecionamentos manualmente para detectar loops
            try:
                from urllib.parse import urljoin, urlparse, urlunparse
                
                def normalize_url(url_str):
                    """Normaliza URL para comparação (remove fragmentos, normaliza path)"""
                    parsed = urlparse(url_str)
                    # Remove fragmento e normaliza
                    normalized = urlunparse((
                        parsed.scheme,
                        parsed.netloc.lower(),
                        parsed.path.rstrip('/'),
                        parsed.params,
                        parsed.query,
                        ''  # Remove fragmento
                    ))
                    return normalized
                
                visited_urls = set()
                current_url = url
                max_manual_redirects = 15
                
                for redirect_count in range(max_manual_redirects):
                    normalized_url = normalize_url(current_url)
                    
                    if normalized_url in visited_urls:
                        print(f"[ERRO] Loop de redirecionamento detectado!")
                        print(f"   URL que causa loop: {current_url[:100]}...")
                        print(f"   URLs visitadas: {len(visited_urls)}")
                        # Tentar usar a última URL válida antes do loop
                        break
                    
                    visited_urls.add(normalized_url)
                    
                    # Fazer requisição sem seguir redirecionamentos automaticamente
                    # Usar GET em vez de HEAD para alguns servidores que não respondem HEAD corretamente
                    try:
                        response = session.get(current_url, allow_redirects=False, timeout=30, verify=True, stream=False)
                    except:
                        # Se GET falhar, tentar HEAD
                        response = session.head(current_url, allow_redirects=False, timeout=30, verify=True)
                    
                    if response.status_code in [301, 302, 303, 307, 308]:
                        # Pegar URL de redirecionamento
                        redirect_url = response.headers.get('Location')
                        if not redirect_url:
                            # Tentar outros headers comuns
                            redirect_url = response.headers.get('location') or response.headers.get('LOCATION')
                        
                        if not redirect_url:
                            print(f"[ERRO] Redirecionamento sem URL de destino")
                            break
                        
                        # Resolver URL relativa
                        if redirect_url.startswith('/'):
                            redirect_url = urljoin(current_url, redirect_url)
                        elif not redirect_url.startswith('http'):
                            redirect_url = urljoin(current_url, redirect_url)
                        
                        print(f"   Redirecionamento {redirect_count + 1}: {redirect_url[:100]}...")
                        current_url = redirect_url
                        
                    elif response.status_code == 200:
                        # Encontrou o arquivo final
                        print(f"   URL final encontrada: {current_url[:100]}...")
                        # Fazer download da URL final
                        response = session.get(current_url, stream=True, timeout=90, verify=True)
                        response.raise_for_status()
                        
                        total_size = int(response.headers.get('content-length', 0))
                        
                        with open(filepath, 'wb') as f:
                            downloaded = 0
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if total_size > 0:
                                        percent = (downloaded / total_size) * 100
                                        print(f"\r   Progresso: {percent:.1f}%", end='', flush=True)
                        
                        print(f"\n[OK] Download concluido: {filepath}")
                        print(f"   Tamanho: {filepath.stat().st_size / (1024*1024):.2f} MB")
                        
                        # Validar arquivo ZIP
                        if not self._validate_zip_file(filepath):
                            filepath.unlink()
                            return None
                        
                        return filepath
                    else:
                        print(f"[ERRO] Status code inesperado: {response.status_code}")
                        break
                
                print(f"[ERRO] Nao foi possivel resolver redirecionamentos")
                print(f"   Tentando URL direta sem redirecionamentos...")
                
                # Última tentativa: usar a URL original com configurações diferentes
                try:
                    # Tentar com cookies da sessão
                    response = session.get(url, stream=True, timeout=90, allow_redirects=False, verify=True)
                    
                    if response.status_code in [301, 302, 303, 307, 308]:
                        final_url = response.headers.get('Location') or response.headers.get('location')
                        if final_url:
                            if not final_url.startswith('http'):
                                final_url = urljoin(url, final_url)
                            print(f"   Tentando URL de redirecionamento direto: {final_url[:100]}...")
                            response = session.get(final_url, stream=True, timeout=90, verify=True)
                    
                    if response.status_code == 200:
                        total_size = int(response.headers.get('content-length', 0))
                        
                        with open(filepath, 'wb') as f:
                            downloaded = 0
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if total_size > 0:
                                        percent = (downloaded / total_size) * 100
                                        print(f"\r   Progresso: {percent:.1f}%", end='', flush=True)
                        
                        print(f"\n[OK] Download concluido: {filepath}")
                        print(f"   Tamanho: {filepath.stat().st_size / (1024*1024):.2f} MB")
                        
                        # Validar arquivo ZIP
                        if not self._validate_zip_file(filepath):
                            filepath.unlink()
                            return None
                        
                        return filepath
                except Exception as e3:
                    print(f"[ERRO] Falha na tentativa direta: {e3}")
                
                return None
                
            except Exception as e2:
                print(f"[ERRO] Falha ao seguir redirecionamentos: {e2}")
                import traceback
                traceback.print_exc()
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[ERRO] Erro ao baixar arquivo: {e}")
            print(f"   Tipo de erro: {type(e).__name__}")
            
            # Tentar novamente com configurações diferentes
            try:
                print(f"   Tentando novamente com configuracoes alternativas...")
                response = requests.get(url, stream=True, timeout=90, allow_redirects=True, 
                                       headers=headers, verify=False)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                
                with open(filepath, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                print(f"\r   Progresso: {percent:.1f}%", end='', flush=True)
                
                print(f"\n[OK] Download concluido: {filepath}")
                print(f"   Tamanho: {filepath.stat().st_size / (1024*1024):.2f} MB")
                
                # Validar arquivo ZIP
                if not self._validate_zip_file(filepath):
                    filepath.unlink()
                    return None
                
                return filepath
            except Exception as e2:
                print(f"[ERRO] Falha na segunda tentativa: {e2}")
                return None
    
    def download_current_month(self) -> Optional[Path]:
        """
        Baixa o arquivo do mês atual
        
        Returns:
            Path do arquivo baixado ou None em caso de erro
        """
        now = datetime.now()
        return self.download(now.year, now.month)
    
    def download_latest_available(self) -> Optional[Path]:
        """
        Tenta baixar o arquivo mais recente disponível
        Começa pelo mês atual e vai retrocedendo até encontrar um arquivo válido
        
        Returns:
            Path do arquivo baixado ou None se nenhum for encontrado
        """
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        
        # Tentar até 12 meses atrás
        for i in range(12):
            year = current_year
            month = current_month - i
            
            # Ajustar ano se necessário
            while month <= 0:
                month += 12
                year -= 1
            
            filepath = self.download(year, month)
            if filepath and filepath.exists():
                return filepath
        
        print("[ERRO] Nenhum arquivo disponivel encontrado nos ultimos 12 meses")
        return None
