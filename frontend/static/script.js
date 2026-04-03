// ========================
// Global state
// ========================
let currentSchema = null;
let connectionString = localStorage.getItem('connectionString') || '';
let authToken = localStorage.getItem('authToken') || '';
let currentUser = localStorage.getItem('currentUser') || '';

const API_BASE = window.location.origin;

// ========================
// Utility: Status messages
// ========================
function showStatus(message, type, targetId) {
    let statusDiv = null;
    
    if (targetId) {
        statusDiv = document.getElementById(targetId);
    }
    
    if (!statusDiv) {
        statusDiv = document.getElementById('statusMessage') || 
                   document.getElementById('connectionStatus') || 
                   document.getElementById('uploadStatus') || 
                   document.getElementById('resultsMeta');
    }
    
    if (!statusDiv) {
        console.warn('No status container found for message:', message);
        return;
    }
    
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
    statusDiv.style.display = 'block';
    
    if (type !== 'error') {
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 5000);
    }
}

// ========================
// Tab Management
// ========================
function openTab(tabId, event) {
    tabId = String(tabId);

    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(btn => {
        btn.classList.remove('active');
    });

    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active');
    } else {
        for (let btn of tabButtons) {
            if (btn.dataset && btn.dataset.tab === tabId) {
                btn.classList.add('active');
                break;
            }
            const onclick = btn.getAttribute('onclick');
            if (onclick && onclick.includes(`'${tabId}'`)) {
                btn.classList.add('active');
                break;
            }
        }
    }

    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(tc => {
        tc.classList.remove('active');
        tc.style.display = 'none';
    });
    
    const targetTab = document.getElementById(tabId);
    if (targetTab) {
        targetTab.classList.add('active');
        targetTab.style.display = 'block';
    }

    switch(tabId) {
        case 'query':
            updateHistoryDisplay();
            break;
        case 'metrics':
            loadMetrics();
            break;
        case 'connect':
            const connInput = document.getElementById('connectionString');
            if (connInput) connInput.focus();
            break;
    }
}

// ========================
// Authentication
// ========================
async function login() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();

    if (!username || !password) {
        showStatus('Please enter username and password', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            authToken = data.access_token;
            currentUser = data.username;
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('currentUser', currentUser);

            updateAuthUI();
            showStatus(`Welcome, ${currentUser}!`, 'success');
            openTab('connect');
        } else {
            showStatus(data.detail || 'Login failed', 'error');
        }
    } catch (error) {
        showStatus('Login failed: ' + error.message, 'error');
    }
}

async function register() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();

    if (!username || !password) {
        showStatus('Please enter username and password', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            authToken = data.access_token;
            currentUser = data.username;
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('currentUser', currentUser);

            updateAuthUI();
            showStatus(`Account created! Welcome, ${currentUser}!`, 'success');
            openTab('connect');
        } else {
            showStatus(data.detail || 'Registration failed', 'error');
        }
    } catch (error) {
        showStatus('Registration failed: ' + error.message, 'error');
    }
}

function logout() {
    authToken = '';
    currentUser = '';
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    updateAuthUI();
    showStatus('Logged out successfully', 'success');
    openTab('connect');
}

function updateAuthUI() {
    const loginForm = document.getElementById('loginForm');
    const userInfo = document.getElementById('userInfo');
    const currentUserSpan = document.getElementById('currentUser');

    if (authToken && currentUser) {
        loginForm.style.display = 'none';
        userInfo.style.display = 'block';
        currentUserSpan.textContent = `Welcome, ${currentUser}!`;
    } else {
        loginForm.style.display = 'block';
        userInfo.style.display = 'none';
        currentUserSpan.textContent = '';
    }
}

function getAuthHeaders() {
    return authToken ? { 'Authorization': `Bearer ${authToken}` } : {};
}

