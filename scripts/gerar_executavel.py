"""
Gera "Kaldi Servidor.exe" (painel de controle) na pasta do sistema.

    python scripts/gerar_executavel.py

O executável contém só o painel; o servidor roda com o Python instalado, a partir desta pasta,
para usar sempre o código e os dados atuais do sistema.
"""
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOME = 'Kaldi Servidor'
SEP = ';' if os.name == 'nt' else ':'


def main():
    os.chdir(RAIZ)
    comando = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--noconsole',
        '--name', NOME, '--icon', os.path.join(RAIZ, 'painel', 'kaldi.ico'),
        '--add-data', f"{os.path.join(RAIZ, 'painel', 'ui.html')}{SEP}painel",
        '--add-data', f"{os.path.join(RAIZ, 'painel', 'logo.svg')}{SEP}painel",
        '--paths', RAIZ,
        '--hidden-import', 'painel.supervisor',
        '--exclude-module', 'flask', '--exclude-module', 'pandas', '--exclude-module', 'reportlab',
        '--exclude-module', 'tkinter', '--exclude-module', 'numpy',
        '--distpath', os.path.join('build', 'dist'), '--workpath', os.path.join('build', 'trabalho'),
        '--specpath', 'build',
        os.path.join(RAIZ, 'painel', 'kaldi_painel.py'),
    ]
    print(' '.join(comando))
    subprocess.run(comando, check=True)
    origem = os.path.join(RAIZ, 'build', 'dist', f'{NOME}.exe')
    destino = os.path.join(RAIZ, f'{NOME}.exe')
    shutil.copy2(origem, destino)
    print(f'Pronto: {destino} ({os.path.getsize(destino) / 1048576:.1f} MB)')


if __name__ == '__main__':
    main()
