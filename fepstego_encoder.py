from PIL import Image          # Biblioteca essencial para processamento de imagem (LSB Steganography)
import sys                     # Utilidades de sistema (para sair em caso de erro)
import os                      # Interação com o sistema de arquivos (verificação de existência)
import argparse                # Módulo padrão para criar a interface de linha de comando (CLI)

# --- CONFIGURAÇÕES GLOBAIS ---
DELIMITER = "EOF"              # Assinatura de parada: Sinaliza o fim da mensagem para o decoder.
COLOR_CHANNEL = 0              # Índice 0 (Vermelho/Red) - O canal de cor escolhido para esconder os bits.
                               # [OPSEC] Escolher um canal específico é parte do protocolo secreto.

# ==============================================================================
#  FUNÇÕES DE CODIFICAÇÃO (LSB)
# ==============================================================================

def text_to_bits(text):
    """
    [ENGENHARIA DE BITS] Converte uma string de texto em uma longa sequência binária (0s e 1s).
    
    O bitstream resultante é o payload real que será injetado nos pixels.
    """
    # Converte a string para um inteiro grande, depois para string binária
    bits = bin(int.from_bytes(text.encode('utf-8', 'surrogatepass'), 'big'))[2:]
    
    # zfill garante que o comprimento é múltiplo de 8 (bytes completos), adicionando zeros à esquerda.
    return bits.zfill(8 * ((len(bits) + 7) // 8))

def esconder_mensagem(caminho_imagem, comando_texto, saida_imagem):
    """
    [PROTOCOLO DE INJEÇÃO] Carrega a imagem, esconde a mensagem via LSB e salva.
    """
    
    # 1. VALIDAÇÃO DE ARQUIVO (Verifica se a base existe)
    if not os.path.exists(caminho_imagem):
        print(f" ERRO: Arquivo base '{caminho_imagem}' não encontrado.")
        sys.exit(1) # Sai com erro se a imagem não estiver no caminho
        
    try:
        # Carrega a imagem e força o modo "RGB" (3 canais) para que o LSB funcione de forma consistente.
        img = Image.open(caminho_imagem).convert("RGB") 
    except Exception as e:
        print(f" ERRO ao carregar a imagem: {e}")
        return

    # 2. PREPARAÇÃO DO PAYLOAD
    # Adiciona o terminador 'EOF' ao final do comando para que o agente saiba onde parar de ler.
    mensagem_full = comando_texto + DELIMITER
    bits_mensagem = text_to_bits(mensagem_full)
    
    largura, altura = img.size
    total_pixels = largura * altura
    
    # 3. VERIFICAÇÃO DE CAPACIDADE (LSB Capacity Check)
    # Garante que o comprimento total dos bits (total_bits) não excede a capacidade máxima
    # da imagem (Total de Pixels * 3 canais).
    if len(bits_mensagem) > total_pixels * 3:
        print(" ERRO: Imagem muito pequena para a mensagem!")
        return
    
    print(f" Escondendo {len(bits_mensagem)} bits em {total_pixels} pixels...")
    
    # 4. INJEÇÃO LSB (Iteração e Ocultação)
    encoded = img.copy() # Cria uma cópia mutável da imagem
    
    idx_bit = 0
    total_bits = len(bits_mensagem)

    # Itera sobre os pixels na ordem XY padrão
    for y in range(altura):
        for x in range(largura):
            if idx_bit < total_bits:
                r, g, b = img.getpixel((x, y))
                bit_atual = int(bits_mensagem[idx_bit])
                
                # --- A OPERAÇÃO LSB CRÍTICA ---
                # 1. (r & ~1): Zera o último bit do canal Vermelho (R).
                # 2. | bit_atual: Define o nosso bit secreto (0 ou 1) no lugar zerado.
                novo_r = (r & ~1) | bit_atual
                
                # Define o novo pixel (a alteração é minúscula, apenas no R)
                encoded.putpixel((x, y), (novo_r, g, b))
                
                idx_bit += 1
            else:
                break # Sai do loop quando a mensagem termina

    # 5. SALVAR ARQUIVO (OPSEC CRÍTICO)
    # Salvamos como PNG para garantir que não haja compressão com perdas (lossy compression)
    # que destruiria os bits escondidos.
    encoded.save(saida_imagem, "PNG")
    print(f"  Comando injetado! Imagem salva como '{saida_imagem}'")

# ==============================================================================
#  INTERFACE DE LINHA DE COMANDO (CLI)
# ==============================================================================

def main():
    """
    Função principal que gerencia os argumentos de linha de comando.
    """
    # Cria o parser de argumentos
    parser = argparse.ArgumentParser(
        description="LSB Steganography Encoder for C2 Command Injection.",
        epilog="Exemplo: python stego_encoder.py -i fep.png -d \"ls -la\" -o stego.png"
    )

    # Argumento -i / --input (Caminho da imagem base)
    parser.add_argument('-i', '--input', 
                        required=True, 
                        help='Caminho para o arquivo PNG de entrada (base).')
    
    # Argumento -d / --data (O Payload/Comando)
    parser.add_argument('-d', '--data', 
                        required=True, 
                        help='O comando de C2 a ser escondido (payload). Ex: "whoami".')
    
    # Argumento -o / --output (Nome do arquivo de saída)
    parser.add_argument('-o', '--output', 
                        default='stego_output.png', 
                        help='Nome do arquivo de saída codificado. (Padrão: stego_output.png).')

    args = parser.parse_args()
    
    # Executa a lógica principal com os argumentos fornecidos pelo usuário
    esconder_mensagem(args.input, args.data, args.output)


if __name__ == "__main__":
    # Garante que o usuário tem a biblioteca Pillow instalada antes de iniciar
    try:
        from PIL import Image
    except ImportError:
        print("  ERRO: Biblioteca 'Pillow' não instalada. Rode: pip install Pillow")
        sys.exit(1)
        
    main()