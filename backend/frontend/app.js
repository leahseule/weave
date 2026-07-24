"use strict";

// 브라우저 자동 스크롤 복원 끄기 — 스크롤 위치를 render()가 직접 제어
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

// --- API client ------------------------------------------------------------
const api = {
  async _json(method, url, body) {
    const opt = { method, headers: {}, cache: "no-store" };
    if (body !== undefined) {
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body);
    }
    const res = await fetch(url, opt);
    if (!res.ok) {
      if (res.status === 401 && !url.startsWith("/auth/")) {
        currentUser = null;
        document.body.classList.add("auth-view");
        renderAuth(document.getElementById("view"));
        throw new Error("로그인이 필요해요");
      }
      const detail = await res.json().catch(() => ({}));
      throw new Error(typeof detail.detail === "string" ? detail.detail : `HTTP ${res.status}`);
    }
    return res.status === 204 ? null : res.json();
  },
  me: () => api._json("GET", "/auth/me"),
  register: (email, password) => api._json("POST", "/auth/register", { email, password }),
  login: (email, password) => api._json("POST", "/auth/login", { email, password }),
  logout: () => api._json("POST", "/auth/logout"),
  authConfig: () => api._json("GET", "/auth/config"),
  listProjects: (active) => api._json("GET", active === undefined ? "/projects" : `/projects?active=${active}`),
  getProject: (id) => api._json("GET", `/projects/${id}`),
  createProject: (data) => api._json("POST", "/projects", data),
  updateProject: (id, data) => api._json("PATCH", `/projects/${id}`, data),
  listMembers: (id) => api._json("GET", `/projects/${id}/members`),
  addMember: (id, email, role) => api._json("POST", `/projects/${id}/members`, { email, role }),
  updateMemberRole: (id, userId, role) => api._json("PATCH", `/projects/${id}/members/${userId}`, { role }),
  removeMember: (id, userId) => api._json("DELETE", `/projects/${id}/members/${userId}`),
  pasteNote: (id, data) => api._json("POST", `/projects/${id}/notes`, data),
  createDocument: (id, data) => api._json("POST", `/projects/${id}/documents`, data),
  audioMeeting: async (id, file, title, attendees, note) => {
    const fd = new FormData();
    fd.append("file", file);
    if (title) fd.append("title", title);
    if (attendees && attendees.length) fd.append("attendees", attendees.join(","));
    if (note && note.trim()) fd.append("note", note.trim());
    const res = await fetch(`/projects/${id}/meetings/audio`, { method: "POST", body: fd });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(typeof d.detail === "string" ? d.detail : `HTTP ${res.status}`);
    }
    return res.json();
  },
  createContext: (projectId, data) => api._json("POST", `/projects/${projectId}/context-items`, data),
  updateContext: (itemId, data) => api._json("PATCH", `/context-items/${itemId}`, data),
  deleteContext: (itemId) => api._json("DELETE", `/context-items/${itemId}`),
  toggleAction: (itemId, done) => api._json("PATCH", `/action-items/${itemId}`, { done }),
  createActionItem: (sourceId, data) => api._json("POST", `/sources/${sourceId}/action-items`, data),
  updateAction: (itemId, data) => api._json("PATCH", `/action-items/${itemId}`, data),
  deleteAction: (itemId) => api._json("DELETE", `/action-items/${itemId}`),
  calendar: () => api._json("GET", "/calendar"),
  updateSource: (id, data) => api._json("PATCH", `/sources/${id}`, data),
  deleteSource: (id) => api._json("DELETE", `/sources/${id}`),
  driveStatus: () => api._json("GET", "/drive/status"),
  driveDisconnect: () => api._json("DELETE", "/drive/disconnect"),
  driveSearch: (q) => api._json("GET", `/drive/search?q=${encodeURIComponent(q)}`),
  driveRecommend: (projectId) => api._json("GET", `/drive/recommend?project_id=${projectId}`),
  obsidianStatus: () => api._json("GET", "/obsidian/status"),
  obsidianSetConfig: (path) => api._json("POST", "/obsidian/config", { path }),
  obsidianClearConfig: () => api._json("DELETE", "/obsidian/config"),
  obsidianSearch: (q) => api._json("GET", `/obsidian/search?q=${encodeURIComponent(q)}`),
  obsidianRecent: () => api._json("GET", "/obsidian/recent"),
  addObsidianNote: (projectId, path) => api._json("POST", `/projects/${projectId}/obsidian-notes`, { path }),
};

// --- Helpers ---------------------------------------------------------------
const el = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
// Google Drive 공식 로고 (인라인 SVG). h=높이(px), 폭은 비율 유지.
const driveLogo = (h = 18) => `<svg class="drive-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 87.3 78" width="${Math.round(h * 1.12)}" height="${h}" aria-hidden="true"><path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/><path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44c-.8 1.4-1.2 2.95-1.2 4.5h27.5z" fill="#00ac47"/><path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.502l5.852 11.5z" fill="#ea4335"/><path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/><path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/><path d="m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 28h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00"/></svg>`;
const esc = (s) => (s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtDate = (iso) => new Date(iso).toLocaleDateString("ko-KR", { year: "2-digit", month: "2-digit", day: "2-digit" });
// Blob을 파일로 내려받기 (전사 실패 시 녹음 보관 등)
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
const recTimestamp = () => { const d = new Date(), p = (n) => String(n).padStart(2, "0"); return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`; };
function fmtWhen(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "방금 전";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}일 전`;
  return fmtDate(iso);
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.hidden = true), 2500);
}

const overlay = document.getElementById("modal-overlay");
const modalEl = document.getElementById("modal");
let modalOnClose = null;
function openModal(node, onClose) { modalOnClose = onClose || null; modalEl.replaceChildren(node); overlay.hidden = false; }
function closeModal() { const cb = modalOnClose; modalOnClose = null; overlay.hidden = true; modalEl.replaceChildren(); if (cb) cb(); }
overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });

/** 커스텀 입력 팝업. 확인 시 입력값(문자열), 취소/바깥클릭 시 null 을 resolve. */
function promptModal({ title, label = "", value = "", placeholder = "", multiline = false, okText = "확인" }) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (v) => { if (!settled) { settled = true; resolve(v); } };
    const fieldHtml = multiline
      ? `<textarea id="pm-input" placeholder="${esc(placeholder)}">${esc(value)}</textarea>`
      : `<input id="pm-input" type="text" value="${esc(value)}" placeholder="${esc(placeholder)}">`;
    const modal = el(`
      <div>
        <h3>${esc(title)}</h3>
        <div class="field">${label ? `<label>${esc(label)}</label>` : ""}${fieldHtml}</div>
        <div class="modal-actions">
          <button class="btn btn-ghost" data-act="cancel">취소</button>
          <button class="btn btn-primary" data-act="ok">${esc(okText)}</button>
        </div>
      </div>`);
    const input = modal.querySelector("#pm-input");
    const submit = () => { const v = input.value.trim(); finish(v || null); closeModal(); };
    modal.querySelector('[data-act="cancel"]').addEventListener("click", () => { finish(null); closeModal(); });
    modal.querySelector('[data-act="ok"]').addEventListener("click", submit);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !multiline) { e.preventDefault(); submit(); }
      else if (e.key === "Escape") { finish(null); closeModal(); }
    });
    openModal(modal, () => finish(null));
    setTimeout(() => { input.focus(); if (!multiline) input.select(); }, 50);
  });
}

// --- Long-press → context menu ---------------------------------------------
function closeContextMenu() { document.querySelectorAll(".context-menu").forEach((m) => m.remove()); }

function showContextMenu(x, y, items, opts = {}) {
  closeContextMenu();
  const menu = el(`<div class="context-menu"></div>`);
  for (const it of items) {
    const iconHtml = it.iconHtml || `<span class="material-symbols-outlined">${it.icon}</span>`;
    const b = el(`<button class="ctx-menu-item ${it.danger ? "danger" : ""}">${iconHtml}${esc(it.label)}</button>`);
    b.addEventListener("click", () => { closeContextMenu(); it.onClick(); });
    menu.append(b);
  }
  document.body.append(menu);
  const r = menu.getBoundingClientRect();
  const left = opts.center ? x - r.width / 2 : x;
  const top = opts.above ? y - r.height - 10 : y;
  menu.style.left = Math.max(8, Math.min(left, window.innerWidth - r.width - 8)) + "px";
  menu.style.top = Math.max(8, Math.min(top, window.innerHeight - r.height - 8)) + "px";
  setTimeout(() => {
    document.addEventListener("click", closeContextMenu, { once: true });
    document.addEventListener("scroll", closeContextMenu, { once: true, capture: true });
  }, 0);
}

/** 요소에 롱프레스(모바일) + 우클릭(데스크톱)으로 컨텍스트 메뉴를 연다. */
function attachLongPress(node, getItems) {
  let timer = null, sx = 0, sy = 0;
  const fire = (x, y) => {
    showContextMenu(x, y, getItems());
    // 롱프레스 직후 따라오는 click(카드 네비 등) 억제
    const suppress = (ev) => { ev.stopPropagation(); ev.preventDefault(); };
    node.addEventListener("click", suppress, { capture: true, once: true });
    setTimeout(() => node.removeEventListener("click", suppress, { capture: true }), 500);
  };
  const start = (x, y) => { sx = x; sy = y; timer = setTimeout(() => fire(x, y), 500); };
  const cancel = () => { clearTimeout(timer); timer = null; };
  node.addEventListener("touchstart", (e) => { const t = e.touches[0]; start(t.clientX, t.clientY); }, { passive: true });
  node.addEventListener("touchmove", (e) => { const t = e.touches[0]; if (Math.hypot(t.clientX - sx, t.clientY - sy) > 10) cancel(); }, { passive: true });
  node.addEventListener("touchend", cancel);
  node.addEventListener("touchcancel", cancel);
  node.addEventListener("mousedown", (e) => { if (e.button === 0) start(e.clientX, e.clientY); });
  node.addEventListener("mouseup", cancel);
  node.addEventListener("mouseleave", cancel);
  node.addEventListener("contextmenu", (e) => { e.preventDefault(); fire(e.clientX, e.clientY); });
}

/** 확인(경고) 모달. 확인 시 true, 취소/바깥클릭 시 false. */
function confirmModal({ title = "삭제할까요?", message = "", confirmText = "삭제", danger = true }) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (v) => { if (!settled) { settled = true; resolve(v); } };
    const modal = el(`
      <div>
        <h3>${esc(title)}</h3>
        ${message ? `<p class="summary-text" style="margin-bottom:22px">${esc(message)}</p>` : ""}
        <div class="modal-actions">
          <button class="btn btn-ghost" data-act="cancel">취소</button>
          <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-act="ok">${esc(confirmText)}</button>
        </div>
      </div>`);
    modal.querySelector('[data-act="cancel"]').addEventListener("click", () => { finish(false); closeModal(); });
    modal.querySelector('[data-act="ok"]').addEventListener("click", () => { finish(true); closeModal(); });
    openModal(modal, () => finish(false));
  });
}

/** 날짜 선택 팝업. 저장 시 "YYYY-MM-DD", 취소/비움 시 null. */
function datePickerModal(current) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (v) => { if (!settled) { settled = true; resolve(v); } };
    const modal = el(`
      <div>
        <h3>마감일 지정</h3>
        <div class="field"><input id="dp-input" type="date" value="${esc(current || "")}"></div>
        <div class="modal-actions">
          <button class="btn btn-ghost" data-act="cancel">취소</button>
          <button class="btn btn-primary" data-act="ok">저장</button>
        </div>
      </div>`);
    modal.querySelector('[data-act="cancel"]').addEventListener("click", () => { finish(null); closeModal(); });
    modal.querySelector('[data-act="ok"]').addEventListener("click", () => { finish(modal.querySelector("#dp-input").value || null); closeModal(); });
    openModal(modal, () => finish(null));
    setTimeout(() => modal.querySelector("#dp-input").focus(), 50);
  });
}

/** 커스텀 입력 팝업으로 텍스트를 받아 save 콜백 실행 후 재렌더. */
async function editText(title, current, save, opts = {}) {
  const next = await promptModal({ title, value: current || "", multiline: !!opts.multiline, placeholder: opts.placeholder || "" });
  if (next === null) return;
  try { await save(next); render(); } catch (e) { toast(e.message); }
}

