/**
 * Admin Dashboard — Data Engineer Frontend
 *
 * Handles:
 * - Listing/filtering learner interactions
 * - Approving/rejecting interactions for few-shot training
 * - Viewing aggregate statistics
 * - Exporting approved examples
 */

const API_BASE = '/api';

// ===== State =====
const state = {
  currentTab: 'interactions',
  currentPage: 0,
  pageSize: 20,
  filterType: '',
  filterStatus: '',
};

// ===== API Helper =====
async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// ===== Tab Navigation =====
document.querySelectorAll('.nav-link[data-tab]').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    state.currentTab = tab;

    // Update nav
    document.querySelectorAll('.nav-link[data-tab]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Update panels
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`tab-panel-${tab}`).classList.add('active');

    // Load data for tab
    if (tab === 'interactions') loadInteractions();
    else if (tab === 'statistics') loadStats();
    else if (tab === 'export') loadExportStats();
  });
});

// ===== Filter handlers =====
document.getElementById('filter-type').addEventListener('change', (e) => {
  state.filterType = e.target.value;
  state.currentPage = 0;
  loadInteractions();
});
document.getElementById('filter-status').addEventListener('change', (e) => {
  state.filterStatus = e.target.value;
  state.currentPage = 0;
  loadInteractions();
});

