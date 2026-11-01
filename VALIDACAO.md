# Validação da entrega

Validação realizada em 1 de novembro de 2026, no Windows deste computador, com Python 3.13, FFmpeg, Whisper `base.en` em CPU e Ollama `qwen3:8b`. As versões instaladas estão em `requirements-lock.txt`.

## Resultado

- **23 testes automatizados aprovados**: alinhamento e nota de ditado, contrações, seleção por palavra, trechos inválidos/silenciosos, persistência, professor indisponível, invalidação de traduções ao editar, proteção de requisições, escape de legendas, envio de vídeo por intervalos, rejeição de modelo cloud, cálculo dos pontos de tradução, diferenças regionais, remoção de correções repetidas, acertos baseados no texto e concordância básica.
- **Transcrição real**: vídeo de demonstração de 17 segundos importado, convertido e transcrito em 3 falas com tempos por palavra.
- **Player real no Edge**: reprodução H.264/AAC, parada ao final do intervalo selecionado e legendas em inglês e português.
- **Professor local real**: ditado com três diferenças recebeu 78,6%; tradução correta recebeu 100%; tradução gramaticalmente válida mas sem relação com a fala recebeu 30% (zero em significado, pontos de gramática e ortografia preservados).
- **Áudio real**: envio de WAV reconhecido pelo Whisper e devolvido como resposta editável. Gravação testada com MediaRecorder e um microfone sintético do navegador alimentado pelo áudio de demonstração; não foi usado o microfone físico.
- **Tradução integral**: trabalho em segundo plano concluído, falas traduzidas persistidas e legendas em português disponibilizadas.
- **PDF**: inglês, português e bilíngue gerados, texto extraído para conferência e download pelo navegador testado. PDF bilíngue renderizado e inspecionado visualmente. Teste adicional com 220 falas confirmou múltiplas páginas e preservação do último diálogo nos dois idiomas.
- **Interface**: desktop 1440 px e celular 390 px verificados, sem transbordamento horizontal ou erros de JavaScript. Configurações, histórico e retorno ao estudo verificados.
- **Instalação**: ambiente virtual instalado, dependências consistentes, modelo Whisper baixado e atalho `English Studio.lnk` criado na área de trabalho.

## Limitações da validação

Não foi transcrito um filme de longa duração; a estrutura suporta o processamento sequencial completo, mas tempo, consumo de espaço e qualidade variam por arquivo. CUDA, todos os codecs e faixas de áudio possíveis, microfone físico e precisão em todos os sotaques não foram validados. As explicações e traduções de um modelo local não são infalíveis.

Os registros de exercícios criados pelos testes foram removidos do histórico antes da entrega. O vídeo de demonstração e sua transcrição/tradução permanecem disponíveis para começar a usar.
