// Card markup only: no requests, storage or navigation here.
// t()/tn() come from the shared main.js loaded before this catalog module.
// User-supplied titles and descriptions always use textContent, never innerHTML.

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function shorten(text, maxLength) {
  return text && text.length > maxLength ? text.slice(0, maxLength - 1) + '…' : text || '';
}

export function makeCourseCard(course) {
  const card = makeElement('article', 'card course-card catalog-card');
  const top = makeElement('div', 'course-card-top');
  top.append(makeElement('span', 'course-topic', course.topic || t('Course')));
  if (course.language) {
    const language = makeElement('span', 'chip chip-language', course.language.toUpperCase());
    language.title = course.language === 'ru' ? t('Course in Russian') : t('Course in English');
    top.append(language);
  }
  const companyLink = makeElement('a', 'company-link course-card-company small muted', course.company_name);
  companyLink.href = course.company_url;
  const title = makeElement('h3', 'course-card-title');
  const link = makeElement('a', 'stretched-link', course.title);
  link.href = course.url;
  title.append(link);
  const bottom = makeElement('div', 'course-card-bottom');
  const chips = makeElement('div', 'chip-row');
  chips.append(makeElement('span', 'chip', course.level), makeElement('span', 'chip', tn(course.lesson_count, '{count} lesson', '{count} lessons')));
  if (course.is_private) chips.append(makeElement('span', 'chip chip-dark', t('Private')));
  const arrow = makeElement('span', 'course-card-arrow', '↗');
  arrow.setAttribute('aria-hidden', 'true');
  bottom.append(chips, arrow);
  card.append(top, companyLink, title);
  if (course.description) card.append(makeElement('p', 'course-card-text muted', shorten(course.description, 140)));
  card.append(bottom);
  return card;
}

export function makeCompanyCard(company) {
  const card = makeElement('a', 'card result-company');
  card.href = company.url;
  let avatar;
  if (company.avatar_url) {
    avatar = makeElement('img', 'avatar avatar-photo');
    avatar.src = company.avatar_url;
    avatar.alt = '';
    avatar.width = 44;
    avatar.height = 44;
    avatar.loading = 'lazy';
  } else {
    avatar = makeElement('span', 'avatar', company.name.slice(0, 2).toUpperCase());
    avatar.setAttribute('aria-hidden', 'true');
  }
  const info = makeElement('div');
  info.append(makeElement('h3', '', company.name), makeElement('p', 'muted', shorten(company.description, 140)), makeElement('span', 'chip', tn(company.course_count, '{count} course', '{count} courses')));
  card.append(avatar, info);
  return card;
}

export function makeMessageCard(title, message, buttonText, onClick) {
  const card = makeElement('div', 'card catalog-empty');
  const button = makeElement('button', 'btn btn-outline', buttonText);
  button.type = 'button';
  button.addEventListener('click', onClick);
  card.append(makeElement('h3', '', title), makeElement('p', 'muted', message), button);
  return card;
}
