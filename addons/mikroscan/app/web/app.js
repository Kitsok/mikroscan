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
    zoomMultiplier: 1,
    topologyGeneratedAt: "",
    parentMap: new Map(),
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
      const data = getNodeData(nodeId);
      if (data.kind !== "device" || data.type !== "mikrotik") {
        return;
      }
      positions[nodeId] = {
        dx: position.dx,
        dy: position.dy,
        parent_id: state.parentMap.get(nodeId) || "",
      };
    });
    return { positions };
  }

  function buildParentMap() {
    const parentMap = new Map();
    function walk(item, parentId = "") {
      parentMap.set(item.node_id, parentId);
      (item.children || []).forEach((child) => walk(child, item.node_id));
    }
    (state.topology?.roots || []).forEach((root) => walk(root, ""));
    (state.topology?.unreached_roots || []).forEach((root) => walk(root, ""));
    state.parentMap = parentMap;
  }

  function applyLayout(layout) {
    state.manualPositions = new Map();
    const positions = layout?.positions || {};
    Object.entries(positions).forEach(([nodeId, position]) => {
      if (!state.nodeMap.has(nodeId) || typeof position !== "object") {
        return;
      }
      const data = getNodeData(nodeId);
      if (data.kind !== "device" || data.type !== "mikrotik") {
        return;
      }
      const savedParentId = String(position.parent_id || "");
      const currentParentId = state.parentMap.get(nodeId) || "";
      if (savedParentId !== currentParentId) {
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

    function visit(node, depth, parentId) {
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
    }

    state.visibleTree.forEach((root) => visit(root, 0, null));
    state.treeNodes = items;
    return { items, edges };
  }

  function applyLayeredLayout(items, availableHeight) {
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
      const offset = state.manualPositions.get(item.id) || { dx: 0, dy: 0 };

      item.x = (baseColumns.get(item.depth) + columnInDepth) * H_SPACING + offset.dx;
      item.y = rowInDepth * V_SPACING + offset.dy;
    });

    return items;
  }

  function buildNodePills(item) {
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
    return lines
      .map((line) => `<span class="pill">${escapeHtml(line)}</span>`)
      .join("");
  }

  function edgeAnchor(point, side) {
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

  function chooseEdgeAnchors(from, to) {
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

  function buildEdgePath(from, to) {
    const { fromSide, toSide } = chooseEdgeAnchors(from, to);
    const start = edgeAnchor(from, fromSide);
    const end = edgeAnchor(to, toSide);
    return {
      start,
      end,
      labelX: start.x + (end.x - start.x) / 2,
      labelY: start.y + (end.y - start.y) / 2,
      d: `M ${start.x} ${start.y} L ${end.x} ${end.y}`,
    };
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
      elements.buildId.textContent =
        `v${status.app_version || "unknown"} • build ${status.build_id || "unknown"}`;
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
    const availableHeight = Math.max(elements.canvasWrapper.clientHeight - 12, NODE_HEIGHT);
    applyLayeredLayout(items, availableHeight);
    const width = Math.max(...items.map((item) => item.x), 0) + NODE_WIDTH + PADDING * 2;
    const height = Math.max(...items.map((item) => item.y), 0) + NODE_HEIGHT + PADDING * 2;
    const availableWidth = Math.max(elements.canvasWrapper.clientWidth - 12, NODE_WIDTH);
    const fitScale = Math.max(0.85, Math.min(1, (availableWidth * 0.98) / Math.max(width, 1)));
    const scale = Math.max(0.5, Math.min(2.5, fitScale * state.zoomMultiplier));
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
        const route = buildEdgePath(from, to);
        return `<path class="edge-line" d="${route.d}" />`;
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
        const route = buildEdgePath(from, to);
        const left = route.labelX;
        const top = route.labelY;
        return `<div class="edge-label" style="left:${left}px;top:${top}px">${escapeHtml(edge.label)}</div>`;
      })
      .join("");

    elements.nodeLayer.innerHTML = "";
    items.forEach((item) => {
      const node = document.createElement("article");
      node.className = `topology-node ${item.data.kind}`;
      if (item.data.offline) {
        node.classList.add("offline");
      }
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
    buildParentMap();
    const layout = await fetchJson("api/layout");
    applyLayout(layout);
    state.topologyGeneratedAt = state.topology.generated_at || "";
    const generated = state.topologyGeneratedAt || "unknown";
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
    await loadStatus();
    if (state.status.last_success) {
      await loadTopology();
      return;
    }
    throw new Error(state.status.last_error || "topology generation failed");
  }

  async function handleScan() {
    const ipRange = elements.scanRange.value.trim();
    await postAction("api/scan", ipRange ? { ip_range: ipRange } : {});
    await waitForIdle();
    await loadStatus();
    if (state.status.last_success) {
      await loadTopology();
      return;
    }
    throw new Error(state.status.last_error || "scan failed");
  }

  async function initialize() {
    elements.refreshTopology.addEventListener("click", async () => {
      await loadStatus();
      await loadTopology();
    });
    elements.generateTopology.addEventListener("click", async () => {
      try {
        await handleGenerateTopology();
      } catch (error) {
        elements.nodeDetails.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
        elements.detailsDrawer.classList.add("open");
      }
    });
    elements.scanNetwork.addEventListener("click", async () => {
      try {
        await handleScan();
      } catch (error) {
        elements.nodeDetails.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
        elements.detailsDrawer.classList.add("open");
      }
    });
    elements.resetLayout.addEventListener("click", async () => {
      state.manualPositions = new Map();
      state.zoomMultiplier = 1;
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
    elements.canvasWrapper.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        const direction = event.deltaY < 0 ? 1.1 : 0.9;
        state.zoomMultiplier = Math.max(0.6, Math.min(3, state.zoomMultiplier * direction));
        renderCanvas();
      },
      { passive: false },
    );

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
        const generatedAt = state.status?.topology?.generated_at || "";
        if (
          generatedAt &&
          generatedAt !== state.topologyGeneratedAt &&
          !state.status.running
        ) {
          await loadTopology();
        }
      } catch (_error) {
        return;
      }
    }, 3000);
  }

  initialize();
})();
