from flask import Flask, render_template, request, redirect, url_for, session
from models import (listar_produtos, listar_clientes, cadastrar_produto, 
                    cadastrar_cliente, registrar_venda)
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'smartcontrol_chave_secreta_99' # Chave para manter o usuário logado

# Simulação de banco de dados de assinantes (Para teste)
USUARIOS_TESTE = {
    "admin@teste.com": {"senha": "123", "nome": "Joelson Admin", "dias": 7, "plano": "Teste Grátis"}
}

# ROTA DE LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        # Verifica se o assinante existe e a senha bate
        if email in USUARIOS_TESTE and USUARIOS_TESTE[email]['senha'] == senha:
            session['usuario'] = email
            session['nome'] = USUARIOS_TESTE[email]['nome']
            return redirect(url_for('index'))
        else:
            return "Email ou senha incorretos! <a href='/login'>Tentar novamente</a>"
            
    return render_template('login.html')

# ROTA DE LOGOUT (Sair)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ROTA 1: DASHBOARD (Protegida)
@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    # Pegamos os dados do assinante logado
    dados_assinante = USUARIOS_TESTE[session['usuario']]
    
    # Bloqueio por falta de dias
    if dados_assinante['dias'] <= 0:
        return redirect(url_for('planos'))

    produtos = listar_produtos()
    clientes = listar_clientes()
    total_estoque = sum(p['quantidade'] for p in produtos)
    total_fiado = sum(c['saldo_devedor'] for c in clientes)
    
    return render_template('index.html', 
                           produtos=produtos, 
                           total_estoque=total_estoque, 
                           total_fiado=total_fiado,
                           assinante=dados_assinante)

# ROTA DE PLANOS
@app.route('/planos')
def planos():
    return render_template('planos.html')

# ROTA 2: CADASTRO DE PRODUTOS
@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            preco_custo = float(request.form['preco_custo'])
            preco_venda = float(request.form['preco_venda'])
            quantidade = int(request.form['quantidade'])
            cadastrar_produto(nome, preco_custo, preco_venda, quantidade)
            return redirect(url_for('index'))
        except Exception as e:
            return f"Erro: {e}"
    return render_template('produtos.html')

# ROTA 3: CADASTRO DE CLIENTES
@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            telefone = request.form['telefone']
            cadastrar_cliente(nome, telefone)
            return redirect(url_for('index'))
        except Exception as e:
            return f"Erro: {e}"
    return render_template('clientes.html')

# ROTA 4: REGISTRAR VENDAS
@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            produto_id = int(request.form['produto_id'])
            cliente_id = int(request.form['cliente_id'])
            quantidade = int(request.form['quantidade'])
            forma_pagamento = request.form['forma_pagamento']
            registrar_venda(produto_id, cliente_id, quantidade, forma_pagamento)
            return redirect(url_for('index'))
        except Exception as e:
            return "Erro ao processar venda."
            
    produtos = listar_produtos()
    clientes = listar_clientes()
    return render_template('vendas.html', produtos=produtos, clientes=clientes)

if __name__ == '__main__':
    app.run(debug=True)