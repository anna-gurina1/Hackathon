// confetti.js — a short burst of confetti on the "Course completed" page.

const confettiCanvas = document.querySelector('[data-confetti]');

if (confettiCanvas) {
  const pen = confettiCanvas.getContext('2d');
  const colors = ['#f0a33a', '#2c6e5a', '#e35d5b', '#4a7fd4', '#f5d04c'];
  const pieces = [];
  let framesLeft = 180; // about 3 seconds

  function resizeCanvas() {
    confettiCanvas.width = confettiCanvas.offsetWidth;
    confettiCanvas.height = confettiCanvas.offsetHeight;
  }

  function createPieces() {
    for (let i = 0; i < 120; i++) {
      pieces.push({
        x: Math.random() * confettiCanvas.width,
        y: Math.random() * -confettiCanvas.height,
        size: 6 + Math.random() * 6,
        speed: 2 + Math.random() * 3,
        drift: -1 + Math.random() * 2,
        angle: Math.random() * Math.PI,
        color: colors[Math.floor(Math.random() * colors.length)]
      });
    }
  }

  function drawFrame() {
    pen.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);

    pieces.forEach(function (piece) {
      piece.y += piece.speed;
      piece.x += piece.drift;
      piece.angle += 0.1;

      pen.save();
      pen.translate(piece.x, piece.y);
      pen.rotate(piece.angle);
      pen.fillStyle = piece.color;
      pen.fillRect(-piece.size / 2, -piece.size / 4, piece.size, piece.size / 2);
      pen.restore();
    });

    framesLeft--;
    if (framesLeft > 0) {
      requestAnimationFrame(drawFrame);
    } else {
      pen.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
    }
  }

  // People who turned off animations in their phone settings don't get confetti
  const wantsLessMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!wantsLessMotion) {
    resizeCanvas();
    createPieces();
    drawFrame();
  }
}
