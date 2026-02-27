from models import conectar_db

def adicionar_colunas_faltantes():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Lista de tabelas que precisam obrigatoriamente do usuario_id
    tabelas = ['produtos', 'clientes', 'vendas']
    
    for tabela in tabelas:
        try:
            print(f"Tentando atualizar a tabela: {tabela}...")
            # Adiciona a coluna usuario_id
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN usuario_id INTEGER")
            print(f"✅ Coluna usuario_id adicionada com sucesso em {tabela}!")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print(f"ℹ️ A tabela {tabela} já possui a coluna usuario_id.")
            else:
                print(f"❌ Erro ao atualizar {tabela}: {e}")
    
    conn.commit()
    conn.close()
    print("\n🚀 Procedimento finalizado! Tente rodar o app.py agora.")

if __name__ == "__main__":
    adicionar_colunas_faltantes()