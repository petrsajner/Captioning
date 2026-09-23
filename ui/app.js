'use strict';
const $ = id => document.getElementById(id);
const recipe = $('recipe-form'), settingsForm = $('settings-form');
let state, selected = new Set(), active = null, dirty = false, page = 0, settingsMode = 'local';
let busy = false, pollBusy = false, recipeTimer, recipeDirty = false, toastTimer, lastGrid = '';
let recipeRevision=0, recipeSaving=null, lastCaptionHistory='';
let localScanBusy=false, localModelsBusy=false, localServers=[];
const labels = {pending:'Waiting',queued:'Queued',processing:'Analyzing…',saved:'Saved',existing:'Existing',skipped:'Skipped',draft:'Draft',review:'To review',error:'Error',invalid:'Conflict / error'};
const phaseLabels={caption:'Captioning…',shorten:'Shortening…',complete:'Completing…',repair_json:'Repairing JSON…',retry_caption:'Requesting a response…'};
const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(text, error=false) { $('toast').textContent=t(text); $('toast').className='toast'+(error?' error':''); $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true, error?11000:4500); }
async function api(path, body, method='POST') {
  const options={method:body===undefined?'GET':method,headers:{'X-Caption-Client':'1'}};
  if(body!==undefined) {options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const response=await fetch('/api'+path,options);
  let data;try{data=await response.json();}catch{throw Error(t('The application is unavailable. Start it again.'));}
  if(!response.ok) throw Error(typeof data.detail==='string'?t(data.detail):t('Check the entered values: ')+(data.detail||[]).map(x=>t(x.msg)).join('; '));
  return data;
}
async function action(fn) {try{await fn();}catch(e){toast(e.message,true);}}
function formValues(form, base) {
  const out={...base};
  for(const el of form.elements) if(el.name&&!el.dataset.attribute) out[el.name]=el.type==='checkbox'?el.checked:(['number','range'].includes(el.type)||el.name==='image_size'?Number(el.value):el.value);
  if(form===recipe)out.omitted_attributes=[...form.querySelectorAll('[data-attribute]')].filter(el=>!el.checked).map(el=>el.dataset.attribute);
  return out;
}
function fillForm(form, values) {for(const el of form.elements) if(el.name && el.name in values) {if(el.type==='checkbox')el.checked=values[el.name];else el.value=values[el.name];}}
function liveSettings() {return formValues(recipe,state.settings);}
function hasBusy() {return busy||state?.job.running||state?.importing;}
function resumeIds(){return state?.job.paused?(state.job.remaining_ids||[]).filter(id=>state.rows.some(r=>r.id===id)):[];}
function allowDiscard() {return !dirty || window.confirm(t('The caption has unsaved edits. Discard these edits?'));}
async function saveRecipe() {
  clearTimeout(recipeTimer);
  if(recipeSaving)await recipeSaving;
  if(!recipeDirty)return;
  const snapshot=liveSettings(), revision=recipeRevision;
  recipeSaving=api('/settings',{settings:snapshot});
  try {await recipeSaving;state.settings=snapshot;recipeDirty=recipeRevision!==revision;
    $('recipe-status').textContent=recipeDirty?t('Unsaved settings…'):t('Settings saved');
  }finally{recipeSaving=null;}
  if(recipeDirty)await saveRecipe();
}
recipe.addEventListener('input',()=>{
  $('word-output').value=recipe.elements.words.value;recipeDirty=true;recipeRevision++;
  renderTrainingPlan();
  $('recipe-status').textContent=t('Unsaved settings…');
  clearTimeout(recipeTimer);recipeTimer=setTimeout(()=>action(saveRecipe),600);
});
recipe.addEventListener('submit',e=>e.preventDefault());
settingsForm.addEventListener('submit',e=>e.preventDefault());

function filteredRows() {
  if(!state)return [];
  const query=$('search').value.toLowerCase(), filter=$('filter').value;
  return state.rows.filter(r=>r.name.toLowerCase().includes(query)&&(filter==='all'||(filter==='saved'&&r.exists)||(filter==='pending'&&!r.exists)||(filter==='review'&&r.status==='review')||(filter==='error'&&['error','invalid'].includes(r.status))));
}
function renderGrid() {
  const rows=filteredRows();page=Math.min(page,Math.max(0,Math.ceil(rows.length/60)-1));
  const visible=rows.slice(page*60,(page+1)*60);
  const signature=JSON.stringify([visible.map(r=>[r.id,r.status,r.phase,r.exists,selected.has(r.id)]),active]);
  if(signature!==lastGrid) {
    $('grid').innerHTML=visible.map(r=>`<article class="image-card ${r.status} ${r.id===active?'active':''}" data-id="${r.id}" tabindex="0" aria-label="${esc(r.name)}"><input class="card-select" type="checkbox" ${selected.has(r.id)?'checked':''} aria-label="${esc(t('Select {name}', {name:r.name}))}"><img class="thumb" loading="lazy" src="/api/image/${r.id}" alt="${esc(r.name)}"><div class="card-info"><div class="card-name" title="${esc(r.path)}">${esc(r.name)}</div><div class="card-bottom"><span>${r.width} × ${r.height}</span><span class="status-label ${r.status}">${esc(t(r.status==='processing'?(phaseLabels[r.phase]||labels.processing):(labels[r.status]||r.status)))}</span></div></div></article>`).join('');
    lastGrid=signature;
  }
  $('empty').hidden=state.rows.length>0;$('grid').hidden=!rows.length;
  $('pagebar').hidden=!state.rows.length;
  $('page-label').textContent=rows.length?t('{start}–{end} of {count}', {start:page*60+1,end:Math.min((page+1)*60,rows.length),count:rows.length}):t('No images match this filter');
  $('prev-page').disabled=page===0;$('next-page').disabled=(page+1)*60>=rows.length;
  $('selection-count').textContent=selected.size?t("{v0} selected", {v0:(selected.size)}):t('Select all');
  $('select-all').checked=rows.length>0&&rows.every(r=>selected.has(r.id));
  $('select-all').indeterminate=rows.some(r=>selected.has(r.id))&&!$('select-all').checked;
}
function updateWords() {const text=$('caption-editor').value.trim();const row=state.rows.find(r=>r.id===active);if(row?.caption_format==='bria_json'){try{JSON.parse(text);$('caption-words').textContent=t('JSON object');}catch{$('caption-words').textContent=t('Invalid JSON');}}else $('caption-words').textContent=(text?text.split(/\s+/).length:0)+t(' words');}
function renderInspector() {
  const row=state.rows.find(r=>r.id===active);
  $('inspector-empty').hidden=!!row;$('inspector-content').hidden=!row;
  if(!row)return;
  const src='/api/image/'+row.id+'?full=true';if($('preview-image').getAttribute('src')!==src)$('preview-image').src=src;
  $('image-name').textContent=row.name;$('image-meta').textContent=`${row.width} × ${row.height} px${row.seconds?' · '+row.seconds+' s':''}`;
  $('image-path').textContent=row.path;$('image-path').title=row.path;
  if(!dirty && $('caption-editor').value!==row.caption) $('caption-editor').value=row.caption;
  $('image-error').hidden=!row.error;$('image-error').textContent=diagnostic(row.error);
  $('caption-state').textContent=dirty?t('● Unsaved edits'):(row.status==='draft'?t('● Generated, not saved yet'):t(labels[row.status]));
  const json=row.caption_format==='bria_json';
  $('caption-output-path').textContent=t('File: ')+row.name.replace(/\.[^.]+$/,json?'.json':'.txt');
  $('caption-notice').hidden=!row.notice;$('caption-notice').textContent=diagnostic(row.notice||'');
  $('format-json').hidden=!json;$('format-json').disabled=hasBusy();
  $('caption-editor').classList.toggle('json-editor',json);
  $('caption-editor').disabled=hasBusy()||row.status==='invalid';
  $('save-caption').disabled=hasBusy()||row.status==='invalid'||!$('caption-editor').value.trim();
  $('regenerate').disabled=hasBusy()||row.status==='invalid';updateWords();
  const history=row.generation_history||[];
  $('caption-history').hidden=!history.length;
  const historyKey=row.id+':'+JSON.stringify(history);
  if(lastCaptionHistory!==historyKey){
    lastCaptionHistory=historyKey;
    $('caption-history-title').textContent=t('Model responses ({count})', {count:history.length});
    $('caption-history-select').innerHTML=history.map((h,i)=>`<option value="${i}">${i+1}. ${esc(t(phaseLabels[h.stage]||h.stage))}${h.word_count!=null?' · '+h.word_count+t(' words'):''}</option>`).join('');
    showCaptionHistory();
  }
  $('use-caption-history').disabled=hasBusy()||!$('caption-history-text').textContent.trim();
}
function showCaptionHistory(){const row=state.rows.find(r=>r.id===active);$('caption-history-text').textContent=row?.generation_history?.[Number($('caption-history-select').value)]?.text||'';$('use-caption-history').disabled=hasBusy()||!$('caption-history-text').textContent.trim();}
$('caption-history-select').onchange=showCaptionHistory;
$('use-caption-history').onclick=()=>{if(hasBusy())return;$('caption-editor').value=$('caption-history-text').textContent;dirty=true;renderInspector();};
function renderRuntime() {
  const r=state.runtime;
  for(const el of settingsForm.elements)el.disabled=r.installing||r.status==='loading';
  $('runtime-badge').textContent=r.running?t('Running'):r.ready?t('Ready'):r.installing?t('Preparing'):t('Not ready');
  $('runtime-message').textContent=r.ready&&r.status==='idle'?t('The runtime and model are ready to start.'):diagnostic(r.message);
  const pct=r.total?Math.min(100,100*r.done/r.total):0;
  $('download-progress').style.width=pct+'%';
  $('download-details').textContent=r.total>1?`${(r.done/1e9).toFixed(2)} / ${(r.total/1e9).toFixed(2)} GB · ${pct.toFixed(0)} %`:'';
  $('runtime-path').textContent=r.root;
  $('install-runtime').disabled=r.installing||r.running||busy||state.job.running;
  $('install-runtime').textContent=r.ready?t('Verify / complete model'):t('Download runtime and model');
  $('cancel-install').hidden=!r.installing;
  $('start-model').hidden=r.running;$('start-model').disabled=!r.ready||r.installing||busy||state.job.running;
  $('stop-model').hidden=!r.running;$('stop-model').disabled=busy||state.job.running;
  // Protect the profile of an in-flight install while allowing its cancellation.
  $('cancel-install').disabled=false;
  $('save-settings').disabled=r.installing||r.status==='loading'||busy;
  $('find-local-servers').disabled=r.installing||r.status==='loading'||localScanBusy||localModelsBusy;
  $('load-local-models').disabled=r.installing||r.status==='loading'||localModelsBusy||localScanBusy;
}
function render() {
  const version='v'+state.version;
  if($('app-version').textContent!==version){$('app-version').textContent=version;document.title='Caption Studio '+version;}
  $('total-badge').textContent=state.rows.length;
  $('pending-count').textContent=state.rows.filter(r=>!r.exists&&!['invalid','error','review'].includes(r.status)).length;
  $('saved-count').textContent=state.rows.filter(r=>r.exists).length;
  $('error-count').textContent=state.rows.filter(r=>['invalid','error'].includes(r.status)).length;
  $('review-count').textContent=state.rows.filter(r=>r.status==='review').length;
  const j=state.job;
  $('job-title').textContent=busy?t('Working…'):diagnostic(j.message);
  $('job-count').textContent=j.total?t("{v0} / {v1} · {v2} saved{v3}{v4}", {v0:(j.completed),v1:(j.total),v2:(j.saved),v3:(j.review?' · '+j.review+t(' to review'):''),v4:(j.skipped?' · '+j.skipped+t(' skipped'):'')}):'';
  $('job-progress').style.width=j.total?100*j.completed/j.total+'%':'0%';
  $('stop-job').hidden=!j.running;
  const pending=resumeIds(), runCount=pending.length||selected.size;
  $('generate').disabled=hasBusy()||!runCount;
  $('generate').innerHTML=`${pending.length?t('Continue'):liveSettings().output_format==='bria_json'?t('Create BRIA JSON'):t('Create captions')}${runCount?' ('+runCount+')':''} <span>→</span>`;
  $('model-chip').querySelector('span').textContent=state.settings.mode==='local'?(state.settings.local_source==='external'?t('Local · ')+(state.settings.local_model||t('external server')):t("Local · {v0}", {v0:(state.runtime.running?t('Qwen running'):'Qwen / server')})):'Cloud · '+(state.settings.cloud_model.split('/').pop()||t('select a model'));
  $('mode-note').textContent=state.settings.mode==='local'?t('Local mode · images stay on this computer'):t("Cloud mode · selected images will be sent to {v0}", {v0:(new URL(state.settings.cloud_url).hostname)});
  for(const id of ['pick-folder','pick-files','open-path','open-settings','model-chip'])$(id).disabled=hasBusy();
  for(const el of recipe.elements)el.disabled=hasBusy()||state.runtime.installing||state.runtime.status==='loading';
  renderTrainingPlan();
  renderGrid();renderInspector();renderRuntime();
}
async function refresh() {
  if(pollBusy)return;pollBusy=true;
  try {
    const next=await api('/state');
    if(recipeDirty&&state)next.settings=state.settings;
    state=next;render();
  } finally {pollBusy=false;}
}
function selectImage(id) {
  if(id!==active&&!allowDiscard())return;
  if(id!==active)dirty=false;active=id;renderGrid();renderInspector();
}
$('grid').addEventListener('click',e=>{
  const card=e.target.closest('.image-card');if(!card)return;
  if(e.target.matches('.card-select')) {e.target.checked?selected.add(card.dataset.id):selected.delete(card.dataset.id);render();}
  else selectImage(card.dataset.id);
});
$('grid').addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('.image-card')){e.preventDefault();selectImage(e.target.dataset.id);}});
$('select-all').onchange=()=>{for(const r of filteredRows())$('select-all').checked?selected.add(r.id):selected.delete(r.id);render();};
for(const id of ['search','filter'])$(id).addEventListener('input',()=>{page=0;renderGrid();});
$('prev-page').onclick=()=>{page--;renderGrid();};$('next-page').onclick=()=>{page++;renderGrid();};
$('caption-editor').oninput=()=>{dirty=true;renderInspector();};
async function saveCaption(){if(!active||hasBusy())return;await api('/caption/'+active,{text:$('caption-editor').value},'PUT');dirty=false;await refresh();toast(t('Caption saved next to the image.'));}
$('save-caption').onclick=()=>action(saveCaption);
$('format-json').onclick=()=>action(async()=>{const data=JSON.parse($('caption-editor').value);if(!data||Array.isArray(data)||typeof data!=='object')throw Error(t('BRIA requires a JSON object.'));$('caption-editor').value=JSON.stringify(data,null,2);dirty=true;renderInspector();});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();action(saveCaption);}});