// --- 녹음 상태 정리 ---------------------------------------------------------
let rec = null;
let lastHash = null; // 스크롤 보존용: 같은 경로 재렌더인지 판별
let lastDetailHash = null; // '최근(이어보기)'용: 마지막으로 본 프로젝트/회의 상세
function cleanupRec() {
  if (!rec) return;
  try { if (rec.recorder && rec.recorder.state !== "inactive") rec.recorder.stop(); } catch (_) {}
  try { rec.stream && rec.stream.getTracks().forEach((t) => t.stop()); } catch (_) {}
  clearInterval(rec.timer);
  cancelAnimationFrame(rec.raf);
  try { rec.audioCtx && rec.audioCtx.close(); } catch (_) {}
  rec = null;
}

// --- Auth (로그인 / 회원가입) ------------------------------------------------
async function renderAuth(view) {
  view.replaceChildren();
  let mode = "login";  // "login" | "register"
  // Google 콜백 실패 메시지 (?auth=error|denied) 처리 후 URL 정리
  const authQuery = new URLSearchParams(location.search).get("auth");
  if (authQuery) history.replaceState(null, "", location.pathname + location.hash);
  let googleEnabled = false;
  try { googleEnabled = (await api.authConfig()).google; } catch (_) {}
  const wrap = el(`<div class="auth-wrap"></div>`);
  const card = el(`<div class="auth-card"></div>`);
  wrap.append(card);
  view.append(wrap);

  const paint = () => {
    const isLogin = mode === "login";
    card.replaceChildren();
    card.append(el(`<div class="auth-brand"><span class="material-symbols-outlined">account_tree</span> Weave</div>`));
    card.append(el(`<p class="auth-sub">회의·메모·문서를 프로젝트로 엮다</p>`));
    if (authQuery) card.append(el(`<div class="auth-err" style="margin-bottom:14px">${authQuery === "denied" ? "Google 로그인이 취소됐어요." : "Google 로그인에 실패했어요. 다시 시도해주세요."}</div>`));
    const form = el(`
      <form class="auth-form">
        <input id="au-email" type="email" placeholder="이메일" autocomplete="username">
        <input id="au-pw" type="password" placeholder="비밀번호 (6자 이상)" autocomplete="${isLogin ? "current-password" : "new-password"}">
        <div class="auth-err" id="au-err" hidden></div>
        <button class="btn btn-primary auth-submit" type="submit">${isLogin ? "로그인" : "회원가입"}</button>
      </form>`);
    const err = form.querySelector("#au-err");
    const submitBtn = form.querySelector(".auth-submit");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = form.querySelector("#au-email").value.trim();
      const pw = form.querySelector("#au-pw").value;
      if (!email || !pw) return;
      err.hidden = true;
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span class="spinner"></span>`;
      try {
        currentUser = isLogin ? await api.login(email, pw) : await api.register(email, pw);
        document.body.classList.remove("auth-view");
        location.hash = "#/";
        render();
      } catch (ex) {
        err.textContent = ex.message;
        err.hidden = false;
        submitBtn.disabled = false;
        submitBtn.textContent = isLogin ? "로그인" : "회원가입";
      }
    });
    card.append(form);

    if (googleEnabled) {
      card.append(el(`<div class="auth-or"><span>또는</span></div>`));
      const gbtn = el(`<button type="button" class="auth-google"><svg class="g-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg> Google로 계속하기</button>`);
      gbtn.addEventListener("click", () => { window.location.href = "/auth/google/login"; });
      card.append(gbtn);
    }

    const toggle = el(`<div class="auth-toggle">${isLogin ? "계정이 없으신가요? " : "이미 계정이 있으신가요? "}<a>${isLogin ? "회원가입" : "로그인"}</a></div>`);
    toggle.querySelector("a").addEventListener("click", () => { mode = isLogin ? "register" : "login"; paint(); });
    card.append(toggle);
    setTimeout(() => card.querySelector("#au-email").focus(), 50);
  };
  paint();
}

// --- Router ----------------------------------------------------------------
let currentUser = null;  // 로그인한 사용자 (없으면 로그인 화면)
let viewRole = null;     // 현재 보고 있는 프로젝트에서 내 권한 (owner/editor/viewer)
// null(캘린더 등 맥락 불명)은 허용 — 서버가 최종 판단
const canEdit = () => viewRole === null || viewRole === "owner" || viewRole === "editor";
const isOwner = () => viewRole === "owner";

async function render() {
  const view = document.getElementById("view");
  const crumbs = document.getElementById("crumbs");
  const hash = location.hash || "#/";
  cleanupRec();  // 녹음 페이지를 떠나면 마이크·타이머 정리
  viewRole = null;  // 프로젝트/상세 렌더에서 다시 설정

  // 인증 가드: 로그인 안 됐으면 로그인 화면
  if (!currentUser) {
    try { currentUser = await api.me(); }
    catch { document.body.classList.add("auth-view"); renderAuth(view); return; }
  }
  document.body.classList.remove("auth-view");
  const scrollY = window.scrollY;
  const sameRoute = hash === lastHash;  // 액션 후 재렌더 vs 실제 페이지 이동
  lastHash = hash;
  const sourceM = hash.match(/^#\/projects\/(\d+)\/sources\/(\d+)/);
  const recordM = hash.match(/^#\/projects\/(\d+)\/record/);
  const projM = hash.match(/^#\/projects\/(\d+)/);
  const isCalendar = hash.startsWith("#/calendar");
  const isSettings = hash.startsWith("#/settings");
  if (projM && !recordM) lastDetailHash = hash;  // 마지막으로 본 상세 화면 기억
  const isList = !projM && !isCalendar && !isSettings;
  const activeNav = isSettings ? "profile" : isCalendar ? "calendar" : isList ? "folders" : "home";
  document.querySelectorAll(".bn-item").forEach((b) => b.classList.toggle("active", b.dataset.nav === activeNav));
  // + FAB는 프로젝트 상세에서만 (홈·상세·녹음·캘린더에선 숨김)
  document.getElementById("bn-fab").style.display = projM && !sourceM && !recordM ? "" : "none";
  // 상세(전사/메모)는 흰 배경 + 테두리 없는 문서 뷰로 구분
  document.body.classList.toggle("detail-view", !!sourceM);
  // 같은 경로 재렌더면 로딩 표시 생략(깜빡임·스크롤 튐 방지)
  if (!sameRoute) view.innerHTML = `<div class="loading"><span class="spinner"></span> 불러오는 중...</div>`;
  const isHome = !projM && !isCalendar && !isSettings;
  crumbs.innerHTML = isHome
    ? ""
    : `<a class="crumb-back" href="#/"><span class="material-symbols-outlined">chevron_left</span>프로젝트 목록</a>`;
  try {
    if (isSettings) {
      await renderSettings(view);
    } else if (recordM) {
      await renderRecord(view, Number(recordM[1]));
    } else if (isCalendar) {
      await renderCalendar(view);
    } else if (sourceM) {
      await renderSourceDetail(view, Number(sourceM[1]), Number(sourceM[2]));
    } else if (projM) {
      await renderProject(view, Number(projM[1]));
    } else {
      await renderHome(view);
    }
  } catch (e) {
    view.innerHTML = `<div class="empty"><span class="material-symbols-outlined">error</span>${esc(e.message)}</div>`;
  }
  // 액션 후 재렌더는 스크롤 위치 유지, 페이지 이동은 맨 위로
  const targetScroll = sameRoute ? scrollY : 0;
  window.scrollTo(0, targetScroll);
  setTimeout(() => window.scrollTo(0, targetScroll), 0);
}
window.addEventListener("hashchange", render);

// --- Home ------------------------------------------------------------------
let homeActive = true; // true=활성 탭, false=비활성 탭

async function renderHome(view) {
  const projects = await api.listProjects(homeActive);
  view.replaceChildren();
  view.append(el(`<h1 class="page-title">프로젝트</h1>`));
  view.append(el(`<p class="page-sub">회의를 프로젝트 단위로 모으고 히스토리를 한눈에.</p>`));

  // 활성 / 비활성 탭
  const tabs = el(`<div class="seg-tabs"></div>`);
  const mkTab = (label, val) => {
    const b = el(`<button class="seg-tab ${homeActive === val ? "active" : ""}">${label}</button>`);
    b.addEventListener("click", () => { if (homeActive !== val) { homeActive = val; render(); } });
    return b;
  };
  tabs.append(mkTab("활성", true), mkTab("비활성", false));
  view.append(tabs);

  if (projects.length === 0) {
    const msg = homeActive
      ? "활성 프로젝트가 없어요.<br>오른쪽 위 '새 프로젝트'로 시작하세요."
      : "비활성 프로젝트가 없어요.";
    view.append(el(`<div class="empty"><span class="material-symbols-outlined">folder_open</span>${msg}</div>`));
    return;
  }

  const grid = el(`<div class="project-grid"></div>`);
  for (const p of projects) {
    const card = el(`
      <div class="card project-card longpress">
        <h3>${esc(p.name)}</h3>
        <p class="obj">${esc(p.objective || "")}</p>
        <div class="meta">
          <span><span class="material-symbols-outlined">forum</span>${p.meeting_count} 회의</span>
          <span><span class="material-symbols-outlined">description</span>${p.document_count} 문서</span>
          <span><span class="material-symbols-outlined">schedule</span>${fmtWhen(p.updated_at)}</span>
        </div>
      </div>`);
    card.addEventListener("click", () => (location.hash = `#/projects/${p.id}`));
    attachLongPress(card, () => [
      p.active
        ? { label: "비활성화", icon: "archive", onClick: async () => { try { await api.updateProject(p.id, { active: false }); render(); } catch (e) { toast(e.message); } } }
        : { label: "활성화", icon: "unarchive", onClick: async () => { try { await api.updateProject(p.id, { active: true }); render(); } catch (e) { toast(e.message); } } },
    ]);
    grid.append(card);
  }
  view.append(grid);
}

// --- Settings (Google Drive 연동) ------------------------------------------
async function renderSettings(view) {
  const st = await api.driveStatus();
  const obst = await api.obsidianStatus();
  view.replaceChildren();
  view.append(el(`<h1 class="page-title">설정</h1>`));
  view.append(el(`<p class="page-sub">계정 및 외부 연동을 관리합니다.</p>`));

  // 계정
  const acct = el(`<section class="card"><h2 class="section-title"><span class="material-symbols-outlined">account_circle</span>계정</h2></section>`);
  acct.append(el(`<p class="settings-path">${esc(currentUser ? currentUser.email : "")}</p>`));
  const logoutBtn = el(`<button class="btn btn-ghost">로그아웃</button>`);
  logoutBtn.addEventListener("click", async () => {
    try { await api.logout(); } catch (_) {}
    currentUser = null;
    location.hash = "#/";
    document.body.classList.add("auth-view");
    renderAuth(document.getElementById("view"));
  });
  acct.append(logoutBtn);
  view.append(acct);

  const card = el(`<section class="card"><h2 class="section-title">${driveLogo(20)}Google Drive</h2></section>`);
  if (!st.configured) {
    card.append(el(`<p class="summary-empty">서버에 OAuth 설정(GOOGLE_CLIENT_ID/SECRET)이 없습니다. weave/.env 에 값을 넣고 재시작하세요.</p>`));
  } else if (st.connected) {
    card.append(el(`<p class="summary-text" style="margin-bottom:16px"><span class="material-symbols-outlined" style="color:var(--secondary);vertical-align:middle">check_circle</span> 연결됨 — 내 Google Drive 문서를 검색해 프로젝트에 참조 문서로 붙일 수 있어요.</p>`));
    const disc = el(`<button class="btn">연결 해제</button>`);
    disc.addEventListener("click", async () => { try { await api.driveDisconnect(); toast("연결 해제됨"); render(); } catch (e) { toast(e.message); } });
    card.append(disc);
  } else {
    card.append(el(`<p class="summary-text" style="margin-bottom:16px">연결하면 내 Google Drive 문서를 검색해 프로젝트에 참조로 붙일 수 있어요. (회의 태그 기반 추천도 제공)</p>`));
    const btn = el(`<button class="btn btn-primary"><span class="material-symbols-outlined">link</span>Google Drive 연결</button>`);
    btn.addEventListener("click", () => { window.location.href = "/drive/connect"; });
    card.append(btn);
  }
  view.append(card);

  // Obsidian
  view.append(buildObsidianCard(obst));
}

function buildObsidianCard(obst) {
  const card = el(`<section class="card"><h2 class="section-title"><span class="material-symbols-outlined">menu_book</span>Obsidian</h2></section>`);
  if (obst.configured) {
    const status = el(`<p class="summary-text"><span class="material-symbols-outlined" style="color:var(--secondary);vertical-align:middle">check_circle</span> 볼트 연결됨</p>`);
    card.append(status);
    if (obst.host_path) card.append(el(`<p class="settings-path">${esc(obst.host_path)}</p>`));
    card.append(el(`<p class="settings-hint">노트를 검색해 메모로 추가할 수 있어요. ＋ 버튼 → 옵시디언에서 검색.</p>`));
    const disc = el(`<button class="btn btn-ghost">연결 해제</button>`);
    disc.addEventListener("click", async () => {
      const ok = await confirmModal({ title: "연결 해제", message: "옵시디언 볼트 연결을 해제할까요?", confirmText: "해제", danger: false });
      if (!ok) return;
      await api.obsidianClearConfig();
      toast("연결 해제됨");
      render();
    });
    card.append(disc);
  } else {
    card.append(el(`<p class="settings-hint">옵시디언 볼트 폴더의 경로를 입력하면 노트를 검색해 메모로 가져올 수 있어요. (홈 폴더 <code>C:\\Users\\...</code> 안에 있는 볼트만 지원)</p>`));
    const box = el(`
      <div>
        <div class="settings-form">
          <input id="ob-path" class="settings-input" placeholder="예: C:\\Users\\사용자\\Documents\\MyVault">
          <button class="btn btn-primary" id="ob-connect">연결</button>
        </div>
        <p class="settings-err" id="ob-err" hidden></p>
      </div>`);
    const input = box.querySelector("#ob-path");
    const btn = box.querySelector("#ob-connect");
    const err = box.querySelector("#ob-err");
    const connect = async () => {
      const path = input.value.trim();
      if (!path) { err.textContent = "볼트 경로를 입력하세요"; err.hidden = false; return; }
      err.hidden = true;
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner"></span>`;
      try {
        await api.obsidianSetConfig(path);
        toast("볼트 연결됨");
        render();
      } catch (e) {
        err.textContent = e.message;
        err.hidden = false;
        btn.disabled = false;
        btn.textContent = "연결";
      }
    };
    btn.addEventListener("click", connect);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); connect(); } });
    card.append(box);
  }
  return card;
}

