/* Resources page JavaScript functionality */

// Global variables
let resourceNames = [];
let resources = [];
let filteredResources = [];
let currentResourceData = null;
let currentChunkSize = 1000; // lines
let currentChunkIndex = 0;
let totalChunks = 0;
let resourceType = '';

const perPage = 10;
let currentPage = 1;

// Initialize the resources functionality
function initializeResources(resourceNamesArray, resourceTypeString) {
    resourceNames = resourceNamesArray;
    resourceType = resourceTypeString;
    resources = resourceNames.map((name, index) => ({ name: name, index: index }));
    filteredResources = [...resources];
    
    // Initialize pagination
    renderPage(currentPage);
    
    // Set up event listeners
    setupEventListeners();
}

// Function to set envoy_version cookie and reload page
function setEnvoyVersion(version) {
    document.cookie = `envoy_version=${version}; path=/ui/resources/; max-age=31536000`;
    window.location.reload();
}

// Set up event listeners
function setupEventListeners() {
    // Pagination event listeners
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                renderPage(currentPage);
            }
        });
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            const totalPages = Math.ceil(filteredResources.length / perPage);
            if (currentPage < totalPages) {
                currentPage++;
                renderPage(currentPage);
            }
        });
    }
    
    // Close side panel when clicking outside of it
    document.addEventListener('click', function(event) {
        const sidePanel = document.getElementById('sidePanel');
        const backdrop = document.getElementById('sidePanelBackdrop');
        const isClickInsidePanel = sidePanel && sidePanel.contains(event.target);
        const isResourceLink = event.target.closest('.panel-block');
        const isBackdropClick = event.target === backdrop;
        
        if ((isBackdropClick || (!isClickInsidePanel && !isResourceLink)) && sidePanel && sidePanel.classList.contains('is-active')) {
            closeSidePanel();
        }
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            const sidePanel = document.getElementById('sidePanel');
            if (sidePanel && sidePanel.classList.contains('is-active')) {
                closeSidePanel();
            }
        }
    });
}

// Side panel functionality
function openSidePanel() {
    const sidePanel = document.getElementById('sidePanel');
    const backdrop = document.getElementById('sidePanelBackdrop');
    
    if (sidePanel) sidePanel.classList.add('is-active');
    if (backdrop) backdrop.classList.add('is-active');
    document.body.classList.add('side-panel-open');
}

function closeSidePanel() {
    const sidePanel = document.getElementById('sidePanel');
    const backdrop = document.getElementById('sidePanelBackdrop');
    
    if (sidePanel) sidePanel.classList.remove('is-active');
    if (backdrop) backdrop.classList.remove('is-active');
    document.body.classList.remove('side-panel-open');
}

