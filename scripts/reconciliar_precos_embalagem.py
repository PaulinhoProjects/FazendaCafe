"""
Reconciliação dos preços de entradas em embalagens gravados antes da correção (commit 8184192).

O cálculo antigo dividia o preço de UMA embalagem pelo volume de TODAS as embalagens da
nota (2 galões de 20 L a R$ 120 viravam R$ 3/L em vez de R$ 6/L). A assinatura do erro é:
    preco_unitario_base × quantidade ≈ preço de uma embalagem   (com mais de uma embalagem)

Como o campo pode ter recebido o TOTAL das embalagens (e aí o valor antigo está certo), só há
correção automática quando a nota PROVA o preço do item: a nota tem só este item, a embalagem é
desta compra (usada por uma única entrada) e o total da nota bate com o valor corrigido. Se a
nota prova o valor antigo, a entrada fica como está. Tudo o que for ambíguo (nota com vários
produtos, sem nota, embalagem compartilhada, total que não bate com nenhum dos dois) vai para
conferência manual — nunca é corrigido sozinho.

Uso:
    python scripts/reconciliar_precos_embalagem.py            # só lista (nada é alterado)
    python scripts/reconciliar_precos_embalagem.py --aplicar  # corrige em uma transação
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'config'))
try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / '.env')
except ImportError:
    pass

from database import executar_query, executar_transacao  # noqa: E402

FATORES = {'l': 1, 'ml': 0.001, 'kg': 1, 'g': 0.001, 'un': 1}
CORRECAO_EM = '2026-11-26 21:24:02-03'


def _fator(origem, destino):
    o, d = (origem or '').strip().lower(), (destino or '').strip().lower()
    if o == d:
        return 1
    if o in FATORES and d in FATORES and ({o, d} in ({'l', 'ml'}, {'kg', 'g'})):
        return FATORES[o] / FATORES[d]
    return None


def analisar():
    linhas = executar_query("""
        SELECT m.id, m.nota_fiscal_id, m.quantidade, m.valor_unitario, m.preco_unitario_base,
               m.embalagens_quantidade, m.data_cadastro, p.nome AS produto, p.unidade AS unidade_base,
               e.id AS embalagem_id, e.descricao, e.capacidade, e.unidade, e.preco AS preco_embalagem,
               n.valor_total AS total_nota,
               (SELECT COUNT(*) FROM movimentacoes_estoque y
                 WHERE y.nota_fiscal_id = m.nota_fiscal_id AND y.tipo = 'entrada' AND y.ativo = TRUE) AS itens_nota,
               (SELECT COUNT(*) FROM movimentacoes_estoque x
                 WHERE x.embalagem_id = m.embalagem_id AND x.tipo = 'entrada') AS usos
        FROM movimentacoes_estoque m
        JOIN produto_embalagens e ON e.id = m.embalagem_id
        JOIN produtos_estoque p ON p.id = m.produto_id
        LEFT JOIN notas_fiscais n ON n.id = m.nota_fiscal_id
        WHERE m.tipo = 'entrada' AND m.ativo = TRUE
          AND COALESCE(m.embalagens_quantidade, 0) > 1
          AND m.data_cadastro < %s
        ORDER BY m.id
    """, (CORRECAO_EM,), fetch_all=True, dict_cursor=True) or []
    corrigir, revisar, mantidos = [], [], []
    for r in linhas:
        fator = _fator(r['unidade'], r['unidade_base'])
        base_atual = float(r['preco_unitario_base'] or r['valor_unitario'] or 0)
        preco_emb = float(r['preco_embalagem'] or 0)
        if not fator or not preco_emb or not base_atual:
            revisar.append((r, 'sem preço da embalagem ou unidade incompatível'))
            continue
        correto = round(preco_emb / (float(r['capacidade']) * fator), 4)
        assinatura = abs(base_atual * float(r['quantidade']) - preco_emb) <= 0.05
        if abs(base_atual - correto) <= 0.0001:
            continue  # já está certo
        total_antigo = base_atual * float(r['quantidade'])
        total_correto = correto * float(r['quantidade'])
        total_nota = float(r['total_nota'] or 0)
        itens_nota = int(r['itens_nota'] or 0)
        tolerancia = max(0.05, 0.005 * max(total_antigo, total_correto))
        if not assinatura:
            revisar.append((r, 'preço diferente do esperado pelo erro antigo: conferir na nota'))
        elif not r['nota_fiscal_id'] or not total_nota:
            revisar.append((r, 'sem nota com total para provar o preço'))
        elif itens_nota != 1:
            revisar.append((r, f'nota com {itens_nota} itens: o total de R$ {total_nota:.2f} não prova o preço deste item'))
        elif int(r['usos']) != 1:
            revisar.append((r, 'embalagem usada por outras compras: o preço dela pode ser de outra nota'))
        elif abs(total_nota - total_correto) <= tolerancia:
            corrigir.append((r, base_atual, correto))
        elif abs(total_nota - total_antigo) <= tolerancia:
            mantidos.append((r, f'nota de R$ {total_nota:.2f} confirma a compra de R$ {total_antigo:.2f}'))
        else:
            revisar.append((r, f'nota de R$ {total_nota:.2f} não bate com R$ {total_antigo:.2f} '
                               f'(atual) nem com R$ {total_correto:.2f} (corrigido)'))
    return corrigir, revisar, mantidos


def aplicar(corrigir):
    def operacao(cur):
        for r, _antes, correto in corrigir:
            cur.execute("""
                UPDATE movimentacoes_estoque
                SET preco_unitario_base = %s, valor_unitario = %s,
                    observacoes = COALESCE(observacoes, '') || %s
                WHERE id = %s AND ativo = TRUE
            """, (correto, round(correto, 2),
                  f' | Preço corrigido na reconciliação: R$ {correto:.4f} por {r["unidade_base"]}', r['id']))
        return len(corrigir)
    return executar_transacao(operacao)


def main():
    corrigir, revisar, mantidos = analisar()
    print(f"Entradas com preço a corrigir automaticamente: {len(corrigir)}")
    for r, antes, correto in corrigir:
        print(f"  #{r['id']} {r['produto']} — {r['embalagens_quantidade']}x {r['descricao']} "
              f"{r['capacidade']} {r['unidade']} a R$ {float(r['preco_embalagem']):.2f}: "
              f"R$ {antes:.4f} -> R$ {correto:.4f} por {r['unidade_base']} "
              f"(compra R$ {antes * float(r['quantidade']):.2f} -> R$ {correto * float(r['quantidade']):.2f})")
    print(f"Entradas que a nota prova estarem certas (mantidas): {len(mantidos)}")
    for r, motivo in mantidos:
        print(f"  #{r['id']} {r['produto']}: {motivo}")
    print(f"Entradas para conferência manual: {len(revisar)}")
    for r, motivo in revisar:
        print(f"  #{r['id']} {r['produto']} (nota {r['nota_fiscal_id']}): {motivo}")
    if '--aplicar' in sys.argv and corrigir:
        print(f"Corrigidas: {aplicar(corrigir)}")
    elif corrigir:
        print("Nada foi alterado. Rode com --aplicar para corrigir.")


if __name__ == '__main__':
    main()
