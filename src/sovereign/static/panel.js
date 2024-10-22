document.addEventListener('DOMContentLoaded', function() {
    function clearSearch() {
        const searchInput = document.getElementById('searchInput');
        searchInput.placeholder = '';
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

        const virtualHosts = document.querySelectorAll('.virtualhost');
        if (filter === "all") {
            virtualHosts.forEach(vh => vh.classList.remove('filtered'));
        } else {
            virtualHosts.forEach(vh => {
                if (vh.getAttribute("data-category") == filter) {
                    vh.classList.remove('filtered');
                } else {
                    vh.classList.add('filtered');
                }
            });
        }
        clearSearch();
    };

    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', function() {
        const query = searchInput.value.toLowerCase();
        const panelBlocks = document.querySelectorAll('.virtualhost');
        panelBlocks.forEach(block => {
            const text = block.textContent.toLowerCase();
            if (text.includes(query)) {
                block.classList.remove('filtered');
            } else {
                block.classList.add('filtered');
            }
        });
    });

    const allTab = document.querySelector('.panel-tabs a.is-active');
    filterTabs(allTab, 'all');
});
