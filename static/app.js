'use strict';
const $ = id => document.getElementById(id);
const state = {movies: [], movie: null, mode: 'dictation', busy: false, uploading: false, recorder: null, recordTimer: null, history: [], jobs: [], generation: 0};
const escapeHTML = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let toastTimer;
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 8500); }
async function api(path, options = {}) {
  const headers = {'X-Study-App': 'english-studio', ...options.headers};
  if (options.body && !(options.body instanceof FormData)) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); }
  let response;
  try { response = await fetch('/api' + path, {...options, headers}); }
  catch { throw new Error('Não foi possível acessar o estúdio. Abra novamente pelo atalho da área de trabalho.'); }
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === 'string' ? data.detail : 'Confira os campos e tente novamente.'); }
  return response.json();
}
function safely(fn) { return async (...args) => { try { await fn(...args); } catch (e) { toast(e.message); } }; }
function formatTime(value, precise = false) {
  const raw = Math.max(0, Number(value) || 0), ticks = Math.round(raw * 100), s = precise ? Math.floor(ticks/100) : Math.floor(raw), h = Math.floor(s/3600), m = Math.floor(s%3600/60), seconds = s%60;
  const base = (h ? String(h).padStart(2,'0') + ':' : '') + String(m).padStart(2,'0') + ':' + String(seconds).padStart(2,'0');
  return precise && ticks%100 ? base + '.' + String(ticks%100).padStart(2,'0') : base;
}
function parseTime(text) {
  if (!/^\d+(?::\d{1,2}){0,2}(?:[.,]\d{1,3})?$/.test(text.trim())) throw new Error('Use minutos:segundos, por exemplo 02:00, ou horas:minutos:segundos.');
  const parts = text.replace(',','.').split(':').map(Number);
  if (parts.slice(1).some(v => v >= 60)) throw new Error('Minutos e segundos após dois-pontos devem ser menores que 60.');
  return parts.reduce((sum, part) => sum*60+part, 0);
}
function scene() {
  if (!state.movie || state.movie.status !== 'ready') throw new Error('Importe um vídeo e aguarde a transcrição.');
  const start = parseTime($('scene-start').value), end = parseTime($('scene-end').value);
  if (end <= start) throw new Error('O fim da cena deve ser posterior ao início.');
  if (end > state.movie.duration + .25) throw new Error('A cena termina depois do vídeo. Ajuste o tempo final.');
  if (end-start > 180) throw new Error('Escolha uma cena de até 3 minutos.');
  return {start, end};
}
function invalidate() { state.generation++; $('result').hidden = true; $('reference-box').hidden = true; }
function updateScene() { invalidate(); try { const range = scene(); $('scene-duration').textContent = `${Math.round((range.end-range.start)*10)/10} segundos`; } catch { $('scene-duration').textContent = 'Até 3 minutos'; } }
function updateControls() {
  const ready = state.movie?.status === 'ready';
  for (const id of ['play-scene','set-start','open-transcript','open-export','reveal']) $(id).disabled = !ready;
  $('evaluate').disabled = !ready || state.busy || !!state.recorder;
  $('record').disabled = !ready || state.busy || state.mode !== 'dictation';
  $('upload-audio').disabled = !ready || state.busy || !!state.recorder;
  $('mode-dictation').disabled = state.busy || !!state.recorder;
  $('mode-translation').disabled = state.busy || !!state.recorder;
  for (const id of ['import-top','import-side','import-stage','add-library']) $(id).disabled = state.uploading;
}
function renderLibrary() {
  const selector = $('mobile-library'), selected = state.movie?.id || '';
  selector.innerHTML = '<option value="">Escolha um vídeo</option>' + state.movies.map(m => `<option value="${m.id}">${escapeHTML(m.title)}</option>`).join('');
  selector.value = selected;
  $('library').innerHTML = state.movies.length ? state.movies.map(m => `<button class="library-item ${state.movie?.id === m.id ? 'active' : ''}" data-movie="${m.id}" title="${escapeHTML(m.title)}"><span>▤</span><span>${escapeHTML(m.title)}<small>${m.status === 'ready' ? formatTime(m.duration) + ' · pronto para estudar' : m.status === 'error' ? 'Requer atenção' : 'Preparando · ' + Math.floor(m.progress) + '%'}</small></span></button>`).join('') : '<p class="library-empty">Suas próximas histórias<br>começam aqui.</p>';
}
async function selectMovie(id) {
  if (state.recorder) { toast('Finalize a gravação antes de trocar de vídeo.'); return; }
  $('player').pause(); invalidate();
  const movie = await api('/movies/' + id);
  state.movie = movie;
  localStorage.setItem('english-studio-movie', id);
  $('answer').value = ''; updateCount();
  $('scene-start').value = '00:00'; $('scene-end').value = formatTime(Math.min(30, movie.duration || 30), true);
  $('subtitles').value = 'off';
  renderMovie(); renderLibrary(); showView('study');
}
function renderMovie() {
  const movie = state.movie;
  if (!movie) return;
  const ready = movie.status === 'ready';
  $('movie-title').textContent = movie.title;
  $('movie-length').textContent = movie.duration ? formatTime(movie.duration) : 'Preparando';
  $('video-empty').hidden = true; $('player').hidden = !ready; $('processing').hidden = ready;
  if (ready) {
    const url = '/api/movies/' + movie.id + '/video';
    if ($('player').getAttribute('src') !== url) { $('player').replaceChildren(); $('player').src = url; $('player').load(); }
  } else {
    $('processing-title').textContent = movie.status === 'error' ? 'Vamos tentar de novo?' : 'Preparando sua história';
    $('processing-text').textContent = movie.message;
    $('processing-progress').value = movie.progress;
    $('processing-progress').hidden = movie.status === 'error';
    $('processing').querySelector('.spinner').hidden = movie.status === 'error';
    $('retry').hidden = movie.status !== 'error'; $('cancel').hidden = movie.status === 'error';
  }
  updateControls();
}
async function refresh() {
  const [movies, jobs] = await Promise.all([api('/movies'), api('/jobs')]);
  state.movies = movies; state.jobs = jobs; renderLibrary();
  if (state.movie) {
    const latest = movies.find(m => m.id === state.movie.id);
    if (latest && state.movie.status !== 'ready') {
      if (latest.status === 'ready') {
        state.movie = await api('/movies/' + latest.id);
        $('scene-end').value = formatTime(Math.min(30, state.movie.duration), true);
        toast('Seu vídeo está pronto. Escolha uma cena e comece!');
      } else state.movie = {...state.movie, ...latest};
      renderMovie();
    }
  }
  const activeJob = jobs.find(j => ['queued','processing'].includes(j.status));
  $('job-banner').hidden = !activeJob;
  if (activeJob) $('job-banner').textContent = `Tradução em andamento · ${activeJob.progress}% · ${activeJob.message}`;
  const currentJob = jobs.find(j => j.movie_id === state.movie?.id);
  $('translation-status').textContent = currentJob ? `${currentJob.progress}% · ${currentJob.message}` : '';
  $('translate-all').disabled = !!currentJob && ['queued','processing'].includes(currentJob.status);
}
async function upload(file) {
  if (!file || state.uploading) return;
  if (file.size > 20*1024**3) throw new Error('O limite é 20 GB por vídeo.');
  state.uploading = true; updateControls();
  $('job-banner').hidden = false; $('job-banner').textContent = 'Copiando vídeo para sua biblioteca…';
  const form = new FormData(); form.append('file', file);
  try {
    const movie = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); xhr.open('POST','/api/movies'); xhr.setRequestHeader('X-Study-App','english-studio');
      xhr.upload.onprogress = event => { if (event.lengthComputable) $('job-banner').textContent = `Copiando vídeo para sua biblioteca · ${Math.round(event.loaded/event.total*100)}%`; };
      xhr.onload = () => { let data; try { data = JSON.parse(xhr.responseText); } catch { reject(new Error('O envio falhou. Verifique se o aplicativo está aberto.')); return; } if (xhr.status >= 200 && xhr.status < 300) resolve(data); else reject(new Error(data.detail || 'Não foi possível importar.')); };
      xhr.onerror = () => reject(new Error('Falha ao importar o vídeo. Verifique se o aplicativo está aberto.'));
      xhr.send(form);
    });
    await refresh(); await selectMovie(movie.id);
  } finally { state.uploading = false; $('job-banner').hidden = true; $('video-file').value = ''; updateControls(); }
}
function showView(view) {
  $('study-view').hidden = view !== 'study'; $('history-view').hidden = view !== 'history';
  $('nav-study').classList.toggle('active',view==='study'); $('nav-history').classList.toggle('active',view==='history');
  $('page-label').textContent = view==='study' ? 'Estúdio de estudo' : 'Meu progresso';
}
function setMode(mode) {
  if (state.mode === mode) return;
  state.mode = mode; invalidate(); $('answer').value = ''; updateCount();
  const dictation = mode === 'dictation';
  $('mode-dictation').classList.toggle('active', dictation); $('mode-dictation').setAttribute('aria-selected', String(dictation));
  $('mode-translation').classList.toggle('active', !dictation); $('mode-translation').setAttribute('aria-selected', String(!dictation));
  $('answer-label').textContent = dictation ? 'Escreva o diálogo em inglês' : 'Traduza o diálogo para português brasileiro';
  $('answer').placeholder = dictation ? 'I think they said…' : 'O que essa cena quer dizer em português?';
  $('voice-row').hidden = !dictation; $('voice-note').hidden = true;
  $('explain').disabled = !dictation; if (!dictation) $('explain').checked = true;
  updateControls();
}
function updateCount() { $('char-count').textContent = `${$('answer').value.length} / 5000`; }
async function playScene() { const range = scene(); $('player').currentTime = range.start; await $('player').play(); }
function enforceScene() {
  if ($('player').paused || !state.movie) return;
  try {
    const range = scene();
    if ($('player').currentTime >= range.end - .025) {
      if ($('loop').checked) $('player').currentTime = range.start;
      else { $('player').pause(); $('player').currentTime = range.end; }
    } else if ($('player').currentTime < range.start - .2) $('player').currentTime = range.start;
  } catch { $('player').pause(); }
}
async function subtitles() {
  const lang = $('subtitles').value;
  if (!state.movie || state.movie.status !== 'ready') { $('subtitles').value = 'off'; return; }
  for (const track of [...$('player').textTracks]) track.mode = 'disabled';
  $('player').querySelectorAll('track').forEach(t => t.remove());
  if (lang === 'off') return;
  const url = `/api/movies/${state.movie.id}/subtitles?language=${lang}&v=${Date.now()}`;
  const check = await fetch(url);
  if (!check.ok) { $('subtitles').value='off'; throw new Error((await check.json()).detail); }
  const track = document.createElement('track'); track.kind='subtitles'; track.label=lang==='en'?'Inglês':'Português'; track.srclang=lang; track.src=url; track.default=true;
  $('player').appendChild(track); track.addEventListener('load', () => track.track.mode='showing'); track.track.mode='showing';
}
function lessonBlock(title, content, wide = false) { return `<div class="lesson-block ${wide ? 'wide' : ''}"><h3>${title}</h3>${content}</div>`; }
function renderResult(result) {
  let html = `<div class="result-top"><div class="score">${Number(result.score).toLocaleString('pt-BR')}<small>%</small></div><div><span class="tiny-label">${result.mode==='dictation'?'ACERTO DAS PALAVRAS':'AVALIAÇÃO DA TRADUÇÃO'}</span><h2>${result.score >= 95 ? 'Muito bem. Continue assim!' : result.score >= 65 ? 'Você está no caminho.' : 'Cada tentativa ensina algo novo.'}</h2><p>${escapeHTML(result.method)}</p><p>Referência automática: revise possíveis erros de reconhecimento antes de interpretar a nota.</p></div></div>`;
  if (result.alignment) {
    html += '<h2>Palavra por palavra</h2><p class="legend">Verde: acerto · Laranja: trocar ou incluir · Vermelho: palavra extra. Exibição normalizada, sem pontuação.</p><div class="alignment">';
    html += result.alignment.map(w => `<span class="word ${w.kind}" title="${{correct:'Correta',replace:'Troca',missing:'Faltou',extra:'Extra'}[w.kind]}">${w.kind==='replace'?`<s>${escapeHTML(w.actual)}</s> → `:w.kind==='missing'?'+ ':w.kind==='extra'?'− ':''}${escapeHTML(w.expected || w.actual)}</span>`).join('') + '</div>';
  }
  html += `<div class="reference-box"><span class="tiny-label">DIÁLOGO DE REFERÊNCIA</span><p>${escapeHTML(result.reference)}</p></div>`;
  if (result.teacher_error) html += `<div class="notice">A comparação foi salva. A explicação não ficou disponível: ${escapeHTML(result.teacher_error)}</div>`;
  const l = result.lesson;
  if (l) {
    html += '<div class="lesson-grid">';
    html += lessonBlock('✦ Seu professor explica', `<p>${escapeHTML(l.resumo)}</p>`, true);
    if (result.mode === 'translation' && l.pontos_significado != null) html += lessonBlock('Como sua tradução foi avaliada', `<p>Significado: <strong>${Number(l.pontos_significado)} / 70</strong><br>Gramática: <strong>${Number(l.pontos_gramatica)} / 20</strong><br>Ortografia: <strong>${Number(l.pontos_ortografia)} / 10</strong></p>`);
    if (l.acertos.length) html += lessonBlock('O que você acertou', '<ul>'+l.acertos.map(x=>`<li>${escapeHTML(x)}</li>`).join('')+'</ul>');
    html += lessonBlock('Ajustes, passo a passo', l.correcoes.length ? l.correcoes.map(c=>`<div class="correction"><strong>${escapeHTML(c.trecho)} → ${escapeHTML(c.correcao)}</strong><p>${escapeHTML(c.explicacao)}</p></div>`).join('') : '<p>Nenhuma correção específica apontada pelo professor.</p>');
    if (l.vocabulario.length) html += lessonBlock('Palavras para levar com você', l.vocabulario.map(v=>`<p><strong>${escapeHTML(v.palavra)}</strong> · ${escapeHTML(v.significado)}<br><em>${escapeHTML(v.exemplo)}</em></p>`).join(''));
    html += lessonBlock('Escute de um jeito novo', `<p>${escapeHTML(l.dica_de_escuta)}</p>`);
    if (l.variacoes_regionais.length) html += lessonBlock('Inglês americano e britânico', l.variacoes_regionais.map(v=>`<p>${escapeHTML(v)}</p>`).join(''));
    html += lessonBlock('Em português brasileiro', `<p>${escapeHTML(l.traducao_referencia)}</p>`);
    html += lessonBlock('Uma forma de escrever', `<p>${escapeHTML(l.resposta_melhorada)}</p>`);
    html += '</div>';
  }
  $('result').innerHTML = html; $('result').hidden = false;
  $('result').scrollIntoView({behavior:'smooth',block:'start'});
}
async function evaluate() {
  const range = scene(), answer = $('answer').value.trim();
  if (!answer) throw new Error('Escreva ou grave sua resposta primeiro.');
  const generation = state.generation, movieId = state.movie.id;
  state.busy = true; updateControls(); $('evaluate').textContent = $('explain').checked ? 'O professor está lendo…' : 'Comparando palavras…';
  try { const result = await api(`/movies/${movieId}/evaluate`, {method:'POST',body:{...range,answer,mode:state.mode,explain:$('explain').checked}}); if (generation === state.generation) renderResult(result); else toast('A correção do trecho anterior foi salva em Meu progresso.'); }
  finally { state.busy = false; updateControls(); $('evaluate').innerHTML = 'Corrigir minha resposta <span>→</span>'; }
}
async function recognize(file) {
  if (file.size > 25*1024**2) throw new Error('Envie um áudio de até 25 MB.');
  const generation = state.generation;
  state.busy = true; updateControls(); $('voice-note').hidden = false; $('voice-note').textContent = 'Reconhecendo sua voz localmente…';
  try {
    const form = new FormData(); form.append('file',file, file.name || 'resposta.webm');
    const result = await api('/audio/transcribe',{method:'POST',body:form});
    if (generation !== state.generation) { toast('A cena mudou durante o reconhecimento. Envie o áudio novamente para esta cena.'); return; }
    $('answer').value = result.text; updateCount(); invalidate(); $('voice-note').textContent = result.note;
  } catch(e) { $('voice-note').textContent='O áudio não pôde ser reconhecido. Você pode enviar outro arquivo ou digitar.'; throw e; }
  finally { state.busy=false; updateControls(); $('audio-file').value=''; }
}
async function record() {
  if (state.recorder) { state.recorder.stop(); return; }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Este navegador não permite gravar. Use Enviar áudio ou abra no Edge/Chrome.');
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({audio:true}); }
  catch { throw new Error('Não foi possível abrir o microfone. Confira a permissão do navegador e do Windows.'); }
  const chunks = [];
  try { state.recorder = new MediaRecorder(stream); }
  catch (error) { stream.getTracks().forEach(t=>t.stop()); throw error; }
  const recorder = state.recorder;
  recorder.ondataavailable = e => { if(e.data.size) chunks.push(e.data); };
  recorder.onstop = safely(async () => {
    clearTimeout(state.recordTimer); stream.getTracks().forEach(t=>t.stop()); state.recorder=null;
    $('record').textContent='♩ Gravar resposta'; $('record').classList.remove('recording'); updateControls();
    await recognize(new Blob(chunks,{type:recorder.mimeType}));
  });
  recorder.start(); $('record').textContent='Parar gravação'; $('record').classList.add('recording');
  $('voice-note').hidden=false; $('voice-note').textContent='Gravando… até 3 minutos. Ao terminar, revise o texto reconhecido antes de corrigir.';
  state.recordTimer=setTimeout(()=>{if(recorder.state==='recording') recorder.stop();},180000); updateControls();
}
async function openSettings() {
  const config = await api('/settings');
  $('model-select').innerHTML = config.models.length ? config.models.map(m=>`<option value="${escapeHTML(m)}">${escapeHTML(m)}</option>`).join('') : '<option value="">Nenhum modelo local disponível</option>';
  $('model-select').value = config.models.includes(config.ollama_model) ? config.ollama_model : config.models[0] || '';
  $('whisper-select').value=config.whisper_model; $('device-select').value=config.device;
  $('settings-status').textContent = `${config.ffmpeg?'FFmpeg disponível.':'FFmpeg não encontrado no PATH.'} ${config.ollama_error || 'Ollama disponível.'} Seus arquivos: ${config.data_path}`;
  $('settings-dialog').showModal();
}
async function updateConnection() {
  const config = await api('/settings');
  const ready = !config.ollama_error && config.models.includes(config.ollama_model);
  $('connection').innerHTML = '<span class="status-dot"></span>' + (ready ? 'IA local conectada' : 'Configure sua IA local');
  $('connection').title = ready ? config.ollama_model : config.ollama_error || 'Selecione um modelo nas configurações';
}
async function openTranscript() {
  state.movie = await api('/movies/'+state.movie.id); $('transcript-search').value=''; renderTranscript(); $('transcript-dialog').showModal();
}
function renderTranscript() {
  const query = $('transcript-search').value.toLowerCase();
  const rows = state.movie.segments.filter(s=>s.text.toLowerCase().includes(query) || (s.translation||'').toLowerCase().includes(query));
  $('transcript-list').innerHTML = rows.map(s=>`<div class="transcript-row" data-index="${s.idx}"><div><button class="text-button jump-segment">▶ ${formatTime(s.start)}</button><small class="muted small"> — ${formatTime(s.end)}</small></div><div><textarea aria-label="Editar fala ${s.idx+1}" maxlength="5000">${escapeHTML(s.text)}</textarea>${s.translation?`<p class="muted">${escapeHTML(s.translation)}</p>`:''}<div class="transcript-controls"><button class="text-button save-segment">Salvar revisão</button><button class="text-button use-segment">Estudar esta fala</button></div></div></div>`).join('') || '<p class="muted">Nenhuma fala encontrada.</p>';
}
async function transcriptClick(event) {
  const row = event.target.closest('.transcript-row'); if (!row) return;
  const segment = state.movie.segments.find(s=>s.idx===Number(row.dataset.index));
  if (event.target.closest('.save-segment')) {
    const button=event.target; button.disabled=true;
    try { await api(`/movies/${state.movie.id}/segments/${segment.idx}`,{method:'PUT',body:{text:row.querySelector('textarea').value}}); state.movie=await api('/movies/'+state.movie.id); invalidate(); renderTranscript(); await subtitles(); toast('Referência corrigida. A tradução dessa fala será refeita na próxima tradução completa.'); } finally { button.disabled=false; }
  } else if (event.target.closest('.use-segment') || event.target.closest('.jump-segment')) {
    $('scene-start').value=formatTime(segment.start,true); $('scene-end').value=formatTime(Math.min(state.movie.duration,segment.end),true); updateScene(); $('transcript-dialog').close(); await playScene();
  }
}
async function downloadPDF() {
  const button=$('download-pdf');button.disabled=true;button.textContent='Preparando seu PDF…';
  try {
    const response = await fetch(`/api/movies/${state.movie.id}/export?language=${$('export-language').value}`);
    if(!response.ok) throw new Error((await response.json()).detail);
    const blob=await response.blob(), url=URL.createObjectURL(blob), a=document.createElement('a');
    a.href=url;a.download=`${state.movie.title.replace(/[<>:"/\\|?*]/g,'_')}-${$('export-language').value}.pdf`;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
    toast('PDF pronto. Confira a pasta de downloads.');
  } finally { button.disabled=false;button.textContent='↓ Baixar PDF completo'; }
}
async function showHistory() {
  state.history=await api('/history');showView('history');
  const rows=state.history, average=rows.length?Math.round(rows.reduce((n,r)=>n+r.result.score,0)/rows.length):0;
  $('history-stats').innerHTML=`<div class="stat"><strong>${rows.length}</strong><span>Exercícios recentes</span></div><div class="stat"><strong>${rows.length?average+'%':'—'}</strong><span>Média dos exercícios exibidos</span></div><div class="stat"><strong>${new Set(rows.map(r=>r.movie_id)).size}</strong><span>Vídeos estudados</span></div>`;
  $('history-list').innerHTML=rows.length?rows.map(r=>`<article class="history-row"><div><h3>${escapeHTML(r.title)}</h3><p>${r.mode==='dictation'?'Ditado':'Tradução'} · ${formatTime(r.start)} — ${formatTime(r.end)} · ${new Date(r.created_at.replace(' ','T')+'Z').toLocaleString('pt-BR')}</p></div><button class="text-button review-attempt" data-id="${r.id}">Rever correção ↗</button><span class="score">${Number(r.result.score).toLocaleString('pt-BR')}%</span></article>`).join(''):'<div class="card empty-history"><h2>Seu primeiro passo está logo ali.</h2><p>Importe um vídeo e corrija uma cena. Seus exercícios aparecerão aqui.</p></div>';
}
for(const id of ['import-top','import-side','import-stage','add-library']) $(id).addEventListener('click',()=>$('video-file').click());
$('video-file').addEventListener('change',safely(e=>upload(e.target.files[0])));
$('library').addEventListener('click',safely(e=>{const b=e.target.closest('[data-movie]');if(b)return selectMovie(b.dataset.movie);}));
$('mobile-library').addEventListener('change',safely(e=>e.target.value && selectMovie(e.target.value)));
$('dropzone').addEventListener('dragover',e=>{e.preventDefault();$('dropzone').classList.add('dragover');});
$('dropzone').addEventListener('dragleave',()=>$('dropzone').classList.remove('dragover'));
$('dropzone').addEventListener('drop',safely(async e=>{e.preventDefault();$('dropzone').classList.remove('dragover');await upload(e.dataTransfer.files[0]);}));
$('nav-study').addEventListener('click',()=>showView('study'));$('nav-history').addEventListener('click',safely(showHistory));
$('mode-dictation').addEventListener('click',()=>setMode('dictation'));$('mode-translation').addEventListener('click',()=>setMode('translation'));
$('answer').addEventListener('input',()=>{updateCount();invalidate();});
$('scene-start').addEventListener('change',updateScene);$('scene-end').addEventListener('change',updateScene);
$('play-scene').addEventListener('click',safely(playScene));
$('set-start').addEventListener('click',()=>{const start=Math.floor($('player').currentTime);$('scene-start').value=formatTime(start);$('scene-end').value=formatTime(Math.min(start+30,state.movie.duration),true);updateScene();});
$('speed').addEventListener('change',()=>$('player').playbackRate=Number($('speed').value));
$('player').addEventListener('error',()=>{if(state.movie?.status==='ready')toast('O navegador não conseguiu reproduzir este vídeo. Tente abrir pelo Edge ou Chrome.');});
$('subtitles').addEventListener('change',safely(subtitles));
$('evaluate').addEventListener('click',safely(evaluate));
$('reveal').addEventListener('click',safely(async()=>{const range=scene();const data=await api(`/movies/${state.movie.id}/reference`,{method:'POST',body:range});$('reference-text').textContent=data.text;$('reference-box').hidden=false;}));
$('record').addEventListener('click',safely(record));$('upload-audio').addEventListener('click',()=>$('audio-file').click());
$('audio-file').addEventListener('change',safely(e=>e.target.files[0]&&recognize(e.target.files[0])));
$('retry').addEventListener('click',safely(async()=>{await api(`/movies/${state.movie.id}/retry`,{method:'POST'});await refresh();}));
$('cancel').addEventListener('click',safely(async()=>{await api(`/movies/${state.movie.id}/cancel`,{method:'POST'});toast('Cancelamento solicitado. Aguarde a operação atual terminar.');}));
$('open-settings').addEventListener('click',safely(openSettings));
$('settings-form').addEventListener('submit',safely(async e=>{e.preventDefault();await api('/settings',{method:'PUT',body:{ollama_model:$('model-select').value,whisper_model:$('whisper-select').value,device:$('device-select').value}});$('settings-dialog').close();await updateConnection();toast('Preferências salvas. Valem para os próximos processamentos.');}));
document.querySelectorAll('.close-dialog').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
$('open-transcript').addEventListener('click',safely(openTranscript));$('transcript-search').addEventListener('input',renderTranscript);$('transcript-list').addEventListener('click',safely(transcriptClick));
$('open-export').addEventListener('click',()=>$('export-dialog').showModal());$('download-pdf').addEventListener('click',safely(downloadPDF));
$('translate-all').addEventListener('click',safely(async()=>{await api(`/movies/${state.movie.id}/translate`,{method:'POST'});await refresh();toast('Tradução iniciada. Você pode continuar estudando enquanto isso.');}));
$('history-list').addEventListener('click',safely(async e=>{const b=e.target.closest('.review-attempt');if(!b)return;const item=state.history.find(r=>r.id===Number(b.dataset.id));await selectMovie(item.movie_id);setMode(item.mode);$('scene-start').value=formatTime(item.start,true);$('scene-end').value=formatTime(item.end,true);$('answer').value=item.answer;updateCount();renderResult(item.result);}));
window.addEventListener('beforeunload',()=>{if(state.recorder?.state==='recording'){state.recorder.onstop=null;state.recorder.stream.getTracks().forEach(t=>t.stop());state.recorder.stop();}});
async function boot() {
  updateControls();await refresh();await updateConnection();
  const saved=localStorage.getItem('english-studio-movie'), id=state.movies.find(m=>m.id===saved)?.id || state.movies[0]?.id;
  if(id)await selectMovie(id);
  let polling=false;
  setInterval(async()=>{if(polling||state.uploading)return;polling=true;try{await refresh();}catch{}finally{polling=false;}},2500);
  setInterval(enforceScene,50);
}
safely(boot)();
