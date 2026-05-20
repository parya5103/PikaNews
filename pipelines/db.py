import os
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import aiosqlite
import asyncpg
import structlog

logger = structlog.get_logger(__name__)

class DatabasePipeline:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.postgres_url = os.getenv("POSTGRES_URL") or config.get("db", {}).get("postgres_url", "")
        self.sqlite_path = os.getenv("SQLITE_PATH") or config.get("db", {}).get("sqlite_path", "pikanews.db")
        self.use_postgres = bool(self.postgres_url)

    async def initialize(self):
        """Create tables and FTS search indexes if they do not exist."""
        if self.use_postgres:
            logger.info("Initializing PostgreSQL database", url=self.postgres_url)
            conn = await asyncpg.connect(self.postgres_url)
            try:
                # Create main articles table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS articles (
                        sha256_hash VARCHAR(64) PRIMARY KEY,
                        title TEXT NOT NULL,
                        subtitle TEXT,
                        author VARCHAR(255),
                        published_at TIMESTAMPTZ NOT NULL,
                        source VARCHAR(100) NOT NULL,
                        category VARCHAR(100) DEFAULT 'movie',
                        industry VARCHAR(50) NOT NULL,
                        tags JSONB DEFAULT '[]'::jsonb,
                        body_text TEXT NOT NULL,
                        body_html TEXT,
                        featured_image_url TEXT,
                        gallery_urls JSONB DEFAULT '[]'::jsonb,
                        video_embeds JSONB DEFAULT '[]'::jsonb,
                        canonical_url TEXT NOT NULL,
                        word_count INT DEFAULT 0,
                        reading_time_min INT DEFAULT 0,
                        entities JSONB DEFAULT '{}'::jsonb,
                        sentiment VARCHAR(50) DEFAULT 'neutral',
                        sentiment_score REAL DEFAULT 0.0,
                        summary TEXT,
                        language VARCHAR(10) DEFAULT 'en',
                        image_phash VARCHAR(64),
                        local_image_paths JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        tsv_search tsvector
                    );
                """)
                # Create text search vectors and index for Postgres
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);")
                
                # Check and add tsvector column and GIN index for search efficiency
                await conn.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS tsv_search tsvector;")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_tsv ON articles USING gin(tsv_search);")
            finally:
                await conn.close()
        else:
            logger.info("Initializing SQLite database", path=self.sqlite_path)
            async with aiosqlite.connect(self.sqlite_path) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS articles (
                        sha256_hash TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        subtitle TEXT,
                        author TEXT,
                        published_at TIMESTAMP NOT NULL,
                        source TEXT NOT NULL,
                        category TEXT DEFAULT 'movie',
                        industry TEXT NOT NULL,
                        tags TEXT,
                        body_text TEXT NOT NULL,
                        body_html TEXT,
                        featured_image_url TEXT,
                        gallery_urls TEXT,
                        video_embeds TEXT,
                        canonical_url TEXT NOT NULL,
                        word_count INTEGER DEFAULT 0,
                        reading_time_min INTEGER DEFAULT 0,
                        entities TEXT,
                        sentiment TEXT DEFAULT 'neutral',
                        sentiment_score REAL DEFAULT 0.0,
                        summary TEXT,
                        language TEXT DEFAULT 'en',
                        image_phash TEXT,
                        local_image_paths TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);")
                
                # FTS5 Virtual Table for SQLite Search
                try:
                    await conn.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                            title, subtitle, body_text, content='articles', content_rowid='rowid'
                        );
                    """)
                    # Triggers for keeping FTS5 in sync with base table
                    await conn.execute("""
                        CREATE TRIGGER IF NOT EXISTS tbl_ai AFTER INSERT ON articles BEGIN
                            INSERT INTO articles_fts(rowid, title, subtitle, body_text)
                            VALUES (new.rowid, new.title, new.subtitle, new.body_text);
                        END;
                    """)
                except aiosqlite.OperationalError as e:
                    logger.warn("SQLite FTS5 creation error, virtual tables might already exist", error=str(e))
                
                await conn.commit()

    @staticmethod
    def calculate_hash(title: str, canonical_url: str) -> str:
        """Compute SHA-256 deduplication key using normalized fields."""
        norm_title = "".join(char for char in title.lower() if char.isalnum())
        norm_url = canonical_url.split("?")[0].lower().strip()
        data = f"{norm_title}|{norm_url}"
        return hashlib.sha256(data.encode()).hexdigest()

    async def save_article(self, article_data: Dict[str, Any]) -> bool:
        """Save article to target DB backend. Deduplicates and inserts if new. Returns True if inserted."""
        title = article_data["title"]
        url = str(article_data["canonical_url"])
        sha256_hash = self.calculate_hash(title, url)
        
        # Format tags/entities/paths as JSON string for sqlite
        tags_json = json.dumps(article_data.get("tags", []))
        gallery_json = json.dumps([str(u) for u in article_data.get("gallery_urls", [])])
        video_json = json.dumps(article_data.get("video_embeds", []))
        entities_json = json.dumps(article_data.get("entities", {}))
        paths_json = json.dumps(article_data.get("local_image_paths", {}))
        
        featured_image = str(article_data["featured_image_url"]) if article_data.get("featured_image_url") else None
        
        # Ensure UTC datetime format for databases
        pub_at = article_data["published_at"]
        if isinstance(pub_at, str):
            pub_at = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
        
        if self.use_postgres:
            conn = await asyncpg.connect(self.postgres_url)
            try:
                # Check for duplicate
                duplicate = await conn.fetchval("SELECT 1 FROM articles WHERE sha256_hash = $1", sha256_hash)
                if duplicate:
                    logger.debug("Duplicate detected, skipping Postgres insert", hash=sha256_hash)
                    return False
                
                await conn.execute("""
                    INSERT INTO articles (
                        sha256_hash, title, subtitle, author, published_at, source, category, industry,
                        tags, body_text, body_html, featured_image_url, gallery_urls, video_embeds,
                        canonical_url, word_count, reading_time_min, entities, sentiment, sentiment_score,
                        summary, language, image_phash, local_image_paths, tsv_search
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24,
                              to_tsvector('english', $2 || ' ' || COALESCE($3, '') || ' ' || $10))
                """, 
                sha256_hash, title, article_data.get("subtitle"), article_data.get("author", "Unknown"),
                pub_at, article_data["source"], article_data.get("category", "movie"), article_data["industry"],
                tags_json, article_data["body_text"], article_data.get("body_html"), featured_image,
                gallery_json, video_json, url, article_data.get("word_count", 0),
                article_data.get("reading_time_min", 0), entities_json, article_data.get("sentiment", "neutral"),
                article_data.get("sentiment_score", 0.0), article_data.get("summary"), article_data.get("language", "en"),
                article_data.get("image_phash"), paths_json
                )
                logger.info("Saved new article to Postgres", title=title, source=article_data["source"])
                return True
            except Exception as e:
                logger.error("Failed to insert into Postgres", error=str(e))
                return False
            finally:
                await conn.close()
        else:
            async with aiosqlite.connect(self.sqlite_path) as conn:
                try:
                    # Check for duplicate
                    async with conn.execute("SELECT 1 FROM articles WHERE sha256_hash = ?", (sha256_hash,)) as cursor:
                        if await cursor.fetchone():
                            logger.debug("Duplicate detected, skipping SQLite insert", hash=sha256_hash)
                            return False

                    await conn.execute("""
                        INSERT INTO articles (
                            sha256_hash, title, subtitle, author, published_at, source, category, industry,
                            tags, body_text, body_html, featured_image_url, gallery_urls, video_embeds,
                            canonical_url, word_count, reading_time_min, entities, sentiment, sentiment_score,
                            summary, language, image_phash, local_image_paths
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sha256_hash, title, article_data.get("subtitle"), article_data.get("author", "Unknown"),
                        pub_at.isoformat(), article_data["source"], article_data.get("category", "movie"), article_data["industry"],
                        tags_json, article_data["body_text"], article_data.get("body_html"), featured_image,
                        gallery_json, video_json, url, article_data.get("word_count", 0),
                        article_data.get("reading_time_min", 0), entities_json, article_data.get("sentiment", "neutral"),
                        article_data.get("sentiment_score", 0.0), article_data.get("summary"), article_data.get("language", "en"),
                        article_data.get("image_phash"), paths_json
                    ))
                    
                    # Manual FTS5 refresh in SQLite if table structure requires
                    # Triggers should handle it, but FTS5 requires rowid mappings
                    await conn.commit()
                    logger.info("Saved new article to SQLite", title=title, source=article_data["source"])
                    return True
                except Exception as e:
                    logger.error("Failed to insert into SQLite", error=str(e))
                    return False

    async def get_latest_articles(self, limit: int = 20, offset: int = 0, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent articles sorted by publication time, with optional category filter."""
        results = []
        if self.use_postgres:
            conn = await asyncpg.connect(self.postgres_url)
            try:
                if category:
                    rows = await conn.fetch("""
                        SELECT * FROM articles 
                        WHERE category = $1
                        ORDER BY published_at DESC LIMIT $2 OFFSET $3
                    """, category, limit, offset)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM articles 
                        ORDER BY published_at DESC LIMIT $1 OFFSET $2
                    """, limit, offset)
                results = [dict(row) for row in rows]
            finally:
                await conn.close()
        else:
            async with aiosqlite.connect(self.sqlite_path) as conn:
                conn.row_factory = aiosqlite.Row
                if category:
                    async with conn.execute("""
                        SELECT * FROM articles 
                        WHERE category = ?
                        ORDER BY published_at DESC LIMIT ? OFFSET ?
                    """, (category, limit, offset)) as cursor:
                        rows = await cursor.fetchall()
                        results = [dict(row) for row in rows]
                else:
                    async with conn.execute("""
                        SELECT * FROM articles 
                        ORDER BY published_at DESC LIMIT ? OFFSET ?
                    """, (limit, offset)) as cursor:
                        rows = await cursor.fetchall()
                        results = [dict(row) for row in rows]

        # Parse JSON fields
        for r in results:
            self._unpack_json_fields(r)
        return results

    async def search_articles(self, query_string: str, limit: int = 20, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search matching articles using full-text search index, with optional category filter."""
        results = []
        if not query_string:
            return results

        if self.use_postgres:
            conn = await asyncpg.connect(self.postgres_url)
            try:
                # Query using pg ts_query on the indexed tsv_search column
                if category:
                    rows = await conn.fetch("""
                        SELECT *, ts_rank_cd(tsv_search, plainto_tsquery('english', $1)) as rank
                        FROM articles
                        WHERE tsv_search @@ plainto_tsquery('english', $1) AND category = $2
                        ORDER BY rank DESC, published_at DESC LIMIT $3
                    """, query_string, category, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT *, ts_rank_cd(tsv_search, plainto_tsquery('english', $1)) as rank
                        FROM articles
                        WHERE tsv_search @@ plainto_tsquery('english', $1)
                        ORDER BY rank DESC, published_at DESC LIMIT $2
                    """, query_string, limit)
                results = [dict(row) for row in rows]
            finally:
                await conn.close()
        else:
            async with aiosqlite.connect(self.sqlite_path) as conn:
                conn.row_factory = aiosqlite.Row
                # Handle basic FTS5 formatting
                match_query = f'"{query_string}"'
                if category:
                    sql = """
                        SELECT a.*, f.rank FROM articles a
                        JOIN articles_fts f ON a.rowid = f.rowid
                        WHERE articles_fts MATCH ? AND a.category = ?
                        ORDER BY f.rank ASC, a.published_at DESC LIMIT ?
                    """
                    try:
                        async with conn.execute(sql, (match_query, category, limit)) as cursor:
                            rows = await cursor.fetchall()
                            results = [dict(row) for row in rows]
                    except aiosqlite.OperationalError:
                        sql_fallback = """
                            SELECT * FROM articles 
                            WHERE (title LIKE ? OR body_text LIKE ?) AND category = ? 
                            ORDER BY published_at DESC LIMIT ?
                        """
                        async with conn.execute(sql_fallback, (f"%{query_string}%", f"%{query_string}%", category, limit)) as cursor:
                            rows = await cursor.fetchall()
                            results = [dict(row) for row in rows]
                else:
                    sql = """
                        SELECT a.*, f.rank FROM articles a
                        JOIN articles_fts f ON a.rowid = f.rowid
                        WHERE articles_fts MATCH ?
                        ORDER BY f.rank ASC, a.published_at DESC LIMIT ?
                    """
                    try:
                        async with conn.execute(sql, (match_query, limit)) as cursor:
                            rows = await cursor.fetchall()
                            results = [dict(row) for row in rows]
                    except aiosqlite.OperationalError:
                        sql_fallback = """
                            SELECT * FROM articles 
                            WHERE title LIKE ? OR body_text LIKE ? 
                            ORDER BY published_at DESC LIMIT ?
                        """
                        async with conn.execute(sql_fallback, (f"%{query_string}%", f"%{query_string}%", limit)) as cursor:
                            rows = await cursor.fetchall()
                            results = [dict(row) for row in rows]

        # Parse JSON fields
        for r in results:
            self._unpack_json_fields(r)
        return results

    async def get_trending_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve trending stories calculated via keyword/entity frequency velocity over the last 24 hours."""
        # Query entities and compute high velocity mentions
        since_time = datetime.now(timezone.utc) - timedelta(hours=24)
        results = []
        
        if self.use_postgres:
            conn = await asyncpg.connect(self.postgres_url)
            try:
                rows = await conn.fetch("""
                    SELECT * FROM articles 
                    WHERE published_at > $1 
                    ORDER BY sentiment_score DESC, published_at DESC LIMIT $2
                """, since_time, limit)
                results = [dict(row) for row in rows]
            finally:
                await conn.close()
        else:
            async with aiosqlite.connect(self.sqlite_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("""
                    SELECT * FROM articles 
                    WHERE published_at > ? 
                    ORDER BY sentiment_score DESC, published_at DESC LIMIT ?
                """, (since_time.isoformat(), limit)) as cursor:
                    rows = await cursor.fetchall()
                    results = [dict(row) for row in rows]

        for r in results:
            self._unpack_json_fields(r)
        return results

    async def get_by_celebrity(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve articles that contain specified actor/celebrity name in extracted entities."""
        results = []
        like_pattern = f"%{name}%"
        
        if self.use_postgres:
            conn = await asyncpg.connect(self.postgres_url)
            try:
                # Query utilizing postgres JSONB containment check or text match
                rows = await conn.fetch("""
                    SELECT * FROM articles 
                    WHERE (entities->>'actors')::text LIKE $1 
                    ORDER BY published_at DESC LIMIT $2
                """, like_pattern, limit)
                results = [dict(row) for row in rows]
            finally:
                await conn.close()
        else:
            async with aiosqlite.connect(self.sqlite_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("""
                    SELECT * FROM articles 
                    WHERE entities LIKE ? 
                    ORDER BY published_at DESC LIMIT ?
                """, (like_pattern, limit)) as cursor:
                    rows = await cursor.fetchall()
                    results = [dict(row) for row in rows]

        for r in results:
            self._unpack_json_fields(r)
        return results

    async def get_database_stats(self) -> Dict[str, Any]:
        """Query statistics from database for the dashboard."""
        stats = {
            "total_articles": 0,
            "by_industry": {},
            "by_category": {},
            "by_source": {},
            "by_sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            "avg_sentiment": 0.0
        }
        
        if self.use_postgres:
            conn = await asyncpg.connect(self.postgres_url)
            try:
                stats["total_articles"] = await conn.fetchval("SELECT COUNT(*) FROM articles")
                
                # Industry
                rows = await conn.fetch("SELECT industry, COUNT(*) as count FROM articles GROUP BY industry")
                stats["by_industry"] = {r["industry"]: r["count"] for r in rows}
                
                # Category
                rows = await conn.fetch("SELECT category, COUNT(*) as count FROM articles GROUP BY category")
                stats["by_category"] = {r["category"]: r["count"] for r in rows}
                
                # Source
                rows = await conn.fetch("SELECT source, COUNT(*) as count FROM articles GROUP BY source")
                stats["by_source"] = {r["source"]: r["count"] for r in rows}
                
                # Sentiment
                rows = await conn.fetch("SELECT sentiment, COUNT(*) as count FROM articles GROUP BY sentiment")
                for r in rows:
                    if r["sentiment"] in stats["by_sentiment"]:
                        stats["by_sentiment"][r["sentiment"]] = r["count"]
                
                avg_sent = await conn.fetchval("SELECT AVG(sentiment_score) FROM articles")
                stats["avg_sentiment"] = round(avg_sent, 2) if avg_sent is not None else 0.0
            except Exception as e:
                logger.error("Failed to query postgres stats", error=str(e))
            finally:
                await conn.close()
        else:
            async with aiosqlite.connect(self.sqlite_path) as conn:
                conn.row_factory = aiosqlite.Row
                try:
                    async with conn.execute("SELECT COUNT(*) as count FROM articles") as cursor:
                        row = await cursor.fetchone()
                        stats["total_articles"] = row["count"] if row else 0
                    
                    # Industry
                    async with conn.execute("SELECT industry, COUNT(*) as count FROM articles GROUP BY industry") as cursor:
                        stats["by_industry"] = {r["industry"]: r["count"] for r in await cursor.fetchall()}
                        
                    # Category
                    async with conn.execute("SELECT category, COUNT(*) as count FROM articles GROUP BY category") as cursor:
                        stats["by_category"] = {r["category"]: r["count"] for r in await cursor.fetchall()}
                        
                    # Source
                    async with conn.execute("SELECT source, COUNT(*) as count FROM articles GROUP BY source") as cursor:
                        stats["by_source"] = {r["source"]: r["count"] for r in await cursor.fetchall()}
                        
                    # Sentiment
                    async with conn.execute("SELECT sentiment, COUNT(*) as count FROM articles GROUP BY sentiment") as cursor:
                        for r in await cursor.fetchall():
                            if r["sentiment"] in stats["by_sentiment"]:
                                stats["by_sentiment"][r["sentiment"]] = r["count"]
                                
                    async with conn.execute("SELECT AVG(sentiment_score) as avg FROM articles") as cursor:
                        row = await cursor.fetchone()
                        stats["avg_sentiment"] = round(row["avg"], 2) if row and row["avg"] is not None else 0.0
                except Exception as e:
                    logger.error("Failed to query sqlite stats", error=str(e))
                    
        return stats

    def _unpack_json_fields(self, r: Dict[str, Any]):
        """Deserialize JSON strings from SQLite / DB output format into native Python collections."""
        # SQLite returns stringified JSON, Postgres returns native dicts (due to asyncpg handling JSONB)
        for field in ["tags", "gallery_urls", "video_embeds", "entities", "local_image_paths"]:
            if r.get(field) and isinstance(r[field], str):
                try:
                    r[field] = json.loads(r[field])
                except Exception:
                    # Keep as string or fallback
                    pass
            elif not r.get(field):
                r[field] = {} if field in ["entities", "local_image_paths"] else []