async function doImport(paths=[],folder='') {
  if(!allowDiscard())return false;
  await saveRecipe();busy=true;render();
  try{
    const append=$('append').checked, oldIds=new Set(state.rows.map(r=>r.id));
    await api('/import',{paths,folder,recursive:$('recursive').checked,append});
    dirty=false;await refresh();
    if(!append)selected.clear();
    for(const r of state.rows)if(!oldIds.has(r.id)||!append)selected.add(r.id);
    if(!state.rows.some(r=>r.id===active))active=state.rows[0]?.id||null;
    page=0;toast(t("Loaded {v0} images.", {v0:(state.rows.length)}));return true;
  }finally{busy=false;render();}
}
async function pickFiles(){if(hasBusy())return;const result=await api('/pick/files',{});if(result.paths.length)await doImport(result.paths);}
$('pick-folder').onclick=()=>{if(!hasBusy())folderPicker.open();};
$('pick-files').onclick=()=>action(pickFiles);
$('open-path').onclick=()=>$('path-dialog').showModal();
$('import-path').onclick=()=>action(async()=>{await doImport([],$('folder-path').value.trim());$('path-dialog').close();});
$('folder-path').addEventListener('keydown',e=>{if(e.key==='Enter')$('import-path').click();});

async function generate(ids,regenerate=false) {
  if(hasBusy()||!allowDiscard())return;
  await saveRecipe();dirty=false;
  if(state.settings.mode==='local'&&state.settings.local_source==='managed'&&!state.runtime.running) {
    if(!state.runtime.ready){openSettings();toast(t('Download the runtime and model first, or select a cloud API.'));return;}
    busy=true;render();toast(t('Starting the local model. Loading may take a moment.'));
    try{await api('/runtime/start',{});}finally{busy=false;await refresh();}
  }
  await api('/jobs',{ids,regenerate});await refresh();
}
$('generate').onclick=()=>action(()=>{const pending=resumeIds();return generate(pending.length?pending:[...selected],pending.length?!!state.job.resume_regenerate:false);});
$('regenerate').onclick=()=>action(()=>generate([active],true));
$('stop-job').onclick=()=>action(async()=>{await api('/jobs/stop',{});await refresh();});

