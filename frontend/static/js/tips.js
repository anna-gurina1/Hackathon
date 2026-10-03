// tips.js — search on the Explore page.
// Asks the server: /api/search?q=...&by=topic|company|profession|result
// Server answers with a list of companies: [{id, name, description, course_count, url}]

const searchForm = document.querySelector('[data-search-form]');
const searchInput = document.querySelector('[data-search-input]');
const searchStatus = document.querySelector('[data-search-status]');
const resultsBox = document.querySelector('[data-search-results]');

let typingTimer = null;

async function runSearch() {
  const searchText = searchInput.value.trim();
  const searchBy = searchForm.querySelector('input[name="by"]:checked').value;

  searchStatus.textContent = 'Searching…';

  try {
    const response = await fetch('/api/search?q=' + encodeURIComponent(searchText) + '&by=' + searchBy);
    const companies = await response.json();
    showCompanies(companies, searchText);
  } catch (error) {
    searchStatus.textContent = 'Something went wrong. Please try again.';
  }
}

function showCompanies(companies, searchText) {
  resultsBox.innerHTML = '';

  if (companies.length === 0) {
    searchStatus.textContent = searchText
      ? 'Nothing found for “' + searchText + '”. Try another word or search by something else.'
      : 'No courses yet.';
    return;
  }

  searchStatus.textContent = companies.length === 1 ? '1 company found' : companies.length + ' companies found';

  companies.forEach(function (company) {
    resultsBox.appendChild(makeCompanyCard(company));
  });
}

// Builds one result card. textContent (not innerHTML) keeps it safe from weird text.
function makeCompanyCard(company) {
  const card = document.createElement('a');
  card.className = 'card result-company';
  card.href = company.url;

  const avatar = document.createElement('span');
  avatar.className = 'avatar';
  avatar.textContent = company.name.slice(0, 2).toUpperCase();

  const info = document.createElement('div');

  const name = document.createElement('h3');
  name.textContent = company.name;

  const description = document.createElement('p');
  description.className = 'small muted';
  description.textContent = company.description || '';

  const courseCount = document.createElement('span');
  courseCount.className = 'chip';
  courseCount.textContent = company.course_count === 1 ? '1 course' : company.course_count + ' courses';

  info.append(name, description, courseCount);
  card.append(avatar, info);
  return card;
}

// Search when the form is sent…
searchForm.addEventListener('submit', function (event) {
  event.preventDefault();
  runSearch();
});

// …when "Topic / Company / …" is switched…
searchForm.querySelectorAll('input[name="by"]').forEach(function (option) {
  option.addEventListener('change', runSearch);
});

// …and while typing, after a short pause.
searchInput.addEventListener('input', function () {
  clearTimeout(typingTimer);
  typingTimer = setTimeout(runSearch, 300);
});

// Show everything when the page opens
runSearch();
