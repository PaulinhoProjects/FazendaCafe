-- Schema base do Sistema AgroCafé
-- Todas as tabelas usadas pelos módulos da aplicação.

CREATE TABLE IF NOT EXISTS talhoes (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    area_hectares NUMERIC(10,2) NOT NULL,
    data_plantio DATE,
    variedade_cafe VARCHAR(100),
    altitude_media NUMERIC(10,2),
    observacoes TEXT,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE,
    espacamento VARCHAR(50),
    produtor_id INTEGER,
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    foto_url TEXT
);

CREATE TABLE IF NOT EXISTS categorias_estoque (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(50) UNIQUE NOT NULL,
    descricao VARCHAR(255),
    cor VARCHAR(20) DEFAULT 'secondary',
    ativo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS produtos_estoque (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    unidade VARCHAR(20),
    estoque_minimo NUMERIC(12,2) DEFAULT 0,
    quantidade_atual NUMERIC(12,2) DEFAULT 0,
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    categoria VARCHAR(50),
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notas_fiscais (
    id SERIAL PRIMARY KEY,
    numero_nota VARCHAR(50) NOT NULL,
    serie VARCHAR(20),
    data_emissao DATE,
    data_recebimento DATE,
    fornecedor VARCHAR(150),
    cnpj_fornecedor VARCHAR(20),
    valor_total NUMERIC(14,2) DEFAULT 0,
    arquivo_pdf TEXT,
    observacoes TEXT,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE
);

-- Fornecedores pré-cadastrados: a NF escolhe na lista e guarda nome/CNPJ como snapshot
CREATE TABLE IF NOT EXISTS fornecedores (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL UNIQUE,
    cnpj VARCHAR(20),
    telefone VARCHAR(30),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS fornecedor_id INTEGER REFERENCES fornecedores(id);

-- Migra fornecedores já usados nas notas para a nova lista (idempotente)
INSERT INTO fornecedores (nome, cnpj)
SELECT DISTINCT BTRIM(n.fornecedor), NULLIF(BTRIM(n.cnpj_fornecedor), '')
FROM notas_fiscais n
WHERE n.fornecedor IS NOT NULL AND BTRIM(n.fornecedor) <> ''
ON CONFLICT (nome) DO NOTHING;

CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
    id SERIAL PRIMARY KEY,
    produto_id INTEGER REFERENCES produtos_estoque(id),
    tipo VARCHAR(20) NOT NULL,
    quantidade NUMERIC(12,2) NOT NULL DEFAULT 0,
    unidade VARCHAR(20),
    data_movimento DATE DEFAULT CURRENT_DATE,
    valor_unitario NUMERIC(14,2),
    observacoes TEXT,
    nota_fiscal_id INTEGER REFERENCES notas_fiscais(id),
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS devolucao_embalagens (
    id SERIAL PRIMARY KEY,
    data_devolucao DATE NOT NULL,
    local_devolucao VARCHAR(150),
    quantidade_embalagens INTEGER DEFAULT 0,
    nome_responsavel VARCHAR(100),
    numero_comprovante VARCHAR(80),
    arquivo_pdf TEXT,
    observacoes TEXT,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS periodos_lavoura (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    descricao TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS receitas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    periodo_id INTEGER REFERENCES periodos_lavoura(id),
    descricao TEXT,
    formula_completa TEXT,
    produtos TEXT,
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS aplicacoes_pulverizacao (
    id SERIAL PRIMARY KEY,
    talhao_id INTEGER NOT NULL REFERENCES talhoes(id),
    periodo_id INTEGER NOT NULL REFERENCES periodos_lavoura(id),
    receita_id INTEGER REFERENCES receitas(id),
    data_aplicacao DATE NOT NULL DEFAULT CURRENT_DATE,
    data_prevista_retorno DATE,
    responsavel VARCHAR(100),
    condicoes_climaticas TEXT,
    observacoes TEXT,
    tipo_aplicacao VARCHAR(50),
    status_retorno VARCHAR(30),
    observacoes_retorno TEXT,
    data_retorno_realizado DATE,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pragas_doencas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL UNIQUE,
    tipo VARCHAR(50),
    nome_cientifico VARCHAR(150),
    sintomas TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ocorrencias_pragas (
    id SERIAL PRIMARY KEY,
    talhao_id INTEGER NOT NULL REFERENCES talhoes(id),
    praga_doenca_id INTEGER NOT NULL REFERENCES pragas_doencas(id),
    aplicacao_id INTEGER REFERENCES aplicacoes_pulverizacao(id),
    data_deteccao DATE DEFAULT CURRENT_DATE,
    nivel_infestacao VARCHAR(50),
    tratado_na_aplicacao BOOLEAN DEFAULT FALSE,
    observacoes TEXT,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS laboratorios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    responsavel VARCHAR(100),
    telefone VARCHAR(30),
    email VARCHAR(120),
    endereco TEXT,
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tipos_analise (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    descricao TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parametros_analise (
    id SERIAL PRIMARY KEY,
    tipo_analise_id INTEGER NOT NULL REFERENCES tipos_analise(id),
    nome VARCHAR(100) NOT NULL,
    unidade VARCHAR(30),
    ordem_exibicao INTEGER DEFAULT 0,
    ativo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS analises (
    id SERIAL PRIMARY KEY,
    talhao_id INTEGER REFERENCES talhoes(id),
    tipo_analise_id INTEGER NOT NULL REFERENCES tipos_analise(id),
    laboratorio_id INTEGER REFERENCES laboratorios(id),
    data_coleta DATE DEFAULT CURRENT_DATE,
    data_resultado DATE,
    numero_protocolo VARCHAR(50),
    responsavel_coleta VARCHAR(100),
    observacoes TEXT,
    arquivo_pdf TEXT,
    arquivo_original VARCHAR(255),
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Laudos de água, substrato e outros não pertencem necessariamente a um talhão
ALTER TABLE analises ALTER COLUMN talhao_id DROP NOT NULL;
ALTER TABLE analises ADD COLUMN IF NOT EXISTS arquivo_original VARCHAR(255);

CREATE TABLE IF NOT EXISTS resultados_analise (
    id SERIAL PRIMARY KEY,
    analise_id INTEGER NOT NULL REFERENCES analises(id),
    parametro_id INTEGER NOT NULL REFERENCES parametros_analise(id),
    valor NUMERIC(12,4),
    interpretacao TEXT,
    observacoes TEXT,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tipos_adubacao (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    descricao TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recomendacoes_adubacao (
    id SERIAL PRIMARY KEY,
    talhao_id INTEGER NOT NULL REFERENCES talhoes(id),
    analise_id INTEGER REFERENCES analises(id),
    data_recomendacao DATE DEFAULT CURRENT_DATE,
    data_validade DATE,
    responsavel VARCHAR(100),
    observacoes TEXT,
    status VARCHAR(30) DEFAULT 'vigente',
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS itens_recomendacao (
    id SERIAL PRIMARY KEY,
    recomendacao_id INTEGER NOT NULL REFERENCES recomendacoes_adubacao(id),
    nutriente VARCHAR(80),
    quantidade_recomendada NUMERIC(12,2),
    unidade VARCHAR(30),
    fonte_recomendada VARCHAR(150),
    observacoes TEXT
);

CREATE TABLE IF NOT EXISTS adubacoes (
    id SERIAL PRIMARY KEY,
    talhao_id INTEGER NOT NULL REFERENCES talhoes(id),
    recomendacao_id INTEGER REFERENCES recomendacoes_adubacao(id),
    tipo_adubacao_id INTEGER REFERENCES tipos_adubacao(id),
    data_aplicacao DATE DEFAULT CURRENT_DATE,
    responsavel VARCHAR(100),
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS produtos_adubacao (
    id SERIAL PRIMARY KEY,
    adubacao_id INTEGER NOT NULL REFERENCES adubacoes(id),
    produto_nome VARCHAR(150),
    quantidade NUMERIC(12,2),
    unidade VARCHAR(30),
    custo_unitario NUMERIC(14,2),
    fornecedor VARCHAR(150),
    observacoes TEXT
);

CREATE TABLE IF NOT EXISTS nutrientes_aplicados (
    id SERIAL PRIMARY KEY,
    adubacao_id INTEGER NOT NULL REFERENCES adubacoes(id),
    nutriente VARCHAR(80),
    quantidade_aplicada NUMERIC(12,2),
    unidade VARCHAR(30)
);

-- Nutrição e Correção do Solo: compra da formulação, saldo e aplicação por talhão.
-- O estoque é próprio deste módulo: não conversa com insumos, café ou maquinário.
CREATE TABLE IF NOT EXISTS nutri_compras (
    id SERIAL PRIMARY KEY,
    fornecedor VARCHAR(150) NOT NULL,
    numero_nota VARCHAR(80),
    data_nota DATE DEFAULT CURRENT_DATE,
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nutri_compra_itens (
    id SERIAL PRIMARY KEY,
    compra_id INTEGER NOT NULL REFERENCES nutri_compras(id),
    produto VARCHAR(150) NOT NULL,
    formulacao VARCHAR(80),
    marca VARCHAR(100),
    tecnologia VARCHAR(80),
    categoria_id INTEGER REFERENCES tipos_adubacao(id),
    quantidade NUMERIC(14,2) NOT NULL,
    unidade VARCHAR(20) DEFAULT 'kg',
    peso_saco_kg NUMERIC(10,2),
    quantidade_kg NUMERIC(14,2) NOT NULL,
    valor_unitario NUMERIC(14,2),
    valor_total NUMERIC(14,2),
    lote VARCHAR(80),
    validade DATE,
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nutri_aplicacoes (
    id SERIAL PRIMARY KEY,
    compra_item_id INTEGER NOT NULL REFERENCES nutri_compra_itens(id),
    data_aplicacao DATE DEFAULT CURRENT_DATE,
    metodo VARCHAR(60) DEFAULT 'Tratorizada',
    responsavel VARCHAR(100),
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nutri_aplicacao_talhoes (
    id SERIAL PRIMARY KEY,
    aplicacao_id INTEGER NOT NULL REFERENCES nutri_aplicacoes(id),
    talhao_id INTEGER NOT NULL REFERENCES talhoes(id),
    recomendacao_id INTEGER REFERENCES recomendacoes_adubacao(id),
    quantidade_kg NUMERIC(14,2) NOT NULL,
    area_ha NUMERIC(12,2),
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dados iniciais
INSERT INTO periodos_lavoura (nome, descricao) VALUES
    ('Pré-floração', 'Preparação e manejo antes da floração'),
    ('Floração', 'Período de floração e polinização'),
    ('Granação', 'Formação e enchimento dos grãos'),
    ('Maturação', 'Maturação dos frutos'),
    ('Colheita', 'Colheita e pós-colheita'),
    ('Manutenção', 'Manejo geral e manutenção da lavoura')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO tipos_analise (nome, descricao) VALUES
    ('Solo', 'Análise química e física do solo'),
    ('Foliar', 'Análise nutricional de folhas'),
    ('Raiz (Nematódeos)', 'Análise de raízes e nematódeos'),
    ('Água', 'Análise de água de irrigação'),
    ('Substrato', 'Análise de substrato e insumos'),
    ('Outros', 'Outros laudos de laboratório')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO tipos_adubacao (nome, descricao) VALUES
    ('Química', 'Adubação com fertilizantes químicos'),
    ('Orgânica', 'Adubação com materiais orgânicos'),
    ('Bioestimulante', 'Bioestimulantes e promotores de crescimento'),
    ('Micronutrientes', 'Aplicação de micronutrientes'),
    ('Convencional', 'Adubação convencional com até 8 aplicações no ciclo'),
    ('Liberação lenta', 'Tecnologia de liberação lenta: 6 a 10 meses entre aplicações'),
    ('Fertirrigação', 'Nutrição via água de irrigação'),
    ('Tratorizada', 'Aplicação tratorizada no solo'),
    ('Calagem', 'Correção da acidez do solo com calcário'),
    ('Gessagem', 'Correção do solo com gesso agrícola')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO pragas_doencas (nome, tipo, nome_cientifico, sintomas) VALUES
    ('Bicho-mineiro', 'Praga', 'Leucoptera coffeella', 'Minas nas folhas e queda prematura'),
    ('Ferrugem', 'Doença', 'Hemileia vastatrix', 'Pústulas alaranjadas na face inferior das folhas'),
    ('Cártico', 'Doença', 'Colletotrichum gloeosporioides', 'Manchas escuras em frutos e folhas'),
    ('Mancha de Alternaria', 'Doença', 'Alternaria alternata', 'Manchas circulares com halo clorótico'),
    ('Nematoides', 'Praga', 'Meloidogyne spp.', 'Galhas nas raízes e definhamento'),
    ('Broca do café', 'Praga', 'Hypothenemus hampei', 'Perfuracão nos grãos'),
    ('Cochonilha', 'Praga', 'Coccidae', 'Massas algodonadas nos ramos')
ON CONFLICT (nome) DO NOTHING;

-- Parâmetros de análise (usam ON CONFLICT para evitar duplicidade)
INSERT INTO parametros_analise (tipo_analise_id, nome, unidade, ordem_exibicao)
SELECT t.id, v.nome, v.unidade, v.ordem
FROM tipos_analise t
CROSS JOIN (VALUES
    ('pH', '—', 1), ('P (Mehlich)', 'mg/dm³', 2), ('K', 'mg/dm³', 3),
    ('Ca', 'cmolc/dm³', 4), ('Mg', 'cmolc/dm³', 5), ('S', 'mg/dm³', 6),
    ('Matéria Orgânica', 'g/kg', 7), ('CTC', 'cmolc/dm³', 8)
) AS v(nome, unidade, ordem)
WHERE t.nome = 'Solo'
AND NOT EXISTS (SELECT 1 FROM parametros_analise p WHERE p.tipo_analise_id = t.id AND p.nome = v.nome);

INSERT INTO parametros_analise (tipo_analise_id, nome, unidade, ordem_exibicao)
SELECT t.id, v.nome, v.unidade, v.ordem
FROM tipos_analise t
CROSS JOIN (VALUES
    ('N', 'g/kg', 1), ('P', 'g/kg', 2), ('K', 'g/kg', 3),
    ('Ca', 'g/kg', 4), ('Mg', 'g/kg', 5), ('S', 'g/kg', 6),
    ('B', 'mg/kg', 7), ('Zn', 'mg/kg', 8), ('Mn', 'mg/kg', 9),
    ('Fe', 'mg/kg', 10), ('Cu', 'mg/kg', 11)
) AS v(nome, unidade, ordem)
WHERE t.nome = 'Foliar'
AND NOT EXISTS (SELECT 1 FROM parametros_analise p WHERE p.tipo_analise_id = t.id AND p.nome = v.nome);

-- Itens estruturados das receitas de pulverizacao
CREATE TABLE IF NOT EXISTS receita_itens (
    id SERIAL PRIMARY KEY,
    receita_id INTEGER NOT NULL REFERENCES receitas(id),
    produto_id INTEGER REFERENCES produtos_estoque(id),
    produto_nome VARCHAR(150),
    dose NUMERIC(12,3) NOT NULL,
    unidade VARCHAR(20) NOT NULL,
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Talhoes destinatarios de cada receita (um lancamento atende varios talhoes)
CREATE TABLE IF NOT EXISTS receita_talhoes (
    id SERIAL PRIMARY KEY,
    receita_id INTEGER NOT NULL REFERENCES receitas(id),
    talhao_id INTEGER NOT NULL REFERENCES talhoes(id),
    area_hectares NUMERIC(10,2) NOT NULL DEFAULT 0,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (receita_id, talhao_id)
);

-- Fila de aplicacao: uma tarefa por talhao da receita
CREATE TABLE IF NOT EXISTS aplicacao_tarefas (
    id SERIAL PRIMARY KEY,
    receita_id INTEGER NOT NULL REFERENCES receitas(id),
    talhao_id INTEGER NOT NULL REFERENCES talhoes(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pendente',
    responsavel VARCHAR(100),
    area_hectares NUMERIC(10,2) NOT NULL DEFAULT 0,
    data_aplicacao DATE,
    hora_aplicacao VARCHAR(5),
    clima_temperatura NUMERIC(6,1),
    clima_umidade INTEGER,
    clima_descricao VARCHAR(100),
    clima_vento NUMERIC(6,1),
    clima_fonte VARCHAR(100),
    clima_atualizado VARCHAR(10),
    observacoes TEXT,
    criado_por VARCHAR(100),
    concluido_por VARCHAR(100),
    data_conclusao TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (receita_id, talhao_id)
);

-- Produtos de cada tarefa: dosagem e consumo ja calculado para o talhao
CREATE TABLE IF NOT EXISTS aplicacao_tarefa_itens (
    id SERIAL PRIMARY KEY,
    tarefa_id INTEGER NOT NULL REFERENCES aplicacao_tarefas(id),
    produto_id INTEGER REFERENCES produtos_estoque(id),
    produto_nome VARCHAR(150),
    dose NUMERIC(12,3) NOT NULL,
    unidade VARCHAR(20) NOT NULL,
    observacoes TEXT,
    quantidade NUMERIC(12,3) NOT NULL DEFAULT 0,
    saldo_anterior NUMERIC(12,3),
    saldo_posterior NUMERIC(12,3),
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Registro de alteracoes das tarefas (quem mudou o que e quando)
CREATE TABLE IF NOT EXISTS aplicacao_tarefa_log (
    id SERIAL PRIMARY KEY,
    tarefa_id INTEGER NOT NULL REFERENCES aplicacao_tarefas(id),
    acao VARCHAR(40) NOT NULL,
    detalhes TEXT,
    usuario VARCHAR(100),
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Avaliacao de eficacia registrada pelo agronomista apos a aplicacao
CREATE TABLE IF NOT EXISTS avaliacoes_eficacia (
    id SERIAL PRIMARY KEY,
    tarefa_id INTEGER NOT NULL UNIQUE REFERENCES aplicacao_tarefas(id),
    talhao_id INTEGER NOT NULL REFERENCES talhoes(id),
    receita_id INTEGER NOT NULL REFERENCES receitas(id),
    agronomista VARCHAR(100),
    data_avaliacao DATE NOT NULL DEFAULT CURRENT_DATE,
    resultado VARCHAR(20) NOT NULL,
    nota INTEGER,
    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Entradas rápidas feitas no campo: origem, quem confirmou e tarefa vinculada
ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS origem VARCHAR(20);
ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS confirmado_por VARCHAR(100);
ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS tarefa_id INTEGER REFERENCES aplicacao_tarefas(id);
CREATE INDEX IF NOT EXISTS idx_movimentacoes_origem ON movimentacoes_estoque(origem);

-- Embalagens: permite comprar 10 galões de 20 L e controlar a abertura de cada um
CREATE TABLE IF NOT EXISTS produto_embalagens (
    id SERIAL PRIMARY KEY,
    produto_id INTEGER NOT NULL REFERENCES produtos_estoque(id),
    descricao VARCHAR(100) NOT NULL,
    capacidade NUMERIC(12,2) NOT NULL,
    unidade VARCHAR(20) NOT NULL,
    preco NUMERIC(14,2),
    nota_fiscal_id INTEGER REFERENCES notas_fiscais(id),
    quantidade_total INTEGER NOT NULL DEFAULT 0,
    quantidade_fechada INTEGER NOT NULL DEFAULT 0,
    volume_aberta NUMERIC(12,2) DEFAULT 0,
    ativo BOOLEAN DEFAULT TRUE,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movimento_embalagens (
    id SERIAL PRIMARY KEY,
    movimento_id INTEGER NOT NULL REFERENCES movimentacoes_estoque(id),
    embalagem_id INTEGER NOT NULL REFERENCES produto_embalagens(id),
    tipo VARCHAR(10) NOT NULL,
    quantidade INTEGER NOT NULL,
    litros NUMERIC(12,2) NOT NULL,
    observacoes TEXT,
    data_movimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Preço por unidade base em cada compra: histórico para alta/baixa
ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS preco_unitario_base NUMERIC(14,4);
ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS embalagem_id INTEGER REFERENCES produto_embalagens(id);
ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS embalagens_quantidade INTEGER;
ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS embalagens_abertas INTEGER;

CREATE INDEX IF NOT EXISTS idx_movimentacoes_produto_data ON movimentacoes_estoque(produto_id, data_movimento DESC);
CREATE INDEX IF NOT EXISTS idx_embalagens_produto ON produto_embalagens(produto_id);

-- Cotações externas: uma linha por fonte/cotação a cada coleta (histórico)
CREATE TABLE IF NOT EXISTS cotacoes_snapshots (
    id SERIAL PRIMARY KEY,
    chave VARCHAR(30) NOT NULL,
    fonte VARCHAR(50) NOT NULL,
    papel VARCHAR(80),
    descricao VARCHAR(180),
    valor NUMERIC(14,4) NOT NULL,
    valor_compra NUMERIC(14,4),
    unidade VARCHAR(40),
    variacao NUMERIC(12,4),
    variacao_percentual NUMERIC(12,4),
    data_origem VARCHAR(60),
    coletado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE cotacoes_snapshots ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_cotacoes_snapshots_chave_data ON cotacoes_snapshots(chave, coletado_em DESC);
CREATE INDEX IF NOT EXISTS idx_cotacoes_snapshots_ativo_data ON cotacoes_snapshots(ativo, coletado_em DESC);

-- Monitoramento das fontes externas: eventos de sucesso, falha e aviso
CREATE TABLE IF NOT EXISTS cotacoes_saude (
    id SERIAL PRIMARY KEY,
    fonte VARCHAR(60) NOT NULL,
    status VARCHAR(10) NOT NULL,
    mensagem VARCHAR(255),
    quantidade INTEGER DEFAULT 0,
    data_origem VARCHAR(60),
    duracao_ms INTEGER DEFAULT 0,
    url VARCHAR(255),
    verificado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_cotacoes_saude_fonte_data ON cotacoes_saude(fonte, verificado_em DESC);
CREATE INDEX IF NOT EXISTS idx_cotacoes_saude_ativo_data ON cotacoes_saude(ativo, verificado_em DESC);

-- ============================================================
-- MAQUINÁRIO: estrutura isolada do estoque de insumos/café
-- ============================================================

CREATE TABLE IF NOT EXISTS maq_produtos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    categoria VARCHAR(60),
    unidade VARCHAR(20) DEFAULT 'un',
    quantidade_atual NUMERIC(12,2) NOT NULL DEFAULT 0,
    estoque_minimo NUMERIC(12,2) NOT NULL DEFAULT 0,
    local_armazenagem VARCHAR(100),
    observacoes TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_maq_produtos_ativo_nome ON maq_produtos(ativo, nome);

CREATE TABLE IF NOT EXISTS maq_movimentacoes (
    id SERIAL PRIMARY KEY,
    produto_id INTEGER NOT NULL REFERENCES maq_produtos(id),
    tipo VARCHAR(10) NOT NULL,
    quantidade NUMERIC(12,2) NOT NULL,
    unidade VARCHAR(20),
    data_movimento DATE NOT NULL DEFAULT CURRENT_DATE,
    valor_unitario NUMERIC(14,4),
    nota_fiscal VARCHAR(80),
    observacoes TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_maq_mov_produto_data ON maq_movimentacoes(produto_id, data_movimento DESC);

CREATE TABLE IF NOT EXISTS maq_maquinas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    marca VARCHAR(80),
    modelo VARCHAR(80),
    ano VARCHAR(10),
    numero_serie VARCHAR(80),
    placa VARCHAR(20),
    horas_atuais NUMERIC(12,1) NOT NULL DEFAULT 0,
    data_aquisicao DATE,
    observacoes TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS maq_manutencoes (
    id SERIAL PRIMARY KEY,
    maquina_id INTEGER NOT NULL REFERENCES maq_maquinas(id),
    tipo VARCHAR(40) NOT NULL,
    data_servico DATE NOT NULL DEFAULT CURRENT_DATE,
    horimetro NUMERIC(12,1),
    descricao TEXT,
    valor NUMERIC(14,2) DEFAULT 0,
    fornecedor VARCHAR(150),
    proxima_data DATE,
    proximas_horas NUMERIC(12,1),
    observacoes TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_maq_manutencoes_maquina_data ON maq_manutencoes(maquina_id, data_servico DESC);

CREATE TABLE IF NOT EXISTS maq_abastecimentos (
    id SERIAL PRIMARY KEY,
    maquina_id INTEGER REFERENCES maq_maquinas(id),
    data_abastecimento DATE NOT NULL DEFAULT CURRENT_DATE,
    produto VARCHAR(40) NOT NULL DEFAULT 'DIESEL S10',
    quantidade_litros NUMERIC(12,2) NOT NULL,
    valor_litro NUMERIC(12,4) NOT NULL,
    valor_total NUMERIC(14,2) NOT NULL,
    fornecedor VARCHAR(150),
    boleto VARCHAR(100),
    vencimento DATE,
    lembrete_em DATE,
    pago BOOLEAN NOT NULL DEFAULT TRUE,
    data_pagamento DATE,
    observacoes TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_maq_abastecimentos_data ON maq_abastecimentos(data_abastecimento DESC);
CREATE INDEX IF NOT EXISTS idx_maq_abastecimentos_pago ON maq_abastecimentos(pago, vencimento);

CREATE TABLE IF NOT EXISTS maq_precos_diesel (
    id SERIAL PRIMARY KEY,
    nivel VARCHAR(20) NOT NULL,
    municipio VARCHAR(100) NOT NULL,
    uf VARCHAR(2),
    produto VARCHAR(40) NOT NULL DEFAULT 'DIESEL S10',
    data_coleta DATE NOT NULL,
    preco_medio NUMERIC(12,4) NOT NULL,
    preco_min NUMERIC(12,4),
    preco_max NUMERIC(12,4),
    amostras INTEGER DEFAULT 0,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (nivel, municipio, data_coleta)
);
CREATE INDEX IF NOT EXISTS idx_maq_precos_diesel_data ON maq_precos_diesel(data_coleta DESC, nivel);

CREATE TABLE IF NOT EXISTS maq_gastos (
    id SERIAL PRIMARY KEY,
    data_gasto DATE NOT NULL DEFAULT CURRENT_DATE,
    descricao VARCHAR(200) NOT NULL,
    categoria VARCHAR(60),
    maquina_id INTEGER REFERENCES maq_maquinas(id),
    valor NUMERIC(14,2) NOT NULL,
    local_compra VARCHAR(150),
    fornecedor VARCHAR(150),
    nota_fiscal VARCHAR(80),
    observacoes TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_maq_gastos_data ON maq_gastos(data_gasto DESC);

-- =====================================================
-- MANEJO DO CAFÉ: calendário (modelo editável), execuções por safra e gastos
-- =====================================================
CREATE TABLE IF NOT EXISTS cafe_calendario (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(150) NOT NULL,
    descricao TEXT,
    categoria VARCHAR(60),
    periodo_id INTEGER REFERENCES periodos_lavoura(id),
    mes_inicio SMALLINT NOT NULL CHECK (mes_inicio BETWEEN 1 AND 12),
    mes_fim SMALLINT NOT NULL CHECK (mes_fim BETWEEN 1 AND 12),
    ordem INTEGER NOT NULL DEFAULT 0,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cafe_calendario_execucoes (
    id SERIAL PRIMARY KEY,
    tarefa_id INTEGER NOT NULL REFERENCES cafe_calendario(id),
    safra VARCHAR(9) NOT NULL,
    talhao_id INTEGER REFERENCES talhoes(id),
    data_execucao DATE NOT NULL DEFAULT CURRENT_DATE,
    observacoes TEXT,
    usuario VARCHAR(100),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cafe_exec_safra ON cafe_calendario_execucoes(safra, tarefa_id);

CREATE TABLE IF NOT EXISTS cafe_gastos (
    id SERIAL PRIMARY KEY,
    data_gasto DATE NOT NULL DEFAULT CURRENT_DATE,
    safra VARCHAR(9) NOT NULL,
    categoria VARCHAR(60) NOT NULL,
    descricao VARCHAR(200),
    forma_pagamento VARCHAR(20) NOT NULL,
    talhao_id INTEGER REFERENCES talhoes(id),
    trabalhador VARCHAR(150),
    pessoas INTEGER NOT NULL DEFAULT 1,
    quantidade NUMERIC(14,2) NOT NULL DEFAULT 1,
    unidade VARCHAR(30),
    valor_unitario NUMERIC(14,2),
    valor_total NUMERIC(14,2) NOT NULL,
    pago BOOLEAN NOT NULL DEFAULT TRUE,
    observacoes TEXT,
    usuario VARCHAR(100),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cafe_gastos_safra ON cafe_gastos(safra, data_gasto DESC);
