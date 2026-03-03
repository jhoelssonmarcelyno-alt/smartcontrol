import sqlite3
from datetime import datetime, timedelta
import json
import uuid
import os

# Define o caminho do banco de dados e garante que a pasta existe
DATABASE = 'database/smartcontrol.db'
os.makedirs('database', exist_ok=True)

def conectar_db():
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
    except Exception as e:
        print(f"Erro ao cadastrar usuário: {e}")
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
    nova_expiracao = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
    plano_nome = f"Plano {dias} Dias"
    conn.execute("UPDATE usuarios SET data_expiracao = ?, plano = ? WHERE id = ?", (nova_expiracao, plano_nome, usuario_id))
    conn.commit()
    conn.close()

def excluir_usuario(usuario_id):
    conn = conectar_db()
    try:
        conn.execute("DELETE FROM produtos WHERE usuario_id = ?", (usuario_id,))
        conn.execute("DELETE FROM clientes WHERE usuario_id = ?", (usuario_id,))
        conn.execute("DELETE FROM vendas WHERE usuario_id = ?", (usuario_id,))
        conn.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
        conn.commit()
    finally:
        conn.close()

def atualizar_senha_usuario(usuario_id, nova_senha):
    conn = conectar_db()
    try:
        conn.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (nova_senha, usuario_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao mudar senha: {e}")
        return False
    finally:
        conn.close()

def obter_dados_assinante(usuario_id):
    conn = conectar_db()
    user = conn.execute('SELECT nome, plano, data_expiracao FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    conn.close()
    if user:
        try:
            expiracao = datetime.strptime(user['data_expiracao'], '%Y-%m-%d %H:%M:%S')
            restantes = (expiracao - datetime.now()).days
            return {'nome': user['nome'], 'plano': user['plano'], 'dias_restantes': max(0, restantes)}
        except:
            return {'nome': user['nome'], 'plano': user['plano'], 'dias_restantes': 0}
    return None

# --- FUNÇÕES DE NEGÓCIO (PRODUTOS E CLIENTES) ---

def cadastrar_produto(nome, preco_custo, preco_venda, quantidade, usuario_id):
    conn = conectar_db()
    conn.execute('''
        INSERT INTO produtos (nome, preco_custo, preco_venda, quantidade, usuario_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (nome.upper(), preco_custo, preco_venda, quantidade, usuario_id))
    conn.commit()
    conn.close()

def listar_produtos(usuario_id):
    conn = conectar_db()
    produtos = conn.execute('SELECT * FROM produtos WHERE usuario_id = ? ORDER BY nome ASC', (usuario_id,)).fetchall()
    conn.close()
    return produtos

def cadastrar_cliente(nome, telefone, usuario_id):
    conn = conectar_db()
    conn.execute('''
        INSERT INTO clientes (nome, telefone, saldo_devedor, permite_fiado, limite_fiado, usuario_id)
        VALUES (?, ?, 0.0, 1, 0.0, ?)
    ''', (nome.upper(), telefone, usuario_id))
    conn.commit()
    conn.close()

def listar_clientes(usuario_id):
    conn = conectar_db()
    clientes = conn.execute('SELECT * FROM clientes WHERE usuario_id = ? ORDER BY nome ASC', (usuario_id,)).fetchall()
    conn.close()
    return clientes

def obter_cliente_por_id(cliente_id, usuario_id):
    conn = conectar_db()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ? AND usuario_id = ?', (cliente_id, usuario_id)).fetchone()
    conn.close()
    return cliente

# --- SISTEMA DE VENDAS E HISTÓRICO ---

def listar_vendas(usuario_id):
    conn = conectar_db()
    vendas = conn.execute('''
        SELECT v.*, p.nome AS produto_nome, c.nome AS cliente_nome
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE v.usuario_id = ?
        ORDER BY v.data DESC LIMIT 100
    ''', (usuario_id,)).fetchall()
    conn.close()
    return vendas

def processar_venda_completa(itens_json, cliente_id, forma_pagamento, usuario_id):
    if not itens_json: return False
    try:
        itens = json.loads(itens_json)
        conn = conectar_db()
        cursor = conn.cursor()
        data_agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_venda_geral = 0

        for item in itens:
            p_id = item['id']
            qtd = int(item['qtd'])
            
            cursor.execute("SELECT preco_custo, preco_venda, quantidade FROM produtos WHERE id = ?", (p_id,))
            prod = cursor.fetchone()
            
            if not prod or prod['quantidade'] < qtd:
                raise Exception(f"Estoque insuficiente")

            v_total = prod['preco_venda'] * qtd
            lucro = (prod['preco_venda'] - prod['preco_custo']) * qtd
            total_venda_geral += v_total

            cursor.execute("""
                INSERT INTO vendas (produto_id, cliente_id, quantidade, valor_total, lucro, forma_pagamento, usuario_id, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (p_id, cliente_id if cliente_id else None, qtd, v_total, lucro, forma_pagamento, usuario_id, data_agora))

            cursor.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?", (qtd, p_id))

        if forma_pagamento.lower() == 'fiado' and cliente_id:
            cursor.execute("UPDATE clientes SET saldo_devedor = saldo_devedor + ?, data_ultima_compra = ? WHERE id = ?", 
                           (total_venda_geral, data_agora, cliente_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro na venda: {e}")
        return False
    finally:
        conn.close()

def obter_resumo_financeiro(usuario_id):
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    
    # 1. Busca Faturamento e Lucro das vendas realizadas
    res_vendas = conn.execute('''
        SELECT 
            COALESCE(SUM(valor_total), 0) as faturamento, 
            COALESCE(SUM(lucro), 0) as lucro_total 
        FROM vendas WHERE usuario_id = ?
    ''', (usuario_id,)).fetchone()
    
    # 2. Busca Valor de Estoque e Lucro Previsto (Venda - Custo) * Qtd
    res_estoque = conn.execute('''
        SELECT 
            COALESCE(SUM(preco_custo * quantidade), 0) as valor_estoque,
            COALESCE(SUM((preco_venda - preco_custo) * quantidade), 0) as lucro_previsto
        FROM produtos WHERE usuario_id = ?
    ''', (usuario_id,)).fetchone()
    
    conn.close()

    return {
        "faturamento": res_vendas['faturamento'],
        "lucro_total": res_vendas['lucro_total'],
        "valor_estoque": res_estoque['valor_estoque'],
        "lucro_previsto": res_estoque['lucro_previsto']
    }
# --- FINANCEIRO E CONFIGURAÇÕES ---

def registrar_pagamento_cliente(cliente_id, valor_pago):
    conn = conectar_db()
    conn.execute('UPDATE clientes SET saldo_devedor = MAX(0, saldo_devedor - ?) WHERE id = ?', (valor_pago, cliente_id))
    conn.commit()
    conn.close()

def obter_extrato_cliente(cliente_id, usuario_id):
    conn = conectar_db()
    vendas = conn.execute('''
        SELECT strftime('%d/%m/%Y %H:%M', v.data) as data_formatada, p.nome as produto, 
               v.quantidade, v.valor_total, v.forma_pagamento
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        WHERE v.cliente_id = ? AND v.usuario_id = ?
        ORDER BY v.data DESC
    ''', (cliente_id, usuario_id)).fetchall()
    conn.close()
    return vendas

def atualizar_configuracao_fiado(cliente_id, permite, limite, usuario_id):
    conn = conectar_db()
    conn.execute('UPDATE clientes SET permite_fiado = ?, limite_fiado = ? WHERE id = ? AND usuario_id = ?', 
                 (permite, limite, cliente_id, usuario_id))
    conn.commit()
    conn.close()

# --- CRIAÇÃO DAS TABELAS E MIGRAÇÕES ---

def criar_tabelas():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # 1. Tabela de Usuários (com campo PIX)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            logo TEXT,
            pix TEXT,
            plano TEXT,
            data_expiracao TEXT
        )
    ''')

    # MIGRAÇÃO AUTOMÁTICA: Adiciona 'pix' se a tabela já existir sem ele
    cursor.execute("PRAGMA table_info(usuarios)")
    colunas = [col[1] for col in cursor.fetchall()]
    if 'pix' not in colunas:
        try:
            cursor.execute('ALTER TABLE usuarios ADD COLUMN pix TEXT')
            print("Migração: Coluna 'pix' adicionada com sucesso!")
        except: pass
    
    # 2. Tabela de Produtos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco_custo REAL,
            preco_venda REAL,
            quantidade INTEGER,
            usuario_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # 3. Tabela de Clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            saldo_devedor REAL DEFAULT 0,
            permite_fiado INTEGER DEFAULT 1,
            limite_fiado REAL DEFAULT 0,
            data_ultima_compra TEXT,
            usuario_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # 4. Tabela de Vendas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            cliente_id INTEGER,
            quantidade INTEGER,
            valor_total REAL,
            lucro REAL,
            forma_pagamento TEXT,
            data TEXT,
            usuario_id INTEGER,
            FOREIGN KEY (produto_id) REFERENCES produtos (id),
            FOREIGN KEY (cliente_id) REFERENCES clientes (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Sistema: Banco de dados e tabelas prontos para uso!")