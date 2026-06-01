/**
 * Hebb Mind API client — fetch wrapper for all /api/v1/* endpoints.
 */

const BASE = '';

async function request(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (res.status === 204) return null;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.error || res.statusText);
  }
  return res.json();
}

/* Health */
export const getHealth = () => request('GET', '/health');
export const getStatus = () => request('GET', '/status');

/* Partitions */
export const listPartitions = () => request('GET', '/api/v1/partitions');
export const getPartition = (id) => request('GET', `/api/v1/partitions/${id}`);
export const createPartition = (data) => request('POST', '/api/v1/partitions', data);
export const updatePartition = (id, data) => request('PATCH', `/api/v1/partitions/${id}`, data);
export const deletePartition = (id) => request('DELETE', `/api/v1/partitions/${id}`);

/* Memories */
export const listMemories = (params = {}) => {
  const q = new URLSearchParams();
  if (params.partition_id) q.set('partition_id', params.partition_id);
  if (params.tags) q.set('tags', params.tags);
  if (params.offset != null) q.set('offset', params.offset);
  if (params.limit != null) q.set('limit', params.limit);
  return request('GET', `/api/v1/memories?${q}`);
};
export const getMemory = (id) => request('GET', `/api/v1/memories/${id}`);
export const createMemory = (data) => request('POST', '/api/v1/memories', data);
export const createMemoriesBatch = (items) => request('POST', '/api/v1/memories/batch', items);
export const updateMemory = (id, data) => request('PATCH', `/api/v1/memories/${id}`, data);
export const deleteMemory = (id) => request('DELETE', `/api/v1/memories/${id}`);

/* Search */
export const searchMemories = (query) => request('POST', '/api/v1/search', query);

/* Graph */
export const listTags = (q) => request('GET', `/api/v1/graph/tags${q ? '?q=' + encodeURIComponent(q) : ''}`);
export const getTag = (id) => request('GET', `/api/v1/graph/tags/${id}`);
export const getNeighbors = (id, depth = 1) => request('GET', `/api/v1/graph/neighbors/${id}?depth=${depth}`);
export const getGraphPath = (from, to) => request('GET', `/api/v1/graph/path?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
export const exportGraph = () => request('GET', '/api/v1/graph/export');

/* Admin */
export const triggerConsolidate = () => request('POST', '/api/v1/admin/consolidate');
export const triggerForget = () => request('POST', '/api/v1/admin/forget');
export const getStats = () => request('GET', '/api/v1/admin/stats');
export const restartService = () => request('POST', '/api/v1/admin/restart');

/* Config */
export const getConfig = () => request('GET', '/api/v1/admin/config');
export const updateConfig = (key, value) => request('PUT', '/api/v1/admin/config', { key, value });
export const getConfigFields = () => request('GET', '/api/v1/admin/config/fields');
export const testLLM = (model, base_url, api_key) => request('POST', '/api/v1/admin/config/test-llm', { model, base_url, api_key });
export const testEmbedding = (params) => request('POST', '/api/v1/admin/config/test-embedding', params);
export const getTestEmbeddingStatus = (task_id) => request('GET', `/api/v1/admin/config/test-embedding/status/${task_id}`);
export const getEmbeddingStatus = () => request('GET', '/api/v1/admin/config/embedding-status');
export const revealConfigValue = (key) => request('GET', `/api/v1/admin/config/reveal/${key}`);

/* Upgrade */
export const getUpgradeState = () => request('GET', '/api/v1/admin/upgrade');
export const forceUpgradeCheck = () => request('POST', '/api/v1/admin/upgrade/check');

/* Claude Code memory documents */
export const listCCProjects = () => request('GET', '/api/v1/claude-memory/projects');
export const listCCFiles = (project) =>
  request('GET', `/api/v1/claude-memory/files?project=${encodeURIComponent(project)}`);
export const getCCFile = (project, name) =>
  request('GET', `/api/v1/claude-memory/file?project=${encodeURIComponent(project)}&name=${encodeURIComponent(name)}`);
export const saveCCFile = (project, name, content) =>
  request('PUT', '/api/v1/claude-memory/file', { project, name, content });
