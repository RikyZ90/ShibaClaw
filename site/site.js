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

const projectInfo = document.querySelector?.('.hero-notes');
if (projectInfo) {
    const badges = [
        {
            href: 'https://pepy.tech/projects/shibaclaw',
            src: 'https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads',
            alt: 'PyPI total downloads',
            width: 116,
        },
        {
            href: 'https://hub.docker.com/r/rikyz90/shibaclaw',
            src: 'https://img.shields.io/docker/pulls/rikyz90/shibaclaw?style=flat-square',
            alt: 'Docker Hub pulls',
            width: 102,
        },
    ];

    badges.forEach(({ href, src, alt, width }) => {
        const link = document.createElement('a');
        link.href = href;
        link.setAttribute('aria-label', alt);

        const badge = document.createElement('img');
        badge.src = src;
        badge.alt = alt;
        badge.width = width;
        badge.height = 20;
        badge.decoding = 'async';

        link.appendChild(badge);
        projectInfo.appendChild(link);
    });
}
