# English Studio

Um professor de inglês local para Windows. Importe um filme, escolha uma cena, escute e escreva o que entendeu. Receba uma nota, veja as diferenças e aprenda com explicações em português brasileiro.

## Começar neste computador

1. Abra **English Studio** pelo atalho da área de trabalho. Também pode executar `Iniciar.cmd`.
2. Clique em **Importar vídeo** ou arraste um arquivo para o player. Aguarde a preparação e a transcrição completa.
3. Defina o início e o fim da cena no formato `02:00` e `03:00`. Para vídeos longos, use `01:02:30`. Cada exercício aceita até 3 minutos; 15 a 30 segundos costuma ser mais confortável.
4. Clique em **Reproduzir cena**. Ajuste a velocidade ou marque **Repetir**.
5. Digite o diálogo, grave pelo microfone ou envie um arquivo de áudio. Revise o texto reconhecido e clique em **Corrigir minha resposta**.
6. Consulte a comparação palavra por palavra e as explicações do professor. Ative legendas em inglês para ouvir novamente com a referência.
7. Experimente a aba **Tradução em português** e escreva sua interpretação em português brasileiro.

O aplicativo também abre em <http://127.0.0.1:8765>. É um aplicativo local com interface web: a janela usa Edge ou Chrome, e o servidor roda somente no próprio computador. Não é um serviço publicado na internet.

O vídeo `examples/Primeira-aula.mp4` é uma demonstração de 17 segundos com voz sintetizada localmente pelo Windows. Ele já foi importado durante a validação. As tentativas de teste foram removidas do histórico antes da entrega.

## Recursos

- Biblioteca local com processamento em segundo plano, progresso, cancelamento e nova tentativa.
- FFmpeg prepara uma versão H.264/AAC para reprodução. Prioriza uma faixa marcada como inglês; se não houver identificação, usa a primeira faixa de áudio. O arquivo de origem escolhido pelo usuário não é alterado.
- Whisper reconhece o áudio completo e salva cada fala com tempos por palavra.
- Seleção de cena, repetição, velocidade de 0,5× a 1,25× e legendas sincronizadas em inglês ou português.
- Ditado digitado, gravação de microfone e envio de áudio de até 25 MB / 3 minutos.
- Nota objetiva de ditado por distância de edição de palavras: trocas, omissões e palavras extras.
- Professor Ollama com acertos, correções passo a passo, gramática, ortografia, vocabulário, dica de escuta, tradução e variações regionais quando pertinentes.
- Avaliação semântica de tradução, aceitando diferentes formas corretas de expressar o mesmo significado em português brasileiro.
- Revisão manual da referência, busca no diálogo completo e estudo de uma fala a partir da transcrição.
- Tradução integral em segundo plano, com resultados salvos a cada lote e retomada das falas pendentes se houver uma falha.
- PDF completo em inglês, português brasileiro ou bilíngue, com horários e numeração de páginas.
- Histórico persistente dos últimos 100 exercícios exibidos. Os registros mais antigos continuam no banco.
- Interface adaptável a telas pequenas, navegação por teclado, estados de carregamento e mensagens de erro.

## Como a nota funciona

**Ditado:** `100 × max(0, 1 − (trocas + omissões + extras) / palavras da referência)`.

Ignora maiúsculas e pontuação e expande contrações comuns: “I'm” e “I am”, por exemplo. A ortografia das palavras conta na comparação. Pontuação, gramática e estilo são tratados separadamente pelo professor. As contrações ambíguas exigem contexto; a comparação não é uma prova formal de proficiência.

**Tradução:** estimativa do modelo local com os critérios de significado (70%), gramática (20%) e ortografia (10%). Não é uma comparação literal com uma única tradução. O modelo pode se equivocar e a nota pode variar entre execuções.

**Resposta em áudio:** transcreve a voz para texto e compara as palavras reconhecidas. **Não mede qualidade de pronúncia, sotaque ou fluência.** É possível corrigir o reconhecimento antes de avaliar.

## PDF e legendas traduzidas

Abra **Leve seu estudo com você**. O PDF em inglês fica disponível assim que a transcrição termina. Para português ou bilíngue, clique em **Traduzir filme completo** e espere a conclusão. O mesmo processo libera as legendas em português no player. O arquivo é salvo na pasta de downloads do navegador.

As traduções são geradas em pequenos lotes com contexto anterior. Filmes longos podem levar bastante tempo; o progresso fica salvo. Caso uma fala seja editada, sua tradução anterior é invalidada; execute a tradução completa novamente para atualizar as falas pendentes.

## IA local e configuração

Em **Configurações**, selecione um modelo **já instalado no Ollama**. A configuração inicial deste computador é `qwen3:8b`, que já estava disponível. Modelos cloud são excluídos e rejeitados pelo aplicativo. Não há chave de API nem cobrança por uso neste programa.

