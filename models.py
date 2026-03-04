import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json
import os
import logging

# --- CONFIGURAÇÃO DE LOGGING ---
# Os logs serão exibidos no console do Render e salvos em arquivo se local.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(), # Exibe no terminal (Render Logs)
        logging.FileHandler('sistema.log', encoding='utf-8') # Salva em arquivo local
    ]
)
logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO DE AMBIENTE ---
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def conectar_db():
    try:
        if DATABASE_URL:
            # Limpa a URL de parâmetros extras que o psycopg2 não gosta
            url = DATABASE_URL
            if "channel_binding" in url:
                url = url.split("&channel_binding")[0]
            
            # Garante o protocolo correto
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
                
            conn = psycopg2.connect(url)
            return conn
        else:
            # SQLite local
            DATABASE = 'database/smartcontrol.db'
            os.makedirs('database', exist_ok=True)
            conn = sqlite3.connect(DATABASE, timeout=10)
            conn.row_factory = sqlite3.Row
            return conn
    except Exception as e:
        logger.error(f"Falha crítica na conexão: {e}")
        raise

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
        logger.info(f"Novo usuário cadastrado: {email}")
        return True
    except Exception as e:
        logger.error(f"Erro ao cadastrar usuário {email}: {e}")
        return False
    finally:
        conn.close()

def cadastrar_cliente(nome, telefone, limite, prazo, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'''
            INSERT INTO clientes (nome, telefone, saldo_devedor, permite_fiado, limite_fiado, prazo_pagamento, usuario_id)
            VALUES ({PL}, {PL}, 0.0, 1, {PL}, {PL}, {PL})
        ''', (nome.upper(), telefone, limite, prazo, usuario_id))
        conn.commit()
        logger.info(f"Cliente {nome} cadastrado pelo usuário ID {usuario_id}")
    except Exception as e:
        logger.error(f"Erro ao cadastrar cliente {nome}: {e}")
    finally:
        conn.close()     

def listar_todos_assinantes():
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute('SELECT id, nome, email, plano, data_expiracao FROM usuarios ORDER BY id DESC')
        rows = cursor.fetchall()
        resultado = []
        for r in rows:
            d = dict(r)
            try:
                exp = datetime.strptime(str(d['data_expiracao'])[:19], '%Y-%m-%d %H:%M:%S')
                d['dias_restantes'] = max(0, (exp - datetime.now()).days)
            except:
                d['dias_restantes'] = 0
            # Garante que data_expiracao nunca é None no template
            if not d.get('data_expiracao'):
                d['data_expiracao'] = '2000-01-01 00:00:00'
            resultado.append(d)
        return resultado
    finally:
        conn.close()

def renovar_assinatura(usuario_id, dias):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        nova_expiracao = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
        plano_nome = f"Plano {dias} Dias"
        cursor.execute(f"UPDATE usuarios SET data_expiracao = {PL}, plano = {PL} WHERE id = {PL}", 
                       (nova_expiracao, plano_nome, usuario_id))
        conn.commit()
        logger.info(f"Assinatura do usuário {usuario_id} renovada por {dias} dias.")
    finally:
        conn.close()

def excluir_usuario(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f"DELETE FROM vendas WHERE usuario_id = {PL}", (usuario_id,))
        cursor.execute(f"DELETE FROM produtos WHERE usuario_id = {PL}", (usuario_id,))
        cursor.execute(f"DELETE FROM clientes WHERE usuario_id = {PL}", (usuario_id,))
        cursor.execute(f"DELETE FROM usuarios WHERE id = {PL}", (usuario_id,))
        conn.commit()
        logger.warning(f"USUÁRIO EXCLUÍDO DEFINITIVAMENTE: ID {usuario_id}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao excluir usuário {usuario_id}: {e}")
        raise e 
    finally:
        conn.close()

def atualizar_senha_usuario(usuario_id, nova_senha):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f"UPDATE usuarios SET senha = {PL} WHERE id = {PL}", (nova_senha, usuario_id))
        conn.commit()
        logger.info(f"Senha alterada para o usuário ID {usuario_id}")
        return True
    except Exception as e:
        logger.error(f"Erro ao mudar senha ID {usuario_id}: {e}")
        return False
    finally:
        conn.close()

def obter_dados_assinante(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'SELECT nome, plano, data_expiracao FROM usuarios WHERE id = {PL}', (usuario_id,))
        user = cursor.fetchone()
        if user:
            try:
                exp_str = str(user['data_expiracao'])[:19]
                expiracao = datetime.strptime(exp_str, '%Y-%m-%d %H:%M:%S')
                restantes = (expiracao - datetime.now()).days
                return {'nome': user['nome'], 'plano': user['plano'], 'dias_restantes': max(0, restantes)}
            except:
                return {'nome': user['nome'], 'plano': user['plano'], 'dias_restantes': 0}
        return None
    finally:
        conn.close()

