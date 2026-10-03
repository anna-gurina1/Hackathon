// quiz_edit.js — tap a suggestion to put it into the "Question" field.

const questionInput = document.getElementById('question-text');

document.querySelectorAll('[data-suggestion]').forEach(function (suggestionButton) {
  suggestionButton.addEventListener('click', function () {
    questionInput.value = suggestionButton.dataset.suggestion;
    questionInput.focus();
  });
});