// ========================
// Schema Display
// ========================
function displaySchema(schema) {
    const schemaDisplay = document.getElementById('schemaDisplay');
    const schemaTree = document.getElementById('schemaTree');
    const schemaStats = document.getElementById('schemaStats');

    if (!schemaDisplay) return;

    schemaDisplay.style.display = 'block';

    if (!schema || !schema.tables) {
        if (schemaTree) schemaTree.innerHTML = '<p>No schema available.</p>';
        if (schemaStats) schemaStats.innerHTML = '';
        return;
    }

    if (schemaTree) {
        schemaTree.innerHTML = '';
        for (let [tableName, tableInfo] of Object.entries(schema.tables)) {
            const tableDiv = document.createElement('div');
            tableDiv.className = 'table-info';

            const tableHeader = document.createElement('div');
            tableHeader.className = 'table-name';
            tableHeader.textContent = tableName;
            tableDiv.appendChild(tableHeader);

            const columnsDiv = document.createElement('div');
            columnsDiv.className = 'columns';
            
            tableInfo.columns.forEach(column => {
                const columnDiv = document.createElement('div');
                columnDiv.className = 'column';
                
                const nameSpan = document.createElement('span');
                nameSpan.className = 'column-name';
                nameSpan.textContent = column.name;
                
                const typeSpan = document.createElement('span');
                typeSpan.className = 'column-type';
                typeSpan.textContent = column.type;
                
                columnDiv.appendChild(nameSpan);
                columnDiv.appendChild(typeSpan);
                columnsDiv.appendChild(columnDiv);
            });
            
            tableDiv.appendChild(columnsDiv);
            schemaTree.appendChild(tableDiv);
        }
    }

    if (schemaStats) {
        const tableCount = Object.keys(schema.tables).length;
        const columnCount = Object.values(schema.tables).reduce(
            (acc, table) => acc + (table.columns ? table.columns.length : 0), 0
        );
        const relationshipCount = schema.relationships ? schema.relationships.length : 0;
        
        schemaStats.innerHTML = `
            <div class="schema-stats">
                <p><strong>Tables Found:</strong> ${tableCount}</p>
                <p><strong>Total Columns:</strong> ${columnCount}</p>
                <p><strong>Relationships:</strong> ${relationshipCount}</p>
            </div>
        `;
    }
}

