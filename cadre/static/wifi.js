/* Panneau Wi-Fi, commun à l'admin et au portail captif. Les noms de réseaux viennent de
   l'extérieur : toujours insérés en texte (textContent), jamais en HTML. */
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
    box.textContent = r.status === "en cours" ? `Connexion à « ${r.ssid} »…`
      : r.status === "connecté" ? `Connecté à « ${r.ssid} » (${r.ip}).`
      : `Échec pour « ${r.ssid} » : ${r.error}`;
  }

  async function refresh() {
    let st;
    try { st = await call("/api/wifi"); } catch {
      el("wifi-state").textContent = "Le cadre ne répond pas (il change peut-être de réseau).";
      return null;
    }
    if (!st.state) { el("wifi-state").textContent = st.error || "Service réseau indisponible."; return null; }
    const s = st.state;
    mode = s.mode;
    current = s.mode === "connected" ? s.ssid : null;
    el("wifi-state").textContent =
      s.mode === "connected" ? `Connecté à « ${s.ssid} » — adresse ${s.ip}`
      : s.mode === "hotspot" ? "Mode configuration : le cadre n'est connecté à aucun réseau."
      : "Connexion en cours…";

    el("wifi-saved").replaceChildren(...(st.saved.length ? st.saved.map((n) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Oublier";
      btn.onclick = () => forget(n);
      return item(n.ssid + (n.ssid === current ? "  (actuel)" : ""), btn);
    }) : [item("Aucun réseau enregistré")]));

    el("wifi-visible").replaceChildren(...(st.networks.length ? st.networks.map((n) => {
      const li = item(n.ssid + (n.secure ? "  🔒" : ""));
      const b = document.createElement("span");
      b.className = "bars";
      b.textContent = bars(n.signal);
      li.prepend(b);
      li.classList.add("pick");
      li.onclick = () => { form.ssid.value = n.ssid; form.password.value = ""; form.password.focus(); };
      return li;
    }) : [item(mode === "hotspot" ? "Aucun réseau trouvé au démarrage" : "Cliquez sur Actualiser")]));

    showResult(st.result);
    return st;
  }

  async function forget(n) {
    const warn = n.ssid === current ? "\nC'est le réseau actuel : le cadre va s'en déconnecter." : "";
    if (!confirm(`Oublier le réseau « ${n.ssid} » ?${warn}`)) return;
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
    el("wifi-scan").textContent = "Recherche…";
    try { await call("/api/wifi/scan", {}); } finally {
      el("wifi-scan").disabled = false;
      el("wifi-scan").textContent = "Actualiser";
      refresh();
    }
  };

  form.onsubmit = async (e) => {
    e.preventDefault();
    const action = e.submitter && e.submitter.name === "save" ? "save" : "connect";
    const ssid = form.ssid.value.trim(), password = form.password.value;
    if (password && (password.length < 8 || password.length > 63)) {
      alert("Le mot de passe Wi-Fi doit faire de 8 à 63 caractères."); return;
    }
    if (action === "connect" && mode === "connected" &&
        !confirm(`Le cadre va quitter « ${current} » pour « ${ssid} ».\n` +
                 "En cas d'échec, il revient automatiquement sur le réseau actuel.")) return;
    const r = await call(`/api/wifi/${action}`, {ssid, password, hidden: false});
    if (!r.ok) { alert(r.error); return; }
    form.password.value = "";
    if (action === "save") { refresh(); return; }
    if (mode === "hotspot") {
      // Le téléphone va perdre ce réseau : on prévient avant que la page ne réponde plus.
      const box = el("wifi-result");
      box.className = "msg ok";
      box.textContent = `Connexion à « ${ssid} » en cours. Ce réseau de configuration va ` +
        "disparaître : regardez la télévision. Si la connexion réussit, un QR code vous mène à " +
        "la gestion des photos. Sinon, le réseau de configuration revient dans une minute environ.";
      return;
    }
    pollUntilDone();
  };

  refresh().then((st) => { if (st && st.busy) pollUntilDone(); });
})();
