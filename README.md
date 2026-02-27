# 🚀 SmartControl SaaS - Gestão de Vendas

O **SmartControl** é um sistema de gestão comercial desenvolvido com **Python (Flask)** e **SQLite**, focado no modelo **SaaS (Software as a Service)**. Ele permite que múltiplos lojistas utilizem a plataforma de forma isolada, gerenciando estoques, clientes e vendas de fiado.

## ✨ Funcionalidades Principais
- **Multitenancy:** Dados isolados por usuário (um lojista não vê os dados do outro).
- **Gestão de Estoque:** Controle de entrada e saída de mercadorias.
- **Controle de Fiados:** Registro de débitos por cliente com saldo devedor automático.
- **Painel Administrativo:** Área restrita para o proprietário gerenciar assinaturas e ativar planos.
- **Sistema de Assinatura:** Bloqueio automático de acesso após o vencimento do período de teste.

## 🛠️ Tecnologias Utilizadas
- **Backend:** Python 3 + Flask
- **Banco de Dados:** SQLite3
- **Frontend:** HTML5, CSS3 (Tailwind CSS) e FontAwesome
- **Autenticação:** Sistema de sessões seguro

## ⚙️ Como rodar o projeto localmente
1. Clone o repositório:
   `git clone https://github.com/jhoelssonmarcelyno-alt/sistema-vendas.git`
2. Crie um ambiente virtual:
   `python -m venv venv`
3. Instale as dependências:
   `pip install -r requirements.txt`
4. Execute a aplicação:
   `python app.py`

---
Desenvolvido por **Jhoelsson Marcelino** 🚀
