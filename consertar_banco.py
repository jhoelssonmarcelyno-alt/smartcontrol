import sqlite3

DATABASE = 'database/smartcontrol.db'

def atualizar():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    print("Iniciando atualização do banco de dados...")
    
    try:
        # Tenta adicionar a coluna forma_pagamento
        cursor.execute('ALTER TABLE vendas ADD COLUMN forma_pagamento TEXT')
        print("- Coluna 'forma_pagamento' adicionada!")
    except sqlite3.OperationalError:
        print("- Coluna 'forma_pagamento' já existe ou erro na tabela.")

    try:
        # Tenta adicionar a coluna data (importante para o histórico)
        cursor.execute('ALTER TABLE vendas ADD COLUMN data TEXT')
        print("- Coluna 'data' adicionada!")
    except sqlite3.OperationalError:
        print("- Coluna 'data' já existe.")

    conn.commit()
    conn.close()
    print("Atualização concluída! Pode rodar o sistema agora.")

if __name__ == "__main__":
    atualizar()