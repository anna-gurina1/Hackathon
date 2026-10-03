// studio.js — the minimal "create course" page and the course studio.
//   1) "+" and "Edit" buttons open hidden forms (data-reveal="id-of-the-block")
//   2) "Cancel" hides the form again
//   3) suggested questions follow the chosen learner level
//   4) "Use" puts a suggested question into a new lesson
//   5) "Show AI suggestions" adds one question from the AI to every topic of the side panel

// ---------- 1. Open hidden blocks ----------
document.querySelectorAll('[data-reveal]').forEach(function (revealButton) {
  revealButton.addEventListener('click', function () {
    const hiddenBlock = document.getElementById(revealButton.dataset.reveal);
    hiddenBlock.hidden = false;

    // the big "+" disappears while its form is open
    if (revealButton.classList.contains('plus-tile')) revealButton.hidden = true;

    const firstInput = hiddenBlock.querySelector('input[type="text"], textarea');
    if (firstInput) firstInput.focus();
  });
});

// ---------- 2. Cancel ----------
document.querySelectorAll('[data-cancel-form]').forEach(function (cancelButton) {
  cancelButton.addEventListener('click', function () {
    const formBlock = cancelButton.closest('[id]');
    formBlock.hidden = true;

    const plusTile = document.querySelector('[data-reveal="' + formBlock.id + '"].plus-tile');
    if (plusTile) plusTile.hidden = false;
  });
});

// ---------- 3. Suggested questions follow the level ----------
const levelPicker = document.querySelector('[data-level-picker]');

function showQuestionsForLevel(levelKey) {
  document.querySelectorAll('.suggest-item').forEach(function (item) {
    item.hidden = !item.dataset.levels.split(' ').includes(levelKey);
  });
  // hide a module when all its questions are hidden, and update the number next to its name
  document.querySelectorAll('.suggest-group').forEach(function (group) {
    const visibleCount = group.querySelectorAll('.suggest-item:not([hidden])').length;
    group.hidden = visibleCount === 0;
    const counter = group.querySelector('[data-suggest-count]');
    if (counter) counter.textContent = visibleCount;
  });
}

if (levelPicker) {
  levelPicker.addEventListener('change', function (event) {
    showQuestionsForLevel(event.target.value);
  });
  const checkedLevel = levelPicker.querySelector('input:checked');
  if (checkedLevel) showQuestionsForLevel(checkedLevel.value);
}

// ---------- 4. "Use" a suggested question for a new lesson ----------
const newLessonBlock = document.getElementById('new-lesson');

document.querySelectorAll('[data-use-question]').forEach(function (useButton) {
  useButton.addEventListener('click', function () {
    if (!newLessonBlock) return;

    newLessonBlock.hidden = false;
    const addLessonButton = document.getElementById('add-lesson-button');
    if (addLessonButton) addLessonButton.hidden = true;

    const questionPrompt = newLessonBlock.querySelector('[data-question-prompt]');
    questionPrompt.textContent = '💡 Idea for this lesson: ' + useButton.dataset.questionText;
    questionPrompt.hidden = false;
    newLessonBlock.querySelector('[data-question-id]').value = useButton.dataset.useQuestion;

    newLessonBlock.scrollIntoView({ behavior: 'smooth', block: 'start' });
    newLessonBlock.querySelector('[data-lesson-title]').focus({ preventScroll: true });
  });
});

// ---------- 5. "Show AI suggestions": one question from the AI in every topic ----------
function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.setAttribute('role', 'status');
  toast.textContent = message;
  document.body.appendChild(toast);
  requestAnimationFrame(function () { toast.classList.add('is-visible'); });
  setTimeout(function () {
    toast.classList.remove('is-visible');
    setTimeout(function () { toast.remove(); }, 400);   // after the fade-out
  }, 4000);
}

const aiButton = document.querySelector('[data-ai-suggest]');

if (aiButton) {
  const courseForm = aiButton.closest('form');
  const aiFieldNames = ['title', 'description', 'topic', 'profession', 'outcome'];

  aiButton.addEventListener('click', async function () {
    // read what the company has typed so far
    const typed = {};
    aiFieldNames.forEach(function (name) {
      const field = courseForm.elements[name];
      typed[name] = field ? field.value.trim() : '';
    });
    const checkedLevel = courseForm.querySelector('input[name="level"]:checked');
    typed.level = checkedLevel ? checkedLevel.value : '';

    if (!aiFieldNames.some(function (name) { return typed[name] !== ''; })) {
      showToast('Fill in the course details first (title, topic or profession) so the AI knows what to suggest.');
      return;
    }

    const normalLabel = aiButton.textContent;
    aiButton.disabled = true;
    aiButton.textContent = 'Thinking…';

    try {
      const response = await fetch(aiButton.dataset.aiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': courseForm.elements['csrf_token'].value,
        },
        body: JSON.stringify(typed),
      });
      if (!response.ok) throw new Error('AI request failed: ' + response.status);
      const data = await response.json();
      showAiQuestions(data.questions || {});
      showToast('Done! One tip from AI was added to each topic on the right.');
    } catch (error) {
      showToast('AI suggestions are not available right now. Please try again later.');
    } finally {
      aiButton.disabled = false;
      aiButton.textContent = normalLabel;
    }
  });
}

function showAiQuestions(questionsByCategory) {
  // new suggestions replace the old ones
  document.querySelectorAll('.suggest-ai').forEach(function (old) { old.remove(); });

  const allLevels = levelPicker
    ? Array.from(levelPicker.querySelectorAll('input')).map(function (input) { return input.value; }).join(' ')
    : 'beginner intermediate advanced';
  let firstGroup = null;

  document.querySelectorAll('.suggest-group').forEach(function (group) {
    const text = questionsByCategory[group.dataset.category];
    if (!text) return;

    const item = document.createElement('div');
    item.className = 'suggest-item suggest-ai';
    item.dataset.levels = allLevels;                 // always visible, whatever the level is

    const body = document.createElement('div');
    body.className = 'suggest-ai-body';
    const question = document.createElement('em');
    question.textContent = text;                     // textContent: the AI text is never run as HTML
    const tag = document.createElement('span');
    tag.className = 'ai-tag';
    tag.textContent = 'tip from AI';
    body.append(question, tag);
    item.appendChild(body);

    group.appendChild(item);
    if (!firstGroup) firstGroup = group;
  });

  // refresh the numbers next to the topic names, open the first topic so the change is noticed
  const levelNow = levelPicker && levelPicker.querySelector('input:checked');
  if (levelNow) showQuestionsForLevel(levelNow.value);
  if (firstGroup) firstGroup.open = true;
}
