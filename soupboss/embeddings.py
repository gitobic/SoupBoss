"""
Ollama client for generating embeddings using nomic-embed-text model.
"""

import ollama
import numpy as np
from typing import List, Optional, Union
import time
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import requests.exceptions
from .config import get_config_manager

console = Console()


class OllamaEmbeddingClient:
    """Client for generating embeddings using Ollama with nomic-embed-text model."""
    
    def __init__(self, 
                 host: Optional[str] = None,
                 model: Optional[str] = None,
                 timeout: Optional[int] = None):
        config = get_config_manager()
        
        # Use config values if not explicitly provided
        if host is None:
            host = f"http://{config.get('ollama', 'host')}:{config.get('ollama', 'port')}"
        if model is None:
            model = config.get('ollama', 'model')
        if timeout is None:
            timeout = config.get('ollama', 'timeout')
        self.host = host
        self.model = model
        self.timeout = timeout
        self.client = ollama.Client(host=host, timeout=timeout)
        self._model_ready = None
    
    def test_connection(self) -> bool:
        """Test if Ollama server is accessible."""
        try:
            # Try to list models to test connection
            self.client.list()
            return True
        except Exception as e:
            console.print(f"[red]Ollama connection failed: {e}[/red]")
            return False
    
    def ensure_model_ready(self) -> bool:
        """Ensure the embedding model is available."""
        if self._model_ready is not None:
            return self._model_ready
        
        try:
            # Check if model is already available
            models = self.client.list()
            model_names = [model.get('name', model.get('model', '')) for model in models.get('models', [])]
            
            if self.model in model_names or f"{self.model}:latest" in model_names:
                self._model_ready = True
                console.print(f"[green]✓ Model {self.model} is ready[/green]")
                return True
            
            # Model not found, try to pull it
            console.print(f"[yellow]Pulling model {self.model}... This may take a while.[/yellow]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
            ) as progress:
                task = progress.add_task(f"Downloading {self.model}", total=None)
                
                try:
                    self.client.pull(self.model)
                    progress.update(task, description="Model downloaded successfully")
                    self._model_ready = True
                    console.print(f"[green]✓ Model {self.model} is now ready[/green]")
                    return True
                except Exception as e:
                    progress.update(task, description=f"Failed to download model: {e}")
                    self._model_ready = False
                    return False
                    
        except Exception as e:
            console.print(f"[red]Error checking model availability: {e}[/red]")
            self._model_ready = False
            return False
    
    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for a single text."""
        if not self.ensure_model_ready():
            return None
        
        try:
            # Clean and prepare text
            cleaned_text = self._clean_text(text)
            if not cleaned_text.strip():
                console.print("[yellow]Warning: Empty text provided for embedding[/yellow]")
                return None
            
            # Generate embedding
            response = self.client.embeddings(model=self.model, prompt=cleaned_text)
            
            if 'embedding' in response and response['embedding']:
                embedding = np.array(response['embedding'], dtype=np.float32)
                return embedding
            else:
                console.print("[red]No embedding returned from Ollama[/red]")
                return None
                
        except Exception as e:
            console.print(f"[red]Error generating embedding: {e}[/red]")
            return None
    
    def generate_embeddings_batch(self, texts: List[str], 
                                  show_progress: bool = True) -> List[Optional[np.ndarray]]:
        """Generate embeddings for multiple texts with progress tracking."""
        if not self.ensure_model_ready():
            return [None] * len(texts)
        
        embeddings = []
        
        if show_progress and len(texts) > 1:
            with Progress() as progress:
                task = progress.add_task("Generating embeddings...", total=len(texts))
                
                for i, text in enumerate(texts):
                    embedding = self.generate_embedding(text)
                    embeddings.append(embedding)
                    progress.update(task, advance=1)
        else:
            for text in texts:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
        
        return embeddings
    
    def _clean_text(self, text: str) -> str:
        """Clean and prepare text for embedding generation."""
        if not text:
            return ""
        
        # Remove excessive whitespace
        cleaned = " ".join(text.split())
        
        # Truncate if too long (models have token limits)
        # nomic-embed-text can handle ~8192 tokens, roughly 32k characters
        max_chars = 30000
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars] + "..."
            console.print(f"[yellow]Text truncated to {max_chars} characters[/yellow]")
        
        return cleaned
    
    def get_model_info(self) -> dict:
        """Get information about the current model."""
        try:
            if not self.ensure_model_ready():
                return {"error": "Model not available"}
            
            models = self.client.list()
            for model in models.get('models', []):
                model_name = model.get('name', model.get('model', ''))
                if model_name == self.model or model_name == f"{self.model}:latest":
                    return {
                        "name": model_name,
                        "size": model.get('size', 'Unknown'),
                        "modified_at": model.get('modified_at', 'Unknown'),
                        "ready": True
                    }
            
            return {"error": "Model not found"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_status(self) -> dict:
        """Get comprehensive status of the Ollama client."""
        status = {
            "host": self.host,
            "model": self.model,
            "connection": False,
            "model_ready": False,
            "error": None
        }
        
        # Test connection
        try:
            self.client.list()
            status["connection"] = True
        except Exception as e:
            status["error"] = f"Connection failed: {e}"
            return status
        
        # Check model readiness
        try:
            status["model_ready"] = self.ensure_model_ready()
            if status["model_ready"]:
                status["model_info"] = self.get_model_info()
        except Exception as e:
            status["error"] = f"Model check failed: {e}"
        
        return status


def get_embedding_client(host: Optional[str] = None, 
                        model: Optional[str] = None) -> OllamaEmbeddingClient:
    """Get an embedding client instance."""
    return OllamaEmbeddingClient(host=host, model=model)


def test_embedding_client(text: str = "This is a test sentence for embedding generation.") -> bool:
    """Test the embedding client functionality."""
    console.print("[cyan]Testing Ollama embedding client...[/cyan]")
    
    client = get_embedding_client()
    
    # Test connection
    if not client.test_connection():
        console.print("[red]✗ Connection test failed[/red]")
        return False
    
    console.print("[green]✓ Connection successful[/green]")
    
    # Test model availability
    if not client.ensure_model_ready():
        console.print("[red]✗ Model not ready[/red]")
        return False
    
    # Test embedding generation
    embedding = client.generate_embedding(text)
    if embedding is None:
        console.print("[red]✗ Embedding generation failed[/red]")
        return False
    
    console.print(f"[green]✓ Generated embedding with shape: {embedding.shape}[/green]")
    console.print(f"[green]✓ Embedding client test passed![/green]")
    
    return True