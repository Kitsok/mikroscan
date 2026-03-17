const VISIBLE_INTERFACE_TYPES = new Set(["vlan", "pppoe-out", "wg", "zerotier"]);
const H_SPACING = 220;
const V_SPACING = 92;
const NODE_WIDTH = 172;
const NODE_HEIGHT = 54;
const PADDING = 56;

const CARD_STYLE = `
  :host {
    display: block;
    --app-bg: var(--lovelace-background, #f4f6fb);
    --surface: var(--card-background-color, rgba(255, 255, 255, 0.96));
    --surface-strong: var(--ha-card-background, #ffffff);
    --ink: var(--primary-text-color, #1f2937);
    --muted: var(--secondary-text-color, #667085);
    --line: color-mix(in srgb, var(--divider-color, #cfd8e3) 86%, transparent);
    --accent: var(--primary-color, #1d6fd6);
    --device: #2b6cb0;
    --host: #4f8a3a;
    --segment: #7a4ea3;
    --logical: #b36b00;
  }
  * {
    box-sizing: border-box;
  }
  ha-card {
    overflow: hidden;
    background: var(--surface-strong);
  }
  .app-shell {
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    min-height: 520px;
    background: var(--app-bg);
    color: var(--ink);
    font-family: var(
      --paper-font-body1_-_font-family,
      "Segoe UI",
      Roboto,
      Arial,
      sans-serif
    );
  }
  .topbar {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 16px;
    padding: 12px 14px;
    border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    backdrop-filter: blur(12px);
  }
  .title-block h1 {
    margin: 0;
    font-size: 1.02rem;
    font-weight: 700;
    line-height: 1.05;
  }
  .eyebrow {
    margin-bottom: 4px;
    color: var(--accent);
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .build-id {
    margin-top: 3px;
    color: var(--muted);
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .topbar-controls {
    display: flex;
    align-items: end;
    gap: 10px;
    min-width: 0;
  }
  .scan-field {
    display: grid;
    gap: 4px;
    min-width: 170px;
    color: var(--muted);
    font-size: 0.68rem;
    font-weight: 700;
  }
  .scan-field input {
    width: 100%;
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 7px 9px;
    background: var(--surface-strong);
    color: var(--ink);
    font-size: 0.78rem;
  }
  .action-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
  }
  .icon-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    min-height: 32px;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--surface-strong);
    color: var(--ink);
    cursor: pointer;
    transition: transform 120ms ease, background 120ms ease, border-color 120ms ease;
  }
  .icon-button:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--accent) 45%, var(--line));
    background: color-mix(in srgb, var(--accent) 9%, var(--surface-strong));
  }
  .icon-button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    transform: none;
  }
  .icon {
    font-size: 0.84rem;
    line-height: 1;
  }
  .status-summary {
    min-width: 140px;
    color: var(--muted);
    font-size: 0.7rem;
    line-height: 1.25;
    text-align: right;
  }
  .map-shell {
    position: relative;
    min-height: 0;
  }
  .canvas-wrapper {
    position: relative;
    overflow: auto;
    min-height: 440px;
    height: 100%;
    background:
      linear-gradient(90deg, color-mix(in srgb, var(--line) 36%, transparent) 1px, transparent 1px),
      linear-gradient(color-mix(in srgb, var(--line) 36%, transparent) 1px, transparent 1px),
      var(--app-bg);
    background-size: 32px 32px, 32px 32px, auto;
  }
  .edge-layer,
  .edge-label-layer,
  .node-layer {
    position: absolute;
    inset: 0;
  }
  .edge-layer,
  .edge-label-layer {
    pointer-events: none;
  }
  .edge-layer {
    overflow: visible;
  }
  .edge-line {
    stroke: color-mix(in srgb, var(--muted) 48%, transparent);
    stroke-width: 2;
    fill: none;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .edge-label {
    position: absolute;
    transform: translate(-50%, -50%);
    padding: 3px 7px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: color-mix(in srgb, var(--surface-strong) 92%, transparent);
    color: var(--muted);
    font-size: 0.63rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    white-space: nowrap;
    box-shadow: 0 4px 10px rgba(15, 23, 42, 0.08);
  }
  .node-layer {
    pointer-events: none;
  }
  .topology-node {
    position: absolute;
    width: ${NODE_WIDTH}px;
    min-height: ${NODE_HEIGHT}px;
    padding: 7px 9px;
    border: 1px solid var(--line);
    border-left-width: 5px;
    border-radius: 12px;
    background: var(--surface-strong);
    box-shadow: none;
    pointer-events: auto;
    user-select: none;
    cursor: grab;
  }
  .topology-node.selected {
    outline: 2px solid color-mix(in srgb, var(--accent) 30%, transparent);
  }
  .topology-node.device { border-left-color: var(--device); }
  .topology-node.host { border-left-color: var(--host); }
  .topology-node.segment { border-left-color: var(--segment); }
  .topology-node.interface { border-left-color: var(--logical); }
  .topology-node.offline {
    opacity: 0.64;
    border-color: color-mix(in srgb, var(--muted) 60%, var(--line));
    border-left-color: var(--muted);
    color: color-mix(in srgb, var(--ink) 72%, var(--muted));
  }
  .node-kind {
    margin-bottom: 2px;
    color: var(--muted);
    font-size: 0.56rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .node-label {
    font-size: 0.8rem;
    font-weight: 700;
    line-height: 1.18;
    word-break: break-word;
  }
  .node-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 6px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 14%, transparent);
    color: var(--accent);
    font-size: 0.64rem;
    font-weight: 700;
  }
  .details-drawer {
    position: absolute;
    top: 14px;
    right: 14px;
    width: min(300px, calc(100% - 28px));
    max-height: calc(100% - 28px);
    overflow: auto;
    padding: 14px;
    border: 1px solid var(--line);
    border-radius: 16px;
    background: color-mix(in srgb, var(--surface-strong) 94%, transparent);
    box-shadow: 0 18px 42px rgba(15, 23, 42, 0.16);
    backdrop-filter: blur(16px);
    opacity: 0;
    pointer-events: none;
    transform: translateY(8px);
    transition: opacity 140ms ease, transform 140ms ease;
  }
  .details-drawer.open {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
  }
  .drawer-close {
    position: absolute;
    top: 10px;
    right: 10px;
    width: 28px;
    height: 28px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--surface-strong);
    color: var(--muted);
    cursor: pointer;
  }
  .drawer-section + .drawer-section {
    margin-top: 16px;
  }
  .drawer-title {
    margin-bottom: 8px;
    color: var(--muted);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .details-body dl {
    display: grid;
    grid-template-columns: minmax(72px, auto) minmax(0, 1fr);
    gap: 6px 10px;
    margin: 0;
  }
  .details-body dt {
    color: var(--muted);
    font-weight: 700;
  }
  .details-body dd {
    margin: 0;
    word-break: break-word;
  }
  .unresolved-list {
    color: var(--muted);
    font-size: 0.78rem;
    line-height: 1.35;
  }
  .unresolved-list ul {
    margin: 0;
    padding-left: 18px;
  }
  .error {
    color: var(--error-color, #db4437);
    font-weight: 700;
  }
`;

class MikroscanMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {
      title: "Mikroscan Map",
      show_controls: true,
      scan_range: "",
    };
    this._hass = null;
    this._state = {
      topology: null,
      status: null,
      nodeMap: new Map(),
      visibleTree: [],
      treeNodes: [],
      selectedId: null,
      collapsed: new Set(),
      manualPositions: new Map(),
      drag: null,
      saveTimer: null,
      saveInFlight: false,
      viewScale: 1,
      zoomMultiplier: 1,
      topologyGeneratedAt: "",
      parentMap: new Map(),
      pendingTopologyReload: false,
      renderedPositions: new Map(),
    };
    this._resizeObserver = null;
    this._pollTimer = null;
    this._boundPointerMove = (event) => this._onPointerMove(event);
    this._boundPointerUp = (event) => this._onPointerUp(event);
    this._boundPointerCancel = () => this._onPointerCancel();
    this._boundResize = () => {
      if (this._state.topology) {
        this._renderCanvas();
      }
    };
  }

  setConfig(config) {
    this._config = {
      title: "Mikroscan Map",
      show_controls: true,
      scan_range: "",
      ...config,
    };
    this._renderShell();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.shadowRoot.innerHTML) {
      this._renderShell();
    }
    if (!this._state.topology) {
      this._loadAll();
    }
  }

  disconnectedCallback() {
    window.removeEventListener("pointermove", this._boundPointerMove);
    window.removeEventListener("pointerup", this._boundPointerUp);
    window.removeEventListener("pointercancel", this._boundPointerCancel);
    window.removeEventListener("resize", this._boundResize);
    this._resizeObserver?.disconnect();
    if (this._pollTimer) {
      window.clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }

  getCardSize() {
    return 10;
  }

  static getConfigElement() {
    return document.createElement("div");
  }

  static getStubConfig() {
    return { type: "custom:mikroscan-map", title: "Mikroscan Map" };
  }

  _renderShell() {
    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLE}</style>
      <ha-card>
        <div class="app-shell">
          <header class="topbar">
            <div class="title-block">
              <div class="eyebrow">Mikroscan</div>
              <h1 id="map-title">${this._escapeHtml(this._config.title || "Mikroscan Map")}</h1>
              <div id="build-id" class="build-id">build unknown</div>
            </div>
            <div class="topbar-controls">
              <label class="scan-field">
                <span>Scan range</span>
                <input id="scan-range" type="text" placeholder="192.168.1.0/24">
              </label>
              ${this._config.show_controls === false ? "" : `
                <div class="action-row">
                  <button id="refresh-topology" class="icon-button" type="button" title="Reload topology" aria-label="Reload topology">
                    <span class="icon" aria-hidden="true">&#8635;</span>
                  </button>
                  <button id="scan-network" class="icon-button" type="button" title="Refresh from devices" aria-label="Refresh from devices">
                    <span class="icon" aria-hidden="true">&#9673;</span>
                  </button>
                  <button id="reset-layout" class="icon-button" type="button" title="Reset layout" aria-label="Reset layout">
                    <span class="icon" aria-hidden="true">&#8864;</span>
                  </button>
                </div>
              `}
              <div id="status-summary" class="status-summary">Loading…</div>
            </div>
          </header>
          <main class="map-shell">
            <div id="canvas-wrapper" class="canvas-wrapper">
              <svg id="edge-layer" class="edge-layer"></svg>
              <div id="edge-label-layer" class="edge-label-layer"></div>
              <div id="node-layer" class="node-layer"></div>
            </div>
            <aside id="details-drawer" class="details-drawer">
              <button id="close-drawer" class="drawer-close" type="button" aria-label="Close details drawer">&times;</button>
              <section class="drawer-section">
                <div class="drawer-title">Selected Object</div>
                <div id="node-details" class="details-body">Click a node to inspect it.</div>
              </section>
              <section class="drawer-section">
                <div class="drawer-title">Unresolved Hosts</div>
                <div id="unresolved-hosts" class="unresolved-list">No unresolved hosts.</div>
              </section>
            </aside>
          </main>
        </div>
      </ha-card>
    `;

    this._elements = {
      buildId: this.shadowRoot.getElementById("build-id"),
      mapTitle: this.shadowRoot.getElementById("map-title"),
      statusSummary: this.shadowRoot.getElementById("status-summary"),
      nodeLayer: this.shadowRoot.getElementById("node-layer"),
      edgeLayer: this.shadowRoot.getElementById("edge-layer"),
      edgeLabelLayer: this.shadowRoot.getElementById("edge-label-layer"),
      canvasWrapper: this.shadowRoot.getElementById("canvas-wrapper"),
      detailsDrawer: this.shadowRoot.getElementById("details-drawer"),
      closeDrawer: this.shadowRoot.getElementById("close-drawer"),
      nodeDetails: this.shadowRoot.getElementById("node-details"),
      unresolvedHosts: this.shadowRoot.getElementById("unresolved-hosts"),
      refreshTopology: this.shadowRoot.getElementById("refresh-topology"),
      scanNetwork: this.shadowRoot.getElementById("scan-network"),
      resetLayout: this.shadowRoot.getElementById("reset-layout"),
      scanRange: this.shadowRoot.getElementById("scan-range"),
    };

    window.removeEventListener("pointermove", this._boundPointerMove);
    window.removeEventListener("pointerup", this._boundPointerUp);
    window.removeEventListener("pointercancel", this._boundPointerCancel);
    window.removeEventListener("resize", this._boundResize);
    window.addEventListener("pointermove", this._boundPointerMove);
    window.addEventListener("pointerup", this._boundPointerUp);
    window.addEventListener("pointercancel", this._boundPointerCancel);
    window.addEventListener("resize", this._boundResize);

    this._elements.refreshTopology?.addEventListener("click", async () => {
      await this._loadStatus();
      await this._loadTopology();
    });
    this._elements.scanNetwork?.addEventListener("click", async () => {
      try {
        await this._handleScan();
      } catch (error) {
        this._elements.nodeDetails.innerHTML = `<div class="error">${this._escapeHtml(error.message)}</div>`;
        this._elements.detailsDrawer.classList.add("open");
      }
    });
    this._elements.resetLayout?.addEventListener("click", async () => {
      this._state.manualPositions = new Map();
      this._state.zoomMultiplier = 1;
      this._renderCanvas();
      await this._persistLayout();
    });
    this._elements.closeDrawer?.addEventListener("click", () => {
      this._state.selectedId = null;
      this._renderDetails();
      this._updateSelectedNodeClasses();
    });
    this._elements.canvasWrapper?.addEventListener("click", () => {
      this._state.selectedId = null;
      this._renderDetails();
      this._updateSelectedNodeClasses();
    });
    this._elements.canvasWrapper?.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        const direction = event.deltaY < 0 ? 1.1 : 0.9;
        this._state.zoomMultiplier = Math.max(0.6, Math.min(3, this._state.zoomMultiplier * direction));
        this._renderCanvas();
      },
      { passive: false },
    );

    if (typeof ResizeObserver !== "undefined" && this._elements.canvasWrapper) {
      this._resizeObserver?.disconnect();
      this._resizeObserver = new ResizeObserver(() => {
        if (this._state.topology) {
          this._renderCanvas();
        }
      });
      this._resizeObserver.observe(this._elements.canvasWrapper);
    }

    if (this._pollTimer) {
      window.clearInterval(this._pollTimer);
    }
    this._pollTimer = window.setInterval(async () => {
      if (!this._hass) {
        return;
      }
      try {
        await this._loadStatus();
        const generatedAt = this._state.status?.topology?.generated_at || "";
        if (generatedAt && generatedAt !== this._state.topologyGeneratedAt && !this._state.status.running) {
          if (this._canReloadTopologyNow()) {
            await this._loadTopology();
          } else {
            this._state.pendingTopologyReload = true;
          }
        }
      } catch (_error) {
        return;
      }
    }, 3000);
  }

  async _callApi(method, path, body) {
    return this._hass.callApi(method, path, body);
  }

  _escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  _buildNodeIndex(model) {
    this._state.nodeMap = new Map((model.nodes || []).map((node) => [node.id, node]));
  }

  _getNodeData(nodeId) {
    return this._state.nodeMap.get(nodeId) || { id: nodeId, label: nodeId, kind: "unknown" };
  }

  _shouldRenderInterfaceNode(data) {
    return data.kind === "interface" && VISIBLE_INTERFACE_TYPES.has(data.type || "");
  }

  _displayNameForNode(data) {
    if (data.kind === "interface") {
      return data.name || data.label || data.id;
    }
    return data.label || data.name || data.id;
  }

  _interfaceEdgeName(data) {
    return data.name || data.label || "";
  }

  _buildEdgeLabel(localPort, remotePort) {
    if (localPort && remotePort) {
      return `${localPort} → ${remotePort}`;
    }
    return localPort || remotePort || "";
  }

  _createVisibleNode(nodeRef, edgeLabel = "") {
    return {
      id: nodeRef.node_id,
      nodeRef,
      data: this._getNodeData(nodeRef.node_id),
      edgeLabel,
      children: [],
    };
  }

  _attachVisibleChild(parent, nodeRef, localPort = "") {
    const data = this._getNodeData(nodeRef.node_id);
    const collapsed = data.kind !== "interface" && this._state.collapsed.has(nodeRef.node_id);
    const children = collapsed ? [] : (nodeRef.children || []);

    if (data.kind === "interface" && !this._shouldRenderInterfaceNode(data)) {
      const nextLocalPort = this._interfaceEdgeName(data) || localPort;
      children.forEach((child) => this._attachVisibleChild(parent, child, nextLocalPort));
      return;
    }

    const childNode = this._createVisibleNode(
      nodeRef,
      this._buildEdgeLabel(localPort, nodeRef.remote_interface || ""),
    );
    children.forEach((child) => this._attachVisibleChild(childNode, child, ""));
    parent.children.push(childNode);
  }

  _buildVisibleTree() {
    const roots = this._state.topology?.roots || [];
    this._state.visibleTree = roots.map((root) => {
      const visibleRoot = this._createVisibleNode(root, "");
      (root.children || []).forEach((child) => this._attachVisibleChild(visibleRoot, child, ""));
      return visibleRoot;
    });
  }

  _flattenTree() {
    const items = [];
    const edges = [];

    const visit = (node, depth, parentId) => {
      items.push({
        id: node.id,
        nodeRef: node.nodeRef,
        data: node.data,
        edgeLabel: node.edgeLabel,
        depth,
        x: 0,
        y: 0,
      });
      if (parentId) {
        edges.push({ from: parentId, to: node.id, label: node.edgeLabel });
      }
      (node.children || []).forEach((child) => visit(child, depth + 1, node.id));
    };

    this._state.visibleTree.forEach((root) => visit(root, 0, null));
    this._state.treeNodes = items;
    return { items, edges };
  }

  _applyLayeredLayout(items, availableHeight) {
    const maxRows = Math.max(1, Math.floor((availableHeight - PADDING * 2) / V_SPACING));
    const depthGroups = new Map();

    items.forEach((item) => {
      if (!depthGroups.has(item.depth)) {
        depthGroups.set(item.depth, []);
      }
      depthGroups.get(item.depth).push(item);
    });

    const depths = Array.from(depthGroups.keys()).sort((a, b) => a - b);
    const baseColumns = new Map();
    let nextBaseColumn = 0;

    depths.forEach((depth) => {
      const group = depthGroups.get(depth) || [];
      baseColumns.set(depth, nextBaseColumn);
      nextBaseColumn += Math.max(1, Math.ceil(group.length / maxRows));
    });

    items.forEach((item) => {
      const group = depthGroups.get(item.depth) || [];
      const index = group.findIndex((entry) => entry.id === item.id);
      const columnInDepth = Math.floor(index / maxRows);
      const rowInDepth = index % maxRows;
      const autoX = (baseColumns.get(item.depth) + columnInDepth) * H_SPACING;
      const autoY = rowInDepth * V_SPACING;
      const savedPosition = this._state.manualPositions.get(item.id);

      if (savedPosition) {
        item.x = savedPosition.x;
        item.y = savedPosition.y;
        return;
      }

      item.x = autoX;
      item.y = autoY;
    });
  }

  _buildNodePills(item) {
    const lines = [];
    if (item.data.offline) {
      lines.push("offline");
    }
    if (item.data.ip) {
      lines.push(item.data.ip);
    }
    if (item.data.kind === "segment") {
      lines.push(item.data.type || "segment");
    }
    if (item.data.kind === "interface" && item.data.type) {
      lines.push(item.data.type);
    }
    if (item.nodeRef.already_shown) {
      lines.push("already shown");
    }
    return lines.map((line) => `<span class="pill">${this._escapeHtml(line)}</span>`).join("");
  }

  _edgeAnchor(point, side) {
    if (side === "left") {
      return { x: point.x, y: point.y + NODE_HEIGHT / 2 };
    }
    if (side === "right") {
      return { x: point.x + NODE_WIDTH, y: point.y + NODE_HEIGHT / 2 };
    }
    if (side === "top") {
      return { x: point.x + NODE_WIDTH / 2, y: point.y };
    }
    return { x: point.x + NODE_WIDTH / 2, y: point.y + NODE_HEIGHT };
  }

  _chooseEdgeAnchors(from, to) {
    if (to.x >= from.x + NODE_WIDTH) {
      return { fromSide: "right", toSide: "left" };
    }
    if (to.x + NODE_WIDTH <= from.x) {
      return { fromSide: "left", toSide: "right" };
    }
    if (to.y >= from.y + NODE_HEIGHT) {
      return { fromSide: "bottom", toSide: "top" };
    }
    if (to.y + NODE_HEIGHT <= from.y) {
      return { fromSide: "top", toSide: "bottom" };
    }

    const fromCenterX = from.x + NODE_WIDTH / 2;
    const fromCenterY = from.y + NODE_HEIGHT / 2;
    const toCenterX = to.x + NODE_WIDTH / 2;
    const toCenterY = to.y + NODE_HEIGHT / 2;
    const dx = toCenterX - fromCenterX;
    const dy = toCenterY - fromCenterY;

    if (Math.abs(dx) >= Math.abs(dy)) {
      return dx >= 0
        ? { fromSide: "right", toSide: "left" }
        : { fromSide: "left", toSide: "right" };
    }

    return dy >= 0
      ? { fromSide: "bottom", toSide: "top" }
      : { fromSide: "top", toSide: "bottom" };
  }

  _buildEdgePath(from, to) {
    const { fromSide, toSide } = this._chooseEdgeAnchors(from, to);
    const start = this._edgeAnchor(from, fromSide);
    const end = this._edgeAnchor(to, toSide);
    return {
      start,
      end,
      labelX: start.x + (end.x - start.x) / 2,
      labelY: start.y + (end.y - start.y) / 2,
      d: `M ${start.x} ${start.y} L ${end.x} ${end.y}`,
    };
  }

  _buildParentMap() {
    const parentMap = new Map();
    const walk = (item, parentId = "") => {
      parentMap.set(item.node_id, parentId);
      (item.children || []).forEach((child) => walk(child, item.node_id));
    };
    (this._state.topology?.roots || []).forEach((root) => walk(root, ""));
    (this._state.topology?.unreached_roots || []).forEach((root) => walk(root, ""));
    this._state.parentMap = parentMap;
  }

  _applyLayout(layout) {
    const previousPositions = new Map(this._state.manualPositions);
    this._state.manualPositions = new Map();
    previousPositions.forEach((position, nodeId) => {
      if (!this._state.nodeMap.has(nodeId)) {
        return;
      }
      const currentParentId = this._state.parentMap.get(nodeId) || "";
      if ((position.parent_id || "") !== currentParentId) {
        return;
      }
      if (Number.isFinite(position.x) && Number.isFinite(position.y)) {
        this._state.manualPositions.set(nodeId, {
          x: position.x,
          y: position.y,
          parent_id: currentParentId,
        });
      }
    });

    Object.entries(layout?.positions || {}).forEach(([nodeId, position]) => {
      if (!this._state.nodeMap.has(nodeId) || typeof position !== "object") {
        return;
      }
      const data = this._state.nodeMap.get(nodeId) || {};
      if (data.kind !== "device" || data.type !== "mikrotik") {
        return;
      }
      const savedParentId = String(position.parent_id || "");
      const currentParentId = this._state.parentMap.get(nodeId) || "";
      if (savedParentId !== currentParentId || this._state.manualPositions.has(nodeId)) {
        return;
      }
      const x = Number(position.x);
      const y = Number(position.y);
      if (Number.isFinite(x) && Number.isFinite(y)) {
        this._state.manualPositions.set(nodeId, { x, y, parent_id: currentParentId });
      }
    });
  }

  _serializeLayout() {
    const positions = {};
    this._state.manualPositions.forEach((position, nodeId) => {
      const data = this._getNodeData(nodeId);
      if (data.kind !== "device" || data.type !== "mikrotik") {
        return;
      }
      const rendered = this._state.renderedPositions.get(nodeId) || position;
      positions[nodeId] = {
        x: rendered.x,
        y: rendered.y,
        parent_id: this._state.parentMap.get(nodeId) || "",
      };
    });
    return { positions };
  }

  _canReloadTopologyNow() {
    return !this._state.drag && !this._state.saveTimer && !this._state.saveInFlight;
  }

  _renderStatus() {
    const status = this._state.status || {};
    const topology = this._state.topology || {};
    const deviceCount = (topology.nodes || []).filter((node) => node.kind === "device").length;
    const hostCount = (topology.nodes || []).filter((node) => node.kind === "host").length;
    const unresolved = status.topology?.unresolved_host_count ?? 0;
    const mode = status.running ? `running ${status.current_action}` : "idle";

    this._elements.statusSummary.textContent =
      `${mode} • ${deviceCount} devices • ${hostCount} hosts • ${unresolved} unresolved`;
    const busy = Boolean(status.running);
    if (this._elements.scanNetwork) {
      this._elements.scanNetwork.disabled = busy;
    }
    if (this._elements.buildId) {
      this._elements.buildId.textContent =
        `v${status.app_version || "unknown"} • build ${status.build_id || "unknown"}`;
    }
    if (this._elements.scanRange && this.shadowRoot.activeElement !== this._elements.scanRange) {
      this._elements.scanRange.value = status.last_scan_range || status.default_scan_range || "";
    }
  }

  _renderDetails() {
    if (!this._state.selectedId) {
      this._elements.detailsDrawer.classList.remove("open");
      this._elements.nodeDetails.textContent = "Click a node to inspect it.";
      return;
    }

    const item = this._state.treeNodes.find((entry) => entry.id === this._state.selectedId);
    if (!item) {
      this._elements.detailsDrawer.classList.remove("open");
      this._elements.nodeDetails.textContent = "Selected node is not visible.";
      return;
    }

    const details = {
      label: this._displayNameForNode(item.data),
      kind: item.data.kind,
      type: item.data.type || "",
      ip: item.data.ip || "",
      mac: item.nodeRef.display_mac || item.data.mac || "",
      device: item.data.device || "",
      edge: item.edgeLabel || "",
      remote_interface: item.nodeRef.remote_interface || "",
      hostname: item.data.hostname || "",
      running: item.data.running || "",
      port: item.data.port || "",
      already_shown: item.nodeRef.already_shown ? "true" : "",
    };

    const rows = Object.entries(details)
      .filter(([, value]) => value)
      .map(([key, value]) => `<dt>${this._escapeHtml(key)}</dt><dd>${this._escapeHtml(value)}</dd>`)
      .join("");

    this._elements.nodeDetails.innerHTML = `<dl>${rows}</dl>`;
    this._elements.detailsDrawer.classList.add("open");
  }

  _renderUnresolvedHosts() {
    const hosts = this._state.topology?.unresolved_hosts || [];
    if (!hosts.length) {
      this._elements.unresolvedHosts.textContent = "No unresolved hosts.";
      return;
    }
    this._elements.unresolvedHosts.innerHTML = `<ul>${hosts
      .map((host) => {
        const label = [host.label || host.ip || host.id, host.ip, host.mac].filter(Boolean).join(" — ");
        return `<li>${this._escapeHtml(label)}</li>`;
      })
      .join("")}</ul>`;
  }

  _updateSelectedNodeClasses() {
    const nodes = this._elements.nodeLayer.querySelectorAll(".topology-node");
    nodes.forEach((node) => {
      if (node.dataset.nodeId === this._state.selectedId) {
        node.classList.add("selected");
      } else {
        node.classList.remove("selected");
      }
    });
  }

  _renderCanvas() {
    this._buildVisibleTree();
    const { items, edges } = this._flattenTree();
    const availableHeight = Math.max(this._elements.canvasWrapper.clientHeight - 12, NODE_HEIGHT);
    this._applyLayeredLayout(items, availableHeight);
    const width = Math.max(...items.map((item) => item.x), 0) + NODE_WIDTH + PADDING * 2;
    const height = Math.max(...items.map((item) => item.y), 0) + NODE_HEIGHT + PADDING * 2;
    const availableWidth = Math.max(this._elements.canvasWrapper.clientWidth - 12, NODE_WIDTH);
    const fitScale = Math.max(0.85, Math.min(1, (availableWidth * 0.98) / Math.max(width, 1)));
    const scale = Math.max(0.5, Math.min(2.5, fitScale * this._state.zoomMultiplier));
    const offsetX = Math.max(0, (availableWidth - width * scale) / 2);
    const offsetY = 8;
    this._state.viewScale = scale;

    this._elements.nodeLayer.style.width = `${width}px`;
    this._elements.nodeLayer.style.height = `${height}px`;
    this._elements.nodeLayer.style.transformOrigin = "top left";
    this._elements.nodeLayer.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

    this._elements.edgeLabelLayer.style.width = `${width}px`;
    this._elements.edgeLabelLayer.style.height = `${height}px`;
    this._elements.edgeLabelLayer.style.transformOrigin = "top left";
    this._elements.edgeLabelLayer.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

    this._elements.edgeLayer.setAttribute("width", String(width));
    this._elements.edgeLayer.setAttribute("height", String(height));
    this._elements.edgeLayer.setAttribute("viewBox", `0 0 ${width} ${height}`);
    this._elements.edgeLayer.style.transformOrigin = "top left";
    this._elements.edgeLayer.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

    const positions = new Map(
      items.map((item) => [
        item.id,
        {
          x: item.x + PADDING,
          y: item.y + PADDING,
        },
      ]),
    );
    this._state.renderedPositions = new Map(
      items.map((item) => [item.id, { x: item.x, y: item.y }]),
    );

    this._elements.edgeLayer.innerHTML = edges
      .map((edge) => {
        const from = positions.get(edge.from);
        const to = positions.get(edge.to);
        if (!from || !to) {
          return "";
        }
        const route = this._buildEdgePath(from, to);
        return `<path class="edge-line" d="${route.d}" />`;
      })
      .join("");

    this._elements.edgeLabelLayer.innerHTML = edges
      .map((edge) => {
        if (!edge.label) {
          return "";
        }
        const from = positions.get(edge.from);
        const to = positions.get(edge.to);
        if (!from || !to) {
          return "";
        }
        const route = this._buildEdgePath(from, to);
        return `<div class="edge-label" style="left:${route.labelX}px;top:${route.labelY}px">${this._escapeHtml(edge.label)}</div>`;
      })
      .join("");

    this._elements.nodeLayer.innerHTML = "";
    items.forEach((item) => {
      const node = document.createElement("article");
      node.className = `topology-node ${item.data.kind}`;
      if (item.data.offline) {
        node.classList.add("offline");
      }
      if (this._state.selectedId === item.id) {
        node.classList.add("selected");
      }
      node.dataset.nodeId = item.id;
      node.style.left = `${item.x + PADDING}px`;
      node.style.top = `${item.y + PADDING}px`;
      node.innerHTML = `
        <div class="node-kind">${this._escapeHtml(item.data.kind)}</div>
        <div class="node-label">${this._escapeHtml(this._displayNameForNode(item.data))}</div>
        <div class="node-meta">${this._buildNodePills(item)}</div>
      `;

      node.addEventListener("click", (event) => {
        event.stopPropagation();
        this._state.selectedId = item.id;
        this._renderDetails();
        this._updateSelectedNodeClasses();
      });

      node.addEventListener("dblclick", (event) => {
        event.stopPropagation();
        if ((item.nodeRef.children || []).length && item.data.kind !== "host") {
          if (this._state.collapsed.has(item.id)) {
            this._state.collapsed.delete(item.id);
          } else {
            this._state.collapsed.add(item.id);
          }
          this._renderCanvas();
          this._renderDetails();
        }
      });

      node.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        this._state.drag = {
          pointerId: event.pointerId,
          nodeId: item.id,
          startX: event.clientX,
          startY: event.clientY,
          base: this._state.renderedPositions.get(item.id) || { x: item.x, y: item.y },
        };
      });

      this._elements.nodeLayer.appendChild(node);
    });
  }

  _renderAll() {
    this._renderStatus();
    this._renderUnresolvedHosts();
    this._renderDetails();
    this._renderCanvas();
  }

  async _loadTopology() {
    this._state.topology = await this._callApi("GET", "api/mikroscan/topology");
    this._buildNodeIndex(this._state.topology);
    this._buildParentMap();
    const layout = await this._callApi("GET", "api/mikroscan/layout");
    this._applyLayout(layout);
    this._state.topologyGeneratedAt = this._state.topology.generated_at || "";
    this._elements.mapTitle.textContent = this._config.title || "Mikroscan Map";
    this._renderAll();
  }

  async _loadStatus() {
    this._state.status = await this._callApi("GET", "api/mikroscan/status");
    this._renderStatus();
  }

  async _loadAll() {
    if (!this._hass) {
      return;
    }
    this._elements.statusSummary.textContent = "Loading topology…";
    const [status, topology, layout] = await Promise.all([
      this._callApi("GET", "api/mikroscan/status"),
      this._callApi("GET", "api/mikroscan/topology"),
      this._callApi("GET", "api/mikroscan/layout"),
    ]);
    this._state.status = status;
    this._state.topology = topology;
    this._state.topologyGeneratedAt = topology.generated_at || "";
    this._buildNodeIndex(topology);
    this._buildParentMap();
    this._applyLayout(layout);
    this._renderAll();
  }

  async _persistLayout() {
    this._state.saveInFlight = true;
    try {
      await this._callApi("POST", "api/mikroscan/layout", this._serializeLayout());
    } finally {
      this._state.saveInFlight = false;
    }
  }

  _scheduleLayoutSave() {
    if (this._state.saveTimer) {
      window.clearTimeout(this._state.saveTimer);
    }
    this._state.saveTimer = window.setTimeout(async () => {
      this._state.saveTimer = null;
      try {
        await this._persistLayout();
        if (this._state.pendingTopologyReload) {
          this._state.pendingTopologyReload = false;
          await this._loadStatus();
          await this._loadTopology();
        }
      } catch (_error) {
        return;
      }
    }, 150);
  }

  async _waitForIdle() {
    for (;;) {
      await this._loadStatus();
      if (!this._state.status.running) {
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }

  async _handleScan() {
    const entered = this._elements.scanRange?.value.trim() || "";
    const scanRange = entered || this._config.scan_range || this._state.status?.last_scan_range || this._state.status?.default_scan_range || "";
    const payload = scanRange ? { ip_range: scanRange } : {};
    await this._hass.callService("mikroscan", "scan", payload);
    await this._waitForIdle();
    await this._loadStatus();
    if (this._state.status.last_success) {
      if (this._canReloadTopologyNow()) {
        await this._loadTopology();
      } else {
        this._state.pendingTopologyReload = true;
      }
      return;
    }
    throw new Error(this._state.status.last_error || "scan failed");
  }

  _onPointerMove(event) {
    if (!this._state.drag || this._state.drag.pointerId !== event.pointerId) {
      return;
    }
    const dx = event.clientX - this._state.drag.startX;
    const dy = event.clientY - this._state.drag.startY;
    this._state.manualPositions.set(this._state.drag.nodeId, {
      x: this._state.drag.base.x + dx / this._state.viewScale,
      y: this._state.drag.base.y + dy / this._state.viewScale,
      parent_id: this._state.parentMap.get(this._state.drag.nodeId) || "",
    });
    this._renderCanvas();
    this._renderDetails();
  }

  _onPointerUp(event) {
    if (!this._state.drag || this._state.drag.pointerId !== event.pointerId) {
      return;
    }
    this._state.drag = null;
    this._scheduleLayoutSave();
  }

  _onPointerCancel() {
    if (!this._state.drag) {
      return;
    }
    this._state.drag = null;
    this._scheduleLayoutSave();
  }
}

customElements.define("mikroscan-map-card", MikroscanMapCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "mikroscan-map",
  name: "Mikroscan Map",
  description: "Embed the Mikroscan topology map in a dashboard.",
});
