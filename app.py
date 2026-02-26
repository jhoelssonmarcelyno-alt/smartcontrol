from flask import Flask, render_template, request, redirect, url_for
from models import listar_produtos, listar_clientes

app = Flask(__name__)

@app.route('/')
def index():
    # Buscando dados reais do banco que você já testou
    produtos = listar_produtos()
    clientes = listar_clientes()
    
    # Cálculos para o Dashboard
    total_estoque = sum(p['quantidade'] for p in produtos)
    # Soma o saldo devedor de todos os clientes para mostrar o total de fiados
    total_fiado = sum(c['saldo_devedor'] for c in clientes)
    
    return render_template('index.html', 
                           produtos=produtos, 
                           total_estoque=total_estoque, 
                           total_fiado=total_fiado)

if __name__ == '__main__':
    app.run(debug=True)