// ===== Interactions =====
async function loadInteractions() {
  const params = new URLSearchParams();
  if (state.filterType) params.set('type', state.filterType);
  if (state.filterStatus) params.set('status', state.filterStatus);
  params.set('limit', state.pageSize);
  params.set('offset', state.currentPage * state.pageSize);

  try {
    const data = await api(`/admin/flywheel/interactions?${params}`);
    renderInteractions(data.interactions, data.total);
  } catch (e) {
    console.error('Load interactions failed:', e);
    document.getElementById('interactions-list').innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <h3>Failed to Load</h3>
        <p>${e.message}</p>
      </div>
    `;
  }
}

function renderInteractions(interactions, total) {
  const container = document.getElementById('interactions-list');
  const countEl = document.getElementById('interactions-count');

  countEl.textContent = `${total} interaction${total !== 1 ? 's' : ''} found`;

  if (!interactions.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <h3>No Interactions Found</h3>
        <p>Try changing the filters, or wait for learners to interact with the system.</p>
      </div>
    `;
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  container.innerHTML = interactions.map(i => renderInteractionCard(i)).join('');

  // Pagination
  const totalPages = Math.ceil(total / state.pageSize);
  const paginationEl = document.getElementById('pagination');
  if (totalPages > 1) {
    let html = '';
    for (let p = 0; p < totalPages; p++) {
      html += `<button class="page-btn ${p === state.currentPage ? 'active' : ''}" onclick="goToPage(${p})">${p + 1}</button>`;
    }
    paginationEl.innerHTML = html;
  } else {
    paginationEl.innerHTML = '';
  }
}

function renderInteractionCard(i) {
  const typeClass = i.type === 'doubt_resolution' ? 'type-doubt' : 'type-evaluation';
  const typeLabel = i.type === 'doubt_resolution' ? '💬 Doubt' : '📝 Evaluation';
  const statusClass = `status-${i.status}`;
  const cardClass = i.status;

  const time = new Date(i.timestamp).toLocaleString();

  let contentHtml = '';
  if (i.type === 'doubt_resolution') {
    contentHtml = `
      <div class="interaction-field">
        <div class="interaction-field-label">Doubt</div>
        <div class="interaction-field-value">${escapeHtml(i.doubt_text)}</div>
      </div>
      <div class="interaction-field">
        <div class="interaction-field-label">Answer</div>
        <div class="interaction-field-value">${escapeHtml(i.answer_text)}</div>
      </div>
      ${i.misconception_type && i.misconception_type !== 'none' ? `
      <div class="interaction-field">
        <div class="interaction-field-label">Misconception (${i.misconception_type})</div>
        <div class="interaction-field-value">${escapeHtml(i.misconception_explanation)}</div>
      </div>` : ''}
    `;
  } else {
    const scorePercent = Math.round((i.score || 0) * 100);
    contentHtml = `
      <div class="interaction-field">
        <div class="interaction-field-label">Question</div>
        <div class="interaction-field-value">${escapeHtml(i.question_text)}</div>
      </div>
      <div class="interaction-field">
        <div class="interaction-field-label">Student Answer (Score: ${scorePercent}%)</div>
        <div class="interaction-field-value">${escapeHtml(i.student_answer)}</div>
      </div>
      <div class="interaction-field">
        <div class="interaction-field-label">Feedback</div>
        <div class="interaction-field-value">${escapeHtml(i.feedback)}</div>
      </div>
    `;
  }

  const actionsHtml = i.status === 'pending' ? `
    <div class="interaction-actions">
      <input type="text" id="notes-${i.id}" placeholder="Curator notes (optional)..." />
      <button class="btn btn-success btn-sm" onclick="approveInteraction('${i.id}')">✓ Approve</button>
      <button class="btn btn-danger btn-sm" onclick="rejectInteraction('${i.id}')">✗ Reject</button>
    </div>
  ` : `
    <div class="interaction-actions">
      <span style="font-size:0.8rem;color:var(--text-muted)">
        ${i.status === 'approved' ? '✅ Approved' : '❌ Rejected'}
        ${i.curator_notes ? ` — "${i.curator_notes}"` : ''}
      </span>
    </div>
  `;

  return `
    <div class="interaction-card ${cardClass}">
      <div class="interaction-header">
        <div style="display:flex;gap:var(--space-sm);align-items:center">
          <span class="interaction-type-badge ${typeClass}">${typeLabel}</span>
          <span class="status-badge ${statusClass}">${i.status}</span>
        </div>
        <span style="font-size:0.75rem;color:var(--text-muted)">${i.id}</span>
      </div>
      <div class="interaction-meta">
        <span>📚 ${escapeHtml(i.concept_name)}</span>
        <span>👤 ${escapeHtml(i.learner_id)}</span>
        <span>🕐 ${time}</span>
      </div>
      <div class="interaction-content">${contentHtml}</div>
      ${actionsHtml}
    </div>
  `;
}

// ===== Approve / Reject =====
async function approveInteraction(id) {
  const notes = document.getElementById(`notes-${id}`)?.value || '';
  try {
    await api(`/admin/flywheel/approve/${id}`, {
      method: 'POST',
      body: JSON.stringify({ curator_notes: notes }),
    });
    loadInteractions();
  } catch (e) {
    alert(`Approve failed: ${e.message}`);
  }
}

async function rejectInteraction(id) {
  const notes = document.getElementById(`notes-${id}`)?.value || '';
  try {
    await api(`/admin/flywheel/reject/${id}`, {
      method: 'POST',
      body: JSON.stringify({ curator_notes: notes }),
    });
    loadInteractions();
  } catch (e) {
    alert(`Reject failed: ${e.message}`);
  }
}

function goToPage(page) {
  state.currentPage = page;
  loadInteractions();
}

// ===== Statistics =====
async function loadStats() {
  try {
    const stats = await api('/admin/flywheel/stats');
    renderStats(stats);
  } catch (e) {
    console.error('Load stats failed:', e);
  }
}

function renderStats(stats) {
  const grid = document.getElementById('admin-stats-grid');
  grid.innerHTML = `
    <div class="stat-card">
      <div class="stat-icon">📊</div>
      <div class="stat-value">${stats.total_interactions}</div>
      <div class="stat-label">Total Interactions</div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">✅</div>
      <div class="stat-value">${stats.by_status?.approved || 0}</div>
      <div class="stat-label">Approved</div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">⏳</div>
      <div class="stat-value">${stats.by_status?.pending || 0}</div>
      <div class="stat-label">Pending Review</div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">📈</div>
      <div class="stat-value">${stats.approval_rate}%</div>
      <div class="stat-label">Approval Rate</div>
    </div>
  `;

  // Misconceptions chart
  const miscEl = document.getElementById('misconceptions-chart');
  const misc = stats.misconceptions_by_type || {};
  const miscEntries = Object.entries(misc).sort((a, b) => b[1] - a[1]);
  const maxMisc = miscEntries.length > 0 ? miscEntries[0][1] : 1;

  if (miscEntries.length === 0) {
    miscEl.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem">No misconceptions recorded yet.</p>';
  } else {
    miscEl.innerHTML = miscEntries.map(([type, count]) => `
      <div class="chart-bar-row">
        <div class="chart-bar-label">${type}</div>
        <div class="chart-bar-track">
          <div class="chart-bar-fill" style="width:${(count / maxMisc * 100)}%"></div>
        </div>
        <div class="chart-bar-value">${count}</div>
      </div>
    `).join('');
  }

  // Top concepts chart
  const conceptsEl = document.getElementById('concepts-chart');
  const concepts = stats.top_concepts || [];
  const maxConcept = concepts.length > 0 ? concepts[0].count : 1;

  if (concepts.length === 0) {
    conceptsEl.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem">No concept data yet.</p>';
  } else {
    conceptsEl.innerHTML = concepts.map(c => `
      <div class="chart-bar-row">
        <div class="chart-bar-label">${escapeHtml(c.concept)}</div>
        <div class="chart-bar-track">
          <div class="chart-bar-fill" style="width:${(c.count / maxConcept * 100)}%"></div>
        </div>
        <div class="chart-bar-value">${c.count}</div>
      </div>
    `).join('');
  }
}

// ===== Export =====
async function loadExportStats() {
  try {
    const stats = await api('/admin/flywheel/stats');
    document.getElementById('export-approved-count').textContent = stats.by_status?.approved || 0;

    // Count by type among approved
    const data = await api('/admin/flywheel/interactions?status=approved&limit=500');
    const doubts = data.interactions.filter(i => i.type === 'doubt_resolution').length;
    const evals = data.interactions.filter(i => i.type === 'evaluation').length;

    document.getElementById('export-doubt-count').textContent = doubts;
    document.getElementById('export-eval-count').textContent = evals;
  } catch (e) {
    console.error('Load export stats failed:', e);
  }
}

async function exportExamples() {
  const btn = document.getElementById('export-btn');
  const resultEl = document.getElementById('export-result');

  btn.disabled = true;
  btn.textContent = 'Exporting...';

  try {
    const result = await api('/admin/flywheel/export', { method: 'POST' });
    resultEl.className = 'export-result active success';
    resultEl.innerHTML = `
      ✅ Export successful!<br>
      <strong>${result.total_approved}</strong> approved examples exported
      (${result.doubt_examples} doubt, ${result.evaluation_examples} evaluation).<br>
      <span style="font-size:0.8rem;color:var(--text-muted)">
        Saved to backend/data/flywheel/approved_examples.json — agents will load these on next startup.
      </span>
    `;
    loadExportStats();
  } catch (e) {
    resultEl.className = 'export-result active';
    resultEl.style.background = 'var(--danger-bg)';
    resultEl.style.color = 'var(--danger)';
    resultEl.textContent = `Export failed: ${e.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Export & Save';
  }
}

// ===== Utilities =====
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// Make functions available globally
window.loadInteractions = loadInteractions;
window.approveInteraction = approveInteraction;
window.rejectInteraction = rejectInteraction;
window.goToPage = goToPage;
window.exportExamples = exportExamples;

// ===== Initial Load =====
loadInteractions();
