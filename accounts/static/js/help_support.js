function toggleFaq(item) {
    document.querySelectorAll('.faq-item.open').forEach(openItem => {
        if (openItem !== item) {
            openItem.classList.remove('open');
        }
    });
    item.classList.toggle('open');
}