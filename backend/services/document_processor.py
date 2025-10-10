import os
import PyPDF2
from docx import Document
import pandas as pd
import logging
from typing import List, Dict, Any
import uuid
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        # Defer model loading to first use to avoid blocking app startup
        self._model_name = model_name
        self.model = None
        self.documents = {}
        self.embeddings = {}
        
    def process_documents(self, file_paths: List[str]) -> Dict[str, Any]:
        """Process multiple document types"""
        results = {
            "processed": [],
            "failed": [],
            "total": len(file_paths)
        }
        
        for file_path in file_paths:
            try:
                doc_id = str(uuid.uuid4())
                content = self._extract_text(file_path)
                chunks = self.dynamic_chunking(content, os.path.splitext(file_path)[1])
                
                # Generate embeddings for chunks (ensure model is loaded)
                if self.model is None:
                    try:
                        self.model = SentenceTransformer(self._model_name)
                    except Exception as e:
                        logger.error(f"Failed to load embedding model: {e}")
                        raise
                chunk_embeddings = self.model.encode(chunks, batch_size=32, show_progress_bar=False)
                
                self.documents[doc_id] = {
                    "file_path": file_path,
                    "content": content,
                    "chunks": chunks,
                    "chunk_embeddings": chunk_embeddings,
                    "processed_at": "2024-01-01T00:00:00Z"  # Placeholder
                }
                
                results["processed"].append({
                    "doc_id": doc_id,
                    "file_name": os.path.basename(file_path),
                    "chunk_count": len(chunks),
                    "status": "success"
                })
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                results["failed"].append({
                    "file_name": os.path.basename(file_path),
                    "error": str(e)
                })
        
        return results
    
    def _extract_text(self, file_path: str) -> str:
        """Extract text from various file formats"""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return self._extract_pdf(file_path)
        elif ext == '.docx':
            return self._extract_docx(file_path)
        elif ext == '.txt':
            return self._extract_txt(file_path)
        elif ext == '.csv':
            return self._extract_csv(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    
    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF"""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""
    
    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX"""
        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            return ""
    
    def _extract_txt(self, file_path: str) -> str:
        """Extract text from TXT"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f"TXT extraction failed: {e}")
            return ""
    
    def _extract_csv(self, file_path: str) -> str:
        """Extract text from CSV"""
        try:
            df = pd.read_csv(file_path)
            return df.to_string()
        except Exception as e:
            logger.error(f"CSV extraction failed: {e}")
            return ""
    
    def dynamic_chunking(self, content: str, doc_type: str) -> List[str]:
        """Intelligent chunking based on document structure"""
        if not content:
            return []
        
        # Basic chunking by paragraphs/sentences
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        chunks = []
        
        if doc_type.lower() in ['.pdf', '.docx']:
            # For resumes and documents, try to preserve sections
            current_chunk = ""
            for paragraph in paragraphs:
                if len(current_chunk) + len(paragraph) < 1000:  # Rough token estimate
                    current_chunk += paragraph + "\n\n"
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = paragraph + "\n\n"
            
            if current_chunk:
                chunks.append(current_chunk.strip())
        else:
            # For other documents, use simpler chunking
            chunks = paragraphs
        
        # Ensure chunks aren't too large
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > 2000:
                # Split large chunks by sentences
                sentences = chunk.split('. ')
                temp_chunk = ""
                for sentence in sentences:
                    if len(temp_chunk) + len(sentence) < 1000:
                        temp_chunk += sentence + ". "
                    else:
                        if temp_chunk:
                            final_chunks.append(temp_chunk.strip())
                        temp_chunk = sentence + ". "
                if temp_chunk:
                    final_chunks.append(temp_chunk.strip())
            else:
                final_chunks.append(chunk)
        
        return final_chunks
    
    def search_documents(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search documents using vector similarity"""
        if not self.documents:
            return []
        
        # Ensure model loaded and encode query
        if self.model is None:
            try:
                self.model = SentenceTransformer(self._model_name)
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                return []
        query_embedding = self.model.encode([query])
        
        results = []
        for doc_id, doc_info in self.documents.items():
            for i, chunk_embedding in enumerate(doc_info["chunk_embeddings"]):
                similarity = np.dot(query_embedding[0], chunk_embedding) / (
                    np.linalg.norm(query_embedding[0]) * np.linalg.norm(chunk_embedding)
                )
                
                results.append({
                    "doc_id": doc_id,
                    "file_name": os.path.basename(doc_info["file_path"]),
                    "chunk_index": i,
                    "content": doc_info["chunks"][i],
                    "similarity": float(similarity)
                })
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]