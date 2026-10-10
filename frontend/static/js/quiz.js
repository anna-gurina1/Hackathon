// quiz.js — shows "2 of 3 answered" while the person picks answers.

const quizForm = document.querySelector('[data-quiz-form]');

if (quizForm) {
  const answeredCounter = quizForm.querySelector('[data-answered-counter]');
  const totalQuestions = quizForm.querySelectorAll('fieldset').length;

  function updateCounter() {
    const answeredCount = quizForm.querySelectorAll('input[type="radio"]:checked').length;
    answeredCounter.textContent = t('{answered} of {total} answered', { answered: answeredCount, total: totalQuestions });
  }

  quizForm.addEventListener('change', updateCounter);

  // Block double clicks on the submit button
  quizForm.addEventListener('submit', function () {
    const submitButton = quizForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.textContent = t('Checking…');
  });
}
