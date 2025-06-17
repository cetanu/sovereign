document.addEventListener('DOMContentLoaded', function() {
    let currentTabFilter = 'all'; // Track the current tab filter
    
    function clearSearch() {
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.value = '';
        }
    }

    // Function to apply both tab and search filters
    function applyFilters() {
        const searchInput = document.getElementById('searchInput');
        const query = searchInput ? searchInput.value.toLowerCase() : '';
        const virtualHosts = document.querySelectorAll('.virtualhost');
        
        virtualHosts.forEach(vh => {
            const text = vh.textContent.toLowerCase();
            const category = vh.getAttribute("data-category");
            
            // Check if it passes the tab filter
            const passesTabFilter = (currentTabFilter === 'all') || (category === currentTabFilter);
            
            // Check if it passes the search filter
            const passesSearchFilter = query === '' || text.includes(query);
            
            // Show only if it passes both filters
            if (passesTabFilter && passesSearchFilter) {
                vh.classList.remove('filtered');
            } else {
                vh.classList.add('filtered');
            }
        });
    }

    // Function to hide all panels except active
    function updateVisibility() {
        const panelBlocks = document.querySelectorAll('.virtualhost');
        panelBlocks.forEach(block => {
            if (!block.classList.contains('is-active')) {
                block.classList.add('filtered');
            } else {
                block.classList.remove('filtered');
            }
        });
    }
    updateVisibility();

    window.filterTabs = function(element, filter) {
        const tabs = document.querySelectorAll('.panel-tabs a');
        tabs.forEach(tab => tab.classList.remove('is-active'));
        element.classList.add('is-active');
        
        currentTabFilter = filter; // Update the current tab filter
        
        // Clear virtual hosts search input when switching tabs
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.value = null;
        }
        
        applyFilters();
    };

    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            applyFilters(); // Apply both filters when searching
        });
    }

    const allTab = document.querySelector('.panel-tabs a.is-active');
    if (allTab) {
        filterTabs(allTab, 'all');
    }
});
