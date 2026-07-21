/* ── Auth ── */
async function initAuth() {
  try {
    const res = await fetch('/.auth/me');
    const data = await res.json();
    const principal = data.clientPrincipal;
    if (!principal) {
      window.location.href = '/.auth/login/aad';
      return false;
    }
    const email = principal.userDetails || principal.userId || 'User';
    document.getElementById('userAvatar').textContent = email.charAt(0).toUpperCase();
    document.getElementById('userEmail').textContent = email;
  } catch {
    // Local dev without SWA CLI — auth endpoint unavailable
    document.getElementById('userEmail').textContent = 'Local Dev';
    document.getElementById('userAvatar').textContent = 'L';
  }
  return true;
}

/* ── Mobile sidebar toggle ── */
function openSidebar() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebarOverlay').classList.add('open');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('open');
}
document.getElementById('btnMenuToggle').addEventListener('click', openSidebar);
document.getElementById('sidebarOverlay').addEventListener('click', closeSidebar);

/* ── State ── */
let currentNotebookId = null;
let notebooks = [];
const notebookDomCache = {};

/* ── Helpers ── */
const $ = id => document.getElementById(id);
const useSearch = () => $('useSearchToggle').checked;

function showToast(msg, isError = false) {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast' + (isError ? ' error' : '');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add('hidden'), 3000);
}

async function api(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== null) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function renderMarkdown(text) {
  return marked.parse(text || '');
}

function updateExerciseCount(grammarCard) {
  const count = grammarCard.querySelectorAll('.exercise-card').length;
  const el = grammarCard.querySelector('.exercise-count');
  if (el) el.textContent = count > 0 ? `${count} exercise${count === 1 ? '' : 's'}` : '';
}

function updateQaCount(grammarCard) {
  const count = grammarCard.querySelectorAll('.qa-card').length;
  const el = grammarCard.querySelector('.qa-count');
  if (el) el.textContent = count > 0 ? `${count} Q&A` : '';
}

function scoreColor(score) {
  if (score >= 9) return '#50c878';
  if (score >= 7) return '#a8d850';
  if (score >= 5) return '#f0c060';
  if (score >= 3) return '#f09040';
  return '#e05555';
}

