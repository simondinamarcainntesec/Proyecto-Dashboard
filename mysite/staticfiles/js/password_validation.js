// === Validación previa al envío del formulario de cambio/restablecimiento de contraseña ===
document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("form");
    if (!form) return;

    // Busca campos de contraseña
    const nueva = document.getElementById("nueva") || document.getElementById("id_new_password1");
    const confirmar = document.getElementById("confirmar") || document.getElementById("id_new_password2");

    // Si no hay campos de contraseña, salimos sin hacer nada (evita aplicarlo al formulario de recuperación)
    if (!nueva || !confirmar) return;

    // Crear contenedor de mensajes de error
    const errorBox = document.createElement("div");
    errorBox.style.color = "#d93025";
    errorBox.style.background = "#f8d7da";
    errorBox.style.border = "1px solid #f5c6cb";
    errorBox.style.padding = "0.75rem 1rem";
    errorBox.style.marginBottom = "1rem";
    errorBox.style.borderRadius = "4px";
    errorBox.style.display = "none";
    errorBox.style.textAlign = "left";
    form.prepend(errorBox);

    // Expresiones regulares
    const regexNumber = /\d/;
    const regexUppercase = /[A-Z]/;
    const regexSpecial = /[!@#$%^&*(),.?":{}|<>_\-+=/\\;'\[\]`~]/;

    form.addEventListener("submit", (e) => {
        const pass = nueva?.value || "";
        const confirm = confirmar?.value || "";
        const errores = [];

        if (pass.length < 8) errores.push("La contraseña debe tener al menos 8 caracteres.");
        if (!regexNumber.test(pass)) errores.push("Debe contener al menos un número.");
        if (!regexUppercase.test(pass)) errores.push("Debe contener al menos una letra mayúscula.");
        if (!regexSpecial.test(pass)) errores.push("Debe contener al menos un carácter especial.");
        if (pass !== confirm) errores.push("Las contraseñas no coinciden.");

        if (errores.length > 0) {
            e.preventDefault();
            errorBox.innerHTML = errores.map(e => `• ${e}`).join("<br>");
            errorBox.style.display = "block";
            nueva.focus();
        } else {
            errorBox.style.display = "none";
        }
    });
});