import sqlite3

def checar():
    # Troque pelo nome real do seu arquivo .db (ex: sistema.db)
    conn = sqlite3.connect('banco_de_dados.db') 
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(vendas)")
        colunas = cursor.fetchall()
        print("COLUNAS ENCONTRADAS NA TABELA VENDAS:")
        for col in colunas:
            print(f"- {col[1]}") # O nome da coluna fica na posição 1
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        conn.close()

checar()