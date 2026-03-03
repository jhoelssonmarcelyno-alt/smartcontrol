import sqlite3
import os

# 1. Tenta descobrir qual o banco de dados que seu app usa
# Geralmente o nome do banco está dentro da sua função 'conectar_db' no models.py
# Vou testar os nomes mais comuns:
bancos_para_testar = ['vendas.db', 'database.db', 'sistema.db', 'dados.db']

for db_file in bancos_para_testar:
    if os.path.exists(db_file):
        print(f"--- Analisando o arquivo: {db_file} ---")
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Verificando se a tabela clientes existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clientes'")
            tabela = cursor.fetchone()
            
            if tabela:
                print(f"✅ Tabela 'clientes' encontrada em {db_file}")
                
                # Verificando as colunas atuais
                cursor.execute("PRAGMA table_info(clientes)")
                colunas = [col[1] for col in cursor.fetchall()]
                print(f"Colunas atuais: {colunas}")
                
                if 'limite_credito' not in colunas:
                    print("⚠️ Coluna 'limite_credito' FALTANDO. Adicionando agora...")
                    cursor.execute('ALTER TABLE clientes ADD COLUMN limite_credito REAL DEFAULT 0.0')
                    conn.commit()
                    print("✨ SUCESSO! Coluna adicionada.")
                else:
                    print("ℹ️ A coluna já consta neste arquivo.")
            else:
                print(f"❌ Tabela 'clientes' não existe em {db_file}")
            
            conn.close()
        except Exception as e:
            print(f"❌ Erro ao processar {db_file}: {e}")
        print("-" * 30)