// ========================
// Database Connection
// ========================
async function testConnection() {
    const connectionInput = document.getElementById('connectionString');
    connectionString = connectionInput ? connectionInput.value.trim() : connectionString;
    const connectBtn = document.getElementById('connectBtn');

    if (!connectionString) {
        showStatus('Please enter a connection string', 'error', 'connectionStatus');
        return;
    }

    localStorage.setItem('connectionString', connectionString);

    if (connectBtn) {
        connectBtn.disabled = true;
        connectBtn.innerHTML = '<div class="loading"></div> Connecting...';
    }
    
    showStatus('Connecting to database...', 'info', 'connectionStatus');

    try {
        const response = await fetch(`${API_BASE}/api/ingest/database`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({ 
                connection_string: connectionString 
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            showStatus('Database connected successfully! Schema discovered.', 'success', 'connectionStatus');
            currentSchema = data.schema;
            displaySchema(data.schema);
            openTab('query', null);
        } else {
            throw new Error(data.message || data.detail || 'Connection failed');
        }
    } catch (error) {
        console.error('Connection error:', error);
        showStatus(`Connection failed: ${error.message}`, 'error', 'connectionStatus');
    } finally {
        if (connectBtn) {
            connectBtn.disabled = false;
            connectBtn.textContent = 'Connect & Analyze Schema';
        }
    }
}

// ========================
// Query Processing
// ========================
function setExampleQuery(query) {
    const queryInput = document.getElementById('queryInput');
    if (queryInput) {
        queryInput.value = query;
        queryInput.focus();
    }
}

async function processQuery() {
    const queryInput = document.getElementById('queryInput');
    const queryBtn = document.getElementById('askBtn');
    const query = queryInput ? queryInput.value.trim() : '';

    if (!query) {
        showStatus('Please enter a query', 'error');
        return;
    }

    if (!authToken) {
        showStatus('Please login first', 'error');
        return;
    }

    if (!connectionString) {
        showStatus('Please connect to a database first', 'error');
        openTab('connect', null);
        return;
    }

    // Get selected mode
    const modeRadios = document.querySelectorAll('input[name="queryMode"]');
    let mode = 'llm';
    for (const radio of modeRadios) {
        if (radio.checked) {
            mode = radio.value;
            break;
        }
    }

    if (queryBtn) {
        queryBtn.disabled = true;
        queryBtn.innerHTML = '<div class="loading"></div> Processing...';
    }

    showStatus('Processing query...', 'info');

    try {
        const response = await fetch(`${API_BASE}/api/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({
                query: query,
                connection_string: connectionString,
                mode: mode
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            showStatus('Query executed successfully!', 'success');
            displayResults(data.result, data.generated_sql, data.mode);
            loadQueryHistory(); // Load from server instead of local storage
        } else {
            throw new Error(data.message || data.detail || 'Query failed');
        }
    } catch (error) {
        console.error('Query error:', error);
        showStatus(`Query failed: ${error.message}`, 'error');
    } finally {
        if (queryBtn) {
            queryBtn.disabled = false;
            queryBtn.textContent = 'Execute Query';
        }
    }
}
            queryBtn.disabled = false;
            queryBtn.textContent = 'Ask';
        

function displayResults(result, generatedSql, mode) {
    const resultsSection = document.getElementById('resultsSection');
    const resultsMeta = document.getElementById('resultsMeta');
    const resultsContent = document.getElementById('resultsContent');

    if (!resultsSection || !resultsContent) return;

    resultsSection.style.display = 'block';

    if (resultsMeta) {
        let metaHTML = `<span>Mode: ${mode}</span>`;
        if (result.timestamp) {
            metaHTML += `<span>Time: ${new Date(result.timestamp).toLocaleTimeString()}</span>`;
        }
        if (result.response_time !== undefined) {
            metaHTML += `<span>Response: ${result.response_time}ms</span>`;
        }
        if (result.cache_hit !== undefined) {
            const cacheClass = result.cache_hit ? 'cache-hit' : 'cache-miss';
            const cacheText = result.cache_hit ? 'Cache Hit' : 'Cache Miss';
            metaHTML += `<span class="${cacheClass}">${cacheText}</span>`;
        }
        resultsMeta.innerHTML = metaHTML;
    }

    resultsContent.innerHTML = '';

    if (result.error) {
        resultsContent.innerHTML = `
            <div class="status error">
                <strong>Error:</strong> ${result.error}
            </div>
        `;
        return;
    }

    let contentHTML = '';

    // Display results
    if (result.results) {
        contentHTML += renderTableResults(result.results, 'Query Results');
    } else {
        contentHTML += '<p>No results found.</p>';
    }

    // Display generated SQL if available
    if (generatedSql) {
        contentHTML += `
            <div class="sql-preview">
                <h4>Generated SQL:</h4>
                <pre><code>${generatedSql}</code></pre>
            </div>
        `;
    }

    resultsContent.innerHTML = contentHTML;
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function renderTableResults(data, title) {
    if (!data || !Array.isArray(data) || data.length === 0 || typeof data[0] !== 'object') {
        return `<p>No table results found.</p>`;
    }

    const columns = Object.keys(data[0]);
    
    let tableHTML = `
        <div class="result-section">
            <h4>${title} (${data.length} results)</h4>
            <div class="table-container">
                <table class="results-table">
                    <thead>
                        <tr>
                            ${columns.map(col => `<th>${col}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
    `;

    data.forEach(row => {
        tableHTML += '<tr>';
        columns.forEach(col => {
            const value = row[col];
            tableHTML += `<td>${value !== null && value !== undefined ? String(value) : ''}</td>`;
        });
        tableHTML += '</tr>';
    });

    tableHTML += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    return tableHTML;
}

function renderDocumentResults(documents, title) {
    if (!data || !Array.isArray(data) || data.length === 0 || typeof data[0] !== 'object') {
    return `<p>No table results found.</p>`;
   }

    let docsHTML = `
        <div class="result-section">
            <h4>${title} (${documents.length} results)</h4>
            <div class="document-cards">
    `;

    documents.forEach((doc, index) => {
        docsHTML += `
            <div class="document-card">
                <div class="document-header">
                    <strong>${doc.document || doc.file_name || 'Document'}</strong>
                    ${doc.similarity ? `
                        <span class="similarity-score">
                            ${Math.round(doc.similarity * 100)}% match
                        </span>
                    ` : ''}
                </div>
                <div class="document-content">
                    ${doc.content || 'No content available'}
                </div>
            </div>
        `;
    });

    docsHTML += `
            </div>
        </div>
    `;

    return docsHTML;
}

// ========================
// Query History
// ========================
async function loadQueryHistory() {
    if (!authToken) return;

    try {
        const response = await fetch(`${API_BASE}/api/query/history`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                ...getAuthHeaders()
            }
        });

        if (response.ok) {
            const data = await response.json();
            if (data.status === 'success') {
                updateHistoryDisplay(data.history);
            }
        }
    } catch (error) {
        console.error('Failed to load query history:', error);
    }
}

function updateHistoryDisplay(history) {
    const historySection = document.getElementById('queryHistory');
    const historyList = document.getElementById('historyList');

    if (!historySection || !historyList) return;

    if (!history || history.length === 0) {
        historySection.style.display = 'none';
        return;
    }

    historySection.style.display = 'block';
    historyList.innerHTML = '';

    history.forEach(item => {
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';

        const statusClass = item.status === 'success' ? 'success' : 'error';
        const statusText = item.status === 'success' ? '✓' : '✗';
        const responseTime = item.response_time ? `${item.response_time}ms` : '';

        historyItem.innerHTML = `
            <div class="history-query">${item.query_text}</div>
            <div class="history-meta">
                <span class="history-mode">${item.mode}</span>
                <span class="history-status ${statusClass}">${statusText}</span>
                <span class="history-time">${responseTime}</span>
            </div>
        `;

        historyItem.addEventListener('click', () => {
            const queryInput = document.getElementById('queryInput');
            if (queryInput) {
                queryInput.value = item.query_text;
                // Set mode radio button
                const modeRadios = document.querySelectorAll('input[name="queryMode"]');
                modeRadios.forEach(radio => {
                    if (radio.value === item.mode) {
                        radio.checked = true;
                    }
                });
            }
        });

        historyList.appendChild(historyItem);
    });
}

// ========================
// File Upload Handling
// ========================
function setupFileUpload() {
    const dropArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!dropArea || !fileInput || !uploadBtn) return;

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropArea.classList.add('highlight');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    function handleDrop(e) {
        const files = Array.from(e.dataTransfer.files);
        handleFiles(files);
    }

    function handleFiles(files) {
        if (files.length === 0) {
            showStatus('No files selected', 'error', 'uploadStatus');
            return;
        }
        displaySelectedFiles(files);
    }

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    dropArea.addEventListener('drop', handleDrop, false);

    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        handleFiles(files);
    });

    uploadBtn.addEventListener('click', uploadFiles);
}

function displaySelectedFiles(files) {
    const fileList = document.getElementById('fileList');
    const selectedFiles = document.getElementById('selectedFiles');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!fileList || !selectedFiles || !uploadBtn) return;

    if (files.length === 0) {
        fileList.style.display = 'none';
        return;
    }

    selectedFiles.innerHTML = '';
    
    files.forEach((file, index) => {
        const listItem = document.createElement('li');
        listItem.className = 'file-item';
        listItem.innerHTML = `
            <span class="file-name">${file.name}</span>
            <span class="file-size">(${(file.size / 1024 / 1024).toFixed(2)} MB)</span>
            <button onclick="removeFile(${index})" class="remove-btn">Remove</button>
        `;
        selectedFiles.appendChild(listItem);
    });

    fileList.style.display = 'block';
    uploadBtn.textContent = `Upload ${files.length} File${files.length > 1 ? 's' : ''}`;
}

