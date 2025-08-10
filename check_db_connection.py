import os
import socket
from urllib.parse import urlparse

DB_HOST = "db.vewcowruacalrstslaqm.supabase.co"
DB_PORT = 5432

print(f"Tentando resolver e conectar a {DB_HOST}:{DB_PORT}...")

try:
    # 1. Resolver o hostname para IPv4
    # socket.getaddrinfo retorna uma lista de tuplas (family, type, proto, canonname, sockaddr)
    # Queremos o primeiro resultado IPv4 (AF_INET)
    addr_info = socket.getaddrinfo(DB_HOST, DB_PORT, socket.AF_INET, socket.SOCK_STREAM)
    ipv4_address = addr_info[0][4][0] # Pega o IP da primeira tupla sockaddr

    print(f"Hostname {DB_HOST} resolvido para IPv4: {ipv4_address}")

    # 2. Tentar conectar à porta
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5) # Timeout de 5 segundos
        s.connect((ipv4_address, DB_PORT))
        print(f"Conexão TCP bem-sucedida a {ipv4_address}:{DB_PORT}")
        print("Parece que a rede está acessível e a porta está aberta.")

except socket.gaierror as e:
    print(f"Erro de resolução de hostname para {DB_HOST}: {e}")
    print("Isso pode indicar um problema de DNS ou que o hostname não tem um endereço IPv4.")
except ConnectionRefusedError:
    print(f"Conexão recusada por {ipv4_address}:{DB_PORT}")
    print("Isso significa que o servidor está online, mas recusou a conexão (ex: firewall, serviço não rodando na porta).")
except socket.timeout:
    print(f"Timeout ao tentar conectar a {ipv4_address}:{DB_PORT}")
    print("Isso pode indicar um firewall bloqueando a conexão ou que o servidor não está respondendo.")
except Exception as e:
    print(f"Ocorreu um erro inesperado: {e}")