function relativeTime(isoStr) {
  if (!isoStr) return '';
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function updateRememberChip(card, score, testedAt) {
  const chip = card.querySelector('.remember-chip');
  if (!chip) return;
  if (score == null) { chip.textContent = ''; return; }
  chip.textContent = `\u{1F9E0} ${score}/10`;
  chip.style.color = scoreColor(score);
  chip.title = `Last self-test: ${score}/10 · ${relativeTime(testedAt)}`;
}

function buildRememberHistoryItem(test) {
  const div = document.createElement('div');
  div.className = 'remember-history-item';
  div.dataset.id = test.id;
  const color = scoreColor(test.score);
  div.innerHTML = `
    <div class="rh-item-header">
      <span class="rh-score" style="color:${color}">${test.score}/10</span>
      <span class="rh-date">${relativeTime(test.created_at)}</span>
      <button class="btn-icon danger btn-delete-test" title="Delete">&#128465;</button>
    </div>
    <div class="rh-answer">"${escHtml(test.user_answer)}"</div>
    <div class="rh-feedback">${renderMarkdown(test.ai_feedback || '')}</div>
  `;
  return div;
}

function buildRememberPanel(card, section, tests) {
  const panel = card.querySelector('.remember-panel');
  const lastInfo = panel.querySelector('.remember-last-info');
  const toggleBtn = panel.querySelector('.btn-toggle-test');
  const form = panel.querySelector('.remember-form');
  const input = panel.querySelector('.remember-input');
  const submitBtn = panel.querySelector('.btn-submit-test');
  const cancelBtn = panel.querySelector('.btn-cancel-test');
  const result = panel.querySelector('.remember-result');
  const scoreBadge = panel.querySelector('.remember-score-badge');
  const scoreLabel = panel.querySelector('.remember-score-label');
  const feedbackContent = panel.querySelector('.remember-feedback-content');
  const historyDiv = panel.querySelector('.remember-history');
  const historyCountEl = panel.querySelector('.history-count');
  const showHistoryBtn = panel.querySelector('.btn-show-history');
  const historyItems = panel.querySelector('.remember-history-items');

  // Init from existing tests
  const latest = tests[0] || null;
  if (latest && latest.score != null) {
    lastInfo.textContent = `${latest.score}/10 · ${relativeTime(latest.created_at)}`;
    lastInfo.style.color = scoreColor(latest.score);
    updateRememberChip(card, latest.score, latest.created_at);
  }
  if (tests.length > 0) {
    historyCountEl.textContent = tests.length;
    historyDiv.classList.remove('hidden');
    tests.forEach(t => historyItems.appendChild(buildRememberHistoryItem(t)));
  }

  // Prevent clicks inside the panel from toggling the grammar card collapse
  panel.addEventListener('click', e => e.stopPropagation());

  // Toggle test form
  toggleBtn.addEventListener('click', () => {
    form.classList.toggle('hidden');
    result.classList.add('hidden');
    if (!form.classList.contains('hidden')) {
      input.value = '';
      input.focus();
      toggleBtn.textContent = 'Close';
    } else {
      toggleBtn.textContent = 'Test yourself';
    }
  });

  cancelBtn.addEventListener('click', () => {
    form.classList.add('hidden');
    result.classList.add('hidden');
    toggleBtn.textContent = 'Test yourself';
  });

  // Submit test
  async function submitTest() {
    const answer = input.value.trim();
    if (!answer) return;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Assessing…';
    result.classList.add('hidden');
    try {
      const test = await api(`/api/grammar/${section.id}/tests`, 'POST', { user_answer: answer });
      // Show result
      const color = scoreColor(test.score);
      scoreBadge.textContent = `${test.score}/10`;
      scoreBadge.style.color = color;
      scoreLabel.textContent = test.score >= 8 ? 'Great job!' : test.score >= 5 ? 'Keep studying!' : 'Review this one!';
      feedbackContent.innerHTML = renderMarkdown(test.ai_feedback || '');
      result.classList.remove('hidden');
      // Update header chip + last info
      updateRememberChip(card, test.score, test.created_at);
      lastInfo.textContent = `${test.score}/10 · just now`;
      lastInfo.style.color = color;
      // Add to history
      historyItems.prepend(buildRememberHistoryItem(test));
      const newCount = historyItems.querySelectorAll('.remember-history-item').length;
      historyCountEl.textContent = newCount;
      historyDiv.classList.remove('hidden');
      showToast(`Score: ${test.score}/10`);
      input.value = '';
    } catch (err) {
      showToast(err.message, true);
    }
    submitBtn.disabled = false;
    submitBtn.textContent = 'Assess';
  }

  submitBtn.addEventListener('click', submitTest);
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && e.ctrlKey) submitTest(); });

  // Toggle history
  showHistoryBtn.addEventListener('click', () => {
    const hidden = historyItems.classList.toggle('hidden');
    showHistoryBtn.innerHTML = `&#128336; History (<span class="history-count">${historyCountEl.textContent}</span>) ${hidden ? '' : '&#9650;'}`;
  });

  // Delete a test from history
  historyItems.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-delete-test');
    if (!btn) return;
    const item = btn.closest('.remember-history-item');
    const testId = item.dataset.id;
    await api(`/api/tests/${testId}`, 'DELETE');
    item.remove();
    const remaining = historyItems.querySelectorAll('.remember-history-item').length;
    historyCountEl.textContent = remaining;
    showHistoryBtn.innerHTML = `&#128336; History (<span class="history-count">${remaining}</span>)`;
    if (remaining === 0) historyDiv.classList.add('hidden');
    showToast('Test deleted');
  });
}

/* ── Sidebar: notebooks ── */
async function loadNotebooks() {
  const list = $('notebookList');
  list.innerHTML = '<li class="loading-item"><span class="spinner"></span> Loading notebooks…</li>';
  notebooks = await api('/api/notebooks');
  renderSidebar();
}

