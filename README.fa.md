<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="800" alt="ShibaClaw">
</p>
<div dir="rtl">

<h1 align="center">ShibaClaw</h1>

<h3 align="center">
AI Agentی که <b>فقط کار می‌کنه</b> — امن، خصوصی، بدون اینکه لازم باشه مدام حواست بهش باشه.
</h3>

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>   
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>
<p align="center">
<b>28 Provider · 11 Chat Channel · WebUI داخلی · هسته با تمرکز روی امنیت · آماده برای MCP</b>
</p>

<h3 align="center">
بر پایه سه اصل:
<b>سادگی · امنیت · حریم خصوصی</b>
</h3>

</div>

<p align="center">
    <a href="./README.md">English</a> &nbsp;·&nbsp;
  <a href="./README.zh-CN.md">简体中文</a> &nbsp;·&nbsp;
  <a href="./README.es.md">Español</a> &nbsp;·&nbsp;
  <a href="./README.pt-BR.md">Português (BR)</a> &nbsp;·&nbsp;
  <a href="./README.ja.md">日本語</a> &nbsp;·&nbsp;
  <a href="./README.de.md">Deutsch</a> &nbsp;·&nbsp;
  <a href="./README.fr.md">Français</a>
</p>

---

<div dir="rtl">

<blockquote>
<p><strong>⚠️ هشدار</strong></p>

<p>
اگر بعد از آپدیت به نسخه <strong>v0.9.5</strong> یا بالاتر با مشکل ورود به <strong>WebUI</strong> مواجه شدید،
دستور <code>shibaclaw reset-admin</code> را در <strong>Terminal</strong> یا <strong>Console</strong> اجرا کنید تا دوباره به برنامه دسترسی پیدا کنید.
</p>
</blockquote>

<details open>

<summary><strong>📢 آخرین نسخه: v0.9.7</strong> — برای دیدن تغییرات کلیک کنید</summary>

<h3>➕ اضافه شده</h3>

<ul>
<li>
<strong>🎨 بازطراحی کامل ظاهر و نوسازی هویت برند</strong> — ظاهر کل برنامه به‌صورت کامل بازطراحی شده و هویت بصری ShibaClaw به‌روزرسانی شده است. تمام فایل‌های لوگو (از <code>16px</code> تا <code>256px</code>، به‌همراه نسخه‌های <code>ICO</code> و <code>WebP</code>) با لوگوی جدید ShibaClaw جایگزین شده‌اند. همچنین صفحه خوش‌آمدگویی WebUI، بخش Settings، رابط Chat و Profile Selectorها همگی با یک طراحی یکپارچه و مدرن به‌روزرسانی شده‌اند.
</li>

<li>
<strong>🐕 هویت بصری Hacker Mode</strong> — Avatar اختصاصی پروفایل <strong>Hacker</strong> (<code>ShibHacker.png</code>) با طراحی Cyber-Shiba برای شخصیت امنیت‌محور اضافه شده است.
</li>
</ul>

<h3>🐞 رفع شده</h3>

<ul>

<li><strong>بسته‌بندی Local RAG در نسخه Windows EXE</strong> — مشکلی که باعث می‌شد بعد از نصب نسخه <code>.exe</code> ویندوز، Plugin مربوط به <strong>Local RAG &amp; Knowledge Base</strong> قابل استفاده نباشد برطرف شد. حالا وابستگی‌های <code>langchain</code>، <code>faiss-cpu</code>، <code>sentence-transformers</code>، <code>pypdf</code> و <code>beautifulsoup4</code> مستقیماً داخل فایل <code>.exe</code> قرار می‌گیرند.</li>

<li><strong>Hot-Reload لحظه‌ای برای نصب و حذف Local RAG</strong> — مدیریت <code>knowledge_manager.py</code> و <code>plugins.py</code> بازنویسی شده تا وضعیت <code>langchain</code>، <code>langchain_community</code> و <code>faiss</code> به‌صورت پویا بررسی شود و کش <code>sys.modules</code> بعد از حذف Plugin پاک شود. حالا نصب یا حذف Plugin بدون نیاز به Restart کردن سرور، بلافاصله در WebUI اعمال می‌شود.</li>

<li><strong>حذف کامل وابستگی‌های RAG</strong> — وابستگی‌های <code>langchain-core</code> و <code>langchain-text-splitters</code> هم به فرآیند حذف Plugin اضافه شدند تا هیچ وابستگی اضافه‌ای داخل <code>site-packages</code> باقی نماند.</li>

<li><strong>Memory Leak</strong> — Memory Leakهای موجود در WebSocket Handlerها و Message Queueها (<code>shibaclaw/agent/context.py</code> و <code>loop.py</code>) برطرف شدند.</li>

<li><strong>Concurrency Lockها</strong> — برای جلوگیری از Race Condition، مکانیزم نگهداری Strong Reference Lock در <code>PackMemory</code> و <code>ShibaBrain</code> پیاده‌سازی شد.</li>

<li><strong>MCP Deadlock</strong> — مشکل Deadlock هنگام اتصال مجدد در <code>MCPManager</code> برطرف شد.</li>

<li><strong>Timeoutها</strong> — مقدار Timeoutها در <code>ExecTool</code> و Execution Loop به حداقل <code>max(0.1, ...)</code> محدود شدند.</li>

<li><strong>ذخیره Sessionها</strong> — مشکل نبودن <code>import os</code> برطرف شد و ذخیره Sessionها به‌صورت Atomic با فایل‌های <code>.jsonl.tmp</code> در <code>manager.py</code> انجام می‌شود.</li>

<li><strong>ایمنی Initialization</strong> — بررسی‌های Null و افزایش ایمنی Timestampها در <code>memory.py</code> و مقداردهی اولیه Providerهای Sub-agent اضافه شد.</li>

<li><strong>تکرار Session در Automationها</strong> — مشکلی که باعث می‌شد Automationهای پس‌زمینه Session همان Chatی که از آن ساخته شده بودند را به ارث ببرند (و در نتیجه پیام‌های تکراری و Historyهای به‌هم‌ریخته ایجاد شود) برطرف شد. حالا <code>AutomationTool</code> به‌صورت پیش‌فرض Jobها را داخل یک Session جداگانه اجرا می‌کند، مگر اینکه <code>target_channel</code> مشخص شده باشد.</li>

<li><strong>پر شدن Context در Sub-agentها</strong> — در <code>SubagentManager</code> مکانیزم Truncate کردن Context و فشرده‌سازی Tokenها (حذف بلاک‌های <code>think</code> و محدود کردن خروجی Tool ها به <code>1500</code> کاراکتر) اضافه شد تا از خطاهای <strong>"Token Window Exceeded"</strong> در Taskهای طولانی و موازی جلوگیری شود.</li>

</ul>

<h3>🔄 تغییر کرده</h3>

<ul>
<li><strong>تقویت CI Pipeline و محیط Build</strong> — مراحل Windows CI Workflow به‌گونه‌ای تنظیم شدند که از <code>shell: bash</code> استفاده کنند تا مشکلات مربوط به پردازش براکت‌ها و کوتیشن‌ها در PowerShell هنگام اجرای دستورهای <code>pip install</code> با چندین Extra برطرف شود. همچنین بررسی‌های اولیه Import در <code>scripts/build_windows.py</code> اضافه شده‌اند.</li>
</ul>

<h3>⚡ بهینه‌سازی شده</h3>

<ul>

<li><strong>پردازش Core Loop</strong> — مقداردهی اولیه <code>KnowledgeManager</code> و فراخوانی‌های <code>list_collections</code> از حلقه غیرهمزمان <code>_run_agent_loop</code> خارج شدند تا عملیات‌های تکراری I/O و Threadهای پس‌زمینه به‌طور قابل‌توجهی کاهش پیدا کنند.</li>

<li><strong>Caching و Lockهای FAISS Vectorstore</strong> — سیستم Cache مربوط به FAISS Vectorstore بهینه شده و مکانیزم جایگزین برای File Lock در ویندوز اضافه شده است.</li>

<li><strong>افزودن History با پیچیدگی O(1)</strong> — حالت افزودن History با پیچیدگی زمانی <code>O(1)</code> در <code>ScentKeeper</code> پیاده‌سازی شده است.</li>

</ul>

<p>
برای مشاهده تاریخچه کامل نسخه‌ها، فایل
<a href="./CHANGELOG.md">Changelog</a>
را ببینید.
</p>

</details>

</div>

---

<p align="center">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
</p>

---