O Whisper inicial é `base.en`, já baixado para este projeto durante a instalação. Para maior precisão, escolha `small.en`, `medium.en` ou `large-v3`; a primeira execução de cada modelo requer internet para baixar seus pesos. Depois, o programa prioriza o cache local. Os arquivos de vídeo, áudio e as respostas não são enviados a serviços externos de IA.

O modo inicial usa **CPU / int8**, que evita dependências extras de GPU e permite que o Ollama use a NVIDIA. O modo CUDA do Whisper exige as bibliotecas compatíveis com CTranslate2, incluindo CUDA 12 e cuDNN 9; apenas ter uma placa NVIDIA não é suficiente. Se ocorrer erro CUDA, retorne a CPU e tente novamente. O modo CUDA não foi validado nesta entrega.

Se o professor estiver desligado, o ditado ainda pode calcular a nota. A avaliação de tradução, as explicações e a tradução integral precisam do Ollama ativo. O inicializador tenta iniciar seu serviço local automaticamente.

## Limites que merecem ser conhecidos

- A análise é **do áudio**. Não interpreta imagens, emoções visuais ou personagens, nem faz identificação de falantes.
- Whisper pode falhar com música alta, sobreposição de vozes, sotaques, silêncio ou áudio ruim. A referência automática não é um gabarito infalível; revise-a em **Diálogos do vídeo**.
- Ao editar uma fala, seus tempos por palavra deixam de ser confiáveis. Por isso, uma fala editada é incluída inteira se cruzar o trecho selecionado. Seus horários de início e fim são preservados.
- Não há suporte a DRM. Os formatos dependem do que FFmpeg consegue decodificar. Limite de importação: 20 GB por arquivo.
- O programa guarda uma cópia do original, uma versão para reprodução e áudio PCM. Reserve espaço adicional. Não remove automaticamente os vídeos importados.
- Interromper o servidor durante uma transcrição exige clicar em **Tentar novamente** depois de abrir. A transcrição reinicia; traduções já concluídas são reaproveitadas.
- Fechar a janela mantém o servidor em segundo plano, permitindo continuar processamentos. Não há processamento em nuvem.
- Os testes reais usaram um vídeo curto. Não foi feito um teste de resistência com um longa-metragem inteiro, nem validação com todos os codecs, microfones ou sotaques.
- Explicações e traduções geradas por IA podem conter imprecisões. Há verificações determinísticas para a nota de ditado, contagem de acertos, concordância básica e algumas diferenças regionais; isso não substitui revisão pedagógica do conteúdo gerado.

## Instalar em outra pasta ou computador

Requisitos: Windows, Python 3.11 ou superior, FFmpeg (`ffmpeg` e `ffprobe` no PATH), Ollama e ao menos um modelo local instalado. Recomenda-se memória suficiente para executar o modelo escolhido; modelos maiores exigem mais RAM/VRAM.

Execute na pasta do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File .\Instalar.ps1
```

Isso cria o ambiente Python, instala as bibliotecas e cria o atalho. O parâmetro de execução vale somente para esse processo; o script não muda a política global do Windows. A instalação de Python, FFmpeg e Ollama não é automatizada pelo script. No outro computador, selecione um modelo disponível em Configurações antes de usar o professor.

O arquivo `requirements-lock.txt` registra as versões exatas usadas na validação, inclusive as ferramentas de teste. Para reproduzir esse ambiente em Python 3.13/Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

## Dados e cópia de segurança

- `data/studio.db`: biblioteca, referências, traduções, preferências e histórico (SQLite).
- `data/media/`: cópias locais dos vídeos, versões para reprodução e áudios.
- `data/models/`: pesos do Whisper.
- `data/server.log`: log do servidor quando iniciado pelo atalho.

Feche o processo do servidor antes de copiar o banco SQLite. Faça backup da pasta `data` inteira para preservar os estudos. O ambiente `.venv` pode ser recriado; não precisa ser incluído no backup.

## Desenvolvimento e validação

Backend Python/FastAPI, SQLite, FFmpeg, faster-whisper/CTranslate2, Ollama via HTTP local e ReportLab. Frontend HTML/CSS/JavaScript sem CDN, fontes remotas ou dependências de build. O servidor escuta exclusivamente em `127.0.0.1`; operações de escrita exigem um cabeçalho local, e a interface usa CSP e escape de conteúdo dinâmico.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Com o servidor ativo, `scripts/smoke_browser.py` verifica interface desktop/mobile, configurações, histórico e erros de JavaScript usando o Edge instalado. `scripts/verify_real_flow.py` é uma validação de integração específica para o vídeo de demonstração: executa os modelos reais e acrescenta tentativas ao histórico. Não rode esse teste sobre uma biblioteca diferente sem adaptá-lo.

O PyAV está limitado à série anterior à 17: a versão 19 removeu um argumento ainda usado pelo faster-whisper 1.2.1. A combinação validada está registrada no lockfile.

Documentação técnica consultada: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) e [API local do Ollama](https://docs.ollama.com/api/generate).
