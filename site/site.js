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
    const signals = document.createElement('div');
    signals.setAttribute('aria-label', 'Project distribution signals');
    signals.style.display = 'flex';
    signals.style.alignItems = 'center';
    signals.style.flexWrap = 'wrap';
    signals.style.gap = '12px';
    signals.style.marginTop = '12px';

    const badges = [
        {
            href: 'https://pepy.tech/projects/shibaclaw',
            src: 'https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=101113&right_color=101113&left_text=PyPI%20downloads',
            alt: 'PyPI total downloads',
        },
        {
            href: 'https://hub.docker.com/r/rikyz90/shibaclaw',
            src: 'https://img.shields.io/docker/pulls/rikyz90/shibaclaw?style=flat-square&label=Docker%20pulls&labelColor=101113&color=101113',
            alt: 'Docker Hub pulls',
        },
    ];

    badges.forEach(({ href, src, alt }) => {
        const link = document.createElement('a');
        link.href = href;
        link.setAttribute('aria-label', alt);
        link.style.display = 'inline-flex';
        link.style.alignItems = 'center';
        link.style.opacity = '0.82';

        const badge = document.createElement('img');
        badge.src = src;
        badge.alt = alt;
        badge.height = 16;
        badge.style.height = '16px';
        badge.style.width = 'auto';
        badge.decoding = 'async';
        badge.loading = 'lazy';

        link.appendChild(badge);
        signals.appendChild(link);
    });

    projectInfo.insertAdjacentElement('afterend', signals);
}