<div dir="rtl">

<h2>⚡ شروع سریع</h2>

<h3>🚀 نصب خودکار (پیشنهادی)</h3>

<p>
ساده‌ترین راه برای شروع. با اجرای فقط یک دستور، آخرین نسخه دانلود می‌شود، میانبرها ساخته می‌شوند و رابط کاربری اجرا خواهد شد.
</p>

<p>
<strong>مدل خودت رو استفاده کن:</strong>
به‌راحتی به Endpointهای محلی مثل <strong>Ollama</strong> و <strong>LM Studio</strong> متصل شو یا از پلن‌های رایگان API در <strong>OpenRouter</strong> استفاده کن و بدون هیچ هزینه‌ای شروع به چت کردن کن.
</p>

</div>

**Windows (PowerShell):**

```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS (Terminal):**

```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

<div dir="rtl">

<blockquote>

<p><strong>نکته</strong></p>

<p>
در ویندوز، این دستور آخرین نسخه آماده برنامه را مستقیماً از GitHub Release دانلود می‌کند و نیازی به نصب Python نیست.
میانبرهای Desktop و Start Menu به‌صورت خودکار ساخته می‌شوند و برنامه نیز برای حذف آسان در بخش <strong>Apps &amp; Features</strong> ویندوز ثبت می‌شود.
</p>

<p>
در Linux و macOS، اسکریپت برنامه را از طریق <code>pip</code> داخل یک Virtual Environment ایزوله نصب می‌کند.
</p>

</blockquote>

</div>

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d
docker exec -it shibaclaw-gateway shibaclaw print-token
```

<div dir="rtl" align="right" style="direction: rtl; text-align: right;">

<p>
<strong dir="ltr">http://localhost:3000</strong>
را باز کنید، 
<span dir="ltr">Token</span>
را وارد کنید و مراحل راه‌اندازی اولیه را دنبال کنید.
</p>

<p>
اگر
<code dir="ltr">shibaclaw-web</code>
را روی شبکه محلی
<span dir="ltr">(LAN)</span>
خود در دسترس قرار دهید (مثلاً با استفاده از
<span dir="ltr">Reverse Proxy</span>)،
می‌توانید همان آدرس را از طریق گوشی خود باز کنید و با
<span dir="ltr">Agent</span>
خود روی موبایل چت کنید.
</p>

</div>

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway
```

<div dir="rtl" align="right" style="direction: rtl; text-align: right;">

<p>
آدرس
<strong dir="ltr">http://localhost:3000</strong>
را باز کنید و مراحل راه‌اندازی اولیه را دنبال کنید.
</p>

<p>
اگر ترجیح می‌دهید از
<span dir="ltr">CLI</span>
استفاده کنید، دستور
<code dir="ltr">shibaclaw onboard</code>
همان مراحل راه‌اندازی را به‌صورت راهنما از داخل
<span dir="ltr">Terminal</span>
اجرا می‌کند.
</p>

</div>

---


<div dir="rtl" align="right">

<h2>✨ همه‌چیز در یک Agent</h2>

<table width="100%">
<tr>

<td width="33%" valign="top">

<h3>🛡️ امنیت در اولویت</h3>

<p>
Vault رمزنگاری‌شده<br>
بررسی آسیب‌پذیری‌های <span dir="ltr">CVE</span><br>
محافظ <span dir="ltr">Prompt Injection</span><br>
محافظت در برابر <span dir="ltr">SSRF</span>
</p>

</td>

<td width="33%" valign="top">

<h3>🧠 حافظه هوشمند</h3>

<p>
سیستم حافظه سه‌سطحی<br>
یادگیری فعال<br>
فشرده‌سازی خودکار
</p>

</td>

<td width="33%" valign="top">

<h3>🌐 28 Provider</h3>

<p>
<span dir="ltr">SDK</span>های Native<br>
بدون <span dir="ltr">LiteLLM Proxy</span><br>
<span dir="ltr">OpenAI · Anthropic · Gemini · DeepSeek...</span>
</p>

</td>

</tr>

<tr>

<td valign="top">

<h3>📱 Web و موبایل</h3>

<p>
<span dir="ltr">WebUI</span> را روی شبکه محلی (<span dir="ltr">LAN</span>) اجرا کنید.<br>
از طریق گوشی یا تبلت به همان Agent متصل شوید.
</p>

</td>

<td valign="top">

<h3>🖥️ اپلیکیشن دسکتاپ</h3>

<p>
<span dir="ltr">Launcher</span> اختصاصی ویندوز با <span dir="ltr">System Tray</span><br>
ترکیبی عالی در کنار <span dir="ltr">WebUI</span>
</p>

</td>

<td valign="top">

<h3>🔌 آماده برای MCP</h3>

<p>
به هر <span dir="ltr">MCP Server</span> متصل شوید.<br>
<span dir="ltr">Tool</span>ها به‌صورت خودکار ثبت می‌شوند.
</p>

</td>

</tr>

</table>

</div>

<div dir="rtl" align="right">

<h2>🐕 چرا ShibaClaw؟ چون فقط کار می‌کند.</h2>

<blockquote>

<p>
<strong>
از
<span dir="ltr">Agent</span>
هایی که باید همیشه بالای سرشان باشی تا درست کار کنند خسته شدی؟
</strong>
</p>

<p>
ShibaClaw با یک اصل ساده طراحی شده:
<strong>فقط کار می‌کند</strong>
 — امن، قابل اعتماد و بدون دردسرهای همیشگی.
</p>

</blockquote>

</div>

<p>
بیشتر فریم‌ورک‌های AI Agent امنیت را به آخر کار موکول می‌کنند، شما را درگیر ناسازگاری بین Providerها می‌کنند یا مجبور می‌کنند مدام تنظیمات را مدیریت کنید. اما ShibaClaw این رویکرد را کاملاً برعکس کرده است؛ امنیت یک قابلیت اضافه نیست، بلکه <strong>پایه و اساس</strong> کل سیستم است.
</p>

<h3>چه چیزی ShibaClaw را متفاوت می‌کند؟</h3>

<ul>

<li>
<strong>امنیت در هسته سیستم</strong> — بررسی آسیب‌پذیری‌های CVE هنگام نصب، محافظت در برابر Prompt Injection روی تمام خروجی Toolها و محافظت در برابر SSRF و DNS Rebinding.
</li>

<li>
<strong>پشتیبانی Native از Providerها</strong> — پشتیبانی از 28 Provider از طریق SDKهای رسمی آن‌ها، بدون نیاز به Proxy Layer.
</li>

<li>
<strong>راه‌اندازی با یک دستور</strong> — با Docker یا pip نصب کنید، Wizard را دنبال کنید و تقریباً در کمتر از یک دقیقه آماده چت خواهید بود.
</li>

<li>
<strong>قابل اجرا در همه‌جا</strong> — از Terminal، WebUI، Discord، Telegram، WhatsApp، اپلیکیشن دسکتاپ ویندوز و پلتفرم‌های دیگر استفاده کنید.
</li>

</ul>

</div>

---

<div dir="rtl">

<h2>🛡️ امنیت، از همان ابتدا</h2>

<p>
قابلیت‌هایی که معمولاً باید با چندین ابزار جانبی، Proxy یا کدنویسی اضافی پیاده‌سازی شوند، در ShibaClaw از همان ابتدا داخل هسته برنامه وجود دارند و <strong>به‌صورت پیش‌فرض فعال هستند.</strong>
</p>

</div>

<div dir="rtl">

<h3>🛡️ لایه‌های امنیتی هسته</h3>

<table>
<thead>
<tr>
  <td align="right"><strong>لایه</strong></td>
  <td align="right"><strong>توضیحات</strong></td>
</tr>
</thead>

<tbody>

<tr>
<td>🔍 بررسی هنگام نصب</td>
<td>
قبل از اجرای <code>pip</code> و <code>npm</code>، بسته‌ها بررسی می‌شوند و در صورت وجود آسیب‌پذیری‌های بحرانی یا High CVE، نصب متوقف می‌شود.
</td>
</tr>

<tr>
<td>🛡️ محافظت در برابر Prompt Injection و Pre-scan</td>
<td>
تمام خروجی Toolها داخل یک مرز تصادفی از نوع <code>&lt;tool_output_...&gt;</code> قرار می‌گیرند. همچنین محتوای ورودی با Regex بررسی می‌شود و Payloadهای غیرقابل اعتماد به‌صورت <strong>Base64</strong> رمزگذاری می‌شوند.
</td>
</tr>

