from typing import Dict, Set

class RAGStateManager:
    def __init__(self):
        self.rag_enabled_users: Set[str] = set()
        self.user_urls: Dict[str, str] = {}
    
    def enable_rag_for_user(self, user_id: str, url: str):
        """Enable RAG mode for a user with a specific URL."""
        self.rag_enabled_users.add(user_id)
        self.user_urls[user_id] = url
    
    def disable_rag_for_user(self, user_id: str):
        """Disable RAG mode for a user."""
        self.rag_enabled_users.discard(user_id)
        self.user_urls.pop(user_id, None)
    
    def is_rag_enabled(self, user_id: str) -> bool:
        """Check if RAG is enabled for a user."""
        return user_id in self.rag_enabled_users
    
    def get_user_url(self, user_id: str) -> str:
        """Get the URL associated with a user."""
        return self.user_urls.get(user_id, "")

# Global state manager
rag_state = RAGStateManager()