document.querySelectorAll('[data-demo]').forEach((button) => {
    const image = document.getElementById(button.getAttribute('aria-controls'));
    const label = button.textContent;
    const error = button.closest('figure').querySelector('.demo-error');

    function stop() {
        button.setAttribute('aria-pressed', 'false');
        button.textContent = label;
        image.src = button.dataset.preview;
    }

    button.addEventListener('click', () => {
        error.hidden = true;
        if (button.getAttribute('aria-pressed') === 'true') {
            stop();
            return;
        }
        button.setAttribute('aria-pressed', 'true');
        button.textContent = 'Stop demo';
        image.src = button.dataset.demo;
    });

    image.addEventListener('error', () => {
        if (button.getAttribute('aria-pressed') === 'true') {
            stop();
            error.hidden = false;
        }
    });
});

document.querySelectorAll('[data-copy]').forEach((button) => {
    const command = document.getElementById(button.dataset.copy);
    const status = document.getElementById('copy-status');
    button.hidden = false;

    button.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(command.textContent.trim());
            button.textContent = 'Copied';
            status.textContent = 'Command copied. Paste it into the terminal shown above it.';
        } catch {
            const range = document.createRange();
            range.selectNodeContents(command);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            status.textContent = 'Command selected. Press Ctrl+C or ⌘C to copy it.';
        }
    });
});
