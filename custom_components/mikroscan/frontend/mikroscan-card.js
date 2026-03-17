const H_SPACING = 210;
const V_SPACING = 76;
const NODE_WIDTH = 164;
const NODE_HEIGHT = 52;
const PADDING = 40;

const CARD_STYLE = `
  :host {
    display: block;
  }
  .shell {
    display: grid;
    gap: 10px;
    min-height: 300px;
    color: var(--primary-text-color);
  }
  ha-card {
    overflow: hidden;
  }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    padding: 10px 10px 0;
  }
  .toolbar h2 {
    margin: 0 auto 0 0;
    font-size: 0.92rem;
    font-weight: 700;
  }
  .toolbar mwc-button {
    --mdc-theme-primary: var(--primary-color);
  }
  .canvas {
    position: relative;
    overflow: auto;
    min-height: 300px;
    background:
      linear-gradient(90deg, rgba(120, 120, 120, 0.08) 1px, transparent 1px),
      linear-gradient(rgba(120, 120, 120, 0.08) 1px, transparent 1px),
      var(--card-background-color);
    background-size: 32px 32px, 32px 32px, auto;
    border-top: 1px solid var(--divider-color);
  }
  svg,
  .nodes {
    position: absolute;
    inset: 0;
  }
  svg {
    pointer-events: none;
  }
  .edge {
    stroke: rgba(120, 120, 120, 0.4);
    stroke-width: 2;
    fill: none;
  }
  .nodes {
    pointer-events: none;
  }
  .node {
    position: absolute;
    min-width: 132px;
    max-width: 190px;
    padding: 7px 9px;
    border-radius: 10px;
    background: var(--ha-card-background, var(--card-background-color));
    border: 1px solid var(--divider-color);
    box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0, 0, 0, 0.1));
    pointer-events: auto;
    user-select: none;
    cursor: grab;
  }
  .node.selected {
    outline: 2px solid color-mix(in srgb, var(--primary-color) 28%, transparent);
  }
  .node.device { border-left: 6px solid #1e6d92; }
  .node.interface { border-left: 6px solid #9a5d1d; }
  .node.host { border-left: 6px solid #567d2b; }
  .node.segment { border-left: 6px solid #74408f; }
  .kind {
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--secondary-text-color);
    font-weight: 700;
    margin-bottom: 2px;
  }
  .label {
    font-size: 0.8rem;
    font-weight: 700;
    line-height: 1.18;
    word-break: break-word;
  }
  .meta {
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
    background: color-mix(in srgb, var(--primary-color) 14%, transparent);
    color: var(--primary-color);
    font-size: 0.64rem;
    font-weight: 700;
  }
  .footer {
    display: grid;
    gap: 8px;
    padding: 8px 10px 10px;
    border-top: 1px solid var(--divider-color);
  }
  .status {
    color: var(--secondary-text-color);
    font-size: 0.78rem;
  }
  .details {
    font-size: 0.78rem;
    line-height: 1.3;
  }
  .details strong {
    display: inline-block;
    min-width: 76px;
  }
`;

