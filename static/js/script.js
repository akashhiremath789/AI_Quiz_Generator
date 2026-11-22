/* ===== AI Quiz Generator - Frontend script ===== */
(function () {
  'use strict';

  /* ---------- Sidebar (mobile) ---------- */
  const sidebar = document.getElementById('sidebar');
  const scrim = document.getElementById('scrim');
  const menuBtn = document.getElementById('menuBtn');
  function toggleSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle('open', open);
    scrim.classList.toggle('open', open);
  }
  if (menuBtn) menuBtn.addEventListener('click', () => toggleSidebar(!sidebar.classList.contains('open')));
  if (scrim) scrim.addEventListener('click', () => toggleSidebar(false));

  /* ---------- Form validation + loading state ---------- */
  function showError(input, message) {
    input.classList.add('invalid');
    const err = input.closest('.form-group')?.querySelector('.field-error');
    if (err) { err.textContent = message; err.style.display = 'block'; }
  }
  function clearError(input) {
    input.classList.remove('invalid');
    const err = input.closest('.form-group')?.querySelector('.field-error');
    if (err) { err.textContent = ''; err.style.display = 'none'; }
  }
  function validateField(input) {
    clearError(input);
    if (input.type === 'file') return true; // handled by the upload helper
    const value = input.value.trim();
    const label = input.closest('.form-group')?.querySelector('label')?.textContent.trim() || 'This field';
    if (input.required && !value) { showError(input, label + ' is required.'); return false; }
    if (input.type === 'email' && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      showError(input, 'Enter a valid email address.'); return false;
    }
    const min = parseInt(input.getAttribute('minlength') || '0', 10);
    if (min && value.length < min) { showError(input, 'Use at least ' + min + ' characters.'); return false; }
    const matchId = input.dataset.match;
    if (matchId && value !== document.getElementById(matchId).value) {
      showError(input, 'Passwords do not match.'); return false;
    }
    return true;
  }

  document.querySelectorAll('form[data-validate]').forEach(form => {
    const fields = form.querySelectorAll('input[type=text],input[type=email],input[type=password],input[type=file]');
    fields.forEach(f => f.addEventListener('blur', () => validateField(f)));
    form.addEventListener('submit', e => {
      let ok = true;
      fields.forEach(f => { if (!validateField(f)) ok = false; });
      const fileInput = form.querySelector('input[type=file]');
      if (fileInput && !checkFile(fileInput)) ok = false;
      if (!ok) { e.preventDefault(); form.querySelector('.invalid')?.focus(); return; }
      if (form.hasAttribute('data-loading')) {
        const btn = form.querySelector('button[type=submit]');
        if (btn.disabled) { e.preventDefault(); return; } // block double submit
        btn.classList.add('is-loading');
        const label = btn.querySelector('.label');
        if (label && label.dataset.loadingText) label.textContent = label.dataset.loadingText;
        setTimeout(() => { btn.disabled = true; }, 0);
      }
    });
  });

  /* ---------- PDF upload (drag & drop + client checks) ---------- */
  const fileInput = document.getElementById('pdf_file');
  const dropzone = document.getElementById('dropzone');
  const fileName = document.getElementById('fileName');
  const fileError = document.getElementById('fileError');

  function checkFile(input) {
    if (!fileError || input.id !== 'pdf_file') return true;
    fileError.style.display = 'none';
    const file = input.files[0];
    const maxMb = parseInt(input.dataset.maxMb || '10', 10);
    let msg = '';
    if (!file) msg = 'Choose a PDF file to upload.';
    else if (!file.name.toLowerCase().endsWith('.pdf')) msg = 'Only PDF files are allowed.';
    else if (file.size > maxMb * 1024 * 1024) msg = 'File is too large. The limit is ' + maxMb + ' MB.';
    else if (file.size === 0) msg = 'This file is empty.';
    if (msg) { fileError.textContent = msg; fileError.style.display = 'block'; return false; }
    return true;
  }
  if (fileInput && dropzone) {
    fileInput.addEventListener('change', () => {
      fileName.textContent = fileInput.files[0] ? fileInput.files[0].name : '';
      checkFile(fileInput);
    });
    ['dragenter', 'dragover'].forEach(ev => dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.add('drag'); }));
    ['dragleave', 'drop'].forEach(ev => dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.remove('drag'); }));
    dropzone.addEventListener('drop', e => {
      if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        fileInput.dispatchEvent(new Event('change'));
      }
    });
  }

  /* ---------- Interactive quiz ---------- */
  if (window.QUIZ_DATA) initQuiz(window.QUIZ_DATA);

  function initQuiz(data) {
    const questions = data.questions;
    const total = questions.length;
    const answers = {};          // { questionId: 'A' | 'B' | 'C' | 'D' }
    const marked = new Set();    // questionIds marked for review
    let current = 0;
    let remaining = data.timeLimit;
    let submitted = false;

    const $ = id => document.getElementById(id);
    const qNum = $('qNum'), qText = $('qText'), optionsEl = $('options');
    const prevBtn = $('prevBtn'), nextBtn = $('nextBtn'), markBtn = $('markBtn');
    const paletteEl = $('palette'), timerEl = $('timer'), timeLeft = $('timeLeft');
    const modal = $('confirmModal');

    function fmt(s) {
      const m = Math.floor(s / 60), r = s % 60;
      return String(m).padStart(2, '0') + ':' + String(r).padStart(2, '0');
    }

    function renderQuestion() {
      const q = questions[current];
      qNum.textContent = 'Question ' + (current + 1) + ' of ' + total;
      qText.textContent = q.question_text;
      optionsEl.innerHTML = '';
      ['A', 'B', 'C', 'D'].forEach(letter => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'option' + (answers[q.id] === letter ? ' selected' : '');
        btn.setAttribute('aria-pressed', answers[q.id] === letter);
        const l = document.createElement('span'); l.className = 'opt-letter'; l.textContent = letter;
        const t = document.createElement('span'); t.textContent = q['option_' + letter.toLowerCase()];
        btn.append(l, t);
        btn.addEventListener('click', () => {
          // clicking the selected option again clears the answer
          if (answers[q.id] === letter) delete answers[q.id]; else answers[q.id] = letter;
          renderQuestion();
        });
        optionsEl.appendChild(btn);
      });
      prevBtn.disabled = current === 0;
      nextBtn.textContent = current === total - 1 ? 'Review & submit' : 'Next →';
      markBtn.classList.toggle('on', marked.has(q.id));
      markBtn.textContent = marked.has(q.id) ? '⚑ Marked' : '⚑ Mark for review';
      renderPalette();
      renderProgress();
    }

    function renderPalette() {
      paletteEl.innerHTML = '';
      questions.forEach((q, i) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = i + 1;
        b.className = 'pal' + (answers[q.id] ? ' answered' : '') + (marked.has(q.id) ? ' marked' : '') + (i === current ? ' current' : '');
        b.setAttribute('aria-label', 'Go to question ' + (i + 1));
        b.addEventListener('click', () => { current = i; renderQuestion(); });
        paletteEl.appendChild(b);
      });
    }

    function renderProgress() {
      const answered = Object.keys(answers).length;
      $('progressBar').style.width = Math.round((answered / total) * 100) + '%';
      $('progressText').textContent = 'Question ' + (current + 1) + ' of ' + total;
      $('answeredText').textContent = answered + ' of ' + total + ' answered' + (marked.size ? ' · ' + marked.size + ' marked' : '');
    }

    prevBtn.addEventListener('click', () => { if (current > 0) { current--; renderQuestion(); } });
    nextBtn.addEventListener('click', () => {
      if (current < total - 1) { current++; renderQuestion(); } else openConfirm();
    });
    markBtn.addEventListener('click', () => {
      const id = questions[current].id;
      marked.has(id) ? marked.delete(id) : marked.add(id);
      renderQuestion();
    });
    document.addEventListener('keydown', e => {
      if (modal.classList.contains('open') || ['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
      if (e.key === 'ArrowRight' && current < total - 1) { current++; renderQuestion(); }
      if (e.key === 'ArrowLeft' && current > 0) { current--; renderQuestion(); }
    });

    /* Submit flow */
    function openConfirm() {
      const answered = Object.keys(answers).length;
      $('confirmSummary').innerHTML =
        '<span>Answered: <strong>' + answered + '</strong> of ' + total + '</span>' +
        '<span>Unanswered: <strong>' + (total - answered) + '</strong></span>' +
        '<span>Marked for review: <strong>' + marked.size + '</strong></span>';
      modal.classList.add('open');
      $('confirmSubmit').focus();
    }
    $('submitBtn').addEventListener('click', openConfirm);
    $('cancelSubmit').addEventListener('click', () => modal.classList.remove('open'));
    $('confirmSubmit').addEventListener('click', () => submitQuiz());

    function submitQuiz() {
      if (submitted) return;            // prevent multiple submissions
      submitted = true;
      clearInterval(timer);
      $('confirmSubmit').disabled = true;
      $('submitBtn').disabled = true;
      $('answersInput').value = JSON.stringify(answers);
      $('timeTakenInput').value = Math.max(0, data.timeLimit - remaining);
      $('submitForm').submit();
    }

    /* Countdown timer */
    function tick() {
      timeLeft.textContent = fmt(remaining);
      timerEl.classList.toggle('low', remaining <= 60);
      if (remaining <= 0) { submitQuiz(); return; }
      remaining--;
    }
    const timer = setInterval(tick, 1000);
    tick();

    window.addEventListener('beforeunload', e => {
      if (!submitted && Object.keys(answers).length) { e.preventDefault(); e.returnValue = ''; }
    });

    renderQuestion();
  }
})();
