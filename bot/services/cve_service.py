"""Service for fetching and managing CVE data from NVD API."""
import aiohttp
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from bot.models import CVERecord
from bot.utils.cache import TTLCache
from bot.utils.retry import retry_async
from bot.utils.constants import (
    CVE_SEVERITY_CRITICAL, CVE_SEVERITY_HIGH, CVE_SEVERITY_MEDIUM, CVE_SEVERITY_LOW,
    DEFAULT_CVE_LIMIT, DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY, DEFAULT_RETRY_BACKOFF,
    SECONDS_PER_DAY
)
from config import settings

log = logging.getLogger(__name__)
_cache = TTLCache(persistent_file="/tmp/cve_cache.json")


class CVEService:
    """Service for interacting with NVD API to get CVE data."""
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize CVE service.
        
        Args:
            db: Optional database session for caching
        """
        self.db = db
        self._sess: Optional[aiohttp.ClientSession] = None
    
    async def _session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling."""
        if not self._sess:
            headers = {}
            if settings.NVD_API_KEY:
                headers["apiKey"] = settings.NVD_API_KEY
            
            connector = aiohttp.TCPConnector(limit=50, limit_per_host=10)
            self._sess = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
                connector=connector
            )
        return self._sess
    
    async def _fetch_json(self, url: str, params: Optional[Dict] = None) -> Any:
        """
        Fetch JSON data from NVD API with retry logic.
        
        Args:
            url: Full API URL
            params: Optional query parameters
            
        Returns:
            Parsed JSON data
        """
        async def _fetch():
            sess = await self._session()
            log.debug(f"Fetching CVE data from {url}")
            async with sess.get(url, params=params) as r:
                r.raise_for_status()
                return await r.json()
        
        return await retry_async(
            _fetch,
            max_attempts=DEFAULT_MAX_RETRIES,
            delay=DEFAULT_RETRY_DELAY * 2,  # NVD has rate limits
            backoff=DEFAULT_RETRY_BACKOFF,
            exceptions=(aiohttp.ClientError, aiohttp.ServerTimeoutError, asyncio.TimeoutError)
        )
    
    def _normalize_product_name(self, product: str) -> str:
        """
        Normalize product name for CVE search.
        
        Args:
            product: Product name
            
        Returns:
            Normalized product name
        """
        # Common mappings
        mappings = {
            "python": "python",
            "nodejs": "node.js",
            "node": "node.js",
            "java": "java",
            "php": "php",
            "ruby": "ruby",
            "go": "golang",
            "rust": "rust",
        }
        return mappings.get(product.lower(), product.lower())
    
    async def search_cve(
        self,
        product: str,
        version: Optional[str] = None,
        limit: int = DEFAULT_CVE_LIMIT
    ) -> List[Dict[str, Any]]:
        """
        Search for CVEs related to a product/version.
        
        Args:
            product: Product name
            version: Optional version string
            limit: Maximum number of results
            
        Returns:
            List of CVE dictionaries
        """
        # Check cache first
        cache_key = f"cve_{product}_{version or 'all'}"
        cached = await _cache.get(cache_key, settings.CVE_TTL)
        if cached is not None:
            log.debug(f"Returning cached CVE data for {product}")
            return cached[:limit]
        
        try:
            # Build search query
            normalized_product = self._normalize_product_name(product)
            keyword = f"{normalized_product}"
            if version:
                keyword += f" {version}"
            
            # NVD API v2.0 endpoint
            url = f"{settings.NVD_API_ROOT}/cves/2.0"
            params = {
                "keywordSearch": keyword,
                "resultsPerPage": min(limit, 50),
                "startIndex": 0
            }
            
            data = await self._fetch_json(url, params)
            
            # Parse results
            cves = []
            if "vulnerabilities" in data:
                for vuln in data["vulnerabilities"]:
                    cve_data = vuln.get("cve", {})
                    cve_id = cve_data.get("id", "")
                    
                    # Extract severity
                    severity = None
                    if "metrics" in cve_data:
                        if "cvssMetricV31" in cve_data["metrics"]:
                            severity_data = cve_data["metrics"]["cvssMetricV31"][0]
                            base_score = severity_data.get("cvssData", {}).get("baseScore", 0)
                            if base_score >= 9.0:
                                severity = CVE_SEVERITY_CRITICAL
                            elif base_score >= 7.0:
                                severity = CVE_SEVERITY_HIGH
                            elif base_score >= 4.0:
                                severity = CVE_SEVERITY_MEDIUM
                            else:
                                severity = CVE_SEVERITY_LOW
                        elif "cvssMetricV2" in cve_data["metrics"]:
                            severity_data = cve_data["metrics"]["cvssMetricV2"][0]
                            base_score = severity_data.get("cvssData", {}).get("baseScore", 0)
                            if base_score >= 9.0:
                                severity = CVE_SEVERITY_CRITICAL
                            elif base_score >= 7.0:
                                severity = CVE_SEVERITY_HIGH
                            elif base_score >= 4.0:
                                severity = CVE_SEVERITY_MEDIUM
                            else:
                                severity = CVE_SEVERITY_LOW
                    
                    # Extract description
                    description = ""
                    if "descriptions" in cve_data:
                        for desc in cve_data["descriptions"]:
                            if desc.get("lang") == "en":
                                description = desc.get("value", "")
                                break
                    
                    # Extract dates
                    published_date = None
                    last_modified = None
                    if "published" in cve_data:
                        try:
                            published_date = datetime.fromisoformat(cve_data["published"].replace("Z", "+00:00"))
                        except:
                            pass
                    if "lastModified" in cve_data:
                        try:
                            last_modified = datetime.fromisoformat(cve_data["lastModified"].replace("Z", "+00:00"))
                        except:
                            pass
                    
                    cves.append({
                        "cve_id": cve_id,
                        "product": product,
                        "version": version,
                        "severity": severity,
                        "description": description[:500] if description else "",  # Limit length
                        "published_date": published_date,
                        "last_modified": last_modified
                    })
            
            # Cache results
            await _cache.set(cache_key, cves)
            
            # Save to database if available
            if self.db:
                self._save_cves_to_db(cves)
            
            return cves[:limit]
        except Exception as e:
            log.error(f"Error searching CVEs for {product}: {e}", exc_info=True)
            return []
    
    def _save_cves_to_db(self, cves: List[Dict[str, Any]]):
        """Save CVEs to database cache."""
        if not self.db:
            return
        
        try:
            for cve_data in cves:
                # Check if already exists
                existing = self.db.query(CVERecord).filter(
                    CVERecord.cve_id == cve_data["cve_id"]
                ).first()
                
                if not existing:
                    record = CVERecord(
                        cve_id=cve_data["cve_id"],
                        product=cve_data["product"],
                        version=cve_data.get("version"),
                        severity=cve_data.get("severity"),
                        description=cve_data.get("description"),
                        published_date=cve_data.get("published_date"),
                        last_modified=cve_data.get("last_modified")
                    )
                    self.db.add(record)
                else:
                    # Update if modified date is newer
                    if cve_data.get("last_modified") and existing.last_modified:
                        if cve_data["last_modified"] > existing.last_modified:
                            existing.severity = cve_data.get("severity")
                            existing.description = cve_data.get("description")
                            existing.last_modified = cve_data.get("last_modified")
            
            self.db.commit()
        except Exception as e:
            log.error(f"Error saving CVEs to database: {e}")
            self.db.rollback()
    
    async def get_recent_cves(
        self,
        product: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get recent CVEs for a product.
        
        Args:
            product: Product name
            days: Number of days to look back
            
        Returns:
            List of recent CVE dictionaries
        """
        """
        Get recent CVEs for a product.
        
        Args:
            product: Product name
            days: Number of days to look back
            
        Returns:
            List of recent CVE dictionaries
        """
        cutoff_date = datetime.utcnow() - timedelta(seconds=days * SECONDS_PER_DAY)
        
        # Try database first
        if self.db:
            records = self.db.query(CVERecord).filter(
                and_(
                    CVERecord.product == product,
                    CVERecord.published_date >= cutoff_date
                )
            ).order_by(CVERecord.published_date.desc()).all()
            
            if records:
                return [{
                    "cve_id": r.cve_id,
                    "product": r.product,
                    "version": r.version,
                    "severity": r.severity,
                    "description": r.description,
                    "published_date": r.published_date,
                    "last_modified": r.last_modified
                } for r in records]
        
        # Fallback to API search
        return await self.search_cve(product, limit=DEFAULT_CVE_LIMIT * 4)
    
    async def close(self):
        """Close aiohttp session."""
        if self._sess and not self._sess.closed:
            await self._sess.close()

