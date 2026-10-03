const loginInput = document.getElementById("loginInput");
const passwordInput = document.getElementById("passwordInput");
const loginButton = document.getElementById("loginButton");
const messageBox = document.getElementById("messageBox");


function showMessage(text, isError) {
    messageBox.textContent = text;
    messageBox.className = isError ? "message error" : "message success";
}


async function sendLoginRequest(login, password) {
    const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: login, password: password })
    });
    return await response.json();
}


loginButton.addEventListener("click", async function () {
    const login = loginInput.value.trim();
    const password = passwordInput.value;

    if (login === "" || password === "") {
        showMessage("Заполни логин и пароль", true);
        return;
    }

    try {
        const serverAnswer = await sendLoginRequest(login, password);
        showMessage(serverAnswer.message, !serverAnswer.ok);
    } catch (error) {
        showMessage("Не удалось связаться с сервером", true);
    }
});