function switchMode(mode) {
  settingsMode=mode;
  document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
  $('local-settings').hidden=mode!=='local';$('cloud-settings').hidden=mode!=='cloud';
}
function openSettings() {
  if(!state)return;
  fillForm(settingsForm,state.settings);switchMode(state.settings.mode);
  $('api-key').value='';$('clear-key').checked=false;
  clearLocalKeyInput();showLocalSource();
  $('local-server-results').hidden=true;$('local-server-results').replaceChildren();localServers=[];
  $('local-discovery-message').textContent=t('Check common local addresses for Ollama, LM Studio, Unsloth and llama.cpp.');
  $('cloud-provider').value=[...$('cloud-provider').options].some(o=>o.value===state.settings.cloud_url)?state.settings.cloud_url:'custom';
  $('key-status').textContent=state.has_key?t('A key is saved. Leave this field empty to keep it.'):t('The key is stored encrypted for your Windows account.');
  $('setup-title').textContent=state.settings.setup_complete?t('Model and runtime'):t('Set up your workspace');
  $('settings-message').textContent='';$('settings-dialog').showModal();renderRuntime();
}
$('open-settings').onclick=openSettings;$('model-chip').onclick=openSettings;
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>switchMode(b.dataset.mode));
document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('cloud-provider').onchange=()=>{if($('cloud-provider').value!=='custom')settingsForm.elements.cloud_url.value=$('cloud-provider').value;settingsForm.elements.cloud_model.value='';$('api-key').value='';$('clear-key').checked=false;$('key-status').textContent=t('Keys are stored separately for each API address.');};
async function saveSetup(close=false) {
  await saveRecipe();
  if(!settingsForm.reportValidity())throw Error(t('Correct the highlighted values.'));
  const config=formValues(settingsForm,liveSettings());config.mode=settingsMode;config.setup_complete=true;
  const result=await api('/settings',{settings:config,api_key:$('api-key').value||null,clear_key:$('clear-key').checked,
    local_api_key:$('local-api-key').value||null,clear_local_key:$('clear-local-key').checked});
  state.settings=config;state.has_key=result.has_key;$('api-key').value='';$('clear-key').checked=false;
  state.has_local_key=result.has_local_key;clearLocalKeyInput();
  $('settings-message').textContent=t('Settings saved');
  await refresh();if(close)$('settings-dialog').close();
}
$('save-settings').onclick=()=>action(()=>saveSetup(true));
$('ui-language').onchange=()=>action(async()=>{
  const language=$('ui-language').value;
  try {
    await saveRecipe();
    await api('/ui-language',{language});
    state.settings.ui_language=language;
    const draft=liveSettings();
    i18n.setLanguage(language);
    lastGrid='';lastCaptionHistory='';
    fillTrainingControls(draft);render();
    $('setup-title').textContent=t(state.settings.setup_complete?'Model and runtime':'Set up your workspace');
    $('settings-message').textContent=t('Language saved');
    if(folderPicker.listing){folderPicker.renderContents();folderPicker.renderTree();}
  } catch(e) {
    $('ui-language').value=state.settings.ui_language;
    throw e;
  }
});
$('load-models').onclick=()=>action(async()=>{
  await saveSetup();$('settings-message').textContent=t('Loading models…');
  const result=await api('/models',state.settings);
  $('cloud-models').innerHTML=result.models.map(m=>`<option value="${esc(m)}">`).join('');
  $('settings-message').textContent=t("Connected · {v0} models. Select a model in the field above.", {v0:(result.models.length)});
  settingsForm.elements.cloud_model.focus();
});
$('install-runtime').onclick=()=>action(async()=>{await saveSetup();await api('/runtime/install',{});await refresh();});
$('cancel-install').onclick=()=>action(async()=>{await api('/runtime/cancel',{});$('runtime-message').textContent=t('Pausing download…');});
$('start-model').onclick=()=>action(async()=>{await saveSetup();busy=true;render();try{await api('/runtime/start',{});}finally{busy=false;await refresh();}});
$('stop-model').onclick=()=>action(async()=>{await api('/runtime/stop',{});await refresh();});
$('preview-prompt').onclick=()=>action(async()=>{const result=await api('/prompt',liveSettings());$('prompt-text').textContent=result.prompt;$('prompt-dialog').showModal();});