// 칩 입력 컴포넌트: 이름을 Enter/콤마로 추가, × 로 삭제 (참석자 등)
function chipInput(initial = [], placeholder = "이름 입력 후 Enter") {
  const wrap = el(`<div class="chip-input"></div>`);
  const chips = el(`<div class="chip-input-chips"></div>`);
  const input = el(`<input class="chip-input-field" placeholder="${esc(placeholder)}">`);
  const values = [...initial];
  const renderChips = () => {
    chips.replaceChildren();
    values.forEach((v, i) => {
      const chip = el(`<span class="chip removable">${esc(v)}<button type="button" class="chip-x" title="삭제">×</button></span>`);
      chip.querySelector(".chip-x").addEventListener("click", () => { values.splice(i, 1); renderChips(); });
      chips.append(chip);
    });
  };
  const add = () => {
    const v = input.value.replace(/,/g, "").trim();
    if (v && !values.includes(v)) { values.push(v); renderChips(); }
    input.value = "";
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); }
    else if (e.key === "Backspace" && !input.value && values.length) { values.pop(); renderChips(); }
  });
  input.addEventListener("blur", add);
  wrap.append(chips, input);
  renderChips();
  return { element: wrap, get: () => values.slice() };
}

// --- Recording (회의 녹음) --------------------------------------------------
async function renderRecord(view, pid) {
  view.replaceChildren();
  const screen = el(`<div class="record-screen"></div>`);
  view.append(screen);
  let attendeeCtl = null;
  let attendees = [];
  let noteText = "";  // 녹음 중 작성하는 메모 (그래놀라식)
  let noteEditor = null;  // 마크다운 라이브 에디터

  const showIdle = () => {
    screen.replaceChildren();
    screen.append(el(`<div class="record-hint">회의를 녹음하세요</div>`));
    const att = el(`<div class="record-attendees"></div>`);
    att.append(el(`<div class="record-att-label"><span class="material-symbols-outlined">group</span>참석자 (선택)</div>`));
    attendeeCtl = chipInput(attendees, "이름 입력 후 Enter");
    att.append(attendeeCtl.element);
    screen.append(att);
    const btn = el(`<button class="record-btn" title="녹음 시작"><span class="material-symbols-outlined">mic</span></button>`);
    btn.addEventListener("click", startRecording);
    screen.append(btn, el(`<div class="record-sub">탭하여 녹음 시작</div>`));
    const upload = el(`<button class="btn btn-ghost record-alt"><span class="material-symbols-outlined">upload</span>음성 파일 업로드</button>`);
    upload.addEventListener("click", () => openAudioModal(pid));
    const cancel = el(`<button class="btn btn-ghost">취소</button>`);
    cancel.addEventListener("click", () => { location.hash = `#/projects/${pid}`; });
    screen.append(upload, cancel);
  };

  const showRecording = () => {
    screen.replaceChildren();
    // 녹음 상태 헤더 (컴팩트)
    const head = el(`<div class="record-live-head"></div>`);
    const dot = el(`<div class="record-live-dot"></div>`);
    const status = el(`<div class="record-live-status">녹음 중</div>`);
    const timer = el(`<div class="record-timer">00:00</div>`);
    const bars = el(`<div class="record-bars">${Array.from({ length: 9 }).map(() => "<span></span>").join("")}</div>`);
    const pauseBtn = el(`<button class="record-btn sm pause-btn" title="일시중지"><span class="material-symbols-outlined">pause</span></button>`);
    const stop = el(`<button class="record-btn recording sm" title="정지"><span class="material-symbols-outlined">stop</span></button>`);
    stop.addEventListener("click", stopRecording);
    const setPausedUI = (p) => {
      pauseBtn.querySelector(".material-symbols-outlined").textContent = p ? "play_arrow" : "pause";
      pauseBtn.title = p ? "재개" : "일시중지";
      dot.classList.toggle("paused", p);
      status.textContent = p ? "일시중지됨" : "녹음 중";
      bars.classList.toggle("paused", p);
    };
    pauseBtn.addEventListener("click", () => {
      if (!rec || !rec.recorder) return;
      if (rec.recorder.state === "recording") {
        rec.recorder.pause();
        rec.pauseStart = Date.now();
        clearInterval(rec.timer); rec.timer = null;
        cancelAnimationFrame(rec.raf); rec.raf = null;
        setPausedUI(true);
      } else if (rec.recorder.state === "paused") {
        rec.pausedMs += Date.now() - rec.pauseStart;
        rec.recorder.resume();
        startTimer();
        startWave();
        setPausedUI(false);
      }
    });
    head.append(dot, status, timer, bars, pauseBtn, stop);
    screen.append(head);
    // 그래놀라식: 녹음 중 메모 (마크다운 라이브 에디터 — Enter로 렌더 적용)
    const noteCard = el(`<section class="card record-note-card"></section>`);
    noteCard.append(el(`<div class="record-note-label"><span class="material-symbols-outlined">stylus_note</span> 내 메모 · Markdown (Enter로 적용)</div>`));
    noteEditor = mdLiveEditor(noteText, "회의 중 떠오른 생각을 자유롭게 남겨보세요…");
    noteEditor.element.classList.add("record-note-editor");
    noteCard.append(noteEditor.element);
    screen.append(noteCard);
    rec.timerEl = timer;
    rec.barEls = [...bars.querySelectorAll("span")];
    setTimeout(() => noteEditor && noteEditor.focus(), 100);
  };

  const showProcessing = () => {
    screen.replaceChildren();
    screen.append(el(`<div class="loading" style="flex-direction:column;gap:16px"><span class="spinner" style="width:34px;height:34px"></span><div>전사하고 있어요…</div></div>`));
  };

  const startTimer = () => {
    rec.timer = setInterval(() => {
      const s = Math.floor((Date.now() - rec.startedAt - rec.pausedMs) / 1000);
      if (rec.timerEl) rec.timerEl.textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    }, 250);
  };
  const startWave = () => {
    if (!rec.analyser) return;
    const tick = () => {
      rec.analyser.getByteFrequencyData(rec.waveData);
      rec.barEls.forEach((b, i) => { b.style.transform = `scaleY(${0.12 + (rec.waveData[i * 2] / 255) * 0.88})`; });
      rec.raf = requestAnimationFrame(tick);
    };
    tick();
  };

  async function startRecording() {
    if (attendeeCtl) attendees = attendeeCtl.get();  // 녹음 시작 시점 참석자 확정
    let stream;
    try {
      // AGC(자동 게인) 끄고 노이즈 억제·에코 제거 → 조용할 때 감도 과하게 오르는 것 방지
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: false },
      });
    } catch (e) { toast("마이크 권한이 필요해요"); return; }

    const mime = MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4" : "";
    const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks = [];
    recorder.addEventListener("dataavailable", (e) => { if (e.data.size) chunks.push(e.data); });
    rec = { recorder, stream, chunks, mime, startedAt: Date.now(), pausedMs: 0, pauseStart: 0, timer: null, raf: null, audioCtx: null, analyser: null, waveData: null };
    recorder.start();
    showRecording();
    startTimer();

    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      rec.audioCtx = new AudioCtx();
      rec.analyser = rec.audioCtx.createAnalyser();
      rec.analyser.fftSize = 64;
      rec.audioCtx.createMediaStreamSource(stream).connect(rec.analyser);
      rec.waveData = new Uint8Array(rec.analyser.frequencyBinCount);
      startWave();
    } catch (_) {}
  }

  async function stopRecording() {
    if (!rec || !rec.recorder) return;
    if (noteEditor) noteText = noteEditor.getValue();  // 화면 교체 전에 메모 확정
    const { recorder, chunks, stream, mime } = rec;
    clearInterval(rec.timer);
    cancelAnimationFrame(rec.raf);
    showProcessing();
    const done = new Promise((r) => recorder.addEventListener("stop", r, { once: true }));
    recorder.stop();
    await done;
    stream.getTracks().forEach((t) => t.stop());
    try { rec.audioCtx && rec.audioCtx.close(); } catch (_) {}
    const type = mime || "audio/webm";
    const ext = type.includes("mp4") ? "mp4" : "webm";
    const file = new File([new Blob(chunks, { type })], `recording.${ext}`, { type });
    rec = null;

    const title = `회의 녹음 ${new Date().toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
    try {
      const src = await api.audioMeeting(pid, file, title, attendees, noteText);
      toast("회의 추가됨");
      location.hash = `#/projects/${pid}/sources/${src.id}`;
    } catch (e) {
      // 전사 실패 시 녹음 유실 방지: 오디오 파일을 자동으로 내려받아 보관
      downloadBlob(file, `회의녹음_${recTimestamp()}.${ext}`);
      toast(`${e.message || "전사 실패"} — 녹음 파일을 저장했어요`);
      location.hash = `#/projects/${pid}`;
    }
  }

  showIdle();
}

// --- Calendar --------------------------------------------------------------
let calRef = null; // { y, m } — 표시 중인 연/월(0-based)

async function renderCalendar(view) {
  const items = await api.calendar();
  const byDate = {};
  for (const it of items) (byDate[it.due_date] = byDate[it.due_date] || []).push(it);

  const now = new Date();
  if (!calRef) calRef = { y: now.getFullYear(), m: now.getMonth() };
  const { y, m } = calRef;
  const pad = (n) => String(n).padStart(2, "0");
  const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

  view.replaceChildren();

  const header = el(`<div class="cal-header"></div>`);
  const prev = el(`<button class="icon-btn"><span class="material-symbols-outlined">chevron_left</span></button>`);
  const next = el(`<button class="icon-btn"><span class="material-symbols-outlined">chevron_right</span></button>`);
  prev.addEventListener("click", () => { calRef = { y: m === 0 ? y - 1 : y, m: m === 0 ? 11 : m - 1 }; render(); });
  next.addEventListener("click", () => { calRef = { y: m === 11 ? y + 1 : y, m: m === 11 ? 0 : m + 1 }; render(); });
  header.append(el(`<h1 class="page-title" style="margin:0">${y}년 ${m + 1}월</h1>`), el(`<div style="flex:1"></div>`), prev, next);
  view.append(header);

  const card = el(`<section class="card"></section>`);

  const wdRow = el(`<div class="cal-weekdays"></div>`);
  for (const w of ["일", "월", "화", "수", "목", "금", "토"]) wdRow.append(el(`<div class="cal-wd">${w}</div>`));
  card.append(wdRow);

  const grid = el(`<div class="cal-grid"></div>`);
  const startDow = new Date(y, m, 1).getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  for (let i = 0; i < startDow; i++) grid.append(el(`<div></div>`));

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${y}-${pad(m + 1)}-${pad(d)}`;
    const cell = el(`<div class="cal-cell"></div>`);
    cell.append(el(`<div class="cal-day ${dateStr === todayStr ? "today" : ""}">${d}</div>`));
    for (const it of byDate[dateStr] || []) {
      const chip = el(`<div class="cal-task ${it.done ? "done" : ""}" title="${esc(it.project_name)} · ${esc(it.source_title)}">${esc(it.content)}</div>`);
      chip.addEventListener("click", () => (location.hash = `#/projects/${it.project_id}/sources/${it.source_id}`));
      cell.append(chip);
    }
    grid.append(cell);
  }
  card.append(grid);
  view.append(card);

  if (items.length === 0) {
    view.append(el(`<p class="page-sub" style="margin-top:16px">액션아이템에 마감일을 지정하면 여기에 표시됩니다. (회의 상세 → 액션아이템 꾹 누르기 → 마감일 지정)</p>`));
  }
}

