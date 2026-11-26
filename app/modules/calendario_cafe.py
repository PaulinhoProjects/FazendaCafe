"""
Calendário do café: tarefas de manejo por mês (modelo editável) e o check de
execução por safra.

A safra vai de setembro a agosto (ex.: 2026/27 = set/2026 a ago/2027), da
florada até o fim da colheita. O mês de início pode ser ajustado pela
configuração "cafe_safra_mes_inicio".
"""
import os
import sys
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, get_config  # noqa: E402
from app.models import get_logger  # noqa: E402

logger = get_logger(__name__)

MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
MESES_NOME = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho',
              'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
CATEGORIAS = ['Planejamento', 'Solo', 'Nutrição', 'Fitossanidade', 'Tratos culturais',
              'Colheita', 'Pós-colheita']

# Modelo inicial — calendário típico do arábica no Sul de Minas.
# (título, categoria, período, mês início, mês fim, descrição)
MODELO_SUL_DE_MINAS = [
    ('Análise de solo — coleta das amostras', 'Planejamento', 'Manutenção', 9, 10,
     'Coletar amostras (0–20 e 20–40 cm) por talhão logo após a colheita para planejar calagem e adubação.'),
    ('Calagem e gessagem', 'Solo', 'Pré-floração', 9, 10,
     'Aplicar calcário e gesso conforme a análise, antes do início das chuvas.'),
    ('Poda (recepa, esqueletamento, decote)', 'Tratos culturais', 'Pré-floração', 9, 10,
     'Executar logo após a colheita nos talhões programados para poda.'),
    ('Arruação / esparramação do cisco', 'Tratos culturais', 'Pré-floração', 9, 9,
     'Devolver o cisco da colheita para debaixo da saia do cafeeiro.'),
    ('Pulverização de pré e pós-florada', 'Fitossanidade', 'Floração', 9, 11,
     'Proteção contra phoma, mancha-aureolada e ácaros conforme o histórico do talhão; boro e zinco junto.'),
    ('1ª adubação de solo (NPK)', 'Nutrição', 'Floração', 10, 11,
     'Primeira parcela com o solo úmido, depois das primeiras chuvas.'),
    ('Adubação foliar (boro, zinco, cobre)', 'Nutrição', 'Floração', 10, 12,
     'Complementar micronutrientes na fase de florada e chumbinho.'),
    ('Desbrota', 'Tratos culturais', 'Granação', 11, 2,
     'Retirar os brotos ladrões nas lavouras podadas ou recepadas.'),
    ('Controle do mato (roçada, capina, herbicida na linha)', 'Tratos culturais', 'Granação', 11, 3,
     'Manter a linha do café limpa no período das águas.'),
    ('2ª adubação de solo (NPK)', 'Nutrição', 'Granação', 12, 1,
     'Segunda parcela da adubação no período chuvoso.'),
    ('Controle de ferrugem e cercospora', 'Fitossanidade', 'Granação', 12, 3,
     'Fungicida sistêmico no período chuvoso; monitorar a incidência nos talhões.'),
    ('Monitoramento e controle da broca', 'Fitossanidade', 'Granação', 12, 2,
     'Trânsito da broca: amostrar frutos e controlar se passar do nível de controle.'),
    ('Análise foliar', 'Planejamento', 'Granação', 1, 2,
     'Coletar folhas para conferir a nutrição durante a granação.'),
    ('3ª adubação de solo (NPK)', 'Nutrição', 'Granação', 2, 3,
     'Última parcela, antes do fim das chuvas.'),
    ('Monitoramento do bicho-mineiro', 'Fitossanidade', 'Maturação', 3, 8,
     'A pressão aumenta na seca; acompanhar as folhas minadas.'),
    ('Organizar a mão de obra da colheita', 'Planejamento', 'Maturação', 3, 4,
     'Combinar equipes, valores da panha e alojamento.'),
    ('Preparar a colheita (terreiro, secador, máquinas, panos, sacaria)', 'Colheita', 'Maturação', 4, 5,
     'Revisar estrutura e equipamentos antes de começar a panha.'),
    ('Colheita (panha manual ou mecanizada)', 'Colheita', 'Colheita', 5, 8,
     'Colher conforme a maturação de cada talhão.'),
    ('Secagem, beneficiamento e armazenamento', 'Pós-colheita', 'Colheita', 5, 8,
     'Controlar a umidade do grão e separar os lotes por qualidade.'),
    ('Varrição e recolhimento do café do chão', 'Colheita', 'Colheita', 7, 8,
     'Recolher o café caído reduz a broca na safra seguinte.'),
    ('Fechamento da safra: produtividade e custos por talhão', 'Planejamento', 'Colheita', 8, 8,
     'Comparar produção, gastos e resultados para planejar a próxima safra.'),
]


