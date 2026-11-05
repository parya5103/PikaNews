// PikaNews Data Module
// Handles loading and managing news data from JSON files

const DataManager = {
    // Base URL for data files
    baseUrl: '/PikaNews/data',
    
    // Cache for loaded data
    cache: {
        allArticles: null,
        latestArticles: null,
        categoryArticles: {},
        trendingArticles: null,
        stats: null
    },
    
    // Initialize the data manager
    init() {
        this.baseUrl = window.location.pathname.includes('/PikaNews') ? '/PikaNews/data' : '/data';
    },
    
    // Load all articles
    async loadAllArticles(forceRefresh = false) {
        if (this.cache.allArticles && !forceRefresh) {
            return this.cache.allArticles;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/all_articles.json`);
            if (!response.ok) {
                console.warn('Failed to load all articles, trying fallback...');
                // Try without /PikaNews prefix
                const fallbackResponse = await fetch('/data/all_articles.json');
                if (fallbackResponse.ok) {
                    this.cache.allArticles = await fallbackResponse.json();
                } else {
                    // Try with news_json directory
                    const newsJsonResponse = await fetch('/PikaNews/news_json/all_articles.json');
                    if (newsJsonResponse.ok) {
                        this.cache.allArticles = await newsJsonResponse.json();
                    } else {
                        this.cache.allArticles = [];
                    }
                }
            } else {
                this.cache.allArticles = await response.json();
            }
        } catch (error) {
            console.error('Error loading all articles:', error);
            this.cache.allArticles = [];
        }
        
        return this.cache.allArticles;
    },
    
    // Load latest articles
    async loadLatestArticles(limit = 20, forceRefresh = false) {
        if (this.cache.latestArticles && !forceRefresh) {
            return this.cache.latestArticles;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/latest.json`);
            if (!response.ok) {
                // Fallback to all articles
                const allArticles = await this.loadAllArticles();
                this.cache.latestArticles = allArticles.slice(0, limit);
            } else {
                let articles = await response.json();
                this.cache.latestArticles = articles.slice(0, limit);
            }
        } catch (error) {
            console.error('Error loading latest articles:', error);
            const allArticles = await this.loadAllArticles();
            this.cache.latestArticles = allArticles.slice(0, limit);
        }
        
        return this.cache.latestArticles;
    },
    
    // Load articles by category
    async loadCategoryArticles(category, limit = 20, forceRefresh = false) {
        if (this.cache.categoryArticles[category] && !forceRefresh) {
            return this.cache.categoryArticles[category];
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/${category}.json`);
            if (!response.ok) {
                // Fallback: filter all articles by category
                const allArticles = await this.loadAllArticles();
                this.cache.categoryArticles[category] = allArticles
                    .filter(a => a.category === category)
                    .slice(0, limit);
            } else {
                let articles = await response.json();
                this.cache.categoryArticles[category] = articles.slice(0, limit);
            }
        } catch (error) {
            console.error(`Error loading ${category} articles:`, error);
            const allArticles = await this.loadAllArticles();
            this.cache.categoryArticles[category] = allArticles
                .filter(a => a.category === category)
                .slice(0, limit);
        }
        
        return this.cache.categoryArticles[category];
    },
    
    // Load trending articles (most recent)
    async loadTrendingArticles(limit = 10, forceRefresh = false) {
        if (this.cache.trendingArticles && !forceRefresh) {
            return this.cache.trendingArticles;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/trending.json`);
            if (!response.ok) {
                // Fallback: get most recent articles
                const allArticles = await this.loadAllArticles();
                this.cache.trendingArticles = allArticles
                    .sort((a, b) => new Date(b.published_at) - new Date(a.published_at))
                    .slice(0, limit);
            } else {
                this.cache.trendingArticles = await response.json();
            }
        } catch (error) {
            console.error('Error loading trending articles:', error);
            const allArticles = await this.loadAllArticles();
            this.cache.trendingArticles = allArticles
                .sort((a, b) => new Date(b.published_at) - new Date(a.published_at))
                .slice(0, limit);
        }
        
        return this.cache.trendingArticles;
    },
    
    // Load stats
    async loadStats(forceRefresh = false) {
        if (this.cache.stats && !forceRefresh) {
            return this.cache.stats;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/stats.json`);
            if (response.ok) {
                this.cache.stats = await response.json();
            } else {
                this.cache.stats = { total: 0, by_category: {} };
            }
        } catch (error) {
            console.error('Error loading stats:', error);
            this.cache.stats = { total: 0, by_category: {} };
        }
        
        return this.cache.stats;
    },
    
    // Search articles
    async searchArticles(query, limit = 20) {
        const allArticles = await this.loadAllArticles();
        const lowerQuery = query.toLowerCase();
        
        return allArticles
            .filter(article => 
                article.title.toLowerCase().includes(lowerQuery) ||
                article.summary.toLowerCase().includes(lowerQuery) ||
                (article.source && article.source.toLowerCase().includes(lowerQuery)) ||
                (article.category && article.category.toLowerCase().includes(lowerQuery))
            )
            .slice(0, limit);
    },
    
    // Get article by ID
    async getArticleById(id) {
        const allArticles = await this.loadAllArticles();
        return allArticles.find(a => a.id === id);
    },
    
    // Get related articles
    async getRelatedArticles(articleId, category, limit = 5) {
        const allArticles = await this.loadAllArticles();
        return allArticles
            .filter(a => a.id !== articleId && a.category === category)
            .sort((a, b) => new Date(b.published_at) - new Date(a.published_at))
            .slice(0, limit);
    },
    
    // Get article count by category
    async getCategoryCounts() {
        const allArticles = await this.loadAllArticles();
        const counts = {};
        allArticles.forEach(a => {
            counts[a.category] = (counts[a.category] || 0) + 1;
        });
        return counts;
    },
    
    // Get last updated timestamp
    async getLastUpdated() {
        const allArticles = await this.loadAllArticles();
        if (allArticles.length === 0) return null;
        
        const collectionTimestamps = allArticles
            .map(a => a.collection_timestamp)
            .filter(ts => ts);
        
        if (collectionTimestamps.length === 0) return null;
        
        return new Date(Math.max(...collectionTimestamps.map(ts => new Date(ts).getTime())));
    },
    
    // Clear cache
    clearCache() {
        this.cache = {
            allArticles: null,
            latestArticles: null,
            categoryArticles: {},
            trendingArticles: null,
            stats: null
        };
    }
};

// Initialize on module load
DataManager.init();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DataManager;
}
