from flask import Flask, render_template, request, redirect, url_for
from models import (listar_produtos, listar_clientes, cadastrar_produto, 
                    cadastrar_cliente, registrar_venda)

app = Flask(__name__)

# ROTA 1: DASHBOARD
@app.route('/')
def index():
    produtos = listar_produtos()
    clientes = listar_clientes()
    total_estoque = sum(p['quantidade'] for p in produtos)
    total_fiado = sum(c['saldo_devedor'] for c in clientes)
    
    return render_template('index.html', 
                           produtos=produtos, 
                           total_estoque=total_estoque, 
                           total_fiado=total_fiado)

# ROTA 2: CADASTRO DE PRODUTOS
@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            preco_custo = float(request.form['preco_custo'])
            preco_venda = float(request.form['preco_venda'])
            quantidade = int(request.form['quantidade'])
            cadastrar_produto(nome, preco_custo, preco_venda, quantidade)
            return redirect(url_for('index'))
        except Exception as e:
            print(f"❌ Erro: {e}")
            return "Erro nos dados do produto."
    return render_template('produtos.html')

# ROTA 3: CADASTRO DE CLIENTES
@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            telefone = request.form['telefone']
            cadastrar_cliente(nome, telefone)
            return redirect(url_for('index'))
        except Exception as e:
            print(f"❌ Erro: {e}")
            return "Erro nos dados do cliente."
    return render_template('clientes.html')

# ROTA 4: REGISTRAR VENDAS (As 4 formas de pagamento)
@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    if request.method == 'POST':
        try:
            produto_id = int(request.form['produto_id'])
            cliente_id = int(request.form['cliente_id'])
            quantidade = int(request.form['quantidade'])
            forma_pagamento = request.form['forma_pagamento']
            
            registrar_venda(produto_id, cliente_id, quantidade, forma_pagamento)
            return redirect(url_for('index'))
        except Exception as e:
            print(f"❌ Erro na venda: {e}")
            return "Erro ao processar venda. Verifique o estoque."
            
    produtos = listar_produtos()
    clientes = listar_clientes()
    return render_template('vendas.html', produtos=produtos, clientes=clientes)

if __name__ == '__main__':
    app.run(debug=True)