// Renderar .pdf-preview-element via pdf.js.
// Kräver att pdfjsLib är laddat och GlobalWorkerOptions.workerSrc satt.
// Anropa initPdfPreviews() efter att elementen lagts till i DOM:en.
(function () {
    const observer = typeof IntersectionObserver !== 'undefined'
        ? new IntersectionObserver(onIntersect, { rootMargin: '200px' })
        : null;

    function onIntersect(entries) {
        entries.forEach(e => {
            if (e.isIntersecting) {
                observer.unobserve(e.target);
                renderPreview(e.target);
            }
        });
    }

    async function renderPreview(el) {
        if (el.dataset.pdfInit) return;
        el.dataset.pdfInit = '1';
        const src = el.dataset.src;
        try {
            const pdf = await pdfjsLib.getDocument(src).promise;
            el.innerHTML = '';
            for (let i = 1; i <= pdf.numPages; i++) {
                const page = await pdf.getPage(i);
                const w = el.clientWidth || 240;
                const baseVp = page.getViewport({ scale: 1 });
                const vp = page.getViewport({ scale: w / baseVp.width });
                const canvas = document.createElement('canvas');
                canvas.width = vp.width;
                canvas.height = vp.height;
                canvas.style.cssText = 'width:100%;display:block;';
                el.appendChild(canvas);
                await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;
            }
        } catch (e) {
            el.innerHTML = '<div class="text-muted small text-center py-3">Förhandsvisning ej tillgänglig</div>';
        }
    }

    window.initPdfPreviews = function () {
        document.querySelectorAll('.pdf-preview[data-src]:not([data-pdf-init])').forEach(el => {
            if (observer) {
                observer.observe(el);
            } else {
                renderPreview(el);
            }
        });
    };
}());
