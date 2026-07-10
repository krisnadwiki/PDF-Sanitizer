/* ── app.js – PDF Sanitizer @krisnadwiki ──────────────────────────────────── */
'use strict';

// ── State ────────────────────────────────────────────────────────────────────
const state = {
  sid:          null,       // session id
  files:        [],         // [{fid, name, size}] antrian upload
  scanResults:  [],         // [{fid, name, ...scan data}]
  selectedFids: new Set(),  // fid yang dicentang di tabel scan
  dpi:          150,
  currentJobId: null,
  history:      JSON.parse(localStorage.getItem('sanitizeHistory') || '[]'),
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ── Navigation ────────────────────────────────────────────────────────────────
const TAB_META = {
  upload:   { title: 'Upload PDF',          sub: 'Unggah file PDF yang ingin diproses' },
  scan:     { title: 'Scan & Analisa',       sub: 'Periksa kandungan berbahaya dalam PDF' },
  sanitize: { title: 'Sanitize',             sub: 'Hapus URI, JavaScript, dan konstruksi berbahaya' },
  history:  { title: 'Riwayat',              sub: 'Daftar pekerjaan yang sudah selesai' },
};

$$('.nav-item').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    switchTab(el.dataset.tab);
  });
});

function switchTab(tab) {
  $$('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
  $$('.tab-content').forEach(el => el.classList.toggle('active', el.id === `tab-${tab}`));
  $('pageTitle').textContent = TAB_META[tab].title;
  $('pageSub').textContent   = TAB_META[tab].sub;
  if (tab === 'history') renderHistory();
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type = 'info', duration = 3500) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icon = type === 'success' ? '✔' : type === 'error' ? '✖' : 'ℹ';
  el.innerHTML = `<span>${icon}</span><span>${msg}</span>`;
  $('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtSize(bytes) {
  if (bytes < 1024)       return bytes + ' B';
  if (bytes < 1048576)    return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(1) + ' GB';
}

function fmtTime(ts) {
  return new Date(ts).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function iconBool(val, trueClass = 'tag-red', falseClass = 'tag-green') {
  if (val) return `<span class="tag ${trueClass}">✔</span>`;
  return `<span class="tag ${falseClass}">–</span>`;
}

// ── ════════════════════════════════════════════════════════════════════════ ──
// UPLOAD TAB
// ── ════════════════════════════════════════════════════════════════════════ ──

const dropzone  = $('dropzone');
const fileInput = $('fileInput');

// Klik area dropzone (bukan button) → buka file picker
dropzone.addEventListener('click', e => {
  // Jangan trigger jika yang diklik adalah tombol "Pilih File"
  if (e.target.closest('#btnPickFile')) return;
  fileInput.click();
});

// Tombol "Pilih File" — stop propagation agar event tidak naik ke dropzone
$('btnPickFile').addEventListener('click', e => {
  e.stopPropagation();
  fileInput.click();
});

dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault(); dropzone.classList.remove('over');
  addFiles([...e.dataTransfer.files]);
});
fileInput.addEventListener('change', () => { addFiles([...fileInput.files]); fileInput.value = ''; });

function addFiles(files) {
  const pdfs = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
  if (!pdfs.length) { toast('Hanya file PDF yang diterima.', 'error'); return; }
  pdfs.forEach(f => {
    if (!state.files.find(x => x.name === f.name && x.size === f.size)) {
      state.files.push({ file: f, name: f.name, size: f.size, id: crypto.randomUUID() });
    }
  });
  renderUploadQueue();
}

function renderUploadQueue() {
  const card = $('uploadQueueCard');
  const list = $('uploadList');
  if (!state.files.length) { card.style.display = 'none'; return; }
  card.style.display = '';
  $('uploadCount').textContent = state.files.length + ' file';
  list.innerHTML = state.files.map(f => `
    <div class="upload-item" data-id="${f.id}">
      <span class="upload-item-icon">
        <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"/></svg>
      </span>
      <span class="upload-item-name" title="${f.name}">${f.name}</span>
      <span class="upload-item-size">${fmtSize(f.size)}</span>
      <button class="upload-item-remove" data-id="${f.id}" title="Hapus">
        <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
      </button>
    </div>`).join('');

  list.querySelectorAll('.upload-item-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      state.files = state.files.filter(f => f.id !== btn.dataset.id);
      renderUploadQueue();
    });
  });
}