function renderSidebar() {
  const list = $('notebookList');
  list.innerHTML = '';
  notebooks.forEach(nb => {
    const li = document.createElement('li');
    li.className = nb.id === currentNotebookId ? 'active' : '';
    li.innerHTML = `<span class="nb-icon">📓</span><span class="nb-name">${escHtml(nb.name)}</span>`;
    li.addEventListener('click', () => openNotebook(nb.id));
    list.appendChild(li);
  });
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Open notebook ── */
async function openNotebook(id) {
  const container = $('grammarList');

  // Save current notebook DOM to cache before switching
  if (currentNotebookId && currentNotebookId !== id && container.children.length) {
    const wrapper = document.createElement('div');
    while (container.firstChild) wrapper.appendChild(container.firstChild);
    notebookDomCache[currentNotebookId] = wrapper;
  }

  currentNotebookId = id;
  closeSidebar();
  renderSidebar();
  const nb = notebooks.find(n => n.id === id);
  $('notebookTitle').textContent = nb.name;
  const subtitleEl = $('notebookSubtitle');
  if (nb.subtitle) {
    subtitleEl.textContent = nb.subtitle;
    subtitleEl.classList.remove('hidden');
  } else {
    subtitleEl.textContent = '';
    subtitleEl.classList.add('hidden');
  }
  $('emptyState').classList.add('hidden');
  $('notebookView').classList.remove('hidden');

  if (notebookDomCache[id]) {
    container.innerHTML = '';
    const cached = notebookDomCache[id];
    while (cached.firstChild) container.appendChild(cached.firstChild);
    delete notebookDomCache[id];
  } else {
    await loadGrammarSections(id);
  }
}

/* ── Grammar sections ── */
async function loadGrammarSections(notebookId) {
  const container = $('grammarList');
  container.innerHTML = '<div class="section-loading"><span class="spinner"></span> Loading grammar sections…</div>';
  const sections = await api(`/api/notebooks/${notebookId}/grammar`);
  container.innerHTML = '';
  for (const section of sections) {
    container.appendChild(await buildGrammarCard(section));
  }
  updateMoveButtons();
}

async function buildGrammarCard(section) {
  const tpl = document.getElementById('tplGrammarSection');
  const card = tpl.content.cloneNode(true).querySelector('.grammar-section');
  card.dataset.id = section.id;
  card.classList.add('collapsed');
  card.querySelector('.grammar-input-text').textContent = section.grammar_input;

  const summaryContent = card.querySelector('.ai-summary-content');

  if (section.ai_summary) {
    summaryContent.classList.remove('summary-placeholder');
    summaryContent.innerHTML = renderMarkdown(section.ai_summary);
  }

  // Collapse toggle
  card.querySelector('.grammar-header').addEventListener('click', (e) => {
    if (e.target.closest('.btn-delete-grammar') || e.target.closest('.btn-move-up') || e.target.closest('.btn-move-down')) return;
    card.classList.toggle('collapsed');
  });

  // Move up/down
  card.querySelector('.btn-move-up').addEventListener('click', () => moveGrammarSection(card, 'up'));
  card.querySelector('.btn-move-down').addEventListener('click', () => moveGrammarSection(card, 'down'));

  // Delete grammar section
  card.querySelector('.btn-delete-grammar').addEventListener('click', async () => {
    if (!confirm('Delete this grammar section and all its exercises?')) return;
    await api(`/api/grammar/${section.id}`, 'DELETE');
    card.remove();
    updateMoveButtons();
    showToast('Section deleted');
  });

  // Regenerate summary
  card.querySelector('.btn-regenerate-summary').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    summaryContent.classList.add('summary-placeholder');
    summaryContent.innerHTML = '<span class="spinner"></span> Regenerating…';
    try {
      const updated = await api(`/api/grammar/${section.id}/summarize`, 'POST', { use_search: useSearch() });
      summaryContent.classList.remove('summary-placeholder');
      summaryContent.innerHTML = renderMarkdown(updated.ai_summary);
      showToast('Summary updated');
    } catch (err) {
      summaryContent.innerHTML = `<span style="color:var(--danger)">${escHtml(err.message)}</span>`;
      showToast(err.message, true);
    }
    btn.disabled = false;
  });

  // Load exercises, Q&As, and remember tests in parallel
  const exerciseList = card.querySelector('.exercise-list');
  const [exercises, qas, tests] = await Promise.all([
    api(`/api/grammar/${section.id}/exercises`),
    api(`/api/grammar/${section.id}/qas`),
    api(`/api/grammar/${section.id}/tests`),
  ]);
  exercises.forEach((ex, i) => {
    const exCard = buildExerciseCard(ex, i + 1, section);
    exCard.classList.add('ex-collapsed');
    exerciseList.appendChild(exCard);
  });
  updateExerciseCount(card);

  // Add exercise
  card.querySelector('.btn-add-exercise').addEventListener('click', async () => {
    const ex = await api(`/api/grammar/${section.id}/exercises`, 'POST');
    const num = exerciseList.querySelectorAll('.exercise-card').length + 1;
    exerciseList.appendChild(buildExerciseCard(ex, num, section));
    updateExerciseCount(card);
  });

  // Load Q&A
  const qaList = card.querySelector('.qa-list');
  qas.forEach(qa => {
    const qaCard = buildQaCard(qa, card);
    qaCard.classList.add('qa-collapsed');
    qaList.appendChild(qaCard);
  });
  updateQaCount(card);

  // Remember test panel
  buildRememberPanel(card, section, tests);

  // Ask Q&A
  const qaInput = card.querySelector('.qa-input');
  const askBtn = card.querySelector('.btn-ask');
  async function submitQa() {
    const question = qaInput.value.trim();
    if (!question) return;
    askBtn.disabled = true;
    askBtn.textContent = 'Asking…';
    qaInput.value = '';
    try {
      const qa = await api(`/api/grammar/${section.id}/qas`, 'POST', { question, use_search: useSearch() });
      qaList.appendChild(buildQaCard(qa, card));
      updateQaCount(card);
      showToast('Answer ready!');
    } catch (err) {
      showToast(err.message, true);
    }
    askBtn.disabled = false;
    askBtn.textContent = 'Ask';
  }
  askBtn.addEventListener('click', submitQa);
  qaInput.addEventListener('keydown', e => { if (e.key === 'Enter') submitQa(); });

  return card;
}

