/**
 * NeighborHealth Profile Component
 * Manages user profile viewing, editing, and logout.
 */

const profileComponent = {
    modal: null,
    form: null,
    btn: null,
    closeBtn: null,
    logoutBtn: null,

    init() {
        this.modal = document.getElementById('profile-modal');
        this.form = document.getElementById('profile-form');
        this.btn = document.getElementById('profile-btn');
        this.closeBtn = document.getElementById('profile-close');
        this.logoutBtn = document.getElementById('prof-logout');

        if (!this.modal || !this.btn) return;

        // Toggle modal
        this.btn.addEventListener('click', () => this.open());
        this.closeBtn.addEventListener('click', () => this.close());
        this.logoutBtn.addEventListener('click', () => this.handleLogout());

        this.form.addEventListener('submit', (e) => this.handleSave(e));

        // Click outside to close
        window.addEventListener('click', (e) => {
            if (e.target === this.modal) this.close();
        });

        this.updateDisplayName();

        // Subscribe to user changes
        store.on('currentUser', () => this.updateDisplayName());
    },

    open() {
        const user = store.get('currentUser');
        if (!user) {
            window.location.href = 'login.html';
            return;
        }

        // Fill form
        const nameField = document.getElementById('prof-name');
        const emailField = document.getElementById('prof-email');
        const wardField = document.getElementById('prof-ward');
        const condField = document.getElementById('prof-conditions');

        if (nameField) nameField.value = user.name || '';
        if (emailField) emailField.value = user.email || '';
        if (wardField) wardField.value = user.home_ward_id ? `Ward ${user.home_ward_id}` : 'Not detected';
        if (condField) condField.value = (user.health_conditions || []).join(', ');

        // Add history button handler
        const historyBtn = document.getElementById('prof-history-btn');
        if (historyBtn && !historyBtn.dataset.wired) {
            historyBtn.dataset.wired = "true";
            historyBtn.addEventListener('click', async () => {
                const u = store.get('currentUser');
                if (!u?.id) return;
                try {
                    const data = await api.getUserHistory(u.id);
                    this._renderHistory(data.history || []);
                } catch(e) {
                    toast.show('Could not load history', 'error');
                }
            });
        }

        this.modal.classList.remove('hidden');
    },

    close() {
        this.modal.classList.add('hidden');
        // Clear history on close to prevent stale data flicker next time
        const historyList = document.getElementById('prof-history-list');
        if (historyList) historyList.innerHTML = '';
    },

    updateDisplayName() {
        const user = store.get('currentUser');
        const display = document.getElementById('user-display-name');
        if (display && user) {
            display.textContent = user.name || (user.email ? user.email.split('@')[0] : 'User');
        } else if (display) {
            display.textContent = 'Guest';
        }
    },

    async handleSave(e) {
        e.preventDefault();
        const user = store.get('currentUser');
        if (!user?.id) return;

        const name = document.getElementById('prof-name').value;
        const conditionsText = document.getElementById('prof-conditions').value;
        const conditions = conditionsText
            .split(',')
            .map(c => c.trim())
            .filter(c => c);

        toast.show("Saving profile...", "info");

        try {
            const updatedUser = await api.updateUser(user.id, {
                name,
                health_conditions: conditions
            });

            store.set('currentUser', updatedUser);
            localStorage.setItem('neighborhealth_user', JSON.stringify(updatedUser));
            this.updateDisplayName();
            // this.close(); // Keep open to show success or let them view history
            toast.show("Profile updated successfully!", "success");
        } catch (err) {
            window.NH_LOG.error("Profile update failed", err);
            toast.show("Failed to update profile", "error");
        }
    },

    handleLogout() {
        localStorage.removeItem('neighborhealth_user');
        store.set('currentUser', null);
        window.location.href = 'login.html';
    },

    _renderHistory(items) {
        const container = document.getElementById('prof-history-list');
        if (!container) return;
        
        container.innerHTML = items.length === 0
            ? '<p style="color:var(--text-muted);font-size:13px;text-align:center;padding:20px;">No AI suggestions found yet.</p>'
            : items.map(item => `
                <div style="padding:12px;border:1px solid var(--border);border-radius:8px;margin-bottom:12px;background:rgba(255,255,255,0.02);">
                  <div style="font-size:10px;color:var(--text-muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.05em;">
                    ${new Date(item.created_at).toLocaleString('en-IN')} · Ward ${item.ward_id} · ${item.disease_id}
                  </div>
                  <div style="font-size:12px;color:var(--text-secondary);margin-bottom:8px;font-weight:500;border-left:2px solid var(--teal);padding-left:8px;">
                    "${item.message}"
                  </div>
                  <div style="font-size:13px;color:var(--text-primary);line-height:1.6;background:rgba(0,0,0,0.2);padding:10px;border-radius:6px;">
                    ${item.response}
                  </div>
                </div>`).join('');
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => profileComponent.init());
