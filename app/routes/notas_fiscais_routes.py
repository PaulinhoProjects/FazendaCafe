from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from app.modules import notas_fiscais
from app.modules import estoque
from app.modules import fornecedores
from app.modules.login_manager import login_required, admin_required
import os
from app.models import get_logger

logger = get_logger(__name__)
notas_fiscais_bp = Blueprint('notas_fiscais', __name__, url_prefix='/notas-fiscais')

@notas_fiscais_bp.route('/')
@login_required
def dashboard():
    try:
        resumo = notas_fiscais.get_resumo_notas()
        notas = notas_fiscais.listar_notas()
        return render_template('notas_fiscais/dashboard.html', resumo=resumo, notas=notas[:10])
    except Exception as e:
        logger.error(f"notas_fiscais_routes.dashboard: {e}")
        flash('Erro ao carregar painel.', 'error')
        return render_template('notas_fiscais/dashboard.html', resumo=None, notas=[])

@notas_fiscais_bp.route('/lista')
@login_required
def listar():
    try:
        notas = notas_fiscais.listar_notas()
        return render_template('notas_fiscais/lista.html', notas=notas)
    except Exception as e:
        logger.error(f"notas_fiscais_routes.listar: {e}")
        flash('Erro ao carregar notas.', 'error')
        return render_template('notas_fiscais/lista.html', notas=[])

@notas_fiscais_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    if request.method == 'POST':
        try:
            fornecedor_id = request.form.get('fornecedor_id')
            nome_fornecedor = ''
            cnpj_fornecedor = ''
            if fornecedor_id == 'novo':
                nome_fornecedor = (request.form.get('novo_fornecedor') or '').strip()
                cnpj_fornecedor = (request.form.get('novo_cnpj') or '').strip()
                fornecedor_id, msg = fornecedores.inserir_fornecedor({
                    'nome': nome_fornecedor, 'cnpj': cnpj_fornecedor})
                if not fornecedor_id:
                    flash(msg, 'error')
                    return render_template('notas_fiscais/nova.html',
                                           fornecedores=fornecedores.listar_fornecedores())
                # Snapshot da nota usa exatamente o que ficou cadastrado
                f = fornecedores.buscar_fornecedor_por_id(fornecedor_id)
                nome_fornecedor = f['nome']
                cnpj_fornecedor = f['cnpj'] or ''
            elif fornecedor_id:
                f = fornecedores.buscar_fornecedor_por_id(int(fornecedor_id))
                if not f or not f['ativo']:
                    flash('Fornecedor inválido.', 'error')
                    return render_template('notas_fiscais/nova.html',
                                           fornecedores=fornecedores.listar_fornecedores())
                fornecedor_id = f['id']
                nome_fornecedor = f['nome']
                cnpj_fornecedor = f['cnpj'] or ''
            else:
                # Compatibilidade com cadastro livre
                nome_fornecedor = (request.form.get('fornecedor') or '').strip()
                cnpj_fornecedor = (request.form.get('cnpj_fornecedor') or '').strip()

            dados = {
                'numero_nota': request.form.get('numero_nota'),
                'serie': request.form.get('serie'),
                'data_emissao': request.form.get('data_emissao'),
                'data_recebimento': request.form.get('data_recebimento'),
                'fornecedor': nome_fornecedor,
                'cnpj_fornecedor': cnpj_fornecedor,
                'fornecedor_id': fornecedor_id,
                'valor_total': request.form.get('valor_total'),
                'observacoes': request.form.get('observacoes')
            }
            arquivo_pdf = None
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename:
                    filename = f"nota_{request.form.get('numero_nota', 'sem_numero')}.pdf"
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    arquivo_pdf = filename

            nota_id = notas_fiscais.inserir_nota_fiscal(dados, arquivo_pdf)
            if nota_id:
                flash('Nota fiscal cadastrada!', 'success')
                return redirect(url_for('notas_fiscais.detalhe', id=nota_id))
            else:
                flash('Erro ao cadastrar.', 'error')
        except Exception as e:
            logger.error(f"notas_fiscais_routes.nova: {e}")
            flash(f'Erro: {e}', 'error')
    return render_template('notas_fiscais/nova.html',
                           fornecedores=fornecedores.listar_fornecedores())

