from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import json
import os
import urllib.parse
from werkzeug.utils import secure_filename
import sqlite3 

# Importando TODAS as funções do models
from models import (
    listar_produtos, listar_clientes, cadastrar_produto, 
    cadastrar_cliente, conectar_db, 
    cadastrar_usuario, listar_todos_assinantes, 
    renovar_assinatura, excluir_usuario,
    obter_dados_assinante, obter_resumo_financeiro, 
    listar_vendas, registrar_pagamento_cliente,
    obter_cliente_por_id, obter_extrato_cliente, atualizar_configuracao_fiado,
    processar_venda_completa, criar_tabelas
)

app = Flask(__name__)
app.secret_key = 'smartcontrol_chave_secreta_99'

# Configuração de Upload de Logo
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ADMIN_EMAIL = "jhoelssonmarcelyno@gmail.com"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- LOGIN / REGISTRAR / LOGOUT ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_digitado = request.form.get('email').lower().strip()
        senha = request.form.get('senha')

        conn = conectar_db()
        conn.row_factory = sqlite3.Row 
        usuario = conn.execute('SELECT * FROM usuarios WHERE email = ?', (email_digitado,)).fetchone()
        conn.close()

        if usuario and usuario['senha'] == senha:
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            session['usuario_email'] = usuario['email'].lower().strip()
            
            if session['usuario_email'] == ADMIN_EMAIL.lower().strip():
                return redirect(url_for('admin_assinantes'))
                
            return redirect(url_for('index'))
        else:
            flash('E-mail ou senha incorretos!', 'erro')
    return render_template('login.html')

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email'].lower().strip()
        senha = request.form['senha']
        if cadastrar_usuario(nome, email, senha):
            return redirect(url_for('login'))
        else:
            flash('Erro ao registrar. O e-mail já pode estar em uso.', 'erro')
    return render_template('registrar.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD (PÁGINA PRINCIPAL) ---
@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    assinante = obter_dados_assinante(usuario_id)
    resumo = obter_resumo_financeiro(usuario_id)
    produtos = listar_produtos(usuario_id)
    clientes_list = listar_clientes(usuario_id)
    
    # Cálculos para os Cards
    total_estoque = sum(p['quantidade'] for p in produtos) if produtos else 0
    
    # Busca valor total de FIADO (Pendências) para o Card de Ações Rápidas
    conn = conectar_db()
    res_fiado = conn.execute("""
        SELECT SUM(valor_total) FROM vendas 
        WHERE forma_pagamento = 'Fiado' AND usuario_id = ?
    """, (usuario_id,)).fetchone()
    total_fiado = res_fiado[0] if res_fiado[0] else 0
    conn.close()

    alertas_estoque = [p for p in produtos if p['quantidade'] < 5] if produtos else []
    
    return render_template('index.html', 
                           assinante=assinante, 
                           resumo=resumo, 
                           produtos=produtos[:5], 
                           total_estoque=total_estoque, 
                           total_fiado=total_fiado,
                           alertas_estoque=alertas_estoque)

# --- SISTEMA DE RELATÓRIOS ---
@app.route('/relatorios_painel')
def relatorios_painel():
    if 'usuario_id' not in session: 
        return redirect(url_for('login'))
    return render_template('relatorios_menu.html')

@app.route('/relatorios')
def relatorios():
    if 'usuario_id' not in session: 
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    periodo = request.args.get('periodo', 'dia')
    
    hoje = datetime.now()
    if periodo == 'dia':
        data_inicio = hoje.strftime('%Y-%m-%d 00:00:00')
    elif periodo == 'semana':
        data_inicio = (hoje - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
    elif periodo == 'mes':
        data_inicio = (hoje - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
    else: # ano
        data_inicio = (hoje - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')

    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    
    # SQL Agrupado: Soma quantidades e valores totais por produto
    query = """
        SELECT 
            p.nome as produto_nome, 
            SUM(v.quantidade) as quantidade_total,
            SUM(v.valor_total) as faturamento_total,
            p.preco_venda, 
            p.preco_custo,
            MAX(v.data) as ultima_venda
        FROM vendas v 
        JOIN produtos p ON v.produto_id = p.id 
        WHERE v.usuario_id = ? AND v.data >= ?
        GROUP BY p.nome
        ORDER BY faturamento_total DESC
    """
    rows = conn.execute(query, (usuario_id, data_inicio)).fetchall()
    conn.close()

    vendas_agrupadas = []
    for row in rows:
        item = dict(row)
        # Formata a data da última venda do produto para exibir no relatório
        try:
            dt = datetime.strptime(item['ultima_venda'][:19], '%Y-%m-%d %H:%M:%S')
            item['ultima_venda_formatada'] = dt.strftime('%d/%m/%Y')
        except:
            item['ultima_venda_formatada'] = "---"
        vendas_agrupadas.append(item)

    # Cálculos Totais do Rodapé
    total_faturado = sum(v['faturamento_total'] for v in vendas_agrupadas)
    total_custo = sum(v['quantidade_total'] * v['preco_custo'] for v in vendas_agrupadas)
    lucro = total_faturado - total_custo

    return render_template('relatorios.html', 
                           vendas=vendas_agrupadas, 
                           periodo=periodo.upper(), 
                           total=total_faturado, 
                           lucro=lucro)

# --- GESTÃO DE INADIMPLENTES ---
@app.route('/relatorio/inadimplentes')
def relatorio_inadimplentes():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    
    user_data = conn.execute('SELECT pix FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    chave_pix = user_data['pix'] if user_data and user_data['pix'] else "[CADASTRE SEU PIX NAS CONFIGURAÇÕES]"

    query = """
        SELECT 
            c.id as cliente_id,
            c.nome as cliente_nome, 
            c.telefone as cliente_telefone,
            SUM(v.valor_total) as total_devido,
            GROUP_CONCAT(p.nome || ' (x' || v.quantidade || ')', ' | ') as detalhes_itens,
            MAX(v.data) as ultima_venda
        FROM vendas v
        JOIN clientes c ON v.cliente_id = c.id
        JOIN produtos p ON v.produto_id = p.id
        WHERE v.forma_pagamento = 'Fiado' AND v.usuario_id = ?
        GROUP BY v.cliente_id
        ORDER BY total_devido DESC
    """
    devedores_raw = conn.execute(query, (usuario_id,)).fetchall()
    conn.close()

    devedores = []
    for d in devedores_raw:
        item = dict(d)
        try:
            dt = datetime.strptime(item['ultima_venda'][:19], '%Y-%m-%d %H:%M:%S')
            item['data_formatada'] = dt.strftime('%d/%m/%Y')
        except:
            item['data_formatada'] = "Data pendente"
        devedores.append(item)
    
    return render_template('inadimplentes.html', devedores=devedores, chave_pix=chave_pix)

@app.route('/venda/dar-baixa/<int:id>', methods=['POST'])
def dar_baixa_pagamento(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    conn = conectar_db()
    
    try:
        conn.execute("""
            UPDATE vendas 
            SET forma_pagamento = 'Pago', valor_total = 0
            WHERE cliente_id = ? AND usuario_id = ? AND forma_pagamento = 'Fiado'
        """, (id, usuario_id))
        
        conn.execute("""
            UPDATE clientes 
            SET saldo_devedor = 0 
            WHERE id = ? AND usuario_id = ?
        """, (id, usuario_id))
        
        conn.commit()
        flash('Dívida total quitada com sucesso!', 'sucesso')
    except Exception as e:
        print(f"Erro ao dar baixa: {e}")
        flash('Erro ao processar o pagamento.', 'erro')
    finally:
        conn.close()
        
    return redirect(url_for('relatorio_inadimplentes'))

# --- CONFIGURAÇÕES ---
@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    conn = conectar_db()
    conn.row_factory = sqlite3.Row

    if request.method == 'POST':
        novo_nome = request.form.get('nome') 
        nova_pix = request.form.get('pix')
        arquivo = request.files.get('logo')
        
        user_atual = conn.execute('SELECT logo FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
        filename = user_atual['logo'] if user_atual else None

        if arquivo and arquivo.filename != '':
            if allowed_file(arquivo.filename):
                ext = arquivo.filename.rsplit('.', 1)[1].lower()
                filename = f"logo_user_{usuario_id}.{ext}"
                arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn.execute('UPDATE usuarios SET nome = ?, logo = ?, pix = ? WHERE id = ?', 
                     (novo_nome, filename, nova_pix, usuario_id))
        conn.commit()
        
        session['nome'] = novo_nome
        session['usuario_logo'] = filename
        flash('Configurações atualizadas com sucesso!', 'sucesso')
        conn.close()
        return redirect(url_for('index'))

    user_info = conn.execute('SELECT * FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    conn.close()
    return render_template('configuracoes.html', user=user_info)

# --- PRODUTOS ---
@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    conn = conectar_db()

    if request.method == 'POST':
        nome = request.form.get('nome').strip().upper()
        preco_custo = float(request.form.get('preco_custo'))
        preco_venda = float(request.form.get('preco_venda'))
        quantidade = int(request.form.get('quantidade')) 

        conn.execute('INSERT INTO produtos (nome, preco_custo, preco_venda, quantidade, usuario_id) VALUES (?, ?, ?, ?, ?)',
                     (nome, preco_custo, preco_venda, quantidade, usuario_id)) 
        
        conn.commit()
        conn.close()
        flash('Produto cadastrado!', 'sucesso')
        return redirect(url_for('produtos'))

    produtos_lista = conn.execute('SELECT * FROM produtos WHERE usuario_id = ? ORDER BY nome ASC', (usuario_id,)).fetchall()
    conn.close()
    return render_template('produtos.html', produtos=produtos_lista)

@app.route('/excluir_produto/<int:id>')
def excluir_produto(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conn = conectar_db()
    conn.execute('DELETE FROM produtos WHERE id = ? AND usuario_id = ?', (id, session['usuario_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('produtos'))

# --- CLIENTES ---
@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip().upper()
        telefone = request.form.get('telefone')
        limite = request.form.get('limite_credito')
        limite = float(limite) if limite else 0.0
        
        if nome:
            conn = conectar_db()
            existente = conn.execute('SELECT id FROM clientes WHERE nome = ? AND usuario_id = ?', 
                                     (nome, usuario_id)).fetchone()
            
            if existente:
                conn.close()
                flash('Erro: Já existe um cliente com este nome!', 'erro')
                return redirect(url_for('clientes'))
            
            conn.execute('''
                INSERT INTO clientes (nome, telefone, limite_fiado, usuario_id, saldo_devedor, permite_fiado) 
                VALUES (?, ?, ?, ?, 0, 1)
            ''', (nome, telefone, limite, usuario_id))
            conn.commit()
            conn.close()
            flash('Cliente cadastrado!', 'sucesso')
            return redirect(url_for('clientes'))
    
    lista_clientes = listar_clientes(usuario_id)
    clientes_com_fiado = []
    
    for c in lista_clientes:
        cliente_dict = dict(c)
        if cliente_dict.get('telefone'):
            num = ''.join(filter(str.isdigit, str(cliente_dict['telefone'])))
            cliente_dict['link_zap'] = f"https://wa.me/55{num}"
        clientes_com_fiado.append(cliente_dict)
        
    return render_template('clientes.html', clientes=clientes_com_fiado)


@app.route('/quitar_fiado/<int:id>', methods=['POST'])
def quitar_fiado(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    valor_pago = float(request.form.get('valor_pago') or 0)
    enviar_whats = request.form.get('enviar_whatsapp')
    
    if valor_pago > 0:
        # 1. Registrar o pagamento na tabela de históricos/saldo do cliente
        registrar_pagamento_cliente(id, valor_pago)
        
        # 2. Corrigir o total em aberto nas vendas individuais (Abatimento em cascata)
        conn = conectar_db()
        conn.row_factory = sqlite3.Row
        vendas_fiado = conn.execute("""
            SELECT id, valor_total FROM vendas 
            WHERE cliente_id = ? AND forma_pagamento = 'Fiado' AND usuario_id = ?
            ORDER BY data ASC
        """, (id, usuario_id)).fetchall()
        
        saldo_pagamento = valor_pago
        for v in vendas_fiado:
            if saldo_pagamento <= 0: break
            
            v_id = v['id']
            v_valor = v['valor_total']
            
            if saldo_pagamento >= v_valor:
                # Quita esta venda totalmente
                conn.execute("UPDATE vendas SET valor_total = 0, forma_pagamento = 'Pago' WHERE id = ?", (v_id,))
                saldo_pagamento -= v_valor
            else:
                # Quita apenas uma parte desta venda
                novo_total = v_valor - saldo_pagamento
                conn.execute("UPDATE vendas SET valor_total = ? WHERE id = ?", (novo_total, v_id))
                saldo_pagamento = 0
        
        conn.commit()
        
        # 3. Lógica do WhatsApp
        cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (id,)).fetchone()
        conn.close()

        if enviar_whats and cliente:
            msg = f"Olá {cliente['nome']}, recebemos seu pagamento de R$ {valor_pago:.2f}. Obrigado!"
            msg_encoded = urllib.parse.quote(msg)
            telefone = "".join(filter(str.isdigit, cliente['telefone'] or ""))
            if telefone:
                return redirect(f"https://wa.me/55{telefone}?text={msg_encoded}")

    return redirect(url_for('clientes'))

# --- VENDAS ---
@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']

    if request.method == 'POST':
        itens_json = request.form.get('itens_json')
        cliente_id = request.form.get('cliente_id')
        forma_pagamento = request.form.get('forma_pagamento')

        if itens_json:
            try:
                c_id = int(cliente_id) if cliente_id and cliente_id.strip() != "" else None
                sucesso = processar_venda_completa(itens_json, c_id, forma_pagamento, usuario_id)
                if sucesso:
                    flash('Venda realizada com sucesso!', 'sucesso')
                else:
                    flash('Erro ao processar venda.', 'erro')
                return redirect(url_for('vendas'))
            except Exception as e:
                flash(f'Erro técnico: {str(e)}', 'erro')
                return redirect(url_for('vendas'))

    vendas_raw = listar_vendas(usuario_id)
    vendas_formatadas = []

    for v in vendas_raw:
        venda_dict = dict(v)
        try:
            data_str = venda_dict.get('data', '')
            dt = datetime.strptime(data_str[:19], '%Y-%m-%d %H:%M:%S')
            venda_dict['data_formatada'] = dt.strftime('%d/%m/%Y %H:%M')
        except:
            venda_dict['data_formatada'] = venda_dict.get('data')
        
        vendas_formatadas.append(venda_dict)

    return render_template('vendas.html', 
                            produtos=listar_produtos(usuario_id), 
                            clientes=listar_clientes(usuario_id), 
                            vendas=vendas_formatadas)

@app.route('/venda/<int:id>/comprovante')
def comprovante_venda(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conn = conectar_db()
    venda_ref = conn.execute("""
        SELECT v.*, c.nome as cliente_nome, c.telefone as cliente_telefone, u.nome as empresa_nome
        FROM vendas v
        LEFT JOIN clientes c ON v.cliente_id = c.id
        LEFT JOIN usuarios u ON v.usuario_id = u.id
        WHERE v.id = ? AND v.usuario_id = ?
    """, (id, session['usuario_id'])).fetchone()

    if not venda_ref:
        conn.close()
        return redirect(url_for('vendas'))

    itens_venda = conn.execute("""
        SELECT v.*, p.nome as produto_nome
        FROM vendas v
        LEFT JOIN produtos p ON v.produto_id = p.id
        WHERE v.data = ? AND v.usuario_id = ?
    """, (venda_ref['data'], session['usuario_id'])).fetchall()
    conn.close()

    total_geral = sum(item['valor_total'] for item in itens_venda)
    return render_template('comprovante.html', venda=venda_ref, itens=itens_venda, total=total_geral)

# --- PLANOS E ADMIN ---
@app.route('/planos')
def planos():
    if session.get('usuario_email') == ADMIN_EMAIL.lower().strip(): 
        return redirect(url_for('admin_assinantes'))
    return render_template('planos.html')

@app.route('/admin/assinantes')
def admin_assinantes():
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL:
        return "Proibido", 403
    return render_template('admin_assinantes.html', assinantes=listar_todos_assinantes())

@app.route('/admin/renovar/<int:id>/<int:dias>')
def renovar(id, dias):
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL: return "Proibido", 403
    renovar_assinatura(id, dias)
    return redirect(url_for('admin_assinantes'))

@app.route('/admin/excluir/<int:id>')
def admin_excluir(id):
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL: return "Proibido", 403
    excluir_usuario(id)
    return redirect(url_for('admin_assinantes'))

@app.route('/financas')
def financas():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    resumo_data = obter_resumo_financeiro(session['usuario_id']) 
    return render_template('financas.html', resumo=resumo_data)

@app.route('/temas')
def temas():
    return render_template('temas.html')

if __name__ == '__main__':
    criar_tabelas() 
    app.run(debug=True, host='0.0.0.0')