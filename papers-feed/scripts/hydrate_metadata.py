# this could probably be rolled into enrichment processing
#!/usr/bin/env python
# fetch_arxiv_metadata.py
"""
Fetches metadata for arXiv papers identified by issue labels and stores it using gh-store.
"""

import json
import sys
import os
import re
from typing import Dict, List, Optional, Any
import fire
from loguru import logger
import arxiv
import requests
from datetime import datetime

from gh_store.core.store import GitHubStore
from gh_store.tools.canonicalize import CanonicalStore
#from gh_store.tools.canonicalize import CanonicalStore as GitHubStore
from gh_store.core.constants import LabelNames
from gh_store.core.types import get_object_id_from_labels, StoredObject
from gh_store.core.exceptions import DuplicateUIDError, ConcurrentUpdateError

def is_metadata_satisfied(data: dict) -> bool:
    """Check if paper metadata is complete (has title, authors, etc.)"""
    if not data:
        return False
    
    title = data.get('title', '').strip()
    authors = data.get('authors', [])
    
    # Check if title exists and is not just the paper ID
    if not title:
        return False
    
    # If title is just the ID or "arXiv:ID", metadata is not satisfied
    paper_id = data.get('paperId', '') or data.get('id', '')
    if paper_id and (title == paper_id or title == f"arXiv:{paper_id}" or paper_id in title):
        return False
    
    # Check if authors exist (can be string or list)
    if isinstance(authors, list):
        has_authors = len(authors) > 0
    elif isinstance(authors, str):
        has_authors = bool(authors.strip())
    else:
        has_authors = False
    
    # Metadata is satisfied if we have a real title and authors
    return has_authors

def is_valid_arxiv_id(arxiv_id: str) -> bool:
    """Validate arXiv ID format."""
    return bool(re.match(r'\d{4}\.\d{4,5}(v\d+)?|\w+\/\d{7}(v\d+)?', arxiv_id))

def extract_arxiv_id_from_object_id(object_id: str) -> str:
    """Extract the arXiv ID from a paper ID with various prefixing schemes."""
    prefix = 'arxiv'
    
    # Case 1: Format is "prefix:id"
    if object_id.startswith(f"{prefix}:"):
        return object_id[len(prefix)+1:]
    
    # Case 2: Format is "prefix.id"
    if object_id.startswith(f"{prefix}."):
        return object_id[len(prefix)+1:]
    
    # Case 3: Format is "prefix:prefix:id"
    if object_id.startswith(f"{prefix}:{prefix}:"):
        return object_id[len(prefix)*2+2:]
    
    # Case 4: Format is "prefix.prefix.id"
    if object_id.startswith(f"{prefix}.{prefix}."):
        return object_id[len(prefix)*2+2:]
    
    # Case 5: If none of the above, return the original ID
    return object_id

def extract_acl_id_from_url(url: str) -> Optional[str]:
    """Extract ACL Anthology ID from URL.
    
    Examples:
    - https://aclanthology.org/2025.findings-emnlp.1171.pdf -> 2025.findings-emnlp.1171
    - https://aclanthology.org/2024.acl-long.123/ -> 2024.acl-long.123
    """
    if not url or 'aclanthology.org' not in url:
        return None
    
    # Match pattern: aclanthology.org/YEAR.VENUE.PAPER_ID
    match = re.search(r'aclanthology\.org/([0-9]{4}\.[a-z-]+\.[0-9]+)', url)
    if match:
        return match.group(1)
    return None