@notas_fiscais_bp.route('/<int:id>')
@login_required
def detalhe(id):
    try:
        nota = notas_fiscais.buscar_nota_por_id(id)
        if not nota:
            flash('Nota nao encontrada.', 'warning')
            return redirect(url_for('notas_fiscais.listar'))
        movimentacoes = notas_fiscais.listar_movimentacoes_por_nota(id)
        pendentes = notas_fiscais.listar_entradas_rapidas_pendentes()
        return render_template('notas_fiscais/detalhe.html', nota=nota,
                               movimentacoes=movimentacoes, pendentes=pendentes)
    except Exception as e:
        logger.error(f"notas_fiscais_routes.detalhe: {e}")
        flash('Erro ao carregar nota.', 'error')
        return redirect(url_for('notas_fiscais.listar'))

@notas_fiscais_bp.route('/<int:id>/entradas-rapidas/vincular', methods=['POST'])
@login_required
def vincular_entradas_rapidas(id):
    ids = request.form.getlist('entrada_ids[]')
    try:
        vinculadas = notas_fiscais.vincular_entradas_rapidas(
            id, ids, session.get('usuario')
        )
        flash('Entradas rápidas vinculadas à nota (estoque não foi alterado): '
              + '; '.join(vinculadas) + '.', 'success')
    except Exception as e:
        logger.error(f"notas_fiscais_routes.vincular_entradas_rapidas: {e}")
        flash(str(e), 'error')
    return redirect(url_for('notas_fiscais.detalhe', id=id))

@notas_fiscais_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir(id):
    try:
        sucesso, msg = notas_fiscais.excluir_nota_fiscal(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"notas_fiscais_routes.excluir: {e}")
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('notas_fiscais.listar'))

@notas_fiscais_bp.route('/<int:id>/itens/novo', methods=['GET', 'POST'])
@login_required
def adicionar_item(id):
    """Adiciona um item a uma nota fiscal com entrada automatica no estoque."""
    if request.method == 'POST':
        try:
            dados = {
                'produto_id': request.form.get('produto_id'),
                'nome_produto': request.form.get('nome_produto'),
                'confirmar_nome': request.form.get('confirmar_nome'),
                'quantidade': request.form.get('quantidade'),
                'valor_unitario': request.form.get('valor_unitario'),
                'unidade': request.form.get('unidade', 'L'),
                'categoria': request.form.get('categoria', 'Outros'),
                'observacoes': request.form.get('observacoes', ''),
                'embalagem_descricao': request.form.get('embalagem_descricao'),
                'embalagem_capacidade': request.form.get('embalagem_capacidade'),
                'embalagem_unidade': request.form.get('embalagem_unidade'),
                'embalagem_quantidade': request.form.get('embalagem_quantidade'),
                'embalagem_preco': request.form.get('embalagem_preco'),
            }
            mov_id, msg = notas_fiscais.adicionar_item_nota(id, dados)
            if mov_id:
                flash(msg, 'success')
            else:
                flash(msg, 'error')
            return redirect(url_for('notas_fiscais.detalhe', id=id))
        except Exception as e:
            logger.error(f"notas_fiscais_routes.adicionar_item: {e}")
            flash(f'Erro ao adicionar item: {e}', 'error')
            return redirect(url_for('notas_fiscais.detalhe', id=id))
    # GET - mostrar formulario
    try:
        nota = notas_fiscais.buscar_nota_por_id(id)
        if not nota:
            flash('Nota nao encontrada.', 'warning')
            return redirect(url_for('notas_fiscais.listar'))
        categorias = estoque.listar_categorias() if hasattr(estoque, 'listar_categorias') else []
        return render_template('notas_fiscais/adicionar_item.html', nota=nota,
                               categorias=categorias,
                               produtos=notas_fiscais.listar_produtos_para_selecao())
    except Exception as e:
        logger.error(f"notas_fiscais_routes.adicionar_item: {e}")
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('notas_fiscais.detalhe', id=id))