<tr>
<td>🔒 سخت‌سازی Shell</td>
<td>
بیش از 20 الگوی مسدودسازی، نرمال‌سازی Escapeها (<code>\x..</code> و <code>\u....</code>) و شناسایی URLهای داخلی برای جلوگیری از سوءاستفاده.
</td>
</tr>

<tr>
<td>⚡ موتور Local-First</td>
<td>
Command Emulator داخلی برای دستورهایی مانند <code>ls</code> و <code>cat</code> بدون نیاز به Subprocess و استفاده از <code>tiktoken</code> به‌صورت آفلاین برای محیط‌های Air-Gapped.
</td>
</tr>

<tr>
<td>🌐 محافظت شبکه</td>
<td>
فیلتر کردن حملات SSRF، اعتبارسنجی مجدد Redirectها و جلوگیری از حملات DNS Rebinding.
</td>
</tr>

<tr>
<td>📁 Workspace Sandbox</td>
<td>
تمام File Toolها و File Browser فقط به Workspace تعریف‌شده دسترسی دارند.
</td>
</tr>

<tr>
<td>🔑 کنترل دسترسی</td>
<td>
احراز هویت با Bearer Token، بررسی‌های Constant-Time، Channel Allowlist و امکان فعال کردن Rate Limiting.
</td>
</tr>

<tr>
<td>🧠 معماری توزیع‌شده</td>
<td>
رابط کاربری (حدود 128MB) از Agent Engine (حدود 256MB+) جدا شده تا مصرف حافظه هر Process به حداقل برسد.
</td>
</tr>

</tbody>
</table>

<h3>🛡️ محافظت در برابر Prompt Injection (ایزوله‌سازی Toolها)</h3>

<p>
به‌جای اینکه خروجی خام Toolها مستقیماً به LLM ارسال شود، ShibaClaw هر خروجی را داخل یک مرز XML‌مانند که در هر اجرا به‌صورت تصادفی تولید می‌شود قرار می‌دهد (برای مثال:
<code>&lt;tool_output_a1b2c3d4&gt;</code>).
</p>

<blockquote>

<p>
💡 <strong>قابل استفاده به‌صورت مستقل</strong>
</p>

<p>
این مکانیزم امنیتی (<strong>Randomized Tool Output Wrapping</strong>) به‌صورت یک کتابخانه مستقل و بدون وابستگی با نام
<a href="https://github.com/RikyZ90/Muzzle"><strong>Muzzle</strong></a>
منتشر شده است. با استفاده از Muzzle می‌توانید همین تکنیک را برای محافظت از هر Agent Framework مانند LangChain، LlamaIndex، CrewAI، AutoGen یا هر چرخه سفارشی LLM استفاده کنید.
</p>

</blockquote>

<p>
<strong>چرا این موضوع اهمیت دارد؟</strong>
</p>

<p>
مهاجمان معمولاً تلاش می‌کنند داخل خروجی Toolها (برای مثال محتوای صفحات وب)، Tagها را زودتر ببندند یا دستورهای جعلی System را تزریق کنند. ShibaClaw با استفاده از یک مرز تصادفی که در هر اجرا تولید می‌شود، همیشه می‌تواند دستورهای واقعی سیستم را از محتوای تزریق‌شده تشخیص دهد.
</p>

<p>
علاوه بر این، اگر محتوای Tool تلاش کند همان Tag پایانی را تزریق کند، آن بخش به‌صورت خودکار Sanitize و Escape می‌شود تا Sandbox کاملاً ایمن باقی بماند و همیشه System Prompt اصلی در اولویت باشد.
</p>

</div>

<div dir="rtl">

<h3>🔍 بررسی خودکار Packageها هنگام نصب</h3>

<p>
قبل از اجرای هر دستور <code>pip</code>، <code>npm</code> یا <code>apt</code>، ShibaClaw ابتدا آن را رهگیری کرده و وابستگی‌های آن را بررسی می‌کند. سپس با استفاده از ابزارهایی مانند <code>pip-audit</code> یا <code>npm audit --json</code>، Packageها را قبل از نصب در برابر پایگاه‌های داده CVE اسکن می‌کند.
</p>

<p>
<strong>چرا این قابلیت مهم است؟</strong>
</p>

<p>
این رویکرد امنیت را از همان ابتدای فرآیند توسعه وارد عمل می‌کند. به‌جای مسدود کردن کامل Package Managerها یا تکیه بر اسکن‌های بعد از نصب، ShibaClaw دقیقاً Dependency Tree را <strong>قبل از اجرا</strong> بررسی می‌کند.
</p>

<p>
اگر Packageها دارای آسیب‌پذیری‌های Critical یا High CVE باشند، یا گزینه‌های مشکوکی مانند <code>--allow-unauthenticated</code> در <code>apt</code> شناسایی شوند، فرآیند نصب متوقف خواهد شد. به این ترتیب AI می‌تواند به‌صورت خودکار نرم‌افزارها را Build و نصب کند، بدون اینکه امنیت سیستم میزبان به خطر بیفتد.
</p>

<p>
اطلاعات کامل درباره سیاست امنیتی و نسخه‌های پشتیبانی‌شده را در
<a href="./SECURITY.md"><strong>SECURITY.md</strong></a>
ببینید.
</p>

</div>

---

<div dir="rtl" align="right">

<h2>🖥️ اپلیکیشن دسکتاپ (Windows)</h2>

<p>
ShibaClaw دارای یک
<strong dir="ltr">Windows Desktop Launcher</strong>
کاملاً یکپارچه است که با
<code dir="ltr">pywebview</code>
ساخته شده و تجربه‌ای روان و کاملاً محلی را بدون نیاز به مدیریت پنجره‌های
<code dir="ltr">Terminal</code>
در پس‌زمینه فراهم می‌کند.
</p>

<ul>

<li>
<strong dir="ltr">System Tray Integration</strong> —
با بستن پنجره، ShibaClaw به‌جای خروج، به‌آرامی به
<span dir="ltr">System Tray</span>
منتقل می‌شود. با کلیک راست روی آیکون Shiba می‌توانید دوباره
<span dir="ltr">WebUI</span>
را باز کنید،
<span dir="ltr">Log</span>
های
<span dir="ltr">Workspace</span>
را ببینید، وارد وب‌سایت شوید یا
<span dir="ltr">Engine</span>
را به‌صورت امن متوقف کنید.
</li>

<li>
<strong dir="ltr">Auto-Login</strong> —
هنگام استفاده از
<span dir="ltr">Desktop Launcher</span>
روی سیستم محلی، احراز هویت
<span dir="ltr">WebUI</span>
به‌صورت پیش‌فرض غیرفعال می‌شود تا تجربه استفاده محلی سریع‌تر و روان‌تر باشد.
</li>

<li>
<strong dir="ltr">Embedded WebUI</strong> —
نیازی به باز کردن
<span dir="ltr">Browser</span>
نیست؛
<span dir="ltr">WebUI</span>
مستقیماً داخل یک پنجره
<span dir="ltr">Native</span>
اجرا می‌شود.
</li>

<li>
<strong>Portable و سبک</strong> —
با استفاده از
<span dir="ltr">PyInstaller</span>
به‌صورت یک پوشه مستقل بسته‌بندی شده و بدون نیاز به نصب
<span dir="ltr">Python</span>
روی سیستم، بلافاصله قابل اجرا است.
</li>

</ul>

</div>

<p>
اگر ShibaClaw را با <code>pip</code> نصب کرده‌اید:
</p>

</div>

```bash
shibaclaw desktop
```

<div dir="rtl">

<p>
یا نسخه آماده Windows را مستقیماً از آخرین Release دانلود کنید:
</p>

<blockquote>

<p>
<strong>
<a href="https://github.com/RikyZ90/ShibaClaw/releases/latest/download/ShibaClaw-windows.zip">
⬇ دانلود ShibaClaw.exe (آخرین نسخه)
</a>
</strong>
</p>

<p>
توضیحات کامل نسخه:
<a href="https://github.com/RikyZ90/ShibaClaw/releases/latest">
github.com/RikyZ90/ShibaClaw/releases/latest
</a>
</p>

</blockquote>

</div>

---

<div dir="rtl" align="right" style="direction: rtl; text-align: right;">

<h2>🌐 WebUI</h2>

</div>

<p align="center">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
</p>

<div dir="rtl" align="right" style="direction: rtl; text-align: right;">

