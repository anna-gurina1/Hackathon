// tips.js — search on the Explore page.
// Asks the server: /api/search?q=...&by=topic|company|profession|result
// by=company  -> a list of companies: [{type: "company", id, name, description, course_count, url}]
// anything else -> a list of courses: [{type: "course", id, title, description, level, lesson_count,
//                                       url, company_name, company_url}]
// A course card opens the course; its company name opens the company page.

const searchForm = document.querySelector('[data-search-form]');
const searchInput = document.querySelector('[data-search-input]');
const searchStatus = document.querySelector('[data-search-status]');
const resultsBox = document.querySelector('[data-search-results]');

let typingTimer = null;

async function runSearch() {
  const searchText = searchInput.value.trim();
  const searchBy = searchForm.querySelector('input[name="by"]:checked').value;

  searchStatus.textContent = t('Searching…');

  try {
    const response = await fetch('/api/search?q=' + encodeURIComponent(searchText) + '&by=' + searchBy);
    const results = await response.json();
    showResults(results, searchText, searchBy === 'company');
  } catch (error) {
    searchStatus.textContent = t('Something went wrong. Please try again.');
  }
}

function showResults(results, searchText, isCompanySearch) {
  resultsBox.innerHTML = '';

  if (results.length === 0) {
    searchStatus.textContent = searchText
      ? t('Nothing found for “{text}”. Try another word or search by something else.', { text: searchText })
      : t('No courses yet.');
    return;
  }

  if (isCompanySearch) {
    searchStatus.textContent = tn(results.length, '{count} company found', '{count} companies found');
  } else {
    searchStatus.textContent = tn(results.length, '{count} course found', '{count} courses found');
  }

  results.forEach(function (item) {
    resultsBox.appendChild(item.type === 'company' ? makeCompanyCard(item) : makeCourseCard(item));
  });
}

// Small helper: an element with a class and text. textContent (not innerHTML) keeps it safe from weird text.
function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function shorten(text, maxLength) {
  if (!text) return '';
  return text.length > maxLength ? text.slice(0, maxLength - 1) + '…' : text;
}

// Course card: the whole card opens the course, the company name opens the company page.
function makeCourseCard(course) {
  const card = makeElement('div', 'card course-card');

  const companyLink = makeElement('a', 'company-link course-card-company small muted', course.company_name);
  companyLink.href = course.company_url;

  const title = makeElement('h3', 'course-card-title');
  const courseLink = makeElement('a', 'stretched-link', course.title);
  courseLink.href = course.url;
  title.appendChild(courseLink);

  const description = makeElement('p', 'course-card-text muted small', shorten(course.description, 110));

  const chips = makeElement('span', 'chip-row');
  chips.append(
    makeElement('span', 'chip', course.level),
    makeElement('span', 'chip', tn(course.lesson_count, '{count} lesson', '{count} lessons'))
  );
  if (course.is_private) chips.append(makeElement('span', 'chip chip-dark', t('🔒 By request')));

  card.append(companyLink, title, description, chips);
  return card;
}

// Company card: opens the company page.
function makeCompanyCard(company) {
  const card = makeElement('a', 'card result-company');
  card.href = company.url;

  let avatar;
  if (company.avatar_url) {
    avatar = makeElement('img', 'avatar avatar-photo');
    avatar.src = company.avatar_url;
    avatar.alt = '';
  } else {
    avatar = makeElement('span', 'avatar', company.name.slice(0, 2).toUpperCase());
  }
  const info = makeElement('div');
  const courseCount = makeElement('span', 'chip',
    tn(company.course_count, '{count} course', '{count} courses'));

  info.append(
    makeElement('h3', '', company.name),
    makeElement('p', 'small muted', shorten(company.description, 140)),
    courseCount
  );
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
