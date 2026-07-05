import re

with open('shibaclaw/webui/static/index.html', 'r') as f:
    content = f.read()

# Replace aria-label="sk-..." with aria-label="API Key"
content = re.sub(r'aria-label="sk-\.\.\."', r'aria-label="API Key"', content)

with open('shibaclaw/webui/static/index.html', 'w') as f:
    f.write(content)
