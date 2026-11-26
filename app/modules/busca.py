"""
Módulo de Busca Global — Kaldi
Procura o termo digitado na barra do topo em talhões, produtos, receitas e notas fiscais.
"""
from config.database import executar_query
from app.models import get_logger

logger = get_logger(__name__)

LIMITE_POR_GRUPO = 8

# (grupo, ícone, classe de cor, consulta) — cada consulta devolve id, titulo, detalhe
CONSULTAS = [
    ('talhoes', 'Talhões', 'bi-pin-map', 'bg-primary-soft', """
        SELECT id, nome AS titulo,
               CONCAT_WS(' · ', NULLIF(variedade_cafe, ''),
                         CASE WHEN area_hectares IS NOT NULL THEN area_hectares::text || ' ha' END) AS detalhe
        FROM talhoes
        WHERE ativo = TRUE AND (nome ILIKE %s OR variedade_cafe ILIKE %s)
        ORDER BY nome LIMIT %s
    """),
    ('produtos', 'Produtos do estoque', 'bi-box-seam', 'bg-accent-soft', """
        SELECT id, nome AS titulo,
               CONCAT_WS(' · ', NULLIF(categoria, ''), quantidade_atual::text || ' ' || COALESCE(unidade, '')) AS detalhe
        FROM produtos_estoque
        WHERE ativo = TRUE AND (nome ILIKE %s OR categoria ILIKE %s)
        ORDER BY nome LIMIT %s
    """),
    ('receitas', 'Receitas de pulverização', 'bi-journal-text', 'bg-info-soft', """
        SELECT id, nome AS titulo, NULLIF(descricao, '') AS detalhe
        FROM receitas
        WHERE ativo = TRUE AND (nome ILIKE %s OR descricao ILIKE %s)
        ORDER BY nome LIMIT %s
    """),
    ('notas', 'Notas fiscais', 'bi-receipt', 'bg-warning-soft', """
        SELECT id, 'NF ' || numero_nota AS titulo, NULLIF(fornecedor, '') AS detalhe
        FROM notas_fiscais
        WHERE ativo = TRUE AND (numero_nota ILIKE %s OR fornecedor ILIKE %s)
        ORDER BY id DESC LIMIT %s
    """),
]


def buscar(termo):
    """Retorna uma lista de grupos com os resultados encontrados (grupos vazios são omitidos)."""
    termo = (termo or '').strip()
    if len(termo) < 2:
        return []
    padrao = f"%{termo}%"
    grupos = []
    for chave, rotulo, icone, cor, consulta in CONSULTAS:
        try:
            linhas = executar_query(consulta, (padrao, padrao, LIMITE_POR_GRUPO),
                                    fetch_all=True, dict_cursor=True) or []
        except Exception as e:
            logger.error(f"busca.buscar ({chave}): {e}")
            linhas = []
        if linhas:
            grupos.append({
                'chave': chave, 'rotulo': rotulo, 'icone': icone, 'cor': cor,
                'itens': [{'id': r['id'], 'titulo': r['titulo'], 'detalhe': r['detalhe']} for r in linhas],
            })
    return grupos
