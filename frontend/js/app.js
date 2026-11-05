// PikaNews Main Application

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initMobileMenu();
    initSearch();
    initBookmarks();
    initModals();
    initScroll();
    initBackToTop();
    loadPageData();
    
    // Hide loading screen
    const loadingScreen = document.getElementById('loading-screen');
    if (loadingScreen) {
        setTimeout(() => {
            loadingScreen.classList.add('hidden');
        }, 500);
    }
});

// ============================================
// Theme Management
// ============================================

function initTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
    
    // Load saved theme or use system preference
    const savedTheme = localStorage.getItem('theme');
    const theme = savedTheme || (prefersDark.matches ? 'dark' : 'light');
    
    setTheme(theme);
    
    // Listen for toggle clicks
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }
    
    // Listen for system theme changes
    prefersDark.addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            setTheme(e.matches ? 'dark' : 'light');
        }
    });
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    
    // Update toggle icon
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.classList.toggle('dark', theme === 'dark');
    }
    
    // Dispatch event
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
}

// ============================================
// Mobile Menu
// ============================================

let mobileMenu;

function initMobileMenu() {
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    
    if (!mobileMenuToggle) return;
    
    // Create mobile menu
    mobileMenu = document.createElement('div');
    mobileMenu.className = 'mobile-menu';
    mobileMenu.innerHTML = `
        <div class="mobile-menu-header">
            <div class="mobile-menu-nav">
                <ul class="mobile-menu-nav-list">
                    <li><a href="index.html" class="mobile-menu-link">Home</a></li>
                    <li><a href="latest.html" class="mobile-menu-link">Latest</a></li>
                    <li><a href="trending.html" class="mobile-menu-link">Trending</a></li>
                    <li><a href="bollywood.html" class="mobile-menu-link">Bollywood</a></li>
                    <li><a href="hollywood.html" class="mobile-menu-link">Hollywood</a></li>
                    <li><a href="entertainment.html" class="mobile-menu-link">Entertainment</a></li>
                    <li><a href="technology.html" class="mobile-menu-link">Technology</a></li>
                    <li><a href="gaming.html" class="mobile-menu-link">Gaming</a></li>
                    <li><a href="business.html" class="mobile-menu-link">Business</a></li>
                    <li><a href="sports.html" class="mobile-menu-link">Sports</a></li>
                    <li><a href="about.html" class="mobile-menu-link">About</a></li>
                    <li><a href="contact.html" class="mobile-menu-link">Contact</a></li>
                </ul>
            </div>
            <button class="mobile-menu-close">&times;</button>
        </div>
        <div class="mobile-menu-actions">
            <a href="#" class="mobile-menu-action" onclick="toggleTheme()">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="5"/>
                    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                </svg>
                <span>Theme</span>
            </a>
            <a href="#" class="mobile-menu-action" onclick="openSearch()">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="m21 21-4.35-4.35"/>
                </svg>
                <span>Search</span>
            </a>
            <a href="#" class="mobile-menu-action" onclick="openBookmarks()">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                </svg>
                <span>Bookmarks</span>
            </a>
        </div>
    `;
    
    document.body.appendChild(mobileMenu);
    
    // Toggle menu
    mobileMenuToggle.addEventListener('click', () => {
        mobileMenuToggle.classList.toggle('active');
        mobileMenu.classList.toggle('active');
    });
    
    // Close menu
    const closeBtn = mobileMenu.querySelector('.mobile-menu-close');
    closeBtn.addEventListener('click', () => {
        mobileMenuToggle.classList.remove('active');
        mobileMenu.classList.remove('active');
    });
    
    // Close on overlay click
    mobileMenu.addEventListener('click', (e) => {
        if (e.target === mobileMenu) {
            mobileMenuToggle.classList.remove('active');
            mobileMenu.classList.remove('active');
        }
    });
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    
    if (mobileMenu) {
        mobileMenu.classList.remove('active');
    }
}

// ============================================
// Search
// ============================================

let searchModal;
let searchInput;
let searchResults;

function initSearch() {
    searchModal = document.getElementById('search-modal');
    searchInput = document.getElementById('search-input');
    searchResults = document.getElementById('search-results');
    
    const searchToggle = document.getElementById('search-toggle');
    const searchForm = document.getElementById('search-form');
    
    if (searchToggle) {
        searchToggle.addEventListener('click', openSearch);
    }
    
    if (searchForm) {
        searchForm.addEventListener('submit', performSearch);
    }
    
    // Handle keyboard shortcut
    document.addEventListener('keydown', (e) => {
        if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            openSearch();
        }
        
        if (e.key === 'Escape' && searchModal && searchModal.classList.contains('active')) {
            closeSearch();
        }
    });
}

