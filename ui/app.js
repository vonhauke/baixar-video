/* SnapYou - logica da interface.
   O Python (app_baixar_video.pyw) expoe a API em window.pywebview.api e manda
   eventos chamando SnapYou.receber({tipo, ...}). */

const $ = (id) => document.getElementById(id);

// erros de JavaScript ficam guardados aqui (o teste automatico confere)
window.__erros = [];
window.addEventListener("error", (e) => window.__erros.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) => window.__erros.push(String(e.reason)));

const SnapYou = (() => {
  const s = {
    estado: "inicio",       // inicio | encontrado | baixando | concluido
    ocupado: false,         // buscando informacoes ou baixando
    buscaId: 0,
    modo: "video",          // video (MP4) | audio (MP3)
    info: null,
    pastas: { video: { nome: "Vídeos", caminho: "" }, audio: { nome: "Música", caminho: "" } },
    arquivo: null,
    aviso: null,            // { acao } quando o aviso esta visivel
    convertendo: false,
    cancelando: false,
    fluxos: {},
  };
  let api = null;

  /* ---------- formatacao ---------- */
  function duracao(seg) {
    if (!seg && seg !== 0) return "";
    seg = Math.max(0, Math.round(seg));
    const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60), x = seg % 60;
    return h ? `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}` : `${m}:${String(x).padStart(2, "0")}`;
  }
  function velocidade(b) {
    if (!b) return "";
    const mb = b / 1e6;
    return mb >= 1 ? `${mb.toFixed(1).replace(".", ",")} MB/s` : `${Math.round(b / 1000)} KB/s`;
  }
  function tamanho(n) {
    if (!n) return "";
    if (n >= 1e9) return `${(n / 1e9).toFixed(1).replace(".", ",")} GB`;
    if (n >= 1e6) return `${Math.round(n / 1e6)} MB`;
    return `${Math.max(1, Math.round(n / 1000))} KB`;
  }
  const rotuloModo = () => (s.modo === "audio" ? "áudio" : "vídeo");
  const formato = () => (s.modo === "audio" ? "MP3" : "MP4");

  /* ---------- telas ---------- */
  function mostrar(estado) {
    s.estado = estado;
    const buscando = estado === "inicio" && s.ocupado;
    const comCartao = estado !== "inicio" || buscando;

    $("cartao").classList.toggle("oculto", !comCartao);
    document.querySelector(".cartao-video > .video:not(.esqueleto-video)").classList.toggle("oculto", buscando);
    $("esqueleto").classList.toggle("oculto", !buscando);
    $("rodape-encontrado").classList.toggle("oculto", estado !== "encontrado");
    $("painel-progresso").classList.toggle("oculto", estado !== "baixando");
    $("painel-sucesso").classList.toggle("oculto", estado !== "concluido");
    $("dica").classList.toggle("oculto", estado !== "inicio" || buscando);
    $("palco").classList.toggle("com-cartao", comCartao || !!s.aviso);
    $("aviso").classList.toggle("oculto", !s.aviso);
    atualizarControles();
  }

  function atualizarControles() {
    const baixando = s.estado === "baixando";
    const travado = s.ocupado;   // buscando ou baixando
    const texto = $("link").value.trim();

    $("link").disabled = travado;
    $("modo-video").disabled = $("modo-audio").disabled = travado;
    $("btn-colar").disabled = travado;
    $("composer").classList.toggle("desativado", travado);

    const podeBuscar = s.estado === "inicio" && !!texto && !s.ocupado;
    const btnBuscar = $("btn-buscar");
    btnBuscar.disabled = !podeBuscar && !(s.estado === "inicio" && s.ocupado);
    btnBuscar.innerHTML = s.estado === "inicio" && s.ocupado
      ? icone("loader-circle", 18, 2.25).replace('class="ic"', 'class="ic girando"')
      : icone("arrow-up", 18, 2.25);
    btnBuscar.title = s.ocupado && s.estado === "inicio" ? "Buscando…" : "Buscar vídeo (Enter)";
    if (s.estado === "inicio" && s.ocupado) btnBuscar.disabled = true;

    $("btn-baixar-texto").textContent = `Baixar ${rotuloModo()}`;
    $("btn-baixar").disabled = s.ocupado;
    $("btn-outro-texto").textContent = `Baixar outro ${rotuloModo()}`;

    const cancelar = $("btn-cancelar");
    if (baixando) {
      cancelar.textContent = s.convertendo ? "Finalizando…" : s.cancelando ? "Cancelando…" : "Cancelar";
      cancelar.disabled = s.convertendo || s.cancelando;
    }
  }

  function textoMudou() {
    if (s.ocupado) return;
    const texto = $("link").value.trim();
    if ((s.estado === "encontrado" || s.estado === "concluido") && s.info && texto !== s.info.url) {
      s.info = null;
      s.aviso = null;
      mostrar("inicio");
    } else {
      atualizarControles();
    }
  }

  /* ---------- aviso dentro da janela ---------- */
  function mostrarAviso(tipo, titulo, texto, detalhe, acao, rotuloAcao = "Tentar de novo") {
    s.aviso = { acao };
    const el = $("aviso");
    el.classList.toggle("aviso-perigo", tipo === "erro");
    $("aviso-icone").innerHTML = icone(tipo === "erro" ? "circle-alert" : "info", 18);
    $("aviso-titulo").textContent = titulo;
    $("aviso-texto").textContent = texto || "";
    $("aviso-texto").classList.toggle("oculto", !texto);
    $("aviso-detalhe").textContent = detalhe ? `Detalhe técnico: ${detalhe}` : "";
    $("aviso-detalhe").classList.toggle("oculto", !detalhe);
    $("aviso-acoes").classList.toggle("oculto", !acao);
    $("aviso-acao").lastChild.textContent = rotuloAcao;
    el.classList.remove("entra"); void el.offsetWidth; el.classList.add("entra");
    mostrar(s.estado);
  }
  function fecharAviso() { s.aviso = null; mostrar(s.estado); }
  function acaoDoAviso() {
    const acao = s.aviso && s.aviso.acao;
    s.aviso = null;
    if (acao) acao(); else mostrar(s.estado);
  }

  /* ---------- modo e pasta ---------- */
  function selecionarModo(modo) {
    s.modo = modo;
    $("modo-video").setAttribute("aria-pressed", String(modo === "video"));
    $("modo-audio").setAttribute("aria-pressed", String(modo === "audio"));
    atualizarPasta();
    atualizarControles();
  }
  function atualizarPasta() {
    const p = s.pastas[s.modo];
    $("pasta-nome").textContent = p.nome;
    $("pasta-caminho").textContent = p.caminho;
    $("btn-pasta").title = `Salvar em: ${p.caminho || p.nome}`;
  }
  async function trocarPasta() {
    const r = await api.trocar_pasta(s.modo);
    if (r) { s.pastas[s.modo] = r; atualizarPasta(); }
  }
  async function abrir(funcao, arg, titulo) {
    const erro = await funcao(arg);
    if (erro) mostrarAviso("erro", titulo, erro);
  }

  /* ---------- acoes ---------- */
  async function colar(textoPronto) {
    if (s.ocupado || s.estado === "baixando") return;
    if (s.estado === "concluido") novoDownload();
    let texto = textoPronto;
    if (texto == null) {
      texto = (await api.colar()) || "";
      if (!texto && navigator.clipboard) {
        try { texto = await navigator.clipboard.readText(); } catch (_) { /* sem permissao */ }
      }
    }
    texto = (texto || "").trim();
    if (texto) {
      $("link").value = texto;
      textoMudou();
      $("link").focus();
    }
  }

  function acaoPrincipal() {
    if (s.ocupado) return;
    if (s.estado === "inicio") buscar();
    else if (s.estado === "encontrado") baixar();
    else if (s.estado === "concluido") novoDownload();
  }

  function buscar() {
    const url = $("link").value.trim();
    if (!url || s.ocupado) return;
    s.ocupado = true;
    s.aviso = null;
    s.buscaId += 1;
    mostrar("inicio");
    api.buscar(url, s.modo, s.buscaId);
  }

  function baixar() {
    if (!s.info || s.ocupado) return;
    s.ocupado = true;
    s.convertendo = false;
    s.cancelando = false;
    s.aviso = null;
    s.fluxos = {};
    progresso(0);
    $("prog-titulo").textContent = "Baixando…";
    $("prog-vel").textContent = "Iniciando…";
    $("prog-eta").textContent = "";
    pintarEtapas("baixando");
    mostrar("baixando");
    api.baixar(s.info.url, s.modo);
  }

  function cancelar() {
    if (s.estado !== "baixando" || s.convertendo || s.cancelando) return;
    s.cancelando = true;
    $("prog-titulo").textContent = "Cancelando…";
    atualizarControles();
    api.cancelar();
  }

  function novoDownload() {
    s.info = null;
    s.arquivo = null;
    s.aviso = null;
    $("link").value = "";
    mostrar("inicio");
    $("link").focus();
  }

  /* ---------- cartao ---------- */
  function preencherCartao(d) {
    $("video-fonte").textContent = d.fonte || "Vídeo";
    $("video-titulo").textContent = d.titulo;
    $("video-titulo").title = d.titulo;
    $("duracao").textContent = duracao(d.duracao);
    const img = $("miniatura-img");
    img.classList.remove("carregada");
    img.removeAttribute("src");

    const qual = d.modo === "audio" ? (d.abr ? `${Math.round(d.abr)} kbps` : "") : (d.altura ? `${d.altura}p` : "");
    const tags = [];
    if (qual) tags.push(`<span class="tag tag-acento">${DS.escapar(qual)}</span>`);
    tags.push(`<span class="tag">${d.modo === "audio" ? "MP3" : "MP4"}</span>`);
    if (d.tamanho) tags.push(`<span class="tag">≈ ${tamanho(d.tamanho)}</span>`);
    $("video-tags").innerHTML = tags.join("");

    const partes = [];
    if (d.duracao) partes.push(duracao(d.duracao));
    if (qual) partes.push("melhor qualidade disponível");
    $("legenda-qualidade").textContent = partes.join(" · ");
  }

  function progresso(fracao) {
    $("prog-barra").firstElementChild.style.width = `${Math.round(fracao * 1000) / 10}%`;
    $("prog-pct").textContent = `${Math.floor(fracao * 100)}%`;
  }

  function pintarEtapas(etapa) {
    const conv = `Convertendo para ${formato()}`;
    const ordem = ["info", "baixando", "convertendo"];
    const atual = etapa === "pronto" ? 3 : ordem.indexOf(etapa);
    const nomes = ["Informações", "Baixando", conv];
    const html = nomes.map((nome, i) => {
      const classe = i < atual ? "feita" : i === atual ? "ativa" : "";
      const marca = i < atual ? icone("check", 10, 3.5) : "";
      const linha = i < 2 ? `<span class="trilho ${i < atual ? "feita" : ""}"></span>` : "";
      return `<span class="etapa ${classe}"><span class="marcador">${marca}</span>${nome}</span>${linha}`;
    }).join("");
    $("etapas").innerHTML = html;
    $("etapas-ok").innerHTML = html;
  }

  /* soma video + audio: sao dois arquivos baixados em sequencia */
  function atualizarBytes(d) {
    if (s.cancelando) return;
    s.fluxos[d.fluxo] = [d.baixado, d.total];
    const vals = Object.values(s.fluxos);
    const baixado = vals.reduce((a, [b]) => a + b, 0);
    const vistos = vals.reduce((a, [, t]) => a + t, 0);
    const total = Math.max((s.info && s.info.tamanho) || 0, vistos);
    const fracao = total ? Math.min(baixado / total, 1) : 0;
    progresso(fracao);
    const vel = velocidade(d.velocidade);
    const tam = tamanho(total);
    $("prog-vel").textContent = tam && vel ? `${tamanho(baixado) || "0 KB"} de ${tam} · ${vel}` : vel;
    let restante = d.eta;
    if (d.velocidade && total) restante = Math.max(total - baixado, 0) / d.velocidade;
    $("prog-eta").textContent = restante != null ? `faltam ${duracao(restante) || "0:00"}` : "";
  }

  /* ---------- eventos vindos do Python ---------- */
  function receber(ev) {
    switch (ev.tipo) {
      case "info":
        if (ev.id !== s.buscaId) return;
        s.info = ev;
        s.ocupado = false;
        preencherCartao(ev);
        mostrar("encontrado");
        $("btn-baixar").focus({ preventScroll: true });
        break;
      case "miniatura":
        if (ev.id !== s.buscaId || !s.info) return;
        if (ev.imagem) {
          const img = $("miniatura-img");
          img.onload = () => img.classList.add("carregada");
          img.src = ev.imagem;
        }
        break;
      case "erro_busca":
        if (ev.id !== s.buscaId) return;
        s.ocupado = false;
        s.estado = "inicio";
        mostrarAviso("erro", ev.titulo, ev.texto, ev.detalhe, buscar);
        $("link").focus();
        break;
      case "bytes":
        if (s.estado === "baixando") atualizarBytes(ev);
        break;
      case "convertendo":
        if (s.estado !== "baixando" || s.cancelando) return;
        s.convertendo = true;
        $("prog-titulo").textContent = `Convertendo para ${formato()}…`;
        progresso(1);
        $("prog-vel").textContent = "Quase pronto";
        $("prog-eta").textContent = "";
        pintarEtapas("convertendo");
        atualizarControles();
        break;
      case "concluido":
        s.ocupado = false;
        s.convertendo = false;
        s.cancelando = false;
        s.arquivo = ev.caminho;
        $("arquivo-nome").textContent = ev.nome;
        $("arquivo-nome").title = ev.caminho;
        $("arquivo-pasta").textContent = `Salvo em ${ev.pasta}`;
        pintarEtapas("pronto");
        mostrar("concluido");
        $("btn-outro").focus({ preventScroll: true });
        break;
      case "cancelado":
        s.ocupado = false;
        s.convertendo = false;
        s.cancelando = false;
        s.estado = "encontrado";
        mostrarAviso("info", "Download cancelado",
          "Os arquivos incompletos foram apagados. Você pode baixar de novo quando quiser.");
        break;
      case "erro":
        s.ocupado = false;
        s.convertendo = false;
        s.cancelando = false;
        s.estado = "encontrado";
        mostrarAviso("erro", ev.titulo, ev.texto, ev.detalhe, baixar);
        break;
    }
  }

  /* ---------- inicio ---------- */
  async function iniciar() {
    desenharIcones();
    pintarEtapas("baixando");
    api = await DS.api();
    const ini = await api.estado_inicial();
    s.pastas = ini.pastas;
    if (ini.mac) $("atalho").textContent = "⌘";
    atualizarPasta();
    mostrar("inicio");

    $("link").addEventListener("input", textoMudou);
    $("btn-buscar").onclick = acaoPrincipal;
    $("btn-baixar").onclick = baixar;
    $("btn-cancelar").onclick = cancelar;
    $("btn-outro").onclick = novoDownload;
    $("btn-colar").onclick = () => colar();
    $("modo-video").onclick = () => selecionarModo("video");
    $("modo-audio").onclick = () => selecionarModo("audio");
    $("menu-trocar").onclick = trocarPasta;
    $("menu-abrir").onclick = () => abrir(api.abrir_pasta, s.modo, "Não foi possível abrir a pasta");
    $("btn-abrir-arquivo").onclick = () => abrir(api.abrir_arquivo, s.arquivo, "Não foi possível abrir o arquivo");
    $("btn-mostrar-pasta").onclick = () => abrir(api.mostrar_na_pasta, s.arquivo, "Não foi possível mostrar o arquivo");
    $("aviso-fechar").onclick = fecharAviso;
    $("aviso-acao").onclick = acaoDoAviso;

    // Ctrl+V / Cmd+V em qualquer lugar da janela cola o link
    document.addEventListener("paste", (e) => {
      if (e.target === $("link")) return;   // o proprio campo ja cola
      e.preventDefault();
      colar((e.clipboardData && e.clipboardData.getData("text")) || null);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.isComposing) {
        const foco = document.activeElement;
        if (foco && foco.tagName === "BUTTON") return;   // o botao ja trata o Enter
        e.preventDefault();
        acaoPrincipal();
      } else if (e.key === "Escape") {
        if (s.estado === "baixando") cancelar();
        else if (s.aviso) fecharAviso();
      }
    });

    $("link").focus();
    document.documentElement.classList.add("pronto");
  }

  document.addEventListener("DOMContentLoaded", iniciar);
  return { receber, _s: s };
})();
