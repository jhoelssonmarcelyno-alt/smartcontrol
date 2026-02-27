from flask import Flask, render_template, request, redirect, url_for, session
from models import (listar_produtos, listar_clientes, cadastrar_produto, 
                    cadastrar_cliente, registrar_venda, conectar_db, 
                    cadastrar_usuario, listar_todos_assinantes, 
                    renovar_assinatura, excluir_usuario,
                    obter_dados_assinante, obter_resumo_financeiro, 
                    listar_vendas)
import json

app = Flask(__name__)
app.secret_key = 'smartcontrol_chave_secreta_99'

# E-mail do administrador mestre
ADMIN_EMAIL = "jhoelssonmarcelyno@gmail.com"

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
    total_estoque = sum(p['quantidade'] for p in produtos)
    total_fiado = sum(c['saldo_devedor'] for c in clientes)
    return render_template('index.html', assinante=assinante, resumo=resumo, 
                           produtos=produtos[:5], total_estoque=total_estoque, total_fiado=total_fiado)

# --- NOVA ROTA: PLANOS (Corrige o erro do botão amarelo) ---
@app.route('/planos')
def planos():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    # Se VOCÊ (Admin) clicar, redireciona direto para a gestão de assinantes
    if session.get('usuario_email') == ADMIN_EMAIL:
        return redirect(url_for('admin_assinantes'))
    
    # Se for um usuário comum, mostra a página de planos (ou uma mensagem)
    return "<h1>Área de Renovação</h1><p>Em breve você poderá renovar seu plano aqui.</p><a href='/'>Voltar</a>"

# --- PRODUTOS E CLIENTES ---
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
            itens = json.loads(itens_json)
            c_id = int(cliente_id) if cliente_id and cliente_id != "" else None
            
            for item in itens:
                registrar_venda(int(item['id']), c_id, int(item['qtd']), forma_pagamento, usuario_id)
            
            return redirect(url_for('vendas')) 

    produtos_lista = listar_produtos(usuario_id)
    clientes_lista = listar_clientes(usuario_id)
    historico_vendas = listar_vendas(usuario_id)
    
    return render_template('vendas.html', 
                           produtos=produtos_lista, 
                           clientes=clientes_lista, 
                           vendas=historico_vendas)

# --- ADMINISTRAÇÃO ---
@app.route('/admin/assinantes')
def admin_assinantes():
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL: 
        return "Proibido", 403
    return render_template('admin_assinantes.html', assinantes=listar_todos_assinantes())

@app.route('/admin/renovar/<int:id>/<int:dias>')
def renovar(id, dias):
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL: 
        return "Proibido", 403
    renovar_assinatura(id, dias)
    return redirect(url_for('admin_assinantes'))

@app.route('/admin/excluir/<int:id>')
def admin_excluir(id):
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL: 
        return "Proibido", 403
    excluir_usuario(id)
    return redirect(url_for('admin_assinantes'))

if __name__ == '__main__':
    app.run(debug=True)