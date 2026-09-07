import * as esbuild from 'esbuild';
import fs from 'fs';
import path from 'path';

// Scripts to bundle (in order)
const jsFiles = [
    'frontend/js/state.js',
    'frontend/js/i18n_catalogs.js',
    'frontend/js/i18n.js',
    'frontend/js/auth.js',
    'frontend/js/knowledge.js',
    'frontend/js/utils.js',
    'frontend/js/realtime.js',
    'frontend/js/api_socket.js',
    'frontend/js/chat.js',
    'frontend/js/interactive.js',
    'frontend/js/files.js',
    'frontend/js/ui_panels.js',
    'frontend/js/settings_panel.js',
    'frontend/js/update_panel.js',
    'frontend/js/onboard_wizard.js',
    'frontend/js/model_selector.js',
    'frontend/js/auth_ui.js',
    'frontend/js/telegram_mini.js',
    'frontend/js/plugins_panel.js',
    'frontend/js/automation.js',
    'frontend/js/notification-center.js',
    'frontend/js/main.js',
    'frontend/js/profiles.js',
    'frontend/js/speech.js',
    'frontend/select_session.js',
    'frontend/js/mcp_manager.js',
    'frontend/js/connected_apps.js',
    'frontend/js/mentions.js',
    'frontend/js/subagent_ui.js'
];

// Combine JS files
let combinedJs = '';
for (const file of jsFiles) {
    if (fs.existsSync(file)) {
        combinedJs += fs.readFileSync(file, 'utf-8') + '\n;';
    } else {
        console.warn('Missing file:', file);
    }
}
fs.mkdirSync('static', { recursive: true });
fs.writeFileSync('static/bundle-temp.js', combinedJs);

// CSS files (index.css imports everything else)
// We can use esbuild directly on index.css

async function build() {
    console.log('Building CSS...');
    await esbuild.build({
        entryPoints: ['frontend/index.css'],
        bundle: true,
        minify: true,
        outfile: 'static/bundle.css',
    });

    console.log('Building JS...');
    await esbuild.build({
        entryPoints: ['static/bundle-temp.js'],
        bundle: false,
        minify: true,
        outfile: 'static/bundle.js',
    });

    // Clean up
    fs.unlinkSync('static/bundle-temp.js');

    console.log('Updating index.html...');
    let html = fs.readFileSync('frontend/index.html', 'utf-8');
    
    // Replace Vite's relative paths back to /static/ for vendor files that are not bundled
    // Actually, we should just copy the vendor files to static/vendor/
    if (fs.existsSync('frontend/vendor')) {
        fs.cpSync('frontend/vendor', 'static/vendor', { recursive: true });
    }
    
    // Copy assets
    if (fs.existsSync('frontend/assets')) {
        fs.cpSync('frontend/assets', 'static/assets', { recursive: true });
    }
    if (fs.existsSync('frontend/img')) {
        fs.cpSync('frontend/img', 'static/img', { recursive: true });
    }
    if (fs.existsSync('frontend/shibaclaw_logo.webp')) {
        fs.copyFileSync('frontend/shibaclaw_logo.webp', 'static/shibaclaw_logo.webp');
    }
    if (fs.existsSync('frontend/favicon.ico')) {
        fs.copyFileSync('frontend/favicon.ico', 'static/favicon.ico');
    }
    fs.mkdirSync('static/js', { recursive: true });
    fs.copyFileSync('frontend/js/chat_history_window.js', 'static/js/chat_history_window.js');
    fs.mkdirSync('static/css', { recursive: true });
    fs.copyFileSync('frontend/css/sidebar_modern.css', 'static/css/sidebar_modern.css');

    // Rewrite script/link tags
    // 1. Remove all the bundled scripts
    for (const js of jsFiles) {
        const scriptPath = js.replace('frontend', '');
        // e.g. scriptPath = /js/realtime.js or /select_session.js
        const scriptRegex = new RegExp(`<script src="[/]?static${scriptPath}.*?></script>\\s*`, 'g');
        const scriptRegex2 = new RegExp(`<script src="[/]?${scriptPath}.*?></script>\\s*`, 'g');
        const scriptRegex3 = new RegExp(`<script src="\\.${scriptPath}.*?></script>\\s*`, 'g');
        html = html.replace(scriptRegex, '');
        html = html.replace(scriptRegex2, '');
        html = html.replace(scriptRegex3, '');
    }

    const buildVer = Date.now();
    // 2. Replace CSS link
    // Look for index.css and replace it with bundle.css
    html = html.replace(/<link rel="stylesheet" href="\/index\.css[^>]*>/, `<link rel="stylesheet" href="/static/bundle.css?v=${buildVer}">`);
    html = html.replace(
        /^[ \t]*<link rel="stylesheet" href="\/static\/css\/sidebar_modern\.css(?:\?v=[^"]*)?">[ \t]*\r?\n/gm,
        ''
    );
    html = html.replace(
        /(<link rel="stylesheet" href="\/static\/bundle\.css\?v=[^"]+">)/,
        `$1\n    <link rel="stylesheet" href="/static/css/sidebar_modern.css?v=${buildVer}">`
    );
    // Ensure vendor links have /static/
    html = html.replace(/href="\/vendor\//g, 'href="/static/vendor/');
    html = html.replace(/src="\/vendor\//g, 'src="/static/vendor/');
    
    // Ensure images and root files point to /static/
    html = html.replace(/href="\/shibaclaw_logo\.webp"/g, 'href="/static/shibaclaw_logo.webp"');
    html = html.replace(/src="\/shibaclaw_logo\.webp"/g, 'src="/static/shibaclaw_logo.webp"');
    html = html.replace(/href="\/favicon\.ico"/g, 'href="/static/favicon.ico"');
    
    // CSS is fully bundled into bundle.css (no separate static/css tree).
    
    // 3. Add bundle.js and the history override at the end of body, in that order.
    html = html.replace(
        /^[ \t]*<script src="\/static\/js\/chat_history_window\.js(?:\?v=[^"]*)?"><\/script>[ \t]*\r?\n/gm,
        ''
    );
    html = html.replace(
        '</body>',
        `    <script src="/static/bundle.js?v=${buildVer}"></script>\n` +
        `    <script src="/static/js/chat_history_window.js?v=${buildVer}"></script>\n` +
        '</body>'
    );

    fs.writeFileSync('static/index.html', html);
    console.log('Build complete!');
}

build().catch(err => {
    console.error(err);
    process.exit(1);
});