$('btnClearQueue').addEventListener('click', () => { state.files = []; renderUploadQueue(); });

$('btnUpload').addEventListener('click', async () => {
  if (!state.files.length) return;
  const btn = $('btnUpload');
  btn.disabled = true;
  btn.textContent = 'Mengupload…';

  const form = new FormData();
  state.files.forEach(f => form.append('files', f.file));
  if (state.sid) form.append('sid', state.sid);  // tambahkan ke existing session

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: form });
    const data = await res.json();
    state.sid = data.sid;
    // Merge uploaded ke scanResults placeholder
    data.uploaded.forEach(u => {
      if (!state.scanResults.find(r => r.fid === u.fid)) {
        state.scanResults.push({ fid: u.fid, name: u.name, size_fmt: fmtSize(u.size), scanned: false });
      }
    });
    toast(`${data.uploaded.length} file berhasil diupload.`, 'success');
    state.files = [];
    renderUploadQueue();
    switchTab('scan');
    renderScanTable();
  } catch (e) {
    toast('Upload gagal: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path d="M10 3a1 1 0 01.707.293l4 4a1 1 0 01-1.414 1.414L11 6.414V14a1 1 0 11-2 0V6.414L6.707 8.707A1 1 0 015.293 7.293l4-4A1 1 0 0110 3z"/></svg> Upload &amp; Lanjutkan ke Scan`;
  }
});

// Clear session
$('btnClearSession').addEventListener('click', async () => {
  if (!confirm('Hapus semua file yang sudah diupload di sesi ini?')) return;
  if (state.sid) {
    await fetch(`/api/session/${state.sid}`, { method: 'DELETE' });
  }
  state.sid = null;
  state.files = [];
  state.scanResults = [];
  state.selectedFids.clear();
  renderUploadQueue();
  renderScanTable();
  toast('Sesi dibersihkan.', 'info');
});

// ── ════════════════════════════════════════════════════════════════════════ ──
// SCAN TAB
// ── ════════════════════════════════════════════════════════════════════════ ──

let scanFilter = 'all';

$('btnScan').addEventListener('click', async () => {
  if (!state.sid) { toast('Tidak ada file. Upload dulu.', 'error'); return; }
  const btn = $('btnScan');
  btn.disabled = true;
  $('scanProgressWrap').style.display = '';
  $('scanProgressBar').style.width = '0%';
  $('scanProgressLabel').textContent = 'Memulai scan…';

  try {
    const res  = await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sid: state.sid }),
    });
    const data = await res.json();
    if (data.error) { toast(data.error, 'error'); return; }

    // Merge hasil ke state
    data.results.forEach(r => {
      const idx = state.scanResults.findIndex(x => x.fid === r.fid);
      if (idx >= 0) state.scanResults[idx] = { ...state.scanResults[idx], ...r, scanned: true };
      else state.scanResults.push({ ...r, scanned: true });
    });

    $('scanProgressBar').style.width = '100%';
    $('scanProgressLabel').textContent = `Scan selesai — ${data.results.length} file.`;
    $('btnExportCsv').disabled = false;
    $('scanStats').style.display = '';
    updateScanStats();
    renderScanTable();
    toast('Scan selesai.', 'success');
  } catch (e) {
    toast('Scan gagal: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    setTimeout(() => $('scanProgressWrap').style.display = 'none', 2000);
  }
});

// Filter pills
$$('#scanFilter .pill').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('#scanFilter .pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    scanFilter = btn.dataset.filter;
    renderScanTable();
  });
});

// Select all checkbox
$('chkAll').addEventListener('change', e => {
  const visible = getVisibleRows();
  visible.forEach(r => {
    const chk = r.querySelector('input[type=checkbox]');
    if (chk) {
      chk.checked = e.target.checked;
      const fid = chk.dataset.fid;
      if (e.target.checked) state.selectedFids.add(fid);
      else state.selectedFids.delete(fid);
    }
  });
  updateSelectionUI();
});

