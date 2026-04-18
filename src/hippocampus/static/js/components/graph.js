/**
 * Knowledge Graph — canvas force-directed layout with tag browsing.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { error } from './toast.js';

let animId = null;

export async function renderGraph(root) {
  /* Cleanup previous animation */
  if (animId) { cancelAnimationFrame(animId); animId = null; }

  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('graph.title')}</h1>
      <p class="page-subtitle">${t('graph.subtitle')}</p>
    </div>
    <div class="flex gap-4 mb-4">
      <input class="form-input" id="graph-search" placeholder="${t('graph.search_placeholder')}" style="max-width:300px">
    </div>
    <div class="graph-container">
      <canvas id="graph-canvas"></canvas>
      <div class="graph-info hidden" id="graph-info"></div>
    </div>
  `;

  const canvas = root.querySelector('#graph-canvas');
  const ctx = canvas.getContext('2d');
  const info = root.querySelector('#graph-info');
  let graphData = null;
  let nodes = [], edges = [];
  let hoveredNode = null, dragNode = null;
  let offsetX = 0, offsetY = 0, scale = 1;

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * devicePixelRatio;
    canvas.height = rect.height * devicePixelRatio;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  }
  resize();
  window.addEventListener('resize', resize);

  /* Load graph */
  try {
    graphData = await api.exportGraph();
    if (!graphData.nodes.length) {
      info.classList.remove('hidden');
      info.textContent = t('graph.no_nodes');
      return;
    }
    initGraph(graphData);
  } catch (e) {
    error('Failed to load graph: ' + e.message);
    return;
  }

  function initGraph(data) {
    const w = canvas.width / devicePixelRatio;
    const h = canvas.height / devicePixelRatio;
    const maxWeight = Math.max(1, ...data.nodes.map(n => n.memory_ids?.length || n.weight || 1));

    nodes = data.nodes.map((n, i) => ({
      id: n.id,
      label: n.label || n.id,
      memCount: n.memory_ids?.length || 0,
      weight: n.weight || 1,
      r: 6 + Math.min(20, ((n.memory_ids?.length || 1) / maxWeight) * 18),
      x: w / 2 + (Math.random() - 0.5) * w * 0.6,
      y: h / 2 + (Math.random() - 0.5) * h * 0.6,
      vx: 0, vy: 0,
    }));

    const nodeMap = {};
    nodes.forEach(n => nodeMap[n.id] = n);

    edges = data.edges.filter(e => nodeMap[e.source] && nodeMap[e.target]).map(e => ({
      source: nodeMap[e.source],
      target: nodeMap[e.target],
      weight: e.weight || 1,
    }));

    animate();
  }

  function simulate() {
    const w = canvas.width / devicePixelRatio;
    const h = canvas.height / devicePixelRatio;
    const k = 0.005; // spring constant
    const repulsion = 3000;
    const damping = 0.92;
    const centerPull = 0.001;

    /* Repulsion between all pairs */
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        let dx = nodes[j].x - nodes[i].x;
        let dy = nodes[j].y - nodes[i].y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        let force = repulsion / (dist * dist);
        let fx = (dx / dist) * force;
        let fy = (dy / dist) * force;
        nodes[i].vx -= fx;  nodes[i].vy -= fy;
        nodes[j].vx += fx;  nodes[j].vy += fy;
      }
    }

    /* Spring attraction along edges */
    for (const e of edges) {
      let dx = e.target.x - e.source.x;
      let dy = e.target.y - e.source.y;
      let dist = Math.sqrt(dx * dx + dy * dy) || 1;
      let force = k * (dist - 100);
      let fx = (dx / dist) * force;
      let fy = (dy / dist) * force;
      e.source.vx += fx;  e.source.vy += fy;
      e.target.vx -= fx;  e.target.vy -= fy;
    }

    /* Center pull + damping */
    for (const n of nodes) {
      if (n === dragNode) continue;
      n.vx += (w / 2 - n.x) * centerPull;
      n.vy += (h / 2 - n.y) * centerPull;
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(n.r, Math.min(w - n.r, n.x));
      n.y = Math.max(n.r, Math.min(h - n.r, n.y));
    }
  }

  function draw() {
    const w = canvas.width / devicePixelRatio;
    const h = canvas.height / devicePixelRatio;
    ctx.clearRect(0, 0, w, h);

    /* Edges */
    ctx.lineWidth = 1;
    for (const e of edges) {
      ctx.beginPath();
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      const isLightEdge = document.documentElement.getAttribute('data-theme') === 'light';
      ctx.strokeStyle = isLightEdge ? 'rgba(208,215,222,0.9)' : 'rgba(48,54,61,0.8)';
      ctx.lineWidth = Math.min(3, e.weight);
      ctx.stroke();
    }

    /* Nodes */
    for (const n of nodes) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      const hue = (n.memCount * 40) % 360;
      ctx.fillStyle = n === hoveredNode ? '#58a6ff' : `hsl(${hue}, 60%, 55%)`;
      ctx.fill();
      if (n === hoveredNode) {
        ctx.strokeStyle = '#58a6ff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      /* Label — adapt to theme */
      const isLight = document.documentElement.getAttribute('data-theme') === 'light';
      ctx.fillStyle = isLight ? '#1f2328' : '#e6edf3';
      ctx.font = `${Math.max(10, n.r * 0.8)}px -apple-system, sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(n.label, n.x, n.y + n.r + 14);
    }
  }

  function animate() {
    simulate();
    draw();
    animId = requestAnimationFrame(animate);
  }

  /* Mouse interaction */
  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }
  function hitTest(pos) {
    for (const n of nodes) {
      const dx = pos.x - n.x, dy = pos.y - n.y;
      if (dx * dx + dy * dy <= (n.r + 4) * (n.r + 4)) return n;
    }
    return null;
  }

  canvas.addEventListener('mousemove', e => {
    const pos = getPos(e);
    if (dragNode) {
      dragNode.x = pos.x;
      dragNode.y = pos.y;
      dragNode.vx = 0;
      dragNode.vy = 0;
      return;
    }
    const node = hitTest(pos);
    hoveredNode = node;
    canvas.style.cursor = node ? 'pointer' : 'default';
    if (node) {
      info.classList.remove('hidden');
      info.innerHTML = `
        <strong>${node.label}</strong><br>
        <span class="text-muted">Memories: ${node.memCount}</span><br>
        <span class="text-muted">Weight: ${node.weight.toFixed(1)}</span>
      `;
    } else {
      info.classList.add('hidden');
    }
  });

  canvas.addEventListener('mousedown', e => {
    dragNode = hitTest(getPos(e));
  });
  canvas.addEventListener('mouseup', () => { dragNode = null; });
  canvas.addEventListener('mouseleave', () => { dragNode = null; hoveredNode = null; });

  /* Search */
  root.querySelector('#graph-search').addEventListener('input', async (e) => {
    const q = e.target.value.trim();
    if (!q) {
      nodes.forEach(n => n._dim = false);
      return;
    }
    const lower = q.toLowerCase();
    nodes.forEach(n => { n._dim = !n.label.toLowerCase().includes(lower); });
  });
}
