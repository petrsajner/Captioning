'use strict';
const $ = id => document.getElementById(id);
const recipe = $('recipe-form'), settingsForm = $('settings-form');
let state, selected = new Set(), active = null, dirty = false, page = 0, settingsMode = 'local';
let busy = false, pollBusy = false, recipeTimer, recipeDirty = false, toastTimer, lastGrid = '';
let recipeRevision=0, recipeSaving=null;
let localScanBusy=false, localModelsBusy=false, localServers=[];
const labels = {pending:'Čeká',queued:'Ve frontě',processing:'Analyzuje…',saved:'Uloženo',existing:'Existující',skipped:'Přeskočeno',draft:'K uložení',error:'Chyba',invalid:'Konflikt / chyba'};
const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(text, error=false) { $('toast').textContent=text; $('toast').className='toast'+(error?' error':''); $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true, error?11000:4500); }
async function api(path, body, method='POST') {
  const options={method:body===undefined?'GET':method,headers:{'X-Caption-Client':'1'}};
  if(body!==undefined) {options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const response=await fetch('/api'+path,options);
  let data;try{data=await response.json();}catch{throw Error('Aplikace není dostupná. Spusťte ji znovu.');}
  if(!response.ok) throw Error(typeof data.detail==='string'?data.detail:'Zkontrolujte vyplněné hodnoty: '+(data.detail||[]).map(x=>x.msg).join('; '));
  return data;
}
async function action(fn) {try{await fn();}catch(e){toast(e.message,true);}}
function formValues(form, base) {
  const out={...base};
  for(const el of form.elements) if(el.name) out[el.name]=el.type==='checkbox'?el.checked:(['number','range'].includes(el.type)||el.name==='image_size'?Number(el.value):el.value);
  return out;
}
function fillForm(form, values) {for(const el of form.elements) if(el.name && el.name in values) {if(el.type==='checkbox')el.checked=values[el.name];else el.value=values[el.name];}}
function liveSettings() {return formValues(recipe,state.settings);}
function hasBusy() {return busy||state?.job.running||state?.importing;}
function allowDiscard() {return !dirty || window.confirm('Popisek obsahuje neuložené úpravy. Zahodit tyto úpravy?');}
async function saveRecipe() {
  clearTimeout(recipeTimer);
  if(recipeSaving)await recipeSaving;
  if(!recipeDirty)return;
  const snapshot=liveSettings(), revision=recipeRevision;
  recipeSaving=api('/settings',{settings:snapshot});
  try {await recipeSaving;state.settings=snapshot;recipeDirty=recipeRevision!==revision;
    $('recipe-status').textContent=recipeDirty?'Neuložené nastavení…':'Nastavení uloženo';
  }finally{recipeSaving=null;}
  if(recipeDirty)await saveRecipe();
}
recipe.addEventListener('input',()=>{
  $('word-output').value=recipe.elements.words.value;recipeDirty=true;recipeRevision++;
  $('recipe-status').textContent='Neuložené nastavení…';
  clearTimeout(recipeTimer);recipeTimer=setTimeout(()=>action(saveRecipe),600);
});
recipe.addEventListener('submit',e=>e.preventDefault());
settingsForm.addEventListener('submit',e=>e.preventDefault());

function filteredRows() {
  if(!state)return [];
  const query=$('search').value.toLowerCase(), filter=$('filter').value;
  return state.rows.filter(r=>r.name.toLowerCase().includes(query)&&(filter==='all'||(filter==='saved'&&r.exists)||(filter==='pending'&&!r.exists)||(filter==='error'&&['error','invalid'].includes(r.status))));
}
function renderGrid() {
  const rows=filteredRows();page=Math.min(page,Math.max(0,Math.ceil(rows.length/60)-1));
  const visible=rows.slice(page*60,(page+1)*60);
  const signature=JSON.stringify([visible.map(r=>[r.id,r.status,r.exists,selected.has(r.id)]),active]);
  if(signature!==lastGrid) {
    $('grid').innerHTML=visible.map(r=>`<article class="image-card ${r.status} ${r.id===active?'active':''}" data-id="${r.id}" tabindex="0" aria-label="${esc(r.name)}"><input class="card-select" type="checkbox" ${selected.has(r.id)?'checked':''} aria-label="Vybrat ${esc(r.name)}"><img class="thumb" loading="lazy" src="/api/image/${r.id}" alt="${esc(r.name)}"><div class="card-info"><div class="card-name" title="${esc(r.path)}">${esc(r.name)}</div><div class="card-bottom"><span>${r.width} × ${r.height}</span><span class="status-label ${r.status}">${labels[r.status]||r.status}</span></div></div></article>`).join('');
    lastGrid=signature;
  }
  $('empty').hidden=state.rows.length>0;$('grid').hidden=!rows.length;
  $('pagebar').hidden=!state.rows.length;
  $('page-label').textContent=rows.length?`${page*60+1}–${Math.min((page+1)*60,rows.length)} z ${rows.length}`:'Žádný obrázek neodpovídá filtru';
  $('prev-page').disabled=page===0;$('next-page').disabled=(page+1)*60>=rows.length;
  $('selection-count').textContent=selected.size?`${selected.size} vybráno`:'Vybrat vše';
  $('select-all').checked=rows.length>0&&rows.every(r=>selected.has(r.id));
  $('select-all').indeterminate=rows.some(r=>selected.has(r.id))&&!$('select-all').checked;
}
function updateWords() {const text=$('caption-editor').value.trim();$('caption-words').textContent=(text?text.split(/\s+/).length:0)+' slov';}
function renderInspector() {
  const row=state.rows.find(r=>r.id===active);
  $('inspector-empty').hidden=!!row;$('inspector-content').hidden=!row;
  if(!row)return;
  const src='/api/image/'+row.id+'?full=true';if($('preview-image').getAttribute('src')!==src)$('preview-image').src=src;
  $('image-name').textContent=row.name;$('image-meta').textContent=`${row.width} × ${row.height} px${row.seconds?' · '+row.seconds+' s':''}`;
  $('image-path').textContent=row.path;$('image-path').title=row.path;
  if(!dirty && $('caption-editor').value!==row.caption) $('caption-editor').value=row.caption;
  $('image-error').hidden=!row.error;$('image-error').textContent=row.error;
  $('caption-state').textContent=dirty?'● Neuložené ruční úpravy':(row.status==='draft'?'● Vygenerováno, zatím neuloženo':labels[row.status]);
  $('caption-editor').disabled=hasBusy()||row.status==='invalid';
  $('save-caption').disabled=hasBusy()||row.status==='invalid'||!$('caption-editor').value.trim();
  $('regenerate').disabled=hasBusy()||row.status==='invalid';updateWords();
}
function renderRuntime() {
  const r=state.runtime;
  for(const el of settingsForm.elements)el.disabled=r.installing||r.status==='loading';
  $('runtime-badge').textContent=r.running?'Běží':r.ready?'Připravené':r.installing?'Příprava':'Nepřipravené';
  $('runtime-message').textContent=r.ready&&r.status==='idle'?'Prostředí i model jsou připravené ke spuštění.':r.message;
  const pct=r.total?Math.min(100,100*r.done/r.total):0;
  $('download-progress').style.width=pct+'%';
  $('download-details').textContent=r.total>1?`${(r.done/1e9).toFixed(2)} / ${(r.total/1e9).toFixed(2)} GB · ${pct.toFixed(0)} %`:'';
  $('runtime-path').textContent=r.root;
  $('install-runtime').disabled=r.installing||r.running||busy||state.job.running;
  $('install-runtime').textContent=r.ready?'Ověřit / doplnit model':'Stáhnout prostředí a model';
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
  $('pending-count').textContent=state.rows.filter(r=>!r.exists&&!['invalid','error'].includes(r.status)).length;
  $('saved-count').textContent=state.rows.filter(r=>r.exists).length;
  $('error-count').textContent=state.rows.filter(r=>['invalid','error'].includes(r.status)).length;
  const j=state.job;
  $('job-title').textContent=busy?'Pracuji…':j.message;
  $('job-count').textContent=j.total?`${j.completed} / ${j.total} · ${j.saved} uloženo${j.skipped?' · '+j.skipped+' přeskočeno':''}`:'';
  $('job-progress').style.width=j.total?100*j.completed/j.total+'%':'0%';
  $('stop-job').hidden=!j.running;
  $('generate').disabled=hasBusy()||!selected.size;
  $('generate').innerHTML=`Vytvořit popisky${selected.size?' ('+selected.size+')':''} <span>→</span>`;
  $('model-chip').querySelector('span').textContent=state.settings.mode==='local'?(state.settings.local_source==='external'?'Lokální · '+(state.settings.local_model||'externí server'):`Lokální · ${state.runtime.running?'Qwen běží':'Qwen / server'}`):'Cloud · '+(state.settings.cloud_model.split('/').pop()||'vyberte model');
  $('mode-note').textContent=state.settings.mode==='local'?'Lokální režim · obrázky zůstávají na tomto počítači':`Cloudový režim · vybrané obrázky se odešlou na ${new URL(state.settings.cloud_url).hostname}`;
  for(const id of ['pick-folder','pick-files','open-path','open-settings','model-chip'])$(id).disabled=hasBusy();
  for(const el of recipe.elements)el.disabled=hasBusy()||state.runtime.installing||state.runtime.status==='loading';
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
async function saveCaption(){if(!active||hasBusy())return;await api('/caption/'+active,{text:$('caption-editor').value},'PUT');dirty=false;await refresh();toast('Popisek uložen vedle obrázku.');}
$('save-caption').onclick=()=>action(saveCaption);
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
    page=0;toast(`Načteno ${state.rows.length} obrázků.`);return true;
  }finally{busy=false;render();}
}
async function pickImages(kind){if(hasBusy())return;const result=await api('/pick/'+kind,{});if(result.paths.length)await doImport(kind==='files'?result.paths:[],kind==='folder'?result.paths[0]:'');}
$('pick-folder').onclick=()=>{if(!hasBusy())folderPicker.open();};
$('pick-files').onclick=()=>action(()=>pickImages('files'));
$('open-path').onclick=()=>$('path-dialog').showModal();
$('import-path').onclick=()=>action(async()=>{await doImport([],$('folder-path').value.trim());$('path-dialog').close();});
$('folder-path').addEventListener('keydown',e=>{if(e.key==='Enter')$('import-path').click();});

