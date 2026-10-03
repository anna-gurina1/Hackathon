// pages.js — small helpers shared by several pages.

// "Copy" buttons: <button data-copy-from="input-id">Copy</button>
// copy the value of the input with that id.
document.querySelectorAll('[data-copy-from]').forEach(function (copyButton) {
  copyButton.addEventListener('click', function () {
    const linkInput = document.getElementById(copyButton.dataset.copyFrom);
    const oldText = copyButton.textContent;

    navigator.clipboard.writeText(linkInput.value).then(function () {
      copyButton.textContent = 'Copied ✓';
      setTimeout(function () { copyButton.textContent = oldText; }, 1500);
    });
  });
});
