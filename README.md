# Controle de Notas Fiscais

Aplicativo desktop em Python (Tkinter) para acompanhar notas fiscais em PDF:
cadastro a partir do PDF, status (EMITIDA / EM ROTA / CONCLUIDA), anexo de
canhoto, pendências automáticas e alerta ao abrir o programa.

## 1. Instalação

Requer Python 3.9+ (Tkinter já vem incluso no instalador padrão do Python
no Windows).

```bash
pip install -r requirements.txt
```

## 2. Executar

```bash
python main.py
```

Na primeira execução o programa vai pedir para você **escolher o diretório
principal** — a pasta onde ficam os PDFs das notas, os canhotos e o arquivo
de índice (`notas_fiscais.json`). Esse caminho fica salvo no seu usuário e
pode ser trocado a qualquer momento pelo botão **"Configurar diretório"**.
Quando vocês migrarem para o servidor, basta apontar esse mesmo botão para o
caminho de rede (ex.: `\\SERVIDOR\NotasFiscais`).

## 3. Como funciona

- **Adicionar nota**: clique em "+ Nova Nota Fiscal (PDF)", selecione o PDF
  no seu computador. O programa tenta ler automaticamente Nome do Cliente,
  Código do Cliente, Data de Emissão, Número da NF e Transportadora, e
  mostra uma tela para você conferir/corrigir os campos antes de salvar. O
  PDF é copiado para o diretório principal e a nota entra na lista com
  status **EMITIDA**.
- **Ver/baixar/imprimir**: dê duplo clique em uma nota da lista para abrir o
  visualizador, baixar uma cópia ou imprimir o PDF.
- **Alterar status**: no mesmo painel de detalhes, escolha EMITIDA, EM ROTA
  ou CONCLUIDA. Para marcar como **CONCLUIDA** é obrigatório anexar antes o
  **canhoto de entrega** (foto ou PDF) — o programa guarda o canhoto junto
  com a nota, no mesmo diretório principal.
- **Pesquisar / filtrar / ordenar**: campo de busca (procura em cliente,
  código, número da NF, transportadora e emissão), filtro por status e
  ordenação por mais recentes/mais antigas.
- **Pendências ("ATRASADAS")**: qualquer nota que fique mais de 3 dias
  parada em EMITIDA aparece automaticamente nessa lista.
- **Alerta ao abrir**: se houver pendências, um aviso aparece ao iniciar o
  programa. Você pode marcar quais notas não quer ver de novo nesse alerta
  ("Aplicar e fechar") ou apenas fechar o aviso (ele volta a aparecer na
  próxima abertura, até a nota mudar de status ou você dispensá-la).

## 4. Sobre a leitura automática dos PDFs

A extração foi ajustada especificamente para o modelo de DANFE usado (o
mesmo formato do exemplo da FORMATEC COMERCIAL LTDA / BORRACHAS VIPAL
enviado), lendo:
- **Cliente**: primeira razão social do destinatário
- **Código do Cliente**: número após "Cliente:" em Dados Adicionais
- **Emissão**: data que aparece na mesma linha do cliente
- **Número da NF**: valor após "Nº."
- **Transportadora**: nome na seção Transportador/Volumes Transportados

Se algum PDF vier de um layout diferente desse padrão, o programa ainda
tenta um conjunto de padrões genéricos como reserva, mas o mais confiável
continua sendo conferir os campos na tela de confirmação antes de salvar
— por isso ela sempre aparece, mesmo quando a leitura automática funciona
bem. Se aparecer um layout novo que a extração não pegue direito, me
mande um exemplo desse PDF que eu ajusto os padrões de novo.

## 5. Estrutura dos arquivos

```
nf_app/
├── main.py         # ponto de entrada (python main.py)
├── app.py          # interface gráfica (Tkinter) e regras de tela
├── storage.py       # leitura/gravação do índice de notas (JSON)
├── pdf_utils.py      # extração dos campos do PDF
├── config.py         # guarda o diretório principal escolhido
└── requirements.txt
```

Dentro do **diretório principal** (a pasta que você escolhe no programa)
ficam:
```
notas_fiscais.json          # índice com todas as notas e status
NF_<numero>_<cliente>.pdf   # PDFs das notas
CANHOTO_<numero>_<cliente>.<ext>  # canhotos anexados
```

## 6. Gerando um instalável para distribuir aos operadores (.exe)

Os operadores não precisam instalar Python nem rodar `pip install`: dá para
empacotar tudo em um único `.exe` do Windows usando o **PyInstaller**, que
já inclui o `pdfplumber` dentro do executável.

**Importante:** o PyInstaller empacota para o sistema operacional em que ele
roda — ele não faz "cross-compile". Ou seja, para gerar um `.exe` do
Windows, você precisa rodar o processo abaixo **em um computador Windows**
(pode ser o seu, não precisa ser o do operador final).

Passo a passo (no Windows, com Python instalado, dentro da pasta do
projeto):

```bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name "ControleNotasFiscais" --collect-all pdfplumber main.py
```

Ou simplesmente dê duplo clique no `build.bat` incluído no projeto — ele
faz os três passos acima automaticamente.

O executável final fica em `dist\ControleNotasFiscais.exe`. Basta copiar
esse único arquivo para o computador de cada operador (não precisa levar o
Python nem os outros arquivos `.py`) — só o `.exe` funciona sozinho. Na
primeira execução, o programa ainda vai pedir para escolher o diretório
principal, igual descrito na seção 2.

Dicas:
- `--windowed` evita que uma janela de terminal preta fique aberta atrás do
  programa.
- `--collect-all pdfplumber` garante que todas as dependências internas do
  pdfplumber (como o `pdfminer.six` e o `Pillow`) sejam incluídas — sem essa
  opção o PyInstaller às vezes esquece algum submódulo e o `.exe` dá erro
  ao tentar ler um PDF.
- Se antivírus/SmartScreen reclamar do `.exe` na primeira vez (comum com
  executáveis não assinados digitalmente), é só permitir a execução; para
  eliminar esse aviso de vez seria necessário assinar o executável com um
  certificado de assinatura de código, o que é opcional.
- Sempre que você alterar o código, repita o `pyinstaller ...` (ou rode o
  `build.bat` de novo) para gerar uma nova versão do `.exe`.

## 7. Observações e próximos passos sugeridos

- **Impressão**: no Windows a impressão é feita direto na impressora padrão.
  No macOS/Linux o PDF é aberto no visualizador padrão para você imprimir
  por lá (limitação do sistema operacional, não do programa).
- **Uso em rede/servidor**: como o índice é um único arquivo JSON, se vários
  operadores forem usar o programa **ao mesmo tempo** apontando para a
  mesma pasta de rede, recomendo migrarmos futuramente para um banco de
  dados (SQLite ou um servidor) para evitar conflito de gravação simultânea.
  Para uso com poucas pessoas alternando o uso, o JSON funciona bem.
- Posso adicionar depois, se for útil: histórico de alterações de status,
  exportar a lista para Excel, campos adicionais (valor da nota, pedido de
  venda), ou múltiplos usuários com login.
