/* Panneau Wi-Fi, commun à l'admin et au portail captif. Les noms de réseaux viennent de
   l'extérieur : toujours insérés en texte (textContent), jamais en HTML. Textes traduits par
   t() (i18n_js.html, inclus avant ce fichier). */
(() => {
  const el = (id) => document.getElementById(id);
  const form = el("wifi-form");
  let current = null, mode = null, polling = false;

  async function call(path, body) {
    const r = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    return r.json();
  }

  function item(text, extra) {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.className = "grow";
    span.textContent = text;
    li.append(span);
    if (extra) li.append(extra);
    return li;
  }

  function bars(signal) {
    return signal > 70 ? "▂▄▆█" : signal > 50 ? "▂▄▆" : signal > 30 ? "▂▄" : "▂";
  }

  function showResult(r) {
    const box = el("wifi-result");
    if (!r) { box.textContent = ""; box.className = "msg"; return; }
    box.className = "msg " + (r.status === "échec" ? "error" : "ok");
    box.textContent = r.status === "en cours" ? t("Connexion à « {ssid} »…", {ssid: r.ssid})
      : r.status === "connecté" ? t("Connecté à « {ssid} » ({ip}).", {ssid: r.ssid, ip: r.ip})
      : t("Échec pour « {ssid} » : {error}", {ssid: r.ssid, error: r.error});
  }

  async function refresh() {
    let st;
    try { st = await call("/api/wifi"); } catch {
      el("wifi-state").textContent = t("Le cadre ne répond pas (il change peut-être de réseau).");
      return null;
    }
    if (!st.state) { el("wifi-state").textContent = st.error || t("Service réseau indisponible."); return null; }
    const s = st.state;
    mode = s.mode;
    current = s.mode === "connected" ? s.ssid : null;
    el("wifi-state").textContent =
      s.mode === "connected" ? t("Connecté à « {ssid} » — adresse {ip}", {ssid: s.ssid, ip: s.ip})
      : s.mode === "hotspot" ? t("Mode configuration : le cadre n'est connecté à aucun réseau.")
      : t("Connexion en cours…");
    const banner = el("wifi-banner");  // admin seulement (absent du portail captif)
    if (banner) banner.hidden = s.mode === "connected";

    el("wifi-saved").replaceChildren(...(st.saved.length ? st.saved.map((n) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = t("Oublier");
      btn.onclick = () => forget(n);
      return item(n.ssid + (n.ssid === current ? "  " + t("(actuel)") : ""), btn);
    }) : [item(t("Aucun réseau enregistré"))]));

    el("wifi-visible").replaceChildren(...(st.networks.length ? st.networks.map((n) => {
      const li = item(n.ssid + (n.secure ? "  🔒" : ""));
      const b = document.createElement("span");
      b.className = "bars";
      b.textContent = bars(n.signal);
      li.prepend(b);
      li.classList.add("pick");
      li.onclick = () => { form.ssid.value = n.ssid; form.password.value = ""; form.password.focus(); };
      return li;
    }) : [item(mode === "hotspot" ? t("Aucun réseau trouvé au démarrage") : t("Cliquez sur Actualiser"))]));

    showResult(st.result);
    return st;
  }

  async function forget(n) {
    const warn = n.ssid === current ? "\n" + t("C'est le réseau actuel : le cadre va s'en déconnecter.") : "";
    if (!confirm(t("Oublier le réseau « {ssid} » ?", {ssid: n.ssid}) + warn)) return;
    const r = await call("/api/wifi/forget", {uuid: n.uuid});
    if (!r.ok) alert(r.error);
    refresh();
  }

  async function pollUntilDone() {
    if (polling) return;
    polling = true;
    for (;;) {
      await new Promise((r) => setTimeout(r, 2000));
      const st = await refresh();
      if (st && !st.busy) break;
    }
    polling = false;
  }

  el("wifi-show").onchange = (e) => { form.password.type = e.target.checked ? "text" : "password"; };

  el("wifi-scan").onclick = async () => {
    el("wifi-scan").disabled = true;
    el("wifi-scan").textContent = t("Recherche…");
    try { await call("/api/wifi/scan", {}); } finally {
      el("wifi-scan").disabled = false;
      el("wifi-scan").textContent = t("Actualiser");
      refresh();
    }
  };

  form.onsubmit = async (e) => {
    e.preventDefault();
    const action = e.submitter && e.submitter.name === "save" ? "save" : "connect";
    const ssid = form.ssid.value.trim(), password = form.password.value;
    if (password && (password.length < 8 || password.length > 63)) {
      alert(t("Le mot de passe Wi-Fi doit faire de 8 à 63 caractères.")); return;
    }
    // État relu juste avant : une page restée ouverte peut dater d'un autre réseau.
    if (action === "connect" && !(await refresh())) return;
    if (action === "connect" && mode === "connected" &&
        !confirm((ssid === current ? t("Le cadre va se reconnecter à « {ssid} ».", {ssid})
                                   : t("Le cadre va quitter « {current} » pour « {ssid} ».", {current, ssid})) +
                 "\n" + t("En cas d'échec, il revient automatiquement sur le réseau actuel."))) return;
    const r = await call(`/api/wifi/${action}`, {ssid, password, hidden: false});
    if (!r.ok) { alert(r.error); return; }
    form.password.value = "";
    if (action === "save") { refresh(); return; }
    if (mode === "hotspot") {
      // Le téléphone va perdre ce réseau : on prévient avant que la page ne réponde plus.
      const box = el("wifi-result");
      box.className = "msg ok";
      box.textContent = t("Connexion à « {ssid} » en cours. Ce réseau de configuration va disparaître : regardez la télévision. Si la connexion réussit, un QR code vous mène à la gestion des photos. Sinon, le réseau de configuration revient dans une minute environ.", {ssid});
      return;
    }
    pollUntilDone();
  };

  refresh().then((st) => { if (st && st.busy) pollUntilDone(); });
})();