class MikroscanMapBase extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._state = {
      topology: null,
      status: null,
      nodeMap: new Map(),
      selectedId: null,
      collapsed: new Set(),
      manualPositions: new Map(),
      drag: null,
      saveTimer: null,
      viewScale: 1,
    };
    this._resizeObserver = null;
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

  getCardSize() {
    return 8;
  }

  _renderShell() {
    if (!this.shadowRoot) {
      return;
    }

    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLE}</style>
      <ha-card>
        <div class="shell">
          <div class="toolbar">
            <h2>${this._escapeHtml(this._config.title || "Mikroscan Map")}</h2>
            ${this._config.show_controls === false ? "" : `
              <mwc-button id="refresh" label="Reload"></mwc-button>
              <mwc-button id="generate" label="Generate"></mwc-button>
              <mwc-button id="scan" label="Scan"></mwc-button>
            `}
          </div>
          <div class="canvas" id="canvas">
            <svg id="edges"></svg>
            <div class="nodes" id="nodes"></div>
          </div>
          <div class="footer">
            <div class="status" id="status">Loading…</div>
            <div class="details" id="details">Click a node to inspect it.</div>
          </div>
        </div>
      </ha-card>
    `;

    this._nodesEl = this.shadowRoot.getElementById("nodes");
    this._edgesEl = this.shadowRoot.getElementById("edges");
    this._canvasEl = this.shadowRoot.getElementById("canvas");
    this._statusEl = this.shadowRoot.getElementById("status");
    this._detailsEl = this.shadowRoot.getElementById("details");

    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () => this._loadAll());
    this.shadowRoot.getElementById("generate")?.addEventListener("click", () => this._generateTopology());
    this.shadowRoot.getElementById("scan")?.addEventListener("click", () => this._scan());

    window.addEventListener("pointermove", (event) => this._onPointerMove(event));
    window.addEventListener("pointerup", (event) => this._onPointerUp(event));
    window.addEventListener("pointercancel", () => {
      this._state.drag = null;
    });

    if (typeof ResizeObserver !== "undefined") {
      this._resizeObserver?.disconnect();
      this._resizeObserver = new ResizeObserver(() => {
        if (this._state.topology) {
          this._render();
        }
      });
      this._resizeObserver.observe(this._canvasEl);
    }
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

  async _loadAll() {
    if (!this._hass) {
      return;
    }
    this._statusEl.textContent = "Loading topology…";
    const [status, topology, layout] = await Promise.all([
      this._callApi("GET", "api/mikroscan/status"),
      this._callApi("GET", "api/mikroscan/topology"),
      this._callApi("GET", "api/mikroscan/layout"),
    ]);
    this._state.status = status;
    this._state.topology = topology;
    this._state.nodeMap = new Map((topology.nodes || []).map((node) => [node.id, node]));
    this._applyLayout(layout);
    this._render();
  }

  _applyLayout(layout) {
    this._state.manualPositions = new Map();
    Object.entries(layout?.positions || {}).forEach(([nodeId, position]) => {
      if (!this._state.nodeMap.has(nodeId) || typeof position !== "object") {
        return;
      }
      const dx = Number(position.dx);
      const dy = Number(position.dy);
      if (Number.isFinite(dx) && Number.isFinite(dy)) {
        this._state.manualPositions.set(nodeId, { dx, dy });
      }
    });
  }

  _serializeLayout() {
    const positions = {};
    this._state.manualPositions.forEach((position, nodeId) => {
      positions[nodeId] = { dx: position.dx, dy: position.dy };
    });
    return { positions };
  }

  _buildDisplayLabel(nodeRef) {
    const data = this._state.nodeMap.get(nodeRef.node_id) || {
      label: nodeRef.node_id,
      kind: nodeRef.kind,
    };
    const bits = [];
    if (nodeRef.remote_interface) {
      bits.push(`<${nodeRef.remote_interface}>`);
    }
    bits.push(data.label || data.name || nodeRef.node_id);
    return bits.join(" ");
  }

  _buildMetaLines(nodeRef) {
    const data = this._state.nodeMap.get(nodeRef.node_id) || {};
    const lines = [];
    if (data.ip) lines.push(data.ip);
    if (nodeRef.display_mac || data.mac) lines.push(nodeRef.display_mac || data.mac);
    if (data.type && data.kind === "interface") lines.push(data.type);
    if (nodeRef.already_shown) lines.push("already shown");
    return lines;
  }

  _flattenTree() {
    const items = [];
    const edges = [];
    let nextLeafY = 0;

    const visit = (nodeRef, depth, parentId) => {
      const data = this._state.nodeMap.get(nodeRef.node_id) || {
        kind: nodeRef.kind,
        label: nodeRef.node_id,
      };
      const children = this._state.collapsed.has(nodeRef.node_id) ? [] : (nodeRef.children || []);
      let y;
      if (!children.length) {
        y = nextLeafY;
        nextLeafY += V_SPACING;
      } else {
        const childYs = children.map((child) => visit(child, depth + 1, nodeRef.node_id));
        y = childYs.reduce((sum, value) => sum + value, 0) / childYs.length;
      }

      const offset = this._state.manualPositions.get(nodeRef.node_id) || { dx: 0, dy: 0 };
      items.push({
        id: nodeRef.node_id,
        nodeRef,
        data,
        x: depth * H_SPACING + offset.dx,
        y: y + offset.dy,
      });

      if (parentId) {
        edges.push({ from: parentId, to: nodeRef.node_id });
      }

      return y + offset.dy;
    };

    (this._state.topology?.roots || []).forEach((root) => {
      visit(root, 0, null);
      nextLeafY += V_SPACING;
    });

    return { items, edges };
  }

  _render() {
    const status = this._state.status || {};
    const { items, edges } = this._flattenTree();
    const width = Math.max(...items.map((item) => item.x), 0) + NODE_WIDTH + PADDING * 2;
    const height = Math.max(...items.map((item) => item.y), 0) + NODE_HEIGHT + PADDING * 2;
    const availableWidth = Math.max(this._canvasEl.clientWidth - 12, NODE_WIDTH);
    const availableHeight = Math.max(this._canvasEl.clientHeight - 12, NODE_HEIGHT);
    const scale = Math.min(
      1,
      (availableWidth * 0.98) / Math.max(width, 1),
      (availableHeight * 0.98) / Math.max(height, 1),
    );
    const offsetX = Math.max(0, (availableWidth - width * scale) / 2);
    const offsetY = Math.max(0, (availableHeight - height * scale) / 2);
    this._state.viewScale = scale;
    const positions = new Map(items.map((item) => [item.id, { x: item.x + PADDING, y: item.y + PADDING }]));

    this._canvasEl.style.minHeight = `${Math.max(height * scale + 16, 300)}px`;
    this._nodesEl.style.width = `${width}px`;
    this._nodesEl.style.height = `${height}px`;
    this._nodesEl.style.transformOrigin = "top left";
    this._nodesEl.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
    this._edgesEl.setAttribute("width", String(width));
    this._edgesEl.setAttribute("height", String(height));
    this._edgesEl.setAttribute("viewBox", `0 0 ${width} ${height}`);
    this._edgesEl.style.transformOrigin = "top left";
    this._edgesEl.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

    this._edgesEl.innerHTML = edges.map((edge) => {
      const from = positions.get(edge.from);
      const to = positions.get(edge.to);
      if (!from || !to) return "";
      const startX = from.x + NODE_WIDTH;
      const startY = from.y + NODE_HEIGHT / 2;
      const endX = to.x;
      const endY = to.y + NODE_HEIGHT / 2;
      const midX = startX + (endX - startX) * 0.42;
      return `<path class="edge" d="M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}" />`;
    }).join("");

    this._nodesEl.innerHTML = "";
    items.forEach((item) => {
      const node = document.createElement("article");
      node.className = `node ${item.data.kind}`;
      if (this._state.selectedId === item.id) node.classList.add("selected");
      node.style.left = `${item.x + PADDING}px`;
      node.style.top = `${item.y + PADDING}px`;
      node.dataset.nodeId = item.id;
      node.innerHTML = `
        <div class="kind">${this._escapeHtml(item.data.kind || "node")}</div>
        <div class="label">${this._escapeHtml(this._buildDisplayLabel(item.nodeRef))}</div>
        <div class="meta">${this._buildMetaLines(item.nodeRef).map((line) =>
          `<span class="pill">${this._escapeHtml(line)}</span>`).join("")}</div>
      `;
      node.addEventListener("click", (event) => {
        event.stopPropagation();
        this._state.selectedId = item.id;
        this._renderDetails(item);
        this._render();
      });
      node.addEventListener("dblclick", (event) => {
        event.stopPropagation();
        if ((item.nodeRef.children || []).length) {
          if (this._state.collapsed.has(item.id)) {
            this._state.collapsed.delete(item.id);
          } else {
            this._state.collapsed.add(item.id);
          }
          this._render();
        }
      });
      node.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        this._state.drag = {
          pointerId: event.pointerId,
          nodeId: item.id,
          startX: event.clientX,
          startY: event.clientY,
          base: this._state.manualPositions.get(item.id) || { dx: 0, dy: 0 },
        };
      });
      this._nodesEl.appendChild(node);
    });

    this._statusEl.textContent =
      `Nodes: ${status.topology?.node_count ?? 0} · ` +
      `Edges: ${status.topology?.edge_count ?? 0} · ` +
      `Unresolved: ${status.topology?.unresolved_host_count ?? 0}`;

    if (this._state.selectedId) {
      const selected = items.find((item) => item.id === this._state.selectedId);
      if (selected) this._renderDetails(selected);
    } else {
      this._detailsEl.textContent = "Click a node to inspect it.";
    }
  }

  _renderDetails(item) {
    const fields = {
      Label: item.data.label || "",
      Kind: item.data.kind || "",
      Type: item.data.type || "",
      IP: item.data.ip || "",
      MAC: item.nodeRef.display_mac || item.data.mac || "",
      Device: item.data.device || "",
      Remote: item.nodeRef.remote_interface || "",
    };
    this._detailsEl.innerHTML = Object.entries(fields)
      .filter(([, value]) => value)
      .map(([key, value]) => `<div><strong>${this._escapeHtml(key)}</strong>${this._escapeHtml(value)}</div>`)
      .join("");
  }

  _onPointerMove(event) {
    if (!this._state.drag || this._state.drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - this._state.drag.startX;
    const dy = event.clientY - this._state.drag.startY;
    this._state.manualPositions.set(this._state.drag.nodeId, {
      dx: this._state.drag.base.dx + dx / this._state.viewScale,
      dy: this._state.drag.base.dy + dy / this._state.viewScale,
    });
    this._render();
  }

  _onPointerUp(event) {
    if (!this._state.drag || this._state.drag.pointerId !== event.pointerId) return;
    this._state.drag = null;
    if (this._state.saveTimer) window.clearTimeout(this._state.saveTimer);
    this._state.saveTimer = window.setTimeout(async () => {
      this._state.saveTimer = null;
      await this._callApi("POST", "api/mikroscan/layout", this._serializeLayout());
    }, 120);
  }

  async _generateTopology() {
    await this._hass.callService("mikroscan", "generate_topology", {});
    await this._loadAll();
  }

  async _scan() {
    const scanRange = this._config.scan_range || "";
    const payload = scanRange ? { ip_range: scanRange } : {};
    await this._hass.callService("mikroscan", "scan", payload);
    await this._loadAll();
  }
}

class MikroscanMapCard extends MikroscanMapBase {
  static getConfigElement() {
    return document.createElement("div");
  }

  static getStubConfig() {
    return { type: "custom:mikroscan-map", title: "Mikroscan Map" };
  }
}

customElements.define("mikroscan-map-card", MikroscanMapCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "mikroscan-map",
  name: "Mikroscan Map",
  description: "Embed the Mikroscan topology map in a dashboard.",
});
