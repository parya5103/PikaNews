// PikaNews Utility Functions

const Utils = {
    // Format date relative to now
    formatDate(dateString) {
        if (!dateString) return '';
        
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);
        
        const intervals = {
            year: 31536000,
            month: 2592000,
            week: 604800,
            day: 86400,
            hour: 3600,
            minute: 60,
            second: 1
        };
        
        for (const [unit, seconds] of Object.entries(intervals)) {
            const interval = Math.floor(diffInSeconds / seconds);
            if (interval >= 1) {
                return `${interval} ${unit}${interval !== 1 ? 's' : ''} ago`;
            }
        }
        
        return 'Just now';
    },
    
    // Format date as readable string
    formatDateLong(dateString) {
        if (!dateString) return '';
        
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    // Format date for display
    formatDateDisplay(dateString) {
        if (!dateString) return '';
        
        const date = new Date(dateString);
        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();
        
        if (isToday) {
            return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        }
        
        const isThisYear = date.getFullYear() === now.getFullYear();
        if (isThisYear) {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }
        
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    },
    
    // Truncate text
    truncate(text, length) {
        if (!text) return '';
        if (text.length <= length) return text;
        return text.substring(0, length) + '...';
    },
    
    // Sanitize HTML to prevent XSS
    sanitize(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    // Escape HTML entities
    escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    },
    
    // Get category color
    getCategoryColor(category) {
        const colors = {
            bollywood: '#ec4899',
            hollywood: '#8b5cf6',
            entertainment: '#f59e0b',
            technology: '#3b82f6',
            gaming: '#10b981',
            business: '#06b6d4',
            sports: '#f97316',
            trending: '#ef4444'
        };
        return colors[category?.toLowerCase()] || '#6b7280';
    },
    
    // Get category icon
    getCategoryIcon(category) {
        const icons = {
            bollywood: '🎬',
            hollywood: '🎭',
            entertainment: '🎤',
            technology: '💻',
            gaming: '🎮',
            business: '💼',
            sports: '⚽',
            trending: '🔥'
        };
        return icons[category?.toLowerCase()] || '📰';
    },
    
    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // Throttle function
    throttle(func, limit) {
        let inThrottle = false;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    // Copy text to clipboard
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (error) {
            // Fallback for older browsers
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            const success = document.execCommand('copy');
            document.body.removeChild(textarea);
            return success;
        }
    },
    
    // Share using Web Share API
    async share({ title, text, url }) {
        if (navigator.share) {
            try {
                await navigator.share({ title, text, url });
                return true;
            } catch (error) {
                if (error.name !== 'AbortError') {
                    console.error('Share failed:', error);
                }
                return false;
            }
        }
        
        // Fallback: copy to clipboard
        const shareText = `${title}\n${text}\n${url}`;
        await this.copyToClipboard(shareText);
        return false;
    },
    
    // Validate URL
    isValidUrl(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    },
    
    // Get domain from URL
    getDomain(url) {
        try {
            const domain = new URL(url).hostname;
            return domain.replace('www.', '');
        } catch {
            return url;
        }
    },
    
    // Format number with commas
    formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    },
    
    // Check if element is in viewport
    isInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    },
    
    // Lazy load images
    lazyLoadImages() {
        const images = document.querySelectorAll('img[data-src]');
        
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    img.classList.add('loaded');
                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: '50px 0px',
            threshold: 0.01
        });
        
        images.forEach(img => imageObserver.observe(img));
    },
    
    // Smooth scroll to element
    scrollToElement(element, offset = 0) {
        const elementPosition = element.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - offset;
        
        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        });
    },
    
    // Scroll to top
    scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    },
    
    // Add loading state
    showLoading(element) {
        element.innerHTML = `
            <div class="loading-placeholder">
                <div class="loading-spinner"></div>
                <p>Loading...</p>
            </div>
        `;
    },
    
    // Show empty state
    showEmpty(element, message = 'No articles found') {
        element.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10 21l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
                </svg>
                <h3>${message}</h3>
            </div>
        `;
    },
    
    // Show error state
    showError(element, message = 'Error loading content') {
        element.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
                <h3>Error</h3>
                <p>${message}</p>
            </div>
        `;
    },
    
    // Get query parameter
    getQueryParam(name) {
        const params = new URLSearchParams(window.location.search);
        return params.get(name);
    },
    
    // Set query parameter
    setQueryParam(name, value) {
        const params = new URLSearchParams(window.location.search);
        params.set(name, value);
        return `?${params.toString()}`;
    },
    
    // Parse URL hash
    parseHash() {
        const hash = window.location.hash.substring(1);
        return hash ? JSON.parse(decodeURIComponent(hash)) : null;
    },
    
    // Set URL hash
    setHash(data) {
        window.location.hash = encodeURIComponent(JSON.stringify(data));
    }
};

// Initialize lazy loading when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', Utils.lazyLoadImages);
} else {
    Utils.lazyLoadImages();
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Utils;
}