def fetch_acl_metadata(acl_id: str) -> Dict[str, Any]:
    """Fetch metadata from ACL Anthology by parsing HTML page."""
    logger.info(f"Fetching metadata for ACL Anthology ID: {acl_id}")
    
    # ACL Anthology HTML pages contain citation metadata in meta tags
    html_url = f"https://aclanthology.org/{acl_id}/"
    
    try:
        response = requests.get(html_url, timeout=10)
        response.raise_for_status()
        html = response.text
        
        # Try BeautifulSoup first (more reliable)
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title_tag = soup.find('meta', {'name': 'citation_title'})
            title = title_tag.get('content', '').strip() if title_tag else ''
            
            # Extract authors (multiple citation_author tags)
            author_tags = soup.find_all('meta', {'name': 'citation_author'})
            authors = [tag.get('content', '').strip() for tag in author_tags if tag.get('content')]
            
            # Extract publication date
            date_tag = soup.find('meta', {'name': 'citation_publication_date'})
            published_date = None
            if date_tag:
                date_str = date_tag.get('content', '').strip()
                # Format is usually "YYYY/MM" or "YYYY"
                if '/' in date_str:
                    year, month = date_str.split('/')[:2]
                    published_date = f"{year}-{month.zfill(2)}-01"
                elif date_str:
                    published_date = f"{date_str}-01-01"
            
            # Extract DOI
            doi_tag = soup.find('meta', {'name': 'citation_doi'})
            doi = doi_tag.get('content', '').strip() if doi_tag else ''
            
            # Extract venue/conference
            venue_tag = soup.find('meta', {'name': 'citation_conference_title'})
            venue = venue_tag.get('content', '').strip() if venue_tag else ''
            
            # Try to extract abstract from page content
            abstract = ''
            abstract_div = soup.find('div', {'id': 'abstract'}) or soup.find('div', class_='abstract')
            if abstract_div:
                abstract = abstract_div.get_text(strip=True)
            
            metadata = {
                'title': title,
                'authors': authors,
                'publishedDate': published_date,
                'abstract': abstract,
                'doi': doi,
                'tags': [venue] if venue else [],
            }
            
            logger.info(f"Successfully fetched metadata for ACL ID: {acl_id}")
            logger.info(f"Title: {title}, Authors: {len(authors)} authors")
            return metadata
            
        except ImportError:
            # BeautifulSoup not available, use regex
            pass
        
        # Fallback to regex parsing
        title_match = re.search(r'<meta\s+name=["\']citation_title["\']\s+content=["\']([^"\']+)["\']', html)
        author_matches = re.findall(r'<meta\s+name=["\']citation_author["\']\s+content=["\']([^"\']+)["\']', html)
        date_match = re.search(r'<meta\s+name=["\']citation_publication_date["\']\s+content=["\']([^"\']+)["\']', html)
        doi_match = re.search(r'<meta\s+name=["\']citation_doi["\']\s+content=["\']([^"\']+)["\']', html)
        venue_match = re.search(r'<meta\s+name=["\']citation_conference_title["\']\s+content=["\']([^"\']+)["\']', html)
        
        published_date = None
        if date_match:
            date_str = date_match.group(1)
            if '/' in date_str:
                year, month = date_str.split('/')[:2]
                published_date = f"{year}-{month.zfill(2)}-01"
            elif date_str:
                published_date = f"{date_str}-01-01"
        
        metadata = {
            'title': title_match.group(1) if title_match else '',
            'authors': author_matches,
            'publishedDate': published_date,
            'abstract': '',
            'doi': doi_match.group(1) if doi_match else '',
            'tags': [venue_match.group(1)] if venue_match else [],
        }
        
        logger.info(f"Successfully fetched metadata for ACL ID: {acl_id} (using regex)")
        return metadata
            
    except requests.RequestException as e:
        logger.error(f"Failed to fetch HTML for ACL ID {acl_id}: {e}")
        raise ValueError(f"Could not fetch metadata for ACL Anthology ID: {acl_id}")

def fetch_arxiv_metadata(arxiv_id: str) -> Dict[str, Any]:
    """Fetch metadata from arXiv API for a given ID using the arxiv client."""
    logger.info(f"Fetching metadata for arXiv ID: {arxiv_id}")
    
    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    paper = next(client.results(search))
    if not paper:
        raise ValueError(f"No paper found with arXiv ID: {arxiv_id}")
    
    metadata = {
        #'id': paper.entry_id,
        'title': paper.title,
        'authors': [author.name for author in paper.authors],
        'publishedDate': paper.published.isoformat() if paper.published else None,
        #'updated': paper.updated.isoformat() if paper.updated else None,
        'doi': paper.doi,
        'tags': paper.categories,
        'abstract': paper.summary,
        #'links': [{'href': link.href, 'type': link.type} for link in paper.links],
        #'comment': paper.comment,
        #'journal_ref': paper.journal_ref,
        #'primary_category': paper.primary_category,
        #'pdf_url': paper.pdf_url,
    }
    
    logger.info(f"Successfully fetched metadata for arXiv ID: {arxiv_id}")
    logger.info(metadata)
    return metadata
    