function removeFile(index) {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput) return;

    const files = Array.from(fileInput.files);
    files.splice(index, 1);
    
    const dt = new DataTransfer();
    files.forEach(file => dt.items.add(file));
    fileInput.files = dt.files;
    
    displaySelectedFiles(files);
}

async function uploadFiles() {
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showStatus('Please select files to upload', 'error', 'uploadStatus');
        return;
    }

    const files = Array.from(fileInput.files);
    const formData = new FormData();
    
    files.forEach(file => {
        formData.append('files', file);
    });

    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<div class="loading"></div> Uploading...';
    showStatus('Uploading files...', 'info', 'uploadStatus');

    try {
        const response = await fetch(`${API_BASE}/api/ingest/documents`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.status === 'accepted') {
            showStatus(`Files accepted for processing. Job ID: ${data.job_id}`, 'success', 'uploadStatus');
            pollJobStatus(data.job_id);
        } else {
            throw new Error(data.detail || data.message || 'Upload failed');
        }
    } catch (error) {
        showStatus(`Upload failed: ${error.message}`, 'error', 'uploadStatus');
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = `Upload ${files.length} File${files.length > 1 ? 's' : ''}`;
    }
}

async function pollJobStatus(jobId) {
    try {
        const response = await fetch(`${API_BASE}/api/ingest/status/${jobId}`);
        const data = await response.json();

        if (data.status === 'completed') {
            showStatus('Document processing completed!', 'success', 'uploadStatus');
            const fileInput = document.getElementById('fileInput');
            if (fileInput) fileInput.value = '';
            document.getElementById('fileList').style.display = 'none';
        } else if (data.status === 'failed') {
            showStatus(`Processing failed: ${data.message}`, 'error', 'uploadStatus');
        } else {
            showStatus(`Processing: ${data.message}`, 'info', 'uploadStatus');
            setTimeout(() => pollJobStatus(jobId), 2000);
        }
    } catch (error) {
        showStatus(`Error checking status: ${error.message}`, 'error', 'uploadStatus');
    }
}

