import sqlite3

DATABASE = 'database/smartcontrol.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Isso permite acessar colunas pelo nome (ex: produto['nome'])
    return conn

# --- FUNÇÕES DE PRODUTOS ---

def cadastrar_produto(nome, preco_custo, preco_venda, quantidade):
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO produtos (nome, preco_custo, preco_venda, quantidade)
        VALUES (?, ?, ?, ?)
    ''', (nome, preco_custo, preco_venda, quantidade))
    conn.commit()
    conn.close()
    print(f"📦 Produto '{nome}' cadastrado com sucesso!")

def listar_produtos():
    conn = get_db_connection()
    produtos = conn.execute('SELECT * FROM produtos').fetchall()
    conn.close()
    return produtos