import sqlite3
from datetime import datetime, timedelta

DATABASE = 'database/smartcontrol.db'

def conectar_db():
    # Adicionamos timeout=10 para ele esperar até 10 segundos se o banco estiver ocupado
    conn = sqlite3.connect(DATABASE, timeout=10) 
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

def excluir_usuario(usuario_id):
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM produtos WHERE usuario_id = ?", (usuario_id,))
        cursor.execute("DELETE FROM clientes WHERE usuario_id = ?", (usuario_id,))
        cursor.execute("DELETE FROM vendas WHERE usuario_id = ?", (usuario_id,))
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
        conn.commit()
    finally:
        conn.close()

# --- FUNÇÕES DE NEGÓCIO ---

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

def obter_resumo_financeiro(usuario_id):
    conn = conectar_db()
    resumo = conn.execute('''
        SELECT SUM(valor_total) as faturamento, SUM(lucro) as lucro_total 
        FROM vendas 
        WHERE usuario_id = ?
    ''', (usuario_id,)).fetchone()
    conn.close()
    return resumo

def obter_dados_assinante(usuario_id):
    conn = conectar_db()
    user = conn.execute('''
        SELECT nome, plano, data_expiracao 
        FROM usuarios WHERE id = ?
    ''', (usuario_id,)).fetchone()
    conn.close()
    
    if user:
        expiracao = datetime.strptime(user['data_expiracao'], '%Y-%m-%d %H:%M:%S')
        dias_restantes = (expiracao - datetime.now()).days
        
        return {
            'nome': user['nome'],
            'plano': user['plano'],
            'dias_restantes': dias_restantes if dias_restantes > 0 else 0
        }
    return None

def listar_vendas(usuario_id):
    conn = conectar_db()
    cursor = conn.cursor()
    # O JOIN é fundamental aqui para a tabela mostrar "Coca-Cola" em vez de "ID 5"
    cursor.execute('''
        SELECT 
            v.id, 
            v.quantidade, 
            v.valor_total, 
            v.forma_pagamento, 
            v.data,
            p.nome AS produto_nome, 
            c.nome AS cliente_nome
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE v.usuario_id = ?
        ORDER BY v.data DESC 
        LIMIT 30
    ''', (usuario_id,))
    vendas = cursor.fetchall()
    conn.close()
    return vendas

def registrar_venda(produto_id, cliente_id, quantidade, forma_pagamento, usuario_id):
    conn = conectar_db()
    try:
        cursor = conn.cursor()
        
        # 1. Busca os dados (Apenas leitura aqui)
        cursor.execute("SELECT preco_custo, preco_venda, quantidade FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, usuario_id))
        produto = cursor.fetchone()
        
        if produto and produto['quantidade'] >= quantidade:
            valor_total = produto['preco_venda'] * quantidade
            lucro_operacao = (produto['preco_venda'] - produto['preco_custo']) * quantidade
            
            # 2. Atualiza estoque
            cursor.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?", (quantidade, produto_id))
            
            # 3. Se for fiado, atualiza o cliente
            if forma_pagamento.lower() == 'fiado' and cliente_id:
                cursor.execute("UPDATE clientes SET saldo_devedor = saldo_devedor + ? WHERE id = ?", (valor_total, cliente_id))
                
            # 4. Registra a venda
            cursor.execute("""
                INSERT INTO vendas (produto_id, cliente_id, quantidade, valor_total, lucro, forma_pagamento, usuario_id, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (produto_id, cliente_id, quantidade, valor_total, lucro_operacao, forma_pagamento, usuario_id, datetime.now()))
            
            conn.commit() # Salva tudo de uma vez
    except Exception as e:
        print(f"Erro ao registrar: {e}")
        conn.rollback() # Se der erro, desfaz o que foi feito pra não corromper
    finally:
        conn.close() # GARANTE que a conexão será fechada, dando erro ou não