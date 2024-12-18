function filter_results(id, list) {
    // Declare variables
    let input, filter, container, iterable, resource, i, txtValue;
    input = document.getElementById(id);
    filter = input.value.toUpperCase();

    container = document.getElementById(list);
    iterable = container.getElementsByTagName("a");

    // Loop through all list items, and hide those who don't match the search query
    for (i = 0; i < iterable.length; i++) {
        resource = iterable[i];
        txtValue = resource.textContent;
        if (txtValue.toUpperCase().indexOf(filter) > -1) {
            iterable[i].style.display = "";
        } else {
            iterable[i].style.display = "none";
        }
    }
}
