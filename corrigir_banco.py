import sqlite3

def adicionar_coluna():
    try:
        # Se o nome do seu banco for diferente de 'dados.db', ajuste aqui
        conn = sqlite3.connect('vendas.db') 
        cursor = conn.cursor()
        
        print("Tentando adicionar a coluna 'limite_credito'...")
        cursor.execute('ALTER TABLE clientes ADD COLUMN limite_credito REAL DEFAULT 0.0')
        
        conn.commit()
        print("✅ Coluna 'limite_credito' adicionada com sucesso!")
        
    except sqlite3.OperationalError:
        print("ℹ️ A coluna já existe ou a tabela não foi encontrada.")
    except Exception as e:
        print(f"❌ Erro: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    adicionar_coluna()