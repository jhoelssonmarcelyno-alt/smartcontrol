from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from models import (listar_produtos, listar_clientes, cadastrar_produto, 
                    cadastrar_cliente, registrar_venda, conectar_db, 
                    cadastrar_usuario, listar_todos_assinantes, 
                    renovar_assinatura, excluir_usuario,
                    obter_dados_assinante, obter_resumo_financeiro, 
                    listar_vendas)
import json
import os
from werkzeug.utils import secure_filename

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
        email = request.form['email']
        senha = request.form['senha']
        conn = conectar_db()
        user = conn.execute('SELECT * FROM usuarios WHERE email = ? AND senha = ?', (email, senha)).fetchone()
        conn.close()
        if user:
            session['usuario_id'] = user['id']
            session['usuario_email'] = user['email']
            session['nome'] = user['nome']
            session['usuario_logo'] = user['logo'] if 'logo' in user.keys() else None
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        if cadastrar_usuario(nome, email, senha):
            return redirect(url_for('login'))
    return render_template('registrar.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- SISTEMA DE RELATÓRIOS (CORRIGIDO) ---

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
        data_inicio = hoje.strftime('%Y-%m-%d')
    elif periodo == 'semana':
        data_inicio = (hoje - timedelta(days=7)).strftime('%Y-%m-%d')
    elif periodo == 'mes':
        data_inicio = (hoje - timedelta(days=30)).strftime('%Y-%m-%d')
    else: # ano
        data_inicio = (hoje - timedelta(days=365)).strftime('%Y-%m-%d')

    conn = conectar_db()
    query = """
        SELECT v.*, p.nome as produto_nome, p.preco_venda, p.preco_custo 
        FROM vendas v 
        JOIN produtos p ON v.produto_id = p.id 
        WHERE v.usuario_id = ? AND v.data >= ?
        ORDER BY v.data DESC
    """
    rows = conn.execute(query, (usuario_id, data_inicio)).fetchall()
    conn.close()

    # CONVERSÃO: Transformamos as linhas do SQLite em dicionários Python mutáveis
    vendas_filtradas = [dict(row) for row in rows]

    # Agora o Python deixa você criar a 'data_formatada' sem erro!
    for venda in vendas_filtradas:
        try:
            # Pega os primeiros 10 caracteres (YYYY-MM-DD)
            data_db = venda.get('data', '')
            dt = datetime.strptime(data_db[:10], '%Y-%m-%d')
            venda['data_formatada'] = dt.strftime('%d/%m/%Y')
        except:
            venda['data_formatada'] = venda.get('data', 'Sem data')

    # Cálculos continuam iguais usando a lista convertida
    total_faturado = sum((v['quantidade'] or 0) * (v['preco_venda'] or 0) for v in vendas_filtradas) if vendas_filtradas else 0
    total_custo = sum((v['quantidade'] or 0) * (v['preco_custo'] or 0) for v in vendas_filtradas) if vendas_filtradas else 0
    lucro = total_faturado - total_custo

    return render_template('relatorios.html', 
                           vendas=vendas_filtradas, 
                           periodo=periodo.upper(), 
                           total=total_faturado, 
                           lucro=lucro)

# --- DASHBOARD ---
@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    assinante = obter_dados_assinante(usuario_id)
    resumo = obter_resumo_financeiro(usuario_id)
    produtos = listar_produtos(usuario_id)
    clientes = listar_clientes(usuario_id)
    total_estoque = sum(p['quantidade'] for p in produtos) if produtos else 0
    total_fiado = sum(c['saldo_devedor'] for c in clientes) if clientes else 0
    return render_template('index.html', assinante=assinante, resumo=resumo, 
                           produtos=produtos[:5], total_estoque=total_estoque, total_fiado=total_fiado)

# --- CONFIGURAÇÕES ---
@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    if request.method == 'POST':
        novo_nome = request.form.get('nome') 
        arquivo = request.files.get('logo')
        filename = session.get('usuario_logo')

        if arquivo and arquivo.filename != '':
            ext = arquivo.filename.rsplit('.', 1)[1].lower()
            filename = f"logo_user_{usuario_id}.{ext}"
            arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = conectar_db()
        conn.execute('UPDATE usuarios SET nome = ?, logo = ? WHERE id = ?', 
                     (novo_nome, filename, usuario_id))
        conn.commit()
        conn.close()
        
        session['nome'] = novo_nome
        session['usuario_logo'] = filename
        return redirect(url_for('index'))

    return render_template('configuracoes.html')

# --- RESTANTE DAS ROTAS (VENDAS, PRODUTOS, ADMIN) ---
@app.route('/planos')
def planos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    if session.get('usuario_email') == ADMIN_EMAIL: return redirect(url_for('admin_assinantes'))
    return "<h1>Área de Renovação</h1><p>Em breve você poderá renovar seu plano aqui.</p><a href='/'>Voltar</a>"

@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    if request.method == 'POST':
        cadastrar_produto(request.form.get('nome'), float(request.form.get('preco_custo') or 0), 
                          float(request.form.get('preco_venda') or 0), int(request.form.get('quantidade') or 0), usuario_id)
        return redirect(url_for('produtos'))
    return render_template('produtos.html', produtos=listar_produtos(usuario_id))

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    if request.method == 'POST':
        if request.form.get('nome'):
            cadastrar_cliente(request.form.get('nome'), request.form.get('telefone'), usuario_id)
            return redirect(url_for('clientes'))
    return render_template('clientes.html', clientes=listar_clientes(usuario_id))

@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    if request.method == 'POST':
        itens_json = request.form.get('itens_json')
        cliente_id = request.form.get('cliente_id')
        forma_pagamento = request.form.get('forma_pagamento')
        if itens_json:
            itens = json.loads(itens_json)
            c_id = int(cliente_id) if cliente_id and cliente_id != "" else None
            for item in itens:
                registrar_venda(int(item['id']), c_id, int(item['qtd']), forma_pagamento, usuario_id)
            return redirect(url_for('vendas')) 
    return render_template('vendas.html', produtos=listar_produtos(usuario_id), 
                           clientes=listar_clientes(usuario_id), vendas=listar_vendas(usuario_id))

@app.route('/admin/assinantes')
def admin_assinantes():
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL: return "Proibido", 403
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

if __name__ == '__main__':
    app.run(debug=True)