// === Validación previa al envío del formulario de cambio de contraseña ===
document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("form");
    if (!form) return; // seguridad por si el formulario no existe

    const nueva = document.getElementById("nueva");
    const confirmar = document.getElementById("confirmar");

    form.addEventListener("submit", (e) => {
        if (nueva.value !== confirmar.value) {
            e.preventDefault();
            alert("❌ Las contraseñas no coinciden. Por favor, verifica los campos.");
            confirmar.focus();
        }
    });
});