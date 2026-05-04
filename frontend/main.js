/**
 * DeepLearn — Personalised Learning System Frontend
 * 
 * Main application logic: handles navigation, API communication,
 * learning sessions, graph visualisation, and UI state.
 */

import { marked } from 'marked';
import katex from 'katex';

// Configure marked for safe, beautiful rendering
marked.setOptions({
  breaks: true,
  gfm: true,
});

const API_BASE = '/api';

// ===== State =====
const state = {
  learnerId: null,
  learnerName: '',
  currentView: 'onboarding',
  graphData: null,
  currentSession: null,
  currentQuestions: null,
  currentQuestionIndex: 0,
  questionStartTime: null,
};

// ===== API Helpers =====
async function api(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `API error ${res.status}`);
    }
    return await res.json();
  } catch (e) {
    console.error(`API call failed: ${path}`, e);
    throw e;
  }
}

// ===== Navigation =====
function switchView(view) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));

  const viewEl = document.getElementById(`view-${view}`);
  const navEl = document.querySelector(`[data-view="${view}"]`);
  if (viewEl) viewEl.classList.add('active');
  if (navEl) navEl.classList.add('active');

  state.currentView = view;

  // Load data for the view
  if (view === 'dashboard') loadDashboard();
  if (view === 'graph') loadGraph();
  if (view === 'review') loadReview();
}

document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', () => {
    if (!state.learnerId && link.dataset.view !== 'onboarding') return;
    switchView(link.dataset.view);
  });
});

// ===== Onboarding =====
document.getElementById('onboarding-start').addEventListener('click', async () => {
  const nameInput = document.getElementById('onboarding-name');
  const name = nameInput.value.trim() || 'Learner';
  // Name IS the unique ID — same name = same user (no random suffix)
  const learnerId = name.toLowerCase().replace(/\s+/g, '_');

  try {
    // POST /learner returns existing profile if ID already exists
    await api('/learner', {
      method: 'POST',
      body: JSON.stringify({ learner_id: learnerId, name }),
    });
    state.learnerId = learnerId;
    state.learnerName = name;

    // Update UI
    document.getElementById('user-avatar').textContent = name.charAt(0).toUpperCase();
    switchView('dashboard');
  } catch (e) {
    alert('Failed to create learner profile. Is the backend running?');
  }
});

// ===== Dashboard =====
async function loadDashboard() {
  if (!state.learnerId) return;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  document.getElementById('dashboard-greeting').textContent = `${greeting}, ${state.learnerName}`;

  try {
    // Load learner profile
    const profile = await api(`/learner/${state.learnerId}`);
    const stats = profile.global_stats || {};
    const enrolledCourses = profile.enrolled_courses || [];

    document.getElementById('stat-avg-mastery').textContent =
      Math.round((stats.avg_mastery || 0) * 100) + '%';
    document.getElementById('stat-concepts').textContent =
      `${stats.concepts_mastered || 0}/${stats.concepts_encountered || 0}`;
    document.getElementById('stat-sessions').textContent = stats.total_sessions || 0;
    document.getElementById('stat-doubts').textContent = stats.doubts_resolved || 0;

    // Handle empty state
    if (!enrolledCourses.length) {
      document.getElementById('dashboard-subtitle').textContent = 'Start by adding a course below';
      renderRecommendations([]);
      renderMasteryBars({});
      const coursesSection = document.getElementById('courses-section');
      if (coursesSection) coursesSection.style.display = 'none';
      return;
    }

    document.getElementById('dashboard-subtitle').textContent = "Here's your learning progress";

    // Load user courses
    await loadUserCourses();

    // Load mastery overview
    const mastery = await api(`/learner/${state.learnerId}/mastery`);
    renderMasteryBars(mastery);

    // Load recommendations
    const recs = await api(`/learner/${state.learnerId}/recommendations?top_k=3`);
    renderRecommendations(recs.recommendations || [], recs.message || '', recs.course_recommendations || []);

    // Show ablation mode indicator if active
    if (recs.ablation_mode) {
      const banner = document.createElement('div');
      banner.id = 'ablation-banner';
      banner.style.cssText = 'background:rgba(234,179,8,0.1);border:1px solid rgba(234,179,8,0.3);border-radius:8px;padding:8px 16px;margin-bottom:16px;font-size:0.85rem;color:#eab308;text-align:center';
      banner.innerHTML = '⚠️ <strong>Ablation Mode</strong> — Knowledge graph personalisation disabled (controlled experiment)';
      const greeting = document.getElementById('dashboard-greeting');
      if (greeting && !document.getElementById('ablation-banner')) {
        greeting.parentNode.insertBefore(banner, greeting.nextSibling);
      }
    }
  } catch (e) {
    console.error('Dashboard load failed:', e);
  }
}

