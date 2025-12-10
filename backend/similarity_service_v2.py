"""
Similarity Service V2 - Handles task instruction and action embeddings for Task Agent data
Updated to work with Task model instead of PullRequest
"""
import logging
import json
import numpy as np
from typing import List, Optional, Dict, Any
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from database_v2 import Task, TaskEmbedding, TaskSimilarity, ActionEmbedding, ActionSimilarity
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class SimilarityServiceV2:
    """Service for calculating and storing task similarity scores for Task Agent data"""
    
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
        Generate embedding for text
        
        Args:
            text: The text to embed
            
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
    
    # =========================================================================
    # TASK INSTRUCTION SIMILARITY
    # =========================================================================
    
    def get_or_create_task_embedding(self, task_id: int, instruction_text: str, db: Session) -> Optional[np.ndarray]:
        """
        Get existing embedding from cache or create new one
        
        Args:
            task_id: Task ID
            instruction_text: The instruction text
            db: Database session
            
        Returns:
            numpy array of embedding vector, or None if failed
        """
        # Check if embedding exists
        existing = db.query(TaskEmbedding).filter(TaskEmbedding.task_id == task_id).first()
        
        if existing:
            logger.debug(f"Using cached embedding for task {task_id}")
            return np.array(existing.embedding)
        
        # Generate new embedding
        embedding_vector = self.generate_embedding(instruction_text)
        if embedding_vector is None:
            return None
        
        # Store in database
        try:
            task_embedding = TaskEmbedding(
                task_id=task_id,
                embedding=embedding_vector.tolist(),
                model_name="all-MiniLM-L6-v2"
            )
            db.add(task_embedding)
            db.commit()
            logger.debug(f"Created and cached embedding for task {task_id}")
            return embedding_vector
        except Exception as e:
            db.rollback()
            
            # If duplicate key error, the embedding already exists
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"Task {task_id}: Instruction embedding already exists in DB")
                return embedding_vector
            
            logger.error(f"Error storing embedding for task {task_id}: {e}")
            return embedding_vector
    
    def calculate_task_similarity_for_domain(self, domain: str, db: Session) -> bool:
        """
        Calculate pairwise similarities for all approved tasks in a domain
        
        Args:
            domain: Domain name to process
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        # Get approved tasks with instruction text
        tasks = db.query(Task).filter(
            Task.domain == domain,
            Task.status == 'approved',
            Task.instruction_text.isnot(None)
        ).all()
        
        if len(tasks) < 2:
            logger.info(f"Domain {domain}: Not enough approved tasks for similarity ({len(tasks)})")
            return True
        
        logger.info(f"Domain {domain}: Processing {len(tasks)} approved tasks")
        
        # Generate embeddings for all tasks
        task_embeddings = {}
        for task in tasks:
            embedding = self.get_or_create_task_embedding(task.id, task.instruction_text, db)
            if embedding is not None:
                task_embeddings[task.id] = embedding
        
        if len(task_embeddings) < 2:
            logger.warning(f"Domain {domain}: Not enough valid embeddings ({len(task_embeddings)})")
            return True
        
        logger.info(f"Domain {domain}: Generated {len(task_embeddings)} embeddings")
        
        # Calculate pairwise similarities
        task_ids = list(task_embeddings.keys())
        embeddings_matrix = np.array([task_embeddings[tid] for tid in task_ids])
        
        # Calculate cosine similarity matrix
        similarity_matrix = cosine_similarity(embeddings_matrix)
        
        # Store similarities (only upper triangle to avoid duplicates)
        new_pairs = 0
        for i in range(len(task_ids)):
            for j in range(i + 1, len(task_ids)):
                task_id_1 = task_ids[i]
                task_id_2 = task_ids[j]
                score = float(similarity_matrix[i, j])
                
                # Check if pair already exists
                existing = db.query(TaskSimilarity).filter(
                    or_(
                        and_(TaskSimilarity.task_id_1 == task_id_1, TaskSimilarity.task_id_2 == task_id_2),
                        and_(TaskSimilarity.task_id_1 == task_id_2, TaskSimilarity.task_id_2 == task_id_1)
                    )
                ).first()
                
                if existing:
                    existing.similarity_score = score
                else:
                    similarity = TaskSimilarity(
                        domain=domain,
                        task_id_1=task_id_1,
                        task_id_2=task_id_2,
                        similarity_score=score
                    )
                    db.add(similarity)
                    new_pairs += 1
        
        db.commit()
        logger.info(f"Domain {domain}: Stored {new_pairs} new similarity pairs")
        return True
    
    # =========================================================================
    # ACTION/TOOL SEQUENCE SIMILARITY
    # =========================================================================
    
    def extract_action_sequence(self, tool_sequence: Optional[Dict]) -> str:
        """
        Extract a text representation of the action sequence for embedding
        
        Args:
            tool_sequence: The tool_sequence JSON from the task
            
        Returns:
            String representation of action sequence
        """
        if not tool_sequence:
            return ""
        
        try:
            # Handle different formats
            if isinstance(tool_sequence, str):
                tool_sequence = json.loads(tool_sequence)
            
            # Extract tool names and actions
            actions = []
            
            if isinstance(tool_sequence, dict):
                # Check for nodes/edges format (Task Agent uses 'label' for action names)
                if 'nodes' in tool_sequence:
                    for node in tool_sequence.get('nodes', []):
                        if isinstance(node, dict):
                            # Task Agent format uses 'label', fallback to other common keys
                            tool_name = node.get('label', node.get('tool_name', node.get('name', '')))
                            if tool_name:
                                actions.append(tool_name)
                # Check for actions array
                elif 'actions' in tool_sequence:
                    for action in tool_sequence.get('actions', []):
                        if isinstance(action, dict):
                            actions.append(action.get('tool', action.get('name', '')))
                        elif isinstance(action, str):
                            actions.append(action)
            elif isinstance(tool_sequence, list):
                for item in tool_sequence:
                    if isinstance(item, dict):
                        actions.append(item.get('tool', item.get('tool_name', item.get('name', ''))))
                    elif isinstance(item, str):
                        actions.append(item)
            
            return " -> ".join(filter(None, actions))
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Error parsing tool_sequence: {e}")
            return ""
    
    def get_or_create_action_embedding(self, task_id: int, tool_sequence: Dict, db: Session) -> Optional[np.ndarray]:
        """
        Get existing action embedding from cache or create new one
        
        Args:
            task_id: Task ID
            tool_sequence: The tool sequence JSON
            db: Database session
            
        Returns:
            numpy array of embedding vector, or None if failed
        """
        # Check if embedding exists
        existing = db.query(ActionEmbedding).filter(ActionEmbedding.task_id == task_id).first()
        
        if existing:
            logger.debug(f"Using cached action embedding for task {task_id}")
            return np.array(existing.embedding)
        
        # Extract action sequence text
        action_text = self.extract_action_sequence(tool_sequence)
        if not action_text:
            logger.debug(f"Task {task_id}: No valid action sequence")
            return None
        
        # Generate embedding
        embedding_vector = self.generate_embedding(action_text)
        if embedding_vector is None:
            return None
        
        # Count tools
        tools = action_text.split(" -> ")
        unique_tools = list(set(tools))
        
        # Store in database
        try:
            action_embedding = ActionEmbedding(
                task_id=task_id,
                embedding=embedding_vector.tolist(),
                action_sequence=action_text,
                tool_count=len(tools),
                unique_tools=unique_tools,
                model_name="all-MiniLM-L6-v2"
            )
            db.add(action_embedding)
            db.commit()
            logger.debug(f"Created and cached action embedding for task {task_id}")
            return embedding_vector
        except Exception as e:
            db.rollback()
            
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"Task {task_id}: Action embedding already exists in DB")
                return embedding_vector
            
            logger.error(f"Error storing action embedding for task {task_id}: {e}")
            return embedding_vector
    
    def calculate_action_similarity_for_domain(self, domain: str, db: Session) -> bool:
        """
        Calculate pairwise action similarities for all approved tasks in a domain
        
        Args:
            domain: Domain name to process
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        # Get approved tasks with tool_sequence
        tasks = db.query(Task).filter(
            Task.domain == domain,
            Task.status == 'approved',
            Task.tool_sequence.isnot(None)
        ).all()
        
        if len(tasks) < 2:
            logger.info(f"Domain {domain}: Not enough tasks with tool_sequence for action similarity ({len(tasks)})")
            return True
        
        logger.info(f"Domain {domain}: Processing {len(tasks)} tasks for action similarity")
        
        # Generate embeddings for all tasks
        task_embeddings = {}
        for task in tasks:
            embedding = self.get_or_create_action_embedding(task.id, task.tool_sequence, db)
            if embedding is not None:
                task_embeddings[task.id] = embedding
        
        if len(task_embeddings) < 2:
            logger.warning(f"Domain {domain}: Not enough valid action embeddings ({len(task_embeddings)})")
            return True
        
        logger.info(f"Domain {domain}: Generated {len(task_embeddings)} action embeddings")
        
        # Calculate pairwise similarities
        task_ids = list(task_embeddings.keys())
        embeddings_matrix = np.array([task_embeddings[tid] for tid in task_ids])
        
        # Calculate cosine similarity matrix
        similarity_matrix = cosine_similarity(embeddings_matrix)
        
        # Store similarities
        new_pairs = 0
        for i in range(len(task_ids)):
            for j in range(i + 1, len(task_ids)):
                task_id_1 = task_ids[i]
                task_id_2 = task_ids[j]
                score = float(similarity_matrix[i, j])
                
                # Check if pair already exists
                existing = db.query(ActionSimilarity).filter(
                    or_(
                        and_(ActionSimilarity.task_id_1 == task_id_1, ActionSimilarity.task_id_2 == task_id_2),
                        and_(ActionSimilarity.task_id_1 == task_id_2, ActionSimilarity.task_id_2 == task_id_1)
                    )
                ).first()
                
                if existing:
                    existing.similarity_score = score
                else:
                    similarity = ActionSimilarity(
                        domain=domain,
                        task_id_1=task_id_1,
                        task_id_2=task_id_2,
                        similarity_score=score
                    )
                    db.add(similarity)
                    new_pairs += 1
        
        db.commit()
        logger.info(f"Domain {domain}: Stored {new_pairs} new action similarity pairs")
        return True
    
    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================
    
    def calculate_all_similarities(self, db: Session) -> Dict[str, Any]:
        """
        Calculate similarities for all domains
        
        Args:
            db: Database session
            
        Returns:
            Summary of processing
        """
        # Get all domains with approved tasks
        domains = db.query(Task.domain).filter(
            Task.domain.isnot(None),
            Task.status == 'approved'
        ).distinct().all()
        
        domains = [d[0] for d in domains]
        
        results = {
            "domains_processed": 0,
            "task_similarity_success": 0,
            "action_similarity_success": 0,
            "errors": []
        }
        
        for domain in domains:
            logger.info(f"Processing domain: {domain}")
            
            try:
                if self.calculate_task_similarity_for_domain(domain, db):
                    results["task_similarity_success"] += 1
            except Exception as e:
                logger.error(f"Error calculating task similarity for {domain}: {e}")
                results["errors"].append(f"Task similarity {domain}: {str(e)}")
            
            try:
                if self.calculate_action_similarity_for_domain(domain, db):
                    results["action_similarity_success"] += 1
            except Exception as e:
                logger.error(f"Error calculating action similarity for {domain}: {e}")
                results["errors"].append(f"Action similarity {domain}: {str(e)}")
            
            results["domains_processed"] += 1
        
        return results
    
    # =========================================================================
    # CUSTOM TEXT SIMILARITY SEARCH
    # =========================================================================
    
    def search_similar_by_text(
        self, 
        query_text: str, 
        db: Session, 
        domain: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Find tasks similar to a custom input text
        
        Args:
            query_text: The text to search for similar tasks
            db: Database session
            domain: Optional domain to filter by
            limit: Maximum number of results
            min_similarity: Minimum similarity score threshold
            
        Returns:
            List of similar tasks with similarity scores
        """
        if not query_text or not query_text.strip():
            return []
        
        # Generate embedding for query text
        query_embedding = self.generate_embedding(query_text)
        if query_embedding is None:
            logger.error("Failed to generate embedding for query text")
            return []
        
        # Get tasks with embeddings
        query = db.query(Task, TaskEmbedding).join(
            TaskEmbedding, Task.id == TaskEmbedding.task_id
        ).filter(Task.instruction_text.isnot(None))
        
        if domain:
            query = query.filter(Task.domain == domain)
        
        tasks_with_embeddings = query.all()
        
        if not tasks_with_embeddings:
            logger.info("No tasks with embeddings found")
            return []
        
        # Calculate similarities
        results = []
        for task, embedding in tasks_with_embeddings:
            try:
                task_embedding = np.array(embedding.embedding)
                similarity = float(cosine_similarity(
                    [query_embedding], 
                    [task_embedding]
                )[0][0])
                
                if similarity >= min_similarity:
                    results.append({
                        "task_id": task.id,
                        "task_agent_id": task.task_agent_id,
                        "description": task.description,
                        "instruction_text": task.instruction_text,
                        "domain": task.domain,
                        "status": task.status,
                        "difficulty": task.difficulty,
                        "trainer_name": task.trainer_name,
                        "similarity_score": similarity
                    })
            except Exception as e:
                logger.error(f"Error calculating similarity for task {task.id}: {e}")
                continue
        
        # Sort by similarity score descending
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return results[:limit]
    
    def search_similar_by_action_sequence(
        self, 
        query_text: str, 
        db: Session, 
        domain: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Find tasks with similar action sequences to a custom input
        
        Args:
            query_text: The action sequence text to search for
            db: Database session
            domain: Optional domain to filter by
            limit: Maximum number of results
            min_similarity: Minimum similarity score threshold
            
        Returns:
            List of similar tasks with similarity scores
        """
        if not query_text or not query_text.strip():
            return []
        
        # Generate embedding for query text
        query_embedding = self.generate_embedding(query_text)
        if query_embedding is None:
            logger.error("Failed to generate embedding for query text")
            return []
        
        # Get tasks with action embeddings
        query = db.query(Task, ActionEmbedding).join(
            ActionEmbedding, Task.id == ActionEmbedding.task_id
        ).filter(Task.tool_sequence.isnot(None))
        
        if domain:
            query = query.filter(Task.domain == domain)
        
        tasks_with_embeddings = query.all()
        
        if not tasks_with_embeddings:
            logger.info("No tasks with action embeddings found")
            return []
        
        # Calculate similarities
        results = []
        for task, embedding in tasks_with_embeddings:
            try:
                task_embedding = np.array(embedding.embedding)
                similarity = float(cosine_similarity(
                    [query_embedding], 
                    [task_embedding]
                )[0][0])
                
                if similarity >= min_similarity:
                    results.append({
                        "task_id": task.id,
                        "task_agent_id": task.task_agent_id,
                        "description": task.description,
                        "instruction_text": task.instruction_text,
                        "action_sequence": embedding.action_sequence,
                        "domain": task.domain,
                        "status": task.status,
                        "difficulty": task.difficulty,
                        "trainer_name": task.trainer_name,
                        "similarity_score": similarity
                    })
            except Exception as e:
                logger.error(f"Error calculating similarity for task {task.id}: {e}")
                continue
        
        # Sort by similarity score descending
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return results[:limit]


def run_similarity_calculation():
    """Run similarity calculation from command line"""
    from database_v2 import SessionLocal
    
    db = SessionLocal()
    try:
        service = SimilarityServiceV2()
        results = service.calculate_all_similarities(db)
        
        print("\n" + "=" * 60)
        print("Similarity Calculation Complete")
        print("=" * 60)
        print(f"Domains processed: {results['domains_processed']}")
        print(f"Task similarity success: {results['task_similarity_success']}")
        print(f"Action similarity success: {results['action_similarity_success']}")
        if results['errors']:
            print(f"Errors: {len(results['errors'])}")
            for err in results['errors']:
                print(f"  - {err}")
        print("=" * 60)
        
        return results
    finally:
        db.close()


if __name__ == "__main__":
    run_similarity_calculation()

