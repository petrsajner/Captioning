'use strict';

class FolderPicker {
  constructor() {
    this.listing = null;
    this.history = [];
    this.historyIndex = -1;
    this.nodes = new Map();
    this.roots = [];
    this.serial = 0;
    this.loading = false;
    this.importing = false;
    $('folder-back').onclick = () => this.travel(-1);
    $('folder-forward').onclick = () => this.travel(1);
    $('folder-up').onclick = () => this.up();
    $('folder-home').onclick = () => this.go('~');
    $('folder-refresh').onclick = () => this.refresh();
    $('folder-go').onclick = () => this.go($('browse-path').value.trim());
    $('browse-path').addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); $('folder-go').click(); }
    });
    $('folder-breadcrumbs').addEventListener('click', e => {
      const b = e.target.closest('[data-path]');
      if (b) this.go(b.dataset.path);
    });
    $('folder-grid').addEventListener('click', e => {
      const b = e.target.closest('[data-path]');
      if (b && !this.loading) this.go(b.dataset.path);
    });
    $('folder-grid').addEventListener('error', e => {
      if (e.target.tagName === 'IMG') {
        e.target.parentElement.classList.add('preview-failed');
        e.target.parentElement.title = 'Náhled není dostupný; soubor se zkontroluje při importu.';
      }
    }, true);
    $('folder-roots').addEventListener('click', e => {
      const toggle = e.target.closest('[data-tree-toggle]');
      const label = e.target.closest('[data-tree-open]');
      if (toggle) this.toggle(toggle.dataset.treeToggle);
      else if (label) this.go(label.dataset.treeOpen);
    });
    $('folder-roots').addEventListener('keydown', e => this.treeKey(e));
    $('folder-prev').onclick = () => this.page(-1);
    $('folder-next').onclick = () => this.page(1);
    $('use-folder').onclick = () => this.confirm();
    document.addEventListener('keydown', e => {
      if (!$('folder-dialog').open || e.defaultPrevented) return;
      if (e.altKey && ['ArrowLeft', 'ArrowRight', 'ArrowUp'].includes(e.key)) {
        e.preventDefault();
        if (e.key === 'ArrowUp') this.up();
        else this.travel(e.key === 'ArrowLeft' ? -1 : 1);
      } else if (e.key === 'F5') {
        e.preventDefault(); this.refresh();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'l') {
        e.preventDefault(); $('browse-path').focus(); $('browse-path').select();
      }
    });
    $('folder-dialog').addEventListener('cancel', e => { if (this.importing) e.preventDefault(); });
  }

  key(path) { return path.replace(/\\/g, '/').replace(/\/$/, '').toLowerCase(); }
  same(a, b) { return this.key(a) === this.key(b); }
  node(descriptor) {
    const key = this.key(descriptor.path);
    if (!this.nodes.has(key)) this.nodes.set(key, {...descriptor, children:null, expanded:false, pending:null, error:''});
    return this.nodes.get(key);
  }
  setChildren(node, folders) {
    node.children = folders.map(f => { this.node(f); return this.key(f.path); });
    node.error = '';
  }
  open() {
    $('folder-recursive').checked = $('recursive').checked;
    $('folder-dialog').showModal();
    this.go(this.listing?.path || '', {record:false});
  }
  controls() {
    const blocked = this.loading || this.importing;
    $('folder-back').disabled = blocked || this.historyIndex <= 0;
    $('folder-forward').disabled = blocked || this.historyIndex + 1 >= this.history.length;
    $('folder-up').disabled = blocked || !this.listing || this.same(this.listing.path, this.listing.parent);
    $('folder-refresh').disabled = blocked || !this.listing;
    $('folder-home').disabled = blocked;
    $('folder-go').disabled = blocked;
    $('use-folder').disabled = blocked || !this.listing;
    $('folder-prev').disabled = blocked || !this.listing || this.listing.page === 0;
    $('folder-next').disabled = blocked || !this.listing || this.listing.page + 1 >= this.listing.pages;
    $('folder-grid').classList.toggle('is-loading', blocked);
    $('folder-grid').inert = blocked;
    $('folder-roots').inert = this.importing;
    $('folder-breadcrumbs').inert = blocked;
    $('browse-path').disabled = blocked;
  }
  error(message) { $('folder-error').textContent = message; $('folder-error').hidden = !message; }

  async go(path, {page=0, record=true, historyIndex=null}={}) {
    if (this.importing) return;
    const serial = ++this.serial;
    this.loading = true; this.error(''); this.controls();
    $('folder-summary').textContent = 'Načítám obsah složky…';
    try {
      const listing = await api('/folders', {path, page});
      if (serial !== this.serial) return;
      this.listing = listing;
      if (historyIndex !== null) this.historyIndex = historyIndex;
      else if (!this.history.length) { this.history = [listing.path]; this.historyIndex = 0; }
      else if (record && !this.same(this.history[this.historyIndex], listing.path)) {
        this.history = this.history.slice(0, this.historyIndex + 1);
        this.history.push(listing.path); this.historyIndex++;
      }
      $('browse-path').value = listing.path;
      this.renderContents();
      this.renderBreadcrumbs();
      this.prepareTree(listing);
      this.revealTree(listing, serial);
    } catch (e) {
      if (serial !== this.serial) return;
      // Failed destinations do not replace the open folder or advance history.
      if (this.listing) {
        $('browse-path').value = this.listing.path;
        this.renderContents();
      } else $('folder-summary').textContent = 'Složku se nepodařilo otevřít. Zvolte Domů nebo zadejte jinou cestu.';
      this.error(e.message);
    } finally {
      if (serial === this.serial) { this.loading = false; this.controls(); }
    }
  }
  travel(delta) {
    const index = this.historyIndex + delta;
    if (!this.loading && index >= 0 && index < this.history.length)
      this.go(this.history[index], {record:false, historyIndex:index});
  }
  up() { if (!this.loading && this.listing && !this.same(this.listing.path, this.listing.parent)) this.go(this.listing.parent); }
  page(delta) { if (!this.loading && this.listing) this.go(this.listing.path, {page:this.listing.page+delta, record:false}); }
  refresh() {
    if (this.loading || !this.listing) return;
    // Refresh the active chain without erasing other expanded branches.
    for (const part of this.listing.breadcrumbs) this.node(part).children = null;
    this.go(this.listing.path, {page:this.listing.page, record:false});
  }
  renderContents() {
    const listing = this.listing;
    $('folder-summary').textContent = `Obrázky: ${listing.image_count} · Podsložky: ${listing.folders.length}` +
      (listing.image_count ? '' : ' · V této složce nejsou podporované obrázky.');
    $('folder-grid').innerHTML = listing.folders.map(f =>
      `<button class="folder-entry" data-path="${esc(f.path)}" title="Otevřít ${esc(f.name)}"><span class="folder-symbol">▰</span><span>${esc(f.name)}</span></button>`).join('') +
      listing.images.map(im => `<figure class="folder-thumbnail"><div><img loading="lazy" src="/api/folder-image/${im.id}" alt="${esc(im.name)}"></div><figcaption title="${esc(im.name)}">${esc(im.name)}</figcaption></figure>`).join('');
    $('folder-pager').hidden = listing.pages <= 1;
    $('folder-page').textContent = `${listing.page+1} / ${listing.pages}`;
    $('use-folder').textContent = `Použít tuto složku (${listing.image_count})`;
    document.querySelector('.folder-contents').scrollTop = 0;
  }
  renderBreadcrumbs() {
    const focusedPath = $('folder-breadcrumbs').contains(document.activeElement) ? document.activeElement.dataset.path : null;
    $('folder-breadcrumbs').innerHTML = this.listing.breadcrumbs.map((b, i, all) =>
      `${i ? '<span class="crumb-separator" aria-hidden="true">›</span>' : ''}<button data-path="${esc(b.path)}" title="${esc(b.path)}" ${i===all.length-1?'aria-current="location"':''}>${esc(b.name)}</button>`).join('');
    $('folder-breadcrumbs').scrollLeft = $('folder-breadcrumbs').scrollWidth;
    if (focusedPath) [...$('folder-breadcrumbs').querySelectorAll('[data-path]')]
      .find(b => this.same(b.dataset.path, focusedPath))?.focus({preventScroll:true});
  }

  prepareTree(listing) {
    this.roots = listing.roots.filter(r => !this.same(r.path, listing.roots[0].path)).map(r => this.node(r));
    const chain = listing.breadcrumbs;
    if (!this.roots.some(r => this.same(r.path, chain[0].path))) this.roots.push(this.node(chain[0]));
    for (let i = 0; i < chain.length; i++) {
      const node = this.node(chain[i]);
      if (i < chain.length - 1) {
        node.expanded = true;
        const child = this.node(chain[i+1]);
        // A temporary known path keeps the selection visible while siblings load.
        node.knownChild = this.key(child.path);
      }
    }
    const current = this.node(chain[chain.length-1]);
    this.setChildren(current, listing.folders);
    current.expanded = true;
    this.renderTree();
  }
  async children(node) {
    if (node.children !== null) return;
    if (node.pending) return node.pending;
    node.pending = (async () => {
      try {
        const result = await api('/folder-tree', {path:node.path});
        this.setChildren(node, result.folders);
      } catch (e) { node.error = e.message; }
      finally { node.pending = null; }
    })();
    return node.pending;
  }
  async revealTree(listing, serial) {
    const chain = listing.breadcrumbs.slice(0, -1).map(d => this.node(d));
    await Promise.all(chain.map(node => this.children(node)));
    if (serial !== this.serial) return;
    this.renderTree();
    const selected = $('folder-roots').querySelector('[aria-current="location"]');
    selected?.scrollIntoView({block:'nearest', inline:'nearest'});
  }
  renderTree() {
    const focused = document.activeElement?.dataset?.treeOpen;
    const renderNode = (node, level, seen=new Set()) => {
      const key = this.key(node.path);
      if (seen.has(key)) return '';
      const visited = new Set(seen); visited.add(key);
      const selected = this.listing && this.same(node.path, this.listing.path);
      const childKeys = node.children ?? (node.knownChild ? [node.knownChild] : []);
      const expandable = node.children === null || childKeys.length > 0;
      return `<div role="treeitem" aria-level="${level}" aria-selected="${!!selected}" ${expandable?`aria-expanded="${node.expanded}"`:''}>
        <div class="tree-row ${selected?'selected':''}" style="--tree-level:${level-1}">
          <button class="tree-toggle" data-tree-toggle="${esc(node.path)}" tabindex="-1" ${expandable?'':'disabled'} aria-label="${node.expanded?'Sbalit':'Rozbalit'} ${esc(node.name)}">${expandable?(node.pending?'…':node.expanded?'▾':'▸'):''}</button>
          <button class="tree-label" data-tree-open="${esc(node.path)}" title="${esc(node.path)}" ${selected?'aria-current="location"':''}>${esc(node.name)}</button>
        </div>
        ${node.expanded&&node.error?`<div class="tree-error" title="${esc(node.error)}">Nelze načíst. Kliknutím na šipku zkuste znovu.</div>`:''}
        ${node.expanded&&childKeys.length?`<div role="group">${childKeys.map(k=>this.nodes.get(k)).filter(Boolean).map(n=>renderNode(n,level+1,visited)).join('')}</div>`:''}
      </div>`;
    };
    $('folder-roots').innerHTML = `<div class="tree-heading">STROM SLOŽEK</div><div role="tree" aria-label="Složky na discích">${this.roots.map(r=>renderNode(r,1)).join('')}</div>`;
    if (focused) this.focusNode(focused, false);
  }
  focusNode(path, scroll=true) {
    const label = [...$('folder-roots').querySelectorAll('[data-tree-open]')].find(b => this.same(b.dataset.treeOpen, path));
    if (label) { label.focus({preventScroll:!scroll}); if (scroll) label.scrollIntoView({block:'nearest', inline:'nearest'}); }
  }
  async toggle(path, expand=null) {
    const node = this.nodes.get(this.key(path));
    if (!node) return;
    if (node.error) { node.error=''; node.expanded=true; }
    else node.expanded = expand ?? !node.expanded;
    if (node.expanded && node.children === null) {
      const request = this.children(node); this.renderTree();
      await request;
    }
    this.renderTree();
  }
  treeKey(e) {
    const label = e.target.closest('[data-tree-open]');
    if (!label || e.altKey) return;
    const node = this.nodes.get(this.key(label.dataset.treeOpen));
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      if (!node.expanded) this.toggle(node.path, true);
      else if (node.children?.length) this.focusNode(this.nodes.get(node.children[0]).path);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      if (node.expanded && (node.children === null || node.children.length)) this.toggle(node.path, false);
      else {
        const parent = label.closest('[role="treeitem"]').parentElement.closest('[role="treeitem"]');
        parent?.querySelector('.tree-label')?.focus();
      }
    } else if (['ArrowDown','ArrowUp','Home','End'].includes(e.key)) {
      e.preventDefault();
      const labels = [...$('folder-roots').querySelectorAll('.tree-label')];
      const index = e.key==='Home'?0:e.key==='End'?labels.length-1:labels.indexOf(label)+(e.key==='ArrowDown'?1:-1);
      labels[Math.max(0,Math.min(index,labels.length-1))]?.focus();
    }
  }
  async confirm() {
    if (!this.listing || this.loading || this.importing) return;
    const path = this.listing.path;
    this.importing=true; this.controls(); this.error('');
    $('recursive').checked = $('folder-recursive').checked;
    try { if (await doImport([],path) !== false) $('folder-dialog').close(); }
    catch (e) { this.error(e.message); }
    finally { this.importing=false; this.controls(); }
  }
}

const folderPicker = new FolderPicker();
