/**
 * All backend API calls — one function per endpoint.
 * Import apiClient; add loading/error handling at call site.
 */
window.api = {

  /** GET /api/v1/risk/all?disease=... */
  async getAllRiskScores(diseaseId = 'dengue') {
    return apiClient.get(`/api/v1/risk/all?disease=${diseaseId}`);
  },

  /** GET /api/v1/risk/{ward_id}?disease=... */
  async getWardRisk(wardId, diseaseId = 'dengue') {
    return apiClient.get(`/api/v1/risk/${wardId}?disease=${diseaseId}`);
  },

  /** GET /api/v1/risk/{ward_id}/history?disease=... */
  async getWardHistory(wardId, days = 30, diseaseId = 'dengue') {
    return apiClient.get(`/api/v1/risk/${wardId}/history?days=${days}&disease=${diseaseId}`);
  },

  /** GET /api/v1/wards */
  async getWards() {
    return apiClient.get('/api/v1/wards');
  },

  /** GET /api/v1/reports/ward/{ward_id} */
  async getWardReports(wardId) {
    return apiClient.get(`/api/v1/reports/ward/${wardId}`);
  },

  /** POST /api/v1/reports */
  async submitReport(payload) {
    // payload: { ward_id, lat, lng, description?, photo_url? }
    return apiClient.post('/api/v1/reports', payload);
  },

  /** POST /api/v1/subscriptions */
  async createSubscription(payload) {
    // payload: { ward_id, contact, contact_type, threshold?, user_id?, name?, email?, notify_diseases? }
    return apiClient.post('/api/v1/subscriptions', payload);
  },

  /** POST /api/v1/users */
  async upsertUser(payload) {
    /** payload: { name, email, phone, address, health_conditions, lat, lng, ward_id } */
    return apiClient.post('/api/v1/users', payload);
  },

  /** POST /api/v1/chat */
  async sendChat(wardId, message, language = 'en', simulationMode = null) {
    const user = store.get('currentUser');
    return apiClient.post('/api/v1/chat', {
      ward_id: wardId,
      message,
      language,
      simulation_mode: simulationMode,
      user_health_conditions: user?.health_conditions || [],
      user_id: user?.id || null,
    });
  },

  /** GET /api/v1/users/{user_id}/history */
  async getUserHistory(userId) {
    return apiClient.get(`/api/v1/users/${userId}/history`);
  },

  /** PUT /api/v1/users/{user_id} */
  async updateUser(userId, payload) {
    // payload: { name, health_conditions, ... }
    return apiClient.put(`/api/v1/users/${userId}`, payload);
  },

  /** POST /api/v1/risk/travel */
  async getTravelRisk(fromWardId, toWardId, disease = 'dengue') {
    const user = store.get('currentUser');
    return apiClient.post('/api/v1/risk/travel', {
      from_ward_id: fromWardId,
      to_ward_id: toWardId,
      disease,
      user_health_conditions: user?.health_conditions || [],
      language: 'en',
    });
  },

  /** GET /api/v1/alerts/today */
  async getTodayAlerts() {
    return apiClient.get('/api/v1/alerts/today');
  },
};
