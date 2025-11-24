"""
Action Similarity Service
Handles extraction of action sequences from task.json and calculation of action-based similarities
"""
import logging
import json
from typing import List, Dict, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from database import PullRequest, ActionEmbedding, ActionSimilarity

logger = logging.getLogger(__name__)


class ActionSimilarityService:
    """
    Service for calculating task similarity based on action sequences (tool calls and parameters)
    Uses the same embedding model as instruction similarity for consistency
    """
    
    def __init__(self):
        self.model_name = "all-MiniLM-L6-v2"
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the sentence transformer model"""
        try:
            logger.info(f"Loading action similarity model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("✓ Action similarity model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load action similarity model: {e}")
            self.model = None
    
    def extract_action_sequence(self, pr: PullRequest, db: Session) -> Optional[Dict]:
        """
        Extract and serialize action sequence from task.json
        
        Returns a dict with:
        - action_sequence: Serialized string representation of actions
        - tool_count: Number of tool calls
        - unique_tools: List of unique tool names used
        """
        if not pr.instruction_text:
            return None
        
        try:
            # Try to get task.json data from the PR
            # We need to fetch this from GitHub since we don't store the full task.json
            from github_service import GitHubService
            github_service = GitHubService()
            
            # Get task.json content
            task_data = github_service._fetch_task_json_for_pr(pr)
            if not task_data:
                logger.debug(f"PR #{pr.number}: Could not fetch task.json")
                return None
            
            # Extract actions from task.task.actions (nested structure)
            task_obj = task_data.get('task', {})
            actions = task_obj.get('actions', [])
            
            if not actions:
                logger.debug(f"PR #{pr.number}: No actions found in task.json")
                return None
            if not actions:
                return None
            
            # Extract action information
            action_sequence_parts = []
            unique_tools = set()
            
            for idx, action in enumerate(actions):
                if not isinstance(action, dict):
                    continue
                    
                tool_name = action.get('name', '')
                arguments = action.get('arguments', {})
                output = action.get('output', {})
                
                if not tool_name:
                    continue
                
                unique_tools.add(tool_name)
                
                # Create a structured representation of the action
                # Format: "tool_name(arg1=value1, arg2=value2) -> output_keys"
                arg_parts = []
                if isinstance(arguments, dict):
                    for key, value in arguments.items():
                        # Truncate long values and handle nested structures
                        if isinstance(value, dict):
                            value_str = f"{{{','.join(value.keys())}}}"[:50]
                        elif isinstance(value, list):
                            value_str = f"[{len(value)} items]"
                        else:
                            value_str = str(value)[:100] if value else ""
                        arg_parts.append(f"{key}={value_str}")
                
                # Include output structure info (keys only, not values)
                output_info = ""
                if isinstance(output, dict) and output:
                    output_keys = list(output.keys())[:3]  # First 3 keys
                    output_info = f" -> {{{','.join(output_keys)}}}"
                
                action_str = f"{tool_name}({', '.join(arg_parts)}){output_info}"
                action_sequence_parts.append(action_str)
            
            if not action_sequence_parts:
                return None
            
            # Join all actions with newlines for better embedding
            action_sequence = "\n".join(action_sequence_parts)
            
            return {
                'action_sequence': action_sequence,
                'tool_count': len(actions),
                'unique_tools': list(unique_tools)
            }
        
        except Exception as e:
            logger.error(f"Error extracting action sequence for PR #{pr.number}: {e}")
            return None
    
    def generate_embedding(self, action_sequence: str) -> Optional[np.ndarray]:
        """Generate embedding for an action sequence"""
        if not self.model:
            logger.error("Action similarity model not loaded")
            return None
        
        if not action_sequence or not action_sequence.strip():
            return None
        
        try:
            embedding = self.model.encode(action_sequence)
            return embedding
        except Exception as e:
            logger.error(f"Error generating action embedding: {e}")
            return None
    
    def get_or_create_embedding(self, pr: PullRequest, db: Session) -> Optional[ActionEmbedding]:
        """
        Get existing embedding or create a new one for a PR's action sequence
        """
        # Check if embedding already exists
        existing = db.query(ActionEmbedding).filter(ActionEmbedding.pr_id == pr.id).first()
        if existing:
            return existing
        
        # Extract action sequence
        action_data = self.extract_action_sequence(pr, db)
        if not action_data:
            logger.debug(f"PR #{pr.number}: No action sequence to embed")
            return None
        
        # Generate embedding
        embedding = self.generate_embedding(action_data['action_sequence'])
        if embedding is None:
            return None
        
        # Store in database
        try:
            action_embedding = ActionEmbedding(
                pr_id=pr.id,
                embedding=embedding.tolist(),
                action_sequence=action_data['action_sequence'],
                tool_count=action_data['tool_count'],
                unique_tools=action_data['unique_tools'],
                model_name=self.model_name
            )
            db.add(action_embedding)
            db.commit()
            db.refresh(action_embedding)
            
            logger.info(f"✓ Created action embedding for PR #{pr.number} ({action_data['tool_count']} tools)")
            return action_embedding
        
        except Exception as e:
            db.rollback()
            
            # If duplicate key error, just fetch and return the existing embedding
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"PR #{pr.number}: Action embedding already exists, fetching it")
                existing = db.query(ActionEmbedding).filter(ActionEmbedding.pr_id == pr.id).first()
                return existing
            
            logger.error(f"Error storing action embedding for PR #{pr.number}: {e}")
            return None
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        try:
            # Reshape for sklearn
            emb1 = embedding1.reshape(1, -1)
            emb2 = embedding2.reshape(1, -1)
            
            similarity = cosine_similarity(emb1, emb2)[0][0]
            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating action similarity: {e}")
            return 0.0
    
    def calculate_similarity_for_domain(self, domain: str, db: Session, limit: Optional[int] = None) -> int:
        """
        Calculate and store pairwise action similarities for all merged PRs in a domain
        
        Args:
            domain: The domain to calculate similarities for
            db: Database session
            limit: Optional limit on number of PRs to process
        
        Returns:
            Number of similarity pairs calculated
        """
        try:
            logger.info(f"Calculating action similarities for domain: {domain}")
            
            # Get all merged PRs with action embeddings in this domain (exclude reverted PRs)
            query = db.query(PullRequest).join(
                ActionEmbedding, PullRequest.id == ActionEmbedding.pr_id
            ).filter(
                PullRequest.domain == domain,
                PullRequest.merged == True,
                PullRequest.is_reverted.isnot(True)
            ).order_by(PullRequest.merged_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            prs_with_embeddings = query.all()
            
            if len(prs_with_embeddings) < 2:
                logger.info(f"Not enough PRs with action embeddings in {domain} (found {len(prs_with_embeddings)})")
                return 0
            
            logger.info(f"Found {len(prs_with_embeddings)} PRs with action embeddings in {domain}")
            
            # Calculate pairwise similarities
            calculated_count = 0
            for i, pr1 in enumerate(prs_with_embeddings):
                for pr2 in prs_with_embeddings[i+1:]:
                    # Skip if same task folder (rework PRs)
                    if pr1.task_folder_path and pr2.task_folder_path:
                        if pr1.task_folder_path == pr2.task_folder_path:
                            continue
                    
                    # Check if similarity already exists
                    existing = db.query(ActionSimilarity).filter(
                        or_(
                            and_(ActionSimilarity.pr_id_1 == pr1.id, ActionSimilarity.pr_id_2 == pr2.id),
                            and_(ActionSimilarity.pr_id_1 == pr2.id, ActionSimilarity.pr_id_2 == pr1.id)
                        )
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Get embeddings
                    emb1 = db.query(ActionEmbedding).filter(ActionEmbedding.pr_id == pr1.id).first()
                    emb2 = db.query(ActionEmbedding).filter(ActionEmbedding.pr_id == pr2.id).first()
                    
                    if not emb1 or not emb2:
                        continue
                    
                    # Calculate similarity
                    similarity_score = self.calculate_similarity(
                        np.array(emb1.embedding),
                        np.array(emb2.embedding)
                    )
                    
                    # Store similarity (always store pr_id_1 < pr_id_2 for consistency)
                    min_id = min(pr1.id, pr2.id)
                    max_id = max(pr1.id, pr2.id)
                    
                    action_similarity = ActionSimilarity(
                        domain=domain,
                        pr_id_1=min_id,
                        pr_id_2=max_id,
                        similarity_score=similarity_score
                    )
                    db.add(action_similarity)
                    calculated_count += 1
                
                # Commit in batches
                if (i + 1) % 10 == 0:
                    db.commit()
                    logger.info(f"Progress: {i + 1}/{len(prs_with_embeddings)} PRs processed, {calculated_count} similarities calculated")
            
            db.commit()
            logger.info(f"✓ Calculated {calculated_count} action similarity pairs for {domain}")
            return calculated_count
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error calculating action similarities for {domain}: {e}")
            return 0
    
    def calculate_similarity_for_new_prs(self, domain: str, new_pr_ids: List[int], db: Session) -> int:
        """
        Calculate action similarities between new PRs and existing ones in a domain
        
        Args:
            domain: The domain
            new_pr_ids: List of new PR IDs to calculate similarities for
            db: Database session
        
        Returns:
            Number of similarity pairs calculated
        """
        try:
            if not new_pr_ids:
                return 0
            
            logger.info(f"Calculating action similarities for {len(new_pr_ids)} new PRs in {domain}")
            
            # Get all existing PRs with action embeddings in this domain (exclude new ones and reverted ones)
            existing_prs = db.query(PullRequest).join(
                ActionEmbedding, PullRequest.id == ActionEmbedding.pr_id
            ).filter(
                PullRequest.domain == domain,
                PullRequest.merged == True,
                PullRequest.is_reverted.isnot(True),
                ~PullRequest.id.in_(new_pr_ids)
            ).all()
            
            # Get new PRs with embeddings
            new_prs = db.query(PullRequest).join(
                ActionEmbedding, PullRequest.id == ActionEmbedding.pr_id
            ).filter(
                PullRequest.id.in_(new_pr_ids),
                PullRequest.merged == True,
                PullRequest.is_reverted.isnot(True)
            ).all()
            
            if not new_prs:
                logger.info(f"No new PRs with action embeddings found")
                return 0
            
            logger.info(f"Comparing {len(new_prs)} new PRs with {len(existing_prs)} existing PRs")
            
            calculated_count = 0
            for new_pr in new_prs:
                for existing_pr in existing_prs:
                    # Skip if same task folder (rework PRs)
                    if new_pr.task_folder_path and existing_pr.task_folder_path:
                        if new_pr.task_folder_path == existing_pr.task_folder_path:
                            continue
                    
                    # Check if similarity already exists
                    min_id = min(new_pr.id, existing_pr.id)
                    max_id = max(new_pr.id, existing_pr.id)
                    
                    existing_sim = db.query(ActionSimilarity).filter(
                        ActionSimilarity.pr_id_1 == min_id,
                        ActionSimilarity.pr_id_2 == max_id
                    ).first()
                    
                    if existing_sim:
                        continue
                    
                    # Get embeddings
                    emb1 = db.query(ActionEmbedding).filter(ActionEmbedding.pr_id == new_pr.id).first()
                    emb2 = db.query(ActionEmbedding).filter(ActionEmbedding.pr_id == existing_pr.id).first()
                    
                    if not emb1 or not emb2:
                        continue
                    
                    # Calculate similarity
                    similarity_score = self.calculate_similarity(
                        np.array(emb1.embedding),
                        np.array(emb2.embedding)
                    )
                    
                    # Store similarity
                    action_similarity = ActionSimilarity(
                        domain=domain,
                        pr_id_1=min_id,
                        pr_id_2=max_id,
                        similarity_score=similarity_score
                    )
                    db.add(action_similarity)
                    calculated_count += 1
                
                db.commit()
            
            logger.info(f"✓ Calculated {calculated_count} action similarity pairs for new PRs")
            return calculated_count
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error calculating action similarities for new PRs: {e}")
            return 0

