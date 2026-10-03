// builder.js — video upload in the course studio.
// Videos can be up to 15 minutes, so we:
//   1) check the file BEFORE uploading (format and size),
//   2) show a real progress bar "Uploading… 42%",
//   3) warn if the expert tries to close the page during the upload.

const MAX_VIDEO_SIZE_MB = 500;                     // same as MAX_CONTENT_LENGTH on the server
const ALLOWED_VIDEO_TYPES = ['mp4', 'webm', 'mov'];
const BIG_VIDEO_WARNING_MB = 300;

let uploadIsRunning = false;

function getSizeInMb(file) {
  return file.size / 1024 / 1024;
}

function getExtension(fileName) {
  return fileName.split('.').pop().toLowerCase();
}

// ---------- 1. Show the chosen file and check it ----------
document.querySelectorAll('[data-video-input]').forEach(function (videoInput) {
  videoInput.addEventListener('change', function () {
    const uploadBox = videoInput.closest('.upload-box');
    const fileNameLabel = uploadBox.querySelector('[data-file-name]');
    const chosenVideo = videoInput.files[0];

    if (!chosenVideo) return;

    const sizeInMb = getSizeInMb(chosenVideo);
    let message = '✓ ' + chosenVideo.name + ' (' + sizeInMb.toFixed(0) + ' MB)';

    if (!ALLOWED_VIDEO_TYPES.includes(getExtension(chosenVideo.name))) {
      message = '✕ ' + chosenVideo.name + ' — please choose mp4, webm or mov';
    } else if (sizeInMb > MAX_VIDEO_SIZE_MB) {
      message = '✕ Too big: ' + sizeInMb.toFixed(0) + ' MB (max ' + MAX_VIDEO_SIZE_MB + ' MB). Record in 720p or compress the video.';
    } else if (sizeInMb > BIG_VIDEO_WARNING_MB) {
      message += ' — big file, upload may take a while';
    }

    fileNameLabel.textContent = message;
    uploadBox.classList.add('has-file');
  });
});

// ---------- 2. Upload with a progress bar ----------
document.querySelectorAll('.lesson-form').forEach(function (answerForm) {
  answerForm.addEventListener('submit', function (event) {
    const videoInput = answerForm.querySelector('[data-video-input]');
    const chosenVideo = videoInput ? videoInput.files[0] : null;
    const saveButton = answerForm.querySelector('[data-save-button]');

    // No video — send the form the usual way
    if (!chosenVideo) {
      saveButton.disabled = true;
      saveButton.textContent = 'Saving…';
      return;
    }

    event.preventDefault();

    if (!ALLOWED_VIDEO_TYPES.includes(getExtension(chosenVideo.name))) {
      alert('Please choose an mp4, webm or mov video.');
      return;
    }
    if (getSizeInMb(chosenVideo) > MAX_VIDEO_SIZE_MB) {
      alert('This video is bigger than ' + MAX_VIDEO_SIZE_MB + ' MB. Record it in 720p or compress it first.');
      return;
    }

    uploadWithProgress(answerForm, saveButton);
  });
});

function uploadWithProgress(answerForm, saveButton) {
  const progressBox = answerForm.querySelector('[data-upload-progress]');
  const progressBar = answerForm.querySelector('[data-upload-bar]');
  const progressText = answerForm.querySelector('[data-upload-text]');

  const uploadRequest = new XMLHttpRequest();
  uploadRequest.open('POST', answerForm.action);

  uploadRequest.upload.addEventListener('progress', function (event) {
    if (!event.lengthComputable) return;
    const percent = Math.round((event.loaded / event.total) * 100);
    progressBar.style.width = percent + '%';
    progressText.textContent = percent < 100
      ? 'Uploading… ' + percent + '% — please keep this page open'
      : 'Processing on the server…';
  });

  uploadRequest.addEventListener('load', function () {
    uploadIsRunning = false;
    if (uploadRequest.status < 400) {
      // The server redirects back to the studio — go there to see the new lesson
      window.location.href = uploadRequest.responseURL;
    } else {
      showUploadError('Upload failed (error ' + uploadRequest.status + '). Please try again.');
    }
  });

  uploadRequest.addEventListener('error', function () {
    uploadIsRunning = false;
    showUploadError('Connection lost. Check your internet and try again.');
  });

  function showUploadError(message) {
    progressText.textContent = message;
    progressBar.style.width = '0%';
    saveButton.disabled = false;
    saveButton.textContent = 'Try again';
  }

  progressBox.hidden = false;
  saveButton.disabled = true;
  saveButton.textContent = 'Uploading…';
  uploadIsRunning = true;

  uploadRequest.send(new FormData(answerForm));   // includes csrf_token, title, text and video
}

// ---------- 3. Don't lose a long upload by closing the tab ----------
window.addEventListener('beforeunload', function (event) {
  if (uploadIsRunning) {
    event.preventDefault();
    event.returnValue = '';
  }
});