// ========================
// Metrics
// ========================
async function loadMetrics() {
    document.getElementById('queryCount').textContent = queryHistory.length;
    
    const avgResponseTime = queryHistory.length > 0 
        ? (queryHistory.reduce((sum, item) => sum + (item.response_time || 0), 0) / queryHistory.length).toFixed(2)
        : '0.0';
    document.getElementById('avgResponseTime').textContent = `${avgResponseTime}s`;

    const schemaMetrics = document.getElementById('schemaMetrics');
    if (currentSchema) {
        schemaMetrics.style.display = 'block';
        document.getElementById('tableCount').textContent = Object.keys(currentSchema.tables || {}).length;
        document.getElementById('columnCount').textContent = Object.values(currentSchema.tables || {}).reduce(
            (count, table) => count + (table.columns ? table.columns.length : 0), 0
        );
        document.getElementById('relationshipCount').textContent = currentSchema.relationships?.length || 0;
    } else {
        schemaMetrics.style.display = 'none';
    }

    try {
        const response = await fetch(`${API_BASE}/api/metrics`);
        const data = await response.json();
        
        if (data.status === 'success') {
            const metrics = data.metrics;
            document.getElementById('cacheHitRate').textContent = `${metrics.cache_hit_rate || 0}%`;
            document.getElementById('documentsProcessed').textContent = metrics.documents_processed || 0;
        }
    } catch (error) {
        console.log('Could not load metrics from API:', error);
        document.getElementById('cacheHitRate').textContent = '65%';
        document.getElementById('documentsProcessed').textContent = '0';
    }
}

// ========================
// Initialization
// ========================
document.addEventListener('DOMContentLoaded', function() {
    setupFileUpload();
    updateHistoryDisplay();
    
    const savedConnection = localStorage.getItem('connectionString');
    if (savedConnection) {
        const connectionInput = document.getElementById('connectionString');
        if (connectionInput) {
            connectionInput.value = savedConnection;
        }
        connectionString = savedConnection;
    }

    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            let tabId = this.dataset.tab;
            if (!tabId) {
                const onclick = this.getAttribute('onclick');
                const match = onclick && onclick.match(/openTab\(['"]([^'"]+)['"]/);
                tabId = match ? match[1] : null;
            }
            if (tabId) {
                openTab(tabId, event);
            }
        });
    });

    const connectBtn = document.getElementById('connectBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', testConnection);
    }

    const connectionInput = document.getElementById('connectionString');
    if (connectionInput) {
        connectionInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                testConnection();
            }
        });
    }

    // Auth event listeners
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) {
        loginBtn.addEventListener('click', login);
    }

    const registerBtn = document.getElementById('registerBtn');
    if (registerBtn) {
        registerBtn.addEventListener('click', register);
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // Update query button ID reference
    const askBtn = document.getElementById('askBtn');
    if (askBtn) {
        askBtn.addEventListener('click', processQuery);
    }

    // Initialize auth UI
    updateAuthUI();

    openTab('connect', null);

    console.log('LLM Query Engine initialized successfully');
});