@notas_fiscais_bp.route('/<int:id>/itens/<int:item_id>/remover', methods=['POST'])
@login_required
def remover_item(id, item_id):
    """Remove um item da nota fiscal e reverte a entrada no estoque."""
    try:
        sucesso, msg = notas_fiscais.remover_item_nota(item_id)
        flash(msg, 'success' if sucesso else 'error')
    except Exception as e:
        logger.error(f"notas_fiscais_routes.remover_item: {e}")
        flash('Erro ao remover item.', 'error')
    return redirect(url_for('notas_fiscais.detalhe', id=id))

@notas_fiscais_bp.route('/<int:id>/relatorio-pdf')
@login_required
def relatorio_pdf(id):
    """Gera PDF da nota fiscal com itens."""
    try:
        from flask import Response
        nota = notas_fiscais.buscar_nota_por_id(id)
        if not nota:
            flash('Nota nao encontrada.', 'warning')
            return redirect(url_for('notas_fiscais.listar'))
        itens = notas_fiscais.listar_movimentacoes_por_nota(id)
        # Gerar PDF simples
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        import io
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2.4*cm, bottomMargin=1.8*cm)
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Nota Fiscal #{nota.get('numero_nota', '')}", styles['Title']))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(f"Fornecedor: {nota.get('fornecedor', '—')}", styles['Normal']))
        elements.append(Paragraph(f"CNPJ: {nota.get('cnpj_fornecedor', '—')}", styles['Normal']))
        elements.append(Paragraph(f"Data Emissao: {nota.get('data_emissao', '—')}", styles['Normal']))
        elements.append(Paragraph(f"Valor da nota (conferência): R$ {nota.get('valor_total') or 0:.2f}", styles['Normal']))
        elements.append(Spacer(1, 1*cm))
        data_tabela = [['Produto', 'Qtd', 'Unidade', 'Preço na base', 'Valor Total']]
        for item in itens:
            preco_item = item.get('preco_base') or item.get('valor_unitario') or 0
            valor_total_item = (item.get('quantidade', 0) or 0) * preco_item
            data_tabela.append([
                item.get('produto_nome', '—'),
                f"{item.get('quantidade', 0):.2f}",
                item.get('unidade', '—'),
                f"R$ {preco_item:.4f}" if preco_item else '—',
                f"R$ {valor_total_item:.2f}"
            ])
        tabela = Table(data_tabela, colWidths=[6*cm, 2.5*cm, 2*cm, 3*cm, 3*cm])
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A5A3B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ]))
        elements.append(tabela)
        valor_itens = notas_fiscais.valor_itens_nota(id)
        valor_nota = nota.get('valor_total') or 0
        elements.append(Spacer(1, 0.4*cm))
        elements.append(Paragraph(f"Valor dos itens: R$ {valor_itens:.2f}", styles['Normal']))
        elements.append(Paragraph(f"Valor da nota: R$ {valor_nota:.2f}", styles['Normal']))
        elements.append(Paragraph(f"Diferença (nota - itens): R$ {valor_nota - valor_itens:.2f}", styles['Normal']))
        from app.modules.relatorios import moldura_kaldi
        doc.build(elements, onFirstPage=moldura_kaldi, onLaterPages=moldura_kaldi)
        buffer.seek(0)
        return Response(buffer.getvalue(), mimetype='application/pdf',
                       headers={'Content-Disposition': f'attachment; filename=NF_{nota.get("numero_nota", id)}.pdf'})
    except Exception as e:
        logger.error(f"notas_fiscais_routes.relatorio_pdf: {e}")
        flash('Erro ao gerar PDF.', 'error')
        return redirect(url_for('notas_fiscais.detalhe', id=id))