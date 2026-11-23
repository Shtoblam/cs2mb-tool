(() => {
  "use strict";
  const pages = ["overview","features","maps","safety","setup","faq"];
  const languageButton = document.getElementById("language-toggle");
  const demoData = {
    dust2: {name:"de_dust2", areas:"2,242", routes:"90", edges:"6,275", floor:"98.77%", indicator:"CT +8.9s"},
    mirage: {name:"de_mirage", areas:"2,544", routes:"99", edges:"6,381", floor:"99.06%", indicator:"CT +6.4s"},
    nuke: {name:"de_nuke", areas:"3,040", routes:"80", edges:"7,676", floor:"99.27%", indicator:"CT +5.2s"}
  };
  let activePage = "overview";
  let selectedDemoMap = "mirage";
  let selectedDemoView = "routes";

  function lang() { return document.documentElement.lang === "en" ? "en" : "ru"; }
  function safeStorageGet(key, fallback) {
    try { return localStorage.getItem(key) || fallback; } catch (_) { return fallback; }
  }
  function safeStorageSet(key, value) {
    try { localStorage.setItem(key, value); } catch (_) { /* Optional browser storage. */ }
  }
  function setLanguage(next) {
    const value = next === "en" ? "en" : "ru";
    document.documentElement.lang = value;
    document.querySelectorAll("[data-href-ru][data-href-en]").forEach((node) => {
      node.setAttribute("href", node.dataset["href-" + value]);
    });
    document.querySelectorAll("[data-ru][data-en]").forEach((node) => {
      const text = node.dataset[value];
      if (text !== undefined) node.innerHTML = text;
    });
    if (languageButton) {
      languageButton.textContent = value === "ru" ? "EN" : "RU";
      languageButton.setAttribute("aria-label", value === "ru" ? "Switch to English" : "Переключить на русский");
    }
    safeStorageSet("cs2mb-language", value);
    updateDemoMetrics();
  }

  function setPage(page, updateHash = true) {
    const next = pages.includes(page) ? page : "overview";
    activePage = next;
    document.querySelectorAll("[data-page-panel]").forEach((panel) => {
      const active = panel.dataset.pagePanel === next;
      panel.classList.toggle("is-active", active);
      panel.setAttribute("aria-hidden", active ? "false" : "true");
    });
    document.querySelectorAll("[data-page]").forEach((button) => {
      const active = button.dataset.page === next;
      button.classList.toggle("is-active", active);
      if (button.getAttribute("role") === "tab") button.setAttribute("aria-selected", active ? "true" : "false");
    });
    safeStorageSet("cs2mb-page", next);
    if (updateHash && window.location.hash !== "#" + next) history.pushState(null, "", "#" + next);
    window.scrollTo({top:0,behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
  }

  function setDemoMap(key) {
    if (!demoData[key]) return;
    selectedDemoMap = key;
    const data = demoData[key];
    const setText = (id, value) => { const n = document.getElementById(id); if (n) n.textContent = value; };
    setText("demo-map-name", data.name.toUpperCase());
    setText("demo-map-title", data.name);
    setText("demo-metric-areas", data.areas);
    setText("demo-metric-routes", data.routes);
    document.querySelectorAll("[data-demo-map]").forEach((button) => button.classList.toggle("is-active",button.dataset.demoMap===key));
    updateDemoMetrics();
    safeStorageSet("cs2mb-demo-map",key);
  }

  function setDemoView(view) {
    selectedDemoView = view === "geometry" ? "geometry" : "routes";
    document.querySelectorAll("[data-demo-view]").forEach((button) => {
      const active = button.dataset.demoView === selectedDemoView;
      button.classList.toggle("is-active",active);
      button.setAttribute("aria-pressed",active?"true":"false");
      button.setAttribute("aria-selected",active?"true":"false");
    });
    const stage=document.getElementById("demo-map-stage");
    if(stage) stage.classList.toggle("is-geometry",selectedDemoView==="geometry");
    updateDemoMetrics();
    safeStorageSet("cs2mb-demo-view",selectedDemoView);
  }

  function updateDemoMetrics() {
    const data=demoData[selectedDemoMap];
    const primary=document.getElementById("demo-metric-primary");
    const areas=document.getElementById("demo-metric-areas");
    const routes=document.getElementById("demo-metric-routes");
    if(!data||!primary||!areas||!routes)return;
    const metricLabels=document.querySelectorAll(".preview-metric .preview-label");
    const metricSmall=document.querySelectorAll(".preview-metric small");
    if(selectedDemoView==="geometry") {
      if(metricLabels[0])metricLabels[0].textContent=lang()==="ru"?"СООТВЕТСТВИЕ ПОЛА":"FLOOR MATCH";
      primary.innerHTML = 'FLOOR <strong>'+data.floor+'</strong>';
      areas.textContent = data.areas;
      routes.textContent = data.edges;
      if(metricLabels[1])metricLabels[1].textContent="NAV AREAS";
      if(metricLabels[2])metricLabels[2].textContent="GRAPH EDGES";
      if(metricSmall[0])metricSmall[0].textContent=lang()==="ru"?"Сопоставление пола":"Floor matching";
      if(metricSmall[1])metricSmall[1].textContent=lang()==="ru"?"Навигационных областей":"Navigation areas";
      if(metricSmall[2])metricSmall[2].textContent=lang()==="ru"?"Связей графа":"Graph edges";
    } else {
      if(metricLabels[0])metricLabels[0].textContent=lang()==="ru"?"ИНДИКАТОР ВРЕМЕНИ":"ROUTE-TIME INDICATOR";
      primary.innerHTML = 'CT <strong>'+data.indicator.replace("CT ","")+'</strong>';
      areas.textContent = data.areas;
      routes.textContent = data.routes;
      if(metricLabels[1])metricLabels[1].textContent="NAV AREAS";
      if(metricLabels[2])metricLabels[2].textContent="ROUTES";
      if(metricSmall[0])metricSmall[0].textContent=lang()==="ru"?"Предварительная оценка":"Preliminary estimate";
      if(metricSmall[1])metricSmall[1].textContent=lang()==="ru"?"Навигационных областей":"Navigation areas";
      if(metricSmall[2])metricSmall[2].textContent="Spawn → target";
    }
  }

  document.querySelectorAll("[data-page]").forEach((button) => {
    button.addEventListener("click", (event) => {
      if (button.tagName === "A") event.preventDefault();
      setPage(button.dataset.page);
    });
  });
  document.querySelectorAll("[data-demo-map]").forEach((button) => {
    button.addEventListener("click", () => setDemoMap(button.dataset.demoMap));
  });
  document.querySelectorAll("[data-demo-view]").forEach((button) => {
    button.addEventListener("click", () => setDemoView(button.dataset.demoView));
  });
  if(languageButton) languageButton.addEventListener("click",()=>setLanguage(lang()==="ru"?"en":"ru"));

  document.querySelectorAll('[role="tablist"]').forEach((tablist) => {
    tablist.addEventListener("keydown",(event)=>{
      if(event.key!=="ArrowLeft"&&event.key!=="ArrowRight")return;
      const tabs=[...tablist.querySelectorAll('[role="tab"]')];
      const index=tabs.indexOf(document.activeElement);
      if(index<0||!tabs.length)return;
      event.preventDefault();
      const delta=event.key==="ArrowRight"?1:-1;
      const next=tabs[(index+delta+tabs.length)%tabs.length];
      next.focus();next.click();
    });
  });

  document.addEventListener("keydown",(event)=>{
    const target=event.target;
    const typing=target&&(target.matches("input,textarea,select")||target.isContentEditable);
    if(!typing&&event.altKey&&/^[1-6]$/.test(event.key)) {
      event.preventDefault();setPage(pages[Number(event.key)-1]);return;
    }
    if(event.key==="Escape") {
      const search= document.getElementById("map-search");
      if(search&&document.activeElement===search)search.blur();
    }
  });
  window.addEventListener("popstate",()=>setPage(window.location.hash.slice(1),false));

  const savedLang=safeStorageGet("cs2mb-language","ru");
  const savedPage=safeStorageGet("cs2mb-page","overview");
  const hash=window.location.hash.slice(1);
  setLanguage(savedLang);
  setPage(pages.includes(hash)?hash:savedPage,false);
  setDemoMap(safeStorageGet("cs2mb-demo-map","mirage"));
  setDemoView(safeStorageGet("cs2mb-demo-view","routes"));
})();