def hydrate_issue_metadata(issue: int, token:str, repo:str):
    #store = GitHubStore(token=token, repo=repo, config_path=None)
    store = CanonicalStore(token=token, repo=repo, config_path=None)
    
    obj = store.issue_handler.get_object_by_number(issue)
    object_id = obj.meta.object_id
    #object_id = get_object_id_from_labels(issue)
    if not object_id.startswith("paper:"):
        logger.info("Not a paper object, exiting.")
        sys.exit(0)
    
    paper_id = object_id[len('paper:'):]
    paper_data = obj.data
    url = paper_data.get('url', '')
    
    updates = {}
    
    # Check if this is an ACL Anthology paper
    acl_id = extract_acl_id_from_url(url)
    if acl_id:
        logger.info(f"Detected ACL Anthology paper: {acl_id}")
        try:
            acl_meta = fetch_acl_metadata(acl_id)
            for k, v_new in acl_meta.items():
                v_old = paper_data.get(k)
                # Update if field is missing, empty string, or empty list
                if not v_old or (isinstance(v_old, str) and not v_old.strip()) or (isinstance(v_old, list) and len(v_old) == 0):
                    updates[k] = v_new
        except Exception as e:
            logger.error(f"Failed to fetch ACL metadata: {e}")
    
    # Check if this is an arXiv paper (only if not ACL)
    elif paper_id.startswith('arxiv') or is_valid_arxiv_id(paper_id):
        if paper_id.startswith('arxiv'):
            arxiv_id = extract_arxiv_id_from_object_id(paper_id)
        else:
            arxiv_id = paper_id
        
        try:
            arxiv_meta = fetch_arxiv_metadata(arxiv_id)
            for k, v_new in arxiv_meta.items():
                v_old = paper_data.get(k)
                # Update if field is missing, empty string, or empty list
                if not v_old or (isinstance(v_old, str) and not v_old.strip()) or (isinstance(v_old, list) and len(v_old) == 0):
                    updates[k] = v_new
        except Exception as e:
            logger.error(f"Failed to fetch arXiv metadata: {e}")
    elif 'url' in object_id or paper_id.startswith('url-'):
        logger.info(f"URL-based paper ({object_id}), metadata hydration not supported yet.")
        store.process_updates(issue)
        return
    else:
        logger.info(f"Unknown paper type for {object_id}, skipping metadata hydration.")
        return

    metadata_satisfied = False
    if updates:
        # Issue is open because we are processing it right now, which acts as an implicit lock on updates.
        # so we close it before pushing the new update
        #store.repo.get_issue(issue).edit(state='closed') # ...this is awkward af. in fact, I think I should just eliminate that whole ConcurrentUpdateError
        # finally: what we came here for
        store.update(object_id=object_id, changes=updates)
        store.process_updates(issue) # ...why is this a separate second step? sheesh, I reaaly did rube goldberg the shit out of this thing
        metadata_satisfied = True
    else:
        metadata_satisfied = is_metadata_satisfied(obj.data)

    if metadata_satisfied:
        store.repo.get_issue(issue).remove_from_labels("TODO:hydrate-metadata")    

# TODO: upstream this to gh-store utilities
def get_open_issues(token:str, repo:str, extra_labels: list|None = None):
    store = GitHubStore(token=token, repo=repo, config_path=None)
    #store = CanonicalStore(token=token, repo=repo, config_path=None)
    
    query_labels = [LabelNames.GH_STORE, LabelNames.STORED_OBJECT]
    if extra_labels: # 
        query_labels += extra_labels
    return store.repo.get_issues(
            labels=query_labels,
            state="open"
        )

