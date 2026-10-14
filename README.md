# Bmpic

Aplicativo desktop para converter imagens JPG e PNG em BMP de 24 bits, mantendo as dimensões originais. PNGs com transparência são compostos sobre fundo preto.

## Requisitos

- Windows 10 ou mais recente
- Python 3.10 ou mais recente, com Tkinter instalado

## Instalação e execução

Abra o PowerShell nesta pasta e execute:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Para usar o app, clique na área tracejada ou arraste um arquivo JPG/PNG para ela. Clique em **Converter** e depois em **Salvar** para escolher onde salvar o BMP. Cancelar a janela de salvar descarta a conversão e mantém a imagem selecionada.

## Gerar executável de arquivo único

Instale as dependências de build e gere o executável independente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name Bmpic --icon assets\icon.ico --add-data "assets;assets" --collect-all customtkinter app.py
```

O único arquivo para distribuir é `dist\Bmpic.exe`. Ele inclui o Python, as bibliotecas e os assets do app; foi gerado para Windows 10 ou mais recente em arquitetura x64 e não exige Python instalado na máquina de destino.

## Releases automáticas no GitHub

Cada push para a branch `main` inicia o build no Windows e publica uma Release com `Bmpic.exe` para baixar. O arquivo fica na seção **Releases** do repositório. Commits locais só iniciam esse fluxo depois de enviados ao GitHub (`git push`).

O BMP gerado mantém o tamanho da imagem de origem. Alguns firmwares exigem dimensões ou profundidade de cor específicas; confira os requisitos do seu console antes de usar a imagem como boot screen.
