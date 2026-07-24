function initSlideshow(containerId, dataElementId, options) {
    const container = document.getElementById(containerId);
    const dataEl = document.getElementById(dataElementId);
    if (!container || !dataEl) return;

    const photos = JSON.parse(dataEl.textContent);
    const intervalMs = (options && options.interval) || 4500;
    let index = 0;
    let playing = photos.length > 1;
    let timer = null;

    const img = container.querySelector('[data-slide-img]');
    const nameEl = container.querySelector('[data-slide-name]');
    const counterEl = container.querySelector('[data-slide-counter]');
    const progressEl = container.querySelector('[data-slide-progress]');
    const playIcon = container.querySelector('[data-play-icon]');
    const pauseIcon = container.querySelector('[data-pause-icon]');

    function render() {
        if (!photos.length) return;
        const photo = photos[index];
        if (img) {
            img.style.opacity = '0';
            window.setTimeout(() => {
                img.src = photo.url;
                img.alt = photo.name;
                img.style.opacity = '1';
            }, 150);
        }
        if (nameEl) nameEl.textContent = photo.name;
        if (counterEl) counterEl.textContent = (index + 1) + ' / ' + photos.length;
        if (progressEl) progressEl.style.width = (((index + 1) / photos.length) * 100) + '%';
    }

    function resetTimer() {
        if (timer) window.clearInterval(timer);
        timer = playing ? window.setInterval(next, intervalMs) : null;
    }

    function next() {
        if (!photos.length) return;
        index = (index + 1) % photos.length;
        render();
    }

    function prev() {
        if (!photos.length) return;
        index = (index - 1 + photos.length) % photos.length;
        render();
    }

    function goNext() { next(); resetTimer(); }
    function goPrev() { prev(); resetTimer(); }

    function setPlaying(next) {
        playing = next;
        if (playIcon) playIcon.classList.toggle('hidden', playing);
        if (pauseIcon) pauseIcon.classList.toggle('hidden', !playing);
        resetTimer();
    }

    function togglePlay() { setPlaying(!playing); }

    const nextBtn = container.querySelector('[data-next]');
    const prevBtn = container.querySelector('[data-prev]');
    const playBtn = container.querySelector('[data-toggle-play]');
    const fsBtn = container.querySelector('[data-fullscreen]');

    if (nextBtn) nextBtn.addEventListener('click', goNext);
    if (prevBtn) prevBtn.addEventListener('click', goPrev);
    if (playBtn) playBtn.addEventListener('click', togglePlay);
    if (fsBtn) {
        fsBtn.addEventListener('click', () => {
            if (!document.fullscreenElement) {
                container.requestFullscreen && container.requestFullscreen();
            } else {
                document.exitFullscreen && document.exitFullscreen();
            }
        });
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowRight') goNext();
        else if (event.key === 'ArrowLeft') goPrev();
        else if (event.key === ' ' && document.activeElement === document.body) {
            event.preventDefault();
            togglePlay();
        }
    });

    let touchStartX = null;
    container.addEventListener('touchstart', (event) => {
        touchStartX = event.touches[0].clientX;
    }, { passive: true });
    container.addEventListener('touchend', (event) => {
        if (touchStartX === null) return;
        const dx = event.changedTouches[0].clientX - touchStartX;
        if (Math.abs(dx) > 40) {
            dx < 0 ? goNext() : goPrev();
        }
        touchStartX = null;
    });

    setPlaying(playing);
    render();
}
