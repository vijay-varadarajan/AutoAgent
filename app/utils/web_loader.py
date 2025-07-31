from dotenv import load_dotenv
import os
import bs4
from langchain import hub
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import START, StateGraph
from typing_extensions import List, TypedDict
import re
from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from functools import partial

import ssl
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load and chunk contents of the website - FLEXIBLE APPROACH
def load_website_flexibly(url):
    print(f"Loading website content from {url}...")
    """Load website content using multiple fallback strategies"""
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Strategy 1: Try common content selectors
    content_selectors = [
        ("main", "main"),
        ("article", "article"), 
        ("content", "content"),
        ("main-content", "main-content"),
        ("post-content", "post-content"),
        ("entry-content", "entry-content"),
        ("container", "container"),
    ]
    
    best_content = ""
    best_length = 0
    
    for class_name, description in content_selectors:
        try:
            if class_name in ["main", "article"]:
                # Tag selector
                loader = WebBaseLoader(
                    web_paths=(url,),
                    bs_kwargs={"parse_only": bs4.SoupStrainer(class_name)},
                    header_template={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    },
                    verify_ssl=False  # Disable SSL verification
                )
            else:
                # Class selector
                loader = WebBaseLoader(
                    web_paths=(url,),
                    bs_kwargs={"parse_only": bs4.SoupStrainer(class_=class_name)},
                    header_template={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    },
                    verify_ssl=False  # Disable SSL verification
                )
            
            docs = loader.load()
            
            if docs and len(docs[0].page_content) > best_length:
                best_content = docs[0].page_content
                best_length = len(best_content)
                print(f"Best content found with: {description} ({best_length} chars)")
                
        except Exception as e:
            print(f"Selector {class_name} failed: {e}")
            continue
    
    # Strategy 2: If no good content found, try without strainer
    if best_length < 500:  # If content is too short
        print("Trying without strainer (full page content)...")
        try:
            loader = WebBaseLoader(
                web_paths=(url,),
                header_template={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                },
                verify_ssl=False  # Disable SSL verification
            )
            docs = loader.load()
            if docs:
                best_content = docs[0].page_content
                best_length = len(best_content)
                print(f"Full page content: {best_length} chars")
        except Exception as e:
            print(f"Full page loading failed: {e}")
    
    # Strategy 3: Try with requests and BeautifulSoup directly as fallback
    if best_length < 100:
        print("Trying direct requests approach...")
        try:
            import requests
            from bs4 import BeautifulSoup
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            # Make request with SSL verification disabled
            response = requests.get(url, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to extract meaningful content
            content_tags = ['main', 'article', '.content', '.main-content', 'body']
            for tag in content_tags:
                if tag.startswith('.'):
                    # Class selector
                    elements = soup.find_all(class_=tag[1:])
                else:
                    # Tag selector
                    elements = soup.find_all(tag)
                
                if elements:
                    content = ' '.join([elem.get_text(strip=True) for elem in elements])
                    if len(content) > best_length:
                        best_content = content
                        best_length = len(content)
                        break
            
            # If still no good content, get all text
            if best_length < 500:
                best_content = soup.get_text(strip=True)
                best_length = len(best_content)
                
            print(f"Direct requests content: {best_length} chars")
            
        except Exception as e:
            print(f"Direct requests approach failed: {e}")
    
    
    print(f"Final content length: {best_length} chars")
    if best_content:
        return [Document(page_content=best_content, metadata={"source": url})]
    else:
        raise ValueError(f"Could not extract content from {url}")


# Clean the content to remove unwanted patterns
def clean_content(text):
    # Split into lines for better processing
    lines = text.split('\n')
    cleaned_lines = []
    
    skip_until_empty = False
    print(f"Original content length: {len(lines)} lines")
    
    for line in lines:
        line = line.strip()
        
        # Skip system messages and related content
        if any(phrase in line for phrase in [
            'System message:',
            'Conversatin samples:',
            '"role": "system"',
            'Python toolbelt preferences:',
            '{"role"',
            '"content":'
        ]):
            skip_until_empty = True
            continue
            
        # Reset skip flag on empty line
        if not line and skip_until_empty:
            skip_until_empty = False
            continue
            
        # Skip lines while in skip mode
        if skip_until_empty:
            continue
            
        # Keep meaningful content
        if line and len(line) > 10:  # Only keep substantial lines
            cleaned_lines.append(line)
    
    print(f"Cleaned content length: {len(cleaned_lines)} lines")
    return '\n\n'.join(cleaned_lines)

# Define state for application
class State(TypedDict):
    question: str
    context: List[Document]
    answer: str

# Define application steps
def retrieve(state: State, vector_store: Chroma):
    retrieved_docs = vector_store.similarity_search(
        state["question"],
        k=8,
    )
    
    unique_docs = []
    seen_content = set()
    
    for doc in retrieved_docs:
        # Use first 100 chars as identifier
        content_hash = doc.page_content[:100]
        if content_hash not in seen_content:
            unique_docs.append(doc)
            seen_content.add(content_hash)
            if len(unique_docs) >= 4:  # Limit to 4 unique docs
                break
    
    return {"context": unique_docs}

def generate(state: State, llm, custom_prompt):
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])
    messages = custom_prompt.invoke({"question": state["question"], "context": docs_content})
    response = llm.invoke(messages)
    return {"answer": response.content}


