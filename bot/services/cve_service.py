"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
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
from pathlib import Path

log = logging.getLogger(__name__)

cache_dir = Path(settings.CACHE_DIR)
cache_dir.mkdir(parents=True, exist_ok=True)

_cache = TTLCache(persistent_file=str(cache_dir / "cve_cache.json"))


class CVEService:
    """Service for interacting with NVD API to get CVE data."""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._sess: Optional[aiohttp.ClientSession] = None
    
    async def _session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling."""
        if not self._sess or self._sess.closed:
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
        """Fetch JSON data from NVD API with retry logic, rate limiting, and circuit breaker."""
        from bot.utils.api_rate_limiter import get_api_rate_limiter, RateLimitConfig
        from bot.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        
        if settings.NVD_API_KEY:
            rate_config = RateLimitConfig(requests_per_second=50.0/30.0, burst_size=10)
        else:
            rate_config = RateLimitConfig(requests_per_second=5.0/30.0, burst_size=2)
        
        rate_limiter = get_api_rate_limiter()
        await rate_limiter.wait_for_api("nvd", rate_config)
        
        if not hasattr(self, '_circuit_breaker'):
            self._circuit_breaker = CircuitBreaker(
                "nvd",
                CircuitBreakerConfig(
                    failure_threshold=3,
                    timeout=120.0,
                    expected_exception=(aiohttp.ClientError, aiohttp.ServerTimeoutError, asyncio.TimeoutError)
                )
            )
        
        async def _fetch():
            sess = await self._session()
            log.debug(f"Fetching CVE data from {url}")
            async with sess.get(url, params=params) as r:
                r.raise_for_status()
                return await r.json()
        
        async def fetch_with_cb():
            return await self._circuit_breaker.call(_fetch)
        
        return await retry_async(
            fetch_with_cb,
            max_attempts=DEFAULT_MAX_RETRIES,
            delay=DEFAULT_RETRY_DELAY * 2,
            backoff=DEFAULT_RETRY_BACKOFF,
            exceptions=(aiohttp.ClientError, aiohttp.ServerTimeoutError, asyncio.TimeoutError)
        )
    
    def _normalize_product_name(self, product: str) -> str:
        """Normalize product name for CVE search."""
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
        """Search for CVEs related to a product/version."""
        cache_key = f"cve_{product}_{version or 'all'}"
        cached = await _cache.get(cache_key, settings.CVE_TTL)
        if cached is not None:
            return cached[:limit]
        
        try:
            normalized_product = self._normalize_product_name(product)
            keyword = normalized_product
            if version:
                keyword += f" {version}"
            
            url = f"{settings.NVD_API_ROOT}/cves/2.0"
            params = {
                "keywordSearch": keyword,
                "resultsPerPage": min(limit, 50),
                "startIndex": 0
            }
            
            data = await self._fetch_json(url, params)
            
            cves = []
            if "vulnerabilities" in data:
                for vuln in data["vulnerabilities"]:
                    cve_data = vuln.get("cve", {})
                    cve_id = cve_data.get("id", "")
                    
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
                    
                    description = ""
                    if "descriptions" in cve_data:
                        for desc in cve_data["descriptions"]:
                            if desc.get("lang") == "en":
                                description = desc.get("value", "")
                                break
                    
                    published_date = None
                    last_modified = None
                    if "published" in cve_data:
                        try:
                            published_date = datetime.fromisoformat(cve_data["published"].replace("Z", "+00:00"))
                        except Exception:
                            pass
                    if "lastModified" in cve_data:
                        try:
                            last_modified = datetime.fromisoformat(cve_data["lastModified"].replace("Z", "+00:00"))
                        except Exception:
                            pass
                    
                    cves.append({
                        "cve_id": cve_id,
                        "product": product,
                        "version": version,
                        "severity": severity,
                        "description": description[:500] if description else "",
                        "published_date": published_date,
                        "last_modified": last_modified
                    })
            
            await _cache.set(cache_key, cves)
            
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
        """Get recent CVEs for a product."""
        cutoff_date = datetime.utcnow() - timedelta(seconds=days * SECONDS_PER_DAY)
        
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
        
        return await self.search_cve(product, limit=DEFAULT_CVE_LIMIT * 4)
    
    async def close(self):
        """Close aiohttp session and cleanup."""
        if self._sess and not self._sess.closed:
            await self._sess.close()
        if _cache:
            try:
                _cache._save_to_disk()
            except Exception as e:
                log.warning(f"Error saving cache on close: {e}")
