import sqlite3
from datetime import datetime, timedelta

DATABASE = 'database/smartcontrol.db'

def conectar_db():
    # Timeout para evitar travamentos em acessos simultâneos
    conn = sqlite3.connect(DATABASE, timeout=10) 
    conn.row_factory = sqlite3.Row
    return conn

# --- SISTEMA DE ASSINANTES E ADMIN ---

def cadastrar_usuario(nome, email, senha):
    conn = conectar_db()
    cursor = conn.cursor()
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
        UPDATE usuarios SET data_expiracao = ?, plano = ? WHERE id = ?
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
        INSERT INTO clientes (nome, telefone, saldo_devedor, permite_fiado, limite_fiado, usuario_id)
        VALUES (?, ?, 0.0, 1, 0.0, ?)
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
        FROM vendas WHERE usuario_id = ?
    ''', (usuario_id,)).fetchone()
    conn.close()
    return resumo

def obter_dados_assinante(usuario_id):
    conn = conectar_db()
    user = conn.execute('SELECT nome, plano, data_expiracao FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    conn.close()
    if user:
        expiracao = datetime.strptime(user['data_expiracao'], '%Y-%m-%d %H:%M:%S')
        restantes = (expiracao - datetime.now()).days
        return {'nome': user['nome'], 'plano': user['plano'], 'dias_restantes': max(0, restantes)}
    return None

def listar_vendas(usuario_id):
    conn = conectar_db()
    vendas = conn.execute('''
        SELECT v.*, p.nome AS produto_nome, c.nome AS cliente_nome
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE v.usuario_id = ?
        ORDER BY v.data DESC LIMIT 30
    ''', (usuario_id,)).fetchall()
    conn.close()
    return vendas

def registrar_venda(produto_id, cliente_id, quantidade, forma_pagamento, usuario_id):
    conn = conectar_db()
    try:
        cursor = conn.cursor()
        
        # 1. Busca dados do produto (Preço e Estoque atual)
        cursor.execute("SELECT preco_custo, preco_venda, quantidade FROM produtos WHERE id = ?", (produto_id,))
        prod = cursor.fetchone()
        
        if not prod:
            raise Exception("Produto não encontrado.")
            
        if prod['quantidade'] < quantidade:
            raise Exception(f"Estoque insuficiente para o produto ID {produto_id}.")

        # 2. Cálculos financeiros
        v_total = prod['preco_venda'] * quantidade
        lucro = (prod['preco_venda'] - prod['preco_custo']) * quantidade
        data_agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 3. Se for Fiado, validar e atualizar saldo do cliente
        if forma_pagamento.lower() == 'fiado' and cliente_id:
            cursor.execute("SELECT permite_fiado, limite_fiado, saldo_devedor FROM clientes WHERE id = ?", (cliente_id,))
            cli = cursor.fetchone()
            
            if cli:
                if not cli['permite_fiado']:
                    raise Exception("Cliente bloqueado para fiado.")
                
                if cli['limite_fiado'] > 0 and (cli['saldo_devedor'] + v_total) > cli['limite_fiado']:
                    raise Exception("Limite de crédito excedido.")
                
                # Atualiza o saldo devedor E a data da última compra para o contador de dias
                cursor.execute("""
                    UPDATE clientes 
                    SET saldo_devedor = saldo_devedor + ?, 
                        data_ultima_compra = ? 
                    WHERE id = ?
                """, (v_total, data_agora, cliente_id))
        
        # 4. Baixa no estoque
        cursor.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?", (quantidade, produto_id))
        
        # 5. Insere o registro da venda
        cursor.execute("""
            INSERT INTO vendas (produto_id, cliente_id, quantidade, valor_total, lucro, forma_pagamento, usuario_id, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (produto_id, cliente_id, quantidade, v_total, lucro, forma_pagamento, usuario_id, data_agora))
        
        # Finaliza a transação salvando tudo
        conn.commit()
        
    except Exception as e:
        conn.rollback() # Cancela tudo se der erro em qualquer item
        raise e
    finally:
        conn.close()

# --- GESTÃO AVANÇADA DE CLIENTES ---

def registrar_pagamento_cliente(cliente_id, valor_pago):
    conn = conectar_db()
    try:
        conn.execute('UPDATE clientes SET saldo_devedor = MAX(0, saldo_devedor - ?) WHERE id = ?', (valor_pago, cliente_id))
        conn.commit()
    finally:
        conn.close()

def obter_cliente_por_id(cliente_id, usuario_id):
    conn = conectar_db()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ? AND usuario_id = ?', (cliente_id, usuario_id)).fetchone()
    conn.close()
    return cliente

def obter_extrato_cliente(cliente_id, usuario_id):
    conn = conectar_db()
    # Usamos o strftime do SQLite para formatar a data diretamente na query
    vendas = conn.execute('''
        SELECT 
            strftime('%d/%m/%Y %H:%M', v.data) as data_formatada, 
            p.nome as produto, 
            v.quantidade, 
            v.valor_total, 
            v.forma_pagamento
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        WHERE v.cliente_id = ? AND v.usuario_id = ?
        ORDER BY v.data DESC
    ''', (cliente_id, usuario_id)).fetchall()
    conn.close()
    return vendas

def atualizar_configuracao_fiado(cliente_id, permite, limite, usuario_id):
    conn = conectar_db()
    conn.execute('''
        UPDATE clientes SET permite_fiado = ?, limite_fiado = ? 
        WHERE id = ? AND usuario_id = ?
    ''', (permite, limite, cliente_id, usuario_id))
    conn.commit()
    conn.close()