function showLocalSource(){
  const external=settingsForm.elements.local_source.value==='external';
  $('managed-settings').hidden=external;$('external-settings').hidden=!external;
}
function clearLocalKeyInput(){
  $('local-api-key').value='';$('clear-local-key').checked=false;
  const saved=state.has_local_key&&state.settings.local_url===settingsForm.elements.local_url.value.replace(/\/$/,'');
  $('local-key-status').textContent=saved?t('A key is saved. Leave this field empty to keep it.'):t('A saved key is used only for this address. Enter a new key here if needed.');
}
function fillLocalModels(models){
  $('local-models').innerHTML=models.map(id=>`<option value="${esc(id)}">`).join('');
  if(models.length&&!models.includes(settingsForm.elements.local_model.value))settingsForm.elements.local_model.value=models[0];
}
$('local-source').onchange=showLocalSource;
settingsForm.elements.local_url.addEventListener('input',()=>{clearLocalKeyInput();$('local-models').replaceChildren();$('local-model-status').textContent=t('Load the available models for this address.');});
$('find-local-servers').onclick=async()=>{
  if(localScanBusy)return;localScanBusy=true;renderRuntime();
  $('local-discovery-message').textContent=t('Finding running local servers…');
  $('local-server-results').hidden=true;
  try{
    const result=await api('/local-servers',{url:settingsForm.elements.local_url.value});
    localServers=result.servers;
    $('local-server-results').innerHTML=localServers.map((server,index)=>`<button type="button" class="local-server" data-server-index="${index}"><span><b>${esc(server.url)}</b><small>${esc(t(server.hint))}</small></span><span>${server.status==='requires_key'?t('Key required'):server.models.length?t('Models: ')+server.models.length:t('No model')} →</span></button>`).join('');
    $('local-server-results').hidden=!localServers.length;
    $('local-discovery-message').textContent=localServers.length?t("Servers found: {v0}. Click to select a connection.", {v0:(localServers.length)}):t('No running server was found. Start its API, or select Existing local server and enter a custom address.');
  }catch(e){$('local-discovery-message').textContent=t(e.message);}
  finally{localScanBusy=false;renderRuntime();}
};
$('local-server-results').onclick=e=>{
  const button=e.target.closest('[data-server-index]');if(!button||localScanBusy)return;
  const server=localServers[Number(button.dataset.serverIndex)];if(!server)return;
  settingsForm.elements.local_source.value=server.managed?'managed':'external';
  if(!server.managed){settingsForm.elements.local_url.value=server.url;settingsForm.elements.local_model.value=server.models[0]||'';}
  clearLocalKeyInput();fillLocalModels(server.models);showLocalSource();
  $('local-model-status').textContent=server.status==='requires_key'?t('The server requires a key. Enter it and click Load models. Compatibility has not been verified yet.'):server.models.length?t('Select an image-capable model. Its presence in this list does not guarantee image support.'):t('The server responds but offers no models. Load a model in its original application and refresh the list.');
  $('local-discovery-message').textContent=t('Selected {url}. Confirm with Save and continue.',{url:server.url});
  if(server.status==='requires_key')$('local-api-key').focus();
};
$('load-local-models').onclick=async()=>{
  if(localModelsBusy)return;localModelsBusy=true;renderRuntime();$('local-model-status').textContent=t('Checking the connection and loading models…');
  try{
    await saveSetup();
    const localSettings={...formValues(settingsForm,state.settings),mode:'local',local_source:'external'};
    const result=await api('/models',localSettings);fillLocalModels(result.models);
    $('local-model-status').textContent=result.models.length?t("Connected. Available models: {v0}. Select an image-capable model and save settings.", {v0:(result.models.length)}):t('Connected, but the list is empty. Load a model in its application first.');
  }catch(e){$('local-model-status').textContent=t(e.message);}
  finally{localModelsBusy=false;renderRuntime();}
};
window.addEventListener('beforeunload',e=>{if(dirty||recipeDirty){e.preventDefault();e.returnValue='';}});

