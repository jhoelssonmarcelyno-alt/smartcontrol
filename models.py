import sqlite3
from datetime import datetime, timedelta

DATABASE = 'database/smartcontrol.db'

def conectar_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# --- SISTEMA DE ASSINANTES E ADMIN ---

def cadastrar_usuario(nome, email, senha):
    conn = conectar_db()
    cursor = conn.cursor()
    # 7 dias de teste grátis por padrão
    expiracao = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute("""
            INSERT INTO usuarios (nome, email, senha, plano, data_expiracao)
            VALUES (?, ?, ?, 'Teste Grátis', ?)
        """, (nome, email, senha, expiracao))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def listar_todos_assinantes():
    conn = conectar_db()
    assinantes = conn.execute('SELECT id, nome, email, plano, data_expiracao FROM usuarios').fetchall()
    conn.close()
    return assinantes

def renovar_assinatura(usuario_id, dias):
    conn = conectar_db()
    cursor = conn.cursor()
    nova_expiracao = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
    plano_nome = f"Plano {dias} Dias"
    
    cursor.execute("""
        UPDATE usuarios 
        SET data_expiracao = ?, plano = ? 
        WHERE id = ?
    """, (nova_expiracao, plano_nome, usuario_id))
    
    conn.commit()
    conn.close()

# FUNÇÃO QUE ESTAVA FALTANDO:
def excluir_usuario(usuario_id):
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        # Limpa todos os dados vinculados a esse usuário antes de deletá-lo
        cursor.execute("DELETE FROM produtos WHERE usuario_id = ?", (usuario_id,))
        cursor.execute("DELETE FROM clientes WHERE usuario_id = ?", (usuario_id,))
        cursor.execute("DELETE FROM vendas WHERE usuario_id = ?", (usuario_id,))
        # Por fim, deleta o usuário
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
        conn.commit()
    finally:
        conn.close()

# --- FUNÇÕES DE NEGÓCIO (PRODUTOS, CLIENTES, VENDAS) ---

def cadastrar_produto(nome, preco_custo, preco_venda, quantidade, usuario_id):
    conn = conectar_db()
    conn.execute('''
        INSERT INTO produtos (nome, preco_custo, preco_venda, quantidade, usuario_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (nome, preco_custo, preco_venda, quantidade, usuario_id))
    conn.commit()
    conn.close()

def listar_produtos(usuario_id):
    conn = conectar_db()
    produtos = conn.execute('SELECT * FROM produtos WHERE usuario_id = ?', (usuario_id,)).fetchall()
    conn.close()
    return produtos

def cadastrar_cliente(nome, telefone, usuario_id):
    conn = conectar_db()
    conn.execute('''
        INSERT INTO clientes (nome, telefone, usuario_id)
        VALUES (?, ?, ?)
    ''', (nome, telefone, usuario_id))
    conn.commit()
    conn.close()

def listar_clientes(usuario_id):
    conn = conectar_db()
    clientes = conn.execute('SELECT * FROM clientes WHERE usuario_id = ?', (usuario_id,)).fetchall()
    conn.close()
    return clientes

def registrar_venda(produto_id, cliente_id, quantidade, forma_pagamento, usuario_id):
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT preco_venda, quantidade FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, usuario_id))
    produto = cursor.fetchone()
    
    if produto and produto['quantidade'] >= quantidade:
        valor_total = produto['preco_venda'] * quantidade
        cursor.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?", (quantidade, produto_id))
        
        if forma_pagamento == 'fiado' and cliente_id:
            cursor.execute("UPDATE clientes SET saldo_devedor = saldo_devedor + ? WHERE id = ?", (valor_total, cliente_id))
            
        cursor.execute("""
            INSERT INTO vendas (produto_id, cliente_id, quantity, valor_total, forma_pagamento, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (produto_id, cliente_id, quantidade, valor_total, forma_pagamento, usuario_id))
        
        conn.commit()
    conn.close()