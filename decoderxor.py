# decoderxor.py

def decifrar_resultado(hex_dados, chave):
    try:
        # 1. Converte de Hexadecimal para Bytes brutos
        bytes_cifrados = bytes.fromhex(hex_dados)
        
        # 2. Aplica o XOR inverso (que é igual ao XOR de ida)
        # A ^ Key = B  --->  B ^ Key = A
        bytes_planos = bytes([b ^ chave for b in bytes_cifrados])
        
        # 3. Converte para texto legível
        texto = bytes_planos.decode('utf-8', errors='ignore')
        return texto
    except ValueError:
        return " Erro: Isso não parece ser hexadecimal válido."
    except Exception as e:
        return f" Erro: {e}"

if __name__ == "__main__":
    print("DECODIFICADOR C2 XOR")
    print("-----------------------")
    
    # A chave tem de ser IGUAL à do script do agente (0x55)
    CHAVE = 0x55 
    
    while True:
        hex_input = input("\nCole o HEX do gists aqui (ou 'sair'): ").strip()
        
        if hex_input.lower() == 'sair':
            break
            
        if not hex_input:
            continue
            
        resultado = decifrar_resultado(hex_input, CHAVE)
        
        print("\n CONTEÚDO ORIGINAL:")
        print("-" * 30)
        print(resultado)
        print("-" * 30)
