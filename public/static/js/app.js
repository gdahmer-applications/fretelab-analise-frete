(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    files: null,
    options: null,
    currentAnalysis: null,
    sourceAnalysisId: null,
    coverage: null,
    lastResolvedCep: "",
    optionsRequestId: 0,
    sessionAnalyses: [],
    parameterIndex: 1,
    historyItems: [],
    archivedItems: [],
    dashboard: null,
    admin: { isAdmin: false, configured: false },
  };

  const defaultFixed = [
    "OUTRA TAXA VALOR FIXO",
    "TAS VALOR FIXO",
    "TDA VALOR FIXO",
    "TDE VALOR FIXO",
    "PEDAGIO VALOR FIXO",
    "COLETA VALOR FIXO",
    "CTE VALOR FIXO",
    "SECCAT VALOR FIXO",
    "ADEME VALOR FIXO",
    "SEGURO VALOR FIXO",
  ];
  const defaultPerc = ["SEGURO(%)", "GRIS(%)", "FRETE VALOR SOBRE A NOTA(%)"];

  function toast(message) {
    const el = $("toast");
    el.textContent = message;
    el.hidden = false;
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => { el.hidden = true; }, 4200);
  }

  function setProcessing(message) {
    document.body.classList.add("is-processing");
    const status = $("topStatus");
    if (status) status.textContent = message;
  }

  function clearProcessing(message = "Pronto") {
    document.body.classList.remove("is-processing");
    const status = $("topStatus");
    if (status) status.textContent = message;
  }

  function setButtonBusy(button, message = "Processando...") {
    if (!button) return () => {};
    const previousText = button.textContent;
    button.disabled = true;
    button.textContent = message;
    return () => {
      button.disabled = false;
      button.textContent = previousText;
    };
  }

  function filenameFromDisposition(header) {
    if (!header) return "";
    const encoded = header.match(/filename\*=UTF-8''([^;]+)/i);
    if (encoded) return decodeURIComponent(encoded[1].replaceAll("\"", ""));
    const plain = header.match(/filename="?([^";]+)"?/i);
    return plain ? plain[1] : "";
  }

  async function api(url, options = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) throw new Error(data.error || `Erro HTTP ${res.status}`);
    return data;
  }

  async function downloadFile(url, filename, options = {}) {
    const { statusMessage, doneMessage, ...fetchOptions } = options;
    if (statusMessage) setProcessing(statusMessage);
    try {
      const response = await fetch(url, fetchOptions);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "Falha ao gerar arquivo.");
      }
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filenameFromDisposition(response.headers.get("Content-Disposition")) || filename;
      document.body.appendChild(link);
      link.click();
      URL.revokeObjectURL(link.href);
      link.remove();
    } finally {
      if (statusMessage) clearProcessing(doneMessage || "Pronto");
    }
  }

  async function refreshAdminStatus() {
    const admin = await api("/api/admin/status");
    state.admin = admin;
    document.body.classList.toggle("admin-mode", Boolean(admin.isAdmin));
    renderFiles();
    return admin;
  }

  async function requestAdminLogin() {
    if (state.admin?.isAdmin) {
      if (!window.confirm("Encerrar modo ADM?")) return;
      await api("/api/admin/logout", { method: "POST", body: "{}" });
      await refreshAdminStatus();
      toast("Modo ADM encerrado.");
      return;
    }
    const password = window.prompt("Senha ADM");
    if (password == null) return;
    await api("/api/admin/login", { method: "POST", body: JSON.stringify({ password }) });
    await refreshAdminStatus();
    toast("Modo ADM ativo.");
  }

  async function adminFetch(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Erro HTTP ${response.status}`);
    return data;
  }

  async function replaceDataset(kind, target, button = null) {
    const input = target.querySelector(`[data-admin-file="${kind}"]`);
    const file = input?.files?.[0];
    if (!file) {
      toast("Selecione um arquivo .xlsx.");
      return;
    }
    if (!window.confirm(`Substituir a base ${kind} inteira por ${file.name}? O Excel sera convertido para SQLite.`)) return;
    const form = new FormData();
    form.append("file", file);
    const restoreButton = setButtonBusy(button, "Convertendo...");
    setProcessing("Convertendo XLSX para SQLite...");
    try {
      await adminFetch(`/api/admin/datasets/${encodeURIComponent(kind)}/replace`, { method: "POST", body: form });
      input.value = "";
      await refreshFiles();
      await loadOptions();
      await loadPreview();
      toast("Base substituida com sucesso.");
    } finally {
      restoreButton();
      clearProcessing("Bases verificadas");
    }
  }

  async function deleteDatasetFile(kind, filename, button = null) {
    if (!window.confirm(`Excluir ${filename}? Esta acao remove o arquivo da pasta de input.`)) return;
    const restoreButton = setButtonBusy(button, "Excluindo...");
    setProcessing("Excluindo arquivo...");
    try {
      await adminFetch(`/api/admin/datasets/${encodeURIComponent(kind)}/files/${encodeURIComponent(filename)}`, { method: "DELETE" });
      await refreshFiles();
      await loadOptions();
      await loadPreview();
      toast("Arquivo excluido.");
    } finally {
      restoreButton();
      clearProcessing("Bases verificadas");
    }
  }

  async function appendNegotiationDataset(target, button = null) {
    const input = target.querySelector("[data-admin-append-file]");
    const file = input?.files?.[0];
    if (!file) {
      toast("Selecione um arquivo .xlsx para adicionar.");
      return;
    }
    if (!window.confirm(`Adicionar os registros de ${file.name} em Contratos Negociacoes?`)) return;
    const form = new FormData();
    form.append("file", file);
    const restoreButton = setButtonBusy(button, "Adicionando...");
    setProcessing("Convertendo e adicionando transportadora...");
    try {
      const result = await adminFetch("/api/admin/datasets/contratos_negociacoes/append", { method: "POST", body: form });
      input.value = "";
      await refreshFiles();
      await loadOptions();
      await loadPreview();
      await loadNegotiationCarriers(target);
      toast(`${result.addedRows || 0} linha(s) adicionada(s) em negociacoes.`);
    } finally {
      restoreButton();
      clearProcessing("Bases verificadas");
    }
  }

  async function deleteNegotiationCarrier(target, button = null) {
    const select = target.querySelector("[data-admin-carrier-select]");
    const carrier = select?.value?.trim();
    if (!carrier) {
      toast("Selecione a transportadora para remover.");
      return;
    }
    if (!window.confirm(`Remover todos os registros de ${carrier} em Contratos Negociacoes?`)) return;
    const restoreButton = setButtonBusy(button, "Removendo...");
    setProcessing("Removendo transportadora da base...");
    try {
      const result = await adminFetch("/api/admin/datasets/contratos_negociacoes/delete-carrier", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ carrier }),
      });
      await refreshFiles();
      await loadOptions();
      await loadPreview();
      await loadNegotiationCarriers(target);
      toast(`${result.removedRows || 0} linha(s) removida(s) de ${carrier}.`);
    } finally {
      restoreButton();
      clearProcessing("Bases verificadas");
    }
  }

  async function loadNegotiationCarriers(target) {
    const select = target.querySelector("[data-admin-carrier-select]");
    if (!select) return;
    select.innerHTML = optionHtml("", "Carregando...");
    try {
      const data = await api("/api/admin/datasets/contratos_negociacoes/carriers");
      const carriers = data.carriers || [];
      select.innerHTML = optionHtml("", carriers.length ? "Selecione..." : "Nenhuma transportadora cadastrada")
        + carriers.map((carrier) => optionHtml(carrier, carrier)).join("");
    } catch (error) {
      select.innerHTML = optionHtml("", "Falha ao carregar");
    }
  }

  function money(value) {
    if (value == null || Number.isNaN(Number(value))) return "-";
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
  }

  function pct(value) {
    if (value == null || Number.isNaN(Number(value))) return "-";
    return new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 }).format(Number(value));
  }

  function pctPlain(value) {
    if (value == null || Number.isNaN(Number(value))) return "-";
    return `${Math.round(Number(value) * 100)}%`;
  }

  function days(value) {
    if (value == null || Number.isNaN(Number(value))) return "-";
    return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(Number(value))} dia(s)`;
  }

  function splitList(value) {
    return String(value || "").split(";").map((item) => item.trim()).filter(Boolean);
  }

  function norm(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toUpperCase();
  }

  function formatLocalDate(date = new Date()) {
    const pad = (value) => String(value).padStart(2, "0");
    return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  function displayDate(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    if (text.includes("/")) return text;
    const parsed = new Date(text);
    return Number.isNaN(parsed.getTime()) ? text : formatLocalDate(parsed);
  }

  function resetAnalysisMetadata(forceName = true) {
    const value = formatLocalDate();
    $("analysisDateInput").value = value;
    if (forceName || !$("analysisNameInput").value.trim()) {
      $("analysisNameInput").value = `Análise ${value}`;
    }
  }

  function analysisMetadataFromUI() {
    return {
      analysisDate: $("analysisDateInput").value.trim(),
      analysisName: $("analysisNameInput").value.trim() || `Análise ${$("analysisDateInput").value.trim()}`,
      responsible: $("analysisResponsibleInput").value.trim(),
    };
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setPage(page) {
    document.querySelectorAll(".page").forEach((el) => el.classList.toggle("active", el.id === `page-${page}`));
    document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.page === page));
    document.querySelectorAll(".top-dropdown").forEach((el) => {
      const hasActive = Boolean(el.querySelector(".nav-item.active"));
      el.classList.toggle("active", hasActive);
      if (el.open) el.open = false;
    });
    if (page === "home") renderHome();
    if (page === "historico") renderFilteredHistory();
  }

  function configFromUI() {
    return {
      weights: {
        start: Number($("cfgStart").value || 20),
        end: Number($("cfgEnd").value || 200),
        step: Number($("cfgStep").value || 20),
      },
      flags: {
        addFixed: $("cfgAddFixed").checked,
        addPerc: $("cfgAddPerc").checked,
        applyMinFrete: $("cfgApplyMin").checked,
      },
      nota: Number($("cfgNota").value || 0),
      fixedFields: splitList($("cfgFixed").value.replace(/\r?\n/g, ";")),
      percentFields: splitList($("cfgPerc").value.replace(/\r?\n/g, ";")),
      columns: {
        nome: $("colNome").value.trim(),
        id: $("colId").value.trim(),
        estoque: $("colEstoque").value.trim(),
        cidade: $("colCidade").value.trim(),
        uf: $("colUf").value.trim(),
        cepInicial: $("colCepIni").value.trim(),
        cepFinal: $("colCepFim").value.trim(),
        ibgeInicial: $("colIbgeIni").value.trim(),
        ibgeFinal: $("colIbgeFim").value.trim(),
        ibge: $("colIbge").value.trim(),
      },
    };
  }

  function resetConfig() {
    $("cfgStart").value = 20;
    $("cfgEnd").value = 200;
    $("cfgStep").value = 20;
    $("cfgNota").value = 1000;
    $("cfgAddFixed").checked = true;
    $("cfgAddPerc").checked = false;
    $("cfgApplyMin").checked = false;
    $("cfgFixed").value = defaultFixed.join("\n");
    $("cfgPerc").value = defaultPerc.join("\n");
    $("colNome").value = "NOME";
    $("colId").value = "ID INTELIPOST";
    $("colEstoque").value = "ESTOQUE";
    $("colCidade").value = "CIDADE";
    $("colUf").value = "UF";
    $("colCepIni").value = "CEPI";
    $("colCepFim").value = "CEPF";
    $("colIbgeIni").value = "";
    $("colIbgeFim").value = "";
    $("colIbge").value = "";
  }

  function kpi(value, label, tone = "", detail = "") {
    return `<div class="kpi ${tone}"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span>${detail ? `<em>${escapeHtml(detail)}</em>` : ""}</div>`;
  }

  function sessionTitle() {
    return `Análise ${state.parameterIndex}`;
  }

  function renderParameterInstances() {
    const target = $("parameterInstances");
    if (!target) return;
    const generated = state.sessionAnalyses.map((analysis, idx) => {
      const cep = analysis.cep?.cep || "-";
      const city = analysis.location?.municipio || analysis.cep?.city || "-";
      return `<div class="parameter-chip">Análise ${idx + 1} gerada | ${escapeHtml(city)} | CEP ${escapeHtml(cep)}</div>`;
    }).join("");
    const active = state.sessionAnalyses.length < state.parameterIndex
      ? `<div class="parameter-chip active">${escapeHtml(sessionTitle())} em edição</div>`
      : "";
    target.innerHTML = generated + active;
    $("activeParamTitle").textContent = sessionTitle();
  }

  function renderFileKpis() {
    const validation = state.files?.validation || {};
    $("fileKpis").innerHTML = [
      kpi(validation.contratos_vigentes?.rowCount || 0, "linhas em contratos vigentes"),
      kpi(validation.contratos_negociacoes?.rowCount || 0, "linhas em negociações"),
      kpi(validation.pedidos?.rowCount || 0, "linhas em pedidos"),
      kpi(validation.contratos_vigentes?.weightColumns?.length || 0, "faixas de peso"),
    ].join("");
  }

  function renderFilePage(kind, targetId) {
    const block = state.files?.status?.[kind];
    const validation = state.files?.validation?.[kind];
    const target = $(targetId);
    if (!target) return;
    if (!block) {
      target.innerHTML = `<div class="notice">Status indisponível.</div>`;
      return;
    }
    const badge = validation?.ok ? `<span class="badge ok">validado</span>` : `<span class="badge warn">atenção</span>`;
    const missing = validation?.missing?.length ? `<p>Campos pendentes: ${validation.missing.join(", ")}</p>` : "";
    const loadErrors = validation?.loadErrors?.length ? `<p>Erros: ${validation.loadErrors.join("; ")}</p>` : "";
    const adminPanel = state.admin?.isAdmin ? `
      <section class="panel admin-panel">
        <div class="panel-head">
          <h2>Manutencao ADM</h2>
          <span class="badge ok">ADM ativo</span>
        </div>
        <div class="admin-actions">
          <label>Substituir base inteira por Excel
            <input data-admin-file="${escapeHtml(kind)}" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />
          </label>
          ${kind === "contratos_vigentes" || kind === "contratos_negociacoes" ? `<button class="secondary" type="button" data-admin-template>Baixar template</button>` : ""}
          <button type="button" data-admin-replace="${escapeHtml(kind)}">Converter e substituir</button>
          <button class="secondary" type="button" data-admin-logout>Encerrar ADM</button>
        </div>
        <p class="muted">O replace recebe um .xlsx, converte a primeira aba para SQLite, remove os arquivos carregaveis atuais desta pasta e preserva o Excel em origem/.</p>
        ${kind === "contratos_negociacoes" ? `
          <div class="admin-record-actions">
            <div class="admin-record-grid">
              <label>Adicionar transportadora por Excel
                <input data-admin-append-file type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />
              </label>
              <button type="button" data-admin-append-negotiation>Adicionar registros</button>
              <label>Transportadora cadastrada
                <select data-admin-carrier-select><option value="">Carregando...</option></select>
              </label>
              <button class="secondary danger" type="button" data-admin-delete-carrier>Remover transportadora</button>
            </div>
            <p class="muted">Use esta manutencao para incluir uma tabela de negociacao temporaria e remover depois apenas a transportadora selecionada.</p>
          </div>
        ` : ""}
      </section>
    ` : "";
    const files = block.files.length ? block.files.map((file) => `
      <div class="file-card">
        <div>
          <strong>${escapeHtml(file.name)}</strong>
          <p>${escapeHtml(file.rows ?? "-")} linhas | ${(file.columns || []).length} colunas | origem: ${escapeHtml(file.source)}</p>
          ${file.error ? `<p>${escapeHtml(file.error)}</p>` : ""}
        </div>
        <div class="file-actions">
          ${file.error ? `<span class="badge danger">erro</span>` : badge}
          ${state.admin?.isAdmin ? `
            <button class="secondary" type="button" data-admin-download="${escapeHtml(kind)}" data-filename="${escapeHtml(file.name)}">Baixar XLSX</button>
            <button class="secondary danger" type="button" data-admin-delete="${escapeHtml(kind)}" data-filename="${escapeHtml(file.name)}">Excluir</button>
          ` : ""}
        </div>
      </div>
    `).join("") : `<div class="notice">Nenhum arquivo encontrado em <span class="mono">${escapeHtml(block.directory)}</span>.</div>`;

    target.innerHTML = `
      ${adminPanel}
      <section class="panel">
        <div class="panel-head"><h2>Diretório</h2>${badge}</div>
        <div class="notice"><span class="mono">${escapeHtml(block.directory)}</span>${missing}${loadErrors}</div>
      </section>
      ${files}
    `;
    bindAdminDatasetActions(target, kind);
  }

  function renderFiles() {
    if (!$("fileKpis")) return;
    renderFileKpis();
    renderFilePage("contratos_vigentes", "vigentesFiles");
    renderFilePage("pedidos", "pedidosFiles");
    renderFilePage("contratos_negociacoes", "negociacoesFiles");
    renderFilePage("regioes_logisticas", "regioesFiles");
  }

  function bindAdminDatasetActions(target, kind) {
    if (!state.admin?.isAdmin) return;
    target.querySelector(`[data-admin-replace="${kind}"]`)?.addEventListener("click", (event) => {
      replaceDataset(kind, target, event.currentTarget).catch((error) => toast(error.message));
    });
    target.querySelector("[data-admin-template]")?.addEventListener("click", (event) => {
      const restoreButton = setButtonBusy(event.currentTarget, "Gerando...");
      downloadFile("/api/templates/contratos", "template_contratos_fretelab.xlsx", {
        statusMessage: "Gerando template XLSX...",
        doneMessage: "Pronto",
      })
        .finally(restoreButton)
        .catch((error) => toast(error.message));
    });
    target.querySelector("[data-admin-append-negotiation]")?.addEventListener("click", (event) => {
      appendNegotiationDataset(target, event.currentTarget).catch((error) => toast(error.message));
    });
    target.querySelector("[data-admin-delete-carrier]")?.addEventListener("click", (event) => {
      deleteNegotiationCarrier(target, event.currentTarget).catch((error) => toast(error.message));
    });
    target.querySelectorAll("[data-admin-download]").forEach((button) => {
      button.addEventListener("click", () => {
        const filename = button.dataset.filename;
        const suggested = filename.replace(/\.[^.]+$/, ".xlsx");
        const restoreButton = setButtonBusy(button, "Gerando...");
        downloadFile(`/api/admin/datasets/${encodeURIComponent(kind)}/files/${encodeURIComponent(filename)}/download`, suggested, {
          statusMessage: "Gerando XLSX da base...",
          doneMessage: "Pronto",
        })
          .finally(restoreButton)
          .catch((error) => toast(error.message));
      });
    });
    target.querySelectorAll("[data-admin-delete]").forEach((button) => {
      button.addEventListener("click", () => {
        deleteDatasetFile(kind, button.dataset.filename, button).catch((error) => toast(error.message));
      });
    });
    target.querySelector("[data-admin-logout]")?.addEventListener("click", () => {
      api("/api/admin/logout", { method: "POST", body: "{}" })
        .then(refreshAdminStatus)
        .then(() => toast("Modo ADM encerrado."))
        .catch((error) => toast(error.message));
    });
    if (kind === "contratos_negociacoes") {
      loadNegotiationCarriers(target);
    }
  }

  function optionHtml(value, label, selected = false) {
    return `<option value="${escapeHtml(value)}"${selected ? " selected" : ""}>${escapeHtml(label)}</option>`;
  }

  function fillSelect(select, values, placeholder) {
    select.innerHTML = optionHtml("", placeholder) + values.map((value) => optionHtml(value, value)).join("");
  }

  function selectedSecondaryCarriers() {
    const values = [...document.querySelectorAll(".secondaryCarrier")].map((select) => select.value).filter(Boolean);
    return [...new Set(values)];
  }

  function carrierOptionsForSelect(currentValue, includeMain = false) {
    const valid = state.coverage?.validCarriers || [];
    const main = $("mainCarrier").value;
    const secondary = selectedSecondaryCarriers();
    const known = valid.some((item) => item.key === currentValue);
    const extras = currentValue && !known ? [optionHtml(currentValue, currentValue, true)] : [];
    return optionHtml("", "Selecione...") + extras.join("") + valid
      .filter((item) => {
        if (!includeMain && item.key === main && item.key !== currentValue) return false;
        if (secondary.includes(item.key) && item.key !== currentValue) return false;
        return true;
      })
      .map((item) => optionHtml(item.key, item.key, item.key === currentValue))
      .join("");
  }

  function setCarrierOptions() {
    const previousMain = $("mainCarrier").value;
    $("mainCarrier").innerHTML = carrierOptionsForSelect(previousMain, true);
    if ([...$("mainCarrier").options].some((opt) => opt.value === previousMain)) $("mainCarrier").value = previousMain;

    document.querySelectorAll(".secondaryCarrier").forEach((select) => {
      const previous = select.value;
      select.innerHTML = carrierOptionsForSelect(previous, false);
      if ([...select.options].some((opt) => opt.value === previous)) select.value = previous;
    });
  }

  function addSecondarySlot(value = "") {
    const wrap = $("secondarySlots");
    const slot = document.createElement("div");
    slot.className = "secondary-slot";
    slot.innerHTML = `
      <select class="secondaryCarrier"></select>
      <button class="secondary" type="button" title="Remover">X</button>
    `;
    slot.querySelector("button").addEventListener("click", () => {
      if (wrap.querySelectorAll(".secondary-slot").length <= 1) {
        toast("Mantenha ao menos uma transportadora secundária.");
        return;
      }
      slot.remove();
      setCarrierOptions();
    });
    slot.querySelector("select").addEventListener("change", setCarrierOptions);
    wrap.appendChild(slot);
    setCarrierOptions();
    slot.querySelector("select").value = value;
    setCarrierOptions();
  }

  function setSecondarySelection(values) {
    const wrap = $("secondarySlots");
    wrap.innerHTML = "";
    const selected = (values || []).filter(Boolean);
    if (!selected.length) selected.push("");
    selected.forEach((value) => addSecondarySlot(value));
    setCarrierOptions();
  }

  function selectedEstbs() {
    const value = $("estbSelect").value || "__ALL__";
    return [value];
  }

  function resetEstbsToAll() {
    if ($("estbSelect")) $("estbSelect").value = "__ALL__";
  }

  function refreshCarriersIfReady() {
    const cep = $("cepLookupInput").value.replace(/\D/g, "").slice(0, 8);
    if (cep.length === 8 && $("ufSelect").value && $("municipioSelect").value && selectedEstbs().length) {
      refreshCarriers().catch((e) => toast(e.message));
    }
  }

  async function loadOptions() {
    const requestId = ++state.optionsRequestId;
    const logisticsRegion = $("logisticsRegionSelect").value;
    const uf = $("ufSelect").value;
    const municipio = $("municipioSelect").value;
    const params = new URLSearchParams();
    if (logisticsRegion) params.set("logisticsRegion", logisticsRegion);
    if (uf) params.set("uf", uf);
    if (municipio) params.set("municipio", municipio);
    const options = await api(`/api/options?${params.toString()}`);
    if (requestId !== state.optionsRequestId) return;
    state.options = options;

    const previousRegion = $("logisticsRegionSelect").value;
    $("logisticsRegionSelect").innerHTML = optionHtml("", "Todas") + (state.options.logisticsRegions || []).map((value) => optionHtml(value, value)).join("");
    if ([...$("logisticsRegionSelect").options].some((opt) => opt.value === previousRegion)) $("logisticsRegionSelect").value = previousRegion;

    const previousUf = $("ufSelect").value;
    fillSelect($("ufSelect"), state.options.ufs || [], "UF");
    if ([...$("ufSelect").options].some((opt) => opt.value === previousUf)) $("ufSelect").value = previousUf;

    const previousMunicipio = $("municipioSelect").value;
    fillSelect($("municipioSelect"), state.options.municipios || [], "Município");
    if ([...$("municipioSelect").options].some((opt) => opt.value === previousMunicipio)) $("municipioSelect").value = previousMunicipio;

    const previousEstb = $("estbSelect").value || "__ALL__";
    $("estbSelect").innerHTML = (state.options.estbs || []).map((item) => optionHtml(item.value, item.label)).join("");
    if ([...$("estbSelect").options].some((opt) => opt.value === previousEstb)) $("estbSelect").value = previousEstb;
    else if ([...$("estbSelect").options].some((opt) => opt.value === "__ALL__")) $("estbSelect").value = "__ALL__";
  }

  async function loadPreview() {
    const kind = $("previewKind").value;
    const q = $("previewFilter").value.trim();
    const params = new URLSearchParams({ kind, limit: "120" });
    if (q) params.set("q", q);
    const data = await api(`/api/preview?${params.toString()}`);
    $("previewMeta").textContent = `${data.rowCount || 0} linha(s) retornada(s) para ${kind}.`;
    const columns = data.columns || [];
    const rows = data.rows || [];
    if (!columns.length) {
      $("previewTable").innerHTML = "";
      return;
    }
    const head = `<thead><tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead>`;
    const body = `<tbody>${rows.map((row) => `<tr>${columns.map((col) => `<td>${escapeHtml(row[col] ?? "")}</td>`).join("")}</tr>`).join("")}</tbody>`;
    $("previewTable").innerHTML = head + body;
  }

  function selectByNormalized(select, wanted) {
    const hit = [...select.options].find((option) => norm(option.value) === norm(wanted) || norm(option.textContent) === norm(wanted));
    if (!hit) return false;
    select.value = hit.value;
    return true;
  }

  async function resolveCepIntoLocation(force = false) {
    const cep = $("cepLookupInput").value.replace(/\D/g, "").slice(0, 8);
    if (cep.length !== 8) {
      if (force) toast("Informe um CEP com 8 dígitos.");
      state.lastResolvedCep = "";
      return;
    }
    if (!force && cep === state.lastResolvedCep) return;
    $("cepLookupInput").value = cep;
    $("topStatus").textContent = "Localizando CEP...";
    const info = await api(`/api/cep/resolve?cep=${cep}`);

    state.lastResolvedCep = cep;
    $("logisticsRegionSelect").value = "";
    $("ufSelect").value = "";
    $("municipioSelect").value = "";
    resetEstbsToAll();
    await loadOptions();

    if (info.logisticsRegion) {
      selectByNormalized($("logisticsRegionSelect"), info.logisticsRegion);
      await loadOptions();
    }
    if (!selectByNormalized($("ufSelect"), info.uf)) {
      toast("UF do CEP não encontrada nas bases.");
      return;
    }
    await loadOptions();
    if (!selectByNormalized($("municipioSelect"), info.city)) {
      toast("Município do CEP não encontrado nas bases.");
      return;
    }
    await loadOptions();
    resetEstbsToAll();
    if ($("ufSelect").value && $("municipioSelect").value && selectedEstbs().length) {
      await refreshCarriers();
    }
    $("topStatus").textContent = "Pronto";
    toast(`Localidade preenchida: ${info.city || "-"} / ${info.uf || "-"}${info.logisticsRegion ? ` - ${info.logisticsRegion}` : ""}.`);
  }

  async function refreshFiles() {
    state.files = await api("/api/files");
    renderFiles();
    $("topStatus").textContent = "Bases verificadas";
  }

  function renderCoverage(data) {
    state.coverage = data;
    const location = data.location || {};
    const ranges = data.cepRanges || [];
    const uniqueRanges = [...new Set(ranges.map((item) => `${item.cepInicial}-${item.cepFinal}`).filter((item) => item !== "-"))];
    if ($("cepNotice")) $("cepNotice").textContent = uniqueRanges.length
      ? `Ranges encontrados: ${uniqueRanges.slice(0, 6).join(", ")}${uniqueRanges.length > 6 ? "..." : ""}`
      : "Nenhum range de CEP retornado para a seleção.";

    const valid = data.validCarriers || [];
    setCarrierOptions();
    $("topStatus").textContent = `${location.municipio || "-"} / ${location.uf || "--"} | ${valid.length} transportadora(s) válida(s)`;
  }

  async function refreshCarriers() {
    const cep = $("cepLookupInput").value.replace(/\D/g, "").slice(0, 8);
    const uf = $("ufSelect").value;
    const municipio = $("municipioSelect").value;
    const estbs = selectedEstbs();
    if (cep.length !== 8) {
      toast("Informe um CEP com 8 dígitos.");
      return;
    }
    if (!uf || !municipio || !estbs.length) {
      toast("Informe o CEP para carregar UF, município e ESTB.");
      return;
    }
    const data = await api("/api/carriers/location", {
      method: "POST",
      body: JSON.stringify({ cep, uf, municipio, estbs, config: configFromUI() }),
    });
    renderCoverage(data);
  }

  function fallbackExecutive(analysis) {
    const rows = analysis.rows || [];
    const ranking = rows.map((row, index) => {
      const values = (row.totals || []).filter((v) => v != null && !Number.isNaN(Number(v))).map(Number);
      const deadlines = (row.deadlines || []).filter((v) => v != null && !Number.isNaN(Number(v))).map(Number);
      return {
        key: row.key,
        label: row.label,
        role: row.role,
        position: index + 1,
        averageCost: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
        averageDeadline: deadlines.length ? deadlines.reduce((a, b) => a + b, 0) / deadlines.length : null,
        badges: row.role === "main" ? ["Principal"] : [],
      };
    }).filter((item) => item.averageCost != null).sort((a, b) => a.averageCost - b.averageCost);
    ranking.forEach((item, index) => { item.position = index + 1; });
    return {
      ranking,
      bestCostCarrier: ranking[0] || null,
      worstCostCarrier: ranking[ranking.length - 1] || null,
      fastestCarrier: ranking.filter((item) => item.averageDeadline != null).sort((a, b) => a.averageDeadline - b.averageDeadline)[0] || null,
      bestBalanceCarrier: ranking[0] || null,
      potentialSaving: { amount: 0, percent: 0 },
      insights: [],
      statusTags: [],
    };
  }

  function comparisonTableHtml(analysis) {
    const location = analysis.location || {};
    const cep = analysis.cep || {};
    const title = `RESULTADO ANÁLISE - ${(location.municipio || cep.city || "-").toUpperCase()} (${cep.cep || "CEP"})`;
    const weights = analysis.weights || [];
    const rows = analysis.rows || [];
    const variations = analysis.variations || [];
    const representativity = analysis.representativity || {};
    const valueColumns = weights.map((_, idx) => rows.map((row) => row.totals?.[idx]).filter((value) => value != null && !Number.isNaN(Number(value))));
    const toneFor = (value, idx) => {
      if (value == null || Number.isNaN(Number(value))) return "";
      const col = valueColumns[idx] || [];
      if (col.length <= 1) return "tone-good";
      const min = Math.min(...col);
      const max = Math.max(...col);
      if (max === min) return "tone-good";
      const ratio = (Number(value) - min) / (max - min);
      if (ratio <= 0.08) return "tone-best";
      if (ratio <= 0.35) return "tone-good";
      if (ratio <= 0.65) return "tone-mid";
      if (ratio <= 0.9) return "tone-bad";
      return "tone-worst";
    };
    const header = `
      <thead>
        <tr class="title-row"><th colspan="${weights.length + 1}">${escapeHtml(title)}</th></tr>
        <tr><th>Transportadora</th>${weights.map((w) => `<th>${escapeHtml(w)} KG</th>`).join("")}</tr>
      </thead>
    `;
    const moneyCell = (value, idx) => value == null
      ? `<td class="${toneFor(value, idx)}">-</td>`
      : `<td class="${toneFor(value, idx)}"><span class="currency"><span>R$</span><span>${escapeHtml(money(value).replace("R$", "").trim())}</span></span></td>`;
    const bodyRows = rows.map((row) => `
      <tr class="${row.role === "main" ? "main-row" : "carrier-row"}">
        <td class="label-cell">${escapeHtml(row.label)}</td>
        ${(row.totals || []).map((v, idx) => moneyCell(v, idx)).join("")}
      </tr>
    `).join("");
    const varRows = variations.map((row) => `
      <tr class="variation-row">
        <td class="label-cell">${escapeHtml(row.label)}</td>
        ${(row.values || []).map((v) => {
          const cls = v == null ? "variation-neutral" : Number(v) < 0 ? "variation-negative" : Number(v) > 0 ? "variation-positive" : "variation-neutral";
          return `<td class="${cls}">${escapeHtml(pctPlain(v))}</td>`;
        }).join("")}
      </tr>
    `).join("");
    const repRow = representativity.values ? `
      <tr class="representativity-row">
        <td class="label-cell">${escapeHtml(representativity.label || "REPRESENTATIVIDADE")}</td>
        ${(representativity.values || []).map((v) => `<td>${escapeHtml(pctPlain(v))}</td>`).join("")}
      </tr>
    ` : "";
    return `${header}<tbody>${bodyRows}${varRows}${repRow}</tbody>`;
  }

  function executiveKpisHtml(analysis) {
    const executive = analysis.executive || fallbackExecutive(analysis);
    const best = executive.bestCostCarrier || {};
    const fastest = executive.fastestCarrier || {};
    const balance = executive.bestBalanceCarrier || {};
    const saving = executive.potentialSaving || {};
    const orders = analysis.summary?.orders;
    return `
      <div class="result-kpi-grid">
        ${kpi(best.label || "-", "Melhor custo médio", "good", money(best.averageCost))}
        ${kpi(fastest.label || "-", "Menor prazo médio", "info", days(fastest.averageDeadline))}
        ${kpi(balance.label || "-", "Melhor custo x prazo", "", money(balance.averageCost))}
        ${kpi(money(saving.amount), "Economia potencial", saving.amount > 0 ? "good" : "", pct(saving.percent))}
        ${kpi(orders ?? "-", "Pedidos relacionados", "", "histórico")}
      </div>
    `;
  }

  function rankingHtml(analysis) {
    const ranking = (analysis.executive || fallbackExecutive(analysis)).ranking || [];
    if (!ranking.length) return `<div class="notice">Ranking indisponível.</div>`;
    return `
      <div class="ranking-list result-ranking">
        ${ranking.slice(0, 8).map((item) => `
          <div class="ranking-item">
            <span class="rank-pos">${escapeHtml(item.position || "-")}</span>
            <div>
              <strong>${escapeHtml(item.label || "-")}</strong>
              <p>${escapeHtml(money(item.averageCost))} médio ${item.averageDeadline != null ? `| ${escapeHtml(days(item.averageDeadline))}` : ""}</p>
              <div class="badge-row">${(item.badges || []).map((tag) => `<span class="badge ${norm(tag).includes("MELHOR") || norm(tag).includes("MENOR") ? "ok" : ""}">${escapeHtml(tag)}</span>`).join("")}</div>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  function insightsHtml(analysis) {
    const insights = (analysis.executive || fallbackExecutive(analysis)).insights || [];
    if (!insights.length) return `<div class="notice">Nenhum insight automático calculado para esta análise.</div>`;
    return `<div class="insight-list">${insights.map((item) => `<div class="insight-item">${escapeHtml(item)}</div>`).join("")}</div>`;
  }

  function resultCardHtml(analysis, index) {
    const location = analysis.location || {};
    const cep = analysis.cep || {};
    const name = analysis.analysisName || analysis.title || "Análise sem nome";
    const date = displayDate(analysis.analysisDate || analysis.createdAt) || "-";
    const responsible = analysis.responsible || "-";
    const tags = (analysis.executive?.statusTags || []).map((tag) => `<span class="badge ok">${escapeHtml(tag)}</span>`).join("");
    return `
      <article class="analysis-result-card" data-analysis-id="${escapeHtml(analysis.id)}">
        <div class="analysis-result-head">
          <div>
            <p class="eyebrow">${index === 0 ? "Análise principal" : "Análise replicada"}</p>
            <h3>${escapeHtml(name)}</h3>
          </div>
          <div class="badge-row"><span class="badge">v${escapeHtml(analysis.version || 1)}</span><span class="badge ok">Salva no histórico</span>${tags}</div>
        </div>
        <div class="analysis-meta">
          <span>Data ${escapeHtml(date)}</span>
          <span>Responsável ${escapeHtml(responsible)}</span>
          <span>${escapeHtml((location.municipio || cep.city || "Localidade").toUpperCase())}</span>
          <span>CEP ${escapeHtml(cep.cep || "-")}</span>
          <span>UF ${escapeHtml(location.uf || cep.uf || "--")}</span>
          <span>ESTB ${escapeHtml(location.estb || "--")}</span>
        </div>
        ${executiveKpisHtml(analysis)}
        <div class="result-detail-grid">
          <section class="mini-panel">
            <div class="panel-head"><h3>Ranking de transportadoras</h3><span class="muted">média das faixas</span></div>
            ${rankingHtml(analysis)}
          </section>
          <section class="mini-panel">
            <div class="panel-head"><h3>Insights automáticos</h3><span class="muted">oportunidades</span></div>
            ${insightsHtml(analysis)}
          </section>
        </div>
        <div class="table-wrap comparison-wrap">
          <table class="comparison-table">${comparisonTableHtml(analysis)}</table>
        </div>
        ${(analysis.warnings || []).length ? `<div class="notice">Diagnóstico: ${escapeHtml((analysis.warnings || []).join("; "))}</div>` : ""}
        <div class="card-actions actions">
          <button class="secondary" data-card-pdf="${escapeHtml(analysis.id)}">PDF desta análise</button>
          <button class="secondary" data-card-html="${escapeHtml(analysis.id)}">HTML desta análise</button>
        </div>
      </article>
    `;
  }

  function renderSessionResults() {
    const target = $("resultCards");
    $("resultPanel").hidden = !state.sessionAnalyses.length;
    $("resultCount").textContent = `${state.sessionAnalyses.length} análise(s) na sessão`;
    target.innerHTML = state.sessionAnalyses.map((analysis, index) => resultCardHtml(analysis, index)).join("");
    target.querySelectorAll("[data-card-pdf]").forEach((btn) => btn.addEventListener("click", () => exportAnalysisFile(btn.dataset.cardPdf, "pdf")));
    target.querySelectorAll("[data-card-html]").forEach((btn) => btn.addEventListener("click", () => exportAnalysisFile(btn.dataset.cardHtml, "html")));
    renderParameterInstances();
  }

  function renderResult(analysis, options = {}) {
    const { setAsSource = true } = options;
    state.currentAnalysis = analysis;
    if (setAsSource) state.sourceAnalysisId = analysis.id;
    if (!state.sessionAnalyses.some((item) => item.id === analysis.id)) {
      state.sessionAnalyses.push(analysis);
    } else {
      state.sessionAnalyses = state.sessionAnalyses.map((item) => item.id === analysis.id ? analysis : item);
    }
    state.parameterIndex = Math.max(state.parameterIndex, state.sessionAnalyses.length + 1);
    renderSessionResults();
  }

  async function runAnalysis() {
    const cep = $("cepLookupInput").value.replace(/\D/g, "").slice(0, 8);
    const uf = $("ufSelect").value;
    const municipio = $("municipioSelect").value;
    const estbs = selectedEstbs();
    const secondary = selectedSecondaryCarriers();
    if (cep.length !== 8) {
      toast("Informe um CEP com 8 dígitos.");
      return;
    }
    if (!uf || !municipio || !estbs.length) {
      toast("Informe o CEP para carregar UF, município e ESTB.");
      return;
    }
    if (!secondary.length) {
      toast("Selecione ao menos uma transportadora secundária.");
      return;
    }
    const payload = {
      cep,
      uf,
      municipio,
      estbs,
      logisticsRegion: $("logisticsRegionSelect").value || "",
      mainCarrier: $("mainCarrier").value || null,
      secondaryCarriers: secondary,
      sourceAnalysisId: state.sourceAnalysisId,
      ...analysisMetadataFromUI(),
      config: configFromUI(),
    };
    $("topStatus").textContent = "Gerando análise...";
    const analysis = await api("/api/analyses", { method: "POST", body: JSON.stringify(payload) });
    renderResult(analysis);
    await loadHistory();
    $("topStatus").textContent = "Análise salva";
    toast(`Análise ${analysis.id} salva como versão ${analysis.version}.`);
  }

  function historyFilters() {
    return {
      date: norm($("historyFilterDate")?.value || ""),
      name: norm($("historyFilterName")?.value || ""),
      responsible: norm($("historyFilterResponsible")?.value || ""),
      cep: String($("historyFilterCep")?.value || "").replace(/\D/g, ""),
      carrier: norm($("historyFilterCarrier")?.value || ""),
      bestCarrier: norm($("historyFilterBestCarrier")?.value || ""),
      status: norm($("historyFilterStatus")?.value || ""),
    };
  }

  function filterHistoryItems(items) {
    const filters = historyFilters();
    return items.filter((item) => {
      const date = norm(`${item.analysisDateDisplay || ""} ${item.createdAtDisplay || ""} ${item.analysisDate || ""} ${item.createdAt || ""}`);
      const name = norm(item.analysisName || item.title || "");
      const responsible = norm(item.responsible || "");
      const cep = String(item.cep || "").replace(/\D/g, "");
      const carrier = norm(`${item.mainCarrier || ""} ${(item.secondaryCarriers || []).join(" ")}`);
      const bestCarrier = norm(`${item.bestCostCarrier || ""} ${item.fastestCarrier || ""} ${item.bestBalanceCarrier || ""}`);
      const status = norm((item.statusTags || []).join(" "));
      if (filters.date && !date.includes(filters.date)) return false;
      if (filters.name && !name.includes(filters.name)) return false;
      if (filters.responsible && !responsible.includes(filters.responsible)) return false;
      if (filters.cep && !cep.includes(filters.cep)) return false;
      if (filters.carrier && !carrier.includes(filters.carrier)) return false;
      if (filters.bestCarrier && !bestCarrier.includes(filters.bestCarrier)) return false;
      if (filters.status && !status.includes(filters.status)) return false;
      return true;
    });
  }

  function historyCardHtml(item) {
    const tags = (item.statusTags || []).map((tag) => `<span class="badge ok">${escapeHtml(tag)}</span>`).join("");
    const savingText = item.potentialSavingAmount != null ? `${money(item.potentialSavingAmount)} (${pct(item.potentialSavingPct)})` : "-";
    return `
      <div class="analysis-card">
        <div>
          <div class="history-title-row">
            <strong>${escapeHtml(item.analysisName || item.title || "Análise sem título")}</strong>
            <div class="badge-row">${tags}</div>
          </div>
          <p>Data: ${escapeHtml(item.analysisDateDisplay || item.createdAtDisplay || item.createdAt || "-")} | Responsável: ${escapeHtml(item.responsible || "-")} | v${escapeHtml(item.version || 1)}</p>
          <p>${escapeHtml(item.city || "-")} / ${escapeHtml(item.uf || "-")} | CEP ${escapeHtml(item.cep || "range")} | ESTB ${escapeHtml(item.estb || "-")}</p>
          <p>Principal: ${escapeHtml(item.mainCarrier || "-")}</p>
          <p>Melhor custo: ${escapeHtml(item.bestCostCarrier || "-")} | Menor prazo: ${escapeHtml(item.fastestCarrier || "-")} | Economia: ${escapeHtml(savingText)}</p>
        </div>
        <div class="actions history-actions">
          <button class="secondary" data-open="${escapeHtml(item.id)}">Abrir</button>
          <button class="secondary" data-duplicate="${escapeHtml(item.id)}">Duplicar</button>
          <button class="secondary" data-compare="${escapeHtml(item.id)}">Comparar</button>
          <button class="secondary" data-pdf="${escapeHtml(item.id)}">PDF</button>
          <button class="secondary" data-html="${escapeHtml(item.id)}">HTML</button>
          ${item.archived ? `<button class="secondary" data-restore="${escapeHtml(item.id)}">Restaurar</button><button class="secondary danger" data-delete="${escapeHtml(item.id)}">Excluir</button>` : `<button class="secondary" data-archive="${escapeHtml(item.id)}">Arquivar</button>`}
        </div>
      </div>
    `;
  }

  function renderAnalysisList(items, targetId) {
    const target = $(targetId);
    if (!items.length) {
      target.innerHTML = `<div class="notice">Nenhuma análise encontrada.</div>`;
      return;
    }
    target.innerHTML = items.map(historyCardHtml).join("");
    target.querySelectorAll("[data-open]").forEach((btn) => btn.addEventListener("click", () => openAnalysis(btn.dataset.open)));
    target.querySelectorAll("[data-duplicate]").forEach((btn) => btn.addEventListener("click", () => duplicateAnalysis(btn.dataset.duplicate)));
    target.querySelectorAll("[data-compare]").forEach((btn) => btn.addEventListener("click", () => addAnalysisToSession(btn.dataset.compare)));
    target.querySelectorAll("[data-pdf]").forEach((btn) => btn.addEventListener("click", () => exportAnalysisFile(btn.dataset.pdf, "pdf")));
    target.querySelectorAll("[data-html]").forEach((btn) => btn.addEventListener("click", () => exportAnalysisFile(btn.dataset.html, "html")));
    target.querySelectorAll("[data-archive]").forEach((btn) => btn.addEventListener("click", () => archiveAnalysis(btn.dataset.archive, true)));
    target.querySelectorAll("[data-restore]").forEach((btn) => btn.addEventListener("click", () => archiveAnalysis(btn.dataset.restore, false)));
    target.querySelectorAll("[data-delete]").forEach((btn) => btn.addEventListener("click", () => deleteAnalysis(btn.dataset.delete)));
  }

  function renderFilteredHistory() {
    renderAnalysisList(filterHistoryItems(state.historyItems), "historyList");
  }

  async function loadDashboard() {
    state.dashboard = await api("/api/dashboard");
    renderHome();
  }

  function renderHome() {
    if (!$("homeKpis")) return;
    const dashboard = state.dashboard || {};
    const totals = dashboard.totals || {};
    const analyses = Number(totals.analyses || 0);
    const score = analyses ? Math.min(100, Math.round((Number(totals.analysesWithSaving || 0) / analyses) * 100)) : 0;
    const scoreEl = $("homeOptimizationScore");
    if (scoreEl) {
      scoreEl.innerHTML = `<span>Otimização</span><strong>${analyses ? `${score}%` : "-"}</strong><em>${analyses ? "análises com oportunidade" : "sem histórico"}</em>`;
    }
    $("homeUpdatedAt").textContent = `Atualizado em ${formatLocalDate()}`;
    const best = dashboard.bestCostCarrier || {};
    const fastest = dashboard.fastestCarrier || {};
    $("homeKpis").innerHTML = [
      kpi(totals.analyses || 0, "análises ativas"),
      kpi(totals.archived || 0, "análises arquivadas"),
      kpi(money(totals.averageCost), "custo médio analisado"),
      kpi(money(totals.totalPotentialSaving), "economia potencial total", "good"),
      kpi(best.label || "-", "melhor transportadora por custo", "good", money(best.averageCost)),
      kpi(fastest.label || "-", "melhor transportadora por prazo", "info", days(fastest.averageDeadline)),
    ].join("");

    const insights = dashboard.opportunities || [];
    $("homeInsights").innerHTML = insights.length
      ? insights.map((item) => `<div class="insight-item">${escapeHtml(item)}</div>`).join("")
      : `<div class="notice">Nenhuma oportunidade calculada ainda. Gere uma análise para popular a visão executiva.</div>`;

    const carriers = dashboard.carrierRanking || [];
    $("homeCarrierRanking").innerHTML = carriers.length
      ? carriers.map((item, idx) => `<div class="ranking-item"><span class="rank-pos">${idx + 1}</span><div><strong>${escapeHtml(item.label || "-")}</strong><p>${escapeHtml(money(item.averageCost))} médio | ${escapeHtml(item.analyses || 0)} análise(s)${item.averageDeadline != null ? ` | ${escapeHtml(days(item.averageDeadline))}` : ""}</p></div></div>`).join("")
      : `<div class="notice">Sem ranking disponível.</div>`;

    const locations = dashboard.highestCostLocations || [];
    $("homeHighCostLocations").innerHTML = locations.length
      ? locations.map((item, idx) => `<div class="ranking-item"><span class="rank-pos warn">${idx + 1}</span><div><strong>${escapeHtml(item.label || "-")}</strong><p>CEP ${escapeHtml(item.cep || "-")} | ${escapeHtml(money(item.averageCost))} médio</p></div></div>`).join("")
      : `<div class="notice">Sem CEPs ou regiões com custo calculado.</div>`;

    const recent = dashboard.recent || [];
    $("homeRecent").innerHTML = recent.length
      ? recent.map((item) => `<div class="analysis-card compact"><div><strong>${escapeHtml(item.analysisName || "-")}</strong><p>${escapeHtml(displayDate(item.date) || item.date || "-")} | ${escapeHtml(item.place || "-")} | CEP ${escapeHtml(item.cep || "-")}</p><p>Melhor custo: ${escapeHtml(item.bestCarrier || "-")} | Economia: ${escapeHtml(money(item.saving))}</p></div><div class="actions"><button class="secondary" data-open="${escapeHtml(item.id)}">Abrir</button></div></div>`).join("")
      : `<div class="notice">Nenhuma análise recente.</div>`;
    $("homeRecent").querySelectorAll("[data-open]").forEach((btn) => btn.addEventListener("click", () => openAnalysis(btn.dataset.open)));
  }

  async function loadHistory() {
    const active = await api("/api/analyses?archived=false");
    const archived = await api("/api/analyses?archived=true");
    state.historyItems = active.items || [];
    state.archivedItems = archived.items || [];
    renderFilteredHistory();
    renderAnalysisList(state.archivedItems, "archivedList");
    await loadDashboard();
  }

  async function applyAnalysisToForm(analysis, duplicate = false) {
    $("analysisDateInput").value = formatLocalDate();
    $("analysisNameInput").value = duplicate ? `Cópia de ${analysis.analysisName || analysis.title || "análise"}` : (analysis.analysisName || analysis.title || "");
    $("analysisResponsibleInput").value = analysis.responsible || "";
    $("cepLookupInput").value = analysis.cep?.cep || "";
    state.lastResolvedCep = analysis.cep?.cep || "";
    state.sourceAnalysisId = duplicate ? null : analysis.id;

    if (analysis.location) {
      $("logisticsRegionSelect").value = analysis.location.logisticsRegion || analysis.filters?.logisticsRegion || "";
      await loadOptions();
      $("ufSelect").value = analysis.location.uf || "";
      await loadOptions();
      $("municipioSelect").value = analysis.location.municipio || "";
      await loadOptions();
      const estb = Array.isArray(analysis.location.estbs) && analysis.location.estbs.length
        ? analysis.location.estbs[0]
        : (analysis.location.estb && analysis.location.estb !== "Todos" ? String(analysis.location.estb).split(",")[0].trim() : "__ALL__");
      if ([...$("estbSelect").options].some((opt) => opt.value === estb)) $("estbSelect").value = estb;
      try {
        await refreshCarriers();
      } catch (_) {}
    }

    const main = analysis.summary?.mainCarrier || (analysis.rows || []).find((row) => row.role === "main")?.key || "";
    if (main) {
      $("mainCarrier").value = main;
    }
    const secondaries = analysis.summary?.secondaryCarriers || (analysis.rows || []).filter((row) => row.role === "secondary").map((row) => row.key);
    setSecondarySelection(secondaries);
    setCarrierOptions();
  }

  async function openAnalysis(id) {
    const analysis = await api(`/api/analyses/${id}`);
    await applyAnalysisToForm(analysis, false);
    renderResult(analysis, { setAsSource: true });
    setPage("nova");
    toast("Análise aberta. Ajuste os parâmetros e gere para criar nova versão.");
  }

  async function duplicateAnalysis(id) {
    const analysis = await api(`/api/analyses/${id}`);
    await applyAnalysisToForm(analysis, true);
    renderResult(analysis, { setAsSource: false });
    setPage("nova");
    toast("Análise duplicada no formulário. Gere a análise para salvar uma nova versão independente.");
  }

  async function addAnalysisToSession(id) {
    const analysis = await api(`/api/analyses/${id}`);
    renderResult(analysis, { setAsSource: false });
    setPage("nova");
    toast("Análise adicionada à comparação da sessão.");
  }

  async function archiveAnalysis(id, archived) {
    await api(`/api/analyses/${id}/archive`, { method: "POST", body: JSON.stringify({ archived }) });
    await loadHistory();
    if (state.currentAnalysis?.id === id && archived) $("resultPanel").hidden = true;
    toast(archived ? "Análise arquivada." : "Análise restaurada.");
  }

  async function deleteAnalysis(id) {
    if (!window.confirm("Excluir definitivamente esta análise?")) return;
    await api(`/api/analyses/${id}`, { method: "DELETE" });
    state.sessionAnalyses = state.sessionAnalyses.filter((analysis) => analysis.id !== id);
    renderSessionResults();
    await loadHistory();
    toast("Análise excluída.");
  }

  async function exportAnalysisFile(id, ext) {
    await downloadFile(`/api/analyses/${id}/export/${ext}`, `analise_frete_${id}.${ext}`);
    toast(`${ext.toUpperCase()} da análise gerado.`);
  }

  async function exportSession(ext) {
    if (!state.sessionAnalyses.length) {
      toast("Gere ao menos uma análise para exportar o consolidado.");
      return;
    }
    const extension = ext === "pdf" ? "pdf" : "html";
    await downloadFile(`/api/analyses/export/session/${ext}`, `comparativo_transportadoras_consolidado.${extension}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: state.sessionAnalyses.map((analysis) => analysis.id) }),
    });
    toast(`Arquivo ${extension.toUpperCase()} consolidado gerado.`);
  }

  function reuseSelectionForAnotherCep() {
    state.parameterIndex = state.sessionAnalyses.length + 1;
    state.sourceAnalysisId = null;
    $("cepLookupInput").value = "";
    $("logisticsRegionSelect").value = "";
    $("ufSelect").value = "";
    $("municipioSelect").value = "";
    resetEstbsToAll();
    state.lastResolvedCep = "";
    resetAnalysisMetadata(true);
    renderParameterInstances();
    $("cepLookupInput").focus();
    toast(`${sessionTitle()} criada. Informe o novo CEP; as transportadoras selecionadas serão reaproveitadas quando forem válidas para a localidade.`);
  }

  function bind() {
    $("adminLoginTrigger")?.addEventListener("click", () => {
      requestAdminLogin().catch((error) => toast(error.message));
    });
    document.querySelectorAll("[data-page]").forEach((btn) => {
      btn.addEventListener("click", () => setPage(btn.dataset.page));
    });
    document.querySelectorAll("[data-action='refresh'], [data-action='refresh-history']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await refreshFiles();
        await loadOptions();
        await loadHistory();
        toast("Dados atualizados.");
      });
    });
    document.querySelector("[data-action='toggle-density']")?.addEventListener("click", () => {
      document.body.classList.toggle("compact");
    });
    document.querySelector("[data-action='new-version']")?.addEventListener("click", () => {
      if (state.currentAnalysis) setPage("nova");
      toast(state.currentAnalysis ? "Edite os parâmetros e gere uma nova versão." : "Abra uma análise do histórico para versionar.");
    });
    $("btnRefreshCarriers")?.addEventListener("click", () => refreshCarriers().catch((e) => toast(e.message)));
    $("btnRunAnalysis").addEventListener("click", () => runAnalysis().catch((e) => {
      $("topStatus").textContent = "Falha na análise";
      toast(e.message);
    }));
    $("btnExportSessionPdf")?.addEventListener("click", () => exportSession("pdf").catch((e) => toast(e.message)));
    $("btnExportSessionHtml")?.addEventListener("click", () => exportSession("html").catch((e) => toast(e.message)));
    $("btnResetConfig").addEventListener("click", resetConfig);
    $("btnReuseSelection").addEventListener("click", reuseSelectionForAnotherCep);
    $("btnAddSecondary").addEventListener("click", () => addSecondarySlot());
    $("mainCarrier").addEventListener("change", setCarrierOptions);
    $("estbSelect").addEventListener("change", refreshCarriersIfReady);
    $("btnPreviewRefresh").addEventListener("click", () => loadPreview().catch((e) => toast(e.message)));
    $("previewKind").addEventListener("change", () => loadPreview().catch((e) => toast(e.message)));
    $("previewFilter").addEventListener("input", () => {
      window.clearTimeout(loadPreview.timer);
      loadPreview.timer = window.setTimeout(() => loadPreview().catch((e) => toast(e.message)), 250);
    });
    ["historyFilterDate", "historyFilterName", "historyFilterResponsible", "historyFilterCep", "historyFilterCarrier", "historyFilterBestCarrier", "historyFilterStatus"].forEach((id) => {
      $(id)?.addEventListener("input", renderFilteredHistory);
      $(id)?.addEventListener("change", renderFilteredHistory);
    });
    $("cepLookupInput").addEventListener("input", (event) => {
      event.target.value = event.target.value.replace(/\D/g, "").slice(0, 8);
      if (event.target.value.length < 8) state.lastResolvedCep = "";
      if (event.target.value.length === 8) resolveCepIntoLocation().catch((e) => {
        $("topStatus").textContent = "Falha ao localizar CEP";
        toast(e.message);
      });
    });
    $("logisticsRegionSelect").addEventListener("change", async () => {
      $("ufSelect").value = "";
      $("municipioSelect").value = "";
      state.lastResolvedCep = "";
      resetEstbsToAll();
      await loadOptions();
    });
    $("ufSelect").addEventListener("change", async () => {
      $("municipioSelect").value = "";
      state.lastResolvedCep = "";
      resetEstbsToAll();
      await loadOptions();
    });
    $("municipioSelect").addEventListener("change", async () => {
      state.lastResolvedCep = "";
      resetEstbsToAll();
      await loadOptions();
      refreshCarriersIfReady();
    });
  }

  async function init() {
    resetConfig();
    resetAnalysisMetadata(true);
    bind();
    renderParameterInstances();
    renderHome();
    await refreshFiles();
    await refreshAdminStatus();
    await loadOptions();
    addSecondarySlot();
    await loadPreview();
    await loadHistory();
    if ($("cepLookupInput").value.replace(/\D/g, "").length === 8) {
      await resolveCepIntoLocation(true);
    }
    $("topStatus").textContent = "Pronto";
  }

  init().catch((error) => {
    $("topStatus").textContent = "Erro";
    toast(error.message);
  });
})();