function getVisibleRows() {
  return [...$$('#scanTbody tr:not(.empty-row)')];
}

function updateSelectionUI() {
  const n = state.selectedFids.size;
  $('scanSelection').textContent = `${n} dipilih`;
  $('btnSanitizeSelected').disabled = n === 0;
}

function updateScanStats() {
  const scanned = state.scanResults.filter(r => r.scanned);
  const unsafe  = scanned.filter(r => !r.safe);
  const safe    = scanned.filter(r => r.safe);
  const uri     = scanned.filter(r => r.has_uri);
  const js      = scanned.filter(r => r.has_js);
  $('statTotal').textContent  = scanned.length;
  $('statUnsafe').textContent = unsafe.length;
  $('statSafe').textContent   = safe.length;
  $('statUri').textContent    = uri.length;
  $('statJs').textContent     = js.length;
}

function renderScanTable() {
  const tbody = $('scanTbody');
  const scanned = state.scanResults.filter(r => r.scanned);

  let rows = scanned;
  if (scanFilter === 'unsafe') rows = scanned.filter(r => !r.safe);
  if (scanFilter === 'safe')   rows = scanned.filter(r => r.safe);

  if (!rows.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="9">
      ${scanned.length ? 'Tidak ada file yang cocok filter.' : 'Belum ada data. Upload dan scan file terlebih dahulu.'}
    </td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const checked = state.selectedFids.has(r.fid) ? 'checked' : '';
    const rowCls  = (!r.safe && !r.error) ? 'row-unsafe' : '';
    const status  = r.error
      ? `<span class="badge badge-red">✖ Error</span>`
      : r.safe
        ? `<span class="badge badge-green">✔ Aman</span>`
        : `<span class="badge badge-orange">⚠ Bermasalah</span>`;
    const issues  = (r.issues || []).map(i => `<span class="tag tag-red">${i}</span>`).join('') || '–';
    return `
      <tr class="${rowCls}">
        <td><input type="checkbox" data-fid="${r.fid}" ${checked} /></td>
        <td title="${r.name}" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.name}</td>
        <td class="center">${r.pages ?? '–'}</td>
        <td style="text-align:right">${r.size_fmt ?? '–'}</td>
        <td class="center">${iconBool(r.has_uri)}</td>
        <td class="center">${iconBool(r.has_js, 'tag-purple', 'tag-green')}</td>
        <td class="center">${iconBool(r.has_annot, 'tag-orange', 'tag-green')}</td>
        <td class="center">${iconBool(r.has_embedded, 'tag-orange', 'tag-green')}</td>
        <td class="center">${status}</td>
      </tr>`;
  }).join('');

  // Bind checkbox per baris
  tbody.querySelectorAll('input[type=checkbox]').forEach(chk => {
    chk.addEventListener('change', e => {
      const fid = e.target.dataset.fid;
      if (e.target.checked) state.selectedFids.add(fid);
      else state.selectedFids.delete(fid);
      updateSelectionUI();
    });
  });
  updateSelectionUI();
}

// Export CSV
$('btnExportCsv').addEventListener('click', () => {
  const rows = state.scanResults.filter(r => r.scanned);
  if (!rows.length) return;
  const cols = ['name','pages','size_fmt','has_uri','has_js','has_annot','has_embedded','safe','issues','error'];
  const csv  = [cols.join(',')];
  rows.forEach(r => {
    csv.push(cols.map(c => {
      const v = c === 'issues' ? (r[c] || []).join(';') : (r[c] ?? '');
      return `"${String(v).replace(/"/g,'""')}"`;
    }).join(','));
  });
  const blob = new Blob([csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a'); a.href = url;
  a.download = `scan_${Date.now()}.csv`; a.click();
  URL.revokeObjectURL(url);
});

// Sanitize selected button (from scan tab)
$('btnSanitizeSelected').addEventListener('click', () => {
  if (!state.selectedFids.size) return;
  switchTab('sanitize');
  updateSanitizePanel();
});

// ── ════════════════════════════════════════════════════════════════════════ ──
// SANITIZE TAB
// ── ════════════════════════════════════════════════════════════════════════ ──

// DPI buttons
$$('#dpiOptions .dpi-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('#dpiOptions .dpi-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.dpi = parseInt(btn.dataset.dpi);
  });
});