<p>
<span dir="ltr">WebUI</span>
به‌صورت داخلی در ShibaClaw وجود دارد؛ نیازی به
<span dir="ltr">Frontend</span>
جداگانه یا نصب
<span dir="ltr">Node.js</span>
نیست.
</p>

<p>
کافی است آن را روی شبکه محلی
<span dir="ltr">(LAN)</span>
در دسترس قرار دهید و همان آدرس را از طریق گوشی یا تبلت خود باز کنید؛ بدون نیاز به هیچ اپلیکیشن اضافی، فقط با یک
<span dir="ltr">Browser</span>.
</p>

<ul dir="rtl" style="direction: rtl; text-align: right; list-style-position: inside;">

<li dir="rtl">
<strong>💬 Chat</strong> — مدیریت چندین
<span dir="ltr">Session</span>
به‌صورت هم‌زمان، نمایش زنده
<span dir="ltr">Tool Call</span>
ها، بلاک‌های
<span dir="ltr">Thinking</span>،
زمان سپری‌شده و امکان تغییر
<span dir="ltr">Model</span>
هر
<span dir="ltr">Session</span>
مستقیماً از
<span dir="ltr">Footer</span>
پنجره
<span dir="ltr">Chat</span>.
</li>

<li dir="rtl">
<strong>📚 Local RAG و Knowledge Base</strong> — با
<span dir="ltr">Drag & Drop</span>
یا
<span dir="ltr">Upload</span>
فایل‌هایی مانند
<span dir="ltr">PDF</span>،
<span dir="ltr">CSV</span>،
<span dir="ltr">HTML</span>
و
<span dir="ltr">TXT</span>
مجموعه‌های محلی بسازید، با
<span dir="ltr">Semantic Search</span>
در آن‌ها جستجو کنید و
<span dir="ltr">Collection</span>
های فعال را به
<span dir="ltr">Session</span>
ها
<span dir="ltr">Pin</span>
کنید.
</li>

<li dir="rtl">
<strong>🏷️ Context Mention (@)</strong> — با استفاده از
<code dir="ltr">@</code>،
<span dir="ltr">Knowledge Base</span>
ها،
<span dir="ltr">MCP Server</span>
ها و
<span dir="ltr">App</span>
های متصل را به‌صورت خودکار پیشنهاد داده و به پیام خود متصل کنید تا تمرکز
<span dir="ltr">Agent</span>
روی همان منابع باشد.
</li>

<li dir="rtl">
<strong>🔎 جستجوی Model بین تمام Providerها</strong> — یک انتخاب‌گر
<span dir="ltr">(Picker)</span>
واحد که
<span dir="ltr">Model</span>
های تمام
<span dir="ltr">Provider</span>
های تنظیم‌شده را نمایش می‌دهد، نام
<span dir="ltr">Provider</span>
را مشخص می‌کند و هنگام تغییر
<span dir="ltr">Model</span>،
<span dir="ltr">Provider</span>
فعال را نیز به‌صورت خودکار تغییر می‌دهد.
</li>

<li dir="rtl">
<strong>🎭 پروفایل‌های Agent</strong> — برای هر
<span dir="ltr">Session</span>
بین شخصیت‌های مختلف مانند
<span dir="ltr">Hacker</span>،
<span dir="ltr">Builder</span>،
<span dir="ltr">Planner</span>
و
<span dir="ltr">Reviewer</span>
جابجا شوید؛ هرکدام با
<span dir="ltr">Avatar</span>
اختصاصی خود.
</li>

<li dir="rtl">
<strong>📁 File Browser</strong> — فایل‌های
<span dir="ltr">Workspace</span>
را مستقیماً داخل
<span dir="ltr">Browser</span>
مشاهده، مرور و ویرایش کنید.
</li>

<li dir="rtl">
<strong>🎙️ Voice</strong> — تبدیل گفتار به متن با
<span dir="ltr">API</span>
های سازگار با
<span dir="ltr">OpenAI</span>
و تبدیل متن به گفتار با قابلیت‌های داخلی
<span dir="ltr">Browser</span>.
</li>

<li dir="rtl">
<strong>⚙️ Settings</strong> — از یک پنل واحد،
<span dir="ltr">Model</span>
پیش‌فرض
<span dir="ltr">Session</span>،
<span dir="ltr">Memory</span>،
<span dir="ltr">Provider</span>
ها،
<span dir="ltr">Tool</span>
ها،
<span dir="ltr">MCP Server</span>
ها،
کانال‌ها،
<span dir="ltr">Skill</span>
ها و
<span dir="ltr">OAuth</span>
را مدیریت کنید.
</li>

<li dir="rtl">
<strong>🚀 Onboard Wizard</strong> — راه‌اندازی اولیه به‌صورت مرحله‌به‌مرحله؛
<span dir="ltr">Provider</span>
را انتخاب کنید،
<span dir="ltr">API Key</span>
را وارد کنید یا
<span dir="ltr">OAuth</span>
را آغاز کنید و سپس
<span dir="ltr">Model</span>
موردنظر خود را انتخاب کنید.
</li>

<li dir="rtl">
<strong>🧠 Context Viewer</strong> —
<span dir="ltr">System Prompt</span>
کامل و جزئیات مصرف
<span dir="ltr">Token</span>
ها را مشاهده کنید.
</li>

<li dir="rtl">
<strong>📡 Gateway Monitor</strong> — وضعیت
<span dir="ltr">Gateway</span>
را بررسی کرده و در صورت نیاز آن را
<span dir="ltr">Restart</span>
کنید.
</li>

<li dir="rtl">
<strong>🔐 OAuth</strong> —
<span dir="ltr">GitHub Copilot</span>،
<span dir="ltr">OpenAI Codex</span>
و
<span dir="ltr">OpenRouter</span>
را مستقیماً از بخش
<span dir="ltr">Settings</span>
پیکربندی کنید.
</li>

<li dir="rtl">
<strong>🛡️ رندر ایمن</strong> —
<span dir="ltr">Markdown</span>
در
<span dir="ltr">Chat</span>
به‌صورت امن
<span dir="ltr">HTML</span>
خام را
<span dir="ltr">Escape</span>
می‌کند و نام فایل‌ها از طریق
<span dir="ltr">DOM</span>
ایمن نمایش داده می‌شوند.
</li>

<li dir="rtl">
<strong>🔄 به‌روزرسانی خودکار</strong> —
<span dir="ltr">GitHub Release</span>
ها بررسی می‌شوند و نسخه‌های جدید از طریق
<span dir="ltr">WebUI</span>
و کانال‌های فعال اطلاع‌رسانی می‌شوند.
</li>

<li dir="rtl">
<strong>🔔 Notification Center (WIP)</strong> —
آیکون اعلان همراه با
<span dir="ltr">Badge</span>
تعداد پیام‌های خوانده‌نشده، دریافت لحظه‌ای اعلان‌ها از طریق
<span dir="ltr">WebSocket</span>
و رفتن مستقیم به
<span dir="ltr">Session</span>
مربوطه.
</li>

<li dir="rtl">
<strong>📱 Responsive</strong> — کاملاً مناسب
<span dir="ltr">Desktop</span>
و
<span dir="ltr">Mobile</span>؛
همان
<span dir="ltr">Agent</span>
را از روی گوشی، تبلت یا لپ‌تاپ در اختیار داشته باشید.
</li>

</ul>

</div>

<div dir="rtl">

<h3>⚡ انتخاب پویا Model</h3>

</div>

<p align="center">
  <img src="assets/model_sel.webp" width="600" alt="Dynamic Model Selector">
</p>

<div dir="rtl">

<p>
برای هر Session می‌توانید Model متفاوتی انتخاب کنید؛ دیگر خبری از یک Model سراسری برای همه گفتگوها نیست و هر مکالمه می‌تواند Model مخصوص خودش را داشته باشد.
</p>

<ul>

<li>
<strong>🔍 جستجو بین تمام Providerها</strong> — همه Modelهای Providerهای تنظیم‌شده (مانند OpenRouter، GitHub Copilot، Anthropic و ...) در یک لیست واحد قابل جستجو هستند.
</li>

<li>
<strong>🧠 مدیریت مستقل هر Session</strong> — هر Session Model انتخاب‌شده خود را به خاطر می‌سپارد. برای مثال می‌توانید هم‌زمان یک Session برنامه‌نویسی با <code>Claude 3.5 Sonnet</code> و یک Session تحقیقاتی با <code>Gemma 4</code> داشته باشید.
</li>

