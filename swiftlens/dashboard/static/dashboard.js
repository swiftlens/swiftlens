/**
 * Swift Context MCP Dashboard JavaScript
 * Provides real-time monitoring and interaction functionality
 */

class DashboardApp {
    constructor() {
        this.websocket = null;
        this.logs = [];
        this.sessions = [];
        this.statistics = {};
        this.filters = {
            tool: '',
            session: '',
            status: ''
        };
        this.autoScroll = true;
        this.currentTab = 'logs';
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupWebSocket();
        this.setupTheme();
        this.loadInitialData();
        
        // Start periodic updates
        setInterval(() => this.updateStatistics(), 30000); // Every 30 seconds
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tab = e.currentTarget.dataset.tab;
                this.switchTab(tab);
            });
        });

        // Theme toggle
        document.getElementById('themeToggle').addEventListener('click', () => {
            this.toggleTheme();
        });

        // Shutdown button
        document.getElementById('shutdownBtn').addEventListener('click', () => {
            this.shutdownServer();
        });

        // Filters
        document.getElementById('toolFilter').addEventListener('change', (e) => {
            this.filters.tool = e.target.value;
            this.applyFilters();
        });

        document.getElementById('sessionFilter').addEventListener('change', (e) => {
            this.filters.session = e.target.value;
            this.applyFilters();
        });

        document.getElementById('statusFilter').addEventListener('change', (e) => {
            this.filters.status = e.target.value;
            this.applyFilters();
        });

        // Auto-scroll toggle
        document.getElementById('autoScroll').addEventListener('change', (e) => {
            this.autoScroll = e.target.checked;
        });

        // Action buttons
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.refreshData();
        });

        document.getElementById('exportBtn').addEventListener('click', () => {
            this.exportLogs();
        });

        document.getElementById('clearBtn').addEventListener('click', () => {
            this.clearLogs();
        });

        // Modal handling
        document.querySelector('.modal-close').addEventListener('click', () => {
            this.closeModal();
        });

        document.getElementById('logDetailModal').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) {
                this.closeModal();
            }
        });
    }

    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus('connected');
        };

        this.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus('disconnected');
            
            // Attempt to reconnect after 5 seconds
            setTimeout(() => this.setupWebSocket(), 5000);
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('disconnected');
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'connected':
                console.log('Dashboard connected:', data.message);
                break;
            
            case 'log_entry':
                this.addLogEntry(data.data);
                break;
            
            case 'pong':
                // Handle ping-pong for keep-alive
                break;
            
            case 'error':
                console.error('WebSocket error:', data.message);
                break;
            
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connectionStatus');
        const icon = statusElement.querySelector('i');
        const text = statusElement.querySelector('span');

        statusElement.className = `status-indicator ${status}`;
        
        switch (status) {
            case 'connected':
                icon.className = 'fas fa-circle';
                text.textContent = 'Connected';
                break;
            case 'disconnected':
                icon.className = 'fas fa-circle';
                text.textContent = 'Disconnected';
                break;
            case 'connecting':
                icon.className = 'fas fa-circle';
                text.textContent = 'Connecting...';
                break;
        }
    }

    setupTheme() {
        const savedTheme = localStorage.getItem('dashboard-theme') || 'light';
        this.setTheme(savedTheme);
    }

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('dashboard-theme', theme);
        
        const themeIcon = document.querySelector('#themeToggle i');
        themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    }

    async loadInitialData() {
        await Promise.all([
            this.loadLogs(),
            this.loadSessions(),
            this.updateStatistics()
        ]);
        this.populateFilters();
    }

    async loadLogs() {
        try {
            const response = await fetch('/api/logs?limit=100');
            const data = await response.json();
            this.logs = data.logs || [];
            this.renderLogs();
        } catch (error) {
            console.error('Error loading logs:', error);
        }
    }

    async loadSessions() {
        try {
            const response = await fetch('/api/sessions');
            const data = await response.json();
            this.sessions = data.sessions || [];
            this.renderSessions();
        } catch (error) {
            console.error('Error loading sessions:', error);
        }
    }

    async updateStatistics() {
        try {
            const response = await fetch('/api/statistics');
            this.statistics = await response.json();
            this.renderStatistics();
            this.renderCharts();
        } catch (error) {
            console.error('Error loading statistics:', error);
        }
    }

    addLogEntry(logEntry) {
        this.logs.unshift(logEntry);
        
        // Keep only the latest 1000 logs in memory
        if (this.logs.length > 1000) {
            this.logs = this.logs.slice(0, 1000);
        }
        
        this.renderLogs();
        this.updateLogCount();
        
        if (this.autoScroll) {
            this.scrollToLatestLog();
        }
    }

    renderLogs() {
        const logsList = document.getElementById('logsList');
        const filteredLogs = this.getFilteredLogs();
        
        if (filteredLogs.length === 0) {
            logsList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-stream"></i>
                    <p>No logs match the current filters</p>
                </div>
            `;
            return;
        }

        const logsHtml = filteredLogs.map(log => this.createLogEntryHtml(log)).join('');
        logsList.innerHTML = logsHtml;
        
        // Add click listeners to log entries
        logsList.querySelectorAll('.log-entry').forEach(entry => {
            entry.addEventListener('click', () => {
                const logId = entry.dataset.logId;
                const log = this.logs.find(l => l.id === logId);
                if (log) {
                    this.showLogDetails(log);
                }
            });
        });
    }

    createLogEntryHtml(log) {
        const timestamp = new Date(log.timestamp).toLocaleString();
        const executionTime = log.execution_time_ms ? `${log.execution_time_ms.toFixed(2)}ms` : '-';
        
        return `
            <div class="log-entry" data-log-id="${log.id}">
                <div class="log-header">
                    <div class="log-tool">${log.tool_name}</div>
                    <div class="log-timestamp">${timestamp}</div>
                    <div class="log-status ${log.status}">${log.status}</div>
                </div>
                <div class="log-details">
                    Session: ${log.session_id} | Client: ${log.client_id}
                </div>
                <div class="log-execution-time">
                    Execution time: ${executionTime}
                </div>
            </div>
        `;
    }

    renderSessions() {
        const sessionsList = document.getElementById('sessionsList');
        
        if (this.sessions.length === 0) {
            sessionsList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-users"></i>
                    <p>No sessions found</p>
                </div>
            `;
            return;
        }

        const sessionsHtml = this.sessions.map(session => {
            const startTime = new Date(session.start_time).toLocaleString();
            const endTime = session.end_time ? new Date(session.end_time).toLocaleString() : '-';
            const status = session.end_time ? 'ended' : 'active';
            
            return `
                <div class="session-item">
                    <div class="session-header">
                        <div class="session-id">${session.session_id}</div>
                        <div class="session-status ${status}">${status}</div>
                    </div>
                    <div class="session-details">
                        Started: ${startTime}<br>
                        Ended: ${endTime}<br>
                        Tool calls: ${session.tool_count || 0}
                    </div>
                </div>
            `;
        }).join('');
        
        sessionsList.innerHTML = sessionsHtml;
    }

    renderStatistics() {
        document.getElementById('totalCalls').textContent = this.statistics.total_tool_calls || '0';
        document.getElementById('activeSessions').textContent = this.statistics.active_sessions || '0';
        document.getElementById('connectedClients').textContent = this.statistics.connected_websockets || '0';
        
        // Calculate success rate
        const statusCounts = this.statistics.status_counts || {};
        const total = Object.values(statusCounts).reduce((sum, count) => sum + count, 0);
        const successCount = statusCounts.success || 0;
        const successRate = total > 0 ? Math.round((successCount / total) * 100) : 0;
        document.getElementById('successRate').textContent = `${successRate}%`;
    }

    renderCharts() {
        this.renderToolUsageChart();
        this.renderStatusChart();
    }

    renderToolUsageChart() {
        const chartElement = document.getElementById('toolUsageChart');
        const toolUsage = this.statistics.tool_usage || {};
        
        if (Object.keys(toolUsage).length === 0) {
            chartElement.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-chart-pie"></i>
                    <p>No tool usage data</p>
                </div>
            `;
            return;
        }

        // Create a simple bar chart representation
        const maxCount = Math.max(...Object.values(toolUsage));
        const chartHtml = Object.entries(toolUsage)
            .sort(([,a], [,b]) => b - a)
            .slice(0, 10) // Top 10 tools
            .map(([tool, count]) => {
                const percentage = (count / maxCount) * 100;
                return `
                    <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                        <div style="width: 120px; font-size: 0.75rem; color: var(--text-secondary);">${tool}</div>
                        <div style="flex: 1; background: var(--bg-tertiary); border-radius: 4px; margin: 0 0.5rem; height: 20px; position: relative;">
                            <div style="background: var(--accent-primary); height: 100%; width: ${percentage}%; border-radius: 4px;"></div>
                        </div>
                        <div style="width: 40px; font-size: 0.75rem; text-align: right;">${count}</div>
                    </div>
                `;
            }).join('');
        
        chartElement.innerHTML = chartHtml;
    }

    renderStatusChart() {
        const chartElement = document.getElementById('statusChart');
        const statusCounts = this.statistics.status_counts || {};
        
        if (Object.keys(statusCounts).length === 0) {
            chartElement.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-chart-line"></i>
                    <p>No status data</p>
                </div>
            `;
            return;
        }

        const total = Object.values(statusCounts).reduce((sum, count) => sum + count, 0);
        const statusColors = {
            success: 'var(--success-color)',
            error: 'var(--error-color)',
            in_progress: 'var(--warning-color)'
        };

        const chartHtml = Object.entries(statusCounts).map(([status, count]) => {
            const percentage = (count / total) * 100;
            const color = statusColors[status] || 'var(--text-muted)';
            
            return `
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <div style="width: 100px; font-size: 0.875rem; color: var(--text-secondary); text-transform: capitalize;">${status}</div>
                    <div style="flex: 1; background: var(--bg-tertiary); border-radius: 4px; margin: 0 1rem; height: 24px; position: relative;">
                        <div style="background: ${color}; height: 100%; width: ${percentage}%; border-radius: 4px;"></div>
                    </div>
                    <div style="width: 60px; font-size: 0.875rem; text-align: right;">${count} (${percentage.toFixed(1)}%)</div>
                </div>
            `;
        }).join('');
        
        chartElement.innerHTML = chartHtml;
    }

    populateFilters() {
        // Populate tool filter
        const toolFilter = document.getElementById('toolFilter');
        const tools = [...new Set(this.logs.map(log => log.tool_name))].sort();
        
        toolFilter.innerHTML = '<option value="">All Tools</option>' +
            tools.map(tool => `<option value="${tool}">${tool}</option>`).join('');

        // Populate session filter
        const sessionFilter = document.getElementById('sessionFilter');
        const sessions = [...new Set(this.logs.map(log => log.session_id))].sort();
        
        sessionFilter.innerHTML = '<option value="">All Sessions</option>' +
            sessions.map(session => `<option value="${session}">${session}</option>`).join('');
    }

    getFilteredLogs() {
        return this.logs.filter(log => {
            if (this.filters.tool && log.tool_name !== this.filters.tool) return false;
            if (this.filters.session && log.session_id !== this.filters.session) return false;
            if (this.filters.status && log.status !== this.filters.status) return false;
            return true;
        });
    }

    applyFilters() {
        this.renderLogs();
        this.updateLogCount();
    }

    updateLogCount() {
        const count = this.getFilteredLogs().length;
        document.getElementById('logCount').textContent = count;
    }

    scrollToLatestLog() {
        const logsList = document.getElementById('logsList');
        logsList.scrollTop = 0; // Scroll to top since newest logs are at the top
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}Tab`).classList.add('active');

        this.currentTab = tabName;

        // Load data for the active tab if needed
        if (tabName === 'sessions') {
            this.loadSessions();
        } else if (tabName === 'statistics') {
            this.updateStatistics();
        }
    }

    showLogDetails(log) {
        const modal = document.getElementById('logDetailModal');
        const content = document.getElementById('logDetailContent');
        
        const timestamp = new Date(log.timestamp).toLocaleString();
        const executionTime = log.execution_time_ms ? `${log.execution_time_ms.toFixed(2)}ms` : 'N/A';
        
        content.innerHTML = `
            <div style="margin-bottom: 1rem;">
                <h4>Tool: ${log.tool_name}</h4>
                <p><strong>Status:</strong> <span class="log-status ${log.status}">${log.status}</span></p>
                <p><strong>Timestamp:</strong> ${timestamp}</p>
                <p><strong>Execution Time:</strong> ${executionTime}</p>
                <p><strong>Session ID:</strong> ${log.session_id}</p>
                <p><strong>Client ID:</strong> ${log.client_id}</p>
            </div>
            
            ${log.parameters ? `
                <div style="margin-bottom: 1rem;">
                    <h4>Parameters:</h4>
                    <pre style="background: var(--bg-secondary); padding: 1rem; border-radius: 4px; overflow-x: auto; font-size: 0.875rem;">${JSON.stringify(log.parameters, null, 2)}</pre>
                </div>
            ` : ''}
            
            ${log.result ? `
                <div style="margin-bottom: 1rem;">
                    <h4>Result:</h4>
                    <pre style="background: var(--bg-secondary); padding: 1rem; border-radius: 4px; overflow-x: auto; font-size: 0.875rem;">${JSON.stringify(log.result, null, 2)}</pre>
                </div>
            ` : ''}
            
            ${log.error_message ? `
                <div style="margin-bottom: 1rem;">
                    <h4>Error Message:</h4>
                    <div style="background: var(--error-color); color: white; padding: 1rem; border-radius: 4px; font-size: 0.875rem;">${log.error_message}</div>
                </div>
            ` : ''}
        `;
        
        modal.classList.add('active');
    }

    closeModal() {
        document.getElementById('logDetailModal').classList.remove('active');
    }

    async refreshData() {
        await this.loadInitialData();
        this.populateFilters();
    }

    exportLogs() {
        const filteredLogs = this.getFilteredLogs();
        const dataStr = JSON.stringify(filteredLogs, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = `mcp-dashboard-logs-${new Date().toISOString().split('T')[0]}.json`;
        link.click();
    }

    clearLogs() {
        if (confirm('Are you sure you want to clear all displayed logs? This will only clear the display, not the database.')) {
            this.logs = [];
            this.renderLogs();
            this.updateLogCount();
        }
    }

    async shutdownServer() {
        if (!confirm('Are you sure you want to shutdown the MCP server? This will close all connections.')) {
            return;
        }

        try {
            const response = await fetch('/api/shutdown', { method: 'POST' });
            const data = await response.json();
            
            alert(data.message || 'Server shutdown initiated');
            
            // Close WebSocket connection
            if (this.websocket) {
                this.websocket.close();
            }
            
        } catch (error) {
            console.error('Error shutting down server:', error);
            alert('Error shutting down server');
        }
    }

    // Send periodic ping to keep WebSocket alive
    startKeepAlive() {
        setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // Every 30 seconds
    }
}

// Initialize the dashboard when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new DashboardApp();
    window.dashboard.startKeepAlive();
});