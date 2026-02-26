-- Tabela de Produtos (Estoque e Lucro)
CREATE TABLE produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    preco_custo REAL NOT NULL,
    preco_venda REAL NOT NULL,
    quantidade INTEGER NOT NULL
);

-- Tabela de Clientes (Para gerenciar Fiados)
CREATE TABLE clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT,
    saldo_devedor REAL DEFAULT 0.0
);

-- Tabela de Vendas
CREATE TABLE vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER,
    cliente_id INTEGER, -- Se for nulo, é venda no balcão (paga)
    quantidade INTEGER,
    valor_total REAL,
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pago BOOLEAN DEFAULT 1, -- 0 para Fiado, 1 para Pago
    FOREIGN KEY (produto_id) REFERENCES produtos(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);