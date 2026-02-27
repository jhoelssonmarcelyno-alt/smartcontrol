import sqlite3

def adicionar_coluna():
    conn = sqlite3.connect('database/smartcontrol.db')
    cursor = conn.cursor()
    try:
        # Adiciona a coluna forma_pagamento que está faltando
        cursor.execute('ALTER TABLE vendas ADD COLUMN forma_pagamento TEXT')
        print("Coluna 'forma_pagamento' adicionada com sucesso!")
    except sqlite3.OperationalError:
        print("A coluna já existe ou a tabela não foi encontrada.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    adicionar_coluna()