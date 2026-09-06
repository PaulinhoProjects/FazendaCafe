function paginarTabela(tabelaId, itensPorPagina = 20) {
    const tabela = document.getElementById(tabelaId);
    if (!tabela) return;

    const tbody = tabela.querySelector('tbody');
    if (!tbody) return;

    const linhas = Array.from(tbody.querySelectorAll('tr'));
    const total = linhas.length;
    const totalPaginas = Math.ceil(total / itensPorPagina);
    let paginaAtual = 1;

    // Criar controles de paginação
    let paginacao = tabela.parentElement.querySelector('.paginacao');
    if (!paginacao) {
        paginacao = document.createElement('div');
        paginacao.className = 'paginacao d-flex justify-content-between align-items-center mt-3';
        tabela.parentElement.appendChild(paginacao);
    }

    function renderizar() {
        const inicio = (paginaAtual - 1) * itensPorPagina;
        const fim = inicio + itensPorPagina;

        linhas.forEach((linha, i) => {
            linha.style.display = (i >= inicio && i < fim) ? '' : 'none';
        });

        paginacao.innerHTML = `
            <span>Mostrando ${inicio + 1}-${Math.min(fim, total)} de ${total} registros</span>
            <div>
                ${paginaAtual > 1 ? `<button class="btn btn-sm btn-outline-secondary" onclick="irParaPagina(${paginaAtual - 1})">« Anterior</button>` : ''}
                <span class="mx-2">${paginaAtual}</span>
                ${paginaAtual < totalPaginas ? `<button class="btn btn-sm btn-outline-secondary" onclick="irParaPagina(${paginaAtual + 1})">Próxima »</button>` : ''}
            </div>
        `;
    }

    window.irParaPagina = function(p) {
        paginaAtual = p;
        renderizar();
    };

    if (total > itensPorPagina) {
        renderizar();
    }
}