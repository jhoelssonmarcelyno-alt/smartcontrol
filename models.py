import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json
import os

# --- CONFIGURAÇÃO DE AMBIENTE ---
# No Render, o DATABASE_URL já vem configurado. 
# No PC, ele tentará usar o SQLite se não encontrar a variável.
DATABASE_URL = os.environ.get('DATABASE_URL')

# Ajuste crucial para o Neon.tech (PostgreSQL) funcionar no Render/Heroku
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def conectar_db():
    if DATABASE_URL:
        # Conexão para Produção (Render + Neon)
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        # Conexão para Desenvolvimento Local (SQLite)
        DATABASE = 'database/smartcontrol.db'
        os.makedirs('database', exist_ok=True)
        conn = sqlite3.connect(DATABASE, timeout=10) 
        conn.row_factory = sqlite3.Row
        return conn

# Variável para usar nos SQLs: se for Postgres usa %s, se for SQLite usa ?
PL = '%s' if DATABASE_URL else '?'

def obter_cursor(conn):
    if DATABASE_URL:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()

# --- SISTEMA DE ASSINANTES E ADMIN ---

def cadastrar_usuario(nome, email, senha):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    expiracao = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute(f"""
            INSERT INTO usuarios (nome, email, senha, plano, data_expiracao)
            VALUES ({PL}, {PL}, {PL}, 'Teste Grátis', {PL})
        """, (nome, email, senha, expiracao))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao cadastrar usuário: {e}")
        return False
    finally:
        conn.close()

def cadastrar_cliente(nome, telefone, limite, prazo, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'''
        INSERT INTO clientes (nome, telefone, saldo_devedor, permite_fiado, limite_fiado, prazo_pagamento, usuario_id)
        VALUES ({PL}, {PL}, 0.0, 1, {PL}, {PL}, {PL})
    ''', (nome.upper(), telefone, limite, prazo, usuario_id))
    conn.commit()
    conn.close()     

def listar_todos_assinantes():
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute('SELECT id, nome, email, plano, data_expiracao FROM usuarios')
    assinantes = cursor.fetchall()
    conn.close()
    return assinantes

def renovar_assinatura(usuario_id, dias):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    nova_expiracao = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
    plano_nome = f"Plano {dias} Dias"
    cursor.execute(f"UPDATE usuarios SET data_expiracao = {PL}, plano = {PL} WHERE id = {PL}", 
                   (nova_expiracao, plano_nome, usuario_id))
    conn.commit()
    conn.close()

