from models import conectar_db

def inicializar_sistema():
    conn = conectar_db()
    cursor = conn.cursor()

    print("Checking and creating tables...")

    # 1. Cria a tabela de usuários (assinantes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            plano TEXT DEFAULT 'Teste Grátis',
            data_expiracao DATETIME
        )
    """)

    # 2. Garante que as outras tabelas existam e tenham a coluna usuario_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco_custo REAL,
            preco_venda REAL,
            quantidade INTEGER,
            usuario_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            saldo_devedor REAL DEFAULT 0,
            usuario_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            cliente_id INTEGER,
            quantidade INTEGER,
            valor_total REAL,
            forma_pagamento TEXT,
            data_venda DATETIME DEFAULT CURRENT_TIMESTAMP,
            usuario_id INTEGER
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Banco de dados atualizado com sucesso!")

if __name__ == "__main__":
    inicializar_sistema()