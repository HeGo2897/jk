/* NEXA TASK: api.js
 * The ONLY file that talks to the Python backend. Everything else calls the Api object.
 * Browser  --fetch (JSON over HTTP)-->  Flask server  --SQL-->  SQLite / MySQL
 */
'use strict';

// Same origin when the page is served by the Flask server. If index.html is opened
// directly from disk (file://), fall back to the default backend address.
const API_BASE = window.NEXA_API_BASE || (location.protocol === 'file:' ? 'http://localhost:8080' : '');

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; } // status 0 = server unreachable
}

async function apiRequest(method, path, body) {
  let response;
  try {
    response = await fetch(API_BASE + path, {
      method,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body)
    });
  } catch (networkError) {
    throw new ApiError(`Cannot connect to ${API_BASE || location.origin}. Is the Python server running?`, 0);
  }
  if (response.status === 204) return null;
  let data = null;
  try { data = await response.json(); } catch (e) { /* non-JSON body */ }
  if (!response.ok) throw new ApiError((data && data.error) || `Request failed (HTTP ${response.status})`, response.status);
  return data;
}

const Api = {
  health:        ()           => apiRequest('GET', '/api/health'),
  listTasks:     ()           => apiRequest('GET', '/api/tasks'),
  createTask:    data         => apiRequest('POST', '/api/tasks', data),
  updateTask:    (id, change) => apiRequest('PUT', `/api/tasks/${id}`, change),
  deleteTask:    id           => apiRequest('DELETE', `/api/tasks/${id}`),
  deleteAll:     ()           => apiRequest('DELETE', '/api/tasks'),
  loadSamples:   ()           => apiRequest('POST', '/api/tasks/sample'),
  listActivity:  ()           => apiRequest('GET', '/api/activity')
};
