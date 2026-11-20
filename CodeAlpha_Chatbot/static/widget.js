/*!
 * FoodieBot chat widget — embed on any website with one line:
 *   <script src="https://YOUR-HOST/static/widget.js" data-title="FoodieBot" defer></script>
 * The API host is taken from the script's own URL, so it works cross-site.
 */
(function () {
  "use strict";
  var script = document.currentScript;
  var API = (script && script.dataset.api) || new URL(script.src).origin;
  var TITLE = (script && script.dataset.title) || "FoodieBot";
  var SUBTITLE = (script && script.dataset.subtitle) || "Your AI kitchen assistant";
  var ACCENT = (script && script.dataset.accent) || "#e8590c";

  var sessionId;
  try {
    sessionId = localStorage.getItem("foodie_session");
    if (!sessionId) {
      sessionId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).slice(0, 36);
      localStorage.setItem("foodie_session", sessionId);
    }
  } catch (e) { sessionId = String(Date.now()); }

  var css = "" +
    ".fb-root{--fb-accent:" + ACCENT + ";position:fixed;right:20px;bottom:20px;z-index:2147483000;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;font-size:15px;line-height:1.45}" +
    ".fb-launcher{width:60px;height:60px;border-radius:50%;border:0;background:var(--fb-accent);color:#fff;cursor:pointer;box-shadow:0 8px 24px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center;transition:transform .2s}" +
    ".fb-launcher:hover{transform:scale(1.07)}.fb-launcher svg{width:28px;height:28px}" +
    ".fb-badge{position:absolute;top:-2px;right:-2px;width:14px;height:14px;border-radius:50%;background:#ef4444;border:2px solid #fff}" +
    ".fb-panel{position:absolute;right:0;bottom:76px;width:390px;max-width:calc(100vw - 32px);height:600px;max-height:calc(100vh - 110px);background:#fff;border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.22);display:flex;flex-direction:column;overflow:hidden;opacity:0;transform:translateY(12px) scale(.98);pointer-events:none;transition:opacity .2s,transform .2s}" +
    ".fb-open .fb-panel{opacity:1;transform:none;pointer-events:auto}" +
    ".fb-head{background:var(--fb-accent);color:#fff;padding:14px 16px;display:flex;align-items:center;gap:12px}" +
    ".fb-avatar{width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:20px}" +
    ".fb-head b{display:block;font-size:16px}.fb-head small{opacity:.85;font-size:12px}" +
    ".fb-close{margin-left:auto;background:none;border:0;color:#fff;font-size:24px;cursor:pointer;line-height:1;padding:4px}" +
    ".fb-body{flex:1;overflow-y:auto;padding:16px;background:#f6f7fb;display:flex;flex-direction:column;gap:10px}" +
    ".fb-msg{max-width:88%;padding:10px 13px;border-radius:14px;white-space:pre-wrap;word-wrap:break-word;animation:fb-in .18s ease-out;color:#111827}" +
    ".fb-bot{align-self:flex-start;background:#fff;border:1px solid #e5e7eb;border-bottom-left-radius:4px}" +
    ".fb-user{align-self:flex-end;background:var(--fb-accent);color:#fff;border-bottom-right-radius:4px}" +
    ".fb-meta{align-self:flex-start;display:flex;gap:6px;margin-top:-4px;font-size:12px;color:#6b7280}" +
    ".fb-meta button{background:none;border:1px solid #e5e7eb;border-radius:12px;padding:1px 8px;cursor:pointer;font-size:13px}" +
    ".fb-meta button:hover{background:#fff4e6}.fb-meta .on{background:#ffe8cc;border-color:var(--fb-accent)}" +
    ".fb-chips{display:flex;flex-wrap:wrap;gap:6px;align-self:flex-start}" +
    ".fb-chip{border:1px solid var(--fb-accent);color:var(--fb-accent);background:#fff;border-radius:16px;padding:5px 11px;font-size:13px;cursor:pointer}" +
    ".fb-chip:hover{background:var(--fb-accent);color:#fff}" +
    ".fb-typing{align-self:flex-start;background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:12px 14px;display:flex;gap:4px}" +
    ".fb-typing i{width:7px;height:7px;border-radius:50%;background:#9ca3af;animation:fb-dot 1s infinite}" +
    ".fb-typing i:nth-child(2){animation-delay:.15s}.fb-typing i:nth-child(3){animation-delay:.3s}" +
    ".fb-form{display:flex;gap:8px;padding:12px;border-top:1px solid #e5e7eb;background:#fff}" +
    ".fb-form input{flex:1;border:1px solid #d1d5db;border-radius:22px;padding:10px 14px;font:inherit;outline:none;color:#111827;background:#fff}" +
    ".fb-form input:focus{border-color:var(--fb-accent)}" +
    ".fb-form button{border:0;background:var(--fb-accent);color:#fff;border-radius:50%;width:42px;height:42px;cursor:pointer;display:flex;align-items:center;justify-content:center}" +
    ".fb-form button:disabled{opacity:.5;cursor:default}" +
    ".fb-foot{font-size:11px;color:#9ca3af;text-align:center;padding:0 0 8px;background:#fff}" +
    "@keyframes fb-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}" +
    "@keyframes fb-dot{0%,60%,100%{opacity:.3;transform:translateY(0)}30%{opacity:1;transform:translateY(-3px)}}" +
    "@media (max-width:480px){.fb-root{right:12px;bottom:12px}.fb-panel{height:calc(100vh - 100px)}}";

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var root = document.createElement("div");
  root.className = "fb-root";
  root.innerHTML =
    '<div class="fb-panel" role="dialog" aria-label="Chat with ' + TITLE + '">' +
      '<div class="fb-head"><div class="fb-avatar">👩‍🍳</div><div><b></b><small></small></div>' +
      '<button class="fb-close" aria-label="Close chat">×</button></div>' +
      '<div class="fb-body" aria-live="polite"></div>' +
      '<form class="fb-form"><input type="text" maxlength="500" placeholder="Type your message…" aria-label="Message" autocomplete="off">' +
      '<button type="submit" aria-label="Send"><svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg></button></form>' +
      '<div class="fb-foot">FoodieBot · AI cooking assistant</div>' +
    '</div>' +
    '<button class="fb-launcher" aria-label="Open chat"><span class="fb-badge"></span>' +
      '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2z"/></svg></button>';
  document.body.appendChild(root);

  root.querySelector(".fb-head b").textContent = TITLE;
  root.querySelector(".fb-head small").textContent = SUBTITLE;
  var body = root.querySelector(".fb-body");
  var form = root.querySelector(".fb-form");
  var input = form.querySelector("input");
  var sendBtn = form.querySelector("button");
  var badge = root.querySelector(".fb-badge");
  var greeted = false;

  function scroll() { body.scrollTop = body.scrollHeight; }

  // Renders **bold** safely (text is escaped first).
  function render(el, text) {
    text.split(/(\*\*[^*]+\*\*)/).forEach(function (part) {
      if (/^\*\*[^*]+\*\*$/.test(part)) {
        var b = document.createElement("b"); b.textContent = part.slice(2, -2); el.appendChild(b);
      } else { el.appendChild(document.createTextNode(part)); }
    });
  }

  function addMsg(text, who) {
    var el = document.createElement("div");
    el.className = "fb-msg fb-" + who;
    render(el, text);
    body.appendChild(el); scroll();
    return el;
  }

  function addChips(list) {
    body.querySelectorAll(".fb-chips").forEach(function (c) { c.remove(); });
    if (!list || !list.length) return;
    var wrap = document.createElement("div");
    wrap.className = "fb-chips";
    list.forEach(function (s) {
      var c = document.createElement("button");
      c.type = "button"; c.className = "fb-chip"; c.textContent = s;
      c.onclick = function () { send(s); };
      wrap.appendChild(c);
    });
    body.appendChild(wrap); scroll();
  }

  function addFeedback(messageId) {
    var meta = document.createElement("div");
    meta.className = "fb-meta";
    meta.innerHTML = '<span>Helpful?</span><button type="button" aria-label="Helpful">👍</button><button type="button" aria-label="Not helpful">👎</button>';
    var btns = meta.querySelectorAll("button");
    [true, false].forEach(function (helpful, i) {
      btns[i].onclick = function () {
        btns.forEach(function (b) { b.classList.remove("on"); });
        btns[i].classList.add("on");
        fetch(API + "/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message_id: messageId, helpful: helpful }) }).catch(function () {});
      };
    });
    body.appendChild(meta); scroll();
  }

  function typing(on) {
    var t = body.querySelector(".fb-typing");
    if (on && !t) {
      t = document.createElement("div"); t.className = "fb-typing"; t.innerHTML = "<i></i><i></i><i></i>";
      body.appendChild(t); scroll();
    } else if (!on && t) { t.remove(); }
  }

  function send(text) {
    text = (text || "").trim();
    if (!text) return;
    addChips([]);
    addMsg(text, "user");
    input.value = ""; sendBtn.disabled = true; typing(true);
    var started = Date.now();
    fetch(API + "/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }) })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        // short natural pause so the typing indicator is visible
        var wait = Math.max(0, 450 - (Date.now() - started));
        setTimeout(function () {
          typing(false);
          if (!res.ok) { addMsg(res.d.error || "Something went wrong.", "bot"); return; }
          addMsg(res.d.reply, "bot");
          if (res.d.message_id && res.d.intent !== "fallback") addFeedback(res.d.message_id);
          addChips(res.d.suggestions);
        }, wait);
      })
      .catch(function () { typing(false); addMsg("I can't reach the server right now. Please try again in a moment.", "bot"); })
      .finally(function () { sendBtn.disabled = false; input.focus(); });
  }

  function toggle(open) {
    var isOpen = root.classList.toggle("fb-open", open);
    if (isOpen) {
      badge.style.display = "none";
      if (!greeted) {
        greeted = true;
        addMsg("Hi! 👋 I'm " + TITLE + ", your AI kitchen buddy. Tell me what ingredients you have, or ask me what to eat today!", "bot");
        addChips(["What should I eat?", "Cook with what I have", "Surprise me", "Plan my meals today"]);
      }
      setTimeout(function () { input.focus(); }, 50);
    }
  }

  root.querySelector(".fb-launcher").onclick = function () { toggle(); };
  root.querySelector(".fb-close").onclick = function () { toggle(false); };
  form.addEventListener("submit", function (e) { e.preventDefault(); send(input.value); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") toggle(false); });

  window.FoodieChat = { open: function () { toggle(true); }, close: function () { toggle(false); }, send: function (t) { toggle(true); send(t); } };
})();