# ---------------------------------------------------------------------------
# Safra
# ---------------------------------------------------------------------------
def mes_inicio_safra():
    try:
        mes = int(get_config('cafe_safra_mes_inicio', '9'))
        return mes if 1 <= mes <= 12 else 9
    except (TypeError, ValueError):
        return 9


def safra_de(data=None):
    """Nome da safra de uma data, ex.: '2026/27'."""
    data = data or date.today()
    inicio = mes_inicio_safra()
    ano = data.year if data.month >= inicio else data.year - 1
    if inicio == 1:
        return str(ano)
    return f"{ano}/{(ano + 1) % 100:02d}"


def meses_da_safra():
    """Lista dos 12 meses na ordem da safra: [(número, sigla), ...]."""
    inicio = mes_inicio_safra()
    return [((inicio - 1 + i) % 12 + 1, MESES[(inicio - 1 + i) % 12]) for i in range(12)]


def _indice(mes):
    return (mes - mes_inicio_safra()) % 12


def _no_periodo(mes, inicio, fim):
    if inicio <= fim:
        return inicio <= mes <= fim
    return mes >= inicio or mes <= fim


def safras_disponiveis():
    atual = safra_de()
    try:
        linhas = executar_query("""
            SELECT DISTINCT safra FROM cafe_calendario_execucoes WHERE ativo = TRUE
            UNION
            SELECT DISTINCT safra FROM cafe_gastos WHERE ativo = TRUE
        """, fetch_all=True, dict_cursor=True) or []
        safras = {r['safra'] for r in linhas} | {atual}
    except Exception as e:
        logger.error(f"calendario_cafe.safras_disponiveis: {e}")
        safras = {atual}
    return sorted(safras, reverse=True)