async function generate(ids,regenerate=false) {
  if(hasBusy()||!allowDiscard())return;
  await saveRecipe();dirty=false;
  if(state.settings.mode==='local'&&state.settings.local_source==='managed'&&!state.runtime.running) {
    if(!state.runtime.ready){openSettings();toast('Nejprve stáhněte prostředí a model, nebo zvolte cloudové API.');return;}
    busy=true;render();toast('Spouštím lokální model. Načtení může chvíli trvat.');
    try{await api('/runtime/start',{});}finally{busy=false;await refresh();}
  }
  await api('/jobs',{ids,regenerate});await refresh();
}
$('generate').onclick=()=>action(()=>generate([...selected]));
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
  $('local-discovery-message').textContent='Vyhledá běžné lokální adresy Ollama, LM Studio, Unsloth a llama.cpp.';
  $('cloud-provider').value=[...$('cloud-provider').options].some(o=>o.value===state.settings.cloud_url)?state.settings.cloud_url:'custom';
  $('key-status').textContent=state.has_key?'Klíč je uložený. Prázdné pole ho ponechá beze změny.':'Klíč se uloží šifrovaně pro váš účet Windows.';
  $('setup-title').textContent=state.settings.setup_complete?'Model a prostředí':'Připravte si svůj pracovní prostor';
  $('settings-message').textContent='';$('settings-dialog').showModal();renderRuntime();
}
$('open-settings').onclick=openSettings;$('model-chip').onclick=openSettings;
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>switchMode(b.dataset.mode));
document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('cloud-provider').onchange=()=>{if($('cloud-provider').value!=='custom')settingsForm.elements.cloud_url.value=$('cloud-provider').value;settingsForm.elements.cloud_model.value='';$('api-key').value='';$('clear-key').checked=false;$('key-status').textContent='Klíče jsou uložené odděleně pro každou adresu API.';};
async function saveSetup(close=false) {
  await saveRecipe();
  if(!settingsForm.reportValidity())throw Error('Opravte označené hodnoty.');
  const config=formValues(settingsForm,liveSettings());config.mode=settingsMode;config.setup_complete=true;
  const result=await api('/settings',{settings:config,api_key:$('api-key').value||null,clear_key:$('clear-key').checked,
    local_api_key:$('local-api-key').value||null,clear_local_key:$('clear-local-key').checked});
  state.settings=config;state.has_key=result.has_key;$('api-key').value='';$('clear-key').checked=false;
  state.has_local_key=result.has_local_key;clearLocalKeyInput();
  $('settings-message').textContent='Nastavení uloženo';
  await refresh();if(close)$('settings-dialog').close();
}
$('save-settings').onclick=()=>action(()=>saveSetup(true));
$('load-models').onclick=()=>action(async()=>{
  await saveSetup();$('settings-message').textContent='Načítám modely…';
  const result=await api('/models',state.settings);
  $('cloud-models').innerHTML=result.models.map(m=>`<option value="${esc(m)}">`).join('');
  $('settings-message').textContent=`Připojeno · ${result.models.length} modelů. Vyberte model v poli nad tlačítkem.`;
  settingsForm.elements.cloud_model.focus();
});
$('install-runtime').onclick=()=>action(async()=>{await saveSetup();await api('/runtime/install',{});await refresh();});
$('cancel-install').onclick=()=>action(async()=>{await api('/runtime/cancel',{});$('runtime-message').textContent='Pozastavuji stahování…';});
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
  $('local-key-status').textContent=saved?'Klíč je uložený. Prázdné pole jej ponechá beze změny.':'Uložený klíč se použije pouze pro tuto adresu. Nový klíč lze zadat zde.';
}
function fillLocalModels(models){
  $('local-models').innerHTML=models.map(id=>`<option value="${esc(id)}">`).join('');
  if(models.length&&!models.includes(settingsForm.elements.local_model.value))settingsForm.elements.local_model.value=models[0];
}
$('local-source').onchange=showLocalSource;
settingsForm.elements.local_url.addEventListener('input',()=>{clearLocalKeyInput();$('local-models').replaceChildren();$('local-model-status').textContent='Pro tuto adresu načtěte dostupné modely.';});
$('find-local-servers').onclick=async()=>{
  if(localScanBusy)return;localScanBusy=true;renderRuntime();
  $('local-discovery-message').textContent='Hledám běžící lokální servery…';
  $('local-server-results').hidden=true;
  try{
    const result=await api('/local-servers',{url:settingsForm.elements.local_url.value});
    localServers=result.servers;
    $('local-server-results').innerHTML=localServers.map((server,index)=>`<button type="button" class="local-server" data-server-index="${index}"><span><b>${esc(server.url)}</b><small>${esc(server.hint)}</small></span><span>${server.status==='requires_key'?'Vyžaduje klíč':server.models.length?'Modely: '+server.models.length:'Žádný model'} →</span></button>`).join('');
    $('local-server-results').hidden=!localServers.length;
    $('local-discovery-message').textContent=localServers.length?`Nalezené servery: ${localServers.length}. Kliknutím vyberte připojení.`:'Nebyl nalezen běžící server. Spusťte API v příslušné aplikaci, nebo zvolte Existující lokální server a zadejte vlastní adresu.';
  }catch(e){$('local-discovery-message').textContent=e.message;}
  finally{localScanBusy=false;renderRuntime();}
};
$('local-server-results').onclick=e=>{
  const button=e.target.closest('[data-server-index]');if(!button||localScanBusy)return;
  const server=localServers[Number(button.dataset.serverIndex)];if(!server)return;
  settingsForm.elements.local_source.value=server.managed?'managed':'external';
  if(!server.managed){settingsForm.elements.local_url.value=server.url;settingsForm.elements.local_model.value=server.models[0]||'';}
  clearLocalKeyInput();fillLocalModels(server.models);showLocalSource();
  $('local-model-status').textContent=server.status==='requires_key'?'Server vyžaduje klíč. Zadejte jej a klikněte na Načíst modely. Kompatibilita zatím není ověřená.':server.models.length?'Vyberte model s podporou obrázků. Jeho přítomnost v seznamu tuto podporu nezaručuje.':'Server odpovídá, ale nenabízí žádný model. Načtěte model v původní aplikaci a obnovte seznam.';
  $('local-discovery-message').textContent='Vybráno '+server.url+'. Připojení potvrďte tlačítkem Uložit a pokračovat.';
  if(server.status==='requires_key')$('local-api-key').focus();
};
$('load-local-models').onclick=async()=>{
  if(localModelsBusy)return;localModelsBusy=true;renderRuntime();$('local-model-status').textContent='Ověřuji připojení a načítám modely…';
  try{
    await saveSetup();
    const localSettings={...formValues(settingsForm,state.settings),mode:'local',local_source:'external'};
    const result=await api('/models',localSettings);fillLocalModels(result.models);
    $('local-model-status').textContent=result.models.length?`Připojeno. Dostupné modely: ${result.models.length}. Vyberte model s podporou obrázků a uložte nastavení.`:'Připojeno, ale seznam je prázdný. Nejprve načtěte model v jeho aplikaci.';
  }catch(e){$('local-model-status').textContent=e.message;}
  finally{localModelsBusy=false;renderRuntime();}
};
window.addEventListener('beforeunload',e=>{if(dirty||recipeDirty){e.preventDefault();e.returnValue='';}});

(async()=>{
  try{
    state=await api('/state');fillForm(recipe,state.settings);$('word-output').value=state.settings.words;
    selected=new Set(state.rows.map(r=>r.id));active=state.rows[0]?.id||null;render();
    if(!state.settings.setup_complete)openSettings();
    setInterval(()=>refresh().catch(()=>{$('job-title').textContent='Spojení s aplikací přerušeno';}),1200);
  }catch(e){toast(e.message,true);}
})();
