import sqlite3
import os

def criar_banco():
    # Garante que a pasta database existe
    if not os.path.exists('database'):
        os.makedirs('database')
    
    # Conecta ao banco (se não existir, ele cria o arquivo)
    connection = sqlite3.connect('database/smartcontrol.db')

    with open('database/schema.sql') as f:
        connection.executescript(f.read())

    connection.commit()
    connection.close()
    print("✅ Banco de dados 'SmartControl' criado com sucesso!")

if __name__ == "__main__":
    criar_banco()