def hydrate_all_open_issues(token:str, repo:str):
    store = CanonicalStore(token=token, repo=repo, config_path=None)
    for issue in get_open_issues(token=token, repo=repo, extra_labels=["TODO:hydrate-metadata"]):
        try:
            hydrate_issue_metadata(issue=issue.number, token=token, repo=repo)
        except TypeError:
            logger.info("unsupported source for issue %s", issue.number)
        except DuplicateUIDError:
            #logger.info("Issue %s has dupes, skipping for now. Run deduplification." % issue.number)
            logger.info("Issue %s has dupes. Running deduplification." % issue.number)
            #object_id = StoredObject.from_issue(issue).object_id
            object_id = get_object_id_from_labels(issue)
            dedupe_status = store.deduplicate_object(object_id)
            hydrate_issue_metadata(issue=dedupe_status.get('canonical_issue'), token=token, repo=repo)
        except ConcurrentUpdateError:
            logger.info("Issue %s has too many unprocessed concurrent updates. Either adjust this threshold, or reconcile the updates manually.", issue.number)

def hydrate_all_paper_issues(token:str, repo:str):
    """Hydrate metadata for all paper issues (open or closed) that need it."""
    from gh_store.core.constants import LabelNames
    
    store = CanonicalStore(token=token, repo=repo, config_path=None)
    github_store = GitHubStore(token=token, repo=repo, config_path=None)
    
    # Get all issues with stored-object label (both open and closed)
    all_issues = github_store.repo.get_issues(
        state="all",
        labels=[LabelNames.STORED_OBJECT],
        sort="created",
        direction="desc"
    )
    
    processed = 0
    skipped = 0
    errors = 0
    
    for issue in all_issues:
        # Only process paper issues
        if not issue.title.startswith("Stored Object: paper:"):
            continue
            
        object_id = issue.title.replace("Stored Object: ", "")
        if not object_id.startswith("paper:"):
            continue
            
        paper_id = object_id[len('paper:'):]
        
        # Only process arXiv papers
        if not paper_id.startswith('arxiv'):
            logger.info(f"Skipping non-arXiv paper: {object_id}")
            skipped += 1
            continue
        
        # Check if metadata is already satisfied
        try:
            obj = store.issue_handler.get_object_by_number(issue.number)
            if is_metadata_satisfied(obj.data):
                logger.info(f"Metadata already satisfied for issue #{issue.number} ({object_id}), skipping")
                skipped += 1
                continue
        except Exception as e:
            logger.warning(f"Could not check issue #{issue.number}: {e}")
            errors += 1
            continue
        
        # Try to hydrate metadata
        try:
            logger.info(f"Processing issue #{issue.number}: {object_id}")
            # Reopen issue temporarily if closed (needed for updates)
            was_closed = issue.state == 'closed'
            if was_closed:
                issue.edit(state='open')
            
            hydrate_issue_metadata(issue=issue.number, token=token, repo=repo)
            
            # Close again if it was closed before
            if was_closed:
                issue.edit(state='closed')
            
            processed += 1
            logger.info(f"✅ Successfully hydrated metadata for issue #{issue.number}")
        except TypeError as e:
            logger.info(f"Unsupported source for issue #{issue.number}: {e}")
            skipped += 1
        except Exception as e:
            logger.error(f"Error processing issue #{issue.number}: {e}")
            errors += 1
    
    logger.info(f"Metadata hydration complete: {processed} processed, {skipped} skipped, {errors} errors")

# class Main:
#     def hydrate_issue_metadata(self, issue: int, token:str, repo:str):
#         hydrate_issue_metadata(issue=issue, token=token, repo=repo)

#     def hydrate_all_open_issues(self, token:str, repo:str):
#         hydrate_all_open_issues(token=token, repo=repo)


if __name__ == "__main__":
    #fire.Fire(Main)
    fire.Fire(
        { 
            "hydrate_issue_metadata": hydrate_issue_metadata, 
            "hydrate_all_open_issues": hydrate_all_open_issues,
            "hydrate_all_paper_issues": hydrate_all_paper_issues
        }
    )