def main():
    """
    Main function to run the RAG application.
    """
    load_dotenv()  # take environment variables from .env.

    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    os.environ["LANGSMITH_TRACING"] = "true"

    llm = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

    # Initialize Chroma with a persistent directory and delete old collection
    vector_store = Chroma(
        collection_name="rag_collection",
        embedding_function=embeddings,
        persist_directory="./chroma_langchain_db",
    )
    try:
        vector_store.delete_collection()
    except Exception as e:
        print(f"Could not delete collection (it may not exist): {e}")

    # Recreate the vector store to ensure it's a fresh instance
    vector_store = Chroma(
        collection_name="rag_collection",
        embedding_function=embeddings,
        persist_directory="./chroma_langchain_db",
    )

    # Load your portfolio content
    url = "https://vijayvaradarajan.co"
    docs = load_website_flexibly(url)

    # Clean the loaded documents
    print(f"Total documents loaded: {len(docs)}")
    for doc in docs:
        doc.page_content = clean_content(doc.page_content)

    print(f"Total characters after cleaning: {len(docs[0].page_content)}")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # chunk size (characters)
        chunk_overlap=50,  # chunk overlap (characters)
        add_start_index=True,  # track index in original document
    )
    all_splits = text_splitter.split_documents(docs)

    # Filter out chunks that are too short or contain unwanted content
    filtered_splits = []
    for split in all_splits:
        content = split.page_content.strip()
        
        if (len(content) > 50 and 
            not content.startswith('System message:') and
            'Conversatin samples:' not in content and
            '"role": "system"' not in content and
            'Python toolbelt preferences:' not in content):
            filtered_splits.append(split)

    print(f"Split blog post into {len(filtered_splits)} sub-documents after filtering.")

    # Index chunks
    document_ids = vector_store.add_documents(documents=filtered_splits)
    print(f"Indexed {len(document_ids)} documents")

    custom_prompt = ChatPromptTemplate.from_template("""
You are an expert AI assistant specializing in answering questions about AI agents, LLMs, and related topics.

Context Information:
{context}

User Question: {question}

Instructions:
1. Carefully analyze the provided context to find relevant information
2. Answer the question comprehensively based on the context
3. If the context contains multiple relevant sections, synthesize them into a coherent response
4. If the context doesn't contain sufficient information, clearly state this limitation
5. Use technical terms appropriately and explain complex concepts when necessary
6. Provide specific examples from the context when they help illustrate your answer

Response:
""")

    # Define application graph
    graph_builder = StateGraph(State)
    
    # Use functools.partial to pass arguments to nodes
    graph_builder.add_node("retrieve", partial(retrieve, vector_store=vector_store))
    graph_builder.add_node("generate", partial(generate, llm=llm, custom_prompt=custom_prompt))
    
    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "generate")
    
    graph = graph_builder.compile()

    # Test the RAG system
    response = graph.invoke({"question": "What are Vijay's experiences"})
    print("\n" + "="*50)
    print("RETRIEVED CONTEXT:")
    print("="*50)
    for i, doc in enumerate(response['context'], 1):
        print(f"Document {i}:")
        print(f"Content preview: {doc.page_content[:200]}...")
        print("-" * 30)

    print("\n" + "="*50)
    print("GENERATED ANSWER:")
    print("="*50)
    print(response['answer'])

if __name__ == "__main__":
    main()