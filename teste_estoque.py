import sqlite3

conn = sqlite3.connect('NOME_CERTO_AQUI.db')
conn.row_factory = sqlite3.Row
# Substitua o ID pelo seu ID de usuário (geralmente 1 se for o primeiro)
usuario_id = 1 

produtos = conn.execute("SELECT nome, preco_custo, preco_venda, quantidade FROM produtos WHERE usuario_id = ?", (usuario_id,)).fetchall()

print(f"{'Produto':<20} | {'Custo':<10} | {'Venda':<10} | {'Qtd':<5} | {'Lucro Est.'}")
print("-" * 65)

for p in produtos:
    lucro_unitario = p['preco_venda'] - p['preco_custo']
    lucro_total = lucro_unitario * p['quantidade']
    print(f"{p['nome']:<20} | {p['preco_custo']:<10} | {p['preco_venda']:<10} | {p['quantidade']:<5} | {lucro_total}")

conn.close()