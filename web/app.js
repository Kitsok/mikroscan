(function () {
  const state = {
    topology: null,
    status: null,
    nodeMap: new Map(),
    visibleTree: [],
    treeNodes: [],
    selectedId: null,
    collapsed: new Set(),
    manualPositions: new Map(),
    drag: null,
    saveLayoutTimer: null,
    viewScale: 1,
  };

  const VISIBLE_INTERFACE_TYPES = new Set(["vlan", "pppoe-out", "wg", "zerotier"]);
  const H_SPACING = 220;
  const V_SPACING = 92;
  const NODE_WIDTH = 172;
  const NODE_HEIGHT = 54;
  const PADDING = 56;

  const elements = {
    buildId: document.getElementById("build-id"),
    mapTitle: document.getElementById("map-title"),
    statusSummary: document.getElementById("status-summary"),
    nodeLayer: document.getElementById("node-layer"),
    edgeLayer: document.getElementById("edge-layer"),
    edgeLabelLayer: document.getElementById("edge-label-layer"),
    canvasWrapper: document.getElementById("canvas-wrapper"),
    detailsDrawer: document.getElementById("details-drawer"),
    closeDrawer: document.getElementById("close-drawer"),
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
      positions[nodeId] = { dx: position.dx, dy: position.dy };
    });
    return { positions };
  }

  function applyLayout(layout) {
    state.manualPositions = new Map();
    const positions = layout?.positions || {};
    Object.entries(positions).forEach(([nodeId, position]) => {
      if (!state.nodeMap.has(nodeId) || typeof position !== "object") {
        return;
      }
      const dx = Number(position.dx);
      const dy = Number(position.dy);
      if (Number.isFinite(dx) && Number.isFinite(dy)) {
        state.manualPositions.set(nodeId, { dx, dy });
      }
    });
  }

  function getNodeData(nodeId) {
    return state.nodeMap.get(nodeId) || { id: nodeId, label: nodeId, kind: "unknown" };
  }

  function shouldRenderInterfaceNode(data) {
    return data.kind === "interface" && VISIBLE_INTERFACE_TYPES.has(data.type || "");
  }

  function displayNameForNode(data) {
    if (data.kind === "interface") {
      return data.name || data.label || data.id;
    }
    return data.label || data.name || data.id;
  }

  function interfaceEdgeName(data) {
    return data.name || data.label || "";
  }

  function buildEdgeLabel(localPort, remotePort) {
    if (localPort && remotePort) {
      return `${localPort} \u2192 ${remotePort}`;
    }
    return localPort || remotePort || "";
  }

  function createVisibleNode(nodeRef, edgeLabel = "") {
    return {
      id: nodeRef.node_id,
      nodeRef,
      data: getNodeData(nodeRef.node_id),
      edgeLabel,
      children: [],
    };
  }

  function attachVisibleChild(parent, nodeRef, localPort = "") {
    const data = getNodeData(nodeRef.node_id);
    const collapsed = data.kind !== "interface" && state.collapsed.has(nodeRef.node_id);
    const children = collapsed ? [] : (nodeRef.children || []);

    if (data.kind === "interface" && !shouldRenderInterfaceNode(data)) {
      const nextLocalPort = interfaceEdgeName(data) || localPort;
      children.forEach((child) => attachVisibleChild(parent, child, nextLocalPort));
      return;
    }

    const childNode = createVisibleNode(
      nodeRef,
      buildEdgeLabel(localPort, nodeRef.remote_interface || ""),
    );
    children.forEach((child) => attachVisibleChild(childNode, child, ""));
    parent.children.push(childNode);
  }

  function buildVisibleTree() {
    const roots = state.topology?.roots || [];
    state.visibleTree = roots.map((root) => {
      const visibleRoot = createVisibleNode(root, "");
      (root.children || []).forEach((child) => attachVisibleChild(visibleRoot, child, ""));
      return visibleRoot;
    });
  }

  function flattenTree() {
    const items = [];
    const edges = [];
    let nextLeafY = 0;

    function visit(node, depth, parentId) {
      const children = node.children || [];
      let y;

      if (!children.length) {
        y = nextLeafY;
        nextLeafY += V_SPACING;
      } else {
        const childYs = children.map((child) => visit(child, depth + 1, node.id));
        y = childYs.reduce((sum, value) => sum + value, 0) / childYs.length;
      }

      const offset = state.manualPositions.get(node.id) || { dx: 0, dy: 0 };
      const x = depth * H_SPACING + offset.dx;
      const adjustedY = y + offset.dy;

      items.push({
        id: node.id,
        nodeRef: node.nodeRef,
        data: node.data,
        edgeLabel: node.edgeLabel,
        x,
        y: adjustedY,
      });

      if (parentId) {
        edges.push({ from: parentId, to: node.id, label: node.edgeLabel });
      }

      return adjustedY;
    }

    let rootOffset = 0;
    state.visibleTree.forEach((root) => {
      nextLeafY = Math.max(nextLeafY, rootOffset);
      visit(root, 0, null);
      rootOffset = nextLeafY + V_SPACING;
    });

    state.treeNodes = items;
    return { items, edges };
  }

  function buildNodePills(item) {
    const lines = [];
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
    return lines
      .map((line) => `<span class="pill">${escapeHtml(line)}</span>`)
      .join("");
  }

  function renderStatus() {
    const status = state.status || {};
    const topology = state.topology || {};
    const deviceCount = (topology.nodes || []).filter((node) => node.kind === "device").length;
    const hostCount = (topology.nodes || []).filter((node) => node.kind === "host").length;
    const unresolved = status.topology?.unresolved_host_count ?? 0;
    const mode = status.running ? `running ${status.current_action}` : "idle";

    elements.statusSummary.textContent =
      `${mode} • ${deviceCount} devices • ${hostCount} hosts • ${unresolved} unresolved`;

    const busy = Boolean(status.running);
    elements.generateTopology.disabled = busy;
    elements.scanNetwork.disabled = busy;
    if (elements.buildId) {
      elements.buildId.textContent = `build ${status.build_id || "unknown"}`;
    }
  }

  function renderDetails() {
    if (!state.selectedId) {
      elements.detailsDrawer.classList.remove("open");
      elements.nodeDetails.textContent = "Click a node to inspect it.";
      return;
    }

    const item = state.treeNodes.find((entry) => entry.id === state.selectedId);
    if (!item) {
      elements.detailsDrawer.classList.remove("open");
      elements.nodeDetails.textContent = "Selected node is not visible.";
      return;
    }

    const details = {
      label: displayNameForNode(item.data),
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
      .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
      .join("");

    elements.nodeDetails.innerHTML = `<dl>${rows}</dl>`;
    elements.detailsDrawer.classList.add("open");
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
    buildVisibleTree();
    const { items, edges } = flattenTree();
    const width = Math.max(...items.map((item) => item.x), 0) + NODE_WIDTH + PADDING * 2;
    const height = Math.max(...items.map((item) => item.y), 0) + NODE_HEIGHT + PADDING * 2;
    const availableWidth = Math.max(elements.canvasWrapper.clientWidth - 12, NODE_WIDTH);
    const scale = Math.max(0.85, Math.min(1, (availableWidth * 0.98) / Math.max(width, 1)));
    const offsetX = Math.max(0, (availableWidth - width * scale) / 2);
    const offsetY = 8;
    state.viewScale = scale;

    elements.nodeLayer.style.width = `${width}px`;
    elements.nodeLayer.style.height = `${height}px`;
    elements.nodeLayer.style.transformOrigin = "top left";
    elements.nodeLayer.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

    elements.edgeLabelLayer.style.width = `${width}px`;
    elements.edgeLabelLayer.style.height = `${height}px`;
    elements.edgeLabelLayer.style.transformOrigin = "top left";
    elements.edgeLabelLayer.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

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

    elements.edgeLabelLayer.innerHTML = edges
      .map((edge) => {
        if (!edge.label) {
          return "";
        }
        const from = positions.get(edge.from);
        const to = positions.get(edge.to);
        if (!from || !to) {
          return "";
        }
        const left = from.x + NODE_WIDTH + (to.x - (from.x + NODE_WIDTH)) * 0.5;
        const top = from.y + NODE_HEIGHT / 2 + (to.y - from.y) * 0.5;
        return `<div class="edge-label" style="left:${left}px;top:${top}px">${escapeHtml(edge.label)}</div>`;
      })
      .join("");

    elements.nodeLayer.innerHTML = "";
    items.forEach((item) => {
      const node = document.createElement("article");
      node.className = `topology-node ${item.data.kind}`;
      if (state.selectedId === item.id) {
        node.classList.add("selected");
      }
      node.dataset.nodeId = item.id;
      node.style.left = `${item.x + PADDING}px`;
      node.style.top = `${item.y + PADDING}px`;

      node.innerHTML = `
        <div class="node-kind">${escapeHtml(item.data.kind)}</div>
        <div class="node-label">${escapeHtml(displayNameForNode(item.data))}</div>
        <div class="node-meta">${buildNodePills(item)}</div>
      `;

      node.addEventListener("click", (event) => {
        event.stopPropagation();
        state.selectedId = item.id;
        renderDetails();
        updateSelectedNodeClasses();
      });

      node.addEventListener("dblclick", (event) => {
        event.stopPropagation();
        if ((item.nodeRef.children || []).length && item.data.kind !== "host") {
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
    elements.mapTitle.textContent = `Topology Map • ${generated}`;
    renderAll();
  }

  async function loadStatus() {
    state.status = await fetchJson("api/status");
    renderStatus();
  }

  async function postAction(url, payload) {
    const result = await fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    await loadStatus();
    return result;
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
    elements.closeDrawer.addEventListener("click", () => {
      state.selectedId = null;
      renderDetails();
      updateSelectedNodeClasses();
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
      renderDetails();
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
      elements.detailsDrawer.classList.add("open");
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