/* ── Reorder grammar sections ── */
function moveGrammarSection(card, direction) {
  const container = $('grammarList');
  if (direction === 'up' && card.previousElementSibling) {
    container.insertBefore(card, card.previousElementSibling);
  } else if (direction === 'down' && card.nextElementSibling) {
    container.insertBefore(card.nextElementSibling, card);
  }
  updateMoveButtons();
  saveGrammarOrder();
}

function updateMoveButtons() {
  const container = $('grammarList');
  const cards = container.querySelectorAll('.grammar-section');
  cards.forEach((card, i) => {
    card.querySelector('.btn-move-up').disabled = (i === 0);
    card.querySelector('.btn-move-down').disabled = (i === cards.length - 1);
  });
}

async function saveGrammarOrder() {
  const container = $('grammarList');
  const ids = [...container.querySelectorAll('.grammar-section')].map(c => c.dataset.id);
  try {
    await api(`/api/notebooks/${currentNotebookId}/grammar/reorder`, 'POST', { ids });
  } catch (err) {
    showToast('Failed to save order: ' + err.message, true);
  }
}

function buildQaCard(qa, grammarCard) {
  const tpl = document.getElementById('tplQaCard');
  const card = tpl.content.cloneNode(true).querySelector('.qa-card');
  card.dataset.id = qa.id;
  card.querySelector('.qa-question-text').textContent = qa.question;
  const answerContent = card.querySelector('.qa-answer-content');
  if (qa.ai_answer) {
    answerContent.innerHTML = renderMarkdown(qa.ai_answer);
  } else {
    answerContent.innerHTML = '<span class="spinner"></span> Generating…';
  }
  card.querySelector('.qa-question-row').addEventListener('click', (e) => {
    if (e.target.closest('.btn-delete-qa')) return;
    card.classList.toggle('qa-collapsed');
  });
  card.querySelector('.btn-delete-qa').addEventListener('click', async () => {
    await api(`/api/qas/${qa.id}`, 'DELETE');
    card.remove();
    updateQaCount(grammarCard);
    showToast('Q&A deleted');
  });
  return card;
}

