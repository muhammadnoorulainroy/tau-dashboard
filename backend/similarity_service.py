"""
Similarity Service - Handles task instruction embeddings and cosine similarity calculations
"""
import logging
import numpy as np
from typing import List, Optional
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from database import PullRequest, TaskEmbedding, TaskSimilarity
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class SimilarityService:
    """Service for calculating and storing task similarity scores"""
    
    def __init__(self):
        """Initialize the sentence transformer model"""
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Loaded sentence transformer model: all-MiniLM-L6-v2")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {e}")
            self.model = None
    
    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for a single instruction text
        
        Args:
            text: The instruction text to embed
            
        Returns:
            numpy array of embedding vector, or None if failed
        """
        if not self.model:
            logger.error("Sentence transformer model not loaded")
            return None
        
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
        
        try:
            embedding = self.model.encode(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def get_or_create_embedding(self, pr_id: int, instruction_text: str, db: Session) -> Optional[np.ndarray]:
        """
        Get existing embedding from cache or create new one
        
        Args:
            pr_id: Pull request ID
            instruction_text: The instruction text
            db: Database session
            
        Returns:
            numpy array of embedding vector, or None if failed
        """
        # Check if embedding exists
        existing = db.query(TaskEmbedding).filter(TaskEmbedding.pr_id == pr_id).first()
        
        if existing:
            logger.debug(f"Using cached embedding for PR {pr_id}")
            return np.array(existing.embedding)
        
        # Generate new embedding
        embedding_vector = self.generate_embedding(instruction_text)
        if embedding_vector is None:
            return None
        
        # Store in database
        try:
            task_embedding = TaskEmbedding(
                pr_id=pr_id,
                embedding=embedding_vector.tolist(),
                model_name="all-MiniLM-L6-v2"
            )
            db.add(task_embedding)
            db.commit()
            logger.debug(f"Created and cached embedding for PR {pr_id}")
            return embedding_vector
        except Exception as e:
            logger.error(f"Error storing embedding for PR {pr_id}: {e}")
            db.rollback()
            return embedding_vector  # Return the embedding even if storage failed
    
    def calculate_similarity_for_domain(self, domain: str, db: Session) -> bool:
        """
        Calculate pairwise similarities for all merged PRs in a domain
        Only calculates for PR pairs without existing similarities
        
        Args:
            domain: Domain name
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get all merged PRs with instructions in this domain
            prs = db.query(PullRequest).filter(
                PullRequest.domain == domain,
                PullRequest.merged == True,
                PullRequest.instruction_text != None,
                PullRequest.instruction_text != ''
            ).all()
            
            if len(prs) < 2:
                logger.info(f"Domain {domain}: Not enough PRs ({len(prs)}) for similarity calculation")
                return True
            
            logger.info(f"Domain {domain}: Calculating similarities for {len(prs)} PRs")
            
            # Get or create embeddings for all PRs
            embeddings = {}
            for pr in prs:
                embedding = self.get_or_create_embedding(pr.id, pr.instruction_text, db)
                if embedding is not None:
                    embeddings[pr.id] = embedding
                else:
                    logger.warning(f"Could not generate embedding for PR {pr.number}")
            
            if len(embeddings) < 2:
                logger.warning(f"Domain {domain}: Not enough valid embeddings ({len(embeddings)})")
                return False
            
            # Calculate pairwise similarities
            pr_ids = list(embeddings.keys())
            similarities_calculated = 0
            
            for i in range(len(pr_ids)):
                for j in range(i + 1, len(pr_ids)):
                    pr_id_1, pr_id_2 = pr_ids[i], pr_ids[j]
                    
                    # Ensure pr_id_1 < pr_id_2 for consistent ordering
                    if pr_id_1 > pr_id_2:
                        pr_id_1, pr_id_2 = pr_id_2, pr_id_1
                    
                    # Check if similarity already exists
                    existing = db.query(TaskSimilarity).filter(
                        TaskSimilarity.pr_id_1 == pr_id_1,
                        TaskSimilarity.pr_id_2 == pr_id_2
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Calculate cosine similarity
                    try:
                        sim_score = cosine_similarity(
                            embeddings[pr_id_1].reshape(1, -1),
                            embeddings[pr_id_2].reshape(1, -1)
                        )[0][0]
                        
                        # Store similarity
                        similarity = TaskSimilarity(
                            domain=domain,
                            pr_id_1=pr_id_1,
                            pr_id_2=pr_id_2,
                            similarity_score=float(sim_score)
                        )
                        db.add(similarity)
                        similarities_calculated += 1
                        
                        # Commit in batches to avoid large transactions
                        if similarities_calculated % 100 == 0:
                            db.commit()
                            logger.info(f"Domain {domain}: Calculated {similarities_calculated} similarities so far...")
                            
                    except Exception as e:
                        logger.error(f"Error calculating similarity between PR {pr_id_1} and {pr_id_2}: {e}")
                        continue
            
            # Final commit
            db.commit()
            logger.info(f"Domain {domain}: Successfully calculated {similarities_calculated} new similarities")
            return True
            
        except Exception as e:
            logger.error(f"Error calculating similarities for domain {domain}: {e}")
            db.rollback()
            return False
    
    def calculate_similarities_for_new_prs(self, pr_ids: List[int], db: Session) -> bool:
        """
        Calculate similarities for newly merged PRs
        Only calculates pairs involving at least one new PR
        
        Args:
            pr_ids: List of new PR IDs
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        if not pr_ids:
            return True
        
        try:
            # Get the new PRs
            new_prs = db.query(PullRequest).filter(
                PullRequest.id.in_(pr_ids),
                PullRequest.merged == True,
                PullRequest.instruction_text != None,
                PullRequest.instruction_text != ''
            ).all()
            
            if not new_prs:
                logger.info("No valid new PRs for similarity calculation")
                return True
            
            # Group by domain for efficient processing
            domains = {}
            for pr in new_prs:
                if pr.domain not in domains:
                    domains[pr.domain] = []
                domains[pr.domain].append(pr)
            
            # Process each domain
            for domain, domain_new_prs in domains.items():
                logger.info(f"Domain {domain}: Calculating similarities for {len(domain_new_prs)} new PRs")
                
                # Get all existing PRs in the domain
                all_prs = db.query(PullRequest).filter(
                    PullRequest.domain == domain,
                    PullRequest.merged == True,
                    PullRequest.instruction_text != None,
                    PullRequest.instruction_text != ''
                ).all()
                
                # Get or create embeddings
                embeddings = {}
                for pr in all_prs:
                    embedding = self.get_or_create_embedding(pr.id, pr.instruction_text, db)
                    if embedding is not None:
                        embeddings[pr.id] = embedding
                
                # Calculate similarities for pairs involving new PRs
                new_pr_ids_set = {pr.id for pr in domain_new_prs}
                similarities_calculated = 0
                
                for i, pr1 in enumerate(all_prs):
                    if pr1.id not in embeddings:
                        continue
                    
                    for j, pr2 in enumerate(all_prs):
                        if i >= j:  # Skip self and duplicates
                            continue
                        if pr2.id not in embeddings:
                            continue
                        
                        # Skip if neither PR is new
                        if pr1.id not in new_pr_ids_set and pr2.id not in new_pr_ids_set:
                            continue
                        
                        pr_id_1 = min(pr1.id, pr2.id)
                        pr_id_2 = max(pr1.id, pr2.id)
                        
                        # Check if similarity already exists
                        existing = db.query(TaskSimilarity).filter(
                            TaskSimilarity.pr_id_1 == pr_id_1,
                            TaskSimilarity.pr_id_2 == pr_id_2
                        ).first()
                        
                        if existing:
                            continue
                        
                        # Calculate similarity
                        try:
                            sim_score = cosine_similarity(
                                embeddings[pr1.id].reshape(1, -1),
                                embeddings[pr2.id].reshape(1, -1)
                            )[0][0]
                            
                            similarity = TaskSimilarity(
                                domain=domain,
                                pr_id_1=pr_id_1,
                                pr_id_2=pr_id_2,
                                similarity_score=float(sim_score)
                            )
                            db.add(similarity)
                            similarities_calculated += 1
                            
                            if similarities_calculated % 50 == 0:
                                db.commit()
                        except Exception as e:
                            logger.error(f"Error calculating similarity: {e}")
                            continue
                
                db.commit()
                logger.info(f"Domain {domain}: Calculated {similarities_calculated} new similarities")
            
            return True
            
        except Exception as e:
            logger.error(f"Error calculating similarities for new PRs: {e}")
            db.rollback()
            return False
    
    def get_similarity_stats_for_pr(self, pr_id: int, db: Session) -> Optional[dict]:
        """
        Get similarity statistics for a specific PR
        
        Args:
            pr_id: Pull request ID
            db: Database session
            
        Returns:
            Dictionary with avg_similarity, max_similarity, min_similarity, or None
        """
        try:
            # Get all similarities involving this PR
            similarities = db.query(TaskSimilarity).filter(
                or_(
                    TaskSimilarity.pr_id_1 == pr_id,
                    TaskSimilarity.pr_id_2 == pr_id
                )
            ).all()
            
            if not similarities:
                return None
            
            scores = [s.similarity_score for s in similarities]
            
            return {
                "avg_similarity": float(np.mean(scores)),
                "max_similarity": float(np.max(scores)),
                "min_similarity": float(np.min(scores)),
                "count": len(scores)
            }
            
        except Exception as e:
            logger.error(f"Error getting similarity stats for PR {pr_id}: {e}")
            return None