<li>
<strong>⚡ تغییر Model در لحظه</strong> — بدون نیاز به Restart کردن Agent، هر زمان خواستید Model را تغییر دهید؛ Gateway به‌صورت خودکار Endpoint مناسب را براساس Model انتخاب‌شده پیدا می‌کند.
</li>

<li>
<strong>🧠 Model اختصاصی برای Memory</strong> — می‌توانید یک Model و Provider جداگانه فقط برای Memory Consolidation و Proactive Learning مشخص کنید تا استخراج اطلاعات مهم با کیفیت بالا انجام شود، بدون اینکه روی بودجه چت شما تأثیر بگذارد.
</li>

<li>
<strong>⭐ شروع با Model پیش‌فرض</strong> — Sessionهای جدید به‌صورت خودکار با Model پیش‌فرضی که در Settings انتخاب کرده‌اید شروع می‌شوند تا همه‌چیز از همان ابتدا یکپارچه باشد.
</li>

</ul>

<div dir="rtl" align="right">

<h3>🤖 پروفایل‌های Agent</h3>

<p>
شخصیت
<span dir="ltr">Agent</span>
را هر زمان که بخواهید، بدون از دست دادن
<span dir="ltr">Context</span>،
تغییر دهید. هر
<span dir="ltr">Profile</span>
فقط
<code dir="ltr">SOUL.md</code>
(<span dir="ltr">System Prompt</span>)
را جایگزین می‌کند و
<span dir="ltr">Model</span>،
<span dir="ltr">Memory</span>
و
<span dir="ltr">Tool</span>
ها همچنان بین همه
<span dir="ltr">Profile</span>
ها مشترک باقی می‌مانند.
</p>

<p>
<span dir="ltr">Profile</span>
ها برای هر
<span dir="ltr">Session</span>
به‌صورت مستقل هستند؛ بنابراین می‌توانید در یک تب مشغول
<span dir="ltr">Security Audit</span>
باشید و هم‌زمان در تب دیگری معماری پروژه را طراحی کنید.
</p>

<p>
<strong>Profileهای داخلی:</strong><br>
<span dir="ltr">Default · Builder · Planner · Reviewer · Hacker</span>
</p>

<p>
<span dir="ltr">Profile Hacker</span>
شامل بیش از 50 پیشنهاد
<span dir="ltr">Tool</span>،
متدولوژی‌های
<span dir="ltr">OWASP</span>،
<span dir="ltr">MITRE</span>
و
<span dir="ltr">NIST</span>،
امتیازدهی
<span dir="ltr">CVSS</span>
و Avatar اختصاصی
<span dir="ltr">Cyber-Shiba</span>
است.
</p>

<p>
همچنین می‌توانید
<span dir="ltr">Profile</span>
های اختصاصی خودتان را به‌صورت تعاملی بسازید؛
<span dir="ltr">Agent</span>
مرحله‌به‌مرحله شما را راهنمایی می‌کند و در پایان همه تنظیمات را به‌صورت خودکار ذخیره می‌کند.
</p>

</div>

---

<div dir="rtl" align="right" style="direction: rtl; text-align: right;">

<h2>🧠 سیستم حافظه پیشرفته سه‌سطحی</h2>

<p>
حافظه ShibaClaw فقط یک بافر ساده برای پیام‌های
<span dir="ltr">Chat</span>
نیست؛ بلکه یک سیستم ساختاریافته و هوشمند است که برای حفظ تداوم پروژه‌ها و کارهای بلندمدت طراحی شده است.
</p>

<div dir="rtl" align="right" style="direction: rtl; text-align: right;">

<ul dir="rtl" style="direction: rtl; text-align: right; list-style-position: inside;">

<li dir="rtl">
<strong><code dir="ltr">USER.md</code> (هویت و ترجیحات)</strong> —
اطلاعات ماندگار کاربر، سبک گفتگو و زبان ترجیحی را ذخیره می‌کند تا
<span dir="ltr">Agent</span>
بداند
<em>شما چه کسی هستید.</em>
</li>

<li dir="rtl">
<strong><code dir="ltr">MEMORY.md</code> (وضعیت عملیاتی)</strong> —
دانش کاری
<span dir="ltr">Agent</span>؛
شامل اطلاعات محیط، موجودیت‌های تکرارشونده و وضعیت پروژه.
</li>

<li dir="rtl">
<strong><code dir="ltr">HISTORY.md</code> (آرشیو Sessionها)</strong> —
آرشیوی قابل جستجو از تمام
<span dir="ltr">Session</span>
های گذشته همراه با خلاصه‌های زمان‌بندی‌شده و برچسب‌گذاری‌شده.
</li>

</ul>

</div>

<p>
به‌جای اینکه هزاران پیام داخل
<span dir="ltr">System Prompt</span>
انباشته شوند، ShibaClaw از یک چرخه
<strong><span dir="ltr">Proactive Learning</span></strong>
استفاده می‌کند.
هر چند پیام یک‌بار، یک فرآیند
<span dir="ltr">LLM</span>
در پس‌زمینه، بدون ایجاد وقفه در گفتگو، اطلاعات ماندگار جدید را استخراج کرده و فایل‌های
<code dir="ltr">USER.md</code>
و
<code dir="ltr">MEMORY.md</code>
را به‌روزرسانی می‌کند.
</p>

<p>
اگر
<code dir="ltr">MEMORY.md</code>
بیش از حد بزرگ شود، مکانیزم
<strong><span dir="ltr">Auto-Compaction</span></strong>
به‌صورت خودکار اطلاعات را خلاصه و موارد تکراری را حذف می‌کند تا وضعیت‌های جدید در اولویت قرار بگیرند و مصرف
<span dir="ltr">Token</span>
همیشه در محدوده تعیین‌شده باقی بماند.
</p>

<p>
هر زمان
<span dir="ltr">Agent</span>
به اطلاعات قدیمی‌تر نیاز داشته باشد، می‌تواند به‌صورت خودکار فایل
<code dir="ltr">HISTORY.md</code>
را با استفاده از الگوریتم‌های
<strong><span dir="ltr">TF-IDF</span></strong>
و امتیازدهی براساس تازگی
<span dir="ltr">(Recency Scoring)</span>
جستجو کند.
</p>

<p>
این تفکیک بین هویت، حافظه عملیاتی و تاریخچه باعث می‌شود
<span dir="ltr">Agent</span>
همیشه روی وضعیت فعلی پروژه متمرکز بماند، بدون اینکه با محدودیت
<span dir="ltr">Token</span>
روبه‌رو شود یا تمرکز خود را از دست بدهد.
</p>

</div>

---

<div dir="rtl">

<h2>🛠️ قابلیت‌ها</h2>

<h3>🧠 گردش‌کار و استدلال</h3>

<ul>

<li>
<strong>مدیریت Session بر اساس Model</strong> — هر Session، Model انتخابی خودش را ذخیره می‌کند و ShibaClaw هنگام اجرا به‌صورت خودکار Provider مناسب را براساس همان Model انتخاب می‌کند.
</li>

<li>
<strong>واگذاری هوشمند وظایف به پس‌زمینه</strong> — Tool با نام <code>spawn</code> می‌تواند یک وظیفه مشخص را به یک Worker جداگانه واگذار کند و پس از اتمام، نتیجه را به Session اصلی برگرداند.
</li>

<li>
<strong>استدلال پیشرفته</strong> — پشتیبانی از قابلیت Extended Thinking در Anthropic، Reasoning Effort در مدل‌های OpenAI O-Series و زنجیره‌های استدلال DeepSeek-R1.
</li>

</ul>

<h3 dir="rtl">ابزارها 🛠️</h3>

<table>
<thead>
<tr>
  <td align="right"><strong>ابزار</strong></td>
  <td align="right"><strong>توضیحات</strong></td>
</tr>
</thead>

<tbody>

<tr>
<td><code>exec</code></td>
<td>اجرای دستورات Shell همراه با بیش از 20 الگوی امنیتی، نرمال‌سازی Encoding و بررسی CVE قبل از نصب Packageها.</td>
</tr>

<tr>
<td><code>read_file</code> / <code>write_file</code> / <code>edit_file</code></td>
<td>خواندن فایل به‌صورت صفحه‌بندی‌شده، جستجو و جایگزینی هوشمند (Fuzzy) و ساخت خودکار پوشه‌های موردنیاز.</td>
</tr>

<tr>
<td><code>web_search</code></td>
<td>جستجو با Brave، Tavily، SearXNG، Jina یا DuckDuckGo (به‌عنوان حالت جایگزین و بدون نیاز به API Key).</td>
</tr>

