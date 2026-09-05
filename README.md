# ☕ Sistema Fazenda Café - Gestão Agrícola

Sistema web completo para gestão agronômica, operacional e financeira de lavouras cafeeiras.

---

## 📌 Funcionalidades Principais

- **Talhões**: Cadastro georreferenciado, variedade, altitude, espaçamento e cálculo automático de pés de café por hectare.
- **Pulverização Foliar & Pragas**: Calendário agronômico por período, receitas, registro de aplicações e controle de carência/retorno.
- **Manejo do Mato**: Controle de roçadas mecânicas/manuais e capinas químicas.
- **Análises & Adubação**: Registro de laudos de solo e foliares com geração de recomendações nutricionais.
- **Estoque de Insumos**: Movimentações (entradas/saídas), estoque mínimo e valorização financeira.
- **Notas Fiscais & Devolução de Embalagens**: Gestão documental com upload de PDFs e rastreabilidade ambiental.
- **Clima**: Integração com API OpenWeatherMap.
- **Relatórios PDF**: Exportação de dados com layout executivo via ReportLab.

---

## 🛠️ Stack Tecnológica

- **Backend**: Python 3 / Flask (Application Factory & Blueprints)
- **Banco de Dados**: PostgreSQL com `psycopg2` (Connection Pool)
- **Frontend**: HTML5, CSS3, JavaScript, Jinja2 Templates
- **Relatórios**: ReportLab, Pandas
- **APIs**: OpenWeatherMap API

---

## 🚀 Como Executar Localmente

### 1. Clonar o repositório e preparar o ambiente
```bash
git clone https://github.com/PaulinhoProjects/FazendaCafe.git
cd FazendaCafe
python -m venv venv
venv\Scripts\activate   # No Windows
pip install -r requirements.txt  # ou instalar dependências
```

### 2. Configurar o arquivo `.env`
Copie o arquivo `.env.example` para `.env` e configure suas credenciais do PostgreSQL:
```bash
cp .env.example .env
```

### 3. Iniciar a aplicação
```bash
python run.py
```
Acesse no navegador: `http://localhost:5000`

---

## 📄 Documentação Completa
Para detalhes aprofundados sobre a arquitetura, modelo de dados, tabelas e guia para IA, consulte o arquivo [DOCUMENTACAO_SISTEMA_CLAUDE.md](DOCUMENTACAO_SISTEMA_CLAUDE.md).
