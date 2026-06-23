/**
 * Knowledge Graph — Sigma.js + Graphology WebGL renderer with ForceAtlas2 layout.
 * Click a tag node to focus it + neighbors and show bound memories.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { onCleanup } from '../lifecycle.js';
import { error } from './toast.js';

let renderer = null;
let fa2Interval = null;

/* ====================================================================
   Color palette
   ==================================================================== */
const PALETTE = {
  dark: {
    nodeColors: [
      '#7c6af6', '#58a6ff', '#3fb950', '#d29922', '#f778ba',
      '#ff7b72', '#79c0ff', '#d2a8ff', '#56d364', '#e3b341',
    ],
    nodeHover:     '#58a6ff',
    nodeSelected:  '#f0883e',
    nodeDimmed:    'rgba(90,90,90,0.25)',
    edgeNormal:    'rgba(110,118,129,0.25)',
    edgeHighlight: 'rgba(88,166,255,0.5)',
    labelNormal:   '#c9d1d9',
    searchMatch:   '#f0883e',
  },
  light: {
    nodeColors: [
      '#6639ba', '#0969da', '#1a7f37', '#9a6700', '#bf3989',
      '#cf222e', '#0550ae', '#8250df', '#116329', '#953800',
    ],
    nodeHover:     '#0969da',
    nodeSelected:  '#bc4c00',
    nodeDimmed:    'rgba(175,184,193,0.3)',
    edgeNormal:    'rgba(175,184,193,0.4)',
    edgeHighlight: 'rgba(9,105,218,0.5)',
    labelNormal:   '#1f2328',
    searchMatch:   '#bc4c00',
  },
};

function theme() {
  return document.documentElement.getAttribute('data-theme') === 'light' ? PALETTE.light : PALETTE.dark;
}

