"""
Database management for SoupBoss using SQLite with vector support.
"""

import sqlite3
import sqlite_vec
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import numpy as np


class SoupBossDB:
    """SQLite database manager with vector similarity support."""
    
    def __init__(self, db_path: str = "data/soupboss.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize database connection and create tables."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        
        # Load sqlite-vec extension
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        
        self._create_tables()
    
    def _create_tables(self):
        """Create all necessary tables."""
        cursor = self.conn.cursor()
        
        # Companies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL, -- 'greenhouse', 'lever', 'smartrecruiters', or 'disney'
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT NOT NULL, -- API job ID
                company_id INTEGER NOT NULL,
                source TEXT NOT NULL, -- 'greenhouse', 'lever', 'smartrecruiters', or 'disney'
                title TEXT NOT NULL,
                department TEXT,
                location TEXT,
                content_html TEXT,
                content_text TEXT,
                raw_data TEXT, -- Full JSON from API
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id),
                UNIQUE (external_id, company_id, source)
            )
        """)
        
        # Resumes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                content_text TEXT,
                file_type TEXT, -- 'pdf', 'txt', etc.
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Job embeddings table with vector support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding BLOB, -- Serialized numpy array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (id),
                UNIQUE (job_id, embedding_model)
            )
        """)
        
        # Resume embeddings table with vector support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resume_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding BLOB, -- Serialized numpy array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (resume_id) REFERENCES resumes (id),
                UNIQUE (resume_id, embedding_model)
            )
        """)
        
        # Matching results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS match_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                similarity_score REAL NOT NULL,
                adjusted_score REAL, -- After any manual adjustments
                embedding_model TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (resume_id) REFERENCES resumes (id),
                FOREIGN KEY (job_id) REFERENCES jobs (id),
                UNIQUE (resume_id, job_id, embedding_model)
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs (company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs (source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_results_resume ON match_results (resume_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_results_job ON match_results (job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_results_score ON match_results (similarity_score DESC)")
        
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # Company management
    def add_company(self, name: str, source: str) -> int:
        """Add a new company."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO companies (name, source) VALUES (?, ?)",
            (name.lower(), source)
        )
        self.conn.commit()
        
        # Get the company ID
        cursor.execute("SELECT id FROM companies WHERE name = ? AND source = ?", (name.lower(), source))
        return cursor.fetchone()["id"]
    
    def get_companies(self, active_only: bool = True) -> List[Dict]:
        """Get all companies."""
        cursor = self.conn.cursor()
        query = "SELECT * FROM companies"
        if active_only:
            query += " WHERE active = TRUE"
        query += " ORDER BY name"
        
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    
    # Job management
    def add_job(self, external_id: str, company_id: int, source: str, title: str,
                department: Optional[str], location: Optional[str], 
                content_html: Optional[str], content_text: Optional[str],
                raw_data: Dict) -> int:
        """Add or update a job posting."""
        cursor = self.conn.cursor()
        
        # Try to update existing job first
        cursor.execute("""
            UPDATE jobs SET
                title = ?, department = ?, location = ?, 
                content_html = ?, content_text = ?, raw_data = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE external_id = ? AND company_id = ? AND source = ?
        """, (title, department, location, content_html, content_text, 
              json.dumps(raw_data), external_id, company_id, source))
        
        if cursor.rowcount == 0:
            # Insert new job
            cursor.execute("""
                INSERT INTO jobs 
                (external_id, company_id, source, title, department, location, 
                 content_html, content_text, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (external_id, company_id, source, title, department, location,
                  content_html, content_text, json.dumps(raw_data)))
        
        job_id = cursor.lastrowid or self.get_job_id(external_id, company_id, source)
        self.conn.commit()
        return job_id
    
    def get_job_id(self, external_id: str, company_id: int, source: str) -> Optional[int]:
        """Get job ID by external identifiers."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM jobs WHERE external_id = ? AND company_id = ? AND source = ?",
            (external_id, company_id, source)
        )
        row = cursor.fetchone()
        return row["id"] if row else None
    
    def get_jobs(self, company_id: Optional[int] = None, source: Optional[str] = None) -> List[Dict]:
        """Get job listings with optional filtering."""
        cursor = self.conn.cursor()
        query = """
            SELECT j.*, c.name as company_name 
            FROM jobs j 
            JOIN companies c ON j.company_id = c.id
        """
        params = []
        conditions = []
        
        if company_id:
            conditions.append("j.company_id = ?")
            params.append(company_id)
        
        if source:
            conditions.append("j.source = ?")
            params.append(source)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY j.created_at DESC"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_job_count(self) -> int:
        """Get total number of jobs."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM jobs")
        return cursor.fetchone()["count"]
    
    # Resume management
    def add_resume(self, name: str, file_path: str, content_text: str, 
                   file_type: str, file_size: int) -> int:
        """Add a new resume."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO resumes (name, file_path, content_text, file_type, file_size)
            VALUES (?, ?, ?, ?, ?)
        """, (name, file_path, content_text, file_type, file_size))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_resumes(self) -> List[Dict]:
        """Get all resumes."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM resumes ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_resume(self, resume_id: int) -> Optional[Dict]:
        """Get a specific resume."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_resume_count(self) -> int:
        """Get total number of resumes."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM resumes")
        return cursor.fetchone()["count"]
    
    def delete_resume(self, resume_id: int) -> bool:
        """Delete a resume and its embeddings."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM resume_embeddings WHERE resume_id = ?", (resume_id,))
        cursor.execute("DELETE FROM match_results WHERE resume_id = ?", (resume_id,))
        cursor.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # Embedding management
    def save_job_embedding(self, job_id: int, model: str, embedding: np.ndarray):
        """Save job embedding vector."""
        cursor = self.conn.cursor()
        embedding_blob = embedding.tobytes()
        cursor.execute("""
            INSERT OR REPLACE INTO job_embeddings (job_id, embedding_model, embedding)
            VALUES (?, ?, ?)
        """, (job_id, model, embedding_blob))
        self.conn.commit()
    
    def save_resume_embedding(self, resume_id: int, model: str, embedding: np.ndarray):
        """Save resume embedding vector."""
        cursor = self.conn.cursor()
        embedding_blob = embedding.tobytes()
        cursor.execute("""
            INSERT OR REPLACE INTO resume_embeddings (resume_id, embedding_model, embedding)
            VALUES (?, ?, ?)
        """, (resume_id, model, embedding_blob))
        self.conn.commit()
    
    def get_job_embedding(self, job_id: int, model: str) -> Optional[np.ndarray]:
        """Get job embedding vector."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT embedding FROM job_embeddings WHERE job_id = ? AND embedding_model = ?",
            (job_id, model)
        )
        row = cursor.fetchone()
        if row:
            return np.frombuffer(row["embedding"], dtype=np.float32)
        return None
    
    def get_resume_embedding(self, resume_id: int, model: str) -> Optional[np.ndarray]:
        """Get resume embedding vector."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT embedding FROM resume_embeddings WHERE resume_id = ? AND embedding_model = ?",
            (resume_id, model)
        )
        row = cursor.fetchone()
        if row:
            return np.frombuffer(row["embedding"], dtype=np.float32)
        return None
    
    # Match results management
    def save_match_result(self, resume_id: int, job_id: int, similarity_score: float,
                          model: str, adjusted_score: Optional[float] = None):
        """Save similarity match result."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO match_results 
            (resume_id, job_id, similarity_score, adjusted_score, embedding_model)
            VALUES (?, ?, ?, ?, ?)
        """, (resume_id, job_id, similarity_score, adjusted_score, model))
        self.conn.commit()
    
    def get_match_results(self, resume_id: Optional[int] = None, 
                          limit: int = 50) -> List[Dict]:
        """Get match results with job and company details."""
        cursor = self.conn.cursor()
        query = """
            SELECT 
                mr.*, 
                j.title as job_title,
                j.department as job_department,
                j.location as job_location,
                c.name as company_name,
                r.name as resume_name
            FROM match_results mr
            JOIN jobs j ON mr.job_id = j.id
            JOIN companies c ON j.company_id = c.id
            JOIN resumes r ON mr.resume_id = r.id
        """
        params = []
        
        if resume_id:
            query += " WHERE mr.resume_id = ?"
            params.append(resume_id)
        
        query += " ORDER BY mr.similarity_score DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    # Cleanup operations
    def clear_jobs(self):
        """Remove all job data."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM job_embeddings")
        cursor.execute("DELETE FROM match_results")
        cursor.execute("DELETE FROM jobs")
        self.conn.commit()
    
    def clear_resumes(self):
        """Remove all resume data."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM resume_embeddings")
        cursor.execute("DELETE FROM match_results")
        cursor.execute("DELETE FROM resumes")
        self.conn.commit()
    
    def clear_embeddings(self):
        """Remove all embedding data."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM job_embeddings")
        cursor.execute("DELETE FROM resume_embeddings")
        cursor.execute("DELETE FROM match_results")
        self.conn.commit()
    
    def reset_database(self):
        """Reset entire database."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM match_results")
        cursor.execute("DELETE FROM job_embeddings")
        cursor.execute("DELETE FROM resume_embeddings")
        cursor.execute("DELETE FROM jobs")
        cursor.execute("DELETE FROM resumes")
        cursor.execute("DELETE FROM companies")
        self.conn.commit()


def get_db(db_path: str = "data/soupboss.db") -> SoupBossDB:
    """Get database instance."""
    return SoupBossDB(db_path)