function updateSanitizePanel() {
  const fids = [...state.selectedFids];
  const box  = $('sanitizeFileSummary');
  if (!fids.length) {
    box.innerHTML = '<span class="text-muted">Pilih file di tab Scan terlebih dahulu</span>';
    $('btnStartSanitize').disabled = true;
    return;
  }
  const names = fids.map(fid => {
    const r = state.scanResults.find(x => x.fid === fid);
    return r ? r.name : fid;
  });
  const unsafe = names.filter(n => {
    const r = state.scanResults.find(x => x.name === n);
    return r && !r.safe;
  });
  box.innerHTML = `
    <div class="fsum-item"><span>Total dipilih</span><strong>${fids.length} file</strong></div>
    <div class="fsum-item"><span>Bermasalah</span><strong style="color:var(--red)">${unsafe.length} file</strong></div>
    <div style="margin-top:8px;font-size:11px;color:var(--gray-400)">${names.slice(0, 5).join(', ')}${names.length > 5 ? ` dan ${names.length - 5} lainnya…` : ''}</div>`;
  $('btnStartSanitize').disabled = false;
}

// Jika tab sanitize dibuka langsung, sync panel
document.querySelector('[data-tab="sanitize"]').addEventListener('click', () => {
  updateSanitizePanel();
});

$('btnStartSanitize').addEventListener('click', startSanitize);

async function startSanitize() {
  const fids = [...state.selectedFids];
  if (!fids.length || !state.sid) { toast('Tidak ada file dipilih.', 'error'); return; }

  // Tampilkan panel progress
  $('sanitizeConfig').style.display = 'none';
  $('sanitizeProgressCard').style.display = '';
  $('sanitizeDownloadRow').style.display = 'none';
  $('sanitizeLog').innerHTML = '';
  $('sanitizeProgressBar').style.width = '0%';
  $('sanitizePct').textContent = '0%';
  $('sanitizeCount').textContent = `0 / ${fids.length}`;
  $('sanitizeEta').textContent = '–';
  $('sanitizeCurrentFile').textContent = 'Memulai…';
  $('sanitizeStatusBadge').textContent = 'Memproses…';
  $('sanitizeStatusBadge').className = 'badge badge-orange';
  $('sSuccess').textContent = '0';
  $('sFailed').textContent  = '0';
  $('sTotal').textContent   = fids.length;

  try {
    const res  = await fetch('/api/sanitize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sid: state.sid, fids, dpi: state.dpi }),
    });
    const data = await res.json();
    if (data.error) { toast(data.error, 'error'); return; }

    state.currentJobId = data.job_id;
    connectWebSocket(data.job_id, fids.length);
  } catch (e) {
    toast('Gagal memulai sanitize: ' + e.message, 'error');
  }
}

