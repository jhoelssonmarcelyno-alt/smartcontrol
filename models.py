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

# --- FUNÇÕES DE CLIENTES (FIADOS) ---

def cadastrar_cliente(nome, telefone):
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO clientes (nome, telefone)
        VALUES (?, ?)
    ''', (nome, telefone))
    conn.commit()
    conn.close()
    print(f"👤 Cliente '{nome}' cadastrado com sucesso!")

def listar_clientes():
    conn = get_db_connection()
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    conn.close()
    return clientes

def atualizar_debito_cliente(cliente_id, valor):
    conn = get_db_connection()
    conn.execute('''
        UPDATE clientes 
        SET saldo_devedor = saldo_devedor + ? 
        WHERE id = ?
    ''', (valor, cliente_id))
    conn.commit()
    conn.close()

def registrar_venda(produto_id, cliente_id, quantidade, valor_total, pago):
    conn = get_db_connection()
    
    # 1. Registra a venda
    conn.execute('''
        INSERT INTO vendas (produto_id, cliente_id, quantidade, valor_total, pago)
        VALUES (?, ?, ?, ?, ?)
    ''', (produto_id, cliente_id, quantidade, valor_total, pago))
    
    # 2. Baixa no estoque
    conn.execute('''
        UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?
    ''', (quantidade, produto_id))
    
    # 3. Se for FIADO (pago = 0), atualiza a dívida do cliente
    if not pago and cliente_id:
        conn.execute('''
            UPDATE clientes SET saldo_devedor = saldo_devedor + ? WHERE id = ?
        ''', (valor_total, cliente_id))
    
    conn.commit()
    conn.close()
    print(f"💰 Venda de R$ {valor_total} registrada!")

    def registrar_venda(produto_id, cliente_id, quantidade, forma_pagamento):
     conn = conectar_db()
    cursor = conn.cursor()
    
    # 1. Busca o preço e o estoque atual do produto
    cursor.execute("SELECT preco_venda, quantidade FROM produtos WHERE id = ?", (produto_id,))
    produto = cursor.fetchone()
    
    if produto and produto['quantidade'] >= quantidade:
        valor_total = produto['preco_venda'] * quantidade
        
        # 2. Diminui o estoque
        cursor.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?", (quantidade, produto_id))
        
        # 3. Se for FIADO, aumenta a dívida do cliente
        if forma_pagamento == 'fiado':
            cursor.execute("UPDATE clientes SET saldo_devedor = saldo_devedor + ? WHERE id = ?", (valor_total, cliente_id))
            
        # 4. Registra a venda na tabela de vendas
        cursor.execute("""
            INSERT INTO vendas (produto_id, cliente_id, quantidade, valor_total, forma_pagamento)
            VALUES (?, ?, ?, ?, ?)
        """, (produto_id, cliente_id, quantidade, valor_total, forma_pagamento))
        
        conn.commit()
    conn.close()

    def criar_tabela_assinantes():
     conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assinantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_expiracao DATETIME,
            plano TEXT -- '7_dias', '30_dias', '90_dias', '180_dias', '365_dias'
        )
    """)
    conn.commit()
    conn.close()

    def criar_tabela_usuarios():
     conn = conectar_db()
    cursor = conn.cursor()
    # Criamos a tabela de usuários (assinantes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            plano TEXT DEFAULT 'teste',
            data_expiracao DATETIME
        )
    """)
    conn.commit()
    conn.close()

# Execute essa função uma vez no seu terminal ou no final do arquivo para criar a tabela