function openSearch() {
    if (!searchModal) return;
    
    searchModal.classList.add('active');
    searchInput.focus();
    searchInput.value = '';
    searchResults.innerHTML = '';
    
    // Close other modals
    closeBookmarks();
    closeArticleModal();
}

function closeSearch() {
    if (!searchModal) return;
    
    searchModal.classList.remove('active');
    searchInput.blur();
}

async function performSearch(e) {
    e.preventDefault();
    
    const query = searchInput.value.trim();
    if (!query) {
        searchResults.innerHTML = '';
        return;
    }
    
    // Show loading
    searchResults.innerHTML = '<div class="loading-placeholder"><div class="loading-spinner"></div></div>';
    
    try {
        const results = await DataManager.searchArticles(query, 20);
        
        if (results.length === 0) {
            searchResults.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg><h3>No results found</h3><p>Try a different search term</p></div>';
            return;
        }
        
        // Render results
        searchResults.innerHTML = results.map(article => `
            <div class="search-result-item" onclick="openArticle('${article.id}')">
                <div class="search-result-title">${Utils.escapeHtml(article.title)}</div>
                <div class="search-result-meta">
                    <span>${Utils.escapeHtml(article.source)}</span> • 
                    <span>${Utils.formatDate(article.published_at)}</span>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Search error:', error);
        searchResults.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg><h3>Error</h3><p>Failed to search articles</p></div>';
    }
}

// ============================================
// Bookmarks
// ============================================

let bookmarksModal;
let bookmarksList;
let bookmarkCount;

function initBookmarks() {
    bookmarksModal = document.getElementById('bookmarks-modal');
    bookmarksList = document.getElementById('bookmarks-list');
    bookmarkCount = document.getElementById('bookmark-count');
    
    const bookmarksToggle = document.getElementById('bookmarks-toggle');
    
    if (bookmarksToggle) {
        bookmarksToggle.addEventListener('click', openBookmarks);
    }
    
    // Load and update bookmarks
    updateBookmarkCount();
}

function openBookmarks() {
    if (!bookmarksModal) return;
    
    bookmarksModal.classList.add('active');
    renderBookmarks();
    
    // Close other modals
    closeSearch();
    closeArticleModal();
}

function closeBookmarks() {
    if (!bookmarksModal) return;
    
    bookmarksModal.classList.remove('active');
}

function renderBookmarks() {
    const bookmarks = getBookmarks();
    
    if (bookmarks.length === 0) {
        bookmarksList.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg><h3>No bookmarks yet</h3><p>Start bookmarking articles to save them for later</p></div>';
        return;
    }
    
    bookmarksList.innerHTML = bookmarks.map(bookmark => {
        const article = JSON.parse(bookmark);
        return `
            <div class="bookmark-item">
                ${article.image_url ? `
                    <img src="${Utils.escapeHtml(article.image_url)}" alt="${Utils.escapeHtml(article.title)}" class="bookmark-image" onerror="this.style.display='none'">
                ` : `
                    <div class="bookmark-image" style="background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 24px; height: 24px; color: var(--text-muted);"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/></svg>
                    </div>
                `}
                <div class="bookmark-content">
                    <div class="bookmark-title">${Utils.escapeHtml(article.title)}</div>
                    <div class="bookmark-meta">
                        <span>${Utils.escapeHtml(article.source)}</span> • 
                        <span>${Utils.formatDate(article.published_at)}</span>
                    </div>
                </div>
                <button class="bookmark-remove" onclick="removeBookmark('${article.id}')" title="Remove bookmark">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        `;
    }).join('');
}

function getBookmarks() {
    try {
        return JSON.parse(localStorage.getItem('bookmarks')) || [];
    } catch {
        return [];
    }
}

function addBookmark(article) {
    const bookmarks = getBookmarks();
    const existingIndex = bookmarks.findIndex(b => {
        const bArticle = JSON.parse(b);
        return bArticle.id === article.id;
    });
    
    if (existingIndex === -1) {
        bookmarks.push(JSON.stringify(article));
        localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
        updateBookmarkCount();
        showToast('Article bookmarked!', 'success');
    } else {
        showToast('Already bookmarked', 'info');
    }
}

function removeBookmark(articleId) {
    let bookmarks = getBookmarks();
    bookmarks = bookmarks.filter(b => {
        const bArticle = JSON.parse(b);
        return bArticle.id !== articleId;
    });
    
    localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
    updateBookmarkCount();
    renderBookmarks();
    showToast('Bookmark removed', 'success');
}

function isBookmarked(articleId) {
    const bookmarks = getBookmarks();
    return bookmarks.some(b => {
        const bArticle = JSON.parse(b);
        return bArticle.id === articleId;
    });
}

function updateBookmarkCount() {
    const count = getBookmarks().length;
    if (bookmarkCount) {
        bookmarkCount.textContent = count > 0 ? count : '';
        bookmarkCount.style.display = count > 0 ? 'flex' : 'none';
    }
}

// ============================================
// Modals
// ============================================

let articleModal;

function initModals() {
    articleModal = document.getElementById('article-modal');
    
    // Close modals on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeSearch();
            closeBookmarks();
            closeArticleModal();
        }
    });
    
    // Close modals on overlay click
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        const overlay = modal.querySelector('.modal-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => {
                modal.classList.remove('active');
            });
        }
    });
}

function openArticle(articleId) {
    closeSearch();
    closeBookmarks();
    closeArticleModal();
    
    // Navigate to article detail page
    window.location.href = `article.html?id=${articleId}`;
}

function openArticleModal(article) {
    if (!articleModal) return;
    
    const articleDetail = document.getElementById('article-detail');
    
    articleDetail.innerHTML = `
        <div class="article-header">
            <span class="article-category" style="background-color: ${Utils.getCategoryColor(article.category)}20; color: ${Utils.getCategoryColor(article.category)};">
                ${Utils.escapeHtml(article.category)}
            </span>
            <h1 class="article-title">${Utils.escapeHtml(article.title)}</h1>
            <div class="article-meta">
                <div class="article-meta-item">
                    <svg class="article-meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                    </svg>
                    <span>${Utils.escapeHtml(article.source || 'Unknown')}</span>
                </div>
                <div class="article-meta-item">
                    <svg class="article-meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                        <line x1="16" y1="2" x2="16" y2="6"/>
                        <line x1="8" y1="2" x2="8" y2="6"/>
                        <line x1="3" y1="10" x2="21" y2="10"/>
                    </svg>
                    <span>${Utils.formatDateLong(article.published_at)}</span>
                </div>
                ${article.author ? `
                    <div class="article-meta-item">
                        <svg class="article-meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                            <circle cx="12" cy="7" r="4"/>
                        </svg>
                        <span>${Utils.escapeHtml(article.author)}</span>
                    </div>
                ` : ''}
            </div>
        </div>
        
        ${article.image_url ? `
            <img src="${Utils.escapeHtml(article.image_url)}" alt="${Utils.escapeHtml(article.title)}" class="article-image" onerror="this.style.display='none'">
        ` : ''}
        
        <div class="article-body">
            <p>${Utils.escapeHtml(article.summary || 'No summary available')}</p>
        </div>
        
        <div class="article-footer">
            <div class="article-source">
                <svg class="article-meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
                </svg>
                <span>Source: ${Utils.escapeHtml(Utils.getDomain(article.url))}</span>
            </div>
            <div class="article-actions">
                <button class="article-action-btn ${isBookmarked(article.id) ? 'bookmarked' : ''}" onclick="toggleBookmark('${article.id}')">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                    </svg>
                    <span>Bookmark</span>
                </button>
                <button class="article-action-btn" onclick="shareArticle('${article.id}')">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="18" cy="5" r="3"/>
                        <circle cx="6" cy="12" r="3"/>
                        <circle cx="18" cy="19" r="3"/>
                        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
                        <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                    </svg>
                    <span>Share</span>
                </button>
                <a href="${Utils.escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer" class="article-action-btn">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                        <polyline points="15 3 21 3 21 9"/>
                        <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                    <span>Read Original</span>
                </a>
            </div>
        </div>
    `;
    
    articleModal.classList.add('active');
}

function closeArticleModal() {
    if (!articleModal) return;
    
    articleModal.classList.remove('active');
}

function toggleBookmark(articleId) {
    DataManager.getArticleById(articleId).then(article => {
        if (article) {
            if (isBookmarked(articleId)) {
                removeBookmark(articleId);
            } else {
                addBookmark(article);
            }
            // Update button state
            const buttons = document.querySelectorAll(`.article-action-btn.bookmark-${articleId}`);
            buttons.forEach(btn => {
                btn.classList.toggle('bookmarked');
            });
        }
    });
}

async function shareArticle(articleId) {
    const article = await DataManager.getArticleById(articleId);
    if (!article) return;
    
    const shareData = {
        title: article.title,
        text: article.summary,
        url: article.url
    };
    
    try {
        await Utils.share(shareData);
        showToast('Article shared!', 'success');
    } catch (error) {
        await Utils.copyToClipboard(article.url);
        showToast('Link copied to clipboard!', 'success');
    }
}

// ============================================
// Scroll Management
// ============================================

function initScroll() {
    const header = document.querySelector('.header');
    
    window.addEventListener('scroll', Utils.throttle(() => {
        // Add scrolled class to header
        if (window.scrollY > 10) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
        
        // Show/hide back to top button
        const backToTop = document.getElementById('back-to-top');
        if (backToTop) {
            if (window.scrollY > 300) {
                backToTop.classList.add('visible');
            } else {
                backToTop.classList.remove('visible');
            }
        }
    }, 100));
}

function initBackToTop() {
    const backToTop = document.getElementById('back-to-top');
    if (backToTop) {
        backToTop.addEventListener('click', Utils.scrollToTop);
    }
}

// ============================================
// Toast Notifications
// ============================================

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };
    
    toast.innerHTML = `
        <div class="toast-icon">${icons[type]}</div>
        <div class="toast-message">${Utils.escapeHtml(message)}</div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================
// Page Data Loading
// ============================================

async function loadPageData() {
    // Load category counts
    loadCategoryCounts();
    
    // Load last updated
    loadLastUpdated();
    
    // Load featured news (latest 5)
    loadFeaturedNews();
    
    // Load latest news
    loadLatestNews();
    
    // Load trending news
    loadTrendingNews();
    
    // Load category news
    loadCategoryNews();
}

async function loadCategoryCounts() {
    try {
        const counts = await DataManager.getCategoryCounts();
        const categories = ['bollywood', 'hollywood', 'entertainment', 'technology', 'gaming', 'business', 'sports', 'trending'];
        
        categories.forEach(category => {
            const countEl = document.getElementById(`${category}-count`);
            if (countEl) {
                countEl.textContent = counts[category] || 0;
            }
        });
    } catch (error) {
        console.error('Error loading category counts:', error);
    }
}

async function loadLastUpdated() {
    try {
        const lastUpdated = await DataManager.getLastUpdated();
        const lastUpdatedEl = document.getElementById('last-updated');
        if (lastUpdatedEl && lastUpdated) {
            lastUpdatedEl.textContent = lastUpdated.toLocaleString();
        }
    } catch (error) {
        console.error('Error loading last updated:', error);
    }
}

async function loadFeaturedNews() {
    const featuredNewsEl = document.getElementById('featured-news');
    if (!featuredNewsEl) return;
    
    try {
        const articles = await DataManager.loadLatestArticles(5);
        
        if (articles.length === 0) {
            Utils.showEmpty(featuredNewsEl, 'No featured articles yet');
            return;
        }
        
        featuredNewsEl.innerHTML = articles.map((article, index) => `
            <div class="news-card featured-card" style="--category-color: ${Utils.getCategoryColor(article.category)}">
                <div class="news-card-image">
                    ${article.image_url ? `
                        <img src="${Utils.escapeHtml(article.image_url)}" alt="${Utils.escapeHtml(article.title)}" loading="lazy" onerror="this.parentNode.innerHTML='<div class=\"news-card-placeholder\"><svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><rect x=\"3\" y=\"3\" width=\"18\" height=\"18\" rx=\"2\"/><path d=\"M9 9h6v6H9z\"/></svg></div>'">
                    ` : `
                        <div class="news-card-placeholder">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="3" width="18" height="18" rx="2"/>
                                <path d="M9 9h6v6H9z"/>
                            </svg>
                        </div>
                    `}
                    <span class="news-card-category" style="background-color: var(--category-color);">${Utils.escapeHtml(article.category)}</span>
                </div>
                <div class="news-card-content">
                    <h3 class="news-card-title">${Utils.escapeHtml(article.title)}</h3>
                    <p class="news-card-summary">${Utils.escapeHtml(Utils.truncate(article.summary, 100))}</p>
                    <div class="news-card-meta">
                        <span class="news-card-source">${Utils.escapeHtml(article.source)}</span>
                        <span class="news-card-time">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px;">
                                <circle cx="12" cy="12" r="10"/>
                                <polyline points="12 6 12 12 16 14"/>
                            </svg>
                            ${Utils.formatDate(article.published_at)}
                        </span>
                    </div>
                    <div class="news-card-actions">
                        <button class="news-card-action" onclick="openArticle('${article.id}')">
                            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M5 12h14M12 5l7 7-7 7"/>
                            </svg>
                            <span>Read</span>
                        </button>
                        <button class="news-card-action" onclick="toggleBookmark('${article.id}')">
                            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading featured news:', error);
        Utils.showError(featuredNewsEl, 'Failed to load featured news');
    }
}

async function loadLatestNews() {
    const latestNewsEl = document.getElementById('latest-news');
    if (!latestNewsEl) return;
    
    try {
        const articles = await DataManager.loadLatestArticles(12);
        
        if (articles.length === 0) {
            Utils.showEmpty(latestNewsEl, 'No latest articles yet');
            return;
        }
        
        latestNewsEl.innerHTML = articles.map(article => `
            <div class="news-card" style="--category-color: ${Utils.getCategoryColor(article.category)}">
                <div class="news-card-image">
                    ${article.image_url ? `
                        <img src="${Utils.escapeHtml(article.image_url)}" alt="${Utils.escapeHtml(article.title)}" loading="lazy" onerror="this.parentNode.innerHTML='<div class=\"news-card-placeholder\"><svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><rect x=\"3\" y=\"3\" width=\"18\" height=\"18\" rx=\"2\"/><path d=\"M9 9h6v6H9z\"/></svg></div>'">
                    ` : `
                        <div class="news-card-placeholder">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="3" width="18" height="18" rx="2"/>
                                <path d="M9 9h6v6H9z"/>
                            </svg>
                        </div>
                    `}
                    <span class="news-card-category" style="background-color: var(--category-color);">${Utils.escapeHtml(article.category)}</span>
                </div>
                <div class="news-card-content">
                    <h3 class="news-card-title">${Utils.escapeHtml(article.title)}</h3>
                    <p class="news-card-summary">${Utils.escapeHtml(Utils.truncate(article.summary, 100))}</p>
                    <div class="news-card-meta">
                        <span class="news-card-source">${Utils.escapeHtml(article.source)}</span>
                        <span class="news-card-time">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px;">
                                <circle cx="12" cy="12" r="10"/>
                                <polyline points="12 6 12 12 16 14"/>
                            </svg>
                            ${Utils.formatDate(article.published_at)}
                        </span>
                    </div>
                    <div class="news-card-actions">
                        <button class="news-card-action" onclick="openArticle('${article.id}')">
                            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M5 12h14M12 5l7 7-7 7"/>
                            </svg>
                            <span>Read</span>
                        </button>
                        <button class="news-card-action" onclick="toggleBookmark('${article.id}')">
                            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading latest news:', error);
        Utils.showError(latestNewsEl, 'Failed to load latest news');
    }
}

async function loadTrendingNews() {
    const trendingNewsEl = document.getElementById('trending-news');
    if (!trendingNewsEl) return;
    
    try {
        const articles = await DataManager.loadTrendingArticles(12);
        
        if (articles.length === 0) {
            Utils.showEmpty(trendingNewsEl, 'No trending articles yet');
            return;
        }
        
        trendingNewsEl.innerHTML = articles.map(article => `
            <div class="news-card" style="--category-color: ${Utils.getCategoryColor(article.category)}">
                <div class="news-card-image">
                    ${article.image_url ? `
                        <img src="${Utils.escapeHtml(article.image_url)}" alt="${Utils.escapeHtml(article.title)}" loading="lazy" onerror="this.parentNode.innerHTML='<div class=\"news-card-placeholder\"><svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><rect x=\"3\" y=\"3\" width=\"18\" height=\"18\" rx=\"2\"/><path d=\"M9 9h6v6H9z\"/></svg></div>'">
                    ` : `
                        <div class="news-card-placeholder">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M20.44 19.44L12 13.5l-8.44 5.94a1 1 0 0 0 1.28 1.56L12 16.5l7.16 4.5a1 1 0 0 0 1.28-1.56z"/>
                                <path d="M12 5v11"/>
                            </svg>
                        </div>
                    `}
                    <span class="news-card-category" style="background-color: var(--category-color);">${Utils.escapeHtml(article.category)}</span>
                </div>
                <div class="news-card-content">
                    <h3 class="news-card-title">${Utils.escapeHtml(article.title)}</h3>
                    <p class="news-card-summary">${Utils.escapeHtml(Utils.truncate(article.summary, 100))}</p>
                    <div class="news-card-meta">
                        <span class="news-card-source">${Utils.escapeHtml(article.source)}</span>
                        <span class="news-card-time">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px;">
                                <circle cx="12" cy="12" r="10"/>
                                <polyline points="12 6 12 12 16 14"/>
                            </svg>
                            ${Utils.formatDate(article.published_at)}
                        </span>
                    </div>
                    <div class="news-card-actions">
                        <button class="news-card-action" onclick="openArticle('${article.id}')">
                            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M5 12h14M12 5l7 7-7 7"/>
                            </svg>
                            <span>Read</span>
                        </button>
                        <button class="news-card-action" onclick="toggleBookmark('${article.id}')">
                            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading trending news:', error);
        Utils.showError(trendingNewsEl, 'Failed to load trending news');
    }
}

async function loadCategoryNews() {
    const categories = ['bollywood', 'hollywood', 'technology', 'gaming', 'business', 'sports'];
    
    for (const category of categories) {
        const newsEl = document.getElementById(`${category}-news`);
        if (!newsEl) continue;
        
        try {
            const articles = await DataManager.loadCategoryArticles(category, 6);
            
            if (articles.length === 0) {
                Utils.showEmpty(newsEl, `No ${category} articles yet`);
                continue;
            }
            
            newsEl.innerHTML = articles.map(article => `
                <div class="news-card" style="--category-color: ${Utils.getCategoryColor(article.category)}">
                    <div class="news-card-image">
                        ${article.image_url ? `
                            <img src="${Utils.escapeHtml(article.image_url)}" alt="${Utils.escapeHtml(article.title)}" loading="lazy" onerror="this.parentNode.innerHTML='<div class=\"news-card-placeholder\"><svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><rect x=\"3\" y=\"3\" width=\"18\" height=\"18\" rx=\"2\"/><path d=\"M9 9h6v6H9z\"/></svg></div>'">
                        ` : `
                            <div class="news-card-placeholder">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                                    <path d="M9 9h6v6H9z"/>
                                </svg>
                            </div>
                        `}
                        <span class="news-card-category" style="background-color: var(--category-color);">${Utils.escapeHtml(article.category)}</span>
                    </div>
                    <div class="news-card-content">
                        <h3 class="news-card-title">${Utils.escapeHtml(article.title)}</h3>
                        <p class="news-card-summary">${Utils.escapeHtml(Utils.truncate(article.summary, 80))}</p>
                        <div class="news-card-meta">
                            <span class="news-card-source">${Utils.escapeHtml(article.source)}</span>
                            <span class="news-card-time">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px;">
                                    <circle cx="12" cy="12" r="10"/>
                                    <polyline points="12 6 12 12 16 14"/>
                                </svg>
                                ${Utils.formatDate(article.published_at)}
                            </span>
                        </div>
                        <div class="news-card-actions">
                            <button class="news-card-action" onclick="openArticle('${article.id}')">
                                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M5 12h14M12 5l7 7-7 7"/>
                                </svg>
                                <span>Read</span>
                            </button>
                            <button class="news-card-action" onclick="toggleBookmark('${article.id}')">
                                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
            
        } catch (error) {
            console.error(`Error loading ${category} news:`, error);
            Utils.showError(newsEl, `Failed to load ${category} news`);
        }
    }
}

// ============================================
// Newsletter Form
// ============================================

function initNewsletter() {
    const newsletterForm = document.getElementById('newsletter-form');
    if (!newsletterForm) return;
    
    newsletterForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = document.getElementById('newsletter-email').value;
        
        if (!email) {
            showToast('Please enter your email', 'error');
            return;
        }
        
        // No mailing backend is wired up yet - never claim a subscription that did not happen
        showToast('Newsletter is not live yet - nothing was stored. All headlines are right here on the homepage.', 'info');
        newsletterForm.reset();
    });
}

// Initialize newsletter form
initNewsletter();

// ============================================
// Export for other modules
// ============================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        openArticle,
        openArticleModal,
        closeArticleModal,
        openSearch,
        closeSearch,
        openBookmarks,
        closeBookmarks,
        addBookmark,
        removeBookmark,
        isBookmarked,
        showToast,
        loadPageData
    };
}
