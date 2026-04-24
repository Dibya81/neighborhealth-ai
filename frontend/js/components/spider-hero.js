/**
 * Spider Hero Section Logic
 * Handles mouse tracking and touch events for the identity reveal effect.
 * Scoped strictly to #spider-hero.
 */
(function() {
    document.addEventListener('DOMContentLoaded', () => {
        const heroSection = document.getElementById('spider-hero');
        if (!heroSection) return;

        const wrapper = heroSection.querySelector('.spider-wrapper');
        const maskGroup = heroSection.querySelector('.spider-mask-group');

        if (!wrapper || !maskGroup) return;

        // 1. Fade-in effect on load
        setTimeout(() => {
            wrapper.classList.add('loaded');
        }, 100);

        function updatePosition(clientX, clientY) {
            const { left, top, width, height } = maskGroup.getBoundingClientRect();
            
            // Calculate percentage position
            const x = ((clientX - left) / width) * 100;
            const y = ((clientY - top) / height) * 100;
            
            // Update CSS variables locally on the hero section
            heroSection.style.setProperty('--spider-mouse-x', `${x}%`);
            heroSection.style.setProperty('--spider-mouse-y', `${y}%`);
        }

        // 2. Mouse tracking for spotlight effect
        heroSection.addEventListener('mousemove', (e) => {
            updatePosition(e.clientX, e.clientY);
        });

        // 3. Reset mask on mouse leave
        heroSection.addEventListener('mouseleave', () => {
            heroSection.style.setProperty('--spider-mouse-x', '50%');
            heroSection.style.setProperty('--spider-mouse-y', '50%');
        });

        // 4. Handle touch events for mobile compatibility
        heroSection.addEventListener('touchmove', (e) => {
            if (e.touches && e.touches[0]) {
                const touch = e.touches[0];
                updatePosition(touch.clientX, touch.clientY);
            }
        }, { passive: true });
    });
})();