async function loadUserCourses() {
  try {
    const result = await api(`/learner/${state.learnerId}/courses`);
    const section = document.getElementById('courses-section');
    const list = document.getElementById('courses-list');
    if (!result.courses || !result.courses.length) {
      section.style.display = 'none';
      return;
    }
    section.style.display = 'block';
    list.innerHTML = result.courses.map((c, index) => {
      const pct = Math.round((c.avg_mastery || 0) * 100);
      return `
        <div class="course-card" id="course-${index}">
          <div class="course-card-header" style="cursor:pointer" onclick="toggleCourseDetails(${index})">
            <div>
              <h3>${c.course_name}</h3>
              <span class="course-card-channel">${c.channel || ''}</span>
            </div>
            <span style="font-size:1.2rem; transition:transform 0.3s" id="course-icon-${index}">▼</span>
          </div>
          <div class="course-card-stats">
            <span>${c.lectures_count} lectures</span>
            <span>${c.concepts_count} concepts</span>
            <span>${c.concepts_mastered}/${c.concepts_count} mastered</span>
          </div>
          <div class="mastery-bar-track" style="margin-top:8px">
            <div class="mastery-bar-fill" style="width:${pct}%;background:${pct >= 70 ? 'var(--success)' : pct >= 30 ? 'var(--warning)' : 'var(--accent-primary)'}"></div>
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">${pct}% mastery</div>
          
          <div class="course-details" id="course-details-${index}" style="display:none; margin-top:var(--space-md); border-top:1px solid var(--border); padding-top:var(--space-md)">
            <h4 style="font-size:0.9rem; margin-bottom:var(--space-sm); color:var(--text-secondary)">Lectures & Concepts</h4>
            ${(c.lectures || []).map(lec => `
              <div style="margin-bottom:var(--space-md)">
                <div style="font-weight:600; font-size:0.85rem; margin-bottom:var(--space-xs); display:flex; gap:8px; align-items:center;">
                  <span>🎥</span> <span>${lec.title}</span>
                </div>
                <div style="display:flex; flex-wrap:wrap; gap:8px; padding-left:24px;">
                  ${lec.concepts.length > 0 ? lec.concepts.map(conc => {
                    const mpct = Math.round(conc.mastery * 100);
                    const color = mpct >= 70 ? 'var(--success)' : mpct >= 30 ? 'var(--warning)' : 'var(--text-muted)';
                    return `
                      <button class="btn btn-secondary btn-sm" style="border-color:${color}; font-size:0.75rem; padding:4px 8px" onclick="startLearning('${conc.id}')">
                        ${conc.name} (${mpct}%)
                      </button>
                    `;
                  }).join('') : '<span style="font-size:0.75rem; color:var(--text-muted)">No specific concepts extracted</span>'}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    console.error('Courses load failed:', e);
  }
}

window.toggleCourseDetails = function(index) {
  const details = document.getElementById(`course-details-${index}`);
  const icon = document.getElementById(`course-icon-${index}`);
  if (details.style.display === 'none') {
    details.style.display = 'block';
    icon.style.transform = 'rotate(180deg)';
  } else {
    details.style.display = 'none';
    icon.style.transform = 'rotate(0deg)';
  }
};

// ===== Course Ingestion =====

// Track current ingest mode
let ingestMode = 'url';

window.setIngestMode = function(mode) {
  ingestMode = mode;
  const urlInput = document.getElementById('ingest-url');
  const topicInput = document.getElementById('ingest-topic');
  const urlBtn = document.getElementById('mode-url-btn');
  const topicBtn = document.getElementById('mode-topic-btn');
  const fetchText = document.getElementById('step-fetch-text');

  if (mode === 'url') {
    urlInput.style.display = '';
    topicInput.style.display = 'none';
    urlBtn.classList.add('active');
    topicBtn.classList.remove('active');
    fetchText.textContent = 'Fetching video metadata & transcripts from YouTube...';
  } else {
    urlInput.style.display = 'none';
    topicInput.style.display = '';
    urlBtn.classList.remove('active');
    topicBtn.classList.add('active');
    fetchText.textContent = 'Searching YouTube for the best lectures & fetching transcripts...';
  }
};

window.ingestCourse = async function() {
  let payload;

  if (ingestMode === 'url') {
    const urlInput = document.getElementById('ingest-url');
    const url = urlInput.value.trim();
    if (!url) { urlInput.focus(); return; }
    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
      showIngestError('Please enter a valid YouTube URL (video or playlist).');
      return;
    }
    payload = { youtube_url: url, learner_id: state.learnerId };
  } else {
    const topicInput = document.getElementById('ingest-topic');
    const topic = topicInput.value.trim();
    if (!topic) { topicInput.focus(); return; }
    if (topic.length < 3) {
      showIngestError('Please enter a more descriptive topic (at least 3 characters).');
      return;
    }
    payload = { topic: topic, learner_id: state.learnerId };
  }

  const btn = document.getElementById('ingest-btn');
  btn.disabled = true;
  btn.textContent = 'Processing...';
  document.getElementById('ingest-url').disabled = true;
  document.getElementById('ingest-topic').disabled = true;

  // Show progress steps
  const progress = document.getElementById('ingest-progress');
  progress.classList.add('active');
  hideIngestResult();
  hideIngestError();

  // Animate steps (simulated since backend is a single call)
  setStepState('step-fetch', 'active');
  setStepState('step-extract', '');
  setStepState('step-build', '');

  const stepTimers = [
    setTimeout(() => {
      setStepState('step-fetch', 'done');
      setStepState('step-extract', 'active');
    }, ingestMode === 'topic' ? 15000 : 8000),
    setTimeout(() => {
      setStepState('step-extract', 'done');
      setStepState('step-build', 'active');
    }, ingestMode === 'topic' ? 35000 : 25000),
  ];

  try {
    const result = await api('/course/ingest', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    stepTimers.forEach(clearTimeout);
    setStepState('step-fetch', 'done');
    setStepState('step-extract', 'done');
    setStepState('step-build', 'done');

    document.getElementById('ingest-result-course').textContent = result.course_name;
    document.getElementById('ingest-result-lectures').textContent = result.lectures_found;
    document.getElementById('ingest-result-concepts').textContent = result.concepts_extracted;
    document.getElementById('ingest-result').classList.add('active');

    await loadDashboard();

  } catch (e) {
    stepTimers.forEach(clearTimeout);
    ['step-fetch', 'step-extract', 'step-build'].forEach(id => {
      const el = document.getElementById(id);
      if (el.classList.contains('active')) {
        setStepState(id, 'error');
      }
    });
    showIngestError(`Ingestion failed: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Ingest Course';
    document.getElementById('ingest-url').disabled = false;
    document.getElementById('ingest-topic').disabled = false;
  }
};

function setStepState(stepId, state) {
  const el = document.getElementById(stepId);
  el.classList.remove('active', 'done', 'error');
  if (state) el.classList.add(state);
}

function showIngestError(msg) {
  const el = document.getElementById('ingest-error');
  el.textContent = msg;
  el.classList.add('active');
}

function hideIngestError() {
  document.getElementById('ingest-error').classList.remove('active');
}

function hideIngestResult() {
  document.getElementById('ingest-result').classList.remove('active');
}

function renderMasteryBars(masteryMap) {
  const container = document.getElementById('mastery-bars');
  // Sort by difficulty
  const sorted = Object.entries(masteryMap).sort((a, b) => a[1].difficulty - b[1].difficulty);

  container.innerHTML = sorted.map(([id, info]) => {
    const pct = Math.round((info.mastery || 0) * 100);
    const color = pct >= 70 ? 'var(--success)' : pct >= 30 ? 'var(--warning)' : 'var(--text-muted)';
    return `
      <div class="mastery-bar-row">
        <div class="mastery-bar-label" title="${info.name}">${info.name}</div>
        <div class="mastery-bar-track">
          <div class="mastery-bar-fill" style="width:${pct}%;background:${color}"></div>
        </div>
        <div class="mastery-bar-value">${pct}%</div>
      </div>
    `;
  }).join('');
}

function renderRecommendations(recs, message, courseRecs = []) {
  const container = document.getElementById('recommendations-list');
  if (!recs.length) {
    container.innerHTML = `<div class="no-graph-notice" style="padding:var(--space-xl)">
      <div class="notice-icon">📌</div>
      <h3>${message || 'No recommendations yet'}</h3>
      <p>${message ? '' : 'Upload a YouTube course to get personalised learning recommendations.'}</p>
    </div>`;
    return;
  }
  container.innerHTML = recs.map(rec => {
    const diff = rec.difficulty || 0;
    const diffClass = diff < 0.35 ? 'difficulty-easy' : diff < 0.6 ? 'difficulty-medium' : 'difficulty-hard';
    const diffLabel = diff < 0.35 ? 'Easy' : diff < 0.6 ? 'Medium' : 'Hard';
    const mastery = Math.round((rec.current_mastery || 0) * 100);
    return `
      <div class="rec-card" onclick="startLearning('${rec.concept_id}')">
        <div class="rec-card-header">
          <div class="rec-card-title">${rec.concept_name}</div>
          <span class="rec-card-difficulty ${diffClass}">${diffLabel}</span>
        </div>
        <div class="rec-card-desc">${rec.motivation || rec.description || ''}</div>
        <div class="rec-card-meta">
          <span>Mastery: ${mastery}%</span>
          <span>Bloom: ${rec.bloom_ceiling || '—'}</span>
        </div>
      </div>
    `;
  }).join('');

  if (courseRecs && courseRecs.length > 0) {
    container.innerHTML += `<div style="grid-column: 1 / -1; margin-top: var(--space-md);">
      <h3 style="font-size: 1rem; color: var(--text-secondary); margin-bottom: var(--space-sm);">New Courses to Explore</h3>
      <div class="recommendations-grid">
        ${courseRecs.map(c => `
          <div class="rec-card" style="border-left-color: var(--accent-primary); cursor: pointer;" onclick="enrollCourse('${c.course_name.replace(/'/g, "\\'")}')">
            <div class="rec-card-header">
              <div class="rec-card-title">${c.course_name}</div>
            </div>
            <div class="rec-card-desc">${c.description}</div>
            <div class="rec-card-meta">
              <span>Lectures: ${c.lectures_count}</span>
              <span>Channel: ${c.channel}</span>
            </div>
          </div>
        `).join('')}
      </div>
    </div>`;
  }
}

window.enrollCourse = async function(courseName) {
  try {
    await api(`/learner/${state.learnerId}/enroll`, {
      method: 'POST',
      body: JSON.stringify({ course_name: courseName })
    });
    
    // Reload dashboard to show the new course and updated recommendations
    await loadDashboard();
  } catch (e) {
    alert(`Failed to enroll in course: ${e.message}`);
  }
};

// ===== Learning Session =====
window.startLearning = async function(conceptId) {
  switchView('learn');
  const container = document.getElementById('learn-container');
  container.innerHTML = '<div class="skeleton-card" style="height:300px"></div>';

  try {
    const session = await api('/session/start', {
      method: 'POST',
      body: JSON.stringify({ learner_id: state.learnerId, concept_id: conceptId }),
    });
    state.currentSession = session;
    renderLearningSession(session);
  } catch (e) {
    container.innerHTML = `<div class="learn-placeholder"><h2>Error</h2><p>${e.message}</p></div>`;
  }
};

function renderLearningSession(session) {
  const container = document.getElementById('learn-container');
  let html = '';

  // Video Embed (if available)
  if (session.embed_url) {
    html += `
      <div class="video-embed-container">
        <div class="video-embed-header">
          <span style="font-size:1.2rem">🎬</span>
          <span>${session.video_title || 'Lecture Video'}</span>
        </div>
        <div class="video-embed-wrapper">
          <iframe
            src="${session.embed_url}?enablejsapi=1"
            frameborder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowfullscreen>
          </iframe>
        </div>
      </div>
    `;
  }

  // Phase 1: Retrieval Questions (if any)
  if (session.retrieval_questions && session.retrieval_questions.length > 0) {
    html += `
      <div class="learn-phase">
        <div class="learn-phase-header">
          <div class="phase-number">1</div>
          <div class="phase-title">Retrieval Practice — Activate Your Prior Knowledge</div>
        </div>
        <p style="color:var(--text-secondary);margin-bottom:var(--space-md);font-size:0.9rem">
          Before learning new material, let's activate what you already know. Answer these from memory:
        </p>
        ${session.retrieval_questions.map((rq, i) => `
          <div class="question-card" id="retrieval-q-${i}">
            <div class="question-meta">
              <span class="question-tag">Retrieval</span>
              <span class="question-tag" style="background:var(--warning-bg);color:var(--warning)">${rq.concept || 'Prerequisite'}</span>
            </div>
            <div class="question-text markdown-content">${renderMarkdown(rq.question)}</div>
            <textarea class="written-answer" placeholder="Answer from memory..." id="retrieval-answer-${i}"></textarea>
          </div>
        `).join('')}
        <button class="btn btn-secondary" onclick="revealExplanation()">I've recalled what I can →</button>
      </div>
    `;
  }

  // Phase 2: Explanation
  const phaseNum = session.retrieval_questions?.length > 0 ? 2 : 1;
  html += `
    <div class="learn-phase" id="explanation-phase" ${session.retrieval_questions?.length > 0 ? 'style="display:none"' : ''}>
      <div class="learn-phase-header">
        <div class="phase-number">${phaseNum}</div>
        <div class="phase-title">Learn: ${session.concept_name}</div>
      </div>
      <div class="question-meta" style="margin-bottom:var(--space-md)">
        <span class="question-tag">${session.mastery_level}</span>
        <span class="question-tag" style="background:var(--success-bg);color:var(--success)">Bloom: ${session.bloom_level}</span>
      </div>
      <div class="learn-explanation">${formatExplanation(session.explanation)}</div>
      ${session.key_takeaways ? `
        <div style="margin-top:var(--space-lg);padding:var(--space-md);background:var(--accent-subtle);border-radius:var(--radius-sm)">
          <strong style="color:var(--text-accent)">Key Takeaways:</strong>
          <ul style="margin-top:var(--space-sm);padding-left:var(--space-lg);color:var(--text-secondary)">
            ${(Array.isArray(session.key_takeaways) ? session.key_takeaways : [session.key_takeaways]).map(t => `<li class="markdown-content">${renderMarkdown(t)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    </div>
  `;

  // Phase 3: Doubts
  html += `
    <div class="learn-phase" id="doubt-phase" ${session.retrieval_questions?.length > 0 ? 'style="display:none"' : ''}>
      <div class="learn-phase-header">
        <div class="phase-number">${phaseNum + 1}</div>
        <div class="phase-title">Have a Doubt? Ask Here</div>
      </div>
      ${session.anticipated_doubts?.length ? `
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:var(--space-md)">
          You might be wondering: <em>${Array.isArray(session.anticipated_doubts) ? renderMarkdown(session.anticipated_doubts[0]) : renderMarkdown(session.anticipated_doubts)}</em>
        </p>
      ` : ''}
      <div class="doubt-input-container">
        <input type="text" class="input-field doubt-input" id="doubt-text" placeholder="Type your doubt here..." />
        <button class="btn btn-primary btn-sm" onclick="submitDoubt()">Ask</button>
      </div>
      <div id="doubt-responses"></div>
    </div>
  `;

  // Phase 4: Practice
  html += `
    <div class="learn-phase" id="practice-phase" ${session.retrieval_questions?.length > 0 ? 'style="display:none"' : ''}>
      <div class="learn-phase-header">
        <div class="phase-number">${phaseNum + 2}</div>
        <div class="phase-title">Practice — Test Your Understanding</div>
      </div>
      <button class="btn btn-primary" onclick="loadQuestions('${session.concept_id}')" id="load-questions-btn">Generate Questions</button>
      <div id="questions-container"></div>
    </div>
  `;

  container.innerHTML = html;
}

window.revealExplanation = function() {
  document.getElementById('explanation-phase').style.display = 'block';
  document.getElementById('doubt-phase').style.display = 'block';
  document.getElementById('practice-phase').style.display = 'block';
  // Smooth scroll
  document.getElementById('explanation-phase').scrollIntoView({ behavior: 'smooth' });
};

function renderLatex(text) {
  if (!text) return text;
  // Step 1: Display math $$...$$ (must come before inline to avoid conflicts)
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false });
    } catch (e) {
      return `<pre class="katex-error">${tex}</pre>`;
    }
  });
  // Step 2: Inline math $...$ (but not $$)
  text = text.replace(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g, (match, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: false, throwOnError: false });
    } catch (e) {
      return `<code class="katex-error">${tex}</code>`;
    }
  });
  // Step 3: \( ... \) inline and \[ ... \] display (alternative LaTeX delimiters)
  text = text.replace(/\\\((.+?)\\\)/g, (match, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: false, throwOnError: false });
    } catch (e) {
      return `<code>${tex}</code>`;
    }
  });
  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (match, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false });
    } catch (e) {
      return `<pre>${tex}</pre>`;
    }
  });
  return text;
}

function renderMarkdown(text) {
  if (!text) return '';
  try {
    // Process LaTeX math first (before markdown touches the $ signs)
    text = renderLatex(text);
    return marked.parse(text);
  } catch (e) {
    console.warn('Markdown parse error:', e);
    return text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\n/g,'<br>');
  }
}

// Keep old name as alias for backward compatibility
const formatExplanation = renderMarkdown;

// ===== Doubt Resolution =====
window.submitDoubt = async function() {
  const input = document.getElementById('doubt-text');
  const doubt = input.value.trim();
  if (!doubt || !state.currentSession) return;

  const container = document.getElementById('doubt-responses');
  container.innerHTML += '<div class="skeleton-card" style="height:80px;margin-top:var(--space-md)"></div>';

  try {
    const result = await api('/doubt/resolve', {
      method: 'POST',
      body: JSON.stringify({
        learner_id: state.learnerId,
        concept_id: state.currentSession.concept_id,
        doubt,
      }),
    });

    // Remove skeleton, add response
    const skeletons = container.querySelectorAll('.skeleton-card');
    skeletons.forEach(s => s.remove());

    const miscType = result.misconception_type !== 'none'
      ? `<span class="question-tag" style="background:var(--warning-bg);color:var(--warning)">Misconception: ${result.misconception_type}</span>`
      : '';

    container.innerHTML += `
      <div class="doubt-response">
        <div class="doubt-response-header">Your question: "${doubt}" ${miscType}</div>
        <div class="markdown-content" style="color:var(--text-secondary);font-size:0.9rem;line-height:1.7">${renderMarkdown(result.answer)}</div>
        ${result.follow_up_question ? `
          <p style="margin-top:var(--space-md);color:var(--text-accent);font-size:0.9rem">
            <strong>Think about:</strong> ${result.follow_up_question}
          </p>
        ` : ''}
      </div>
    `;
    input.value = '';
  } catch (e) {
    const skeletons = container.querySelectorAll('.skeleton-card');
    skeletons.forEach(s => s.remove());
    container.innerHTML += `<p style="color:var(--danger);margin-top:var(--space-md)">Error: ${e.message}</p>`;
  }
};

// ===== Question Generation & Answering =====
window.loadQuestions = async function(conceptId) {
  const btn = document.getElementById('load-questions-btn');
  btn.disabled = true;
  btn.textContent = 'Generating...';
  const container = document.getElementById('questions-container');
  container.innerHTML = '<div class="skeleton-card" style="height:200px;margin-top:var(--space-md)"></div>';

  try {
    const result = await api(`/learner/${state.learnerId}/questions/${conceptId}`);
    state.currentQuestions = result.questions || [];
    state.currentQuestionIndex = 0;
    btn.style.display = 'none';
    renderQuestion(0);
  } catch (e) {
    container.innerHTML = `<p style="color:var(--danger)">Error: ${e.message}</p>`;
    btn.disabled = false;
    btn.textContent = 'Generate Questions';
  }
};

function renderQuestion(index) {
  const container = document.getElementById('questions-container');
  if (!state.currentQuestions || index >= state.currentQuestions.length) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--space-xl)">
        <h3 style="color:var(--success)">🎉 All questions completed!</h3>
        <p style="color:var(--text-secondary);margin-top:var(--space-sm)">Great work! Check your updated mastery on the dashboard.</p>
        <button class="btn btn-primary" onclick="switchView('dashboard')" style="margin-top:var(--space-lg)">Back to Dashboard</button>
      </div>
    `;
    return;
  }

  const q = state.currentQuestions[index];
  state.questionStartTime = Date.now();

  let answerSection = '';
  if (q.type === 'mcq' && q.options) {
    answerSection = `
      <div class="mcq-options">
        ${q.options.map((opt, i) => `
          <button class="mcq-option" id="mcq-opt-${i}" data-opt-index="${i}">${opt}</button>
        `).join('')}
      </div>
    `;
  } else {
    answerSection = `
      <textarea class="written-answer" id="written-answer" placeholder="Write your answer..."></textarea>
      <button class="btn btn-primary btn-sm" style="margin-top:var(--space-sm)" onclick="submitWrittenAnswer()">Submit Answer</button>
    `;
  }

  container.innerHTML = `
    <div class="question-card" style="margin-top:var(--space-md)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-md)">
        <div class="question-meta">
          <span class="question-tag">${q.bloom_level || 'understand'}</span>
          <span class="question-tag" style="background:var(--success-bg);color:var(--success)">${q.pattern || 'concept'}</span>
          ${q.interleaved_concept ? `<span class="question-tag" style="background:var(--warning-bg);color:var(--warning)">+ ${q.interleaved_concept}</span>` : ''}
        </div>
        <span style="font-size:0.8rem;color:var(--text-muted)">${index + 1} / ${state.currentQuestions.length}</span>
      </div>
      <div class="question-text markdown-content">${renderMarkdown(q.question)}</div>
      ${answerSection}
      <div id="feedback-container"></div>
    </div>
  `;

  // Attach MCQ click handlers via addEventListener (avoids quoting issues)
  if (q.type === 'mcq' && q.options) {
    q.options.forEach((opt, i) => {
      const btn = document.getElementById(`mcq-opt-${i}`);
      if (btn) btn.addEventListener('click', () => selectMCQ(i, opt));
    });
  }
}

window.selectMCQ = async function(index, answer) {
  // Disable all options
  document.querySelectorAll('.mcq-option').forEach(opt => opt.disabled = true);
  document.getElementById(`mcq-opt-${index}`).classList.add('selected');

  await submitAnswer(answer);
};

window.submitWrittenAnswer = async function() {
  const textarea = document.getElementById('written-answer');
  const answer = textarea.value.trim();
  if (!answer) return;
  textarea.disabled = true;
  await submitAnswer(answer);
};

async function submitAnswer(answer) {
  const responseTime = (Date.now() - state.questionStartTime) / 1000;
  const q = state.currentQuestions[state.currentQuestionIndex];
  const feedbackContainer = document.getElementById('feedback-container');

  feedbackContainer.innerHTML = '<div class="skeleton-card" style="height:80px;margin-top:var(--space-md)"></div>';

  try {
    const result = await api('/evaluate', {
      method: 'POST',
      body: JSON.stringify({
        learner_id: state.learnerId,
        concept_id: state.currentSession.concept_id,
        question: q,
        answer,
        response_time: responseTime,
      }),
    });

    // Show correct/incorrect for MCQ
    if (q.type === 'mcq' && q.options) {
      q.options.forEach((opt, i) => {
        const el = document.getElementById(`mcq-opt-${i}`);
        if (opt === q.correct_answer) el.classList.add('correct');
        else if (opt === answer && !result.is_correct) el.classList.add('incorrect');
      });
    }

    const scoreDisplay = q.type === 'mcq'
      ? (result.is_correct ? '✓ Correct' : '✗ Incorrect')
      : `${result.score}/${result.max_score}`;

    feedbackContainer.innerHTML = `
      <div class="feedback-card ${result.is_correct ? '' : 'incorrect'}">
        <div class="feedback-score">${scoreDisplay}</div>
        <div class="feedback-text markdown-content">${renderMarkdown(result.feedback)}</div>
        <div class="mastery-update">
          📊 Mastery updated to <strong>${Math.round(result.new_mastery * 100)}%</strong>
          | ⏱ Response time: ${responseTime.toFixed(1)}s
          ${result.prerequisites_penalised?.length ? `| ⚠️ Prerequisites flagged for review` : ''}
        </div>
        <button class="btn btn-primary btn-sm" style="margin-top:var(--space-md)"
          onclick="nextQuestion()">
          ${state.currentQuestionIndex < state.currentQuestions.length - 1 ? 'Next Question →' : 'Finish'}
        </button>
      </div>
    `;
  } catch (e) {
    feedbackContainer.innerHTML = `<p style="color:var(--danger)">Evaluation error: ${e.message}</p>`;
  }
}

window.nextQuestion = function() {
  state.currentQuestionIndex++;
  renderQuestion(state.currentQuestionIndex);
};

// ===== Knowledge Graph Visualisation =====
async function loadGraph() {
  if (!state.learnerId) return;
  try {
    const graphData = await api(`/learner/${state.learnerId}/graph`);
    state.graphData = graphData;

    const emptyState = document.getElementById('graph-empty-state');
    const canvas = document.getElementById('graph-canvas');

    if (!graphData.nodes || graphData.nodes.length === 0) {
      if (emptyState) emptyState.style.display = 'block';
      if (canvas) canvas.style.display = 'none';
      return;
    }
    if (emptyState) emptyState.style.display = 'none';
    if (canvas) canvas.style.display = 'block';

    const masteryMap = await api(`/learner/${state.learnerId}/mastery`);

    drawGraph(graphData, masteryMap);
    
    // Also render mastery bars here since they live in this section now
    renderMasteryBars(masteryMap);
  } catch (e) {
    console.error('Graph load failed:', e);
  }
}

function drawGraph(graphData, masteryMap) {
  const canvas = document.getElementById('graph-canvas');
  const ctx = canvas.getContext('2d');
  const wrapper = canvas.parentElement;

  canvas.width = wrapper.clientWidth * 2;
  canvas.height = wrapper.clientHeight * 2;
  canvas.style.width = wrapper.clientWidth + 'px';
  canvas.style.height = wrapper.clientHeight + 'px';
  ctx.scale(2, 2);

  const W = wrapper.clientWidth;
  const H = wrapper.clientHeight;

  // Layout: arrange nodes by lecture/difficulty
  const nodes = graphData.nodes;
  const edges = graphData.edges.filter(e => e.type === 'prerequisite');

  // Group by lecture
  const lectures = {};
  nodes.forEach(n => {
    const lec = n.lecture || 'Other';
    if (!lectures[lec]) lectures[lec] = [];
    lectures[lec].push(n);
  });

  const lecKeys = Object.keys(lectures).sort();
  const colWidth = W / (lecKeys.length + 1);

  // Position nodes
  const positions = {};
  lecKeys.forEach((lec, col) => {
    const nodesInLec = lectures[lec];
    const rowHeight = H / (nodesInLec.length + 1);
    nodesInLec.forEach((n, row) => {
      positions[n.id] = {
        x: (col + 1) * colWidth,
        y: (row + 1) * rowHeight,
      };
    });
  });

  // Draw edges
  ctx.lineWidth = 1.5;
  edges.forEach(e => {
    const from = positions[e.source];
    const to = positions[e.target];
    if (!from || !to) return;

    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    // Curved edges
    const cx = (from.x + to.x) / 2;
    const cy = (from.y + to.y) / 2 - 20;
    ctx.quadraticCurveTo(cx, cy, to.x, to.y);
    ctx.strokeStyle = 'rgba(99, 102, 241, 0.2)';
    ctx.stroke();

    // Arrow
    const angle = Math.atan2(to.y - cy, to.x - cx);
    ctx.beginPath();
    ctx.moveTo(to.x, to.y);
    ctx.lineTo(to.x - 8 * Math.cos(angle - 0.4), to.y - 8 * Math.sin(angle - 0.4));
    ctx.lineTo(to.x - 8 * Math.cos(angle + 0.4), to.y - 8 * Math.sin(angle + 0.4));
    ctx.fillStyle = 'rgba(99, 102, 241, 0.3)';
    ctx.fill();
  });

  // Draw nodes
  nodes.forEach(n => {
    const pos = positions[n.id];
    if (!pos) return;

    const mastery = masteryMap[n.id]?.mastery || 0;
    const radius = 18 + mastery * 8;

    // Node circle
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);

    if (mastery >= 0.7) {
      ctx.fillStyle = 'rgba(99, 102, 241, 0.3)';
      ctx.strokeStyle = '#6366f1';
    } else if (mastery >= 0.2) {
      ctx.fillStyle = 'rgba(245, 158, 11, 0.2)';
      ctx.strokeStyle = '#f59e0b';
    } else {
      ctx.fillStyle = 'rgba(55, 65, 81, 0.3)';
      ctx.strokeStyle = '#374151';
    }

    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();

    // Label
    ctx.fillStyle = '#e8e8ed';
    ctx.font = '500 10px Inter';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Truncate long names
    const name = n.name.length > 18 ? n.name.slice(0, 16) + '…' : n.name;
    ctx.fillText(name, pos.x, pos.y);

    // Mastery percentage below
    if (mastery > 0) {
      ctx.fillStyle = '#9ca3af';
      ctx.font = '400 8px JetBrains Mono';
      ctx.fillText(Math.round(mastery * 100) + '%', pos.x, pos.y + radius + 10);
    }
  });
}

// ===== Review Schedule =====
async function loadReview() {
  if (!state.learnerId) return;

  try {
    const result = await api(`/learner/${state.learnerId}/review-schedule`);
    const container = document.getElementById('review-list');

    if (!result.review_schedule?.length) {
      container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:var(--space-xl)">No concepts need review yet. Keep learning!</p>';
      return;
    }

    container.innerHTML = result.review_schedule.map(item => `
      <div class="review-item">
        <div class="review-item-info">
          <h3>${item.concept_name}</h3>
          <p>Effective mastery: ${Math.round(item.effective_mastery * 100)}% (stored: ${Math.round(item.stored_mastery * 100)}%)</p>
        </div>
        <div style="display:flex;gap:var(--space-md);align-items:center">
          <span class="urgency-badge urgency-${item.urgency}">${item.urgency}</span>
          <button class="btn btn-secondary btn-sm" onclick="startLearning('${item.concept_id}')">Review</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Review load failed:', e);
  }
}

// ===== Resize handler for graph =====
window.addEventListener('resize', () => {
  if (state.currentView === 'graph' && state.graphData) {
    loadGraph();
  }
});
