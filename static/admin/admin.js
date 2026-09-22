(() => {
  const state = {
    token: localStorage.getItem("admin_token") || "",
    scope: localStorage.getItem("admin_scope") || "",
    chatroomId: localStorage.getItem("admin_cid") || "",
    selected: "",
    tab: "master",
  };

  const $ = (s) => document.querySelector(s);
  const viewLogin = $("#view-login");
  const viewMain = $("#view-main");

  async function api(path, opts = {}) {
    const headers = Object.assign({ "content-type": "application/json" }, opts.headers || {});
    if (state.token) headers["Authorization"] = "Bearer " + state.token;
    const r = await fetch(path, Object.assign({}, opts, { headers }));
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || r.statusText || "请求失败");
    return j;
  }

  function showLogin() {
    viewLogin.classList.remove("hidden");
    viewMain.classList.add("hidden");
  }

  function showMain() {
    viewLogin.classList.add("hidden");
    viewMain.classList.remove("hidden");
    $("#who").textContent =
      state.scope === "master" ? "身份：总管理" : "身份：群管理 · " + (state.chatroomId || "");
    $("#code-box").classList.toggle("hidden", state.scope !== "master");
    loadGroups();
  }

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.tab = btn.dataset.tab;
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b === btn));
      $("#form-master").classList.toggle("hidden", state.tab !== "master");
      $("#form-group").classList.toggle("hidden", state.tab !== "group");
    });
  });

  $("#form-master").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("#login-err").textContent = "";
    try {
      const fd = new FormData(e.target);
      const j = await api("/admin/api/login", {
        method: "POST",
        body: JSON.stringify({ mode: "master", password: fd.get("password") }),
      });
      state.token = j.token;
      state.scope = "master";
      state.chatroomId = "";
      localStorage.setItem("admin_token", state.token);
      localStorage.setItem("admin_scope", "master");
      localStorage.removeItem("admin_cid");
      showMain();
    } catch (err) {
      $("#login-err").textContent = err.message;
    }
  });

  $("#form-group").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("#login-err").textContent = "";
    try {
      const fd = new FormData(e.target);
      const j = await api("/admin/api/login", {
        method: "POST",
        body: JSON.stringify({
          mode: "group",
          chatroom_id: fd.get("chatroom_id"),
          code: fd.get("code"),
        }),
      });
      state.token = j.token;
      state.scope = "group";
      state.chatroomId = j.chatroom_id;
      localStorage.setItem("admin_token", state.token);
      localStorage.setItem("admin_scope", "group");
      localStorage.setItem("admin_cid", state.chatroomId);
      showMain();
    } catch (err) {
      $("#login-err").textContent = err.message;
    }
  });

  $("#btn-logout").addEventListener("click", async () => {
    try {
      await api("/admin/api/logout", { method: "POST", body: "{}" });
    } catch (_) {}
    state.token = "";
    localStorage.removeItem("admin_token");
    showLogin();
  });

  async function loadGroups() {
    const j = await api("/admin/api/groups");
    const ul = $("#group-list");
    ul.innerHTML = "";
    (j.groups || []).forEach((g) => {
      const li = document.createElement("li");
      li.innerHTML =
        '<div class="name"></div><div class="id"></div>';
      li.querySelector(".name").textContent = g.title || "（未命名群）";
      li.querySelector(".id").textContent = g.chatroom_id;
      li.addEventListener("click", () => selectGroup(g.chatroom_id, li));
      ul.appendChild(li);
      if (state.scope === "group" && g.chatroom_id === state.chatroomId) {
        selectGroup(g.chatroom_id, li);
      }
    });
    if (!(j.groups || []).length) {
      ul.innerHTML = "<li class='hint'>暂无群。去目标群发「帮助」后再刷新。</li>";
    }
  }

  async function selectGroup(cid, li) {
    state.selected = cid;
    document.querySelectorAll("#group-list li").forEach((el) => el.classList.remove("on"));
    if (li) li.classList.add("on");
    const j = await api("/admin/api/settings?chatroom_id=" + encodeURIComponent(cid));
    fillForm(j.settings);
  }

  function fillForm(s) {
    $("#edit-empty").classList.add("hidden");
    const form = $("#form-settings");
    form.classList.remove("hidden");
    $("#edit-title").textContent = "配置 · " + (s.title || s.chatroom_id);
    form.title.value = s.title || "";
    form.welcome_text.value = s.welcome_text || "";
    form.help_text.value = s.help_text || "";
    form.game_dice.checked = !!Number(s.game_dice);
    form.game_lot.checked = !!Number(s.game_lot);
    form.draw_enabled.checked = !!Number(s.draw_enabled);
    form.moenode_api_key.value = "";
    form.clear_moe.checked = false;
    form.llm_enabled.checked = !!Number(s.llm_enabled);
    form.llm_base_url.value = s.llm_base_url || "";
    form.llm_model.value = s.llm_model || "";
    form.llm_api_key.value = "";
    form.clear_llm.checked = false;
    form.llm_wake.value = s.llm_wake || "";
    form.llm_system.value = s.llm_system || "";
    $("#group-code").textContent = s.group_admin_code || "—";
    $("#moe-hint").textContent = s.moenode_api_key_set ? "当前：已配置跑图密钥" : "当前：未配置";
    $("#llm-hint").textContent = s.llm_api_key_set ? "当前：已配置大模型密钥" : "当前：未配置";
    form.dataset.cid = s.chatroom_id;
    $("#save-msg").textContent = "";
  }

  $("#form-settings").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const cid = form.dataset.cid;
    const settings = {
      title: form.title.value,
      welcome_text: form.welcome_text.value,
      help_text: form.help_text.value,
      game_dice: form.game_dice.checked ? 1 : 0,
      game_lot: form.game_lot.checked ? 1 : 0,
      draw_enabled: form.draw_enabled.checked ? 1 : 0,
      llm_enabled: form.llm_enabled.checked ? 1 : 0,
      llm_base_url: form.llm_base_url.value,
      llm_model: form.llm_model.value,
      llm_wake: form.llm_wake.value,
      llm_system: form.llm_system.value,
    };
    if (form.clear_moe.checked) settings.moenode_api_key = "__CLEAR__";
    else if (form.moenode_api_key.value.trim()) settings.moenode_api_key = form.moenode_api_key.value.trim();
    else settings.moenode_api_key = "__KEEP__";

    if (form.clear_llm.checked) settings.llm_api_key = "__CLEAR__";
    else if (form.llm_api_key.value.trim()) settings.llm_api_key = form.llm_api_key.value.trim();
    else settings.llm_api_key = "__KEEP__";

    try {
      const j = await api("/admin/api/settings", {
        method: "POST",
        body: JSON.stringify({ chatroom_id: cid, settings }),
      });
      $("#save-msg").textContent = "已保存";
      fillForm(j.settings);
    } catch (err) {
      $("#save-msg").textContent = err.message;
    }
  });

  $("#btn-rotate").addEventListener("click", async () => {
    if (!state.selected) return;
    if (!confirm("重置后旧管理码立即失效，确定？")) return;
    const j = await api("/admin/api/rotate-code", {
      method: "POST",
      body: JSON.stringify({ chatroom_id: state.selected }),
    });
    $("#group-code").textContent = j.group_admin_code;
  });

  // boot
  if (state.token) {
    api("/admin/api/me")
      .then((j) => {
        state.scope = j.scope;
        state.chatroomId = j.chatroom_id || "";
        showMain();
      })
      .catch(() => {
        state.token = "";
        localStorage.removeItem("admin_token");
        showLogin();
      });
  } else {
    showLogin();
  }
})();
