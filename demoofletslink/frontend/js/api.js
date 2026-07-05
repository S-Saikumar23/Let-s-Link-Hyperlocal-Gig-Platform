const API_BASE = `${window.location.origin}/api`;

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('letslink_token');
  }

  setToken(token) {
    this.token = token;
    localStorage.setItem('letslink_token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('letslink_token');
    localStorage.removeItem('letslink_user');
  }

  async request(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
      if (res.status === 401) { 
        this.clearToken(); 
        if (window.location.hash !== '#/login') window.location.hash = '#/login'; 
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || 'Request failed');
      }
      if (res.status === 204) return null;
      return await res.json();
    } catch (e) {
      if (e.message === 'Failed to fetch') throw new Error('Server unavailable. Is the backend running?');
      throw e;
    }
  }

  get(endpoint) { return this.request(endpoint); }
  post(endpoint, data) { return this.request(endpoint, { method: 'POST', body: JSON.stringify(data) }); }
  put(endpoint, data) { return this.request(endpoint, { method: 'PUT', body: JSON.stringify(data) }); }
  delete(endpoint) { return this.request(endpoint, { method: 'DELETE' }); }
}

const api = new ApiClient();