// --- Project detail --------------------------------------------------------
async function renderProject(view, id) {
  const p = await api.getProject(id);
  viewRole = p.role || null;  // 권한 게이팅 기준
  document.getElementById("bn-fab").style.display = canEdit() ? "" : "none";
  view.replaceChildren();

  // 제목 (편집 가능자만: 꾹 누르거나 더블클릭해 편집)
  const h1 = el(`<h1 class="page-title ${canEdit() ? "longpress" : ""}" style="margin:0 0 6px" ${canEdit() ? 'title="꾹 누르거나 더블클릭해 편집"' : ""}>${esc(p.name)}</h1>`);
  if (canEdit()) {
    const editName = () => editText("프로젝트 이름", p.name, (v) => api.updateProject(p.id, { name: v }));
    attachLongPress(h1, () => [{ label: "이름 수정", icon: "edit", onClick: editName }]);
    h1.addEventListener("dblclick", editName);
  }
  view.append(h1);
  const roleTag = viewRole && viewRole !== "owner" ? ` · ${viewRole === "viewer" ? "뷰어(읽기 전용)" : "에디터"}` : "";
  view.append(el(`<p class="page-sub" style="margin-bottom:28px">최종 업데이트 ${fmtWhen(p.updated_at)}${roleTag}</p>`));

  const grid = el(`<div class="detail-grid"></div>`);

  const events = p.sources.filter((s) => s.type !== "DOCUMENT");
  const documents = p.sources.filter((s) => s.type === "DOCUMENT");

  // --- Left column: Project History(회의·메모) + 관련 문서 ---
  const leftCol = el(`<div></div>`);

  const histCard = el(`<section class="card"></section>`);
  const histHead = el(`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px"></div>`);
  histHead.append(el(`<h2 class="section-title" style="margin:0"><span class="material-symbols-outlined">history</span>History</h2>`));
  const toggleAllBtn = el(`<button class="icon-btn subtle" title="액션아이템 모두 펼치기"><span class="material-symbols-outlined">unfold_more</span></button>`);
  histHead.append(toggleAllBtn);
  histCard.append(histHead);

  const timeline = el(`<div class="timeline"></div>`);
  if (events.length === 0) {
    timeline.append(el(`<p class="tl-summary">아직 회의·메모가 없어요. 하단 <b>＋</b> 버튼으로 추가하세요.</p>`));
  }
  for (const s of events) timeline.append(renderSource(s, p.id));
  histCard.append(timeline);

  // 히스토리 추가 버튼 (하단) — FAB와 동일한 추가 메뉴 (편집 가능자만)
  if (canEdit()) {
    const addHistBtn = el(`<button class="tl-add"><span class="material-symbols-outlined">add</span>히스토리 추가하기</button>`);
    addHistBtn.addEventListener("click", () => {
      const r = addHistBtn.getBoundingClientRect();
      showContextMenu(r.left + r.width / 2, r.top, historyMenuItems(p.id), { above: true, center: true });
    });
    histCard.append(addHistBtn);
  }

  // 액션아이템 전체 접기/펼치기 (기본: 접힌 상태)
  let allCollapsed = true;
  toggleAllBtn.addEventListener("click", () => {
    allCollapsed = !allCollapsed;
    timeline.querySelectorAll(".ai-sub").forEach((sub) => {
      sub.classList.toggle("collapsed", allCollapsed);
      const chev = sub.querySelector(".chev");
      if (chev) chev.textContent = allCollapsed ? "chevron_right" : "expand_more";
    });
    toggleAllBtn.innerHTML = `<span class="material-symbols-outlined">${allCollapsed ? "unfold_more" : "unfold_less"}</span>`;
    toggleAllBtn.title = allCollapsed ? "액션아이템 모두 펼치기" : "액션아이템 모두 접기";
  });
  // 액션아이템이 하나도 없으면 버튼 숨김
  toggleAllBtn.hidden = timeline.querySelectorAll(".ai-sub").length === 0;
  leftCol.append(histCard);

  const docsCard = el(`<section class="card"></section>`);
  docsCard.append(el(`<h2 class="section-title"><span class="material-symbols-outlined">folder</span>Reference <span style="font-weight:400;color:var(--on-surface-variant);font-size:14px">${documents.length || ""}</span></h2>`));
  if (documents.length === 0) {
    docsCard.append(el(`<p class="tl-summary">${canEdit() ? "아래 <b>＋ 레퍼런스 추가하기</b>로 관련 문서를 참조로 추가하세요." : "아직 참조 문서가 없어요."}</p>`));
  } else {
    const dl = el(`<div class="doc-list"></div>`);
    for (const d of documents) dl.append(renderDocCard(d));
    docsCard.append(dl);
  }
  // 레퍼런스 추가 버튼 (하단) — Drive 검색 / 링크 추가 (편집 가능자만)
  if (canEdit()) {
    const addRefBtn = el(`<button class="tl-add"><span class="material-symbols-outlined">add</span>레퍼런스 추가하기</button>`);
    addRefBtn.addEventListener("click", () => {
      const r = addRefBtn.getBoundingClientRect();
      showContextMenu(r.left + r.width / 2, r.top, referenceMenuItems(p.id), { above: true, center: true });
    });
    docsCard.append(addRefBtn);
  }
  leftCol.append(docsCard);
  grid.append(leftCol);

  // --- Context column ---
  const ctxCol = el(`<div class="context-col"></div>`);
  ctxCol.append(renderContext(p));
  ctxCol.append(await renderMembers(p));
  grid.append(ctxCol);

  view.append(grid);
}

const ROLE_LABEL = { owner: "소유자", editor: "에디터", viewer: "뷰어" };

// 프로젝트 멤버 카드 (소유자는 초대·권한변경·제거 가능)
async function renderMembers(p) {
  const card = el(`<section class="card"></section>`);
  const head = el(`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px"></div>`);
  head.append(el(`<h2 class="section-title" style="margin:0"><span class="material-symbols-outlined">group</span>멤버</h2>`));
  card.append(head);
  let members = [];
  try { members = await api.listMembers(p.id); } catch (_) { members = []; }
  const owner = isOwner();
  if (owner) {
    const inviteBtn = el(`<button class="btn btn-sm"><span class="material-symbols-outlined">person_add</span>초대</button>`);
    inviteBtn.addEventListener("click", () => openInviteModal(p.id));
    head.append(inviteBtn);
  }
  const list = el(`<div class="member-list"></div>`);
  for (const m of members) {
    const isMe = currentUser && m.user_id === currentUser.id;
    const initial = esc((m.email[0] || "?").toUpperCase());
    const row = el(`<div class="member-row">
      <span class="member-avatar role-${m.role}">${initial}</span>
      <div class="member-info"><span class="member-email">${esc(m.email)}</span>${isMe ? `<span class="member-you">나</span>` : ""}</div>
    </div>`);
    const canManage = owner && m.role !== "owner";
    const pill = el(`<button class="role-pill role-${m.role}" ${canManage ? "" : "disabled"}>${ROLE_LABEL[m.role] || m.role}${canManage ? `<span class="material-symbols-outlined">unfold_more</span>` : ""}</button>`);
    if (canManage) {
      pill.addEventListener("click", () => {
        const r = pill.getBoundingClientRect();
        const items = [];
        if (m.role !== "editor") items.push({ label: "에디터로 변경", icon: "edit", onClick: () => _setMemberRole(p.id, m, "editor") });
        if (m.role !== "viewer") items.push({ label: "뷰어로 변경", icon: "visibility", onClick: () => _setMemberRole(p.id, m, "viewer") });
        items.push({ label: "멤버 제거", icon: "person_remove", danger: true, onClick: () => _removeMember(p.id, m) });
        showContextMenu(r.left, r.bottom + 4, items);
      });
    }
    row.append(pill);
    list.append(row);
  }
  card.append(list);
  return card;
}

async function _setMemberRole(pid, m, role) {
  try { await api.updateMemberRole(pid, m.user_id, role); toast(`${ROLE_LABEL[role]}로 변경됨`); render(); }
  catch (e) { toast(e.message); }
}

async function _removeMember(pid, m) {
  const ok = await confirmModal({ title: "멤버 제거", message: `${m.email} 님을 이 프로젝트에서 제거할까요?`, confirmText: "제거" });
  if (!ok) return;
  try { await api.removeMember(pid, m.user_id); toast("제거됨"); render(); }
  catch (e) { toast(e.message); }
}

function openInviteModal(projectId) {
  let role = "editor";
  const modal = el(`
    <div>
      <h3>멤버 초대</h3>
      <div class="hint" style="margin-bottom:18px">가입된 사용자의 이메일로 초대해요.</div>
      <div class="field"><label>이메일</label><input id="iv-email" type="email" placeholder="member@example.com"></div>
      <div class="field"><label>권한</label>
        <div class="role-toggle" id="iv-role">
          <button type="button" data-role="editor" class="active"><span class="rt-name">에디터</span><span class="rt-desc">편집 가능</span></button>
          <button type="button" data-role="viewer"><span class="rt-name">뷰어</span><span class="rt-desc">읽기 전용</span></button>
        </div>
      </div>
      <div class="auth-err" id="iv-err" hidden></div>
      <div class="modal-actions">
        <button class="btn btn-ghost" id="iv-cancel">취소</button>
        <button class="btn btn-primary" id="iv-add">초대</button>
      </div>
    </div>`);
  const toggle = modal.querySelector("#iv-role");
  toggle.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      role = b.dataset.role;
      toggle.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
    })
  );
  const err = modal.querySelector("#iv-err");
  modal.querySelector("#iv-cancel").addEventListener("click", closeModal);
  const addBtn = modal.querySelector("#iv-add");
  addBtn.addEventListener("click", async () => {
    const email = modal.querySelector("#iv-email").value.trim();
    if (!email) return;
    err.hidden = true;
    addBtn.disabled = true;
    addBtn.innerHTML = `<span class="spinner"></span>`;
    try { await api.addMember(projectId, email, role); closeModal(); toast("초대됨"); render(); }
    catch (e) { err.textContent = e.message; err.hidden = false; addBtn.disabled = false; addBtn.textContent = "초대"; }
  });
  openModal(modal);
  setTimeout(() => modal.querySelector("#iv-email").focus(), 50);
}

