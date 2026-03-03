import sqlite3

def adicionar_coluna_pix():
    conn = sqlite3.connect('database.db') # Verifique se o nome do seu arquivo é esse mesmo
    cursor = conn.cursor()
    try:
        cursor.execute('ALTER TABLE usuarios ADD COLUMN pix TEXT;')
        conn.commit()
        print("Coluna 'pix' adicionada com sucesso!")
    except sqlite3.OperationalError:
        print("A coluna 'pix' já existe ou a tabela não foi encontrada.")
    finally:
        conn.close()

if __name__ == '__main__':
    adicionar_coluna_pix()