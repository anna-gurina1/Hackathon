// studio.js — the minimal "create course" page and the course studio.
//   1) "+" and "Edit" buttons open hidden forms (data-reveal="id-of-the-block")
//   2) "Cancel" hides the form again
//   3) suggested questions follow the chosen learner level
//   4) "Use" puts a suggested question into a new lesson

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