// --- 경량 Markdown 렌더러 (외부 라이브러리 없이, XSS 방지: 텍스트 먼저 이스케이프) ---
function mdToHtml(src) {
  const escHtml = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (raw) => {
    // 백틱 코드 스팬 기준으로 분리 → 코드 안에는 서식 미적용
    return escHtml(raw).split(/(`[^`]+`)/).map((seg) => {
      if (seg.length >= 2 && seg[0] === "`" && seg[seg.length - 1] === "`") return `<code>${seg.slice(1, -1)}</code>`;
      let t = seg;
      t = t.replace(/!?\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
      t = t.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, a, b) => `<span class="wikilink">${b || a}</span>`);
      t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      t = t.replace(/__([^_]+)__/g, "<strong>$1</strong>");
      t = t.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
      t = t.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?]|$)/g, "$1<em>$2</em>");
      t = t.replace(/~~([^~]+)~~/g, "<del>$1</del>");
      return t;
    }).join("");
  };

  let text = (src || "").replace(/\r\n/g, "\n");
  text = text.replace(/^---\n[\s\S]*?\n---\n?/, "");  // 옵시디언 YAML frontmatter 숨김
  const lines = text.split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      out.push(`<pre class="md-pre"><code>${escHtml(buf.join("\n"))}</code></pre>`);
      continue;
    }
    if (!line.trim()) { i++; continue; }
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { const lvl = h[1].length; out.push(`<h${lvl} class="md-h">${inline(h[2])}</h${lvl}>`); i++; continue; }
    if (/^\s*([-*_])[ \t]*(?:\1[ \t]*){2,}$/.test(line)) { out.push('<hr class="md-hr">'); i++; continue; }
    // 표 (GFM): 헤더 행 + |---|---| 구분선 + 데이터 행
    if (line.includes("|") && i + 1 < lines.length) {
      const cells = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
      const sep = cells(lines[i + 1]);
      if (sep.length >= 1 && sep.every((c) => /^:?-+:?$/.test(c))) {
        const headers = cells(line);
        const aligns = sep.map((c) => {
          const L = c.startsWith(":"), R = c.endsWith(":");
          return L && R ? "center" : R ? "right" : L ? "left" : "";
        });
        i += 2;
        const rows = [];
        while (i < lines.length && lines[i].includes("|") && lines[i].trim()) { rows.push(cells(lines[i])); i++; }
        const al = (idx) => (aligns[idx] ? ` style="text-align:${aligns[idx]}"` : "");
        let html = '<table class="md-table"><thead><tr>';
        headers.forEach((h, idx) => { html += `<th${al(idx)}>${inline(h)}</th>`; });
        html += "</tr></thead><tbody>";
        for (const row of rows) {
          html += "<tr>";
          headers.forEach((_, idx) => { html += `<td${al(idx)}>${inline(row[idx] || "")}</td>`; });
          html += "</tr>";
        }
        out.push(html + "</tbody></table>");
        continue;
      }
    }
    if (/^\s*>\s?/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^\s*>\s?/, "")); i++; }
      out.push(`<blockquote class="md-quote">${inline(buf.join(" "))}</blockquote>`);
      continue;
    }
    if (/^\s*([-*+]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const items = [];
      while (i < lines.length && /^\s*([-*+]|\d+\.)\s+/.test(lines[i])) {
        const content = lines[i].replace(/^\s*([-*+]|\d+\.)\s+/, "");
        const task = content.match(/^\[([ xX])\]\s+(.*)$/);
        if (task) {
          const checked = task[1].toLowerCase() === "x";
          items.push(`<li class="md-task"><input type="checkbox" disabled ${checked ? "checked" : ""}>${inline(task[2])}</li>`);
        } else {
          items.push(`<li>${inline(content)}</li>`);
        }
        i++;
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag} class="md-list">${items.join("")}</${tag}>`);
      continue;
    }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|\s*>|\s*([-*+]|\d+\.)\s)/.test(lines[i])) { buf.push(lines[i]); i++; }
    out.push(`<p class="md-p">${inline(buf.join("\n")).replace(/\n/g, "<br>")}</p>`);
  }
  return out.join("\n");
}

function mdBlock(text) {
  const div = el(`<div class="md-body"></div>`);
  div.innerHTML = mdToHtml(text);
  return div;
}

// 마크다운 라이브 에디터 (옵시디언식): 줄을 쓰고 Enter를 누르면 그 줄이 렌더링돼 적용된다.
// 렌더된 줄은 원본을 data-md에 보관 → 텍스트 유실 없음. getValue()로 원본 마크다운 반환.
function mdLiveEditor(initial = "", placeholder = "") {
  const root = el(`<div class="mde md-body" contenteditable="true" spellcheck="false"></div>`);
  root.dataset.ph = placeholder;

  const rawBlock = (text = "") => { const b = el(`<div class="mde-block mde-raw"><br></div>`); if (text) b.textContent = text; return b; };
  const renderedBlock = (md) => { const b = el(`<div class="mde-block mde-rendered"></div>`); b.dataset.md = md; b.innerHTML = mdToHtml(md) || "<br>"; return b; };

  const caretTo = (block, atStart = false) => {
    const r = document.createRange();
    r.selectNodeContents(block);
    r.collapse(atStart);
    const s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  };
  const blockOf = (node) => {
    while (node && node !== root && !(node.nodeType === 1 && node.classList && node.classList.contains("mde-block"))) node = node.parentNode;
    return (node && node.classList && node.classList.contains("mde-block")) ? node : null;
  };
  const curBlock = () => { const s = window.getSelection(); return s.rangeCount ? blockOf(s.getRangeAt(0).startContainer) : null; };

  const renderBlock = (block) => {
    const md = block.textContent;
    if (!md.trim()) return block;  // 빈 줄은 그대로
    const rb = renderedBlock(md);
    block.replaceWith(rb);
    return rb;
  };
  const editBlock = (block) => {
    const raw = rawBlock(block.dataset.md || "");
    block.replaceWith(raw);
    return raw;
  };
  const syncEmpty = () => root.classList.toggle("mde-empty", getValue().trim() === "");

  root.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const block = curBlock();
      if (!block) return;
      const done = block.classList.contains("mde-raw") ? renderBlock(block) : block;
      const nb = rawBlock("");
      done.after(nb);
      caretTo(nb);
      syncEmpty();
    }
  });
  // 렌더된 줄을 클릭하면 원본(raw)으로 열어 편집
  root.addEventListener("mousedown", (e) => {
    const rb = e.target.closest ? e.target.closest(".mde-rendered") : null;
    if (rb && root.contains(rb)) { e.preventDefault(); caretTo(editBlock(rb)); }
  });
  root.addEventListener("input", syncEmpty);
  root.addEventListener("paste", (e) => {
    e.preventDefault();
    const t = ((e.clipboardData || window.clipboardData).getData("text") || "").replace(/\r\n/g, "\n");
    // 여러 줄 붙여넣기: 첫 줄만 현재 줄에, 나머지는 렌더 줄로
    const parts = t.split("\n");
    document.execCommand("insertText", false, parts[0] || "");
    let cur = curBlock();
    for (let i = 1; i < parts.length; i++) {
      if (cur && cur.classList.contains("mde-raw")) cur = renderBlock(cur);
      const nb = parts[i].trim() ? renderedBlock(parts[i]) : rawBlock("");
      (cur || root).after ? cur.after(nb) : root.append(nb);
      cur = nb;
    }
    if (cur) { const tail = rawBlock(""); cur.after(tail); caretTo(tail); }
    syncEmpty();
  });

  function getValue() {
    return [...root.querySelectorAll(".mde-block")]
      .map((b) => b.classList.contains("mde-rendered") ? (b.dataset.md || "") : b.textContent)
      .join("\n").replace(/\s+$/, "");
  }

  // 초기화: 각 줄을 렌더 줄로, 끝에 편집용 빈 줄
  for (const line of String(initial || "").split("\n")) {
    if (line.trim()) root.append(renderedBlock(line));
  }
  root.append(rawBlock(""));
  syncEmpty();

  return { element: root, getValue, focus: () => { const last = root.lastElementChild; if (last) caretTo(last); } };
}

// 상세 내용 카드: 보기 ↔ 인라인 편집 토글 (모달 없이 화면에서 바로 수정)
function buildContentCard(s, isNote) {
  const left = el(`<section class="card"></section>`);
  const head = el(`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px"></div>`);
  head.append(el(`<h2 class="section-title" style="margin:0"><span class="material-symbols-outlined">${isNote ? "edit_note" : "graphic_eq"}</span>${isNote ? "메모 내용" : "음성 기록"}</h2>`));
  const editActions = el(`<div class="edit-actions"></div>`);
  const editBtn = el(`<button class="btn btn-sm"><span class="material-symbols-outlined">edit</span>편집</button>`);
  const cancelBtn = el(`<button class="btn btn-ghost btn-sm" hidden>취소</button>`);
  const saveBtn = el(`<button class="btn btn-primary btn-sm" hidden>저장</button>`);
  editActions.append(cancelBtn, saveBtn, editBtn);
  if (canEdit()) head.append(editActions);
  left.append(head);

  const bodyWrap = el(`<div></div>`);
  left.append(bodyWrap);
  renderContentView(bodyWrap, s.body);

  let ta = null;
  const showView = () => {
    editBtn.hidden = false; cancelBtn.hidden = true; saveBtn.hidden = true;
    renderContentView(bodyWrap, s.body);
  };
  editBtn.addEventListener("click", () => {
    editBtn.hidden = true; cancelBtn.hidden = false; saveBtn.hidden = false;
    bodyWrap.replaceChildren();
    ta = el(`<textarea class="inline-edit"></textarea>`);
    ta.value = s.body || "";
    bodyWrap.append(ta);
    const grow = () => { ta.style.height = "auto"; ta.style.height = ta.scrollHeight + "px"; };
    ta.addEventListener("input", grow);
    grow();
    ta.focus();
  });
  cancelBtn.addEventListener("click", showView);
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="spinner"></span>`;
    try { await api.updateSource(s.id, { body: ta.value }); toast("저장됨"); render(); }
    catch (e) { toast(e.message); saveBtn.disabled = false; saveBtn.textContent = "저장"; }
  });
  return left;
}

// 내용 표시: [mm:ss] 세그먼트가 있으면 음성 기록 형식, 아니면 일반 텍스트
function renderContentView(wrap, body) {
  wrap.replaceChildren();
  const text = body || "(내용 없음)";
  if (/^\[\d{1,2}:\d{2}\]/m.test(text)) {
    const segs = el(`<div class="transcript-segments"></div>`);
    for (const line of text.split("\n")) {
      const m = line.match(/^\[(\d{1,2}:\d{2})\]\s*(.*)$/);
      if (m) segs.append(el(`<div class="tseg"><span class="tts">${m[1]}</span><span class="ttx">${esc(m[2])}</span></div>`));
      else if (line.trim()) segs.append(el(`<div class="tseg"><span class="tts"></span><span class="ttx">${esc(line)}</span></div>`));
    }
    wrap.append(segs);
  } else if (body && body.trim()) {
    wrap.append(mdBlock(body));  // 메모·텍스트는 Markdown 렌더링
  } else {
    wrap.append(el(`<div class="transcript" style="color:var(--on-surface-variant)">(내용 없음)</div>`));
  }
}

async function openMoveMeetingModal(currentPid, sourceId) {
  const projects = await api.listProjects();
  const modal = el(`
    <div>
      <h3>프로젝트 이동</h3>
      <div class="hint" style="margin-bottom:14px">이 회의와 관련 결정·태그가 선택한 프로젝트로 옮겨집니다.</div>
      <div class="proj-list" id="mv-list"></div>
      <div class="modal-actions"><button class="btn btn-ghost" id="mv-cancel">취소</button></div>
    </div>`);
  const list = modal.querySelector("#mv-list");
  for (const pr of projects) {
    const isCurrent = pr.id === currentPid;
    const row = el(`<button class="proj-option ${isCurrent ? "current" : ""}"><span class="material-symbols-outlined">${isCurrent ? "check_circle" : "folder"}</span>${esc(pr.name)}</button>`);
    if (!isCurrent) {
      row.addEventListener("click", async () => {
        try { await api.updateSource(sourceId, { project_id: pr.id }); closeModal(); toast("이동됨"); location.hash = `#/projects/${pr.id}/sources/${sourceId}`; }
        catch (e) { toast(e.message); }
      });
    }
    list.append(row);
  }
  modal.querySelector("#mv-cancel").addEventListener("click", closeModal);
  openModal(modal);
}