# --- FUNÇÕES DE NEGÓCIO ---

def cadastrar_produto(nome, preco_custo, preco_venda, quantidade, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'''
            INSERT INTO produtos (nome, preco_custo, preco_venda, quantidade, usuario_id)
            VALUES ({PL}, {PL}, {PL}, {PL}, {PL})
        ''', (nome.upper(), preco_custo, preco_venda, quantidade, usuario_id))
        conn.commit()
    finally:
        conn.close()

def listar_produtos(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'SELECT * FROM produtos WHERE usuario_id = {PL} ORDER BY nome ASC', (usuario_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def listar_clientes(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'SELECT * FROM clientes WHERE usuario_id = {PL} ORDER BY nome ASC', (usuario_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def obter_cliente_por_id(cliente_id, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'SELECT * FROM clientes WHERE id = {PL} AND usuario_id = {PL}', (cliente_id, usuario_id))
        return cursor.fetchone()
    finally:
        conn.close()

# --- SISTEMA DE VENDAS E HISTÓRICO ---

def listar_vendas(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'''
            SELECT v.*, p.nome AS produto_nome, c.nome AS cliente_nome
            FROM vendas v
            JOIN produtos p ON v.produto_id = p.id
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.usuario_id = {PL}
            ORDER BY v.data DESC LIMIT 100
        ''', (usuario_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def processar_venda_completa(itens_json, cliente_id, forma_pagamento, usuario_id):
    if not itens_json: return False
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        itens = json.loads(itens_json)
        data_agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_venda_geral = 0

        for item in itens:
            p_id = item['id']
            qtd = int(item['qtd'])
            
            cursor.execute(f"SELECT preco_custo, preco_venda, quantidade FROM produtos WHERE id = {PL} AND usuario_id = {PL}", (p_id, usuario_id))
            prod = cursor.fetchone()
            
            if not prod or prod['quantidade'] < qtd:
                logger.warning(f"Venda negada: Estoque insuficiente produto {p_id} (Usuário {usuario_id})")
                raise Exception(f"Estoque insuficiente")

            v_total = float(prod['preco_venda']) * qtd
            lucro = (float(prod['preco_venda']) - float(prod['preco_custo'])) * qtd
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
                WHERE id = {PL} AND usuario_id = {PL}
            """, (total_venda_geral, data_agora, cliente_id, usuario_id))
        
        conn.commit()
        logger.info(f"Venda processada com sucesso. Valor: R${total_venda_geral:.2f} (Usuário {usuario_id})")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao processar venda completa: {e}")
        return False
    finally:
        conn.close()

def obter_resumo_financeiro(usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'SELECT COALESCE(SUM(valor_total), 0) as f, COALESCE(SUM(lucro), 0) as l FROM vendas WHERE usuario_id={PL}', (usuario_id,))
        res_vendas = cursor.fetchone()

        cursor.execute(f'SELECT COALESCE(SUM(quantidade*preco_venda), 0) as v, COALESCE(SUM(quantidade*(preco_venda-preco_custo)), 0) as lp FROM produtos WHERE usuario_id={PL}', (usuario_id,))
        res_estoque = cursor.fetchone()

        cursor.execute(f'SELECT COALESCE(SUM(saldo_devedor), 0) as t FROM clientes WHERE usuario_id={PL} AND saldo_devedor>0', (usuario_id,))
        res_fiado = cursor.fetchone()

        return {
            'faturamento': float(res_vendas['f'] or 0),
            'lucro': float(res_vendas['l'] or 0),
            'valor_estoque': float(res_estoque['v'] or 0),
            'lucro_previsto': float(res_estoque['lp'] or 0),
            'total_fiado': float(res_fiado['t'] or 0)
        }
    finally:
        conn.close()

# --- FINANCEIRO E CONFIGURAÇÕES ---

def registrar_pagamento_cliente(cliente_id, valor_pago):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'UPDATE clientes SET saldo_devedor = saldo_devedor - {PL} WHERE id = {PL}', (valor_pago, cliente_id))
        cursor.execute(f'UPDATE clientes SET saldo_devedor = 0 WHERE id = {PL} AND saldo_devedor < 0', (cliente_id,))
        conn.commit()
        logger.info(f"Pagamento registrado: R${valor_pago} para cliente ID {cliente_id}")
    finally:
        conn.close()

def obter_extrato_cliente(cliente_id, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        c_id = int(cliente_id)
        if DATABASE_URL:
            sql_data = "to_char(v.data::timestamp, 'DD/MM/YYYY HH24:MI')"
        else:
            sql_data = "strftime('%d/%m/%Y %H:%M', v.data)"

        cursor.execute(f'''
            SELECT {sql_data} as data_formatada, p.nome as produto, v.quantidade, v.valor_total, v.forma_pagamento
            FROM vendas v JOIN produtos p ON v.produto_id = p.id
            WHERE v.cliente_id = {PL} AND v.usuario_id = {PL}
            ORDER BY v.data DESC
        ''', (c_id, usuario_id))
        return cursor.fetchall()
    finally:
        conn.close()

def atualizar_configuracao_fiado(cliente_id, permite, limite, usuario_id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'UPDATE clientes SET permite_fiado = {PL}, limite_fiado = {PL} WHERE id = {PL} AND usuario_id = {PL}', 
                      (permite, limite, cliente_id, usuario_id))
        conn.commit()
    finally:
        conn.close()

def assinatura_ativa(usuario_id):
    """Verifica se o utilizador ainda tem dias de acesso restantes"""
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        cursor.execute(f'SELECT data_expiracao FROM usuarios WHERE id = {PL}', (usuario_id,))
        user = cursor.fetchone()
        if user:
            # Converte a string do banco para objeto datetime
            exp_str = str(user['data_expiracao'])[:19]
            expiracao = datetime.strptime(exp_str, '%Y-%m-%d %H:%M:%S')
            
            # Se a expiração for maior que agora, está ativo
            return expiracao > datetime.now()
        return False
    except Exception as e:
        logger.error(f"Erro ao verificar assinatura do ID {usuario_id}: {e}")
        return False
    finally:
        conn.close()

def obter_metricas_globais_admin():
    """Retorna números totais da plataforma (apenas para o Admin)"""
    conn = conectar_db()
    cursor = obter_cursor(conn)
    try:
        # Total de usuários
        cursor.execute('SELECT COUNT(*) as total FROM usuarios')
        total_users = cursor.fetchone()
        
        # Total de vendas processadas na plataforma
        cursor.execute('SELECT SUM(valor_total) as f, SUM(lucro) as l FROM vendas')
        vendas_globais = cursor.fetchone()
        
        # Usuários que expiram nos próximos 3 dias
        hoje = datetime.now()
        prazo = (hoje + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(f'SELECT COUNT(*) as total FROM usuarios WHERE data_expiracao <= {PL}', (prazo,))
        prestes_a_vencer = cursor.fetchone()

        return {
            'total_usuarios': total_users['total'] if not DATABASE_URL else total_users['total'],
            'faturamento_plataforma': float(vendas_globais['f'] or 0),
            'lucro_plataforma': float(vendas_globais['l'] or 0),
            'usuarios_vencendo': prestes_a_vencer['total']
        }
    finally:
        conn.close()     

def criar_tabelas():
    conn = conectar_db()
    cursor = obter_cursor(conn)
    id_type = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    real_type = "DOUBLE PRECISION" if DATABASE_URL else "REAL"
    try:
        cursor.execute(f'CREATE TABLE IF NOT EXISTS usuarios (id {id_type}, nome TEXT NOT NULL, email TEXT UNIQUE NOT NULL, senha TEXT NOT NULL, logo TEXT, pix TEXT, plano TEXT, data_expiracao TEXT)')
        cursor.execute(f'CREATE TABLE IF NOT EXISTS produtos (id {id_type}, nome TEXT NOT NULL, preco_custo {real_type}, preco_venda {real_type}, quantidade INTEGER, usuario_id INTEGER)')
        cursor.execute(f'CREATE TABLE IF NOT EXISTS clientes (id {id_type}, nome TEXT NOT NULL, telefone TEXT, saldo_devedor {real_type} DEFAULT 0, permite_fiado INTEGER DEFAULT 1, limite_fiado {real_type} DEFAULT 0, prazo_pagamento INTEGER DEFAULT 15, data_ultima_compra TEXT, usuario_id INTEGER)')
        cursor.execute(f'CREATE TABLE IF NOT EXISTS vendas (id {id_type}, produto_id INTEGER, cliente_id INTEGER, quantidade INTEGER, valor_total {real_type}, lucro {real_type}, forma_pagamento TEXT, data TEXT, usuario_id INTEGER)')
        conn.commit()
        logger.info("Tabelas verificadas/criadas com sucesso.")
    finally:
        conn.close()