function buildExerciseCard(exercise, num, section) {
  const tpl = document.getElementById('tplExercise');
  const card = tpl.content.cloneNode(true).querySelector('.exercise-card');
  card.dataset.id = exercise.id;
  card.querySelector('.exercise-num').textContent = `Exercise ${num}`;

  // Collapse toggle on exercise header
  card.querySelector('.exercise-header').addEventListener('click', (e) => {
    if (e.target.closest('.btn-delete-exercise')) return;
    card.classList.toggle('ex-collapsed');
  });

  const textarea = card.querySelector('.exercise-input');
  textarea.value = exercise.user_input || '';

  // Auto-save on blur
  textarea.addEventListener('blur', async () => {
    await api(`/api/exercises/${exercise.id}`, 'PATCH', { user_input: textarea.value });
  });

  const feedbackBox = card.querySelector('.ai-feedback-box');
  const feedbackContent = card.querySelector('.ai-feedback-content');

  if (exercise.ai_feedback) {
    feedbackBox.classList.remove('hidden');
    feedbackContent.innerHTML = renderMarkdown(exercise.ai_feedback);
  }

  // Evaluate
  card.querySelector('.btn-evaluate').addEventListener('click', async (e) => {
    await runEvaluate(e.currentTarget, exercise.id, textarea, feedbackBox, feedbackContent, section);
  });

  // Regenerate feedback
  card.querySelector('.btn-regenerate-feedback').addEventListener('click', async (e) => {
    await runEvaluate(e.currentTarget, exercise.id, textarea, feedbackBox, feedbackContent, section);
  });

  // Collapse/expand AI feedback content
  const collapseBtn = card.querySelector('.btn-collapse-feedback');
  collapseBtn.addEventListener('click', () => {
    const hidden = feedbackContent.classList.toggle('hidden');
    collapseBtn.innerHTML = hidden ? '&#9660; Expand' : '&#9650; Collapse';
  });

  // Delete exercise (save refs before removing card)
  card.querySelector('.btn-delete-exercise').addEventListener('click', async () => {
    const list = card.closest('.exercise-list');
    const grammarCard = card.closest('.grammar-section');
    await api(`/api/exercises/${exercise.id}`, 'DELETE');
    card.remove();
    showToast('Exercise deleted');
    renumberExercises(list);
    updateExerciseCount(grammarCard);
  });

  return card;
}

async function runEvaluate(btn, exerciseId, textarea, feedbackBox, feedbackContent, section) {
  // Save latest text first
  await api(`/api/exercises/${exerciseId}`, 'PATCH', { user_input: textarea.value });

  btn.disabled = true;
  feedbackBox.classList.remove('hidden');
  feedbackContent.innerHTML = '<span class="spinner"></span> Evaluating…';

  try {
    const updated = await api(`/api/exercises/${exerciseId}/evaluate`, 'POST', { use_search: useSearch() });
    feedbackContent.innerHTML = renderMarkdown(updated.ai_feedback);
    showToast('AI feedback ready!');
  } catch (err) {
    feedbackContent.innerHTML = `<span style="color:var(--danger)">${escHtml(err.message)}</span>`;
    showToast(err.message, true);
  }
  btn.disabled = false;
}

function renumberExercises(list) {
  if (!list) return;
  list.querySelectorAll('.exercise-card').forEach((card, i) => {
    card.querySelector('.exercise-num').textContent = `Exercise ${i + 1}`;
  });
}

/* ── Modals ── */
function openModal(id) { $(id).classList.remove('hidden'); }
function closeModal(id) { $(id).classList.add('hidden'); }

// New notebook
$('btnAddNotebook').addEventListener('click', () => {
  $('inputNotebookName').value = '';
  $('inputNotebookSubtitle').value = '';
  openModal('modalNewNotebook');
  setTimeout(() => $('inputNotebookName').focus(), 50);
});
$('btnCancelNotebook').addEventListener('click', () => closeModal('modalNewNotebook'));
$('btnConfirmNotebook').addEventListener('click', async () => {
  const name = $('inputNotebookName').value.trim();
  if (!name) return;
  const subtitle = $('inputNotebookSubtitle').value.trim();
  try {
    const nb = await api('/api/notebooks', 'POST', { name, subtitle });
    notebooks.unshift(nb);
    renderSidebar();
    closeModal('modalNewNotebook');
    openNotebook(nb.id);
  } catch (err) { showToast(err.message, true); }
});
$('inputNotebookName').addEventListener('keydown', e => { if (e.key === 'Enter') $('inputNotebookSubtitle').focus(); });

