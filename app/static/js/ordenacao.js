function habilitarOrdenacao(tabelaId) {
    const tabela = document.getElementById(tabelaId);
    if (!tabela) return;

    const thead = tabela.querySelector('thead');
    if (!thead) return;

    const ths = thead.querySelectorAll('th');
    ths.forEach((th, colIndex) => {
        if (th.classList.contains('no-sort')) return;
        th.style.cursor = 'pointer';
        th.addEventListener('click', function() {
            const tbody = tabela.querySelector('tbody');
            const linhas = Array.from(tbody.querySelectorAll('tr'));
            let ascending = !th.classList.contains('sort-asc');

            ths.forEach(t => { t.classList.remove('sort-asc', 'sort-desc'); });
            th.classList.add(ascending ? 'sort-asc' : 'sort-desc');

            linhas.sort((a, b) => {
                const aText = a.cells[colIndex] ? a.cells[colIndex].textContent.trim() : '';
                const bText = b.cells[colIndex] ? b.cells[colIndex].textContent.trim() : '';
                const aNum = parseFloat(aText.replace(/[^\d,-]/g, '').replace(',', '.'));
                const bNum = parseFloat(bText.replace(/[^\d,-]/g, '').replace(',', '.'));
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return ascending ? aNum - bNum : bNum - aNum;
                }
                return ascending ? aText.localeCompare(bText) : bText.localeCompare(aText);
            });

            linhas.forEach(linha => tbody.appendChild(linha));
        });
    });
}