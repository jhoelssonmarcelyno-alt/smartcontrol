from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import json
import os
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
    processar_venda_completa, criar_tabelas, PL, obter_cursor, DATABASE_URL
)

app = Flask(__name__)
app.secret_key = 'smartcontrol_chave_secreta_99'

# Configuração de Upload de Logo
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# E-MAIL DO ADMINISTRADOR
ADMIN_EMAIL = "jhoelssonmarcelyno@gmail.com"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- AUXILIARES ---
def atualizar_senha_usuario_local(usuario_id, nova_senha):
    try:
        conn = conectar_db()
        cursor = obter_cursor(conn)
        cursor.execute(f'UPDATE usuarios SET senha = {PL} WHERE id = {PL}', (nova_senha, usuario_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

# --- LOGIN / REGISTRAR / LOGOUT ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_digitado = request.form.get('email').lower().strip()
        senha = request.form.get('senha')
        
        conn = conectar_db()
        cursor = obter_cursor(conn)
        cursor.execute(f'SELECT * FROM usuarios WHERE email = {PL}', (email_digitado,))
        usuario = cursor.fetchone()
        conn.close()
        
        if usuario and str(usuario['senha']) == str(senha):
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            session['usuario_email'] = usuario['email'].lower().strip()
            session['usuario_logo'] = usuario.get('logo') 
            
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
    if 'usuario_id' not in session: 
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    resumo = obter_resumo_financeiro(usuario_id)
    assinante = obter_dados_assinante(usuario_id)
    produtos = listar_produtos(usuario_id)
    alertas_estoque = [p for p in produtos if p['quantidade'] < 3]
    e_admin = session.get('usuario_email') == ADMIN_EMAIL.lower().strip()
    
    return render_template('index.html', 
                           resumo=resumo, 
                           assinante=assinante, 
                           alertas_estoque=alertas_estoque,
                           e_admin=e_admin)

# --- PERFIL DO CLIENTE ---
@app.route('/cliente/<int:id>')
@app.route('/detalhes_cliente/<int:id>')
def detalhes_cliente(id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    conn = conectar_db()
    cursor = obter_cursor(conn)
    
    cursor.execute(f'SELECT * FROM clientes WHERE id = {PL} AND usuario_id = {PL}', (id, usuario_id))
    cliente = cursor.fetchone()
    
    if not cliente:
        conn.close()
        flash("Cliente não encontrado!", "erro")
        return redirect(url_for('clientes'))

    cursor.execute(f'''
        SELECT p.nome as produto, v.quantidade, v.valor_total, v.data, v.forma_pagamento 
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        WHERE v.cliente_id = {PL} AND v.usuario_id = {PL} 
        ORDER BY v.data DESC
    ''', (id, usuario_id))
    vendas_query = cursor.fetchall()
    
    extrato = []
    for v in vendas_query:
        vd = dict(v)
        data_origem = vd.get('data')
        if data_origem:
            try:
                # Limpa a string da data para evitar erros de milissegundos no Postgres
                dt_obj = datetime.strptime(str(data_origem)[:19], '%Y-%m-%d %H:%M:%S')
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
def clientes():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    conn = conectar_db()
    cursor = obter_cursor(conn)
    
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip().upper()
        telefone = request.form.get('telefone')
        limite = float(request.form.get('limite_credito') or 0.0)
        prazo = int(request.form.get('prazo_pagamento') or 15)
        
        cursor.execute(f'SELECT id FROM clientes WHERE nome = {PL} AND usuario_id = {PL}', (nome, usuario_id))
        existente = cursor.fetchone()
        
        if existente: 
            flash('Erro: Já existe um cliente com este nome!', 'erro')
        else:
            cursor.execute(f'''
                INSERT INTO clientes (nome, telefone, limite_fiado, prazo_pagamento, usuario_id, saldo_devedor, permite_fiado) 
                VALUES ({PL}, {PL}, {PL}, {PL}, {PL}, 0, 1)
            ''', (nome, telefone, limite, prazo, usuario_id))
            conn.commit()
            flash('Cliente cadastrado!', 'sucesso')
        conn.close()
        return redirect(url_for('clientes'))

    cursor.execute(f'SELECT * FROM clientes WHERE usuario_id = {PL} ORDER BY nome', (usuario_id,))
    lista_c = cursor.fetchall()
    hoje = datetime.now()
    clientes_formatados = []
    
    for c in lista_c:
        d = dict(c)
        if d.get('telefone'): 
            d['link_zap'] = f"https://wa.me/55{''.join(filter(str.isdigit, str(d['telefone'])))}"
        
        cursor.execute(f'SELECT MAX(data) FROM vendas WHERE cliente_id={PL} AND usuario_id={PL}', (d['id'], usuario_id))
        venda_rec = cursor.fetchone()
        
        d['dias_atraso'], d['data_formatada'] = 0, "Sem compras"
        
        # Lógica para extrair a data correta do resultado do banco
        venda_data = None
        if venda_rec:
            if isinstance(venda_rec, dict): venda_data = venda_rec.get('max') or venda_rec.get('MAX(data)')
            elif isinstance(venda_rec, (list, tuple)): venda_data = venda_rec[0]

        if venda_data:
            try:
                dt_v = datetime.strptime(str(venda_data)[:19], '%Y-%m-%d %H:%M:%S')
                d['data_formatada'] = dt_v.strftime('%d/%m/%Y')
                venc = dt_v + timedelta(days=int(d.get('prazo_pagamento') or 15))
                if hoje > venc and d.get('saldo_devedor', 0) > 0: 
                    d['dias_atraso'] = (hoje - venc).days
            except: pass
        clientes_formatados.append(d)
    conn.close()
    return render_template('clientes.html', clientes=clientes_formatados)

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
        try: d['data_formatada'] = datetime.strptime(str(d['data'])[:19], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
        except: d['data_formatada'] = d['data']
        v_fmt.append(d)
    return render_template('vendas.html', produtos=listar_produtos(u_id), clientes=listar_clientes(u_id), vendas=v_fmt)

# --- ADMIN E PLANOS ---
@app.route('/admin/assinantes')
def admin_assinantes():
    if session.get('usuario_email') != ADMIN_EMAIL.lower().strip(): return "Proibido", 403
    return render_template('admin_assinantes.html', assinantes=listar_todos_assinantes())

# Funções restantes (excluir, editar, relatorios) seguem a mesma lógica...
# Adicionei a chamada de criação de tabelas obrigatória para o deploy
try:
    criar_tabelas()
except Exception as e:
    print(f"Aviso na criação de tabelas: {e}")

if __name__ == '__main__':
    app.run(debug=True)