// Rename notebook
$('btnRenameNotebook').addEventListener('click', () => {
  const nb = notebooks.find(n => n.id === currentNotebookId);
  $('inputRenameNotebook').value = nb ? nb.name : '';
  $('inputRenameSubtitle').value = nb ? (nb.subtitle || '') : '';
  openModal('modalRenameNotebook');
  setTimeout(() => $('inputRenameNotebook').focus(), 50);
});
$('btnCancelRename').addEventListener('click', () => closeModal('modalRenameNotebook'));
$('btnConfirmRename').addEventListener('click', async () => {
  const name = $('inputRenameNotebook').value.trim();
  if (!name) return;
  const subtitle = $('inputRenameSubtitle').value.trim();
  try {
    const updated = await api(`/api/notebooks/${currentNotebookId}`, 'PATCH', { name, subtitle });
    const idx = notebooks.findIndex(n => n.id === currentNotebookId);
    notebooks[idx] = updated;
    renderSidebar();
    $('notebookTitle').textContent = updated.name;
    const subtitleEl = $('notebookSubtitle');
    if (updated.subtitle) {
      subtitleEl.textContent = updated.subtitle;
      subtitleEl.classList.remove('hidden');
    } else {
      subtitleEl.textContent = '';
      subtitleEl.classList.add('hidden');
    }
    closeModal('modalRenameNotebook');
  } catch (err) { showToast(err.message, true); }
});
$('inputRenameNotebook').addEventListener('keydown', e => { if (e.key === 'Enter') $('inputRenameSubtitle').focus(); });

// Delete notebook
$('btnDeleteNotebook').addEventListener('click', async () => {
  if (!confirm('Delete this notebook and ALL its content?')) return;
  await api(`/api/notebooks/${currentNotebookId}`, 'DELETE');
  delete notebookDomCache[currentNotebookId];
  notebooks = notebooks.filter(n => n.id !== currentNotebookId);
  currentNotebookId = null;
  renderSidebar();
  $('notebookView').classList.add('hidden');
  $('emptyState').classList.remove('hidden');
  showToast('Notebook deleted');
});

// Add grammar section
$('btnAddGrammar').addEventListener('click', () => {
  $('inputGrammar').value = '';
  openModal('modalAddGrammar');
  setTimeout(() => $('inputGrammar').focus(), 50);
});
$('btnCancelGrammar').addEventListener('click', () => closeModal('modalAddGrammar'));
$('btnConfirmGrammar').addEventListener('click', async () => {
  const grammar = $('inputGrammar').value.trim();
  if (!grammar) return;
  closeModal('modalAddGrammar');
  try {
    const section = await api(`/api/notebooks/${currentNotebookId}/grammar`, 'POST', { grammar_input: grammar });
    const container = $('grammarList');
    const card = await buildGrammarCard(section);
    card.classList.remove('collapsed');
    container.appendChild(card);
    updateMoveButtons();
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Kick off summary immediately
    const summaryContent = card.querySelector('.ai-summary-content');
    summaryContent.classList.add('summary-placeholder');
    summaryContent.innerHTML = '<span class="spinner"></span> Generating summary…';
    const regenBtn = card.querySelector('.btn-regenerate-summary');
    regenBtn.disabled = true;
    try {
      const updated = await api(`/api/grammar/${section.id}/summarize`, 'POST', { use_search: useSearch() });
      summaryContent.classList.remove('summary-placeholder');
      summaryContent.innerHTML = renderMarkdown(updated.ai_summary);
    } catch (err) {
      summaryContent.innerHTML = `<span style="color:var(--danger)">Failed: ${escHtml(err.message)}</span>`;
      showToast(err.message, true);
    }
    regenBtn.disabled = false;
  } catch (err) { showToast(err.message, true); }
});
$('inputGrammar').addEventListener('keydown', e => { if (e.key === 'Enter') $('btnConfirmGrammar').click(); });

// Close modals on overlay click
['modalNewNotebook','modalRenameNotebook','modalAddGrammar'].forEach(id => {
  $(id).addEventListener('click', e => { if (e.target === $(id)) closeModal(id); });
});

// Export PDF
$('btnExportPDF').addEventListener('click', exportToPDF);

async function exportToPDF() {
  const nb = notebooks.find(n => n.id === currentNotebookId);
  if (!nb) return;
  showToast('Preparing export…');
  try {
    const sections = await api(`/api/notebooks/${currentNotebookId}/grammar`);
    const allSections = await Promise.all(sections.map(async s => {
      const exercises = await api(`/api/grammar/${s.id}/exercises`);
      return { ...s, exercises };
    }));
    const html = buildExportHtml(nb, allSections);
    const win = window.open('', '_blank');
    win.document.write(html);
    win.document.close();
    setTimeout(() => { win.focus(); win.print(); }, 400);
  } catch (err) {
    showToast('Export failed: ' + err.message, true);
  }
}

