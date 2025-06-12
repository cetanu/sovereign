const input = document.getElementById('filterInput');
const form = document.getElementById('filterForm');

window.addEventListener('DOMContentLoaded', () => {
  const match = document.cookie.match(/(?:^|; )node_expression=([^;]*)/);
  if (match) {
    input.value = match[1];
  }
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const value = input.value.trim();
  document.cookie = `node_expression=${value}; path=/ui/resources/; max-age=31536000`;
  location.reload();
});
