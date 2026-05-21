from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter()


_WIDGET_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Chat</title>
<style>
  :root { color-scheme: light; }
  html, body { margin: 0; padding: 0; height: 100%; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background: #fff; color: #111; }
  .vx { display: flex; flex-direction: column; height: 100vh; }
  .vx-header { padding: 14px 18px; border-bottom: 1px solid #eee; font-weight: 600; font-size: 14px; background: linear-gradient(90deg,#6d28d9,#2563eb); color: #fff; }
  .vx-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 8px; background: #fafafa; }
  .vx-msg { max-width: 80%; padding: 8px 12px; border-radius: 14px; font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
  .vx-msg.user { align-self: flex-end; background: linear-gradient(135deg,#7c3aed,#2563eb); color: #fff; border-bottom-right-radius: 4px; }
  .vx-msg.bot { align-self: flex-start; background: #fff; color: #111; border: 1px solid #eee; border-bottom-left-radius: 4px; }
  .vx-msg.bot.pending { color: #999; font-style: italic; }
  .vx-input { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #eee; background: #fff; }
  .vx-input input { flex: 1; padding: 9px 14px; border: 1px solid #ddd; border-radius: 999px; font-size: 14px; outline: none; }
  .vx-input input:focus { border-color: #7c3aed; }
  .vx-input button { background: linear-gradient(135deg,#7c3aed,#2563eb); color: #fff; border: none; border-radius: 999px; padding: 9px 16px; font-size: 14px; cursor: pointer; }
  .vx-input button:disabled { opacity: .4; cursor: not-allowed; }
  .vx-error { padding: 14px; color: #b91c1c; font-size: 13px; }
</style>
</head>
<body>
<div class="vx">
  <div class="vx-header" id="vx-header">Chat</div>
  <div class="vx-messages" id="vx-messages"></div>
  <div class="vx-input">
    <input id="vx-text" type="text" placeholder="Type your message..." autocomplete="off" />
    <button id="vx-send">Send</button>
  </div>
</div>
<script>
(function () {
  var params = new URLSearchParams(location.search);
  var key = params.get('key') || '';
  var title = params.get('title') || 'Chat';
  document.getElementById('vx-header').textContent = title;
  var messagesEl = document.getElementById('vx-messages');
  var inputEl = document.getElementById('vx-text');
  var sendBtn = document.getElementById('vx-send');
  var history = [];
  var busy = false;

  if (!key) {
    messagesEl.innerHTML = '<div class="vx-error">Missing widget key.</div>';
    inputEl.disabled = true; sendBtn.disabled = true;
    return;
  }

  function addMsg(role, content, pending) {
    var d = document.createElement('div');
    d.className = 'vx-msg ' + (role === 'user' ? 'user' : 'bot') + (pending ? ' pending' : '');
    d.textContent = content;
    messagesEl.appendChild(d);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return d;
  }

  async function send() {
    var text = inputEl.value.trim();
    if (!text || busy) return;
    busy = true; sendBtn.disabled = true; inputEl.disabled = true;
    inputEl.value = '';
    history.push({ role: 'user', content: text });
    addMsg('user', text, false);
    var botEl = addMsg('bot', 'Thinking…', true);
    var full = '';
    try {
      var res = await fetch('/v1/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
        body: JSON.stringify({ messages: history })
      });
      if (!res.ok || !res.body) throw new Error('HTTP ' + res.status);
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';
      var eventType = 'message';
      while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        var lines = buffer.split('\\n');
        buffer = lines.pop();
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          if (line.indexOf('event: ') === 0) { eventType = line.slice(7).trim(); continue; }
          if (line.indexOf('data: ') !== 0) continue;
          var data = line.slice(6);
          if (eventType === 'sources') { eventType = 'message'; continue; }
          if (data === '[DONE]') continue;
          if (botEl.classList.contains('pending')) { botEl.classList.remove('pending'); botEl.textContent = ''; }
          full += data;
          botEl.textContent = full;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        }
      }
      if (full) history.push({ role: 'assistant', content: full });
      else { botEl.classList.remove('pending'); botEl.textContent = '(no response)'; }
    } catch (e) {
      botEl.classList.remove('pending');
      botEl.textContent = 'Sorry, something went wrong.';
    } finally {
      busy = false; sendBtn.disabled = false; inputEl.disabled = false; inputEl.focus();
    }
  }

  sendBtn.addEventListener('click', send);
  inputEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') send(); });
  inputEl.focus();
})();
</script>
</body>
</html>
"""


_EMBED_JS = """(function () {
  var script = document.currentScript;
  if (!script) return;
  var key = script.getAttribute('data-key');
  var title = script.getAttribute('data-title') || 'Chat';
  if (!key) { console.error('[voxen] missing data-key on script tag'); return; }

  var base = new URL(script.src);
  var widgetUrl = base.origin + '/widget?key=' + encodeURIComponent(key) + '&title=' + encodeURIComponent(title);

  var btn = document.createElement('button');
  btn.setAttribute('aria-label', 'Open chat');
  btn.style.cssText = 'position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;border:none;background:linear-gradient(135deg,#7c3aed,#2563eb);color:#fff;font-size:22px;cursor:pointer;box-shadow:0 8px 24px rgba(79,70,229,.35);z-index:2147483646;';
  btn.textContent = '\\u{1F4AC}';

  var frame = document.createElement('iframe');
  frame.src = widgetUrl;
  frame.title = title;
  frame.style.cssText = 'position:fixed;right:20px;bottom:88px;width:380px;height:560px;max-width:calc(100vw - 40px);max-height:calc(100vh - 108px);border:none;border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.25);z-index:2147483647;display:none;background:#fff;';

  var open = false;
  function toggle() {
    open = !open;
    frame.style.display = open ? 'block' : 'none';
    btn.textContent = open ? '\\u2715' : '\\u{1F4AC}';
  }
  btn.addEventListener('click', toggle);

  function mount() {
    document.body.appendChild(frame);
    document.body.appendChild(btn);
  }
  if (document.body) mount();
  else document.addEventListener('DOMContentLoaded', mount);
})();
"""


@router.get("/widget", response_class=HTMLResponse)
async def widget_page() -> HTMLResponse:
    return HTMLResponse(_WIDGET_HTML)


@router.get("/widget/embed.js")
async def widget_embed_js() -> Response:
    return Response(_EMBED_JS, media_type="application/javascript")