function renderActionItem(a) {
  // 편집·삭제 후 전체 re-render 대신 이 행만 갱신 → 액션아이템 섹션이 닫히지 않음
  const row = el(`<div class="action longpress" title="꾹 눌러 편집"></div>`);
  const editable = canEdit();
  const paint = () => {
    row.classList.toggle("done", !!a.done);
    row.innerHTML = `<input type="checkbox" ${a.done ? "checked" : ""} ${editable ? "" : "disabled"} id="da${a.id}"><label for="da${a.id}">${esc(a.content)}</label>${a.due_date ? `<span class="ai-date"><span class="material-symbols-outlined">event</span>${a.due_date.slice(5)}</span>` : ""}`;
    row.querySelector("input").addEventListener("change", async (e) => {
      try { await api.toggleAction(a.id, e.target.checked); a.done = e.target.checked; row.classList.toggle("done", a.done); }
      catch (err) { toast(err.message); e.target.checked = !e.target.checked; }
    });
  };
  paint();
  if (!editable) { row.title = ""; return row; }
  attachLongPress(row, () => {
    const items = [
      { label: "수정", icon: "edit", onClick: async () => {
          const v = await promptModal({ title: "액션아이템 수정", value: a.content });
          if (v === null) return;
          try { await api.updateAction(a.id, { content: v }); a.content = v; paint(); } catch (e) { toast(e.message); }
        } },
      { label: a.due_date ? "마감일 변경" : "마감일 지정", icon: "event", onClick: async () => {
          const d = await datePickerModal(a.due_date);
          if (d === null) return;
          try { await api.updateAction(a.id, { due_date: d }); a.due_date = d; paint(); } catch (e) { toast(e.message); }
        } },
    ];
    if (a.due_date) items.push({ label: "마감일 제거", icon: "event_busy", onClick: async () => { try { await api.updateAction(a.id, { due_date: null }); a.due_date = null; paint(); } catch (e) { toast(e.message); } } });
    items.push({ label: "삭제", icon: "delete", danger: true, onClick: async () => {
        try {
          await api.deleteAction(a.id);
          const sub = row.closest(".ai-sub");
          row.remove();
          if (sub) { const c = sub.querySelector(".ai-count"); if (c) c.textContent = sub.querySelectorAll(".action").length; }
        } catch (e) { toast(e.message); }
      } });
    return items;
  });
  return row;
}

// 그래놀라식 "내 메모": 음성 기록 옆에 사용자가 직접 남기는 메모 (Source.note 재사용)
function buildNoteCard(s) {
  const card = el(`<section class="card note-card"></section>`);
  const head = el(`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px"></div>`);
  head.append(el(`<h2 class="section-title" style="margin:0"><span class="material-symbols-outlined">stylus_note</span>내 메모</h2>`));
  const editActions = el(`<div class="edit-actions"></div>`);
  const editBtn = el(`<button class="btn btn-sm"><span class="material-symbols-outlined">edit</span>편집</button>`);
  const cancelBtn = el(`<button class="btn btn-ghost btn-sm" hidden>취소</button>`);
  const saveBtn = el(`<button class="btn btn-primary btn-sm" hidden>저장</button>`);
  editActions.append(cancelBtn, saveBtn, editBtn);
  if (canEdit()) head.append(editActions);
  card.append(head);
  const wrap = el(`<div></div>`);
  card.append(wrap);

  const renderView = () => {
    editBtn.hidden = false; cancelBtn.hidden = true; saveBtn.hidden = true;
    wrap.replaceChildren();
    if (s.note && s.note.trim()) {
      wrap.append(mdBlock(s.note));  // 내 메모도 Markdown 렌더링
    } else if (canEdit()) {
      editBtn.hidden = true;
      const empty = el(`<button class="note-empty"><span class="material-symbols-outlined">add</span>회의 중 떠오른 생각·메모를 남겨보세요</button>`);
      empty.addEventListener("click", enterEdit);
      wrap.append(empty);
    } else {
      editBtn.hidden = true;
      wrap.append(el(`<p class="summary-empty">메모가 없습니다.</p>`));
    }
  };
  let editor = null;
  const enterEdit = () => {
    editBtn.hidden = true; cancelBtn.hidden = false; saveBtn.hidden = false;
    wrap.replaceChildren();
    editor = mdLiveEditor(s.note || "", "회의 중 떠오른 생각을 자유롭게 남겨보세요…");
    editor.element.classList.add("note-edit-editor");
    wrap.append(editor.element);
    editor.focus();
  };
  cancelBtn.addEventListener("click", renderView);
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="spinner"></span>`;
    const v = editor ? editor.getValue() : "";
    try { await api.updateSource(s.id, { note: v }); s.note = v; toast("저장됨"); renderView(); }
    catch (e) { toast(e.message); saveBtn.disabled = false; saveBtn.textContent = "저장"; }
  });
  editBtn.addEventListener("click", enterEdit);
  renderView();
  return card;
}

// 회의 참석자 표시 + 편집
function buildAttendeesRow(s) {
  const row = el(`<div class="attendees-row"></div>`);
  const head = el(`<div class="attendees-head"></div>`);
  head.append(el(`<span class="ctx-label"><span class="material-symbols-outlined" style="font-size:16px;vertical-align:-3px">group</span> 참석자</span>`));
  if (canEdit()) {
    const editBtn = el(`<button class="icon-btn subtle" title="참석자 편집"><span class="material-symbols-outlined">edit</span></button>`);
    editBtn.addEventListener("click", () => openAttendeesModal(s));
    head.append(editBtn);
  }
  row.append(head);
  const chips = el(`<div class="chips"></div>`);
  if (s.attendees && s.attendees.length) {
    for (const a of s.attendees) chips.append(el(`<span class="chip person"><span class="material-symbols-outlined">person</span>${esc(a)}</span>`));
  } else if (canEdit()) {
    const add = el(`<button class="attendees-add">＋ 참석자 추가</button>`);
    add.addEventListener("click", () => openAttendeesModal(s));
    chips.append(add);
  } else {
    chips.append(el(`<span class="summary-empty">참석자 없음</span>`));
  }
  row.append(chips);
  return row;
}

function openAttendeesModal(s) {
  const modal = el(`
    <div>
      <h3>참석자 편집</h3>
      <div class="field"><div id="at-input"></div></div>
      <div class="modal-actions">
        <button class="btn btn-ghost" id="at-cancel">취소</button>
        <button class="btn btn-primary" id="at-save">저장</button>
      </div>
    </div>`);
  const ctl = chipInput(s.attendees || [], "이름 입력 후 Enter");
  modal.querySelector("#at-input").append(ctl.element);
  modal.querySelector("#at-cancel").addEventListener("click", closeModal);
  const save = modal.querySelector("#at-save");
  save.addEventListener("click", async () => {
    save.disabled = true;
    save.innerHTML = `<span class="spinner"></span>`;
    try { await api.updateSource(s.id, { attendees: ctl.get() }); closeModal(); toast("저장됨"); render(); }
    catch (e) { toast(e.message); save.disabled = false; save.textContent = "저장"; }
  });
  openModal(modal);
}

// --- Meeting detail (전사 상세) --------------------------------------------
async function renderSourceDetail(view, pid, sid) {
  const p = await api.getProject(pid);
  viewRole = p.role || null;  // 권한 게이팅 기준
  const s = p.sources.find((x) => x.id === sid);

  if (!s) {
    view.innerHTML = `<div class="empty"><span class="material-symbols-outlined">error</span>회의를 찾을 수 없어요.</div>`;
    return;
  }
  view.replaceChildren();

  view.append(el(`<a class="back-link" href="#/projects/${pid}"><span class="material-symbols-outlined">arrow_back</span>${esc(p.name)}</a>`));

  const originLabel = s.origin === "audio" ? "🎙 음성" : s.origin === "pasted" ? "📝 메모" : "";
  const titleRow = el(`<div class="detail-title-row"></div>`);
  const titleEl = el(`<h1 class="page-title ${canEdit() ? "longpress" : ""}" style="margin:0;flex:1" ${canEdit() ? 'title="꾹 눌러 제목 편집"' : ""}>${esc(s.title)}</h1>`);
  if (canEdit()) attachLongPress(titleEl, () => [
    { label: "제목 수정", icon: "edit", onClick: () => editText("제목", s.title, (v) => api.updateSource(s.id, { title: v })) },
  ]);
  titleRow.append(titleEl);
  if (canEdit()) {
    const delBtn = el(`<button class="icon-btn detail-delete" title="삭제"><span class="material-symbols-outlined">delete</span></button>`);
    delBtn.addEventListener("click", async () => {
      const ok = await confirmModal({
        title: `${s.type === "NOTE" ? "메모" : "회의"} 삭제`,
        message: `"${s.title}"을(를) 삭제합니다. 관련 액션아이템·핀도 함께 삭제되며 되돌릴 수 없어요.`,
        confirmText: "삭제",
      });
      if (!ok) return;
      try { await api.deleteSource(s.id); toast("삭제됨"); location.hash = `#/projects/${pid}`; }
      catch (e) { toast(e.message); }
    });
    titleRow.append(delBtn);
  }
  view.append(titleRow);
  view.append(el(`<p class="page-sub" style="margin-bottom:14px">${fmtDate(s.created_at)}${originLabel ? " · " + originLabel : ""}</p>`));

  // 연결된 프로젝트 (편집 가능자만 이동)
  const projChip = el(`<button class="proj-chip"${canEdit() ? "" : " disabled"}><span class="material-symbols-outlined">folder</span>${esc(p.name)}${canEdit() ? '<span class="material-symbols-outlined">expand_more</span>' : ""}</button>`);
  if (canEdit()) projChip.addEventListener("click", () => openMoveMeetingModal(p.id, s.id));
  view.append(projChip);

  // 참석자 (회의)
  if (s.type === "MEETING") view.append(buildAttendeesRow(s));

  // 주요 키워드
  if (s.keywords && s.keywords.length) {
    const kwrow = el(`<div style="margin-bottom:24px"></div>`);
    kwrow.append(el(`<div class="ctx-label" style="margin-bottom:8px">주요 키워드</div>`));
    const chips = el(`<div class="chips"></div>`);
    for (const k of s.keywords) chips.append(el(`<span class="chip">${esc(k)}</span>`));
    kwrow.append(chips);
    view.append(kwrow);
  }

  const isNote = s.type === "NOTE";

  const grid = el(`<div class="meeting-detail-grid"></div>`);

  // 좌: [내 메모(회의만)] → [음성 기록/메모 내용] 세로로 쌓기
  const leftCol = el(`<div class="content-col"></div>`);
  if (!isNote) leftCol.append(buildNoteCard(s));
  leftCol.append(buildContentCard(s, isNote));
  grid.append(leftCol);

  // 우: AI 요약 + 액션아이템 (내 메모와 같은 수평선에서 시작)
  const right = el(`<div class="summary-col"></div>`);
  const sumCard = el(`<section class="card"><h2 class="section-title"><span class="material-symbols-outlined">auto_awesome</span>요약</h2></section>`);
  sumCard.append(
    s.summary
      ? el(`<p class="summary-text">${esc(s.summary)}</p>`)
      : el(`<p class="summary-empty">요약이 없습니다.</p>`)
  );
  const aiCard = el(`<div class="subcard"><div class="label">Action Items</div></div>`);
  for (const a of s.action_items || []) aiCard.append(renderActionItem(a));
  if (canEdit()) {
    const addAi = el(`<button class="add-line"><span class="material-symbols-outlined">add</span>액션아이템 추가</button>`);
    addAi.addEventListener("click", () => editText("액션아이템 추가", "", (v) => api.createActionItem(s.id, { content: v })));
    aiCard.append(addAi);
  }
  sumCard.append(aiCard);
  right.append(sumCard);
  grid.append(right);

  view.append(grid);
}

const SOURCE_META = {
  NOTE: { cls: "note", icon: "edit_note" },
  MEETING: { cls: "meeting", icon: "forum" },
  DOCUMENT: { cls: "document", icon: "description" },
};

// 문서 = 파일 링크 카드 (관련 문서 모음에서 사용)
function renderDocCard(d) {
  const url = (d.body || "").trim();
  const hasLink = !!url;
  const isDrive = /(?:drive|docs)\.google\.com/i.test(url);
  const icon = !hasLink ? "description" : "link";
  const iconHtml = isDrive ? driveLogo(22) : `<span class="material-symbols-outlined doc-card-icon">${icon}</span>`;
  const sourceLabel = !hasLink ? "링크 없음" : isDrive ? "Google Drive · 열기" : "링크 · 열기";
  const noteHtml = d.note && d.note.trim() ? `<div class="doc-card-note">${esc(d.note)}</div>` : "";
  const inner =
    iconHtml +
    `<div class="doc-card-body"><div class="doc-card-name">${esc(d.title)}</div>` +
    `<div class="doc-card-sub">${sourceLabel} · ${fmtDate(d.created_at)}</div>${noteHtml}</div>` +
    (hasLink ? `<span class="material-symbols-outlined doc-card-open">open_in_new</span>` : "");
  const lp = canEdit() ? " longpress" : "";
  const card = hasLink
    ? el(`<a class="doc-card${lp}" href="${esc(d.body)}" target="_blank" rel="noopener">${inner}</a>`)
    : el(`<div class="doc-card no-link${lp}">${inner}</div>`);
  if (canEdit()) attachLongPress(card, () => {
    const items = [
      { label: d.note ? "메모 수정" : "메모 추가", icon: "sticky_note_2", onClick: () => editText("문서 메모", d.note || "", (v) => api.updateSource(d.id, { note: v }), { multiline: true, placeholder: "이 문서가 어떤 문서인지" }) },
    ];
    if (d.note) items.push({ label: "메모 지우기", icon: "clear", onClick: async () => { try { await api.updateSource(d.id, { note: "" }); render(); } catch (e) { toast(e.message); } } });
    items.push({ label: "삭제", icon: "delete", danger: true, onClick: async () => { try { await api.deleteSource(d.id); render(); } catch (e) { toast(e.message); } } });
    return items;
  });
  return card;
}

