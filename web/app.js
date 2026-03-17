(function () {
  const state = {
    topology: null,
    status: null,
    nodeMap: new Map(),
    treeNodes: [],
    selectedId: null,
    collapsed: new Set(),
    manualPositions: new Map(),
    drag: null,
    saveLayoutTimer: null,
    viewScale: 1,
  };

  const H_SPACING = 214;
  const V_SPACING = 76;
  const NODE_WIDTH = 164;
  const NODE_HEIGHT = 52;
  const PADDING = 48;

  const elements = {
    mapTitle: document.getElementById("map-title"),
    nodeLayer: document.getElementById("node-layer"),
    edgeLayer: document.getElementById("edge-layer"),
    canvasWrapper: document.getElementById("canvas-wrapper"),
    statusGrid: document.getElementById("status-grid"),
    nodeDetails: document.getElementById("node-details"),
    unresolvedHosts: document.getElementById("unresolved-hosts"),
    refreshTopology: document.getElementById("refresh-topology"),
    generateTopology: document.getElementById("generate-topology"),
    scanNetwork: document.getElementById("scan-network"),
    resetLayout: document.getElementById("reset-layout"),
    scanRange: document.getElementById("scan-range"),
  };

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || payload.message || `Request failed: ${response.status}`);
    }
    return payload;
  }

  function buildNodeIndex(model) {
    state.nodeMap = new Map((model.nodes || []).map((node) => [node.id, node]));
  }

  function serializePositions() {
    const positions = {};
    state.manualPositions.forEach((position, nodeId) => {
      positions[nodeId] = {
        dx: position.dx,
        dy: position.dy,
      };
    });
    return { positions };
  }

  function applyLayout(layout) {
    state.manualPositions = new Map();
    const positions = layout?.positions || {};
    Object.entries(positions).forEach(([nodeId, position]) => {
      if (!state.nodeMap.has(nodeId) || !position || typeof position !== "object") {
        return;
      }
      const dx = Number(position.dx);
      const dy = Number(position.dy);
      if (!Number.isFinite(dx) || !Number.isFinite(dy)) {
        return;
      }
      state.manualPositions.set(nodeId, { dx, dy });
    });
  }

  function getNodeData(nodeId) {
    return state.nodeMap.get(nodeId) || { id: nodeId, label: nodeId, kind: "unknown" };
  }

  function buildDisplayLabel(nodeRef) {
    const data = getNodeData(nodeRef.node_id);
    const bits = [];
    if (nodeRef.remote_interface) {
      bits.push(`<${nodeRef.remote_interface}>`);
    }
    bits.push(data.label || data.name || nodeRef.node_id);
    return bits.join(" ");
  }

  function buildMetaLines(nodeRef) {
    const data = getNodeData(nodeRef.node_id);
    const lines = [];

    if (data.ip) {
      lines.push(data.ip);
    }
    if (nodeRef.display_mac || data.mac) {
      lines.push(nodeRef.display_mac || data.mac);
    }
    if (data.type && data.kind === "interface") {
      lines.push(data.type);
    }
    if (nodeRef.already_shown) {
      lines.push("already shown");
    }
    return lines;
  }

  function flattenTree() {
    const items = [];
    const edges = [];
    let nextLeafY = 0;

    function visit(nodeRef, depth, parentId) {
      const data = getNodeData(nodeRef.node_id);
      const children = state.collapsed.has(nodeRef.node_id) ? [] : (nodeRef.children || []);
      const localId = nodeRef.node_id;
      let y;

      if (!children.length) {
        y = nextLeafY;
        nextLeafY += V_SPACING;
      } else {
        const childYs = [];
        children.forEach((child) => {
          childYs.push(visit(child, depth + 1, localId));
        });
        y = childYs.reduce((sum, value) => sum + value, 0) / childYs.length;
      }

      const computedX = depth * H_SPACING;
      const position = state.manualPositions.get(localId);
      const x = computedX + (position ? position.dx : 0);
      const adjustedY = y + (position ? position.dy : 0);

      items.push({
        id: localId,
        nodeRef,
        data,
        depth,
        x,
        y: adjustedY,
      });

      if (parentId) {
        edges.push({ from: parentId, to: localId });
      }

      return adjustedY;
    }

    const roots = state.topology?.roots || [];
    let rootOffset = 0;
    roots.forEach((root) => {
      nextLeafY = Math.max(nextLeafY, rootOffset);
      visit(root, 0, null);
      rootOffset = nextLeafY + V_SPACING;
    });

    state.treeNodes = items;
    return { items, edges };
  }

  function renderStatus() {
    const status = state.status || {};
    const rows = [
      ["Current", status.current_action || "idle"],
      ["Last action", status.last_action || "none"],
      ["Last success", status.last_success === null ? "unknown" : String(status.last_success)],
      ["Last error", status.last_error || "none"],
      ["Nodes", status.topology?.node_count ?? 0],
      ["Edges", status.topology?.edge_count ?? 0],
      ["Roots", status.topology?.root_count ?? 0],
      ["Unresolved", status.topology?.unresolved_host_count ?? 0],
    ];

    elements.statusGrid.innerHTML = rows
      .map(([term, value]) => `<dt>${escapeHtml(term)}</dt><dd>${escapeHtml(value)}</dd>`)
      .join("");

    const busy = Boolean(status.running);
    elements.generateTopology.disabled = busy;
    elements.scanNetwork.disabled = busy;
  }

  function renderDetails() {
    if (!state.selectedId) {
      elements.nodeDetails.textContent = "Click a node to inspect it.";
      return;
    }

    const item = state.treeNodes.find((entry) => entry.id === state.selectedId);
    if (!item) {
      elements.nodeDetails.textContent = "Selected node is not visible in the current tree.";
      return;
    }

    const details = {
      id: item.id,
      kind: item.data.kind,
      type: item.data.type || "",
      label: item.data.label || "",
      ip: item.data.ip || "",
      mac: item.nodeRef.display_mac || item.data.mac || "",
      device: item.data.device || "",
      remote_interface: item.nodeRef.remote_interface || "",
      hostname: item.data.hostname || "",
      running: item.data.running || "",
      already_shown: item.nodeRef.already_shown ? "true" : "",
    };

    const rows = Object.entries(details)
      .filter(([, value]) => value)
      .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
      .join("");

    elements.nodeDetails.innerHTML = `<dl>${rows}</dl>`;
  }

  function renderUnresolvedHosts() {
    const hosts = state.topology?.unresolved_hosts || [];
    if (!hosts.length) {
      elements.unresolvedHosts.textContent = "No unresolved hosts.";
      return;
    }

    elements.unresolvedHosts.innerHTML = `<ul>${hosts
      .map((host) => {
        const label = [host.label || host.ip || host.id, host.ip, host.mac]
          .filter(Boolean)
          .join(" — ");
        return `<li>${escapeHtml(label)}</li>`;
      })
      .join("")}</ul>`;
  }

  function renderCanvas() {
    const { items, edges } = flattenTree();
    const width = Math.max(...items.map((item) => item.x), 0) + NODE_WIDTH + PADDING * 2;
    const height = Math.max(...items.map((item) => item.y), 0) + NODE_HEIGHT + PADDING * 2;
    const availableWidth = Math.max(elements.canvasWrapper.clientWidth - 12, NODE_WIDTH);
    const availableHeight = Math.max(elements.canvasWrapper.clientHeight - 12, NODE_HEIGHT);
    const scale = Math.min(
      1,
      (availableWidth * 0.98) / Math.max(width, 1),
      (availableHeight * 0.98) / Math.max(height, 1),
    );
    const offsetX = Math.max(0, (availableWidth - width * scale) / 2);
    const offsetY = Math.max(0, (availableHeight - height * scale) / 2);
    state.viewScale = scale;

    elements.nodeLayer.style.width = `${width}px`;
    elements.nodeLayer.style.height = `${height}px`;
    elements.nodeLayer.style.transformOrigin = "top left";
    elements.nodeLayer.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
    elements.edgeLayer.setAttribute("width", String(width));
    elements.edgeLayer.setAttribute("height", String(height));
    elements.edgeLayer.setAttribute("viewBox", `0 0 ${width} ${height}`);
    elements.edgeLayer.style.transformOrigin = "top left";
    elements.edgeLayer.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

    const positions = new Map(
      items.map((item) => [
        item.id,
        {
          x: item.x + PADDING,
          y: item.y + PADDING,
        },
      ]),
    );

    elements.edgeLayer.innerHTML = edges
      .map((edge) => {
        const from = positions.get(edge.from);
        const to = positions.get(edge.to);
        if (!from || !to) {
          return "";
        }

        const startX = from.x + NODE_WIDTH;
        const startY = from.y + NODE_HEIGHT / 2;
        const endX = to.x;
        const endY = to.y + NODE_HEIGHT / 2;
        const midX = startX + (endX - startX) * 0.42;
        return `<path class="edge-line" d="M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}" />`;
      })
      .join("");

    elements.nodeLayer.innerHTML = "";
    items.forEach((item) => {
      const node = document.createElement("article");
      node.className = `topology-node ${item.data.kind}`;
      if (state.selectedId === item.id) {
        node.classList.add("selected");
      }
      if (state.collapsed.has(item.id)) {
        node.classList.add("collapsed");
      }
      node.dataset.nodeId = item.id;
      node.style.left = `${item.x + PADDING}px`;
      node.style.top = `${item.y + PADDING}px`;

      const meta = buildMetaLines(item.nodeRef)
        .map((line) => `<span class="pill">${escapeHtml(line)}</span>`)
        .join("");

      node.innerHTML = `
        <div class="node-kind">${escapeHtml(item.data.kind)}</div>
        <div class="node-label">${escapeHtml(buildDisplayLabel(item.nodeRef))}</div>
        <div class="node-meta">${meta}</div>
      `;

      node.addEventListener("click", (event) => {
        event.stopPropagation();
        state.selectedId = item.id;
        renderDetails();
        updateSelectedNodeClasses();
      });

      node.addEventListener("dblclick", (event) => {
        event.stopPropagation();
        if ((item.nodeRef.children || []).length) {
          if (state.collapsed.has(item.id)) {
            state.collapsed.delete(item.id);
          } else {
            state.collapsed.add(item.id);
          }
          renderCanvas();
          renderDetails();
        }
      });

      node.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        state.drag = {
          pointerId: event.pointerId,
          nodeId: item.id,
          startX: event.clientX,
          startY: event.clientY,
          base: state.manualPositions.get(item.id) || { dx: 0, dy: 0 },
        };
      });

      elements.nodeLayer.appendChild(node);
    });
  }

  function updateSelectedNodeClasses() {
    const nodes = elements.nodeLayer.querySelectorAll(".topology-node");
    nodes.forEach((node) => {
      if (node.dataset.nodeId === state.selectedId) {
        node.classList.add("selected");
      } else {
        node.classList.remove("selected");
      }
    });
  }

  function renderAll() {
    renderStatus();
    renderUnresolvedHosts();
    renderDetails();
    renderCanvas();
  }

  async function loadTopology() {
    state.topology = await fetchJson("api/topology");
    buildNodeIndex(state.topology);
    const layout = await fetchJson("api/layout");
    applyLayout(layout);
    const generated = state.topology.generated_at || "unknown";
    elements.mapTitle.textContent = `Current topology • ${generated}`;
    renderAll();
  }

  async function loadStatus() {
    state.status = await fetchJson("api/status");
    renderStatus();
  }

  async function postAction(url, payload) {
    try {
      const result = await fetchJson(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
      await loadStatus();
      return result;
    } catch (error) {
      state.status = {
        ...(state.status || {}),
        last_error: error.message,
      };
      renderStatus();
      throw error;
    }
  }

  async function persistLayout() {
    await postAction("api/layout", serializePositions());
  }

  function scheduleLayoutSave() {
    if (state.saveLayoutTimer) {
      window.clearTimeout(state.saveLayoutTimer);
    }
    state.saveLayoutTimer = window.setTimeout(async () => {
      state.saveLayoutTimer = null;
      try {
        await persistLayout();
      } catch (_error) {
        return;
      }
    }, 150);
  }

  async function waitForIdle() {
    for (;;) {
      await loadStatus();
      if (!state.status.running) {
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }

  async function handleGenerateTopology() {
    await postAction("api/generate-topology");
    await waitForIdle();
    await loadTopology();
  }

  async function handleScan() {
    const ipRange = elements.scanRange.value.trim();
    await postAction("api/scan", ipRange ? { ip_range: ipRange } : {});
    await waitForIdle();
    await loadTopology();
  }

  async function initialize() {
    elements.refreshTopology.addEventListener("click", async () => {
      await loadStatus();
      await loadTopology();
    });
    elements.generateTopology.addEventListener("click", handleGenerateTopology);
    elements.scanNetwork.addEventListener("click", handleScan);
    elements.resetLayout.addEventListener("click", async () => {
      state.manualPositions = new Map();
      renderCanvas();
      await persistLayout();
    });
    elements.canvasWrapper.addEventListener("click", () => {
      state.selectedId = null;
      renderDetails();
      updateSelectedNodeClasses();
    });
    window.addEventListener("pointermove", (event) => {
      if (!state.drag || state.drag.pointerId !== event.pointerId) {
        return;
      }

      const dx = event.clientX - state.drag.startX;
      const dy = event.clientY - state.drag.startY;
      state.manualPositions.set(state.drag.nodeId, {
        dx: state.drag.base.dx + dx / state.viewScale,
        dy: state.drag.base.dy + dy / state.viewScale,
      });
      renderCanvas();
    });
    window.addEventListener("pointerup", (event) => {
      if (state.drag && state.drag.pointerId === event.pointerId) {
        state.drag = null;
        scheduleLayoutSave();
      }
    });
    window.addEventListener("pointercancel", () => {
      state.drag = null;
    });
    window.addEventListener("resize", () => {
      if (state.topology) {
        renderCanvas();
      }
    });

    try {
      await loadStatus();
      await loadTopology();
    } catch (error) {
      elements.nodeDetails.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    }

    window.setInterval(async () => {
      try {
        await loadStatus();
      } catch (_error) {
        return;
      }
    }, 3000);
  }

  initialize();
})();
