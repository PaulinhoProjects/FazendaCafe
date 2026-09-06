from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.modules import notas_fiscais
from app.modules import estoque
from app.modules.login_manager import login_required, admin_required
import os

notas_fiscais_bp = Blueprint('notas_fiscais', __name__, url_prefix='/notas-fiscais')

@notas_fiscais_bp.route('/')
@login_required
def dashboard():
    try:
        resumo = notas_fiscais.get_resumo_notas()
        notas = notas_fiscais.listar_notas()
        return render_template('notas_fiscais/dashboard.html', resumo=resumo, notas=notas[:10])
    except Exception as e:
        flash('Erro ao carregar painel.', 'error')
        return render_template('notas_fiscais/dashboard.html', resumo=None, notas=[])

@notas_fiscais_bp.route('/lista')
@login_required
def listar():
    try:
        notas = notas_fiscais.listar_notas()
        return render_template('notas_fiscais/lista.html', notas=notas)
    except Exception as e:
        flash('Erro ao carregar notas.', 'error')
        return render_template('notas_fiscais/lista.html', notas=[])

@notas_fiscais_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    if request.method == 'POST':
        try:
            dados = {
                'numero_nota': request.form.get('numero_nota'),
                'serie': request.form.get('serie'),
                'data_emissao': request.form.get('data_emissao'),
                'data_recebimento': request.form.get('data_recebimento'),
                'fornecedor': request.form.get('fornecedor'),
                'cnpj_fornecedor': request.form.get('cnpj_fornecedor'),
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
            flash(f'Erro: {e}', 'error')
    return render_template('notas_fiscais/nova.html')

@notas_fiscais_bp.route('/<int:id>')
@login_required
def detalhe(id):
    try:
        nota = notas_fiscais.buscar_nota_por_id(id)
        if not nota:
            flash('Nota nao encontrada.', 'warning')
            return redirect(url_for('notas_fiscais.listar'))
        movimentacoes = notas_fiscais.listar_movimentacoes_por_nota(id)
        return render_template('notas_fiscais/detalhe.html', nota=nota, movimentacoes=movimentacoes)
    except Exception as e:
        flash('Erro ao carregar nota.', 'error')
        return redirect(url_for('notas_fiscais.listar'))

@notas_fiscais_bp.route('/<int:id>/excluir', methods=['POST'])
@admin_required
@login_required
def excluir(id):
    try:
        sucesso, msg = notas_fiscais.excluir_nota_fiscal(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('notas_fiscais.listar'))

@notas_fiscais_bp.route('/<int:id>/itens/novo', methods=['GET', 'POST'])
@login_required
def adicionar_item(id):
    """Adiciona um item a uma nota fiscal com entrada automatica no estoque."""
    if request.method == 'POST':
        try:
            dados = {
                'nome_produto': request.form.get('nome_produto'),
                'quantidade': request.form.get('quantidade'),
                'valor_unitario': request.form.get('valor_unitario'),
                'unidade': request.form.get('unidade', 'L'),
                'categoria': request.form.get('categoria', 'Outros'),
                'observacoes': request.form.get('observacoes', '')
            }
            mov_id, msg = notas_fiscais.adicionar_item_nota(id, dados)
            if mov_id:
                flash(msg, 'success')
            else:
                flash(msg, 'error')
            return redirect(url_for('notas_fiscais.detalhe', id=id))
        except Exception as e:
            flash(f'Erro ao adicionar item: {e}', 'error')
            return redirect(url_for('notas_fiscais.detalhe', id=id))
    # GET - mostrar formulario
    try:
        nota = notas_fiscais.buscar_nota_por_id(id)
        if not nota:
            flash('Nota nao encontrada.', 'warning')
            return redirect(url_for('notas_fiscais.listar'))
        categorias = estoque.listar_categorias() if hasattr(estoque, 'listar_categorias') else []
        return render_template('notas_fiscais/adicionar_item.html', nota=nota, categorias=categorias)
    except Exception as e:
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
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Nota Fiscal #{nota.get('numero_nota', '')}", styles['Title']))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(f"Fornecedor: {nota.get('fornecedor', '—')}", styles['Normal']))
        elements.append(Paragraph(f"CNPJ: {nota.get('cnpj_fornecedor', '—')}", styles['Normal']))
        elements.append(Paragraph(f"Data Emissao: {nota.get('data_emissao', '—')}", styles['Normal']))
        elements.append(Paragraph(f"Valor Total: R$ {nota.get('valor_total') or 0:.2f}", styles['Normal']))
        elements.append(Spacer(1, 1*cm))
        data_tabela = [['Produto', 'Qtd', 'Unidade', 'Valor Unit.', 'Valor Total']]
        for item in itens:
            valor_total_item = (item.get('quantidade', 0) or 0) * (item.get('valor_unitario', 0) or 0)
            data_tabela.append([
                item.get('produto_nome', '—'),
                f"{item.get('quantidade', 0):.2f}",
                item.get('unidade', '—'),
                f"R$ {item.get('valor_unitario', 0):.2f}" if item.get('valor_unitario') else '—',
                f"R$ {valor_total_item:.2f}"
            ])
        tabela = Table(data_tabela, colWidths=[6*cm, 2.5*cm, 2*cm, 3*cm, 3*cm])
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C5F2D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ]))
        elements.append(tabela)
        doc.build(elements)
        buffer.seek(0)
        return Response(buffer.getvalue(), mimetype='application/pdf',
                       headers={'Content-Disposition': f'attachment; filename=NF_{nota.get("numero_nota", id)}.pdf'})
    except Exception as e:
        flash('Erro ao gerar PDF.', 'error')
        return redirect(url_for('notas_fiscais.detalhe', id=id))