const fs = require('fs');
let taskMd = fs.readFileSync('c:/Users/Rikyz/.shibaclaw/workspace/TASK.md', 'utf8');

const taskName = "ansa";
const escapedName = taskName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const reExisting = new RegExp(`(^|\\n)### Task: ${escapedName}\\s*\\n[\\s\\S]*?(?=\\n### |\\n## |$)`, 'g');
const cleaned = taskMd.replace(reExisting, '');

console.log("OLD:");
console.log(taskMd);
console.log("NEW:");
console.log(cleaned);
