/* ── Let's Link — Main Application ─────────────────────── */

const app = {
  user: JSON.parse(localStorage.getItem('letslink_user') || 'null'),
  categories: [],
  tasks: [],
  selectedCategory: null,
  currentPage: 'home',
  chatSocket: null,
  searchQuery: '',
  browseOffset: 0,
  browseLimit: 20,
  hasMoreTasks: true,

  async init() {
    window.addEventListener('hashchange', () => this.route());
    this.route();
    this.updateSOSVisibility();
  },

  route() {
    const hash = window.location.hash.slice(2) || 'home';
    const [page, param] = hash.split('/');
    this.currentPage = page;
    this.updateNav();

    // Close any open WebSocket when navigating away from chat
    if (page !== 'chat' && this.chatSocket) {
      this.chatSocket.close();
      this.chatSocket = null;
    }

    const pages = {
      home: () => this.renderHome(),
      browse: () => this.renderBrowse(),
      login: () => this.renderAuth('login'),
      register: () => this.renderAuth('register'),
      post: () => this.requireAuth(() => this.renderPostTask()),
      'my-tasks': () => this.requireAuth(() => this.renderMyTasks()),
      profile: () => this.requireAuth(() => this.renderProfile()),
      task: () => this.renderTaskDetail(param),
      chat: () => this.requireAuth(() => this.renderChat(param)),
      'verify-phone': () => this.requireAuth(() => this.renderVerifyPhone()),
    };
    (pages[page] || pages.home)();
    this.updateSOSVisibility();
  },

  requireAuth(fn) {
    if (!this.user) { window.location.hash = '#/login'; return; }
    fn();
  },

  updateNav() {
    const navEl = document.getElementById('main-nav');
    if (!navEl) return;
    navEl.querySelectorAll('.nav-link').forEach(l => {
      l.classList.toggle('active', l.dataset.page === this.currentPage);
    });
    document.getElementById('nav-auth').innerHTML = this.user
      ? `<button class="nav-link" onclick="app.renderProfile()" data-page="profile">👤 <span>${this.user.name.split(' ')[0]}</span></button>
         <button class="nav-link" onclick="app.logout()">🚪</button>`
      : `<a href="#/login" class="btn btn-primary btn-sm">Sign In</a>`;
  },

  /* ── Auth ──────────────────────────────────────────── */
  renderAuth(mode) {
    const isLogin = mode === 'login';
    document.getElementById('app').innerHTML = `
      <div class="page flex justify-center items-center" style="min-height:100vh;padding-top:64px">
        <div class="card" style="width:100%;max-width:420px">
          <h2 class="text-center" style="margin-bottom:8px">${isLogin ? 'Welcome Back' : 'Join Let\'s Link'}</h2>
          <p class="text-center text-secondary text-sm" style="margin-bottom:24px">${isLogin ? 'Sign in to continue' : 'Create your free account'}</p>
          <form onsubmit="app.handleAuth(event,'${mode}')" class="flex flex-col gap-md">
            ${!isLogin ? `<div class="form-group"><label class="form-label">Full Name</label><input class="form-input" id="auth-name" required placeholder="Your name"></div>` : ''}
            ${isLogin 
              ? `<div class="form-group"><label class="form-label">Email</label><input class="form-input" id="auth-email" type="email" required placeholder="email@example.com"></div>`
              : `<div class="form-group"><label class="form-label">Phone Number</label><input class="form-input" id="auth-phone" required placeholder="10-digit phone number"></div>
                 <div class="form-group"><label class="form-label">Email</label><input class="form-input" id="auth-email" type="email" required placeholder="email@example.com"></div>`
            }
            <div class="form-group"><label class="form-label">Password</label><input class="form-input" id="auth-pass" type="password" required placeholder="Min 6 characters" minlength="6"></div>
            ${!isLogin ? `<div class="form-group"><label class="form-label">I want to</label><select class="form-input" id="auth-role"><option value="both">Both: Find & Provide services</option><option value="requester">Find services (Requester)</option><option value="provider">Provide services (Provider)</option></select></div>` : ''}
            <button class="btn btn-primary btn-lg" type="submit">${isLogin ? 'Sign In' : 'Create Account'}</button>
          </form>
          <p class="text-center text-sm" style="margin-top:16px">
            ${isLogin ? 'Don\'t have an account? <a href="#/register">Sign up</a>' : 'Already have an account? <a href="#/login">Sign in</a>'}
          </p>
        </div>
      </div>`;
  },

  async handleAuth(e, mode) {
    e.preventDefault();
    const email = document.getElementById('auth-email').value;
    const password = document.getElementById('auth-pass').value;
    try {
      let data;
      if (mode === 'login') {
        data = await api.post('/auth/login', { email, password });
      } else {
        const phone = document.getElementById('auth-phone').value;
        data = await api.post('/auth/register', {
          phone, email, password,
          name: document.getElementById('auth-name').value,
          role: document.getElementById('auth-role').value,
        });
      }
      if (data) {
        api.setToken(data.access_token);
        this.user = data.user;
        localStorage.setItem('letslink_user', JSON.stringify(data.user));
        showToast(`Welcome, ${data.user.name}!`, 'success');
        window.location.hash = '#/browse';
      }
    } catch (err) { showToast(err.message, 'error'); }
  },

  logout() {
    api.clearToken();
    this.user = null;
    showToast('Signed out', 'info');
    window.location.hash = '#/home';
  },

  /* ── Home Page ─────────────────────────────────────── */
  renderHome() {
    document.getElementById('app').innerHTML = `
      <div class="page">
        <section class="hero container">
          <h1 class="hero-title">Get Things Done,<br><span class="text-gradient">Right In Your Neighborhood</span></h1>
          <p class="hero-subtitle">Need a fan repaired? Groceries delivered? Let's Link connects you with skilled people nearby — affordable, fast, and safe.</p>
          <div class="hero-actions">
            <a href="#/browse" class="btn btn-primary btn-lg">🔍 Find Help</a>
            <a href="#/${this.user ? 'post' : 'register'}" class="btn btn-secondary btn-lg">📝 Post a Task</a>
          </div>
        </section>

        <section class="container">
          <div class="stats-bar">
            <div class="stat-card"><div class="stat-number text-gradient">10K+</div><div class="stat-label">Tasks Completed</div></div>
            <div class="stat-card"><div class="stat-number text-gradient">5K+</div><div class="stat-label">Active Providers</div></div>
            <div class="stat-card"><div class="stat-number text-gradient">50+</div><div class="stat-label">Service Categories</div></div>
            <div class="stat-card"><div class="stat-number text-gradient">4.8★</div><div class="stat-label">Average Rating</div></div>
          </div>
        </section>

        <section class="section container">
          <h2 class="text-center" style="margin-bottom:8px">How It Works</h2>
          <p class="text-center text-secondary" style="margin-bottom:16px">Three simple steps to get any task done</p>
          <div class="steps-grid">
            <div class="step-card"><div class="step-number">1</div><div class="step-title">Post Your Task</div><div class="step-desc">Describe what you need, set a budget, and share your location.</div></div>
            <div class="step-card"><div class="step-number">2</div><div class="step-title">Get Offers</div><div class="step-desc">Nearby skilled people send you offers. Chat, compare, and pick the best.</div></div>
            <div class="step-card"><div class="step-number">3</div><div class="step-title">Task Done!</div><div class="step-desc">Your tasker completes the job. Pay securely and leave a review.</div></div>
          </div>
        </section>

        <section class="section container">
          <h2 class="text-center" style="margin-bottom:8px">Why Let's Link?</h2>
          <p class="text-center text-secondary" style="margin-bottom:8px">Built for everyone — from homeowners to job seekers</p>
          <div class="features-grid">
            <div class="feature-card"><div class="feature-icon">💰</div><div class="feature-title">Fair Pricing</div><div class="feature-desc">No middleman markup. Negotiate directly with service providers for the best price.</div></div>
            <div class="feature-card"><div class="feature-icon">📍</div><div class="feature-title">Hyperlocal</div><div class="feature-desc">Find help right in your neighborhood. Faster response, lower travel costs.</div></div>
            <div class="feature-card"><div class="feature-icon">🛡️</div><div class="feature-title">Safe & Secure</div><div class="feature-desc">Verified profiles, in-app chat, escrow payments, and SOS emergency button.</div></div>
            <div class="feature-card"><div class="feature-icon">💼</div><div class="feature-title">Earn Flexibly</div><div class="feature-desc">Pick tasks that match your skills. Work when you want, earn what you deserve.</div></div>
            <div class="feature-card"><div class="feature-icon">💬</div><div class="feature-title">Built-in Chat</div><div class="feature-desc">Discuss task details, share photos, and coordinate — all within the app.</div></div>
            <div class="feature-card"><div class="feature-icon">⭐</div><div class="feature-title">Trust System</div><div class="feature-desc">Ratings, reviews, and trust scores help you choose the right person every time.</div></div>
          </div>
        </section>

        <section class="section container text-center" style="padding:60px 0">
          <h2 style="margin-bottom:12px">Ready to Get Started?</h2>
          <p class="text-secondary" style="margin-bottom:24px">Join thousands of people already using Let's Link</p>
          <a href="#/${this.user ? 'post' : 'register'}" class="btn btn-primary btn-lg">Get Started — It's Free</a>
        </section>

        <footer class="footer"><div class="container">
          <div class="footer-grid">
            <div class="footer-col"><h4>Let's Link</h4><p class="text-muted" style="line-height:1.6">Connecting needs with skills, one task at a time.</p></div>
            <div class="footer-col"><h4>Platform</h4><a href="#/browse">Browse Tasks</a><a href="#/post">Post a Task</a><a href="#/register">Sign Up</a></div>
            <div class="footer-col"><h4>Categories</h4><a href="#">Electrical</a><a href="#">Plumbing</a><a href="#">Delivery</a><a href="#">Cleaning</a></div>
            <div class="footer-col"><h4>Support</h4><a href="#">Help Center</a><a href="#">Safety</a><a href="#">Terms</a><a href="#">Privacy</a></div>
          </div>
          <div class="footer-bottom">© 2026 Let's Link. All rights reserved.</div>
        </div></footer>
      </div>`;
  },

  /* ── Browse Tasks ──────────────────────────────────── */
  async renderBrowse() {
    // Show skeleton loaders
    document.getElementById('app').innerHTML = `
      <div class="page container">
        <div class="section-header" style="margin-top:16px"><h2>Browse Tasks</h2></div>
        <div class="tasks-grid">
          ${Array(6).fill('<div class="skeleton skeleton-card"></div>').join('')}
        </div>
      </div>`;
    try {
      if (!this.categories.length) this.categories = await api.get('/tasks/categories') || [];
    } catch(e) {
      this.categories = [
        {id:'1',name:'Electrical',icon:'zap'},{id:'2',name:'Plumbing',icon:'droplets'},
        {id:'3',name:'Cleaning',icon:'sparkles'},{id:'4',name:'Delivery',icon:'package'},
        {id:'5',name:'Carpentry',icon:'hammer'},{id:'6',name:'Tutoring',icon:'book-open'},
        {id:'7',name:'Tech Help',icon:'monitor'},{id:'8',name:'Other',icon:'more-horizontal'},
      ];
    }
    try {
      let url = '/tasks/?';
      if (this.selectedCategory) url += `category_id=${this.selectedCategory}&`;
      if (this.searchQuery) url += `search=${encodeURIComponent(this.searchQuery)}&`;
      url += `limit=${this.browseLimit}&offset=0`;
      this.tasks = await api.get(url) || [];
      this.browseOffset = this.tasks.length;
      this.hasMoreTasks = this.tasks.length >= this.browseLimit;
    } catch(e) {
      console.error('Failed to load tasks:', e);
      showToast(e.message || 'Failed to load tasks', 'error');
      this.tasks = [];
      this.hasMoreTasks = false;
    }

    document.getElementById('app').innerHTML = `
      <div class="page container">
        <div class="section-header" style="margin-top:16px">
          <h2>Browse Tasks</h2>
          ${this.user ? '<a href="#/post" class="btn btn-primary btn-sm">+ Post a Task</a>' : ''}
        </div>
        <div class="search-bar" style="margin:12px 0">
          <form onsubmit="app.handleSearch(event)" class="flex gap-sm">
            <input class="form-input" id="search-input" placeholder="Search tasks..." value="${escapeHtml(this.searchQuery)}" style="flex:1;border-radius:var(--radius-full)">
            <button class="btn btn-primary btn-sm" type="submit">🔍 Search</button>
            ${this.searchQuery ? '<button type="button" class="btn btn-secondary btn-sm" onclick="app.clearSearch()">✕ Clear</button>' : ''}
          </form>
        </div>
        <div class="categories-grid">${this.categories.map(c => renderCategoryCard(c, c.id === this.selectedCategory)).join('')}</div>
        ${this.selectedCategory ? `<div style="margin:12px 0"><button class="btn btn-secondary btn-sm" onclick="app.filterCategory(null)">✕ Clear Filter</button></div>` : ''}
        <div class="tasks-grid" id="tasks-list">
          ${this.tasks.length ? this.tasks.map(t => renderTaskCard(t)).join('') : `<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">📋</div><div class="empty-title">${this.searchQuery ? 'No tasks match your search' : 'No tasks found'}</div><div class="empty-desc">${this.searchQuery ? 'Try different keywords' : 'Be the first to post a task in this area!'}</div><a href="#/post" class="btn btn-primary">Post a Task</a></div>`}
        </div>
        ${this.hasMoreTasks && this.tasks.length ? `<button class="load-more-btn" onclick="app.loadMoreTasks()">Load More Tasks</button>` : ''}
      </div>`;
  },

  handleSearch(e) {
    e.preventDefault();
    this.searchQuery = document.getElementById('search-input').value.trim();
    this.renderBrowse();
  },

  clearSearch() {
    this.searchQuery = '';
    this.renderBrowse();
  },

  filterCategory(id, name) {
    this.selectedCategory = this.selectedCategory === id ? null : id;
    this.renderBrowse();
  },

  /* ── Post Task ─────────────────────────────────────── */
  async renderPostTask() {
    if (!this.categories.length) {
      try { this.categories = await api.get('/tasks/categories') || []; } catch(e) { this.categories = [{id:'1',name:'Electrical',icon:'zap'},{id:'2',name:'Plumbing',icon:'droplets'},{id:'3',name:'Delivery',icon:'package'},{id:'4',name:'Cleaning',icon:'sparkles'},{id:'5',name:'Other',icon:'more-horizontal'}]; }
    }
    const catOptions = this.categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    document.getElementById('app').innerHTML = `
      <div class="page container" style="max-width:640px">
        <h2 style="margin-bottom:24px">Post a New Task</h2>
        <form onsubmit="app.handlePostTask(event)" class="flex flex-col gap-md">
          <div class="form-group"><label class="form-label">Task Title *</label><input class="form-input" id="task-title" required placeholder="e.g. Fix ceiling fan in bedroom" maxlength="200"></div>
          <div class="form-group"><label class="form-label">Category *</label><select class="form-input" id="task-category" required>${catOptions}</select></div>
          <div class="form-group"><label class="form-label">Description</label><textarea class="form-input" id="task-desc" placeholder="Provide details about the task..."></textarea></div>
          <div class="flex gap-md">
            <div class="form-group" style="flex:1"><label class="form-label">Min Budget (₹)</label><input class="form-input" id="task-bmin" type="number" min="0" placeholder="100"></div>
            <div class="form-group" style="flex:1"><label class="form-label">Max Budget (₹)</label><input class="form-input" id="task-bmax" type="number" min="0" placeholder="500"></div>
          </div>
          <div class="form-group"><label class="form-label">Urgency</label><select class="form-input" id="task-urgency"><option value="flexible">Flexible</option><option value="this_week">This Week</option><option value="today">Today</option><option value="now">Right Now!</option></select></div>
          <div class="form-group"><label class="form-label">Address / Location</label><input class="form-input" id="task-address" placeholder="Your area or full address"></div>
          <div class="form-group">
            <label class="form-label">Task Photos (optional)</label>
            <input class="form-input" id="task-images" type="file" accept="image/*" multiple style="padding:10px">
            <span class="text-xs text-muted">Max 5MB per image. JPG, PNG, WebP supported.</span>
          </div>
          <button class="btn btn-primary btn-lg" type="submit" id="post-btn">🚀 Post Task</button>
        </form>
      </div>`;
  },

  async handlePostTask(e) {
    e.preventDefault();
    const btn = document.getElementById('post-btn');
    btn.disabled = true;
    btn.textContent = 'Posting...';
    try {
      // Try to get user's actual location
      let latitude = 12.9716, longitude = 77.5946; // Default: Bangalore
      try {
        const pos = await new Promise((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
        );
        latitude = pos.coords.latitude;
        longitude = pos.coords.longitude;
      } catch (geoErr) {
        console.log('Geolocation unavailable, using default location');
      }

      const task = await api.post('/tasks/', {
        title: document.getElementById('task-title').value,
        category_id: document.getElementById('task-category').value,
        description: document.getElementById('task-desc').value,
        budget_min: parseFloat(document.getElementById('task-bmin').value) || null,
        budget_max: parseFloat(document.getElementById('task-bmax').value) || null,
        urgency: document.getElementById('task-urgency').value,
        address: document.getElementById('task-address').value,
        latitude, longitude,
        visibility_radius_km: 5,
      });

      // Upload images if any
      const fileInput = document.getElementById('task-images');
      if (fileInput && fileInput.files.length > 0 && task) {
        for (const file of fileInput.files) {
          try {
            const formData = new FormData();
            formData.append('file', file);
            await fetch(`${API_BASE}/uploads/task-media/${task.id}`, {
              method: 'POST',
              headers: { 'Authorization': `Bearer ${api.token}` },
              body: formData,
            });
          } catch (imgErr) {
            console.warn('Image upload failed:', imgErr);
          }
        }
      }

      showToast('Task posted successfully!', 'success');
      window.location.hash = '#/browse';
    } catch (err) {
      showToast(err.message, 'error');
      btn.disabled = false;
      btn.textContent = '🚀 Post Task';
    }
  },

  /* ── Task Detail ───────────────────────────────────── */
  async viewTask(id) { window.location.hash = `#/task/${id}`; },

  async renderTaskDetail(id) {
    document.getElementById('app').innerHTML = `<div class="page container"><div class="loader"><div class="spinner"></div></div></div>`;
    let task;
    try { task = await api.get(`/tasks/${id}`); } catch(e) { console.error('Failed to load task:', e); showToast(e.message || 'Failed to load task', 'error'); task = null; }
    if (!task) { document.getElementById('app').innerHTML = `<div class="page container"><div class="empty-state"><div class="empty-icon">❌</div><div class="empty-title">Task not found</div><a href="#/browse" class="btn btn-primary">Back to Browse</a></div></div>`; return; }

    const isRequester = this.user && task.requester_id === this.user.id;
    const isProvider = this.user && task.provider_id === this.user.id;
    const isParticipant = isRequester || isProvider;
    const budget = task.budget_min && task.budget_max ? `₹${task.budget_min} – ₹${task.budget_max}` : task.budget_min ? `₹${task.budget_min}+` : 'Open to quotes';

    // Load offers if requester
    let offersHtml = '';
    if (isRequester && task.status === 'open') {
      try {
        const offers = await api.get(`/tasks/${task.id}/offers`);
        if (offers && offers.length > 0) {
          offersHtml = `
            <div class="card" style="margin-bottom:24px">
              <h3 style="margin-bottom:16px">📩 Offers Received (${offers.length})</h3>
              <div class="flex flex-col gap-md">
                ${offers.map(o => `
                  <div class="card" style="background:var(--bg-card);padding:16px">
                    <div class="flex justify-between items-center" style="margin-bottom:8px">
                      <div class="flex items-center gap-sm">
                        ${renderAvatar(o.provider?.name || 'User', 'sm')}
                        <div>
                          <div style="font-weight:600">${escapeHtml(o.provider?.name || 'Provider')}</div>
                          <div class="text-xs text-muted">${timeAgo(o.created_at)}</div>
                        </div>
                      </div>
                      <div class="task-budget">₹${o.offered_price}</div>
                    </div>
                    ${o.message ? `<p class="text-secondary text-sm" style="margin-bottom:12px">${escapeHtml(o.message)}</p>` : ''}
                    ${o.status === 'pending' ? `<button class="btn btn-success btn-sm" onclick="app.acceptOffer('${task.id}','${o.id}')">✅ Accept Offer</button>` : `<span class="badge badge-${o.status === 'accepted' ? 'success' : 'secondary'}">${o.status}</span>`}
                  </div>
                `).join('')}
              </div>
            </div>`;
        }
      } catch(e) {}
    }

    // Action buttons for requester
    let actionsHtml = '';
    if (isRequester) {
      const actions = [];
      if (task.status === 'assigned' || task.status === 'in_progress') {
        actions.push(`<button class="btn btn-success" onclick="app.completeTask('${task.id}')">✅ Mark Complete</button>`);
      }
      if (task.status === 'completed') {
        actions.push(`<button class="btn btn-primary" onclick="app.initiatePayment('${task.id}')">💰 Pay Now</button>`);
        actions.push(`<button class="btn btn-success btn-sm" onclick="app.releasePayment('${task.id}')">📤 Release Payment</button>`);
      }
      if (task.status === 'open' || task.status === 'assigned') {
        actions.push(`<button class="btn btn-danger btn-sm" onclick="app.cancelTask('${task.id}')">❌ Cancel Task</button>`);
      }
      if (isParticipant && ['assigned','in_progress','completed'].includes(task.status)) {
        actions.push(`<a href="#/chat/${task.id}" class="btn btn-secondary">💬 Open Chat</a>`);
      }
      if (isParticipant && task.status !== 'cancelled') {
        actions.push(`<button class="btn btn-warning btn-sm" onclick="app.showDisputeForm('${task.id}')">⚠️ Raise Dispute</button>`);
      }
      if (actions.length) {
        actionsHtml = `<div class="card" style="margin-bottom:24px"><div class="flex gap-md" style="flex-wrap:wrap">${actions.join('')}</div></div>`;
      }
    } else if (isProvider) {
      const actions = [];
      if (['assigned','in_progress','completed'].includes(task.status)) {
        actions.push(`<a href="#/chat/${task.id}" class="btn btn-secondary">💬 Open Chat</a>`);
      }
      if (task.status !== 'cancelled') {
        actions.push(`<button class="btn btn-warning btn-sm" onclick="app.showDisputeForm('${task.id}')">⚠️ Raise Dispute</button>`);
      }
      if (actions.length) {
        actionsHtml = `<div class="card" style="margin-bottom:24px"><div class="flex gap-md" style="flex-wrap:wrap">${actions.join('')}</div></div>`;
      }
    }

    document.getElementById('app').innerHTML = `
      <div class="page container" style="max-width:800px">
        <a href="#/browse" class="text-sm text-muted" style="display:inline-block;margin-bottom:16px">← Back to tasks</a>
        <div class="card" style="margin-bottom:24px">
          <div class="flex justify-between items-center" style="margin-bottom:16px;flex-wrap:wrap;gap:12px">
            <div>
              <h2 style="margin-bottom:4px">${escapeHtml(task.title)}</h2>
              <div class="task-meta">${getUrgencyBadge(task.urgency)} ${getStatusBadge(task.status)}<span class="text-sm text-muted">Posted ${timeAgo(task.created_at)}</span></div>
            </div>
            <div class="task-budget" style="font-size:1.5rem">${budget}</div>
          </div>
          ${task.description ? `<p class="text-secondary" style="margin-bottom:16px;line-height:1.7">${escapeHtml(task.description)}</p>` : ''}
          <div class="flex gap-md" style="flex-wrap:wrap">
            <span class="badge badge-primary">📍 ${task.address || 'Location set'}</span>
            <span class="badge badge-secondary">${task.offers_count || 0} offers</span>
            ${task.provider ? `<span class="badge badge-success">🔧 Assigned to ${escapeHtml(task.provider.name)}</span>` : ''}
          </div>
        </div>
        ${actionsHtml}
        ${offersHtml}
        ${!isRequester && this.user && task.status === 'open' ? `
          <div class="card" style="margin-bottom:24px">
            <h3 style="margin-bottom:16px">Make an Offer</h3>
            <form onsubmit="app.submitOffer(event,'${task.id}')" class="flex flex-col gap-md">
              <div class="form-group"><label class="form-label">Your Price (₹)</label><input class="form-input" id="offer-price" type="number" required min="1" placeholder="Enter your price"></div>
              <div class="form-group"><label class="form-label">Message (optional)</label><textarea class="form-input" id="offer-msg" placeholder="Why you're the right person for this task..." style="min-height:80px"></textarea></div>
              <button class="btn btn-success" type="submit">Send Offer</button>
            </form>
          </div>` : ''}
          
        <div id="dispute-form-container" style="display:none;margin-bottom:24px">
          <div class="card border-warning">
            <h3 style="margin-bottom:16px;color:var(--danger)">⚠️ Raise a Dispute</h3>
            <p class="text-sm text-secondary" style="margin-bottom:16px">Use this if there is a severe issue (fraud, damage, no-show, etc). Our team will intervene.</p>
            <form onsubmit="app.submitDispute(event,'${task.id}')" class="flex flex-col gap-md">
              <div class="form-group">
                <label class="form-label">Reason</label>
                <select class="form-input" id="dispute-reason" required>
                  <option value="damage">Property Damage</option>
                  <option value="incomplete">Incomplete Work</option>
                  <option value="fraud">Fraud / Scam</option>
                  <option value="overcharge">Overcharging</option>
                  <option value="no_show">Provider No-Show</option>
                  <option value="theft">Theft</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Description</label>
                <textarea class="form-input" id="dispute-desc" required placeholder="Explain what happened in detail..." style="min-height:100px"></textarea>
              </div>
              <div class="flex gap-sm">
                <button class="btn btn-danger" type="submit">Submit Dispute</button>
                <button class="btn btn-secondary" type="button" onclick="document.getElementById('dispute-form-container').style.display='none'">Cancel</button>
              </div>
            </form>
          </div>
        </div>

        ${isParticipant && ['assigned', 'in_progress', 'completed'].includes(task.status) ? `
          <div class="card" style="margin-bottom:24px">
            <div class="flex justify-between items-center" style="margin-bottom:16px">
              <h3>📸 Photo Proofs</h3>
              <button class="btn btn-primary btn-sm" onclick="document.getElementById('proof-upload').click()">+ Upload Proof</button>
              <input type="file" id="proof-upload" accept="image/*" style="display:none" onchange="app.uploadProof(this, '${task.id}')">
            </div>
            <div id="task-proofs-container" class="flex gap-sm" style="overflow-x:auto;padding-bottom:8px">
              <div class="text-sm text-muted">Loading proofs...</div>
            </div>
          </div>
        ` : ''}

        ${!this.user && task.status === 'open' ? `<div class="card text-center" style="margin-bottom:24px"><p style="margin-bottom:12px">Sign in to make an offer on this task</p><a href="#/login" class="btn btn-primary">Sign In</a></div>` : ''}
      </div>`;
    
    // Load proofs after rendering the container
    if (isParticipant && ['assigned', 'in_progress', 'completed'].includes(task.status)) {
      this.loadTaskProofs(task.id);
    }
  },

  async submitOffer(e, taskId) {
    e.preventDefault();
    try {
      await api.post(`/tasks/${taskId}/offers`, {
        task_id: taskId,
        offered_price: parseFloat(document.getElementById('offer-price').value),
        message: document.getElementById('offer-msg').value,
      });
      showToast('Offer sent!', 'success');
      this.renderTaskDetail(taskId);
    } catch (err) { showToast(err.message, 'error'); }
  },

  async acceptOffer(taskId, offerId) {
    try {
      await api.put(`/tasks/${taskId}/offers/${offerId}/accept`);
      showToast('Offer accepted! Provider has been assigned.', 'success');
      this.renderTaskDetail(taskId);
    } catch (err) { showToast(err.message, 'error'); }
  },

  async completeTask(taskId) {
    if (!confirm('Mark this task as completed?')) return;
    try {
      await api.put(`/tasks/${taskId}/complete`);
      showToast('Task marked as completed!', 'success');
      this.renderTaskDetail(taskId);
    } catch (err) { showToast(err.message, 'error'); }
  },

  async cancelTask(taskId) {
    if (!confirm('Are you sure you want to cancel this task? This cannot be undone.')) return;
    try {
      await api.put(`/tasks/${taskId}/cancel`);
      showToast('Task cancelled.', 'info');
      this.renderTaskDetail(taskId);
    } catch (err) { showToast(err.message, 'error'); }
  },

  /* ── Chat ─────────────────────────────────────────── */
  async renderChat(taskId) {
    if (!taskId) { window.location.hash = '#/my-tasks'; return; }
    document.getElementById('app').innerHTML = `<div class="page container"><div class="loader"><div class="spinner"></div></div></div>`;

    // Load task info
    let task;
    try { task = await api.get(`/tasks/${taskId}`); } catch(e) {}

    // Load message history
    let messages = [];
    try { messages = await api.get(`/chat/${taskId}/messages`) || []; } catch(e) {}

    const otherName = task ? (task.requester_id === this.user.id
      ? (task.provider?.name || 'Provider')
      : (task.requester?.name || 'Requester')) : 'Chat';

    document.getElementById('app').innerHTML = `
      <div class="page" style="display:flex;flex-direction:column;height:100vh;padding-top:64px">
        <div style="padding:16px 20px;background:var(--bg-surface);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px">
          <a href="#/task/${taskId}" class="text-muted" style="font-size:1.2rem">←</a>
          ${renderAvatar(otherName, 'sm')}
          <div>
            <div style="font-weight:600;font-size:0.95rem">${escapeHtml(otherName)}</div>
            <div class="text-xs text-muted">${task ? escapeHtml(task.title) : 'Chat'}</div>
          </div>
        </div>
        <div class="chat-messages" id="chat-messages">
          ${messages.length ? messages.map(m => this.renderChatBubble(m)).join('') : '<div class="text-center text-muted" style="padding:40px">No messages yet. Start the conversation!</div>'}
        </div>
        <div class="chat-input-area">
          <input class="form-input" id="chat-input" placeholder="Type a message..." autocomplete="off" onkeydown="if(event.key==='Enter'){event.preventDefault();app.sendChatMessage('${taskId}')}">
          <button class="btn btn-primary btn-icon" onclick="app.sendChatMessage('${taskId}')">📤</button>
        </div>
      </div>`;

    // Scroll to bottom
    const chatContainer = document.getElementById('chat-messages');
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Connect WebSocket
    this.connectChatSocket(taskId);
  },

  renderChatBubble(msg) {
    const isSent = msg.sender_id === this.user.id;
    const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return `
      <div class="chat-bubble ${isSent ? 'sent' : 'received'}">
        ${!isSent ? `<div class="text-xs" style="font-weight:600;margin-bottom:4px;opacity:0.7">${escapeHtml(msg.sender_name || 'User')}</div>` : ''}
        ${escapeHtml(msg.content)}
        <div class="time">${time}</div>
      </div>`;
  },

  connectChatSocket(taskId) {
    if (this.chatSocket) { this.chatSocket.close(); this.chatSocket = null; }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/chat/ws/${taskId}?token=${api.token}`;

    try {
      this.chatSocket = new WebSocket(wsUrl);

      this.chatSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'message') {
          const chatContainer = document.getElementById('chat-messages');
          if (chatContainer) {
            // Remove "no messages" placeholder
            const placeholder = chatContainer.querySelector('.text-center.text-muted');
            if (placeholder) placeholder.remove();

            const bubble = document.createElement('div');
            bubble.className = 'chat-bubble received';
            bubble.innerHTML = `
              <div class="text-xs" style="font-weight:600;margin-bottom:4px;opacity:0.7">${escapeHtml(data.sender_name || 'User')}</div>
              ${escapeHtml(data.content)}
              <div class="time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>`;
            chatContainer.appendChild(bubble);
            chatContainer.scrollTop = chatContainer.scrollHeight;
          }
        }
      };

      this.chatSocket.onclose = () => { this.chatSocket = null; };
      this.chatSocket.onerror = () => { console.warn('WebSocket error'); };
    } catch(e) {
      console.warn('WebSocket connection failed:', e);
    }
  },

  async sendChatMessage(taskId) {
    const input = document.getElementById('chat-input');
    const content = input.value.trim();
    if (!content) return;

    input.value = '';

    // Add bubble immediately (optimistic UI)
    const chatContainer = document.getElementById('chat-messages');
    if (chatContainer) {
      const placeholder = chatContainer.querySelector('.text-center.text-muted');
      if (placeholder) placeholder.remove();

      const bubble = document.createElement('div');
      bubble.className = 'chat-bubble sent';
      bubble.innerHTML = `${escapeHtml(content)}<div class="time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>`;
      chatContainer.appendChild(bubble);
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Send via WebSocket if connected
    if (this.chatSocket && this.chatSocket.readyState === WebSocket.OPEN) {
      this.chatSocket.send(JSON.stringify({ content, message_type: 'text' }));
    } else {
      // Fallback to REST
      try {
        await api.post(`/chat/${taskId}/messages`, { task_id: taskId, content, message_type: 'text' });
      } catch (err) { showToast('Failed to send message', 'error'); }
    }
  },

  /* ── My Tasks ──────────────────────────────────────── */
  async renderMyTasks() {
    document.getElementById('app').innerHTML = `<div class="page container"><div class="loader"><div class="spinner"></div></div></div>`;
    let posted = [], accepted = [];
    try { posted = await api.get('/tasks/my-tasks?role=requester') || []; } catch(e) {}
    try { accepted = await api.get('/tasks/my-tasks?role=provider') || []; } catch(e) {}

    document.getElementById('app').innerHTML = `
      <div class="page container">
        <h2 style="margin-bottom:24px">My Tasks</h2>
        <h3 style="margin-bottom:12px">Tasks I Posted</h3>
        <div class="tasks-grid" style="margin-bottom:32px">${posted.length ? posted.map(t => renderTaskCard(t)).join('') : '<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">📋</div><div class="empty-title">No tasks posted yet</div><a href="#/post" class="btn btn-primary btn-sm">Post Your First Task</a></div>'}</div>
        <h3 style="margin-bottom:12px">Tasks I Accepted</h3>
        <div class="tasks-grid">${accepted.length ? accepted.map(t => renderTaskCard(t)).join('') : '<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">💼</div><div class="empty-title">No accepted tasks yet</div><a href="#/browse" class="btn btn-primary btn-sm">Browse Available Tasks</a></div>'}</div>
      </div>`;
  },

  /* ── Profile ───────────────────────────────────────── */
  async renderProfile() {
    if (!this.user) { window.location.hash = '#/login'; return; }
    window.location.hash = '#/profile';
    document.getElementById('app').innerHTML = `<div class="page container" style="max-width:700px"><div class="loader"><div class="spinner"></div></div></div>`;

    // Fetch real stats from API
    let tasksDone = '—', avgRating = '—', earned = '—';
    try {
      const profile = await api.get(`/users/${this.user.id}`);
      if (profile) {
        tasksDone = profile.tasks_completed || 0;
        avgRating = profile.avg_rating ? `${profile.avg_rating}★` : 'N/A';
      }
    } catch(e) {}
    try {
      const summary = await api.get(`/reviews/user/${this.user.id}/summary`);
      if (summary) {
        avgRating = summary.average_rating ? `${summary.average_rating}★` : 'N/A';
      }
    } catch(e) {}

    document.getElementById('app').innerHTML = `
      <div class="page container" style="max-width:700px">
        <div class="profile-header">
          <div class="relative">
            ${this.user.avatar_url
              ? `<img src="${this.user.avatar_url}" alt="Avatar" style="width:88px;height:88px;border-radius:50%;object-fit:cover;border:3px solid var(--primary)">`
              : renderAvatar(this.user.name, 'xl')}
            <label for="avatar-upload" class="btn btn-icon btn-primary" style="position:absolute;bottom:0;right:0;width:28px;height:28px;font-size:0.8rem;cursor:pointer">📷</label>
            <input type="file" id="avatar-upload" accept="image/*" style="display:none" onchange="app.uploadAvatar(this)">
          </div>
          <div class="profile-info">
            <div class="profile-name">${escapeHtml(this.user.name)}</div>
            <div class="text-secondary text-sm">📞 ${this.user.phone} ${this.user.email ? '· ✉️ ' + this.user.email : ''}</div>
            <div class="flex gap-md" style="margin-top:8px;flex-wrap:wrap">
              <span class="badge badge-primary">${this.user.role === 'both' ? '🔄 Requester & Provider' : this.user.role === 'requester' ? '📋 Requester' : '🔧 Provider'}</span>
              <span class="badge badge-success">Trust: ${this.user.trust_score}/100</span>
              <span class="badge badge-secondary">${this.user.verification_level} verified</span>
            </div>
            <div class="profile-stats">
              <div><div class="profile-stat-value">${tasksDone}</div><div class="profile-stat-label">Tasks Done</div></div>
              <div><div class="profile-stat-value">${avgRating}</div><div class="profile-stat-label">Rating</div></div>
              <div><div class="profile-stat-value">${earned}</div><div class="profile-stat-label">Earned</div></div>
            </div>
          </div>
        </div>
        </div>
        <div class="flex gap-md" style="margin-top:24px;flex-wrap:wrap">
          ${!this.user.is_phone_verified ? `<a href="#/verify-phone" class="btn btn-warning" style="flex:1">📱 Verify Phone</a>` : ''}
          <a href="#/my-tasks" class="btn btn-secondary" style="flex:1">📋 My Tasks</a>
          <a href="#/post" class="btn btn-primary" style="flex:1">+ Post Task</a>
          <button class="btn btn-danger btn-sm" onclick="app.logout()">Sign Out</button>
        </div>

        <div class="card" style="margin-top:24px">
          <h3 style="margin-bottom:16px">🛡️ Verification Center</h3>
          <p class="text-sm text-secondary" style="margin-bottom:16px">Upload your PAN Card, Driving License, or Skill Certificates to build trust and increase your score. Verified users get 3x more tasks.</p>
          <div id="my-documents" style="margin-bottom:24px">
            <div class="loader" style="transform:scale(0.5);margin:0"></div>
          </div>
          
          <h4 style="margin-bottom:12px;font-size:1rem">Upload New Document</h4>
          <form onsubmit="app.uploadDocument(event)" class="flex flex-col gap-md">
            <div class="form-group">
              <label class="form-label">Document Type</label>
              <select class="form-input" id="doc-type" required>
                <option value="pan_card">PAN Card</option>
                <option value="driving_license">Driving License</option>
                <option value="voter_id">Voter ID</option>
                <option value="skill_certificate">Skill Certificate (ITI/Diploma)</option>
                <option value="trade_license">Trade License</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Title (e.g. ITI Electrician)</label>
              <input class="form-input" id="doc-title" required placeholder="Document title">
            </div>
            <div class="form-group">
              <label class="form-label">Document File (Image/PDF, max 5MB)</label>
              <input class="form-input" type="file" id="doc-file" required accept=".jpg,.jpeg,.png,.webp,.pdf">
            </div>
            <button class="btn btn-primary" type="submit">Upload Document</button>
          </form>
        </div>
      </div>`;
    this.loadMyDocuments();
  },

  async uploadAvatar(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    if (file.size > 2 * 1024 * 1024) { showToast('Image too large. Max 2MB.', 'error'); return; }

    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/uploads/avatar`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${api.token}` },
        body: formData,
      });
      if (!res.ok) throw new Error('Upload failed');
      const data = await res.json();
      this.user.avatar_url = data.url;
      localStorage.setItem('letslink_user', JSON.stringify(this.user));
      showToast('Avatar updated!', 'success');
      this.renderProfile();
    } catch (err) { showToast(err.message || 'Upload failed', 'error'); }
  },

  async loadMyDocuments() {
    try {
      const docs = await api.get('/documents/my');
      const container = document.getElementById('my-documents');
      if (!docs || docs.length === 0) {
        container.innerHTML = '<div class="text-sm text-muted">No documents uploaded yet.</div>';
        return;
      }
      container.innerHTML = docs.map(d => `
        <div class="card" style="padding:12px;margin-bottom:12px;background:var(--bg-card)">
          <div class="flex justify-between items-center">
            <div>
              <div style="font-weight:600">${escapeHtml(d.title)}</div>
              <div class="text-xs text-muted">${d.doc_type}</div>
            </div>
            <div class="flex items-center gap-sm">
              <span class="badge badge-${d.status === 'approved' ? 'success' : d.status === 'rejected' ? 'danger' : 'warning'}">${d.status}</span>
              ${d.status !== 'approved' ? `<button class="btn btn-icon text-danger" onclick="app.deleteDocument('${d.id}')" title="Delete">🗑️</button>` : ''}
            </div>
          </div>
          ${d.admin_notes ? `<div class="text-xs text-danger" style="margin-top:8px">Admin note: ${escapeHtml(d.admin_notes)}</div>` : ''}
        </div>
      `).join('');
    } catch (e) {
      document.getElementById('my-documents').innerHTML = '<div class="text-sm text-danger">Failed to load documents</div>';
    }
  },

  async uploadDocument(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true; btn.textContent = 'Uploading...';
    try {
      const formData = new FormData();
      formData.append('doc_type', document.getElementById('doc-type').value);
      formData.append('title', document.getElementById('doc-title').value);
      formData.append('file', document.getElementById('doc-file').files[0]);

      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${api.token}` },
        body: formData,
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
      showToast('Document uploaded successfully!', 'success');
      e.target.reset();
      this.loadMyDocuments();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false; btn.textContent = 'Upload Document';
    }
  },

  async deleteDocument(id) {
    if (!confirm('Delete this document?')) return;
    try {
      await api.delete(`/documents/${id}`);
      showToast('Document deleted', 'success');
      this.loadMyDocuments();
    } catch(e) {
      showToast('Failed to delete document', 'error');
    }
  },

  /* ── Disputes & Proofs ──────────────────────────────── */
  showDisputeForm(taskId) {
    const el = document.getElementById('dispute-form-container');
    if (el) {
      el.style.display = 'block';
      el.scrollIntoView({ behavior: 'smooth' });
    }
  },

  async submitDispute(e, taskId) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true; btn.textContent = 'Submitting...';
    try {
      const payload = {
        task_id: taskId,
        reason: document.getElementById('dispute-reason').value,
        description: document.getElementById('dispute-desc').value,
      };
      await api.post('/disputes/raise', payload);
      showToast('Dispute raised successfully. Our team will review it.', 'success');
      document.getElementById('dispute-form-container').style.display = 'none';
      this.renderTaskDetail(taskId);
    } catch (err) {
      showToast(err.message || 'Failed to raise dispute', 'error');
    } finally {
      btn.disabled = false; btn.textContent = 'Submit Dispute';
    }
  },

  async uploadProof(input, taskId) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    if (file.size > 5 * 1024 * 1024) { showToast('Image too large. Max 5MB.', 'error'); return; }

    try {
      const formData = new FormData();
      formData.append('file', file);
      // Determine proof type based on task status (simplified logic)
      formData.append('proof_type', 'completion'); 
      formData.append('caption', 'Uploaded via UI');

      const res = await fetch(`${API_BASE}/tasks/${taskId}/proof`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${api.token}` },
        body: formData,
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
      showToast('Proof uploaded!', 'success');
      this.loadTaskProofs(taskId);
    } catch (err) { showToast(err.message || 'Upload failed', 'error'); }
  },

  async loadTaskProofs(taskId) {
    const container = document.getElementById('task-proofs-container');
    if (!container) return;
    try {
      const proofs = await api.get(`/tasks/${taskId}/proofs`);
      if (!proofs || proofs.length === 0) {
        container.innerHTML = '<div class="text-sm text-muted">No proofs uploaded yet.</div>';
        return;
      }
      container.innerHTML = proofs.map(p => `
        <div style="flex:0 0 auto;width:120px;border-radius:8px;overflow:hidden;border:1px solid var(--border)">
          <a href="${p.file_url}" target="_blank">
            <img src="${p.file_url}" alt="Proof" style="width:100%;height:100px;object-fit:cover">
          </a>
          <div style="padding:4px;text-align:center;font-size:0.75rem;background:var(--bg-card)">
            ${p.proof_type}
          </div>
        </div>
      `).join('');
    } catch(e) {
      container.innerHTML = '<div class="text-sm text-danger">Failed to load proofs</div>';
    }
  },

  /* ── Load More (Pagination) ─────────────────────────── */
  async loadMoreTasks() {
    const btn = document.querySelector('.load-more-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Loading...'; }
    try {
      let url = `/tasks/?limit=${this.browseLimit}&offset=${this.browseOffset}`;
      if (this.selectedCategory) url += `&category_id=${this.selectedCategory}`;
      if (this.searchQuery) url += `&search=${encodeURIComponent(this.searchQuery)}`;
      const moreTasks = await api.get(url) || [];
      this.tasks = [...this.tasks, ...moreTasks];
      this.browseOffset += moreTasks.length;
      this.hasMoreTasks = moreTasks.length >= this.browseLimit;

      const grid = document.getElementById('tasks-list');
      if (grid) {
        moreTasks.forEach(t => { grid.insertAdjacentHTML('beforeend', renderTaskCard(t)); });
      }
      if (!this.hasMoreTasks && btn) btn.remove();
      else if (btn) { btn.disabled = false; btn.textContent = 'Load More Tasks'; }
    } catch(e) {
      if (btn) { btn.disabled = false; btn.textContent = 'Load More Tasks'; }
      showToast('Failed to load more tasks', 'error');
    }
  },

  /* ── SOS ────────────────────────────────────────────── */
  updateSOSVisibility() {
    const sosBtn = document.getElementById('sos-btn');
    if (!sosBtn) return;
    // Show SOS if user is logged in
    sosBtn.style.display = this.user ? 'flex' : 'none';
  },

  async triggerSOS() {
    if (!confirm('🆘 EMERGENCY!\n\nThis will send an SOS alert with your location. Continue?')) return;
    try {
      // Try getting current location
      try {
        const pos = await new Promise((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
        );
        await api.put('/users/me', { latitude: pos.coords.latitude, longitude: pos.coords.longitude });
      } catch(e) {}

      const res = await api.post('/safety/sos');
      showToast('🆘 SOS Alert sent! Stay safe.', 'warning');
      if (res.emergency_contact) {
        showToast(`Emergency contact (${res.emergency_contact}) will be notified.`, 'info');
      } else {
        showToast('Tip: Set an emergency contact in your profile.', 'info');
      }
    } catch (err) { showToast(err.message || 'SOS failed', 'error'); }
  },

  /* ── OTP Verification ──────────────────────────────── */
  async renderVerifyPhone() {
    if (!this.user) { window.location.hash = '#/login'; return; }
    document.getElementById('app').innerHTML = `
      <div class="page flex justify-center items-center" style="min-height:100vh;padding-top:64px">
        <div class="card" style="width:100%;max-width:420px;text-align:center">
          <h2 style="margin-bottom:8px">📱 Verify Your Phone</h2>
          <p class="text-secondary text-sm" style="margin-bottom:24px">We'll send a 6-digit code to <strong>${this.user.phone}</strong></p>
          <div id="otp-step-1">
            <button class="btn btn-primary btn-lg" style="width:100%" onclick="app.sendOTP()">Send OTP</button>
          </div>
          <div id="otp-step-2" style="display:none">
            <div class="form-group" style="margin-bottom:16px">
              <input class="form-input otp-input" id="otp-code" maxlength="6" placeholder="------" autocomplete="one-time-code">
            </div>
            <button class="btn btn-primary btn-lg" style="width:100%;margin-bottom:12px" onclick="app.verifyOTP()">Verify Code</button>
            <button class="btn btn-secondary btn-sm" onclick="app.sendOTP()">Resend OTP</button>
          </div>
        </div>
      </div>`;
  },

  async sendOTP() {
    try {
      const res = await api.post('/safety/otp/send', { phone: this.user.phone });
      showToast(res.message || 'OTP sent!', 'success');
      // In dev mode, show the OTP
      if (res.dev_otp) {
        showToast(`Dev OTP: ${res.dev_otp}`, 'info');
      }
      document.getElementById('otp-step-1').style.display = 'none';
      document.getElementById('otp-step-2').style.display = 'block';
    } catch (err) { showToast(err.message, 'error'); }
  },

  async verifyOTP() {
    const otp = document.getElementById('otp-code').value.trim();
    if (otp.length !== 6) { showToast('Enter the 6-digit OTP', 'error'); return; }
    try {
      const res = await api.post('/safety/otp/verify', { phone: this.user.phone, otp });
      this.user.is_phone_verified = true;
      localStorage.setItem('letslink_user', JSON.stringify(this.user));
      showToast('✅ Phone verified successfully!', 'success');
      window.location.hash = '#/profile';
    } catch (err) { showToast(err.message, 'error'); }
  },

  /* ── Report User ───────────────────────────────────── */
  async reportUser(userId, userName) {
    const reason = prompt(`Report ${userName}?\n\nSelect reason:\n1. Harassment\n2. Fraud/Scam\n3. Spam\n4. Inappropriate behavior\n5. Other\n\nEnter number (1-5):`);
    const reasons = { '1': 'harassment', '2': 'fraud', '3': 'spam', '4': 'inappropriate', '5': 'other' };
    if (!reason || !reasons[reason]) return;

    const description = prompt('Any additional details? (optional)');
    try {
      await api.post('/safety/reports', {
        reported_id: userId,
        reason: reasons[reason],
        description: description || null,
      });
      showToast('Report submitted. Thank you for keeping the community safe.', 'success');
    } catch (err) { showToast(err.message, 'error'); }
  },

  /* ── Razorpay Payment ──────────────────────────────── */
  async initiatePayment(taskId) {
    try {
      const order = await api.post('/payments/create-order', { task_id: taskId });

      // Demo mode — show simulated payment UI
      if (order.demo_mode) {
        this.showDemoPayment(taskId, order);
        return;
      }

      // Real Razorpay checkout
      const options = {
        key: order.razorpay_key_id,
        amount: order.amount * 100,
        currency: order.currency,
        name: "Let's Link",
        description: `Payment for Task`,
        order_id: order.order_id,
        handler: async (response) => {
          try {
            await api.post('/payments/verify', {
              task_id: taskId,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });
            showToast('💰 Payment successful! Held in escrow.', 'success');
            this.renderTaskDetail(taskId);
          } catch (err) { showToast('Payment verification failed', 'error'); }
        },
        prefill: {
          name: this.user.name,
          contact: this.user.phone,
          email: this.user.email || '',
        },
        theme: { color: '#6C5CE7' },
      };

      const rzp = new Razorpay(options);
      rzp.open();
    } catch (err) { showToast(err.message || 'Payment failed', 'error'); }
  },

  showDemoPayment(taskId, order) {
    const providerReceives = order.provider_receives;
    showModal('💰 Payment', `
      <div style="text-align:center">
        <div style="font-size:2rem;font-weight:700;color:var(--primary);margin-bottom:4px">₹${order.amount}</div>
        <div class="text-sm text-muted" style="margin-bottom:20px">Platform fee: ₹${order.platform_fee} · Provider receives: ₹${providerReceives}</div>
        
        <div style="background:var(--bg-card);border-radius:12px;padding:16px;margin-bottom:16px;border:1px solid var(--border)">
          <div class="text-sm" style="font-weight:600;margin-bottom:12px">Select Payment Method</div>
          <div class="flex gap-sm" style="justify-content:center;flex-wrap:wrap">
            <label style="cursor:pointer;padding:10px 20px;border-radius:8px;border:2px solid var(--primary);background:var(--primary-alpha);display:flex;align-items:center;gap:8px">
              <input type="radio" name="demo-pay" value="upi" checked style="accent-color:var(--primary)"> 📱 UPI
            </label>
            <label style="cursor:pointer;padding:10px 20px;border-radius:8px;border:2px solid var(--border);display:flex;align-items:center;gap:8px">
              <input type="radio" name="demo-pay" value="card" style="accent-color:var(--primary)"> 💳 Card
            </label>
            <label style="cursor:pointer;padding:10px 20px;border-radius:8px;border:2px solid var(--border);display:flex;align-items:center;gap:8px">
              <input type="radio" name="demo-pay" value="wallet" style="accent-color:var(--primary)"> 👛 Wallet
            </label>
          </div>
        </div>

        <div id="demo-pay-status" style="display:none;margin-bottom:16px">
          <div class="spinner" style="margin:0 auto 8px"></div>
          <div class="text-sm text-muted">Processing payment...</div>
        </div>

        <button class="btn btn-primary btn-lg" style="width:100%" id="demo-pay-btn" onclick="app.processDemoPayment('${taskId}', '${order.order_id}')">
          Pay ₹${order.amount}
        </button>
        <div class="text-xs text-muted" style="margin-top:12px">🔒 Demo mode — no real money is charged</div>
      </div>
    `);
  },

  async processDemoPayment(taskId, orderId) {
    const btn = document.getElementById('demo-pay-btn');
    const status = document.getElementById('demo-pay-status');
    if (btn) { btn.disabled = true; btn.textContent = 'Processing...'; }
    if (status) status.style.display = 'block';

    // Simulate processing delay
    await new Promise(r => setTimeout(r, 2000));

    try {
      await api.post('/payments/verify', {
        task_id: taskId,
        razorpay_order_id: orderId,
        razorpay_payment_id: `demo_pay_${Date.now()}`,
        razorpay_signature: 'demo_signature',
      });
      closeModal();
      showToast('💰 Payment successful! Held in escrow until you release it.', 'success');
      this.renderTaskDetail(taskId);
    } catch (err) {
      showToast(err.message || 'Payment failed', 'error');
      if (btn) { btn.disabled = false; btn.textContent = 'Retry Payment'; }
      if (status) status.style.display = 'none';
    }
  },

  async releasePayment(taskId) {
    if (!confirm('Release payment to the provider? This cannot be undone.')) return;
    try {
      const res = await api.post('/payments/release', { task_id: taskId });
      showToast(`💰 ₹${res.amount_released} released to provider!`, 'success');
      this.renderTaskDetail(taskId);
    } catch (err) { showToast(err.message, 'error'); }
  },


};

document.addEventListener('DOMContentLoaded', () => app.init());