function renderSource(s, projectId) {
  const meta = SOURCE_META[s.type] || SOURCE_META.NOTE;
  const item = el(`<div class="tl-item"><div class="tl-icon ${meta.cls}"><span class="material-symbols-outlined">${meta.icon}</span></div></div>`);

  // 메모 / 회의
  item.append(el(`<div class="tl-head"><h4>${esc(s.title)}</h4><span class="tl-date">${fmtDate(s.created_at)}</span></div>`));
  item.classList.add("clickable");
  item.title = "클릭해 내용 보기";
  item.addEventListener("click", (e) => {
    if (e.target.closest(".action, input, label, button, a")) return;
    location.hash = `#/projects/${projectId}/sources/${s.id}`;
  });
  if (s.summary) item.append(el(`<p class="tl-summary">${esc(s.summary)}</p>`));
  if (s.action_items && s.action_items.length) {
    const sub = el(`<div class="subcard ai-sub collapsed"></div>`);
    const toggle = el(`<button class="subcard-toggle" type="button"><span class="material-symbols-outlined chev">chevron_right</span><span class="label">Action Items</span><span class="ai-count">${s.action_items.length}</span></button>`);
    const list = el(`<div class="ai-list"></div>`);
    for (const a of s.action_items) list.append(renderActionItem(a));
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const collapsed = sub.classList.toggle("collapsed");
      toggle.querySelector(".chev").textContent = collapsed ? "chevron_right" : "expand_more";
    });
    sub.append(toggle, list);
    item.append(sub);
  }
  return item;
}

function renderContext(p) {
  const editable = canEdit();
  const card = el(`<section class="card"><h2 class="section-title"><span class="material-symbols-outlined">bubble_chart</span>Context</h2></section>`);

  // Objective (편집 가능자만 꾹 눌러 편집)
  const objBlock = el(`<div class="ctx-block"><div class="ctx-label">Objective</div></div>`);
  const objText = el(`<p class="objective ${editable ? "longpress" : ""}" ${editable ? 'title="꾹 눌러 편집"' : ""}>${esc(p.objective || "")}</p>`);
  if (editable) attachLongPress(objText, () => [
    { label: "목표 수정", icon: "edit", onClick: () => editText("프로젝트 목표", p.objective, (v) => api.updateProject(p.id, { objective: v }), { multiline: true }) },
  ]);
  objBlock.append(objText);
  card.append(objBlock);

  // Key decisions — 회의에서 자동 누적 + 직접 추가, 단순 목록
  const decisions = p.context_items.filter((c) => c.kind === "DECISION");
  const decBlock = el(`<div class="ctx-block"><div class="ctx-label">Key Decisions</div></div>`);
  for (const c of decisions) decBlock.append(renderDecision(p.id, c, editable));
  if (editable) {
    const addDec = el(`<button class="add-line"><span class="material-symbols-outlined">add</span>결정 추가</button>`);
    addDec.addEventListener("click", () => editText("결정 추가", "", (v) => api.createContext(p.id, { kind: "DECISION", content: v }), { multiline: true, placeholder: "이 프로젝트의 핵심 결정" }));
    decBlock.append(addDec);
  }
  card.append(decBlock);

  // Project tags — 사용자가 직접 추가/삭제 (ContextItem kind=TAG)
  const tags = p.context_items.filter((c) => c.kind === "TAG");
  const tagBlock = el(`<div class="ctx-block"><div class="ctx-label">Project Tags</div></div>`);
  const chips = el(`<div class="chips"></div>`);
  for (const t of tags) {
    const chip = el(`<span class="chip ${editable ? "longpress" : ""}" ${editable ? 'title="꾹 눌러 편집"' : ""}>${esc(t.content)}</span>`);
    if (editable) attachLongPress(chip, () => [
      { label: "수정", icon: "edit", onClick: () => editText("태그", t.content, (v) => api.updateContext(t.id, { content: v })) },
      { label: "삭제", icon: "delete", danger: true, onClick: async () => { try { await api.deleteContext(t.id); render(); } catch (e) { toast(e.message); } } },
    ]);
    chips.append(chip);
  }
  if (editable) {
    const addChip = el(`<button class="chip chip-add" title="태그 추가"><span class="material-symbols-outlined" style="font-size:16px">add</span></button>`);
    addChip.addEventListener("click", () => editText("태그 추가", "", (v) => api.createContext(p.id, { kind: "TAG", content: v }), { placeholder: "예: B2G" }));
    chips.append(addChip);
  }
  tagBlock.append(chips);
  card.append(tagBlock);

  return card;
}

function renderDecision(projectId, c, editable = true) {
  const row = el(`<div class="decision ${editable ? "longpress" : ""}" ${editable ? 'title="꾹 눌러 편집"' : ""}><span class="material-symbols-outlined">check_circle</span></div>`);
  row.append(el(`<div>${esc(c.content)}</div>`));
  if (editable) attachLongPress(row, () => [
    { label: "수정", icon: "edit", onClick: () => editText("결정 수정", c.content, (v) => api.updateContext(c.id, { content: v }), { multiline: true }) },
    { label: "삭제", icon: "delete", danger: true, onClick: async () => { try { await api.deleteContext(c.id); render(); } catch (e) { toast(e.message); } } },
  ]);
  return row;
}

// --- Add-source actions ----------------------------------------------------
function renderAddBar(projectId) {
  const bar = el(`<div class="add-bar"></div>`);
  const pasteBtn = el(`<button class="btn btn-secondary"><span class="material-symbols-outlined">content_paste</span>메모 붙여넣기</button>`);
  const audioBtn = el(`<button class="btn"><span class="material-symbols-outlined">mic</span>음성 업로드</button>`);
  pasteBtn.addEventListener("click", () => openPasteModal(projectId));
  audioBtn.addEventListener("click", () => openAudioModal(projectId));
  bar.append(pasteBtn, audioBtn);
  return bar;
}

function openPasteModal(projectId) {
  const modal = el(`
    <div>
      <h3>메모 추가하기</h3>
      <div class="field" id="pm-field"></div>
      <div class="modal-actions">
        <button class="btn btn-ghost" id="pm-cancel">취소</button>
        <button class="btn btn-primary" id="pm-save">메모 추가</button>
      </div>
    </div>`);
  const editor = mdLiveEditor("", "메모를 입력하세요. 제목·요약·할 일은 AI가 정리해요.");
  editor.element.classList.add("paste-editor");
  modal.querySelector("#pm-field").append(editor.element);
  modal.querySelector("#pm-cancel").addEventListener("click", closeModal);
  const saveBtn = modal.querySelector("#pm-save");
  saveBtn.addEventListener("click", async () => {
    const text = editor.getValue().trim();
    if (!text) { toast("내용을 입력하세요"); return; }
    saveBtn.innerHTML = `<span class="spinner"></span> 분석 중...`;
    saveBtn.disabled = true;
    try { await api.pasteNote(projectId, { text }); closeModal(); toast("메모 추가됨"); render(); }
    catch (e) { toast(e.message); saveBtn.innerHTML = "메모 추가"; saveBtn.disabled = false; }
  });
  openModal(modal);
  setTimeout(() => editor.focus(), 50);
}

function driveIcon(mime) {
  if (!mime) return "draft";
  if (mime.includes("spreadsheet") || mime.includes("excel")) return "grid_on";
  if (mime.includes("presentation") || mime.includes("powerpoint")) return "slideshow";
  if (mime.includes("document") || mime.includes("word")) return "description";
  if (mime.includes("pdf")) return "picture_as_pdf";
  if (mime.includes("folder")) return "folder";
  if (mime.includes("image")) return "image";
  return "draft";
}

async function openDriveSearchModal(projectId, initialQuery = "") {
  const st = await api.driveStatus();
  if (!st.connected) {
    toast("설정에서 Google Drive를 먼저 연결하세요");
    location.hash = "#/settings";
    return;
  }
  const modal = el(`
    <div>
      <h3 style="display:flex;align-items:center;gap:8px">${driveLogo(20)} Drive에서 문서 검색</h3>
      <div class="drive-search-box">
        <span class="material-symbols-outlined" id="ds-icon">search</span>
        <input id="ds-q" placeholder="파일명 또는 내용으로 검색">
      </div>
      <div id="ds-suggest" class="ds-suggest"></div>
      <div id="ds-results" class="drive-results"></div>
      <div class="modal-actions">
        <button class="btn btn-ghost" id="ds-close">닫기</button>
        <button class="btn btn-primary" id="ds-add" hidden>추가</button>
      </div>
    </div>`);
  const results = modal.querySelector("#ds-results");
  const addBtn = modal.querySelector("#ds-add");
  const input = modal.querySelector("#ds-q");
  let files = [];
  const proj = await api.getProject(projectId);
  const existingUrls = new Set(
    proj.sources.filter((s) => s.type === "DOCUMENT" && s.body).map((s) => s.body)
  );
  const projectTags = proj.context_items.filter((c) => c.kind === "TAG").map((c) => c.content);

  const emptyHint = () => {
    results.innerHTML = `<div class="drive-empty"><span class="material-symbols-outlined">search</span><p>검색어를 입력해 Drive에서 문서를 찾으세요</p></div>`;
  };
  const syncAdd = () => {
    const n = results.querySelectorAll("input:checked").length;
    addBtn.hidden = files.length === 0;
    addBtn.textContent = n ? `추가 (${n})` : "추가";
    addBtn.disabled = n === 0;
  };

  const renderResults = (headerText) => {
    results.replaceChildren();
    if (headerText) results.append(el(`<div class="ds-results-head">${esc(headerText)}</div>`));
    files.forEach((f, i) => {
      const already = existingUrls.has(f.webViewLink);
      const meta = already ? "이미 추가됨" : fmtDate(f.modifiedTime);
      const row = el(`<label class="drive-row ${already ? "added" : ""}"><input type="checkbox" data-i="${i}" ${already ? "disabled" : ""}><span class="material-symbols-outlined drive-file-icon">${driveIcon(f.mimeType)}</span><div class="drive-info"><div class="drive-name">${esc(f.name)}</div><div class="drive-meta">${meta}</div></div></label>`);
      if (!already) row.querySelector("input").addEventListener("change", syncAdd);
      results.append(row);
    });
    syncAdd();
  };

  const doSearch = async () => {
    const q = input.value.trim();
    if (!q) { files = []; emptyHint(); syncAdd(); return; }
    addBtn.hidden = true;
    results.innerHTML = `<div class="loading"><span class="spinner"></span> 검색 중...</div>`;
    try {
      files = (await api.driveSearch(q)).files;
      if (!files.length) {
        results.innerHTML = `<div class="drive-empty"><span class="material-symbols-outlined">search_off</span><p>"${esc(q)}" 결과가 없어요</p></div>`;
        syncAdd();
        return;
      }
      renderResults();
    } catch (e) {
      results.innerHTML = `<div class="drive-empty"><span class="material-symbols-outlined">error</span><p>${esc(e.message)}</p></div>`;
    }
  };

  const loadRecommend = async () => {
    addBtn.hidden = true;
    results.innerHTML = `<div class="loading"><span class="spinner"></span> 추천 불러오는 중...</div>`;
    try {
      files = (await api.driveRecommend(projectId)).files;
      if (!files.length) { emptyHint(); syncAdd(); return; }
      renderResults("프로젝트 태그 기반 추천");
    } catch (e) { emptyHint(); }
  };

  // 추천 검색어 칩 (프로젝트 태그)
  if (projectTags.length) {
    const sug = modal.querySelector("#ds-suggest");
    sug.append(el(`<span class="ds-suggest-label">추천 검색어</span>`));
    projectTags.slice(0, 8).forEach((tag) => {
      const chip = el(`<button class="chip ds-chip">${esc(tag)}</button>`);
      chip.addEventListener("click", () => { input.value = tag; doSearch(); });
      sug.append(chip);
    });
  }

  addBtn.addEventListener("click", async () => {
    const picked = [...results.querySelectorAll("input:checked")].map((c) => files[Number(c.dataset.i)]);
    if (!picked.length) return;
    addBtn.disabled = true;
    addBtn.innerHTML = `<span class="spinner"></span> 추가 중...`;
    try {
      await Promise.all(picked.map((f) => api.createDocument(projectId, { title: f.name, url: f.webViewLink })));
      closeModal();
      toast(`${picked.length}개 문서 추가됨`);
      render();
    } catch (e) { toast(e.message); addBtn.disabled = false; addBtn.textContent = "추가"; }
  });

  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doSearch(); } });
  modal.querySelector("#ds-icon").addEventListener("click", doSearch);
  modal.querySelector("#ds-close").addEventListener("click", () => { closeModal(); render(); });
  openModal(modal);
  if (initialQuery) { input.value = initialQuery; doSearch(); }
  else if (projectTags.length) { loadRecommend(); }
  else { emptyHint(); setTimeout(() => input.focus(), 50); }
}

