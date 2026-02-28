from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import json
import os
import urllib.parse
from werkzeug.utils import secure_filename

# Importando TODAS as funções do models
from models import (
    listar_produtos, listar_clientes, cadastrar_produto, 
    cadastrar_cliente, registrar_venda, conectar_db, 
    cadastrar_usuario, listar_todos_assinantes, 
    renovar_assinatura, excluir_usuario,
    obter_dados_assinante, obter_resumo_financeiro, 
    listar_vendas, registrar_pagamento_cliente,
    obter_cliente_por_id, obter_extrato_cliente, atualizar_configuracao_fiado
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

    vendas_filtradas = [dict(row) for row in rows]

    for venda in vendas_filtradas:
        try:
            data_db = venda.get('data', '')
            dt = datetime.strptime(data_db[:10], '%Y-%m-%d')
            venda['data_formatada'] = dt.strftime('%d/%m/%Y')
        except:
            venda['data_formatada'] = venda.get('data', 'Sem data')

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
    clientes_list = listar_clientes(usuario_id)
    total_estoque = sum(p['quantidade'] for p in produtos) if produtos else 0
    total_fiado = sum(c['saldo_devedor'] for c in clientes_list) if clientes_list else 0
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
            if allowed_file(arquivo.filename):
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

# --- PRODUTOS ---
@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    if request.method == 'POST':
        cadastrar_produto(request.form.get('nome'), float(request.form.get('preco_custo') or 0), 
                          float(request.form.get('preco_venda') or 0), int(request.form.get('quantidade') or 0), usuario_id)
        return redirect(url_for('produtos'))
    return render_template('produtos.html', produtos=listar_produtos(usuario_id))

# --- CLIENTES E FIADO (CORRIGIDO COM CONTADOR DE DIAS) ---
@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    
    if request.method == 'POST':
        if request.form.get('nome'):
            cadastrar_cliente(request.form.get('nome'), request.form.get('telefone'), usuario_id)
            return redirect(url_for('clientes'))
    
    lista_clientes = listar_clientes(usuario_id)
    clientes_com_fiado = []
    
    for c in lista_clientes:
        cliente_dict = dict(c)
        
        # --- CORREÇÃO DA DATA E DIAS DE ATRASO ---
        if cliente_dict.get('saldo_devedor', 0) > 0:
            try:
                # Pega a data (ex: 2026-02-27 09:32...) e corta apenas os 10 primeiros caracteres (2026-02-27)
                data_ref = cliente_dict.get('data_ultima_compra') or cliente_dict.get('data_cadastro')
                
                if data_ref:
                    # Transformamos em objeto de data para calcular os dias
                    data_dt = datetime.strptime(data_ref[:10], '%Y-%m-%d')
                    dias_atraso = (datetime.now() - data_dt).days
                    cliente_dict['dias_atraso'] = dias_atraso
                    
                    # CRIAMOS A DATA FORMATADA (BR): 27/02/2026
                    cliente_dict['data_formatada'] = data_dt.strftime('%d/%m/%Y')
                else:
                    cliente_dict['dias_atraso'] = 0
                    cliente_dict['data_formatada'] = "Sem data"
            except:
                cliente_dict['dias_atraso'] = 0
                cliente_dict['data_formatada'] = "Erro na data"
        else:
            cliente_dict['dias_atraso'] = 0
            cliente_dict['data_formatada'] = "-"

        clientes_com_fiado.append(cliente_dict)
        
    return render_template('clientes.html', clientes=clientes_com_fiado)

@app.route('/cliente/<int:id>/detalhes')
def cliente_detalhes(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    cliente = obter_cliente_por_id(id, usuario_id)
    if not cliente: return "Cliente não encontrado", 404
    historico = obter_extrato_cliente(id, usuario_id)
    return render_template('cliente_detalhes.html', cliente=cliente, historico=historico)

@app.route('/cliente/<int:id>/configurar_fiado', methods=['POST'])
def configurar_fiado(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    permite = 1 if request.form.get('permite_fiado') else 0
    limite = float(request.form.get('limite_fiado') or 0)
    atualizar_configuracao_fiado(id, permite, limite, session['usuario_id'])
    return redirect(url_for('cliente_detalhes', id=id))

@app.route('/quitar_fiado/<int:id>', methods=['POST'])
def quitar_fiado(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    valor_pago = float(request.form.get('valor_pago') or 0)
    enviar_whats = request.form.get('enviar_whatsapp')
    
    conn = conectar_db()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if cliente and valor_pago > 0:
        registrar_pagamento_cliente(id, valor_pago)
        novo_saldo = max(0, cliente['saldo_devedor'] - valor_pago)
        
        if enviar_whats:
            msg = f"Olá {cliente['nome']}, recebemos seu pagamento de R$ {valor_pago:.2f}. Seu saldo devedor atual é de R$ {novo_saldo:.2f}. Obrigado!"
            msg_encoded = urllib.parse.quote(msg)
            # Limpando o telefone para o WhatsApp
            telefone = "".join(filter(str.isdigit, cliente['telefone'] or ""))
            if telefone:
                return redirect(f"https://wa.me/55{telefone}?text={msg_encoded}")

    return redirect(url_for('clientes'))

@app.route('/venda/<int:id>/comprovante')
def comprovante_venda(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    conn = conectar_db()
    query = """
        SELECT v.*, p.nome as produto_nome, p.preco_venda, 
               c.nome as cliente_nome, c.telefone as cliente_telefone, 
               u.logo as usuario_logo, u.nome as empresa_nome
        FROM vendas v 
        JOIN produtos p ON v.produto_id = p.id 
        JOIN usuarios u ON v.usuario_id = u.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ? AND v.usuario_id = ?
    """
    venda = conn.execute(query, (id, session['usuario_id'])).fetchone()
    conn.close()
    
    if not venda: return "Venda não encontrada", 404
    
    link_zap = None
    if venda['cliente_telefone']:
        try:
            data_dt = datetime.strptime(venda['data'][:19], '%Y-%m-%d %H:%M:%S')
            data_formatada = data_dt.strftime('%d/%m/%Y %H:%M')
        except:
            data_formatada = venda['data']

        msg = (
            f"⚡ *{venda['empresa_nome'] or 'SmartControl'}* ⚡\n\n"
            f"Olá, *{venda['cliente_nome'] or 'Cliente'}*! 👋\n"
            f"Aqui está o detalhe da sua compra:\n\n"
            f"📦 *Produto:* {venda['produto_nome']}\n"
            f"🔢 *Qtd:* {venda['quantidade']}\n"
            f"💰 *Total:* R$ {venda['valor_total']:.2f}\n"
            f"💳 *Pagamento:* {venda['forma_pagamento'].upper()}\n"
            f"📅 *Data:* {data_formatada}\n\n"
            f"Agradecemos a preferência! 😊"
        )
        
        msg_encoded = urllib.parse.quote(msg)
        telefone = "".join(filter(str.isdigit, venda['cliente_telefone']))
        if telefone:
            link_zap = f"https://wa.me/55{telefone}?text={msg_encoded}"
    
    return render_template('comprovante.html', venda=venda, link_zap=link_zap)

# ---VENDAS ---
@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    if request.method == 'POST':
        itens_json = request.form.get('itens_json')
        cliente_id = request.form.get('cliente_id')
        forma_pagamento = request.form.get('forma_pagamento')
        if itens_json:
            try:
                itens = json.loads(itens_json)
                c_id = int(cliente_id) if cliente_id and cliente_id != "" else None
                for item in itens:
                    registrar_venda(int(item['id']), c_id, int(item['qtd']), forma_pagamento, usuario_id)
                return redirect(url_for('vendas')) 
            except Exception as e:
                return f"<script>alert('{str(e)}'); window.location.href='/vendas';</script>"
    return render_template('vendas.html', produtos=listar_produtos(usuario_id), 
                           clientes=listar_clientes(usuario_id), vendas=listar_vendas(usuario_id))

# --- PLANOS E ADMIN ---
@app.route('/planos')
def planos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    if session.get('usuario_email') == ADMIN_EMAIL: return redirect(url_for('admin_assinantes'))
    return render_template('planos.html')

@app.route('/admin/cadastrar_assinante', methods=['POST'])
def admin_cadastrar_assinante():
    if 'usuario_email' not in session or session['usuario_email'] != ADMIN_EMAIL:
        return "Proibido", 403
    
    nome = request.form.get('nome')
    email = request.form.get('email')
    senha = request.form.get('senha')
    
    if cadastrar_usuario(nome, email, senha):
        flash(f"Usuário {nome} cadastrado com sucesso!", "success")
    else:
        flash("Erro ao cadastrar usuário. E-mail pode já existir.", "error")
        
    return redirect(url_for('admin_assinantes'))

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
    app.run(debug=True, host='0.0.0.0')