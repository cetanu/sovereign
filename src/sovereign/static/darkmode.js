document.addEventListener('DOMContentLoaded', function() {
    const darkmode = "theme-dark";
    const lightmode = "theme-light";
    const toggle = document.getElementById('dark-mode-toggle');
    const htmlTag = document.documentElement;

    function preferredTheme() {
        const preference = localStorage.getItem("theme");
        if (preference) {
            return preference;
        }
        if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
            return "dark";
        } else {
            return "light";
        };
    }

    function currentTheme() {
        if (htmlTag.classList.contains(darkmode)) {
            return "dark"
        } else {
            return "light"
        }
    }

    function setTheme(theme) {
        localStorage.setItem("theme", theme);
        if (theme === "dark") {
            htmlTag.classList.remove(lightmode);
            htmlTag.classList.add(darkmode);
            toggle.textContent = '🌘';
        } else {
            htmlTag.classList.remove(darkmode);
            htmlTag.classList.add(lightmode);
            toggle.textContent = '🌞';
        }
    }

    setTheme(preferredTheme());

    toggle.addEventListener("click", function() {
        let current = currentTheme();
        console.log("Current theme: " + current);
        if (current === "dark") {
            setTheme("light");
        } else {
            setTheme("dark");
        }
    });
});
