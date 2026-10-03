// lesson.js — helpers for long lesson videos (up to 15 minutes):
// 1) playback speed buttons, 2) continue from where the person stopped.

const lessonVideo = document.querySelector('[data-lesson-video]');

if (lessonVideo) {
  const videoKey = lessonVideo.dataset.videoKey;          // e.g. "course-1-lesson-2"
  const speedButtons = document.querySelectorAll('[data-speed]');
  const resumeNote = document.querySelector('[data-resume-note]');

  // ---------- 1. Speed ----------
  function setSpeed(newSpeed) {
    lessonVideo.playbackRate = newSpeed;
    localStorage.setItem('video-speed', newSpeed);         // same speed on the next lesson

    speedButtons.forEach(function (button) {
      button.classList.toggle('is-active', Number(button.dataset.speed) === newSpeed);
    });
  }

  speedButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      setSpeed(Number(button.dataset.speed));
    });
  });

  const savedSpeed = Number(localStorage.getItem('video-speed'));
  if (savedSpeed) setSpeed(savedSpeed);

  // ---------- 2. Continue watching ----------
  function formatTime(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(Math.floor(totalSeconds % 60)).padStart(2, '0');
    return minutes + ':' + seconds;
  }

  lessonVideo.addEventListener('loadedmetadata', function () {
    const savedTime = Number(localStorage.getItem(videoKey));
    const almostTheEnd = lessonVideo.duration - 10;

    if (savedTime > 5 && savedTime < almostTheEnd) {
      lessonVideo.currentTime = savedTime;
      resumeNote.textContent = 'Continued from ' + formatTime(savedTime);
      resumeNote.hidden = false;
    }
    // playbackRate resets when the video loads, so set it again
    if (savedSpeed) lessonVideo.playbackRate = savedSpeed;
  });

  // Save the position every 5 seconds while watching
  let lastSavedAt = 0;
  lessonVideo.addEventListener('timeupdate', function () {
    if (Math.abs(lessonVideo.currentTime - lastSavedAt) >= 5) {
      lastSavedAt = lessonVideo.currentTime;
      localStorage.setItem(videoKey, lastSavedAt);
    }
  });

  // Watched to the end — next time start from the beginning
  lessonVideo.addEventListener('ended', function () {
    localStorage.removeItem(videoKey);
  });
}