function buildExportHtml(nb, sections) {
  const sectionsHtml = sections.map((s, si) => {
    const summaryHtml = s.ai_summary ? marked.parse(s.ai_summary) : '';
    const exercisesHtml = s.exercises
      .filter(e => e.user_input || e.ai_feedback)
      .map((e, ei) => {
        const feedbackHtml = e.ai_feedback ? marked.parse(e.ai_feedback) : '';
        return `<div class="ex-card">
  <div class="ex-num">Exercise ${ei + 1}</div>
  ${e.user_input ? `<div class="ex-input">${escHtml(e.user_input).replace(/\n/g, '<br>')}</div>` : ''}
  ${feedbackHtml ? `<div class="ex-feedback-label">AI Feedback</div><div class="ex-feedback">${feedbackHtml}</div>` : ''}
</div>`;
      }).join('');

    return `<div class="section">
  <div class="section-header">
    <span class="tag">Grammar</span>
    <h2>${escHtml(s.grammar_input)}</h2>
  </div>
  ${summaryHtml ? `<div class="summary"><div class="block-label">AI Summary</div>${summaryHtml}</div>` : ''}
  ${exercisesHtml ? `<div class="exercises"><div class="block-label">My Exercises</div>${exercisesHtml}</div>` : ''}
</div>`;
  }).join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>${escHtml(nb.name)}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;font-size:13px;color:#1a1a2e;max-width:820px;margin:0 auto;padding:30px 24px 60px}
h1{font-size:22px;font-weight:700;margin-bottom:5px}
.nb-subtitle{color:#555;font-size:13px;margin-bottom:28px;white-space:pre-wrap;line-height:1.5}
.nb-spacer{margin-bottom:24px}
.section{border:1px solid #ccc;border-radius:8px;margin-bottom:24px;overflow:hidden;page-break-inside:avoid}
.section-header{background:#f0eff8;padding:12px 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid #ccc}
.tag{font-size:10px;font-weight:700;text-transform:uppercase;color:#5549c0;background:#e8e4ff;padding:2px 8px;border-radius:20px;flex-shrink:0}
h2{font-size:15px;font-weight:700;margin:0}
.block-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#5549c0;margin-bottom:9px;padding-bottom:5px;border-bottom:1px solid #e8e8f5}
.summary{padding:14px 16px;border-bottom:1px solid #eee}
.summary h2{font-size:13px;color:#5549c0;border-bottom:1px solid #e8e8f0;padding-bottom:3px;margin:12px 0 6px;font-weight:700}
.summary h2:first-child{margin-top:0}
.summary p{margin:0 0 6px;line-height:1.65}
.summary ul,.summary ol{margin:4px 0 8px 18px;line-height:1.65}
.summary li{margin-bottom:3px}
.summary strong{color:#1a1a2e}
.summary code{background:#f0eff8;color:#8b6914;padding:1px 4px;border-radius:3px;font-size:12px}
.exercises{padding:14px 16px}
.ex-card{border:1px solid #ddd;border-radius:6px;padding:10px 12px;margin-bottom:10px}
.ex-card:last-child{margin-bottom:0}
.ex-num{font-size:10px;font-weight:700;text-transform:uppercase;color:#888;margin-bottom:6px}
.ex-input{background:#f5f5fa;padding:8px 10px;border-radius:5px;font-size:13px;margin-bottom:10px;line-height:1.65}
.ex-feedback-label{font-size:10px;font-weight:700;text-transform:uppercase;color:#5549c0;margin-bottom:6px}
.ex-feedback h2{font-size:13px;color:#5549c0;border-bottom:1px solid #e8e8f0;padding-bottom:3px;margin:10px 0 5px;font-weight:700}
.ex-feedback h2:first-child{margin-top:0}
.ex-feedback p{margin:0 0 5px;line-height:1.55}
.ex-feedback ul,.ex-feedback ol{margin:3px 0 7px 18px;line-height:1.55}
.ex-feedback li{margin-bottom:2px}
.ex-feedback strong{color:#1a1a2e}
@media print{body{padding:0 16px}@page{margin:18mm}}
</style>
</head>
<body>
<h1>${escHtml(nb.name)}</h1>
${nb.subtitle ? `<div class="nb-subtitle">${escHtml(nb.subtitle)}</div>` : '<div class="nb-spacer"></div>'}
${sectionsHtml || '<p style="color:#888">No grammar sections yet.</p>'}
</body>
</html>`;
}

/* ── Init ── */
initAuth().then(ok => { if (ok !== false) loadNotebooks(); });