# ---------------------------------------------------------------------------
# Modelo do calendário
# ---------------------------------------------------------------------------
def garantir_modelo():
    """Na primeira execução, carrega o modelo do Sul de Minas (só se a tabela nunca teve tarefas)."""
    try:
        existe = executar_query("SELECT COUNT(*) AS total FROM cafe_calendario",
                                fetch_one=True, dict_cursor=True)
        if existe and existe['total']:
            return
        periodos = executar_query("SELECT id, nome FROM periodos_lavoura WHERE ativo = TRUE",
                                  fetch_all=True, dict_cursor=True) or []
        por_nome = {p['nome']: p['id'] for p in periodos}
        for ordem, (titulo, categoria, periodo, inicio, fim, descricao) in enumerate(MODELO_SUL_DE_MINAS, 1):
            executar_query("""
                INSERT INTO cafe_calendario (titulo, descricao, categoria, periodo_id, mes_inicio, mes_fim, ordem)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (titulo, descricao, categoria, por_nome.get(periodo), inicio, fim, ordem))
    except Exception as e:
        logger.error(f"calendario_cafe.garantir_modelo: {e}")


def listar_periodos():
    try:
        return executar_query("SELECT id, nome FROM periodos_lavoura WHERE ativo = TRUE ORDER BY id",
                              fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"calendario_cafe.listar_periodos: {e}")
        return []


def listar_tarefas():
    try:
        linhas = executar_query("""
            SELECT c.id, c.titulo, c.descricao, c.categoria, c.periodo_id, c.mes_inicio, c.mes_fim,
                   c.ordem, p.nome AS periodo_nome
            FROM cafe_calendario c
            LEFT JOIN periodos_lavoura p ON p.id = c.periodo_id
            WHERE c.ativo = TRUE
        """, fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"calendario_cafe.listar_tarefas: {e}")
        return []
    tarefas = []
    for r in linhas:
        duracao = (r['mes_fim'] - r['mes_inicio']) % 12 + 1
        inicio_idx = _indice(r['mes_inicio'])
        tarefas.append({
            'id': r['id'], 'titulo': r['titulo'], 'descricao': r['descricao'] or '',
            'categoria': r['categoria'] or 'Planejamento', 'periodo_id': r['periodo_id'],
            'periodo_nome': r['periodo_nome'] or '', 'mes_inicio': r['mes_inicio'],
            'mes_fim': r['mes_fim'], 'ordem': r['ordem'], 'duracao': duracao,
            'inicio_idx': inicio_idx, 'fim_idx': inicio_idx + duracao - 1,
            'janela': MESES[r['mes_inicio'] - 1] if duracao == 1
            else f"{MESES[r['mes_inicio'] - 1]}–{MESES[r['mes_fim'] - 1]}",
        })
    return sorted(tarefas, key=lambda t: (t['inicio_idx'], t['ordem'], t['titulo']))


def buscar_tarefa(tarefa_id):
    return next((t for t in listar_tarefas() if t['id'] == tarefa_id), None)


def _validar(dados):
    titulo = (dados.get('titulo') or '').strip()
    if not titulo:
        return None, 'Informe o nome da tarefa.'
    try:
        inicio = int(dados.get('mes_inicio'))
        fim = int(dados.get('mes_fim'))
    except (TypeError, ValueError):
        return None, 'Escolha o mês de início e de fim.'
    if not (1 <= inicio <= 12 and 1 <= fim <= 12):
        return None, 'Mês inválido.'
    categoria = dados.get('categoria') if dados.get('categoria') in CATEGORIAS else 'Planejamento'
    try:
        periodo_id = int(dados.get('periodo_id')) if dados.get('periodo_id') else None
    except (TypeError, ValueError):
        periodo_id = None
    descricao = (dados.get('descricao') or '').strip() or None
    return (titulo[:150], descricao, categoria, periodo_id, inicio, fim), None


def salvar_tarefa(tarefa_id, dados):
    valores, erro = _validar(dados)
    if erro:
        return False, erro
    try:
        if tarefa_id:
            executar_query("""
                UPDATE cafe_calendario
                SET titulo = %s, descricao = %s, categoria = %s, periodo_id = %s,
                    mes_inicio = %s, mes_fim = %s
                WHERE id = %s AND ativo = TRUE
            """, valores + (tarefa_id,))
            return True, 'Tarefa do calendário atualizada.'
        executar_query("""
            INSERT INTO cafe_calendario (titulo, descricao, categoria, periodo_id, mes_inicio, mes_fim, ordem)
            VALUES (%s, %s, %s, %s, %s, %s,
                    (SELECT COALESCE(MAX(ordem), 0) + 1 FROM cafe_calendario))
        """, valores)
        return True, 'Tarefa incluída no calendário.'
    except Exception as e:
        logger.error(f"calendario_cafe.salvar_tarefa: {e}")
        return False, 'Não foi possível salvar a tarefa.'


def excluir_tarefa(tarefa_id):
    try:
        executar_query("UPDATE cafe_calendario SET ativo = FALSE WHERE id = %s", (tarefa_id,))
        return True, 'Tarefa removida do calendário.'
    except Exception as e:
        logger.error(f"calendario_cafe.excluir_tarefa: {e}")
        return False, 'Não foi possível remover a tarefa.'


# ---------------------------------------------------------------------------
# Execução por safra
# ---------------------------------------------------------------------------
def listar_execucoes(safra):
    try:
        return executar_query("""
            SELECT e.id, e.tarefa_id, e.talhao_id, e.data_execucao, e.observacoes, e.usuario,
                   t.nome AS talhao_nome
            FROM cafe_calendario_execucoes e
            LEFT JOIN talhoes t ON t.id = e.talhao_id
            WHERE e.ativo = TRUE AND e.safra = %s
            ORDER BY e.data_execucao DESC, e.id DESC
        """, (safra,), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"calendario_cafe.listar_execucoes: {e}")
        return []


def registrar_execucao(tarefa_id, safra, dados, usuario):
    try:
        talhao_id = int(dados.get('talhao_id')) if dados.get('talhao_id') else None
    except (TypeError, ValueError):
        talhao_id = None
    data_execucao = dados.get('data_execucao') or None
    observacoes = (dados.get('observacoes') or '').strip() or None
    try:
        executar_query("""
            INSERT INTO cafe_calendario_execucoes
                (tarefa_id, safra, talhao_id, data_execucao, observacoes, usuario)
            VALUES (%s, %s, %s, COALESCE(%s::date, CURRENT_DATE), %s, %s)
        """, (tarefa_id, safra, talhao_id, data_execucao, observacoes, usuario))
        return True, 'Tarefa marcada como feita.'
    except Exception as e:
        logger.error(f"calendario_cafe.registrar_execucao: {e}")
        return False, 'Não foi possível registrar a execução.'


def desfazer_execucao(execucao_id):
    try:
        executar_query("UPDATE cafe_calendario_execucoes SET ativo = FALSE WHERE id = %s", (execucao_id,))
        return True, 'Registro de execução removido.'
    except Exception as e:
        logger.error(f"calendario_cafe.desfazer_execucao: {e}")
        return False, 'Não foi possível remover o registro.'


def montar_calendario(safra=None, hoje=None):
    """Tarefas com a situação na safra: feita, agora, atrasada, proxima ou futura."""
    hoje = hoje or date.today()
    safra = safra or safra_de(hoje)
    safra_atual = safra_de(hoje)
    idx_hoje = _indice(hoje.month)
    execucoes = listar_execucoes(safra)
    por_tarefa = {}
    for e in execucoes:
        por_tarefa.setdefault(e['tarefa_id'], []).append(e)

    tarefas = listar_tarefas()
    for t in tarefas:
        t['execucoes'] = por_tarefa.get(t['id'], [])
        if t['execucoes']:
            t['situacao'] = 'feita'
        elif safra < safra_atual:
            t['situacao'] = 'atrasada'
        elif safra > safra_atual:
            t['situacao'] = 'futura'
        elif _no_periodo(hoje.month, t['mes_inicio'], t['mes_fim']):
            t['situacao'] = 'agora'
        elif t['fim_idx'] <= 11 and idx_hoje > t['fim_idx']:
            t['situacao'] = 'atrasada'
        elif 0 < (t['inicio_idx'] - idx_hoje) <= 1:
            t['situacao'] = 'proxima'
        else:
            t['situacao'] = 'futura'

    contagem = {s: sum(1 for t in tarefas if t['situacao'] == s)
                for s in ('feita', 'agora', 'atrasada', 'proxima', 'futura')}
    return {
        'safra': safra, 'safra_atual': safra_atual, 'tarefas': tarefas, 'contagem': contagem,
        'meses': meses_da_safra(), 'mes_hoje_idx': idx_hoje if safra == safra_atual else None,
        'mes_hoje_nome': MESES_NOME[hoje.month - 1], 'total': len(tarefas),
    }


def sugestoes_do_mes(limite=6):
    """Resumo para a visão geral do manejo: o que fazer agora e o que ficou para trás."""
    dados = montar_calendario()
    agora = [t for t in dados['tarefas'] if t['situacao'] == 'agora']
    atrasadas = [t for t in dados['tarefas'] if t['situacao'] == 'atrasada']
    proximas = [t for t in dados['tarefas'] if t['situacao'] == 'proxima']
    return {
        'safra': dados['safra'], 'mes': dados['mes_hoje_nome'],
        'agora': agora[:limite], 'atrasadas': atrasadas[:limite], 'proximas': proximas[:limite],
        'total_agora': len(agora), 'total_atrasadas': len(atrasadas),
        'feitas': dados['contagem']['feita'], 'total': dados['total'],
    }
