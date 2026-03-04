import sqlite3

for banco in ['banco_de_dados.db', 'database.db', 'vendas.db']:
    try:
        conn = sqlite3.connect(banco)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tabelas = cursor.fetchall()
        if tabelas:
            print(f"No arquivo {banco}, as tabelas são: {tabelas}")
        conn.close()
    except:
        pass