<tr>
<td><code>web_fetch</code></td>
<td>دریافت محتوای وب همراه با محافظت در برابر SSRF، حملات DNS Rebinding و اعتبارسنجی Redirectها.</td>
</tr>

<tr>
<td><code>memory_search</code></td>
<td>جستجوی رتبه‌بندی‌شده در تاریخچه Sessionها با استفاده از TF-IDF، امتیازدهی براساس تازگی و میزان اهمیت.</td>
</tr>

<tr>
<td><code>knowledge_search</code></td>
<td>جستجوی Semantic روی Collectionهای فعال Local Knowledge Base با استفاده از FAISS Vector Store.</td>
</tr>

<tr>
<td><code>message</code></td>
<td>ارسال پیام بین کانال های مختلف همراه با پشتیبانی از فایل‌ها و Media.</td>
</tr>

<tr>
<td><code>automation</code></td>
<td>مدیریت و زمان‌بندی Jobهای پس‌زمینه با Cron، بازه‌های زمانی، تاریخ ISO و پشتیبانی از Timezone.</td>
</tr>

<tr>
<td><code>spawn</code></td>
<td>ایجاد Worker مستقل برای انجام یک وظیفه مشخص و ارسال نتیجه به Session اصلی پس از پایان کار.</td>
</tr>

<tr>
<td>MCP</td>
<td>اتصال به هر MCP Server (از طریق stdio، SSE یا Streamable HTTP). تمام Toolها به‌صورت خودکار با قالب <code>mcp_&lt;server&gt;_&lt;tool&gt;</code> ثبت می‌شوند.</td>
</tr>

</tbody>
</table>

<div dir="rtl" align="right">

<h3>📡 کانال‌ها (Channels)</h3>

<p dir="ltr" align="center">
Telegram · Discord · Slack · WhatsApp · Matrix · Email · DingTalk · Feishu · QQ · WeCom · MoChat
</p>

<p>
تمام کانال‌ها از طریق یک Message Bus مشترک مدیریت می‌شوند. اتصال WhatsApp نیز با استفاده از Bridge مبتنی بر Node.js (Baileys) و اسکن QR Code انجام می‌شود.
</p>

</div>

<div dir="rtl" align="right">

<h3>🎯 Skillها</h3>

<p>
ShibaClaw به‌صورت پیش‌فرض دارای 8 Skill داخلی است؛ از جمله
<span dir="ltr">GitHub</span>،
<span dir="ltr">Weather</span>،
<span dir="ltr">Summarize</span>،
<span dir="ltr">tmux</span>،
<span dir="ltr">Automation</span>،
<span dir="ltr">Memory Guide</span>،
<span dir="ltr">Skill Creator</span>
و
<span dir="ltr">ClawHub Browser</span>.
</p>

<p>
Skillها فایل‌های
<code dir="ltr">Markdown</code>
هستند که از
<code dir="ltr">YAML Frontmatter</code>
و در صورت نیاز
<code dir="ltr">Script</code>
های کمکی پشتیبانی می‌کنند. می‌توانید Skillهای اختصاصی خود را بسازید یا آن‌ها را از
<a href="https://clawhub.ai/"><strong>ClawHub</strong></a>
نصب کنید.
</p>

<p>
همچنین می‌توانید Skillهای پرکاربرد را
<code dir="ltr">Pin</code>
کنید تا در ابتدای هر گفتگو به‌صورت خودکار بارگذاری شوند.
</p>

</div>

<h3 dir="rtl">🤖 اتوماسیون</h3>

<ul>

<li>
<strong>موتور اتوماسیون</strong> — مدیریت Jobهای زمان‌بندی‌شده و وظایف پس‌زمینه با پشتیبانی از Timezone، رابط کاربری یکپارچه و ذخیره تنظیمات در فایل <code>automation.json</code>. از زمان‌بندی‌های <code>every</code>، <code>cron</code> و <code>at</code> پشتیبانی می‌کند و Jobهای ازدست‌رفته را هنگام راه‌اندازی به‌صورت هوشمند مدیریت می‌کند تا از ایجاد Execution Storm جلوگیری شود.
</li>

<li>
<strong>ادغام با <code>TASK.md</code></strong> — تمام وظایف پس‌زمینه از طریق فایل <code>TASK.md</code> مدیریت می‌شوند. اگر هیچ Task فعالی وجود نداشته باشد، Engine بدون استفاده از LLM از آن مرحله عبور می‌کند تا مصرف Token کاهش پیدا کند.
</li>

</ul>

<p>
اگر از نسخه‌های قدیمی‌تر ارتقا می‌دهید، فایل <code>HEARTBEAT.md</code> حذف شده است. تمام Taskها و Scheduleهای خود را به <code>TASK.md</code> و رابط کاربری جدید Automation منتقل کنید.
</p>

<h3 dir="rtl">🔌 Plugin‌ها و TTS (Text-to-Speech)</h3>

<ul>

<li>
<strong>سیستم Plugin قابل نصب</strong> — قابلیت‌های Agent را با Pluginهای Python که به‌صورت پویا قابل نصب هستند گسترش دهید (مانند تبدیل متن به گفتار یا Integrationهای اختصاصی). همه Pluginها مستقیماً از طریق Settings در WebUI مدیریت می‌شوند. برای ساخت Plugin اختصاصی، فایل
<a href="./docs/PLUGINS_DEVELOPMENT_GUIDE.md"><code>docs/PLUGINS_DEVELOPMENT_GUIDE.md</code></a>
را ببینید.
</li>

<li>
<strong>تبدیل متن به گفتار آفلاین و رایگان (Supertonic)</strong> — Plugin <strong>Supertonic TTS</strong> با استفاده از ONNX، تبدیل متن به گفتار را به‌صورت کاملاً آفلاین و بدون هزینه فراهم می‌کند. این Plugin از 31 زبان، صداهای سفارشی (<code>F1</code> و <code>M1</code>) و تنظیم سرعت گفتار پشتیبانی می‌کند.
</li>

<li>
<strong>پخش‌کننده صوت داخل Browser</strong> — پیام‌های صوتی Agent مستقیماً داخل رابط Chat با یک Audio Player اختصاصی و طراحی Glassmorphism پخش می‌شوند که از Timeline قابل جابه‌جایی و نمایش مدت زمان نیز پشتیبانی می‌کند.
</li>

</ul>

</div>

---

<div dir="rtl" align="right">

<h2>🔌 اکوسیستم MCP</h2>

<p>
ShibaClaw به‌طور کامل از
<strong dir="ltr">Model Context Protocol (MCP)</strong>
پشتیبانی می‌کند و
<strong dir="ltr">Agent</strong>
شما را از یک ابزار مستقل به یک مرکز هوشمند و قابل توسعه تبدیل می‌کند.
</p>

<p>
به‌جای اینکه فقط به
<strong dir="ltr">Skill</strong>
های داخلی محدود باشید، ShibaClaw می‌تواند به هر
<strong dir="ltr">MCP Server</strong>
سازگار متصل شود و بدون تغییر حتی یک خط از کد اصلی، دسترسی
<strong dir="ltr">Agent</strong>
را به مجموعه بزرگی از ابزارها و منابع داده خارجی فراهم کند.
</p>

</div>
<h3>چرا این قابلیت مهم است؟</h3>

<ul>

<li>
<strong>⚡ توسعه‌پذیری فوری</strong> — کافی است MCP Serverهای ساخته‌شده توسط جامعه توسعه‌دهندگان را اضافه کنید تا به سرویس‌هایی مانند Google Drive، Slack، GitHub، PostgreSQL و بسیاری سرویس‌های دیگر متصل شوید.
</li>

<li>
<strong>🛠️ استاندارد واحد برای Toolها</strong> — با استفاده از یک پروتکل استاندارد برای ارتباط بین AI و Toolها، سازگاری و پایداری سیستم حفظ می‌شود.
</li>

<li>
<strong>🏗️ معماری ماژولار</strong> — هسته Agent سبک باقی می‌ماند و قابلیت‌های آن از طریق شبکه‌ای از MCP Serverها به‌راحتی گسترش پیدا می‌کند.
</li>

</ul>

<p>
برای شروع، کافی است MCP Serverهای خود را مستقیماً از بخش <strong>Settings</strong> پیکربندی کنید.
</p>

<h3 dir= "rtl">🌐 Appها (ادغام با Klavis)</h3>

