from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import json
import os
import urllib.parse
import sqlite3
from werkzeug.utils import secure_filename

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

# --- AUXILIARES ---
def atualizar_senha_usuario(usuario_id, nova_senha):
    try:
        conn = conectar_db()
        conn.execute('UPDATE usuarios SET senha = ? WHERE id = ?', (nova_senha, usuario_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def atualizar_estrutura_banco():
    conn = conectar_db()
    try:
        conn.execute('ALTER TABLE clientes ADD COLUMN prazo_pagamento INTEGER DEFAULT 15')
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

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
            session['usuario_logo'] = usuario['logo'] 
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

# --- DASHBOARD ---
@app.route('/')
def index():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    resumo = obter_resumo_financeiro(usuario_id)
    assinante = obter_dados_assinante(usuario_id)
    produtos = listar_produtos(usuario_id)
    alertas_estoque = [p for p in produtos if p['quantidade'] < 5]
    return render_template('index.html', resumo=resumo, assinante=assinante, alertas_estoque=alertas_estoque)

# --- PERFIL DO CLIENTE (CORRIGIDO PARA O JINJA) ---
@app.route('/cliente/<int:id>')
@app.route('/detalhes_cliente/<int:id>')
def detalhes_cliente(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ? AND usuario_id = ?', (id, usuario_id)).fetchone()
    if not cliente:
        conn.close()
        flash("Cliente não encontrado!", "erro")
        return redirect(url_for('clientes'))

    vendas_query = conn.execute('''
        SELECT p.nome as produto, v.quantidade, v.valor_total, v.data, v.forma_pagamento 
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        WHERE v.cliente_id = ? AND v.usuario_id = ? 
        ORDER BY v.data DESC
    ''', (id, usuario_id)).fetchall()
    
    extrato = []
    for v in vendas_query:
        vd = dict(v)
        data_origem = vd.get('data')
        # Garante que data_dia sempre exista para o groupby do Jinja não dar erro
        if data_origem:
            try:
                dt_obj = datetime.strptime(str(data_origem)[:10], '%Y-%m-%d')
                vd['data_dia'] = dt_obj.strftime('%d/%m/%Y')
                vd['data_formatada'] = dt_obj.strftime('%d/%m/%Y %H:%M')
            except:
                vd['data_dia'] = "Data Indefinida"
                vd['data_formatada'] = str(data_origem)
        else:
            vd['data_dia'] = "Sem Data"
            vd['data_formatada'] = "---"
        extrato.append(vd)
    conn.close()
    return render_template('perfil_devedor.html', cliente=cliente, extrato=extrato)

# --- CLIENTES ---
@app.route('/clientes', methods=['GET', 'POST'])
@app.route('/gestao_clientes', methods=['GET', 'POST'])
def clientes():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip().upper()
        telefone = request.form.get('telefone')
        limite = float(request.form.get('limite_credito') or 0.0)
        prazo = int(request.form.get('prazo_pagamento') or 15)
        existente = conn.execute('SELECT id FROM clientes WHERE nome = ? AND usuario_id = ?', (nome, usuario_id)).fetchone()
        if existente: flash('Erro: Já existe um cliente com este nome!', 'erro')
        else:
            conn.execute('INSERT INTO clientes (nome, telefone, limite_fiado, prazo_pagamento, usuario_id, saldo_devedor, permite_fiado) VALUES (?, ?, ?, ?, ?, 0, 1)', (nome, telefone, limite, prazo, usuario_id))
            conn.commit()
            flash('Cliente cadastrado!', 'sucesso')
        conn.close()
        return redirect(url_for('clientes'))

    lista_c = conn.execute('SELECT * FROM clientes WHERE usuario_id = ? ORDER BY nome', (usuario_id,)).fetchall()
    hoje = datetime.now()
    clientes_formatados = []
    for c in lista_c:
        d = dict(c)
        if d.get('telefone'): d['link_zap'] = f"https://wa.me/55{''.join(filter(str.isdigit, str(d['telefone'])))}"
        venda_rec = conn.execute('SELECT MAX(data) FROM vendas WHERE cliente_id=? AND usuario_id=?', (d['id'], usuario_id)).fetchone()
        d['dias_atraso'], d['data_formatada'] = 0, "Sem compras"
        if venda_rec and venda_rec[0]:
            try:
                dt_v = datetime.strptime(venda_rec[0][:19], '%Y-%m-%d %H:%M:%S')
                d['data_formatada'] = dt_v.strftime('%d/%m/%Y')
                venc = dt_v + timedelta(days=int(d.get('prazo_pagamento') or 15))
                if hoje > venc and d.get('saldo_devedor', 0) > 0: d['dias_atraso'] = (hoje - venc).days
            except: pass
        clientes_formatados.append(d)
    conn.close()
    return render_template('clientes.html', clientes=clientes_formatados)

@app.route('/editar_cliente/<int:id>', methods=['POST'])
def editar_cliente(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    nome, tel = request.form.get('nome').upper(), request.form.get('telefone')
    limite, prazo = request.form.get('limite_credito'), int(request.form.get('prazo_pagamento') or 15)
    conn = conectar_db()
    conn.execute('UPDATE clientes SET nome=?, telefone=?, limite_fiado=?, prazo_pagamento=? WHERE id=? AND usuario_id=?', (nome, tel, limite, prazo, id, session['usuario_id']))
    conn.commit()
    conn.close()
    flash('Dados atualizados!', 'sucesso')
    return redirect(url_for('clientes'))

# --- FINANCEIRO E QUITAÇÕES ---
@app.route('/financas')
def financas():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    return render_template('financas.html', resumo=obter_resumo_financeiro(session['usuario_id']))

@app.route('/quitar_total/<int:cliente_id>', methods=['POST'])
def quitar_total(cliente_id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conn = conectar_db()
    conn.execute("UPDATE vendas SET forma_pagamento='Pago' WHERE cliente_id=? AND forma_pagamento='Fiado' AND usuario_id=?", (cliente_id, session['usuario_id']))
    conn.execute("UPDATE clientes SET saldo_devedor=0 WHERE id=? AND usuario_id=?", (cliente_id, session['usuario_id']))
    conn.commit()
    conn.close()
    flash('Dívida liquidada!', 'sucesso')
    return redirect(url_for('detalhes_cliente', id=cliente_id))

@app.route('/quitar_parcial/<int:cliente_id>', methods=['POST'])
def quitar_parcial(cliente_id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    valor_pago = float(request.form.get('valor_pago', 0))
    if valor_pago <= 0: return redirect(url_for('detalhes_cliente', id=cliente_id))
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    vendas = conn.execute("SELECT id, valor_total FROM vendas WHERE cliente_id=? AND forma_pagamento='Fiado' AND usuario_id=? ORDER BY data ASC", (cliente_id, session['usuario_id'])).fetchall()
    restante = valor_pago
    for v in vendas:
        if restante <= 0: break
        if restante >= v['valor_total']:
            conn.execute("UPDATE vendas SET forma_pagamento='Pago' WHERE id=?", (v['id'],))
            restante -= v['valor_total']
        else: break
    conn.execute("UPDATE clientes SET saldo_devedor = MAX(0, saldo_devedor - ?) WHERE id=? AND usuario_id=?", (valor_pago, cliente_id, session['usuario_id']))
    conn.commit()
    conn.close()
    flash(f'Abatimento de R$ {valor_pago:.2f} realizado!', 'sucesso')
    return redirect(url_for('detalhes_cliente', id=cliente_id))

@app.route('/quitar_fiado/<int:id>', methods=['POST'])
def quitar_fiado(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    val = float(request.form.get('valor_pago') or 0)
    if val > 0:
        registrar_pagamento_cliente(id, val)
        conn = conectar_db()
        conn.row_factory = sqlite3.Row
        vendas = conn.execute("SELECT id, valor_total FROM vendas WHERE cliente_id=? AND forma_pagamento='Fiado' AND usuario_id=? ORDER BY data ASC", (id, session['usuario_id'])).fetchall()
        sobra = val
        for v in vendas:
            if sobra <= 0: break
            if sobra >= v['valor_total']:
                conn.execute("UPDATE vendas SET valor_total=0, forma_pagamento='Pago' WHERE id=?", (v['id'],))
                sobra -= v['valor_total']
            else:
                conn.execute("UPDATE vendas SET valor_total=? WHERE id=?", (v['valor_total']-sobra, v['id']))
                sobra = 0
        conn.commit()
        cliente = conn.execute('SELECT * FROM clientes WHERE id=?', (id,)).fetchone()
        conn.close()
        if request.form.get('enviar_whatsapp') and cliente:
            msg = urllib.parse.quote(f"Olá {cliente['nome']}, recebemos R$ {val:.2f}. Obrigado!")
            tel = "".join(filter(str.isdigit, cliente['telefone'] or ""))
            return redirect(f"https://wa.me/55{tel}?text={msg}")
    return redirect(url_for('clientes'))

# --- PRODUTOS ---
@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    conn = conectar_db()
    if request.method == 'POST':
        nome, c, v, q = request.form.get('nome').strip().upper(), float(request.form.get('preco_custo')), float(request.form.get('preco_venda')), int(request.form.get('quantidade'))
        conn.execute('INSERT INTO produtos (nome, preco_custo, preco_venda, quantidade, usuario_id) VALUES (?, ?, ?, ?, ?)', (nome, c, v, q, usuario_id))
        conn.commit()
        flash('Produto cadastrado!', 'sucesso')
    produtos_lista = conn.execute('SELECT * FROM produtos WHERE usuario_id=? ORDER BY nome ASC', (usuario_id,)).fetchall()
    conn.close()
    return render_template('produtos.html', produtos=produtos_lista)

@app.route('/excluir_produto/<int:id>')
def excluir_produto(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conn = conectar_db()
    conn.execute('DELETE FROM produtos WHERE id=? AND usuario_id=?', (id, session['usuario_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('produtos'))

# --- VENDAS ---
@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    u_id = session['usuario_id']
    if request.method == 'POST':
        itens, c_id, forma = request.form.get('itens_json'), request.form.get('cliente_id'), request.form.get('forma_pagamento')
        if itens:
            cli = int(c_id) if c_id and c_id.strip() != "" else None
            if processar_venda_completa(itens, cli, forma, u_id): flash('Venda realizada!', 'sucesso')
            else: flash('Erro na venda.', 'erro')
            return redirect(url_for('vendas'))
    v_fmt = []
    for v in listar_vendas(u_id):
        d = dict(v)
        try: d['data_formatada'] = datetime.strptime(d['data'][:19], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
        except: d['data_formatada'] = d['data']
        v_fmt.append(d)
    return render_template('vendas.html', produtos=listar_produtos(u_id), clientes=listar_clientes(u_id), vendas=v_fmt)

@app.route('/venda/<int:id>/comprovante')
def comprovante_venda(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    v = conn.execute("SELECT v.*, c.nome as cliente_nome, u.nome as empresa_nome FROM vendas v LEFT JOIN clientes c ON v.cliente_id=c.id LEFT JOIN usuarios u ON v.usuario_id=u.id WHERE v.id=? AND v.usuario_id=?", (id, session['usuario_id'])).fetchone()
    if not v: return redirect(url_for('vendas'))
    itens = conn.execute("SELECT v.*, p.nome as produto_nome FROM vendas v LEFT JOIN produtos p ON v.produto_id=p.id WHERE v.data=? AND v.usuario_id=?", (v['data'], session['usuario_id'])).fetchall()
    conn.close()
    return render_template('comprovante.html', venda=v, itens=itens, total=sum(i['valor_total'] for i in itens))

# --- RELATÓRIOS E INADIMPLENTES ---
@app.route('/relatorios_painel')
def relatorios_painel():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    return render_template('relatorios_menu.html')

@app.route('/relatorios')
def relatorios():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    u_id, periodo = session['usuario_id'], request.args.get('periodo', 'dia')
    hoje = datetime.now()
    if periodo == 'dia': d_ini = hoje.strftime('%Y-%m-%d 00:00:00')
    elif periodo == 'semana': d_ini = (hoje - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
    elif periodo == 'mes': d_ini = (hoje - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
    else: d_ini = (hoje - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT p.nome as produto_nome, SUM(v.quantidade) as quantidade_total, SUM(v.valor_total) as faturamento_total, p.preco_venda, p.preco_custo, MAX(v.data) as ultima_venda FROM vendas v JOIN produtos p ON v.produto_id = p.id WHERE v.usuario_id = ? AND v.data >= ? GROUP BY p.nome ORDER BY faturamento_total DESC", (u_id, d_ini)).fetchall()
    v_agrup = []
    for r in rows:
        item = dict(r)
        try: item['ultima_venda_formatada'] = datetime.strptime(item['ultima_venda'][:19], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
        except: item['ultima_venda_formatada'] = "---"
        v_agrup.append(item)
    t_fat = sum(v['faturamento_total'] for v in v_agrup)
    t_custo = sum(v['quantidade_total'] * v['preco_custo'] for v in v_agrup)
    conn.close()
    return render_template('relatorios.html', vendas=v_agrup, periodo=periodo.upper(), total=t_fat, lucro=t_fat - t_custo)

@app.route('/relatorio/inadimplentes')
def relatorio_inadimplentes():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    u_id = session['usuario_id']
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    u_pix = conn.execute('SELECT pix FROM usuarios WHERE id=?', (u_id,)).fetchone()
    c_pix = u_pix['pix'] if u_pix and u_pix['pix'] else "[CADASTRE SEU PIX]"
    dev_raw = conn.execute("SELECT id, nome, telefone, prazo_pagamento, saldo_devedor, (SELECT MAX(data) FROM vendas WHERE cliente_id=clientes.id AND forma_pagamento='Fiado') as ultima_venda FROM clientes WHERE usuario_id=? AND saldo_devedor>0 ORDER BY saldo_devedor DESC", (u_id,)).fetchall()
    devedores, t_geral, maior = [], 0, 0
    for d in dev_raw:
        item = dict(d)
        item['telefone_limpo'] = "".join(filter(str.isdigit, str(item['telefone']))) if item['telefone'] else ""
        item['vencimento_br'], item['status_alerta'], item['dias_atraso'] = "---", "OK", 0
        if item['ultima_venda']:
            try:
                dt_v = datetime.strptime(item['ultima_venda'][:19], '%Y-%m-%d %H:%M:%S')
                venc = dt_v + timedelta(days=int(item['prazo_pagamento'] or 15))
                item['vencimento_br'], hoje = venc.strftime('%d/%m/%Y'), datetime.now()
                if hoje > venc: item['status_alerta'], item['dias_atraso'] = 'CRÍTICO', (hoje - venc).days
                elif (venc - hoje).days <= 2: item['status_alerta'] = 'PROXIMO'
            except: pass
        t_geral += item['saldo_devedor']
        if item['saldo_devedor'] > maior: maior = item['saldo_devedor']
        devedores.append(item)
    conn.close()
    return render_template('inadimplentes.html', devedores=devedores, chave_pix=c_pix, total_inadimplencia=t_geral, maior_divida=maior)

# --- CONFIGURAÇÕES ---
@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    u_id = session['usuario_id']
    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    if request.method == 'POST':
        nome, pix, arq = request.form.get('nome'), request.form.get('pix'), request.files.get('logo')
        user_at = conn.execute('SELECT logo FROM usuarios WHERE id=?', (u_id,)).fetchone()
        fname = user_at['logo'] if user_at else None
        if arq and allowed_file(arq.filename):
            fname = f"logo_user_{u_id}.{arq.filename.rsplit('.', 1)[1].lower()}"
            arq.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        conn.execute('UPDATE usuarios SET nome=?, logo=?, pix=? WHERE id=?', (nome, fname, pix, u_id))
        conn.commit()
        session['usuario_nome'], session['usuario_logo'] = nome, fname
        flash('Configurações salvas!', 'sucesso')
    u_info = conn.execute('SELECT * FROM usuarios WHERE id=?', (u_id,)).fetchone()
    conn.close()
    return render_template('configuracoes.html', user=u_info)

@app.route('/alterar_senha', methods=['POST'])
def alterar_senha():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    nova, conf = request.form.get('nova_senha'), request.form.get('confirmar_senha')
    if nova == conf and atualizar_senha_usuario(session['usuario_id'], nova): flash('Senha alterada!', 'sucesso')
    else: flash('Erro na senha!', 'erro')
    return redirect(url_for('configuracoes'))

# --- ADMIN E PLANOS ---
@app.route('/planos')
def planos(): return render_template('planos.html')

@app.route('/admin/assinantes')
def admin_assinantes():
    if session.get('usuario_email') != ADMIN_EMAIL: return "Proibido", 403
    return render_template('admin_assinantes.html', assinantes=listar_todos_assinantes())

@app.route('/admin/cadastrar_assinante', methods=['POST'])
def admin_cadastrar_assinante():
    if session.get('usuario_email') != ADMIN_EMAIL: return "Proibido", 403
    if cadastrar_usuario(request.form.get('nome'), request.form.get('email').lower().strip(), request.form.get('senha')): flash('Cadastrado!', 'sucesso')
    return redirect(url_for('admin_assinantes'))

@app.route('/admin/renovar/<int:id>/<int:dias>')
def renovar(id, dias):
    if session.get('usuario_email') != ADMIN_EMAIL: return "Proibido", 403
    renovar_assinatura(id, dias)
    return redirect(url_for('admin_assinantes'))

@app.route('/admin/excluir/<int:id>')
def admin_excluir(id):
    if session.get('usuario_email') != ADMIN_EMAIL: return "Proibido", 403
    excluir_usuario(id)
    return redirect(url_for('admin_assinantes'))

@app.route('/admin/resetar_senha/<int:id>')
def admin_resetar_senha(id):
    if session.get('usuario_email') != ADMIN_EMAIL: return "Proibido", 403
    atualizar_senha_usuario(id, "123456")
    flash('Resetada para 123456', 'sucesso')
    return redirect(url_for('admin_assinantes'))

if __name__ == '__main__':
    criar_tabelas()
    atualizar_estrutura_banco()
    app.run(debug=True, host='0.0.0.0')