// tips.js — search on the Explore page.
// Asks the server: /api/search?q=...&by=topic|company|profession|result
// by=company  -> a list of companies: [{type: "company", id, name, description, course_count, url}]
// anything else -> a list of courses: [{type: "course", id, title, description, level, lesson_count,
//                                       language, url, company_name, company_url}]
// The "Only courses in Russian/English" switch adds &lang=ru|en (courses only).
// A course card opens the course; its company name opens the company page.

const searchForm = document.querySelector('[data-search-form]');
const searchInput = document.querySelector('[data-search-input]');
const searchStatus = document.querySelector('[data-search-status]');
const resultsBox = document.querySelector('[data-search-results]');
const onlyMyLanguage = document.querySelector('[data-only-my-language]');
const onlyMyLanguageBox = document.querySelector('[data-only-my-language-box]');

// the switch is remembered in this browser
if (onlyMyLanguage) {
  onlyMyLanguage.checked = localStorage.getItem('onlyMyLanguage') === 'yes';
  onlyMyLanguage.addEventListener('change', function () {
    localStorage.setItem('onlyMyLanguage', onlyMyLanguage.checked ? 'yes' : 'no');
    runSearch();
  });
}

let typingTimer = null;

async function runSearch() {
  const searchText = searchInput.value.trim();
  const searchBy = searchForm.querySelector('input[name="by"]:checked').value;

  const isCompanySearch = searchBy === 'company';
  // companies have no language, so the switch is hidden while searching companies
  if (onlyMyLanguageBox) onlyMyLanguageBox.hidden = isCompanySearch;

  let url = '/api/search?q=' + encodeURIComponent(searchText) + '&by=' + searchBy;
  if (onlyMyLanguage && onlyMyLanguage.checked && !isCompanySearch) {
    url += '&lang=' + document.documentElement.lang;
  }

  searchStatus.textContent = t('Searching…');

  try {
    const response = await fetch(url);
    const results = await response.json();
    showResults(results, searchText, isCompanySearch);
  } catch (error) {
    searchStatus.textContent = t('Something went wrong. Please try again.');
  }
}

function showResults(results, searchText, isCompanySearch) {
  resultsBox.innerHTML = '';

  if (results.length === 0) {
    const languageFilterOn = onlyMyLanguage && onlyMyLanguage.checked && !isCompanySearch;
    if (languageFilterOn) {
      searchStatus.textContent = t('No courses in your language yet. Turn off “Only courses in…” to see all courses.');
      return;
    }
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
  if (course.language) {
    // EN / RU: the language the course is written in
    const languageChip = makeElement('span', 'chip chip-language', course.language.toUpperCase());
    languageChip.title = course.language === 'ru' ? t('Course in Russian') : t('Course in English');
    chips.append(languageChip);
  }
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