<p>
برای اینکه اتصال سرویس‌های محبوب SaaS مانند Gmail، Google Drive، Google Docs، Slack، GitHub، Outlook و سایر سرویس‌ها تا حد ممکن ساده باشد، ShibaClaw با <strong>Klavis</strong> (<code>klavis.ai</code>) یکپارچه شده است.
</p>

<p>
به‌جای اینکه مجبور باشید برای هر سرویس به‌صورت جداگانه Developer Credential بسازید، OAuth Consent Screen تنظیم کنید و Redirect URLها را در Google Cloud یا Microsoft Azure پیکربندی کنید، ShibaClaw همه این موارد را از طریق بخش <strong>Connected Apps</strong> مدیریت می‌کند.
</p>

<ul>

<li>
<strong>🔑 یک API Key</strong> — فقط کافی است یک API Key از
<a href="https://klavis.ai"><strong>klavis.ai</strong></a>
دریافت کنید و آن را در تنظیمات Backend مربوط به ShibaClaw ذخیره کنید.
</li>

<li>
<strong>⚡ اتصال با یک کلیک</strong> — Gmail، Slack و سایر سرویس‌ها را تنها با یک کلیک و از طریق OAuth امن که توسط Klavis مدیریت می‌شود، متصل یا قطع کنید.
</li>

<li>
<strong>🤖 ساخت خودکار MCP Server</strong> — پس از اتصال هر App، ShibaClaw به‌صورت خودکار MCP Server مناسب را با Toolهای استاندارد ایجاد و آن‌ها را بدون نیاز به تنظیمات اضافی در Session فعال Agent ثبت می‌کند.
</li>

</ul>

</div>

---

<div dir="rtl">

<h2 dir="rtl">🌐 Providerهای پشتیبانی‌شده</h2>

<p>
ShibaClaw از SDKهای رسمی Providerها استفاده می‌کند (بدون LiteLLM Proxy) و Provider فعال را براساس Model انتخاب‌شده یا شناسه استاندارد Model که شامل پیشوند Provider است، به‌صورت خودکار تشخیص می‌دهد.
</p>

<p>
در WebUI، تمام Modelهای Providerهای پیکربندی‌شده در یک لیست واحد و قابل جستجو نمایش داده می‌شوند، درحالی‌که هر Session همچنان Model اختصاصی خودش را حفظ می‌کند.
</p>

<div dir="rtl" align="right">

<h3>🔑 API Key</h3>

<table dir="rtl" align="right">
<thead>
<tr>
<th>Provider</th>
<th>env متغیر</th>
</tr>
</thead>

<tbody>
<tr>
<td dir="ltr">OpenAI</td>
<td><code dir="ltr">OPENAI_API_KEY</code></td>
</tr>

<tr>
<td dir="ltr">Anthropic</td>
<td><code dir="ltr">ANTHROPIC_API_KEY</code></td>
</tr>

<tr>
<td dir="ltr">DeepSeek</td>
<td><code dir="ltr">DEEPSEEK_API_KEY</code></td>
</tr>

<tr>
<td dir="ltr">Google Gemini</td>
<td><code dir="ltr">GEMINI_API_KEY</code> ¹</td>
</tr>

<tr>
<td dir="ltr">Groq</td>
<td><code dir="ltr">GROQ_API_KEY</code></td>
</tr>

<tr>
<td dir="ltr">Moonshot</td>
<td><code dir="ltr">MOONSHOT_API_KEY</code></td>
</tr>

<tr>
<td dir="ltr">MiniMax</td>
<td><code dir="ltr">MINIMAX_API_KEY</code></td>
</tr>

<tr>
<td dir="ltr">Zhipu AI</td>
<td><code dir="ltr">ZAI_API_KEY</code></td>
</tr>

<tr>
<td dir="ltr">DashScope</td>
<td><code dir="ltr">DASHSCOPE_API_KEY</code></td>
</tr>

</tbody>
</table>

</div>

<div dir="rtl">

<p>
¹ کافی است <code>GEMINI_API_KEY</code> را به‌عنوان env متغیر تنظیم کنید؛ نیازی به ذخیره کردن API Key نیست، زیرا Endpoint سازگار با OpenAI از قبل پیکربندی شده است.
</p>

<div dir="rtl" align="right">

<h3>🌐 Gateway / Proxy</h3>

<p dir="ltr" align="center">
OpenRouter · AiHubMix · SiliconFlow · VolcEngine · BytePlus
</p>

<p>
همه این Gatewayها به‌صورت خودکار از روی پیشوند API Key یا مقدار
<code dir="ltr">api_base</code>
شناسایی می‌شوند.
</p>

<h3>💻 Local</h3>