def excluir_usuario(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f"DELETE FROM produtos WHERE usuario_id = {PL}", (usuario_id,))
        cursor.execute(f"DELETE FROM clientes WHERE usuario_id = {PL}", (usuario_id,))
        cursor.execute(f"DELETE FROM vendas WHERE usuario_id = {PL}", (usuario_id,))
        cursor.execute(f"DELETE FROM usuarios WHERE id = {PL}", (usuario_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e 
    finally:
        conn.close()

def atualizar_senha_usuario(usuario_id, nova_senha):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f"UPDATE usuarios SET senha = {PL} WHERE id = {PL}", (nova_senha, usuario_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao mudar senha: {e}")
        return False
    finally:
        conn.close()

def obter_dados_assinante(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'SELECT nome, plano, data_expiracao FROM usuarios WHERE id = {PL}', (usuario_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        try:
            exp_str = str(user['data_expiracao'])[:19]
            expiracao = datetime.strptime(exp_str, '%Y-%m-%d %H:%M:%S')
            restantes = (expiracao - datetime.now()).days
            return {'nome': user['nome'], 'plano': user['plano'], 'dias_restantes': max(0, restantes)}
        except:
            return {'nome': user['nome'], 'plano': user['plano'], 'dias_restantes': 0}
    return None

# --- FUNÇÕES DE NEGÓCIO ---

def cadastrar_produto(nome, preco_custo, preco_venda, quantidade, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'''
        INSERT INTO produtos (nome, preco_custo, preco_venda, quantidade, usuario_id)
        VALUES ({PL}, {PL}, {PL}, {PL}, {PL})
    ''', (nome.upper(), preco_custo, preco_venda, quantidade, usuario_id))
    conn.commit()
    conn.close()

def listar_produtos(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'SELECT * FROM produtos WHERE usuario_id = {PL} ORDER BY nome ASC', (usuario_id,))
    produtos = cursor.fetchall()
    conn.close()
    return produtos

def listar_clientes(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'SELECT * FROM clientes WHERE usuario_id = {PL} ORDER BY nome ASC', (usuario_id,))
    clientes = cursor.fetchall()
    conn.close()
    return clientes

def obter_cliente_por_id(cliente_id, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'SELECT * FROM clientes WHERE id = {PL} AND usuario_id = {PL}', (cliente_id, usuario_id))
    cliente = cursor.fetchone()
    conn.close()
    return cliente

# --- SISTEMA DE VENDAS E HISTÓRICO ---

def listar_vendas(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'''
        SELECT v.*, p.nome AS produto_nome, c.nome AS cliente_nome
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE v.usuario_id = {PL}
        ORDER BY v.data DESC LIMIT 100
    ''', (usuario_id,))
    vendas = cursor.fetchall()
    conn.close()
    return vendas

def processar_venda_completa(itens_json, cliente_id, forma_pagamento, usuario_id):
    if not itens_json: return False
    try:
        itens = json.loads(itens_json)
        conn = conectar_db()
        cursor = obter_cursor(conn)
        data_agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_venda_geral = 0

        for item in itens:
            p_id = item['id']
            qtd = int(item['qtd'])
            
            cursor.execute(f"SELECT preco_custo, preco_venda, quantidade FROM produtos WHERE id = {PL}", (p_id,))
            prod = cursor.fetchone()
            
            if not prod or prod['quantidade'] < qtd:
                raise Exception(f"Estoque insuficiente")

            v_total = prod['preco_venda'] * qtd
            lucro = (prod['preco_venda'] - prod['preco_custo']) * qtd
            total_venda_geral += v_total

            cursor.execute(f"""
                INSERT INTO vendas (produto_id, cliente_id, quantidade, valor_total, lucro, forma_pagamento, usuario_id, data)
                VALUES ({PL}, {PL}, {PL}, {PL}, {PL}, {PL}, {PL}, {PL})
            """, (p_id, cliente_id if cliente_id else None, qtd, v_total, lucro, forma_pagamento, usuario_id, data_agora))

            cursor.execute(f"UPDATE produtos SET quantidade = quantidade - {PL} WHERE id = {PL}", (qtd, p_id))

        if forma_pagamento.strip().upper() == 'FIADO' and cliente_id:
            cursor.execute(f"""
                UPDATE clientes 
                SET saldo_devedor = COALESCE(saldo_devedor, 0) + {PL}, 
                    data_ultima_compra = {PL} 
                WHERE id = {PL}
            """, (total_venda_geral, data_agora, cliente_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro na venda: {e}")
        return False
    finally:
        conn.close()

def obter_resumo_financeiro(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    
    cursor.execute(f'''
        SELECT 
            COALESCE(SUM(valor_total), 0) as faturamento, 
            COALESCE(SUM(lucro), 0) as lucro 
        FROM vendas WHERE usuario_id = {PL}
    ''', (usuario_id,))
    res_vendas = cursor.fetchone()

    cursor.execute(f'''
        SELECT 
            COALESCE(SUM(quantidade * preco_venda), 0) as valor_venda,
            COALESCE(SUM(quantidade * (preco_venda - preco_custo)), 0) as lucro_previsto
        FROM produtos WHERE usuario_id = {PL}
    ''', (usuario_id,))
    res_estoque = cursor.fetchone()

    cursor.execute(f'''
        SELECT COALESCE(SUM(saldo_devedor), 0) as total
        FROM clientes 
        WHERE usuario_id = {PL} AND saldo_devedor > 0
    ''', (usuario_id,))
    res_fiado = cursor.fetchone()

    conn.close()

    return {
        'faturamento': res_vendas['faturamento'],
        'lucro': res_vendas['lucro'],
        'valor_estoque': res_estoque['valor_venda'],
        'lucro_previsto': res_estoque['lucro_previsto'],
        'total_fiado': res_fiado['total']
    }

# --- FINANCEIRO E CONFIGURAÇÕES ---

def registrar_pagamento_cliente(cliente_id, valor_pago):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'UPDATE clientes SET saldo_devedor = saldo_devedor - {PL} WHERE id = {PL}', (valor_pago, cliente_id))
    cursor.execute(f'UPDATE clientes SET saldo_devedor = 0 WHERE id = {PL} AND saldo_devedor < 0', (cliente_id,))
    conn.commit()
    conn.close()

def obter_extrato_cliente(cliente_id, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    c_id = int(cliente_id)
    
    if DATABASE_URL:
        sql_data = "to_char(v.data::timestamp, 'DD/MM/YYYY HH24:MI')"
    else:
        sql_data = "strftime('%d/%m/%Y %H:%M', v.data)"

    cursor.execute(f'''
        SELECT 
            {sql_data} as data_formatada, 
            p.nome as produto, 
            v.quantidade, 
            v.valor_total, 
            v.forma_pagamento
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        WHERE v.cliente_id = {PL} 
        ORDER BY v.data DESC
    ''', (c_id,))
    vendas = cursor.fetchall()
    conn.close()
    return vendas

def atualizar_configuracao_fiado(cliente_id, permite, limite, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'UPDATE clientes SET permite_fiado = {PL}, limite_fiado = {PL} WHERE id = {PL} AND usuario_id = {PL}', 
                  (permite, limite, cliente_id, usuario_id))
    conn.commit()
    conn.close()

def criar_tabelas():
    conn = conectar_db()
    cursor = obter_cursor(conn)
    
    id_type = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    real_type = "DOUBLE PRECISION" if DATABASE_URL else "REAL"

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS usuarios (
            id {id_type},
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            logo TEXT,
            pix TEXT,
            plano TEXT,
            data_expiracao TEXT
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS produtos (
            id {id_type},
            nome TEXT NOT NULL,
            preco_custo {real_type},
            preco_venda {real_type},
            quantidade INTEGER,
            usuario_id INTEGER
        )
    ''')
    
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS clientes (
            id {id_type},
            nome TEXT NOT NULL,
            telefone TEXT,
            saldo_devedor {real_type} DEFAULT 0,
            permite_fiado INTEGER DEFAULT 1,
            limite_fiado {real_type} DEFAULT 0,
            prazo_pagamento INTEGER DEFAULT 15,
            data_ultima_compra TEXT,
            usuario_id INTEGER
        )
    ''')
    
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS vendas (
            id {id_type},
            produto_id INTEGER,
            cliente_id INTEGER,
            quantidade INTEGER,
            valor_total {real_type},
            lucro {real_type},
            forma_pagamento TEXT,
            data TEXT,
            usuario_id INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()