const input = document.getElementById('filterInput');
const inputMessage = document.getElementById('filterMessage');
const form = document.getElementById('filterForm');

function validateInput(inputString) {
  if (!inputString || inputString.trim() === '') {
    return "empty";
  }
  const validationRegex = /^(?:(?:id|cluster|metadata\.[\w\.\=\-]+|locality\.?(?:zone|sub_zone|region))=[a-zA-Z0-9_-]+ ?)*$/;
  return validationRegex.test(inputString);
}

window.addEventListener('DOMContentLoaded', () => {
  const match = document.cookie.match(/(?:^|; )node_expression=([^;]*)/);
  if (match) {
    input.value = match[1];
  }
});

input.addEventListener('input', (event) => {
  const result = validateInput(event.target.value);
  if (result === "empty") {
    input.className = "input is-dark";
    inputMessage.className = "help is-dark";
    inputMessage.innerHTML = "";
  } else if (result === true) {
    input.className = "input is-success";
    inputMessage.className = "help is-success";
    inputMessage.innerHTML = "Press enter to apply filter expression";
  } else {
    input.className = "input is-danger";
    inputMessage.className = "help is-danger";
    inputMessage.innerHTML = "The node filter expression may have no effect, or be invalid";
  }
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const value = input.value.trim();
  document.cookie = `node_expression=${value}; path=/ui/resources/; max-age=31536000`;
  location.reload();
});