<p>
Ollama (<code dir="ltr">http://localhost:11434</code>) · LM Studio · llama.cpp · vLLM · هر Endpoint سازگار با OpenAI (<code dir="ltr">http://localhost:1234/v1</code>)
</p>

<blockquote>

<p>
<strong>نکته برای کاربران Docker:</strong>
</p>

<p>
اگر ShibaClaw را با Docker Compose اجرا می‌کنید، آدرس
<code dir="ltr">localhost</code>
به داخل Container اشاره می‌کند، نه سیستم اصلی شما.
</p>

<p>
برای اتصال به سرویس‌هایی مانند LM Studio یا Ollama که روی سیستم میزبان اجرا می‌شوند، از این آدرس‌ها استفاده کنید:
</p>

<p>
<code dir="ltr">http://host.docker.internal:1234/v1</code><br>
یا برای Ollama:<br>
<code dir="ltr">http://host.docker.internal:11434</code>
</p>

<p>
در Linux به‌صورت Native نیز می‌توانید از:
<br>
<code dir="ltr">http://172.17.0.1:port</code>
استفاده کنید.
</p>

</blockquote>

</div>

<h3 dir="rtl">🔐 OAuth</h3>

</div>

| Provider       | روش احراز هویت                                              | راه‌اندازی                                                  |
| -------------- | ----------------------------------------------------------- | ----------------------------------------------------------- |
| OpenRouter     | PKCE Browser Flow، ذخیره خودکار API Key در تنظیمات Provider | WebUI Settings                                              |
| GitHub Copilot | Device Flow همراه با تمدید خودکار Token                     | `shibaclaw provider login github-copilot` یا WebUI Settings |
| OpenAI Codex   | PKCE Browser Flow                                           | `shibaclaw provider login openai-codex` یا WebUI Settings   |

<div dir="rtl">

<p>
برای OpenRouter، آدرس Callback به‌صورت پیش‌فرض از همان URL و Port فعلی WebUI استفاده می‌کند؛ بنابراین <code>http://localhost:3000</code> فقط مخصوص OAuth نیست.
</p>

<p>
اگر WebUI را پشت Reverse Proxy قرار داده‌اید یا می‌خواهید Callback از یک دامنه عمومی دیگر استفاده کند، قبل از اجرای Server این env متغیر را تنظیم کنید:
</p>
</div>

<pre><code>SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host</code></pre>

<div dir="rtl">

<div dir="rtl" align="right">

<h3>💡 پیشنهاد برای استفاده از Modelهای رایگان و Premium</h3>

<p>
ShibaClaw حتی بدون استفاده از APIهای گران‌قیمت هم عملکرد فوق‌العاده‌ای دارد:
</p>

<ul>

<li>
<strong>🆓 Modelهای رایگان و Open</strong> — پیشنهاد می‌کنیم از <strong>OpenRouter</strong> استفاده کنید تا به Modelهای رایگان و قدرتمندی مانند
<code dir="ltr">nvidia/nemotron-3-super-120b-a12b:free</code>
و
<code dir="ltr">gemma-4-31b-it:free</code>
دسترسی داشته باشید.
</li>

<li>
<strong>🚀 Modelهای Premium بدون محدودیت</strong> — اگر از OAuth مربوط به <strong>GitHub Copilot</strong> استفاده کنید، به Modelهای Premium مانند
<code dir="ltr">raptor</code>
(<code dir="ltr">oswe-vscode-prime</code>)
بدون پرداخت هزینه اضافی دسترسی خواهید داشت و عملاً درخواست‌های نامحدود خواهید داشت.
</li>

</ul>

</div>

---

<div dir="rtl">

<h2>📊 مقایسه ShibaClaw (با تمرکز بر امنیت)</h2>

<blockquote>

<p>
این جدول فقط یک مقایسه تقریبی با تمرکز بر قابلیت‌های امنیتی است و بر اساس مستندات عمومی پروژه‌ها تا <strong>May 2026</strong> تهیه شده است.
</p>

<p>
علامت <strong>❓</strong> به معنی «مستند نشده یا بررسی نشده» است، <strong>نه اینکه آن قابلیت وجود ندارد.</strong>
</p>

</blockquote>

</div>

| قابلیت امنیتی                                    | ShibaClaw | OpenClaw | Hermes Agent | Nanobot | ZeroClaw |
| ------------------------------------------------ | :-------: | :------: | :----------: | :-----: | :------: |
| Vault رمزنگاری‌شده (AES Fernet)                  |    ✅     |    ❌    |      ❌      |   ❌    |    ❌    |
| بررسی CVE هنگام نصب (`pip`، `npm`، `apt`)        |    ✅     |    ❌    |      ❌      |   ❌    |    ❌    |
| محافظت از Prompt Injection روی تمام خروجی Toolها |    ✅     |    ❌    |      ❌      |   ❌    |    ❌    |
| محافظت داخلی در برابر SSRF و DNS Rebinding       |    ✅     |    ❌    |      ❌      |   ❌    |    ❌    |

<div dir="rtl">

<p>
هدف ShibaClaw این است که این لایه‌های امنیتی را به‌صورت پیش‌فرض در هسته سیستم ارائه دهد تا برای اجرای یک Agent امن، نیازی به ابزارهای جانبی یا Proxyهای مختلف نداشته باشید.
</p>

</div>

---

<div dir="rtl">

<h2>🏗️ معماری</h2>

</div>

<p align="center">
  <img src="assets/arch.png" width="800" alt="ShibaClaw Architecture">
</p>

<div dir="rtl">

<h3 dir="rtl">🐳 Docker Compose</h3>

</div>

| سرویس               | وظیفه                                                   | Port پیش‌فرض                  |
| ------------------- | ------------------------------------------------------- | ----------------------------- |
| `shibaclaw-gateway` | هسته Agent، Message Bus و کانال ها                      | `19999` (HTTP) · `19998` (WS) |
| `shibaclaw-web`     | WebUI (Starlette + Native WebSocket) و سرویس Automation | `3000`                        |

<div dir="rtl">

<p>
هر دو سرویس از Volume مشترک
<code>~/.shibaclaw/</code>
استفاده می‌کنند که شامل Configها، Workspace، Memory، Automationها و Media Cache است.
</p>

<h3>🖥️ حالت Single-Process</h3>

<p>
دستور <code>shibaclaw web</code>، Agent، WebUI و Automationها را همگی در یک Process اجرا می‌کند و نیازی به Gateway جداگانه نیست.
</p>

<h3 dir="rtl">⚙️ Stack</h3>

</div>

| لایه           | فناوری                                                      |
| -------------- | ----------------------------------------------------------- |
| Server         | Uvicorn → Starlette (ASGI)                                  |
| ارتباط لحظه‌ای | Native WebSocket (`/ws` در WebUI و Port `19998` در Gateway) |
| Frontend       | Vanilla JS · Marked.js · Highlight.js                       |
| Sessionها      | فایل‌های JSONL به‌صورت Append-only برای هر Session          |

<div dir="rtl">

<h3>💾 مصرف منابع</h3>

</div>

| بخش     | حالت Idle | بیشترین مصرف |
| ------- | --------- | ------------ |
| Gateway | ~120 MB   | ~350 MB      |
| WebUI   | ~120 MB   | ~350 MB      |

<div dir="rtl">

<p>
در Docker Compose برای هر Container محدودیت 512 MB و Reservation برابر با 256 MB در نظر گرفته شده است. همچنین خروجی Toolها به‌صورت Stream و با Buffer محدود ارسال می‌شوند تا دستورهای طولانی مانند <code>apt</code> یا <code>npm install</code> باعث افزایش بیش‌ازحد مصرف حافظه نشوند.
</p>

</div>

---

<div dir="rtl">

<h2>🔧 مرجع CLI</h2>

</div>

```bash
shibaclaw web               # اجرای WebUI (Agent + Automationها در یک Process)
shibaclaw gateway           # اجرای فقط Gateway (برای Docker)
shibaclaw onboard           # Wizard راه‌اندازی اولیه در CLI
shibaclaw agent -m "Hello"  # ارسال یک پیام از طریق Terminal
shibaclaw agent             # حالت تعاملی (REPL) همراه با History
shibaclaw status            # بررسی Providerها، Workspace و وضعیت OAuth
shibaclaw print-token       # نمایش Token مربوط به WebUI
shibaclaw channels status   # نمایش کانال های فعال
shibaclaw provider login <p># ورود OAuth (github-copilot، openai-codex)
shibaclaw desktop           # اجرای اپلیکیشن دسکتاپ ویندوز
```

---

<div dir="rtl">

<h2>🐛 عیب‌یابی</h2>

</div>

| مشکل                 | راه‌حل پیشنهادی                                                               |
| -------------------- | ----------------------------------------------------------------------------- |
| بررسی کلی وضعیت      | `shibaclaw status`                                                            |
| Logهای Container     | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web`                 |
| اتصال برقرار نمی‌شود | Token را با `shibaclaw print-token` بررسی کنید و از باز بودن Port مطمئن شوید. |
| خطاهای Provider      | با `shibaclaw status` وضعیت API Key و OAuth را بررسی کنید.                    |
| سیاست‌های امنیتی     | [`SECURITY.md`](./SECURITY.md)                                                |

---

<div dir="rtl" align="right" style="direction: rtl; text-align: right;">

<h2>🤝 مشارکت</h2>

<p>
برای مشارکت در توسعه پروژه، فایل
<a href="./CONTRIBUTING.md"><code dir="ltr">CONTRIBUTING.md</code></a>
را مطالعه کنید. از
<span dir="ltr">Pull Request</span>
های شما استقبال می‌شود.
</p>

<p>
<span dir="ltr">Plugin</span>
ها (چه برای کانال‌ها و چه موتورهای
<span dir="ltr">TTS</span>)
از طریق
<span dir="ltr">Python Entry Point</span>
ها قابل توسعه هستند. برای ساخت
<span dir="ltr">Plugin</span>
اختصاصی، فایل
<a href="./docs/PLUGINS_DEVELOPMENT_GUIDE.md"><code dir="ltr">PLUGINS_DEVELOPMENT_GUIDE.md</code></a>
را ببینید.
</p>

<p>
راهنمای ساخت
<span dir="ltr">Skill</span>
نیز در فایل
<a href="./docs/CHANNEL_PLUGIN_GUIDE.md"><code dir="ltr">CHANNEL_PLUGIN_GUIDE.md</code></a>
و
<span dir="ltr">Skill</span>
داخلی
<code dir="ltr">skill-creator</code>
قرار دارد.
</p>

<p>
اگر قصد توسعه
<span dir="ltr">Gateway</span>
را دارید، مستندات پروتکل
<span dir="ltr">WebSocket</span>
روی
<span dir="ltr">Port</span>
<code dir="ltr">19998</code>
در فایل
<a href="./docs/GATEWAY_PROTOCOL.md"><code dir="ltr">GATEWAY_PROTOCOL.md</code></a>
قرار دارد.
</p>

</div>

---

<div dir="rtl">

<h2>🌟 به خانواده ShibaClaw بپیوندید</h2>

<p>
ShibaClaw توسط یک توسعه‌دهنده ساخته شده، با کمک جامعه متن‌باز نگهداری می‌شود و هر روز در حال رشد است.
</p>

<p>
اگر این پروژه باعث صرفه‌جویی در وقتتان شده، امنیت Workflow شما را بیشتر کرده یا حتی فقط لبخندی روی صورتتان آورده است، لطفاً به آن یک <strong>⭐ Star</strong> بدهید.
</p>

<blockquote>

<p>
"همان AI Agentی که فقط کار می‌کند؛ بدون دردسرهای همیشگی." 🐕
</p>

</blockquote>

</div>

<p align="center">
  ⭐ <a href="https://github.com/RikyZ90/ShibaClaw">به پروژه Star بدهید</a>
  &nbsp;·&nbsp;
  ☕ <a href="https://buymeacoffee.com/rikyz90f">از پروژه حمایت کنید</a>
  &nbsp;·&nbsp;
  🐛 <a href="https://github.com/RikyZ90/ShibaClaw/issues">ثبت Issue</a>
  &nbsp;·&nbsp;
  🔧 <a href="https://github.com/RikyZ90/ShibaClaw/pulls">Pull Request ارسال</a>
</p>