async function openObsidianSearchModal(projectId) {
  const st = await api.obsidianStatus();
  if (!st.configured) {
    toast("설정에서 옵시디언 볼트를 연결하세요");
    location.hash = "#/settings";
    return;
  }
  const modal = el(`
    <div>
      <h3>옵시디언에서 검색</h3>
      <div class="drive-search-box">
        <span class="material-symbols-outlined" id="ob-icon">search</span>
        <input id="ob-q" placeholder="노트 이름 또는 내용으로 검색">
      </div>
      <div id="ob-results" class="drive-results"></div>
      <div class="modal-actions">
        <button class="btn btn-ghost" id="ob-close">닫기</button>
        <button class="btn btn-primary" id="ob-add" hidden>메모로 추가</button>
      </div>
    </div>`);
  const results = modal.querySelector("#ob-results");
  const addBtn = modal.querySelector("#ob-add");
  const input = modal.querySelector("#ob-q");
  let notes = [];

  const syncAdd = () => {
    const n = results.querySelectorAll("input:checked").length;
    addBtn.hidden = notes.length === 0;
    addBtn.textContent = n ? `메모로 추가 (${n})` : "메모로 추가";
    addBtn.disabled = n === 0;
  };
  const renderList = (list, headerText) => {
    notes = list;
    results.replaceChildren();
    if (headerText) results.append(el(`<div class="obs-list-label">${esc(headerText)}</div>`));
    list.forEach((nt, i) => {
      const row = el(`<label class="drive-row obs-row"><input type="checkbox" data-i="${i}"><span class="material-symbols-outlined drive-file-icon">description</span><div class="drive-info"><div class="drive-name">${esc(nt.name)}</div><div class="obs-excerpt">${esc(nt.excerpt)}</div></div></label>`);
      row.querySelector("input").addEventListener("change", syncAdd);
      results.append(row);
    });
    syncAdd();
  };
  const showRecent = async () => {
    addBtn.hidden = true;
    results.innerHTML = `<div class="loading"><span class="spinner"></span> 최근 노트 불러오는 중...</div>`;
    try {
      const list = (await api.obsidianRecent()).notes;
      if (!list.length) { notes = []; results.innerHTML = `<div class="drive-empty"><span class="material-symbols-outlined">description</span><p>볼트에 노트가 없어요</p></div>`; syncAdd(); return; }
      renderList(list, "최근 수정한 노트 · 검색어를 입력해 찾을 수도 있어요");
    } catch (e) { results.innerHTML = `<div class="drive-empty"><span class="material-symbols-outlined">error</span><p>${esc(e.message)}</p></div>`; }
  };
  const doSearch = async () => {
    const q = input.value.trim();
    if (!q) { showRecent(); return; }
    addBtn.hidden = true;
    results.innerHTML = `<div class="loading"><span class="spinner"></span> 검색 중...</div>`;
    try {
      const found = (await api.obsidianSearch(q)).notes;
      if (!found.length) { notes = []; results.innerHTML = `<div class="drive-empty"><span class="material-symbols-outlined">search_off</span><p>"${esc(q)}" 결과가 없어요</p></div>`; syncAdd(); return; }
      renderList(found, null);
    } catch (e) { results.innerHTML = `<div class="drive-empty"><span class="material-symbols-outlined">error</span><p>${esc(e.message)}</p></div>`; }
  };
  addBtn.addEventListener("click", async () => {
    const picked = [...results.querySelectorAll("input:checked")].map((c) => notes[Number(c.dataset.i)]);
    if (!picked.length) return;
    addBtn.disabled = true;
    addBtn.innerHTML = `<span class="spinner"></span> 추가·분석 중...`;
    try {
      for (const nt of picked) await api.addObsidianNote(projectId, nt.path);
      closeModal();
      toast(`${picked.length}개 메모 추가됨`);
      render();
    } catch (e) { toast(e.message); addBtn.disabled = false; addBtn.textContent = "메모로 추가"; }
  });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doSearch(); } });
  input.addEventListener("input", () => { if (!input.value.trim()) showRecent(); });
  modal.querySelector("#ob-icon").addEventListener("click", doSearch);
  modal.querySelector("#ob-close").addEventListener("click", closeModal);
  openModal(modal);
  showRecent();
  setTimeout(() => input.focus(), 50);
}

function openLinkModal(projectId) {
  const modal = el(`
    <div>
      <h3>링크 추가</h3>
      <div class="field"><label>링크 (URL)</label><input id="lk-url" placeholder="https://... (노션·웹페이지·문서 등)"></div>
      <div class="field"><label>이름 (선택)</label><input id="lk-title" placeholder="비워두면 페이지 제목을 자동으로 가져와요">
        <div class="hint">웹페이지·문서 링크를 프로젝트에 참조로 남깁니다.</div></div>
      <div class="modal-actions">
        <button class="btn btn-ghost" id="lk-cancel">취소</button>
        <button class="btn btn-primary" id="lk-save">추가</button>
      </div>
    </div>`);
  modal.querySelector("#lk-cancel").addEventListener("click", closeModal);
  const saveBtn = modal.querySelector("#lk-save");
  saveBtn.addEventListener("click", async () => {
    const url = modal.querySelector("#lk-url").value.trim();
    if (!url) { toast("링크를 입력하세요"); return; }
    const title = modal.querySelector("#lk-title").value.trim();
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="spinner"></span>`;
    // 이름을 비우면 title 미전송 → 서버가 페이지 제목을 자동으로 가져옴
    try { await api.createDocument(projectId, { url, title: title || undefined }); closeModal(); toast("링크 추가됨"); render(); }
    catch (e) { toast(e.message); saveBtn.disabled = false; saveBtn.textContent = "추가"; }
  });
  openModal(modal);
  setTimeout(() => modal.querySelector("#lk-url").focus(), 50);
}

function openAudioModal(projectId) {
  const modal = el(`
    <div>
      <h3>음성 업로드 → 회의</h3>
      <div class="field"><label>제목 (선택)</label><input id="am-title" placeholder="비워두면 파일명으로"></div>
      <div class="field"><label>음성 파일</label><input id="am-file" type="file" accept="audio/*">
        <div class="hint">Whisper로 전사 후 자동 추출됩니다. 긴 녹음은 자동으로 조각내 처리해요(최대 300MB).</div></div>
      <div class="field"><label>참석자 (선택)</label><div id="am-att"></div></div>
      <div class="modal-actions">
        <button class="btn btn-ghost" id="am-cancel">취소</button>
        <button class="btn btn-primary" id="am-save">업로드 & 전사</button>
      </div>
    </div>`);
  const attCtl = chipInput([], "이름 입력 후 Enter");
  modal.querySelector("#am-att").append(attCtl.element);
  modal.querySelector("#am-cancel").addEventListener("click", closeModal);
  const saveBtn = modal.querySelector("#am-save");
  saveBtn.addEventListener("click", async () => {
    const file = modal.querySelector("#am-file").files[0];
    const title = modal.querySelector("#am-title").value.trim();
    if (!file) { toast("음성 파일을 선택하세요"); return; }
    saveBtn.innerHTML = `<span class="spinner"></span> 전사 중...`;
    saveBtn.disabled = true;
    try { const src = await api.audioMeeting(projectId, file, title, attCtl.get()); closeModal(); toast("회의 추가됨"); location.hash = `#/projects/${projectId}/sources/${src.id}`; }
    catch (e) { toast(e.message); saveBtn.innerHTML = "업로드 & 전사"; saveBtn.disabled = false; }
  });
  openModal(modal);
}

// --- New project -----------------------------------------------------------
function openNewProjectModal() {
  const modal = el(`
    <div>
      <h3>새 프로젝트</h3>
      <div class="field"><label>이름</label><input id="np-name" placeholder="예: 신규 제안서 작성"></div>
      <div class="field"><label>목표 (선택)</label><input id="np-obj" placeholder="비우면 첫 회의에서 자동 추출">
        <div class="hint">목표는 첫 회의를 추가하면 자동으로 채워집니다.</div></div>
      <div class="modal-actions">
        <button class="btn btn-ghost" id="np-cancel">취소</button>
        <button class="btn btn-primary" id="np-save">만들기</button>
      </div>
    </div>`);
  modal.querySelector("#np-cancel").addEventListener("click", closeModal);
  modal.querySelector("#np-save").addEventListener("click", async () => {
    const name = modal.querySelector("#np-name").value.trim();
    const objective = modal.querySelector("#np-obj").value.trim() || null;
    if (!name) { toast("이름을 입력하세요"); return; }
    try { const p = await api.createProject({ name, objective }); closeModal(); location.hash = `#/projects/${p.id}`; }
    catch (e) { toast(e.message); }
  });
  openModal(modal);
}

async function createEmptyProject() {
  try {
    const p = await api.createProject({ name: "새 프로젝트" });
    location.hash = `#/projects/${p.id}`;
  } catch (e) { toast(e.message); }
}
document.getElementById("new-project-btn").addEventListener("click", createEmptyProject);

// --- Bottom navigation -----------------------------------------------------
function currentProjectId() {
  const m = location.hash.match(/^#\/projects\/(\d+)/);
  return m ? Number(m[1]) : null;
}

document.querySelectorAll(".bn-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    const nav = btn.dataset.nav;
    if (nav === "home") location.hash = lastDetailHash || "#/";   // 최근(이어보기)
    else if (nav === "folders") location.hash = "#/";             // 프로젝트 목록
    else if (nav === "calendar") location.hash = "#/calendar";
    else if (nav === "profile") location.hash = "#/settings";
  });
});

// Google OAuth 리다이렉트 결과 처리
(() => {
  const p = new URLSearchParams(location.search).get("drive");
  if (!p) return;
  const msg = { connected: "Google Drive 연결됨", denied: "연결이 취소되었습니다", error: "연결 중 오류가 발생했습니다" }[p];
  if (msg) setTimeout(() => toast(msg), 400);
  const targetHash = p === "connected" ? "#/settings" : location.hash;
  history.replaceState(null, "", "/" + targetHash);
})();

// 히스토리(회의·메모) 추가 항목 — Project History 하단 버튼 & FAB 공용
function historyMenuItems(pid) {
  return [
    { label: "회의 녹음", icon: "mic", onClick: () => { location.hash = `#/projects/${pid}/record`; } },
    { label: "메모 추가하기", icon: "edit_note", onClick: () => openPasteModal(pid) },
    { label: "옵시디언에서 검색", icon: "menu_book", onClick: () => openObsidianSearchModal(pid) },
  ];
}

// 레퍼런스(문서) 추가 항목 — Reference 하단 버튼 & FAB 공용
function referenceMenuItems(pid) {
  return [
    { label: "Drive에서 검색", iconHtml: driveLogo(18), onClick: () => openDriveSearchModal(pid) },
    { label: "링크 추가", icon: "link", onClick: () => openLinkModal(pid) },
  ];
}

// FAB 전체 메뉴 = 히스토리 + 레퍼런스(문서) 추가
function addMenuItems(pid) {
  return [...historyMenuItems(pid), ...referenceMenuItems(pid)];
}

document.getElementById("bn-fab").addEventListener("click", () => {
  const pid = currentProjectId();
  if (!pid) { createEmptyProject(); return; }  // 홈에서는 바로 빈 프로젝트
  const r = document.getElementById("bn-fab").getBoundingClientRect();
  showContextMenu(r.left + r.width / 2, r.top, addMenuItems(pid), { above: true, center: true });
});

render();
