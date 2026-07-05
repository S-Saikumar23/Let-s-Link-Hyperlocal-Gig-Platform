/* ── Reusable UI Components ────────────────────────────── */

const Icons = {
  zap: '⚡', droplets: '🔧', sparkles: '✨', package: '📦', truck: '🚚',
  paintbrush: '🎨', hammer: '🔨', 'book-open': '📚', 'chef-hat': '👨‍🍳',
  'paw-print': '🐾', 'flower-2': '🌱', monitor: '💻', 'party-popper': '🎉',
  'more-horizontal': '➕', search: '🔍', mapPin: '📍', clock: '🕐',
  star: '⭐', chat: '💬', shield: '🛡️', wallet: '💰', user: '👤',
  bell: '🔔', heart: '❤️', check: '✅', x: '❌', send: '📤',
  home: '🏠', briefcase: '💼', settings: '⚙️', logout: '🚪',
};

function getUrgencyBadge(urgency) {
  const map = {
    now: { class: 'badge-error', label: '🔴 Urgent' },
    today: { class: 'badge-warning', label: '🟡 Today' },
    this_week: { class: 'badge-primary', label: '🔵 This Week' },
    flexible: { class: 'badge-secondary', label: '🟢 Flexible' },
  };
  const b = map[urgency] || map.flexible;
  return `<span class="badge ${b.class}">${b.label}</span>`;
}

function getStatusBadge(status) {
  const map = {
    open: { class: 'badge-success', label: 'Open' },
    assigned: { class: 'badge-primary', label: 'Assigned' },
    in_progress: { class: 'badge-warning', label: 'In Progress' },
    completed: { class: 'badge-secondary', label: 'Completed' },
    cancelled: { class: 'badge-error', label: 'Cancelled' },
    disputed: { class: 'badge-error', label: 'Disputed' },
  };
  const b = map[status] || map.open;
  return `<span class="badge ${b.class}">${b.label}</span>`;
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function renderStars(rating, max = 5) {
  let html = '<span class="stars">';
  for (let i = 1; i <= max; i++) {
    html += `<span class="star ${i <= rating ? 'filled' : ''}">★</span>`;
  }
  html += '</span>';
  return html;
}

function avatarInitials(name) {
  return (name || '?').split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
}

function renderAvatar(name, size = '') {
  const cls = size ? `avatar avatar-${size}` : 'avatar';
  return `<div class="${cls}">${avatarInitials(name)}</div>`;
}

function renderTaskCard(task) {
  const budget = task.budget_min && task.budget_max
    ? `₹${task.budget_min} – ₹${task.budget_max}`
    : task.budget_min ? `₹${task.budget_min}+` : 'Open to quotes';

  const categoryName = task.category?.name || 'General';
  const categoryIcon = Icons[task.category?.icon] || '📋';

  return `
    <div class="task-card" onclick="app.viewTask('${task.id}')">
      <div class="task-header">
        <div>
          <div class="task-title">${escapeHtml(task.title)}</div>
          <div class="task-meta" style="margin-top:8px">
            <span class="task-meta-item">${categoryIcon} ${categoryName}</span>
            <span class="task-meta-item">📍 ${task.address || 'Nearby'}</span>
            <span class="task-meta-item">🕐 ${timeAgo(task.created_at)}</span>
          </div>
        </div>
        ${getUrgencyBadge(task.urgency)}
      </div>
      ${task.description ? `<p class="text-secondary text-sm" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${escapeHtml(task.description)}</p>` : ''}
      <div class="task-footer">
        <span class="task-budget">${budget}</span>
        <div class="flex items-center gap-sm">
          <span class="text-sm text-muted">${task.offers_count || 0} offers</span>
          ${getStatusBadge(task.status)}
        </div>
      </div>
    </div>`;
}

function renderCategoryCard(cat, selected = false) {
  const icon = Icons[cat.icon] || '📋';
  return `
    <div class="category-card ${selected ? 'selected' : ''}" onclick="app.filterCategory('${cat.id}', '${cat.name}')">
      <div class="category-icon">${icon}</div>
      <span class="category-name">${cat.name}</span>
    </div>`;
}

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3500);
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function showModal(title, bodyHtml, footerHtml = '') {
  closeModal();
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'active-modal';
  overlay.onclick = (e) => { if (e.target === overlay) closeModal(); };
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h3>${title}</h3>
        <button class="modal-close" onclick="closeModal()">✕</button>
      </div>
      <div class="modal-body">${bodyHtml}</div>
      ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}
    </div>`;
  document.body.appendChild(overlay);
}

function closeModal() {
  const m = document.getElementById('active-modal');
  if (m) m.remove();
}
