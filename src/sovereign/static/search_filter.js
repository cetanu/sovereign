function filter_results(id) {
    const input = document.getElementById(id);
    const filter = input.value.toLowerCase();

    filteredResources = resources.filter((res) => {
        const name = res.name || res.cluster_name || "";
        return name.toLowerCase().includes(filter);
    });

    currentPage = 1;
    renderPage(currentPage);
}

