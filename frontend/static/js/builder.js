// builder.js — nicer video upload in the course builder.

// 1. When a video is chosen, show its name and size instead of "Tap to choose".
document.querySelectorAll('[data-video-input]').forEach(function (videoInput) {
  videoInput.addEventListener('change', function () {
    const uploadBox = videoInput.closest('.upload-box');
    const fileNameLabel = uploadBox.querySelector('[data-file-name]');
    const chosenVideo = videoInput.files[0];

    if (!chosenVideo) return;

    const sizeInMb = (chosenVideo.size / 1024 / 1024).toFixed(1);
    fileNameLabel.textContent = '✓ ' + chosenVideo.name + ' (' + sizeInMb + ' MB)';
    uploadBox.classList.add('has-file');
  });
});

// 2. Videos are big, so show "Uploading…" and block the button while it's sending.
document.querySelectorAll('.answer-form').forEach(function (answerForm) {
  answerForm.addEventListener('submit', function () {
    const saveButton = answerForm.querySelector('[data-save-button]');
    saveButton.disabled = true;
    saveButton.textContent = 'Uploading…';
  });
});