function fillTrainingControls(settings){
  const omitted=new Set(settings.omitted_attributes||[]);
  $('training-controls').innerHTML=state.training_attributes.map(a=>`<label class="caption-detail"><span><input type="checkbox" name="include_${a.id}" data-attribute="${a.id}" ${omitted.has(a.id)?'':'checked'}><span class="detail-name">${esc(t(a.label))}</span><span class="detail-state" aria-hidden="true"><span class="state-on">ON</span><span class="state-off">OFF</span></span></span><small>${esc(t(a.detail))}</small></label>`).join('');
}
function renderTrainingPlan(){
  const s=liveSettings(), omitted=new Set(s.omitted_attributes), attrs=state.training_attributes;
  $('training-plan').textContent=t('{included} of {total} details included in caption', {included:attrs.length-omitted.size,total:attrs.length});
  const json=s.output_format==='bria_json', blocked=hasBusy()||state.runtime.installing||state.runtime.status==='loading';
  recipe.elements.format.disabled=json||blocked;recipe.elements.words.disabled=json||blocked;
  $('json-format-note').hidden=!json;
  $('length-policy-note').hidden=json;
  $('trigger-note').textContent=json?t('Inserted into short_description so the JSON remains valid.'):t('Added exactly at the start of each caption.');
  $('output-note').innerHTML=`<b>image.jpg → image.${json?'json':'txt'}</b><br>${esc(t('Same folder, UTF-8. Skipping applies to both formats. Replaced captions are backed up; the other format is archived so the trainer cannot select it accidentally.'))}`;
}
$('apply-training-preset').onclick=()=>{
  const preset=recipe.elements.preset.value, omitted=preset==='character'||preset==='object'?['identity']:preset==='style'?['style']:[];
  fillTrainingControls({...liveSettings(),omitted_attributes:omitted});
  recipe.dispatchEvent(new Event('input',{bubbles:true}));
};

(async()=>{
  try{
    await i18n.ready;state=await api('/state');i18n.setLanguage(state.settings.ui_language);fillTrainingControls(state.settings);fillForm(recipe,state.settings);$('word-output').value=state.settings.words;
    selected=new Set(state.rows.map(r=>r.id));active=state.rows[0]?.id||null;render();
    if(!state.settings.setup_complete)openSettings();
    if(state.recovered.length){const note=t('Some saved data could not be used and was reset. The original file was kept as: {names}',{names:state.recovered.join(', ')});toast(note,true);if($('settings-dialog').open)$('settings-message').textContent=note;}
    setInterval(()=>refresh().catch(()=>{$('job-title').textContent=t('Connection to the application was lost');}),1200);
  }catch(e){toast(e.message,true);}
})();
