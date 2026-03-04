from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import json
import os
import urllib.parse
from werkzeug.utils import secure_filename
from functools import wraps

# Importando TODAS as funções do models.py (incluindo as novas)
from models import (
    listar_produtos, listar_clientes, cadastrar_produto, 
    cadastrar_cliente, conectar_db, 
    cadastrar_usuario, listar_todos_assinantes, 
    renovar_assinatura, excluir_usuario,
    obter_dados_assinante, obter_resumo_financeiro, 
    listar_vendas, registrar_pagamento_cliente,
    obter_cliente_por_id, obter_extrato_cliente, atualizar_configuracao_fiado,
    processar_venda_completa, criar_tabelas, PL, obter_cursor, DATABASE_URL,
    obter_resumo_financeiro as obter_metricas_globais_admin # Usando a lógica global
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

# --- DECORATOR DE SEGURANÇA (BLOQUEIO DE ASSINATURA) ---
def verificar_assinatura(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        
        u_id = session['usuario_id']
        u_email = session.get('usuario_email', '').lower().strip()
        
        # O administrador nunca é bloqueado
        if u_email == ADMIN_EMAIL.lower().strip():
            return f(*args, **kwargs)
            
        dados = obter_dados_assinante(u_id)
        if not dados or dados.get('dias_restantes', 0) <= 0:
            return redirect(url_for('vencido'))
            
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- AUXILIARES ---
def atualizar_senha_usuario(usuario_id, nova_senha):
    try:
        conn = conectar_db()
        cursor = obter_cursor(conn)
        cursor.execute(f'UPDATE usuarios SET senha = {PL} WHERE id = {PL}', (nova_senha, usuario_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao atualizar senha: {e}")
        return False

# --- LOGIN / REGISTRAR / LOGOUT ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_digitado = request.form.get('email', '').lower().strip()
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
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('E-mail ou senha incorretos!', 'erro')
            
    return render_template('login.html')

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email', '').lower().strip()
        senha = request.form.get('senha')
        if cadastrar_usuario(nome, email, senha):
            flash('Conta criada com sucesso!', 'sucesso')
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
@verificar_assinatura
def index():
    usuario_id = session['usuario_id']
    resumo = obter_resumo_financeiro(usuario_id)
    assinante = obter_dados_assinante(usuario_id)
    produtos = listar_produtos(usuario_id)
    alertas_estoque = [p for p in produtos if (p['quantidade'] or 0) < 3]
    e_admin = session.get('usuario_email') == ADMIN_EMAIL.lower().strip()
    
    return render_template('index.html', 
                           resumo=resumo, 
                           assinante=assinante, 
                           alertas_estoque=alertas_estoque,
                           e_admin=e_admin)

# --- PERFIL DO CLIENTE ---
@app.route('/cliente/<int:id>')
@app.route('/detalhes_cliente/<int:id>')
@verificar_assinatura
def detalhes_cliente(id):
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
@app.route('/gestao_clientes', methods=['GET', 'POST'])
@verificar_assinatura
def clientes():
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
        
        cursor.execute(f"SELECT MAX(data) FROM vendas WHERE cliente_id={PL} AND usuario_id={PL} AND forma_pagamento='Fiado'", (d['id'], usuario_id))
        venda_rec = cursor.fetchone()
        
        d['dias_atraso'], d['data_formatada'] = 0, "Sem dívidas"
        venda_data = list(dict(venda_rec).values())[0] if venda_rec and isinstance(venda_rec, dict) else (venda_rec[0] if venda_rec else None)
        
        if venda_data and d.get('saldo_devedor', 0) > 0:
            try:
                dt_v = datetime.strptime(str(venda_data)[:19], '%Y-%m-%d %H:%M:%S')
                d['data_formatada'] = dt_v.strftime('%d/%m/%Y')
                venc = dt_v + timedelta(days=int(d.get('prazo_pagamento') or 15))
                if hoje > venc: 
                    d['dias_atraso'] = (hoje - venc).days
            except: pass
        clientes_formatados.append(d)
    conn.close()
    return render_template('clientes.html', clientes=clientes_formatados)

@app.route('/editar_cliente/<int:id>', methods=['POST'])
@verificar_assinatura
def editar_cliente(id):
    nome = request.form.get('nome').upper()
    tel = request.form.get('telefone')
    limite = request.form.get('limite_credito')
    prazo = int(request.form.get('prazo_pagamento') or 15)
    
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'UPDATE clientes SET nome={PL}, telefone={PL}, limite_fiado={PL}, prazo_pagamento={PL} WHERE id={PL} AND usuario_id={PL}', 
                   (nome, tel, limite, prazo, id, session['usuario_id']))
    conn.commit()
    conn.close()
    flash('Dados atualizados!', 'sucesso')
    return redirect(url_for('clientes'))

# --- FINANCEIRO E QUITAÇÕES ---
@app.route('/financas')
@verificar_assinatura
def financas():
    return render_template('financas.html', resumo=obter_resumo_financeiro(session['usuario_id']))

@app.route('/quitar_total/<int:cliente_id>', methods=['POST'])
@verificar_assinatura
def quitar_total(cliente_id):
    u_id = session['usuario_id']
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f"UPDATE vendas SET forma_pagamento='Pago' WHERE cliente_id={PL} AND forma_pagamento='Fiado' AND usuario_id={PL}", (cliente_id, u_id))
    cursor.execute(f"UPDATE clientes SET saldo_devedor=0 WHERE id={PL} AND usuario_id={PL}", (cliente_id, u_id))
    conn.commit()
    conn.close()
    flash('Dívida liquidada!', 'sucesso')
    return redirect(url_for('detalhes_cliente', id=cliente_id))

@app.route('/quitar_parcial/<int:cliente_id>', methods=['POST'])
@verificar_assinatura
def quitar_parcial(cliente_id):
    valor_pago = float(request.form.get('valor_pago', 0))
    if valor_pago <= 0: return redirect(url_for('detalhes_cliente', id=cliente_id))
    
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f"SELECT id, valor_total FROM vendas WHERE cliente_id={PL} AND forma_pagamento='Fiado' AND usuario_id={PL} ORDER BY data ASC", (cliente_id, session['usuario_id']))
    vendas = cursor.fetchall()
    
    restante = valor_pago
    for v in vendas:
        v_dict = dict(v)
        if restante <= 0: break
        if restante >= v_dict['valor_total']:
            cursor.execute(f"UPDATE vendas SET forma_pagamento='Pago' WHERE id={PL}", (v_dict['id'],))
            restante -= v_dict['valor_total']
        else: break
        
    cursor.execute(f"UPDATE clientes SET saldo_devedor = saldo_devedor - {PL} WHERE id={PL} AND usuario_id={PL}", (valor_pago, cliente_id, session['usuario_id']))
    cursor.execute(f"UPDATE clientes SET saldo_devedor = 0 WHERE id={PL} AND saldo_devedor < 0", (cliente_id,))
    
    conn.commit()
    conn.close()
    flash(f'Abatimento de R$ {valor_pago:.2f} realizado!', 'sucesso')
    return redirect(url_for('detalhes_cliente', id=cliente_id))

# --- PRODUTOS ---
@app.route('/produtos', methods=['GET', 'POST'])
@verificar_assinatura
def produtos():
    usuario_id = session['usuario_id']
    conn = conectar_db()
    cursor = obter_cursor(conn)
    
    if request.method == 'POST':
        nome = request.form.get('nome').strip().upper()
        c = float(request.form.get('preco_custo') or 0)
        v = float(request.form.get('preco_venda') or 0)
        q = int(request.form.get('quantidade') or 0)
        cursor.execute(f'INSERT INTO produtos (nome, preco_custo, preco_venda, quantidade, usuario_id) VALUES ({PL}, {PL}, {PL}, {PL}, {PL})', (nome, c, v, q, usuario_id))
        conn.commit()
        flash('Produto cadastrado!', 'sucesso')
        
    cursor.execute(f'SELECT * FROM produtos WHERE usuario_id={PL} ORDER BY nome ASC', (usuario_id,))
    produtos_lista = cursor.fetchall()
    conn.close()
    return render_template('produtos.html', produtos=produtos_lista)

@app.route('/excluir_produto/<int:id>')
@verificar_assinatura
def excluir_produto(id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f'DELETE FROM produtos WHERE id={PL} AND usuario_id={PL}', (id, session['usuario_id']))
    conn.commit()
    conn.close()
    flash('Produto excluído!', 'sucesso')
    return redirect(url_for('produtos'))

# --- VENDAS ---
@app.route('/vendas', methods=['GET', 'POST'])
@verificar_assinatura
def vendas():
    u_id = session['usuario_id']
    if request.method == 'POST':
        itens = request.form.get('itens_json')
        c_id = request.form.get('cliente_id')
        forma = request.form.get('forma_pagamento')
        if itens:
            cli = int(c_id) if c_id and c_id.strip() != "" else None
            if processar_venda_completa(itens, cli, forma, u_id): 
                flash('Venda realizada!', 'sucesso')
            else: 
                flash('Erro na venda: Verifique estoque ou dados.', 'erro')
            return redirect(url_for('vendas'))
            
    v_fmt = []
    for v in listar_vendas(u_id):
        d = dict(v)
        try: 
            d['data_formatada'] = datetime.strptime(str(d['data'])[:19], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
        except: 
            d['data_formatada'] = d['data']
        v_fmt.append(d)
    return render_template('vendas.html', produtos=listar_produtos(u_id), clientes=listar_clientes(u_id), vendas=v_fmt)

@app.route('/venda/<int:id>/comprovante')
@verificar_assinatura
def comprovante_venda(id):
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f"SELECT v.*, c.nome as cliente_nome, u.nome as empresa_nome FROM vendas v LEFT JOIN clientes c ON v.cliente_id=c.id LEFT JOIN usuarios u ON v.usuario_id=u.id WHERE v.id={PL} AND v.usuario_id={PL}", (id, session['usuario_id']))
    v = cursor.fetchone()
    
    if not v: 
        conn.close()
        return redirect(url_for('vendas'))
        
    cursor.execute(f"SELECT v.*, p.nome as produto_nome FROM vendas v LEFT JOIN produtos p ON v.produto_id=p.id WHERE v.data={PL} AND v.usuario_id={PL}", (v['data'], session['usuario_id']))
    itens = cursor.fetchall()
    conn.close()
    return render_template('comprovante.html', venda=v, itens=itens, total=sum(i['valor_total'] for i in itens))

# --- RELATÓRIOS ---
@app.route('/relatorios_painel')
@verificar_assinatura
def relatorios_painel():
    return render_template('relatorios_menu.html')

@app.route('/relatorios')
@verificar_assinatura
def relatorios():
    u_id = session['usuario_id']
    periodo = request.args.get('periodo', 'dia')
    hoje = datetime.now()
    
    if periodo == 'dia': d_ini = hoje.strftime('%Y-%m-%d 00:00:00')
    elif periodo == 'semana': d_ini = (hoje - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
    elif periodo == 'mes': d_ini = (hoje - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
    else: d_ini = (hoje - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
    
    conn = conectar_db()
    cursor = obter_cursor(conn)
    cursor.execute(f"""
        SELECT p.nome as produto_nome, SUM(v.quantidade) as quantidade_total, 
               SUM(v.valor_total) as faturamento_total, p.preco_venda, p.preco_custo, 
               MAX(v.data) as ultima_venda 
        FROM vendas v JOIN produtos p ON v.produto_id = p.id 
        WHERE v.usuario_id = {PL} AND v.data >= {PL} 
        GROUP BY p.nome, p.preco_venda, p.preco_custo ORDER BY faturamento_total DESC
    """, (u_id, d_ini))
    rows = cursor.fetchall()
    
    v_agrup = []
    for r in rows:
        item = dict(r)
        try: 
            item['ultima_venda_formatada'] = datetime.strptime(str(item['ultima_venda'])[:19], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
        except: 
            item['ultima_venda_formatada'] = "---"
        v_agrup.append(item)
        
    t_fat = sum(v['faturamento_total'] for v in v_agrup)
    t_custo = sum(v['quantidade_total'] * v['preco_custo'] for v in v_agrup)
    conn.close()
    return render_template('relatorios.html', vendas=v_agrup, periodo=periodo.upper(), total=t_fat, lucro=t_fat - t_custo)

@app.route('/relatorio/inadimplentes')
@verificar_assinatura
def relatorio_inadimplentes():
    u_id = session['usuario_id']
    conn = conectar_db()
    cursor = obter_cursor(conn)
    
    cursor.execute(f'SELECT pix FROM usuarios WHERE id={PL}', (u_id,))
    u_pix = cursor.fetchone()
    c_pix = u_pix['pix'] if u_pix and u_pix.get('pix') else "[CADASTRE SEU PIX]"
    
    cursor.execute(f"""
        SELECT id, nome, telefone, prazo_pagamento, saldo_devedor, 
        (SELECT MAX(data) FROM vendas WHERE cliente_id=clientes.id AND forma_pagamento='Fiado') as ultima_venda 
        FROM clientes WHERE usuario_id={PL} AND saldo_devedor>0 ORDER BY saldo_devedor DESC
    """, (u_id,))
    dev_raw = cursor.fetchall()
    
    devedores, t_geral, maior = [], 0, 0
    for d in dev_raw:
        item = dict(d)
        item['telefone_limpo'] = "".join(filter(str.isdigit, str(item['telefone']))) if item['telefone'] else ""
        item['vencimento_br'], item['status_alerta'], item['dias_atraso'] = "---", "OK", 0
        
        if item['ultima_venda']:
            try:
                dt_v = datetime.strptime(str(item['ultima_venda'])[:19], '%Y-%m-%d %H:%M:%S')
                venc = dt_v + timedelta(days=int(item['prazo_pagamento'] or 15))
                item['vencimento_br'] = venc.strftime('%d/%m/%Y')
                hoje = datetime.now()
                if hoje > venc: 
                    item['status_alerta'], item['dias_atraso'] = 'CRÍTICO', (hoje - venc).days
                elif (venc - hoje).days <= 2: 
                    item['status_alerta'] = 'PROXIMO'
            except: pass
        
        t_geral += (item['saldo_devedor'] or 0)
        if (item['saldo_devedor'] or 0) > maior: maior = item['saldo_devedor']
        devedores.append(item)
    conn.close()
    return render_template('inadimplentes.html', devedores=devedores, chave_pix=c_pix, total_inadimplencia=t_geral, maior_divida=maior)

# --- CONFIGURAÇÕES ---
@app.route('/configuracoes', methods=['GET', 'POST'])
@verificar_assinatura
def configuracoes():
    u_id = session['usuario_id']
    conn = conectar_db()
    cursor = obter_cursor(conn)
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        pix = request.form.get('pix')
        arq = request.files.get('logo')
        
        cursor.execute(f'SELECT logo FROM usuarios WHERE id={PL}', (u_id,))
        user_at = cursor.fetchone()
        fname = user_at['logo'] if user_at else None
        
        if arq and allowed_file(arq.filename):
            ext = arq.filename.rsplit('.', 1)[1].lower()
            fname = f"logo_user_{u_id}.{ext}"
            arq.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            
        cursor.execute(f'UPDATE usuarios SET nome={PL}, logo={PL}, pix={PL} WHERE id={PL}', (nome, fname, pix, u_id))
        conn.commit()
        session['usuario_nome'] = nome
        session['usuario_logo'] = fname
        flash('Configurações salvas!', 'sucesso')
        
    cursor.execute(f'SELECT * FROM usuarios WHERE id={PL}', (u_id,))
    u_info = cursor.fetchone()
    conn.close()
    return render_template('configuracoes.html', user=u_info)

@app.route('/alterar_senha', methods=['POST'])
@verificar_assinatura
def alterar_senha():
    nova = request.form.get('nova_senha')
    conf = request.form.get('confirmar_senha')
    if nova and nova == conf:
        if atualizar_senha_usuario(session['usuario_id'], nova): 
            flash('Senha alterada!', 'sucesso')
        else:
            flash('Erro ao atualizar no banco.', 'erro')
    else: 
        flash('As senhas não coincidem!', 'erro')
    return redirect(url_for('configuracoes'))

# --- ADMIN E PLANOS ---
@app.route('/planos')
def planos(): 
    return render_template('planos.html')

@app.route('/admin/assinantes')
def admin_assinantes():
    if session.get('usuario_email') != ADMIN_EMAIL.lower().strip(): return "Proibido", 403
    return render_template('admin_assinantes.html', assinantes=listar_todos_assinantes())

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('usuario_email') != ADMIN_EMAIL.lower().strip(): return "Acesso Negado", 403

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        acao = request.form.get('acao')
        if acao == 'renovar': renovar_assinatura(user_id, 30)
        elif acao == 'excluir': excluir_usuario(user_id)
        return redirect(url_for('admin_dashboard'))

    # Usando o ID 0 ou similar para métricas totais conforme definido no models
    metricas = obter_metricas_globais_admin(0) 
    assinantes = listar_todos_assinantes()
    return render_template('admin_dashboard.html', metricas=metricas, assinantes=assinantes)

@app.route('/vencido')
def vencido():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    dados = obter_dados_assinante(session['usuario_id'])
    return render_template('vencido.html', dados=dados)

# Inicialização segura do banco
try:
    criar_tabelas()
except Exception as e:
    print(f"Erro ao criar tabelas: {e}")

if __name__ == '__main__':
    app.run(debug=True)