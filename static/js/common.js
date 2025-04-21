/**
 * Common JavaScript functions for the Raspberry Pi web interface
 */

// Status message handling
function showStatusMessage(message, type = 'info', duration = 3000) {
    const statusElement = document.getElementById('status-message');
    if (!statusElement) return;
    
    statusElement.textContent = message;
    statusElement.className = 'status-bar ' + type;
    statusElement.style.display = 'block';
    
    setTimeout(() => {
        statusElement.style.display = 'none';
    }, duration);
}

// Update the "last update" time
function updateLastUpdateTime() {
    const timeElement = document.getElementById('update-time-value');
    if (timeElement) {
        timeElement.textContent = '0 seconds ago';
        
        let seconds = 0;
        setInterval(() => {
            seconds++;
            let timeText = '';
            
            if (seconds < 60) {
                timeText = `${seconds} second${seconds !== 1 ? 's' : ''} ago`;
            } else if (seconds < 3600) {
                const minutes = Math.floor(seconds / 60);
                timeText = `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
            } else {
                const hours = Math.floor(seconds / 3600);
                timeText = `${hours} hour${hours !== 1 ? 's' : ''} ago`;
            }
            
            timeElement.textContent = timeText;
        }, 1000);
    }
}

// Initialize dark mode from localStorage
function initDarkMode() {
    if (localStorage.getItem('dark-mode') === 'true') {
        document.body.classList.add('dark-mode');
    }
    
    // Add dark mode toggle handler
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', () => {
            document.body.classList.toggle('dark-mode');
            localStorage.setItem('dark-mode', document.body.classList.contains('dark-mode'));
        });
    }
}

// Utility function for making API requests
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(url, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.message || 'API request failed');
        }
        
        return result;
    } catch (error) {
        console.error('API request error:', error);
        showStatusMessage('Error: ' + error.message, 'error');
        throw error;
    }
}

// Initialize standardized tabs
function initTabs() {
    document.querySelectorAll('.nav-tabs').forEach(tabGroup => {
        tabGroup.querySelectorAll('.nav-link').forEach(tabLink => {
            tabLink.addEventListener('click', e => {
                // Only handle tab links that are part of tab navigation
                // Skip links that navigate to other pages (those without hash in href)
                const href = tabLink.getAttribute('href');
                if (!href || !href.startsWith('#')) {
                    return; // Allow regular navigation for non-tab links
                }
                
                e.preventDefault();
                
                // Get target tab ID from href attribute
                const targetId = href.slice(1);
                
                // Deactivate all tabs in this group
                tabGroup.querySelectorAll('.nav-link').forEach(link => {
                    link.classList.remove('active');
                });
                
                // Hide all tab panes
                const tabContentId = tabGroup.getAttribute('data-tab-content') || 'tab-content';
                const tabContent = document.getElementById(tabContentId);
                if (tabContent) {
                    tabContent.querySelectorAll('.tab-pane').forEach(pane => {
                        pane.classList.remove('active');
                    });
                }
                
                // Activate clicked tab and show corresponding pane
                tabLink.classList.add('active');
                const targetPane = document.getElementById(targetId);
                if (targetPane) {
                    targetPane.classList.add('active');
                }
                
                // Save active tab to localStorage
                const tabId = tabGroup.getAttribute('id');
                if (tabId) {
                    localStorage.setItem(`activeTab-${tabId}`, targetId);
                }
            });
        });
        
        // Restore active tab from localStorage if available
        const tabId = tabGroup.getAttribute('id');
        if (tabId) {
            const activeTabId = localStorage.getItem(`activeTab-${tabId}`);
            if (activeTabId) {
                const savedTabLink = tabGroup.querySelector(`[href="#${activeTabId}"]`);
                if (savedTabLink) {
                    savedTabLink.click();
                }
            }
        }
    });
}

// Initialize module grid (reorganizable panels)
function initModuleGrid() {
    function saveGridLayout() {
        try {
            const layouts = {};
            document.querySelectorAll('.module-grid').forEach(grid => {
                const gridId = grid.getAttribute('id');
                if (!gridId) return;
                
                const moduleIds = Array.from(grid.querySelectorAll('.module-card'))
                    .map(el => el.getAttribute('id'))
                    .filter(id => id);
                
                layouts[gridId] = moduleIds;
            });
            
            localStorage.setItem('moduleGridLayouts', JSON.stringify(layouts));
        } catch (error) {
            console.error('Error saving grid layout:', error);
        }
    }
    
    function loadGridLayout() {
        document.querySelectorAll('.module-grid').forEach(grid => {
            try {
                const gridId = grid.getAttribute('id');
                if (!gridId) return;
                
                const savedLayouts = localStorage.getItem('moduleGridLayouts');
                if (!savedLayouts) return;
                
                const layouts = JSON.parse(savedLayouts);
                if (!layouts[gridId]) return;
                
                const moduleIds = layouts[gridId];
                const moduleElements = Array.from(grid.querySelectorAll('.module-card'));
                
                grid.innerHTML = '';
                
                moduleIds.forEach(moduleId => {
                    const moduleEl = moduleElements.find(el => el.getAttribute('id') === moduleId);
                    if (moduleEl) {
                        grid.appendChild(moduleEl);
                    }
                });
            } catch (error) {
                console.error('Error loading grid layout:', error);
            }
        });
    }
    
    // Make modules draggable for reordering (if browser supports it)
    if (typeof window.DragEvent !== 'undefined') {
        document.querySelectorAll('.module-card').forEach(module => {
            module.setAttribute('draggable', 'true');
            
            module.addEventListener('dragstart', e => {
                e.dataTransfer.setData('text/plain', module.getAttribute('id'));
                module.classList.add('dragging');
            });
            
            module.addEventListener('dragend', () => {
                module.classList.remove('dragging');
            });
        });
        
        document.querySelectorAll('.module-grid').forEach(grid => {
            grid.addEventListener('dragover', e => {
                e.preventDefault();
                const afterElement = getDragAfterElement(grid, e.clientY);
                const draggable = document.querySelector('.dragging');
                
                if (afterElement == null) {
                    grid.appendChild(draggable);
                } else {
                    grid.insertBefore(draggable, afterElement);
                }
            });
            
            grid.addEventListener('dragend', saveGridLayout);
        });
    }
    
    // Helper to determine where to place dragged module
    function getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.module-card:not(.dragging)')];
        
        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            
            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }
    
    // Load saved layouts
    loadGridLayout();
}

// Section toggle functionality
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) return;
    
    const isVisible = section.style.display !== 'none';
    section.style.display = isVisible ? 'none' : 'block';
    
    // Update toggle text
    const toggle = document.querySelector(`[data-target="${sectionId}"]`);
    if (toggle) {
        toggle.textContent = isVisible ? 'Show' : 'Hide';
    }
    
    // Save state to localStorage
    localStorage.setItem(`section-${sectionId}`, isVisible ? 'hidden' : 'visible');
}

// Initialize section visibility from localStorage
function initSectionVisibility() {
    document.querySelectorAll('.section-toggle').forEach(toggle => {
        const sectionId = toggle.getAttribute('data-target');
        const section = document.getElementById(sectionId);
        if (!section) return;
        
        const savedState = localStorage.getItem(`section-${sectionId}`);
        if (savedState === 'hidden') {
            section.style.display = 'none';
            toggle.textContent = 'Show';
        }
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initDarkMode();
    updateLastUpdateTime();
    initTabs();
    initModuleGrid();
    initSectionVisibility();
    
    // Add refresh functionality
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
});
