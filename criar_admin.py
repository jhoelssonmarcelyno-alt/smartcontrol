from models import conectar_db
from datetime import datetime, timedelta

def criar_super_admin():
    conn = conectar_db()
    cursor = conn.cursor()
    
    email = "jhoelssonmarcelyno@gmail.com"
    senha = "251291"
    nome = "Jhoelsson Admin"
    # Define expiração para daqui a 10 anos para o admin não ser bloqueado
    expiracao = (datetime.now() + timedelta(days=3650)).strftime('%Y-%m-%d %H:%M:%S')

    try:
        # Tenta inserir o novo admin
        cursor.execute("""
            INSERT INTO usuarios (nome, email, senha, plano, data_expiracao)
            VALUES (?, ?, ?, 'Admin Master', ?)
        """, (nome, email, senha, expiracao))
        print(f"✅ Administrador {email} criado com sucesso!")
    except:
        # Se o e-mail já existir, apenas atualiza a senha
        cursor.execute("""
            UPDATE usuarios SET senha = ?, plano = 'Admin Master' WHERE email = ?
        """, (senha, email))
        print(f"✅ Senha e status do administrador {email} atualizados!")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_super_admin()