export async function renderGraph(root) {
  if (renderer) { renderer.kill(); renderer = null; }
  if (fa2Interval) { clearInterval(fa2Interval); fa2Interval = null; }

  root.innerHTML = `
    <div class="tab-toolbar">
      <div class="flex gap-4" style="align-items:center;">
        <input class="form-input" id="graph-search" placeholder="${t('graph.search_placeholder')}" style="max-width:300px">
        <button class="btn btn-sm" id="graph-layout-toggle">${t('graph.pause_layout')}</button>
        <span id="graph-stats" class="text-muted text-sm"></span>
      </div>
    </div>
    <div style="display:flex;gap:16px;height:calc(100vh - 300px);min-height:400px;">
      <div class="graph-container" id="graph-container" style="flex:1;min-width:0;height:100%;"></div>
      <div id="graph-panel" class="hidden" style="width:320px;flex-shrink:0;height:100%;overflow-y:auto;"></div>
    </div>
  `;

  const container = root.querySelector('#graph-container');
  const searchInput = root.querySelector('#graph-search');
  const layoutBtn = root.querySelector('#graph-layout-toggle');
  const statsEl = root.querySelector('#graph-stats');
  const panel = root.querySelector('#graph-panel');

  /* Load data */
  let graphData;
  try {
    graphData = await api.exportGraph();
    if (!graphData.nodes.length) {
      container.innerHTML = `<div class="empty-state" style="padding:60px">${t('graph.no_nodes')}</div>`;
      return;
    }
  } catch (e) {
    error(t('graph.load_failed', { msg: e.message }));
    return;
  }

  /* Build graph */
  const Graph = globalThis.graphology;
  const graph = new Graph({ multi: false, type: 'undirected' });
  const maxWeight = Math.max(1, ...graphData.nodes.map(n => (n.memory_ids?.length || 1)));
  const spread = Math.sqrt(graphData.nodes.length) * 10;

  // Store memory_ids per node for the panel
  const nodeMemoryIds = {};

  for (let i = 0; i < graphData.nodes.length; i++) {
    const n = graphData.nodes[i];
    const memCount = n.memory_ids?.length || 0;
    const size = 4 + Math.min(16, (memCount / maxWeight) * 14);
    const colors = theme().nodeColors;
    const color = colors[i % colors.length];
    nodeMemoryIds[n.id] = n.memory_ids || [];
    graph.addNode(n.id, {
      label: n.label || n.id,
      x: (Math.random() - 0.5) * spread,
      y: (Math.random() - 0.5) * spread,
      size,
      color,
      _origColor: color,
      memCount,
    });
  }

  for (const e of graphData.edges) {
    if (graph.hasNode(e.source) && graph.hasNode(e.target)) {
      try {
        graph.addEdge(e.source, e.target, {
          weight: e.weight || 1,
          size: Math.min(3, (e.weight || 1)),
          color: theme().edgeNormal,
        });
      } catch { /* dup */ }
    }
  }

  statsEl.textContent = t('graph.stats', { nodes: graph.order, edges: graph.size });

  /* Renderer */
  renderer = new Sigma(graph, container, {
    renderLabels: true,
    labelSize: 12,
    labelColor: { color: theme().labelNormal },
    labelRenderedSizeThreshold: 6,
    labelBackgroundColor: 'transparent',
    labelDensity: 0.5,
    defaultEdgeColor: theme().edgeNormal,
    defaultNodeColor: theme().nodeColors[0],
    minCameraRatio: 0.05,
    maxCameraRatio: 10,
    allowInvalidContainer: true,
  });

  /* ForceAtlas2 */
  const FA2 = globalThis.ForceAtlas2;
  let layoutRunning = true;

  function runFA2Step() {
    if (!layoutRunning) return;
    FA2.assign(graph, {
      iterations: 5,
      settings: {
        gravity: 0.5, scalingRatio: 50,
        barnesHutOptimize: graph.order > 50, barnesHutTheta: 0.5,
        slowDown: 10, strongGravityMode: false, outboundAttractionDistribution: true,
      },
    });
  }

  for (let i = 0; i < 50; i++) runFA2Step();
  renderer.getCamera().animatedReset();
  fa2Interval = setInterval(runFA2Step, 50);

  setTimeout(() => {
    if (layoutRunning) {
      layoutRunning = false;
      clearInterval(fa2Interval); fa2Interval = null;
      layoutBtn.textContent = t('graph.resume_layout');
    }
  }, 10000);

  layoutBtn.addEventListener('click', () => {
    if (layoutRunning) {
      layoutRunning = false;
      clearInterval(fa2Interval); fa2Interval = null;
      layoutBtn.textContent = t('graph.resume_layout');
    } else {
      layoutRunning = true;
      fa2Interval = setInterval(runFA2Step, 50);
      layoutBtn.textContent = t('graph.pause_layout');
      setTimeout(() => {
        if (layoutRunning) {
          layoutRunning = false;
          clearInterval(fa2Interval); fa2Interval = null;
          layoutBtn.textContent = t('graph.resume_layout');
        }
      }, 10000);
    }
  });

  /* ================================================================
     State: selected node
     ================================================================ */
  let selectedNode = null;

  function clearSelection() {
    selectedNode = null;
    const t = theme();
    graph.forEachNode((n) => {
      graph.setNodeAttribute(n, 'color', graph.getNodeAttribute(n, '_origColor'));
    });
    graph.forEachEdge((e) => {
      graph.setEdgeAttribute(e, 'hidden', false);
      graph.setEdgeAttribute(e, 'color', t.edgeNormal);
    });
    renderer.setSetting('labelColor', { color: t.labelNormal });
    panel.classList.add('hidden');
    panel.innerHTML = '';
  }

  function focusNode(node) {
    const t = theme();
    const neighbors = new Set(graph.neighbors(node));
    neighbors.add(node);

    graph.forEachNode((n) => {
      if (n === node) {
        graph.setNodeAttribute(n, 'color', n === selectedNode ? t.nodeSelected : t.nodeHover);
      } else if (neighbors.has(n)) {
        graph.setNodeAttribute(n, 'color', graph.getNodeAttribute(n, '_origColor'));
      } else {
        graph.setNodeAttribute(n, 'color', t.nodeDimmed);
      }
    });

    graph.forEachEdge((e, _a, src, tgt) => {
      if (neighbors.has(src) && neighbors.has(tgt)) {
        graph.setEdgeAttribute(e, 'color', t.edgeHighlight);
        graph.setEdgeAttribute(e, 'hidden', false);
      } else {
        graph.setEdgeAttribute(e, 'hidden', true);
      }
    });
  }

  /* ================================================================
     Hover
     ================================================================ */
  renderer.on('enterNode', ({ node }) => {
    if (selectedNode) return; // don't override selection
    focusNode(node);
  });

  renderer.on('leaveNode', () => {
    if (selectedNode) return;
    clearSelection();
  });

  /* ================================================================
     Click: select node → focus + show memory panel
     ================================================================ */
  renderer.on('clickNode', async ({ node }) => {
    if (selectedNode === node) {
      clearSelection();
      return;
    }

    selectedNode = node;
    focusNode(node);

    const label = graph.getNodeAttribute(node, 'label');
    const memCount = graph.getNodeAttribute(node, 'memCount') || 0;
    const neighbors = graph.neighbors(node).map(n => graph.getNodeAttribute(n, 'label'));

    // Show panel with loading
    panel.classList.remove('hidden');
    panel.innerHTML = `
      <div class="card" style="height:100%;display:flex;flex-direction:column;overflow:hidden;">
        <div class="flex-between" style="flex-shrink:0;margin-bottom:12px;">
          <h3 style="font-size:14px;font-weight:600;margin:0;">${esc(label)}</h3>
          <button class="btn btn-sm" id="panel-close" style="padding:2px 8px;font-size:16px;line-height:1;">&times;</button>
        </div>
        <div style="flex-shrink:0;margin-bottom:12px;">
          <span class="text-muted text-sm">${t('graph.mem_count', { n: memCount })}</span>
          ${neighbors.length ? `<div class="text-muted text-sm" style="margin-top:4px;">${t('graph.neighbors')} ${neighbors.slice(0, 8).map(n => `<span class="tag">${esc(n)}</span>`).join(' ')}${neighbors.length > 8 ? ` +${neighbors.length - 8}` : ''}</div>` : ''}
        </div>
        <div id="panel-memories" style="flex:1;overflow-y:auto;font-size:13px;min-height:0;">
          <div class="text-muted">${t('graph.loading_memories')}</div>
        </div>
      </div>
    `;

    panel.querySelector('#panel-close').addEventListener('click', clearSelection);

    // Fetch memories for this tag
    const memoriesEl = panel.querySelector('#panel-memories');
    try {
      const memIds = nodeMemoryIds[node] || [];
      if (!memIds.length) {
        memoriesEl.innerHTML = `<div class="text-muted">${t('graph.no_linked_memories')}</div>`;
        return;
      }

      // Fetch up to 20 memories
      const fetches = memIds.slice(0, 20).map(id => api.getMemory(id).catch(() => null));
      const memories = (await Promise.all(fetches)).filter(Boolean);

      if (!memories.length) {
        memoriesEl.innerHTML = `<div class="text-muted">${t('graph.memories_not_found')}</div>`;
        return;
      }

      memoriesEl.innerHTML = memories.map(m => `
        <div style="padding:8px 0;border-bottom:1px solid var(--border);">
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px;">
            <span class="tag" style="font-size:10px;">${esc(m.partition_id)}</span>
            <span style="margin-left:4px;">${new Date(m.created_at).toLocaleDateString()}</span>
          </div>
          <div style="line-height:1.5;">${esc(m.content.length > 200 ? m.content.slice(0, 200) + '...' : m.content)}</div>
          ${m.tags?.length ? `<div style="margin-top:4px;">${m.tags.map(t => `<span class="tag" style="font-size:10px;">${esc(t)}</span>`).join(' ')}</div>` : ''}
        </div>
      `).join('');

      if (memIds.length > 20) {
        memoriesEl.innerHTML += `<div class="text-muted" style="padding:8px 0;">${t('graph.more_memories', { n: memIds.length - 20 })}</div>`;
      }
    } catch (e) {
      memoriesEl.innerHTML = `<div style="color:var(--accent-red);">${esc(t('graph.panel_load_failed', { msg: e.message }))}</div>`;
    }
  });

  /* Click stage (background) to deselect */
  renderer.on('clickStage', () => {
    if (selectedNode) clearSelection();
  });

  /* ================================================================
     Search
     ================================================================ */
  searchInput.addEventListener('input', (e) => {
    if (selectedNode) clearSelection();
    const q = e.target.value.trim().toLowerCase();
    const t = theme();

    if (!q) {
      graph.forEachNode((n) => {
        graph.setNodeAttribute(n, 'color', graph.getNodeAttribute(n, '_origColor'));
      });
      graph.forEachEdge((e) => {
        graph.setEdgeAttribute(e, 'hidden', false);
        graph.setEdgeAttribute(e, 'color', t.edgeNormal);
      });
      return;
    }

    const matched = new Set();
    graph.forEachNode((n) => {
      const label = graph.getNodeAttribute(n, 'label').toLowerCase();
      if (label.includes(q)) {
        graph.setNodeAttribute(n, 'color', t.searchMatch);
        matched.add(n);
      } else {
        graph.setNodeAttribute(n, 'color', t.nodeDimmed);
      }
    });

    graph.forEachEdge((e, _a, src, tgt) => {
      if (matched.has(src) && matched.has(tgt)) {
        graph.setEdgeAttribute(e, 'color', t.edgeHighlight);
        graph.setEdgeAttribute(e, 'hidden', false);
      } else {
        graph.setEdgeAttribute(e, 'hidden', true);
      }
    });
  });

  /* ================================================================
     Theme switch
     ================================================================ */
  const observer = new MutationObserver(() => {
    const t = theme();
    renderer.setSetting('labelColor', { color: t.labelNormal });
    renderer.setSetting('defaultEdgeColor', t.edgeNormal);
    let i = 0;
    graph.forEachNode((n) => {
      const c = t.nodeColors[i % t.nodeColors.length];
      graph.setNodeAttribute(n, 'color', c);
      graph.setNodeAttribute(n, '_origColor', c);
      i++;
    });
    graph.forEachEdge((e) => {
      graph.setEdgeAttribute(e, 'color', t.edgeNormal);
    });
    if (selectedNode) clearSelection();
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  // Tear down on unmount (tab switch / navigation): the theme observer would
  // otherwise accumulate one live instance per visit, and the WebGL renderer +
  // ForceAtlas2 interval would keep running against a detached container.
  onCleanup(() => {
    observer.disconnect();
    if (renderer) { renderer.kill(); renderer = null; }
    if (fa2Interval) { clearInterval(fa2Interval); fa2Interval = null; }
  });
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
