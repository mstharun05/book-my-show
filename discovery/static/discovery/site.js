(() => {
  const dialog = document.getElementById('city-dialog');
  const search = document.getElementById('city-search');
  const choices = [...document.querySelectorAll('.city-choice')];
  let showAll = false;
  const filterCities = () => {
    const term = search.value.trim().toLowerCase();
    choices.forEach((button, index) => { button.hidden = term ? !button.dataset.city.toLowerCase().includes(term) : (!showAll && index >= 10); });
    document.getElementById('city-empty').hidden = choices.some(button => !button.hidden);
  };
  document.querySelectorAll('[data-open-city]').forEach(button => button.addEventListener('click', () => { dialog.showModal(); search.focus(); }));
  document.querySelector('[data-close-city]')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
  search?.addEventListener('input', filterCities);
  document.getElementById('all-cities')?.addEventListener('click', event => { showAll = !showAll; event.target.textContent = showAll ? 'Popular cities' : 'View all cities'; filterCities(); });
  document.getElementById('detect-city')?.addEventListener('click', () => {
    const status = document.getElementById('location-status');
    if (!navigator.geolocation) { status.textContent = 'Location is unavailable. Please choose your city below.'; return; }
    status.textContent = 'Finding a nearby city…';
    navigator.geolocation.getCurrentPosition(position => {
      const cities = JSON.parse(document.getElementById('city-coordinates').textContent);
      const radians = n => n * Math.PI / 180;
      const distance = city => {
        const lat1 = radians(position.coords.latitude), lat2 = radians(city[1]);
        const dlat = lat2 - lat1, dlng = radians(city[2] - position.coords.longitude);
        const a = Math.sin(dlat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlng / 2) ** 2;
        return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - Math.min(1, a)));
      };
      const nearest = cities.reduce((a,b) => distance(a) < distance(b) ? a : b);
      if (distance(nearest) > 100) { status.textContent = 'No nearby listed city found. Please choose your city manually.'; return; }
      search.value = nearest[0]; filterCities();
      status.textContent = `Nearby city: ${nearest[0]}. Select it below to confirm.`;
    }, () => { status.textContent = 'Location was not available. You can select your city manually.'; }, {enableHighAccuracy:false, timeout:10000, maximumAge:300000});
  });
  const carousel = document.querySelector('.feature-carousel');
  if (!carousel) return;
  const slides = [...carousel.querySelectorAll('.feature-slide')];
  const dots = [...carousel.querySelectorAll('.carousel-dots button')];
  let current = 0;
  function go(index) { current = (index + slides.length) % slides.length; slides.forEach((slide,i) => {slide.hidden = i !== current;}); dots.forEach((dot,i) => dot.setAttribute('aria-pressed',String(i === current))); }
  carousel.querySelector('.carousel-prev').addEventListener('click', () => go(current-1));
  carousel.querySelector('.carousel-next').addEventListener('click', () => go(current+1));
  dots.forEach((dot,index) => dot.addEventListener('click', () => go(index)));
  carousel.addEventListener('keydown', event => { if(event.key === 'ArrowRight') go(current+1); if(event.key === 'ArrowLeft') go(current-1); });
})();
