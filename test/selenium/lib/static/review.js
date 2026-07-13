document.querySelectorAll('.promote button').forEach(btn => {
    btn.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(btn.dataset.copy);
        } catch (e) { /* clipboard blocked */ }
        const orig = btn.textContent;
        btn.classList.add('copied');
        btn.textContent = 'Copied!';
        setTimeout(() => {
            btn.textContent = orig;
            btn.classList.remove('copied');
        }, 1500);
    });
});
