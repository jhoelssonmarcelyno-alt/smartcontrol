from flask import Flask, render_template, request, redirect, url_for, session
from models import (listar_produtos, listar_clientes, cadastrar_produto, 
                    cadastrar_cliente, registrar_venda, conectar_db, 
                    cadastrar_usuario, listar_todos_assinantes, 
                    renovar_assinatura, excluir_usuario) # <-- Adicionado aqui
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'smartcontrol_chave_secreta_99'

# Configuração do seu email de administrador Master
ADMIN_EMAIL = "jhoelssonmarcelyno@gmail.com"

# FUNÇÃO AUXILIAR: Verifica dias restantes de assinatura
def verificar_assinatura(data_exp_str):
    try:
        data_exp = datetime.strptime(data_exp_str, '%Y-%m-%d %H:%M:%S')
        delta = data_exp - datetime.now()
        return delta.days
    except:
        return -1

# --- ROTAS DE ACESSO E AUTENTICAÇÃO ---

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
            session['plano'] = user['plano']
            session['expira'] = user['data_expiracao']
            return redirect(url_for('index'))
        else:
            return "Email ou senha incorretos! <a href='/login'>Tentar novamente</a>"
            
    return render_template('login.html')

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        
        if cadastrar_usuario(nome, email, senha):
            return redirect(url_for('login'))
        else:
            return "Erro: Email já cadastrado. <a href='/registrar'>Tentar outro</a>"
    return render_template('registrar.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROTA 1: DASHBOARD PRINCIPAL ---

@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    dias_restantes = verificar_assinatura(session['expira'])
    
    # Bloqueio de Assinatura (Admin é imune)
    if dias_restantes < 0 and session['usuario_email'] != ADMIN_EMAIL:
        return redirect(url_for('planos'))

    uid = session['usuario_id']
    produtos = listar_produtos(uid)
    clientes = listar_clientes(uid)
    
    total_estoque = sum(p['quantidade'] for p in produtos)
    total_fiado = sum(c['saldo_devedor'] for c in clientes)
    
    assinante = {
        "nome": session['nome'],
        "plano": session['plano'],
        "dias_restantes": dias_restantes if dias_restantes > 0 else 0
    }
    
    return render_template('index.html', 
                           produtos=produtos, 
                           total_estoque=total_estoque, 
                           total_fiado=total_fiado,
                           assinante=assinante)

# --- ROTAS DE GESTÃO DO USUÁRIO ---

@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        cadastrar_produto(request.form['nome'], float(request.form['preco_custo']), 
                          float(request.form['preco_venda']), int(request.form['quantidade']), 
                          session['usuario_id'])
        return redirect(url_for('index'))
    return render_template('produtos.html')

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        cadastrar_cliente(request.form['nome'], request.form['telefone'], session['usuario_id'])
        return redirect(url_for('index'))
    return render_template('clientes.html')

@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        registrar_venda(int(request.form['produto_id']), int(request.form['cliente_id']), 
                        int(request.form['quantidade']), request.form['forma_pagamento'], 
                        session['usuario_id'])
        return redirect(url_for('index'))
    
    produtos = listar_produtos(session['usuario_id'])
    clientes = listar_clientes(session['usuario_id'])
    return render_template('vendas.html', produtos=produtos, clientes=clientes)

@app.route('/planos')
def planos():
    return render_template('planos.html')

# --- MÓDULO ADMINISTRATIVO (RESTRITO AO DONO) ---

@app.route('/admin/assinantes')
def admin_assinantes():
    # Segurança rigorosa: verifica se o email na sessão bate com o seu
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL:
        return "Acesso proibido: Apenas o Proprietário pode acessar esta área.", 403
    
    assinantes = listar_todos_assinantes()
    return render_template('admin_assinantes.html', assinantes=assinantes)

@app.route('/admin/renovar/<int:id>/<int:dias>')
def renovar(id, dias):
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL:
        return "Acesso proibido", 403
    
    renovar_assinatura(id, dias)
    return redirect(url_for('admin_assinantes'))

@app.route('/admin/excluir/<int:id>')
def admin_excluir(id):
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL:
        return "Acesso proibido", 403
    
    excluir_usuario(id)
    return redirect(url_for('admin_assinantes'))

if __name__ == '__main__':
    app.run(debug=True)