function showLoading() {
    const content = document.getElementById('sidePanelContent');
    if (content) {
        content.innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <div class="loading-spinner"></div>
                <p style="margin-top: 1rem;">Loading resource data...</p>
            </div>
        `;
    }
}

function showError(message) {
    const content = document.getElementById('sidePanelContent');
    if (content) {
        content.innerHTML = `
            <div class="notification is-danger">
                <strong>Error:</strong> ${message}
            </div>
        `;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function syntaxHighlight(json) {
    if (typeof json !== 'string') {
        json = JSON.stringify(json, null, 2);
    }
    
    // Escape HTML first
    json = escapeHtml(json);
    
    // Apply syntax highlighting
    json = json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        let cls = 'json-number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'json-key';
                // Remove the colon from the match for styling, we'll add it back
                match = match.slice(0, -1);
                return '<span class="' + cls + '">' + match + '</span><span class="json-punctuation">:</span>';
            } else {
                cls = 'json-string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'json-boolean';
        } else if (/null/.test(match)) {
            cls = 'json-null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
    
    // Highlight punctuation (brackets, braces, commas)
    json = json.replace(/([{}[\],])/g, '<span class="json-punctuation">$1</span>');
    
    return json;
}

function makeJsonCollapsible(element) {
    // This function would add collapsible functionality
    // For now, we'll keep it simple and just return the element
    // Future enhancement: add click handlers for { } and [ ] to collapse/expand
    return element;
}

function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        // Use the modern clipboard API
        navigator.clipboard.writeText(text).then(() => {
            showCopySuccess();
        }).catch(err => {
            console.error('Failed to copy: ', err);
            fallbackCopyTextToClipboard(text);
        });
    } else {
        // Fallback for older browsers
        fallbackCopyTextToClipboard(text);
    }
}

function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showCopySuccess();
        }
    } catch (err) {
        console.error('Fallback: Oops, unable to copy', err);
    }
    
    document.body.removeChild(textArea);
}

function showCopySuccess() {
    const copyBtn = document.querySelector('.copy-button');
    if (copyBtn) {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copied!';
        copyBtn.style.backgroundColor = '#48c774';
        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.style.backgroundColor = '#433fca';
        }, 2000);
    }
}

// Helper function to generate preferences section HTML
function getPreferencesHtml() {
    const currentThreshold = localStorage.getItem('jsonSizeThreshold') || 0.5;
    const autoChunk = localStorage.getItem('autoChunkLargeJson') === 'true';
    
    return `
        <details class="has-background-grey-darker">
            <summary class="has-background-grey-dark has-text-white-ter p-3 is-clickable" style="cursor: pointer;">
                <span class="is-size-7">Display Preferences</span>
            </summary>
            <div class="box has-background-grey-dark has-text-white-ter m-0" style="border-radius: 0;">
                <div class="content is-small">
                    <div class="field">
                        <label class="checkbox has-text-white-ter">
                            <input type="checkbox" id="autoChunkPreference" ${autoChunk ? 'checked' : ''} 
                                   onchange="event.stopPropagation(); updateAutoChunkPreference(this.checked)" 
                                   class="mr-2">
                            Always use chunked view for large files
                        </label>
                    </div>
                    <div class="field is-grouped">
                        <div class="control">
                            <label class="label is-small has-text-white-ter">Size threshold:</label>
                        </div>
                        <div class="control">
                            <div class="select is-dark is-small">
                                <select id="thresholdSelector" value="${currentThreshold}" 
                                        onchange="event.stopPropagation(); updateThresholdPreference(this.value)">
                                    <option value="0.25" ${currentThreshold == 0.25 ? 'selected' : ''}>250 KB</option>
                                    <option value="0.5" ${currentThreshold == 0.5 ? 'selected' : ''}>500 KB</option>
                                    <option value="1" ${currentThreshold == 1 ? 'selected' : ''}>1 MB</option>
                                    <option value="2" ${currentThreshold == 2 ? 'selected' : ''}>2 MB</option>
                                    <option value="5" ${currentThreshold == 5 ? 'selected' : ''}>5 MB</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="field is-grouped">
                        <div class="control">
                            <button class="button is-link is-small" onclick="event.stopPropagation(); showChunkedJson()">
                                Switch to Chunked View
                            </button>
                        </div>
                        <div class="control">
                            <button class="button is-success is-small" onclick="event.stopPropagation(); showFullJson()">
                                Switch to Full View
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </details>
    `;
}

// Helper functions to update preferences
function updateAutoChunkPreference(checked) {
    localStorage.setItem('autoChunkLargeJson', checked.toString());
}

function updateThresholdPreference(threshold) {
    localStorage.setItem('jsonSizeThreshold', threshold);
}

async function loadResourceInSidePanel(resourceType, resourceName) {
    const titleElement = document.getElementById('sidePanelTitle');
    if (titleElement) {
        titleElement.textContent = `${resourceType}: ${resourceName}`;
    }
    openSidePanel();
    showLoading();
    
    try {
        // Get current URL parameters to maintain context
        const urlParams = new URLSearchParams(window.location.search);
        const region = urlParams.get('region') || '';
        const apiVersion = urlParams.get('api_version') || 'v2';
        
        // Build the fetch URL with current parameters
        let fetchUrl = `/ui/resources/${resourceType}/${encodeURIComponent(resourceName)}`;
        const params = new URLSearchParams();
        if (region) params.append('region', region);
        params.append('api_version', apiVersion);
        
        if (params.toString()) {
            fetchUrl += '?' + params.toString();
        }
        
        const response = await fetch(fetchUrl, {
            credentials: 'same-origin' // Include cookies in the request
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        const jsonString = JSON.stringify(data, null, 2);
        const sizeKB = (new Blob([jsonString]).size / 1024).toFixed(1);
        const sizeMB = sizeKB / 1024;
        
        // Store the data globally
        currentResourceData = {
            data: data,
            jsonString: jsonString,
            sizeKB: sizeKB,
            sizeMB: sizeMB
        };
        
        // Check if the JSON is large and show warning/chunked view
        // Use a lower threshold (500KB) to be more conservative about browser performance
        const threshold = localStorage.getItem('jsonSizeThreshold') || 0.5; // MB
        if (sizeMB > threshold) {
            // Check user preference for auto-chunking
            const autoChunk = localStorage.getItem('autoChunkLargeJson') === 'true';
            if (autoChunk) {
                showChunkedJson();
            } else {
                showLargeJsonWarning(resourceType, resourceName);
            }
        } else {
            showFullJson();
        }
    } catch (error) {
        console.error('Error loading resource:', error);
        showError(error.message);
    }
}

function showLargeJsonWarning(resourceType, resourceName) {
    const sizeKB = currentResourceData.sizeKB;
    const sizeMB = currentResourceData.sizeMB;
    
    const content = document.getElementById('sidePanelContent');
    if (content) {
        content.innerHTML = `
            <div class="notification is-warning">
                <p>
                    <strong>Large JSON detected (${sizeKB} KB / ${sizeMB.toFixed(1)} MB)</strong><br>
                    Loading this much data may slow down your browser. <br>
                </p>
                
                Choose an option:
                <button class="button is-dark is-small" onclick="event.stopPropagation(); showChunkedJson()">
                    View in Chunks
                </button>
                <button class="button is-dark is-small" onclick="event.stopPropagation(); showFullJson()">
                    Load Full JSON
                </button>
            </div>
        `;
    }
}

function showChunkedJson() {
    const lines = currentResourceData.jsonString.split('\n');
    totalChunks = Math.ceil(lines.length / currentChunkSize);
    currentChunkIndex = 0;
    
    renderChunkedJson();
}

function showFullJson() {
    // Store the JSON string globally for copying
    window.currentJsonData = currentResourceData.jsonString;
    
    const content = document.getElementById('sidePanelContent');
    if (content) {
        content.innerHTML = `
            <div class="json-container">
                <div class="json-header">
                    <span style="color: #d4d4d4; font-size: 0.875rem;">JSON Response (${currentResourceData.sizeKB} KB) - Full View</span>
                    <button class="button is-primary is-small" onclick="event.stopPropagation(); copyToClipboard(window.currentJsonData)">
                        Copy JSON
                    </button>
                </div>
                ${getPreferencesHtml()}
                <div class="json-content">${syntaxHighlight(currentResourceData.data)}</div>
            </div>
        `;
    }
}

function renderChunkedJson() {
    const lines = currentResourceData.jsonString.split('\n');
    const startLine = currentChunkIndex * currentChunkSize;
    const endLine = Math.min(startLine + currentChunkSize, lines.length);
    const chunkLines = lines.slice(startLine, endLine);
    const chunkText = chunkLines.join('\n');
    
    // Store current chunk for copying
    window.currentJsonData = currentResourceData.jsonString; // Always allow copying full JSON
    window.currentChunkData = chunkText;
    
    const content = document.getElementById('sidePanelContent');
    if (content) {
        content.innerHTML = `
            <div class="json-container">
                <div class="json-header">
                    <span style="color: #d4d4d4; font-size: 0.875rem;">JSON Response (${currentResourceData.sizeKB} KB) - Chunked View</span>
                    <button class="button is-primary is-small" onclick="event.stopPropagation(); copyToClipboard(window.currentJsonData)">
                        Copy Full JSON
                    </button>
                </div>
                ${getPreferencesHtml()}
                <div class="json-chunk-controls p-4">
                    <div class="field is-grouped is-grouped-multiline">
                        <div class="control">
                            <label class="label is-small has-text-white">Lines per chunk:</label>
                            <div class="select is-dark is-small">
                                <select onchange="event.stopPropagation(); changeChunkSize(this.value)">
                                    <option value="50" ${currentChunkSize === 50 ? 'selected' : ''}>50</option>
                                    <option value="100" ${currentChunkSize === 100 ? 'selected' : ''}>100</option>
                                    <option value="250" ${currentChunkSize === 250 ? 'selected' : ''}>250</option>
                                    <option value="500" ${currentChunkSize === 500 ? 'selected' : ''}>500</option>
                                    <option value="1000" ${currentChunkSize === 1000 ? 'selected' : ''}>1000</option>
                                    <option value="2000" ${currentChunkSize === 2000 ? 'selected' : ''}>2000</option>
                                    <option value="5000" ${currentChunkSize === 5000 ? 'selected' : ''}>5000</option>
                                </select>
                            </div>
                        </div>
                        <div class="control">
                            <div class="buttons">
                                <button class="button is-primary is-small" onclick="event.stopPropagation(); previousChunk()" ${currentChunkIndex === 0 ? 'disabled' : ''}>
                                    ← Previous
                                </button>
                                <button class="button is-primary is-small" onclick="event.stopPropagation(); nextChunk()" ${currentChunkIndex >= totalChunks - 1 ? 'disabled' : ''}>
                                    Next →
                                </button>
                                <button class="button is-info is-small" onclick="event.stopPropagation(); copyToClipboard(window.currentChunkData)">
                                    Copy Chunk
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                <progress class="progress is-primary is-small" value="${endLine}" max="${lines.length}">
                    Chunk ${currentChunkIndex + 1} of ${totalChunks}
                </progress>
                <div class="json-content">${syntaxHighlight(chunkText)}</div>
            </div>
        `;
    }
}

function changeChunkSize(newSize) {
    currentChunkSize = parseInt(newSize);
    const lines = currentResourceData.jsonString.split('\n');
    totalChunks = Math.ceil(lines.length / currentChunkSize);
    
    // Adjust current chunk index to stay roughly in the same area
    const currentLine = currentChunkIndex * currentChunkSize;
    currentChunkIndex = Math.floor(currentLine / currentChunkSize);
    currentChunkIndex = Math.min(currentChunkIndex, totalChunks - 1);
    
    renderChunkedJson();
}

function previousChunk() {
    if (currentChunkIndex > 0) {
        currentChunkIndex--;
        renderChunkedJson();
    }
}

function nextChunk() {
    if (currentChunkIndex < totalChunks - 1) {
        currentChunkIndex++;
        renderChunkedJson();
    }
}

async function loadVirtualHostInSidePanel(routeConfiguration, virtualHost) {
    const titleElement = document.getElementById('sidePanelTitle');
    if (titleElement) {
        titleElement.textContent = `Virtual Host: ${virtualHost}`;
    }
    openSidePanel();
    showLoading();
    
    try {
        // Get current URL parameters to maintain context
        const urlParams = new URLSearchParams(window.location.search);
        const region = urlParams.get('region') || '';
        const apiVersion = urlParams.get('api_version') || 'v2';
        
        // Build the fetch URL with current parameters
        let fetchUrl = `/ui/resources/routes/${encodeURIComponent(routeConfiguration)}/${encodeURIComponent(virtualHost)}`;
        const params = new URLSearchParams();
        if (region) params.append('region', region);
        params.append('api_version', apiVersion);
        
        if (params.toString()) {
            fetchUrl += '?' + params.toString();
        }
        
        const response = await fetch(fetchUrl, {
            credentials: 'same-origin' // Include cookies in the request
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        const jsonString = JSON.stringify(data, null, 2);
        const sizeKB = (new Blob([jsonString]).size / 1024).toFixed(1);
        const sizeMB = sizeKB / 1024;
        
        // Store the data globally
        currentResourceData = {
            data: data,
            jsonString: jsonString,
            sizeKB: sizeKB,
            sizeMB: sizeMB
        };
        
        // Check if the JSON is large and show warning/chunked view
        const threshold = localStorage.getItem('jsonSizeThreshold') || 0.5; // MB
        if (sizeMB > threshold) {
            // Check user preference for auto-chunking
            const autoChunk = localStorage.getItem('autoChunkLargeJson') === 'true';
            if (autoChunk) {
                showChunkedJson();
            } else {
                showLargeJsonWarning('Virtual Host', virtualHost);
            }
        } else {
            showFullJson();
        }
    } catch (error) {
        console.error('Error loading virtual host:', error);
        showError(error.message);
    }
}

function filter_results(id) {
    const input = document.getElementById(id);
    if (!input) return;
    
    const filter = input.value.toLowerCase();

    filteredResources = resources.filter((res) => {
        const name = res.name || "";
        return name.toLowerCase().includes(filter);
    });

    currentPage = 1;
    renderPage(currentPage);
    
    // Update the resource count display
    const countElement = document.getElementById('resource-count');
    if (countElement) {
        const count = filteredResources.length;
        const plural = count === 1 ? 'resource' : 'resources';
        countElement.textContent = `${count} ${plural}`;
    }
}

function renderPage(page) {
    const container = document.getElementById('resource-container');
    if (!container) return;
    
    container.innerHTML = '';

    const start = (page - 1) * perPage;
    const end = start + perPage;
    const pageItems = filteredResources.slice(start, end);

    for (const resource of pageItems) {
        const name = resource.name;
        const item = document.createElement('a');
        item.className = 'panel-block has-text-weight-medium';
        item.href = '#';
        item.onclick = (e) => {
            e.preventDefault();
            loadResourceInSidePanel(resourceType, name);
        };
        item.innerHTML = `
            <span class="panel-icon">
                <i class="fas fa-arrow-right" aria-hidden="true"></i>
            </span>
            ${name}
        `;
        container.appendChild(item);
    }
    renderPaginationControls();
}

function renderPaginationControls() {
    const totalPages = Math.ceil(filteredResources.length / perPage);
    const pageList = document.getElementById('page-numbers');
    if (!pageList) return;
    
    pageList.innerHTML = '';

    for (let i = 1; i <= totalPages; i++) {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.className = 'pagination-link';
        if (i === currentPage) {
            a.classList.add('has-background-grey-lighter');
            a.classList.add('has-background-black-bis');
        }
        a.textContent = i;
        a.addEventListener('click', () => {
            currentPage = i;
            renderPage(currentPage);
        });
        li.appendChild(a);
        pageList.appendChild(li);
    }

    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    
    if (prevBtn) prevBtn.disabled = currentPage === 1;
    if (nextBtn) nextBtn.disabled = currentPage === totalPages;
}
