import os
import asyncio
from typing import List, Optional, Dict
from dotenv import load_dotenv
import chromadb

from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool

from app.utils.web_loader import load_website_flexibly, clean_content

class RAGService:
    def __init__(self):
        load_dotenv()
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        self.llm = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        
        # Store vector stores per user
        self.user_vector_stores: Dict[str, Chroma] = {}
        self.user_agent_executors: Dict[str, any] = {}
        self.memory = MemorySaver()
        
        self.chroma_client = chromadb.HttpClient(
            ssl=True,
            host='api.trychroma.com',
            tenant=os.getenv("CHROMA_TENANT"),
            database='rag_collection',
            headers={
                'x-chroma-token': os.getenv("CHROMA_API_KEY"),
            }
        )
    
    def _get_collection_name(self, user_id: str) -> str:
        """Generate collection name based on user ID."""
        # Sanitize user ID for collection name (ChromaDB has naming restrictions)
        sanitized_id = user_id.replace("-", "_").replace("@", "_at_")
        return f"user_{sanitized_id}_rag"

    async def load_website(self, user_id: str, urls: List[str]) -> str:
        """Load and index a website for a specific user."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._load_website_sync, user_id, urls
        )

    def _load_website_sync(self, user_id: str, urls: List[str]) -> str:
        """Load and index a website synchronously for a specific user."""
        all_docs = []
        successful_urls = []
        failed_urls = []
        
        try:
            # Process each URL and collect results
            for url in urls:
                try:
                    docs = load_website_flexibly(url)
                    if docs:
                        all_docs.extend(docs)  # Use extend instead of +=
                        successful_urls.append(url)
                        print(f"Loaded {len(docs)} documents from {url}")
                    else:
                        failed_urls.append(url)
                        print(f"No content found at {url}")
                except Exception as e:
                    failed_urls.append(url)
                    print(f"Error loading {url}: {str(e)}")
            
            # Check if we got any documents at all
            if not all_docs:
                if failed_urls:
                    return f"Failed to load content from any of the provided URLs: {', '.join(failed_urls)}"
                else:
                    return "No content found at any of the provided URLs"
            
            # Clean documents
            for doc in all_docs:
                doc.page_content = clean_content(doc.page_content)
            
            collection_name = self._get_collection_name(user_id)
            
            # Delete existing collection if it exists
            if user_id in self.user_vector_stores:
                try:
                    self.user_vector_stores[user_id].delete_collection()
                except Exception as e:
                    print(f"Warning: Could not delete existing collection: {e}")
            
            # Create new vector store for this user
            self.user_vector_stores[user_id] = Chroma(
                client=self.chroma_client,
                collection_name=collection_name,
                embedding_function=self.embeddings,
            )
            
            # Split and filter documents
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=50,
                add_start_index=True,
            )
            all_splits = text_splitter.split_documents(all_docs)
            
            print(f"Total documents after splitting: {len(all_splits)}")
            # Filter chunks
            filtered_splits = [
                split for split in all_splits
                if len(split.page_content.strip()) > 50
                and not split.page_content.startswith('System message:')
                and 'Conversatin samples:' not in split.page_content
            ]
            
            # Index documents
            document_ids = self.user_vector_stores[user_id].add_documents(documents=filtered_splits)
            
            # Initialize agent executor for this user
            self._initialize_agent(user_id)
            
            # Create success message
            success_msg = f"Successfully loaded and indexed {len(document_ids)} documents"
            if successful_urls:
                success_msg += f" from {len(successful_urls)} URLs: {', '.join(successful_urls)}"
            
            if failed_urls:
                success_msg += f"\n⚠️ Failed to load {len(failed_urls)} URLs: {', '.join(failed_urls)}"
            
            print(success_msg)
            return success_msg
        
        except Exception as e:
            return f"Error loading websites: {str(e)}"
    
    def _initialize_agent(self, user_id: str):
        """Initialize the agent executor with the retrieve tool for a specific user."""
        vector_store = self.user_vector_stores.get(user_id)
        
        @tool(response_format="content_and_artifact")
        def retrieve(query: str):
            """Retrieve information related to a query."""
            if not vector_store:
                return "Vector store not initialized. Please load a website first.", []
            
            retrieved_docs = vector_store.similarity_search(query, k=2)
            serialized = "\n\n".join(
                (f"Source: {doc.metadata}\nContent: {doc.page_content}")
                for doc in retrieved_docs
            )
            return serialized, retrieved_docs
        
        self.user_agent_executors[user_id] = create_react_agent(
            self.llm, 
            [retrieve], 
            checkpointer=self.memory
        )
        
        print(f"Initialized RAG agent for user {user_id} with collection {self._get_collection_name(user_id)}")
    
    async def query(self, user_id: str, question: str) -> str:
        """Query the RAG system with a question for a specific user."""
        print(f"Querying RAG for user {user_id}: {question}")
        if user_id not in self.user_agent_executors:
            return "RAG agent not initialized for this user. Please load a website first."
        
        try:
            config = {"configurable": {"thread_id": f"user_{user_id}_session"}}
            
            response_parts = []
            async for event in self.user_agent_executors[user_id].astream(
                {"messages": [{"role": "user", "content": question}]},
                config=config,
            ):
                if "agent" in event and event["agent"]:
                    agent_data = event["agent"]
                    if "messages" in agent_data and agent_data['messages']:
                        last_msg = agent_data['messages'][-1]
                        if hasattr(last_msg, 'content'):
                            response_parts.append(last_msg.content)

            print(f"RAG response for user {user_id}: {response_parts}")
            return response_parts[-1] if response_parts else "No response generated"
        
        except Exception as e:
            return f"Error processing query: {str(e)}"
    
    def has_user_data(self, user_id: str) -> bool:
        """Check if user has loaded data."""
        return user_id in self.user_vector_stores
    
    def clear_user_data(self, user_id: str) -> bool:
        """Clear user's RAG data."""
        try:
            if user_id in self.user_vector_stores:
                self.user_vector_stores[user_id].delete_collection()
                del self.user_vector_stores[user_id]
            
            if user_id in self.user_agent_executors:
                del self.user_agent_executors[user_id]
            
            return True
        except Exception as e:
            print(f"Error clearing user data: {e}")
            return False

# Global RAG service instance
rag_service = RAGService()