function connectWebSocket(jobId, total) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws/${jobId}`);

  ws.onmessage = e => {
    const msg = JSON.parse(e.data);

    if (msg.type === 'progress') {
      const pct = msg.pct;
      $('sanitizeProgressBar').style.width = pct + '%';
      $('sanitizePct').textContent   = pct + '%';
      $('sanitizeCount').textContent = `${msg.done} / ${msg.total}`;
      $('sanitizeEta').textContent   = msg.eta;
      if (msg.entry) {
        $('sanitizeCurrentFile').textContent = msg.entry.name;
        // Update counters
        const job = jobs_local[jobId] || (jobs_local[jobId] = { success: 0, failed: 0 });
        if (msg.entry.status === 'success') job.success++;
        else job.failed++;
        $('sSuccess').textContent = job.success;
        $('sFailed').textContent  = job.failed;
        appendLog(msg.entry);
      }
    }

    if (msg.type === 'done') {
      $('sanitizeProgressBar').style.width = '100%';
      $('sanitizePct').textContent   = '100%';
      $('sanitizeCount').textContent = `${msg.total} / ${msg.total}`;
      $('sanitizeEta').textContent   = '–';
      $('sanitizeCurrentFile').textContent = 'Selesai.';
      $('sanitizeStatusBadge').textContent = 'Selesai';
      $('sanitizeStatusBadge').className   = 'badge badge-green';
      $('sSuccess').textContent = msg.success;
      $('sFailed').textContent  = msg.failed;
      $('sTotal').textContent   = msg.total;
      $('sanitizeDownloadRow').style.display = '';

      // Download button
      $('btnDownload').onclick = () => {
        window.location = `/api/download/${msg.job_id}`;
      };

      // Simpan ke history
      addHistory({
        job_id:    msg.job_id,
        total:     msg.total,
        success:   msg.success,
        failed:    msg.failed,
        dpi:       state.dpi,
        timestamp: Date.now(),
      });

      toast(`Sanitize selesai — ${msg.success} sukses, ${msg.failed} gagal.`, msg.failed > 0 ? 'info' : 'success');
      ws.close();
    }
  };

  ws.onerror = () => toast('Koneksi WebSocket terputus.', 'error');

  // Keep-alive ping
  const ping = setInterval(() => { if (ws.readyState === 1) ws.send('ping'); else clearInterval(ping); }, 15000);
}

// Counter lokal per job (WS tidak memiliki state)
const jobs_local = {};

function appendLog(entry) {
  const log = $('sanitizeLog');
  const cls = entry.status === 'success' ? 'log-success' : entry.status === 'failed' ? 'log-failed' : 'log-skip';
  const icon = entry.status === 'success' ? '✔' : entry.status === 'failed' ? '✖' : '⏭';
  const ts   = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const line = document.createElement('div');
  line.className = `log-line ${cls}`;
  line.innerHTML = `<span class="log-ts">[${ts}]</span>${icon} ${entry.name} <span style="opacity:.6">— ${entry.message}</span>`;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

$('btnNewJob').addEventListener('click', () => {
  $('sanitizeConfig').style.display = '';
  $('sanitizeProgressCard').style.display = 'none';
  state.selectedFids.clear();
  updateSelectionUI();
  updateSanitizePanel();
  switchTab('scan');
});

// ── ════════════════════════════════════════════════════════════════════════ ──
// HISTORY TAB
// ── ════════════════════════════════════════════════════════════════════════ ──

function addHistory(entry) {
  state.history.unshift(entry);
  if (state.history.length > 50) state.history = state.history.slice(0, 50);
  localStorage.setItem('sanitizeHistory', JSON.stringify(state.history));
}

function renderHistory() {
  const list = $('historyList');
  if (!state.history.length) {
    list.innerHTML = '<div class="empty-state">Belum ada riwayat proses.</div>';
    return;
  }
  list.innerHTML = state.history.map(h => `
    <div class="history-item">
      <div>
        <div style="font-weight:600;font-size:13px">Job ${h.job_id.slice(0,8)}</div>
        <div class="history-meta">${fmtTime(h.timestamp)} · DPI ${h.dpi} · ${h.total} file</div>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <span class="badge badge-green">✔ ${h.success}</span>
        ${h.failed > 0 ? `<span class="badge badge-red">✖ ${h.failed}</span>` : ''}
        <a href="/api/download/${h.job_id}" class="btn btn-ghost btn-sm" title="Download hasil">
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
          ZIP
        </a>
      </div>
    </div>`).join('');
}

$('btnClearHistory').addEventListener('click', () => {
  state.history = [];
  localStorage.removeItem('sanitizeHistory');
  renderHistory();
});

// ── Mobile sidebar toggle ─────────────────────────────────────────────────
const sidebar        = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const btnHamburger   = document.getElementById('btnHamburger');

function openSidebar() {
  sidebar.classList.add('open');
  sidebarOverlay.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeSidebar() {
  sidebar.classList.remove('open');
  sidebarOverlay.classList.remove('active');
  document.body.style.overflow = '';
}

btnHamburger.addEventListener('click', () => {
  sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
});

sidebarOverlay.addEventListener('click', closeSidebar);

// Tutup sidebar otomatis saat nav item diklik di mobile
$$('.nav-item').forEach(el => {
  el.addEventListener('click', () => {
    if (window.innerWidth <= 768) closeSidebar();
  });
});
