import * as esbuild from 'esbuild';
import fs from 'fs';
import path from 'path';

// Scripts to bundle (in order)
const jsFiles = [
    'frontend/js/state.js',
    'frontend/js/auth.js',
    'frontend/js/knowledge.js',
    'frontend/js/utils.js',
    'frontend/js/realtime.js',
    'frontend/js/api_socket.js',
    'frontend/js/chat.js',
    'frontend/js/files.js',
    'frontend/js/ui_panels.js',
    'frontend/js/settings_panel.js',
    'frontend/js/update_panel.js',
    'frontend/js/onboard_wizard.js',
    'frontend/js/model_selector.js',
    'frontend/js/auth_ui.js',
    'frontend/js/plugins_panel.js',
    'frontend/js/automation.js',
    'frontend/js/notification-center.js',
    'frontend/js/main.js',
    'frontend/js/profiles.js',
    'frontend/js/speech.js',
    'frontend/select_session.js',
    'frontend/js/mcp_manager.js',
    'frontend/js/connected_apps.js',
    'frontend/js/mentions.js'
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
    if (fs.existsSync('frontend/js')) {
        fs.cpSync('frontend/js', 'static/js', { recursive: true });
    }
    if (fs.existsSync('frontend/shibaclaw_logo.webp')) {
        fs.copyFileSync('frontend/shibaclaw_logo.webp', 'static/shibaclaw_logo.webp');
    }
    if (fs.existsSync('frontend/favicon.ico')) {
        fs.copyFileSync('frontend/favicon.ico', 'static/favicon.ico');
    }

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

    // 2. Replace CSS link
    // Look for index.css and replace it with bundle.css
    html = html.replace(/<link rel="stylesheet" href="\/index\.css[^>]*>/, '<link rel="stylesheet" href="/static/bundle.css">');
    // Ensure vendor links have /static/
    html = html.replace(/href="\/vendor\//g, 'href="/static/vendor/');
    html = html.replace(/src="\/vendor\//g, 'src="/static/vendor/');
    
    // Ensure remaining /js/ links point to /static/js/
    html = html.replace(/src="\/js\//g, 'src="/static/js/');

    // Ensure images and root files point to /static/
    html = html.replace(/href="\/shibaclaw_logo\.webp"/g, 'href="/static/shibaclaw_logo.webp"');
    html = html.replace(/src="\/shibaclaw_logo\.webp"/g, 'src="/static/shibaclaw_logo.webp"');
    html = html.replace(/href="\/favicon\.ico"/g, 'href="/static/favicon.ico"');
    
    // Ensure all remaining /css/ links point to /static/css/
    html = html.replace(/href="\/css\//g, 'href="/static/css/');
    
    // Copy the css folder as well so unbundled css files are available
    if (fs.existsSync('frontend/css')) {
        fs.cpSync('frontend/css', 'static/css', { recursive: true });
    }
    
    // 3. Add bundle.js at the end of body
    html = html.replace('</body>', '    <script src="/static/bundle.js"></script>\n</body>');

    fs.writeFileSync('static/index.html', html);
    console.log('Build complete!');
}

build().catch(err => {
    console.error(err);
    process.exit(1);
});
