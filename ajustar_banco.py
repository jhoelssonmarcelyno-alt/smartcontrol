import sqlite3

def adicionar_coluna():
    conn = sqlite3.connect('banco.db') # Coloque o nome do seu arquivo .db aqui
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE clientes ADD COLUMN prazo_pagamento INTEGER DEFAULT 15")
        conn.commit()
        print("Coluna 'prazo_pagamento' adicionada com sucesso!")
    except sqlite3.OperationalError:
        print("A coluna já existe ou o nome do arquivo .db está incorreto.")
    finally:
        conn.close()

if __name__ == "__main__":
    adicionar_coluna()