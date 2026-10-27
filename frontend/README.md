# Frontend

`templates/` — Jinja HTML. `static/css/` — стили. `static/js/` — JavaScript без сборщика.

Каталог: `catalog.js` управляет формой/URL/запросами; `catalog-cards.js` рисует карточки через безопасный textContent. Оба подключаются как ES modules. Начальная серверная карточка — макрос `catalog_card` в `templates/partials/macros.html`.

Порядок стилей: style.css → стили страницы → refinements.css. Внешний вид этим рефакторингом не менялся.

[Подробное руководство](../docs/CODE-GUIDE.md)
