#!/usr/bin/env python3
"""
Test script for RAG AI Agent API
"""

import requests
import json
import time
from typing import Dict, Any


class RAGAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def test_health(self) -> Dict[str, Any]:
        """Test health endpoint"""
        print("\n=== Testing Health Endpoint ===")
        response = requests.get(f"{self.base_url}/api/v1/rag/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_index(self, directory: str = None) -> Dict[str, Any]:
        """Test document indexing"""
        print("\n=== Testing Index Endpoint ===")
        payload = {"directory": directory} if directory else {}
        response = requests.post(
            f"{self.base_url}/api/v1/rag/index",
            json=payload
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_query(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Test query endpoint"""
        print(f"\n=== Testing Query Endpoint ===")
        print(f"Query: {query}")
        params = {
            "query": query,
            "limit": limit
        }
        response = requests.get(
            f"{self.base_url}/api/v1/rag/query",
            params=params
        )
        print(f"Status Code: {response.status_code}")
        result = response.json()
        
        # Print formatted results
        print(f"\nAnswer: {result.get('answer', 'No answer')}")
        print(f"\nTop Results ({result.get('total_results', 0)} total):")
        
        for i, res in enumerate(result.get('results', [])[:3], 1):
            print(f"\n{i}. Score: {res.get('similarity_score', 0):.3f}")
            print(f"   Content: {res.get('content', '')[:200]}...")
            print(f"   Source: {res.get('metadata', {}).get('file_name', 'Unknown')}")
        
        return result
    
    def test_stats(self) -> Dict[str, Any]:
        """Test stats endpoint"""
        print("\n=== Testing Stats Endpoint ===")
        response = requests.get(f"{self.base_url}/api/v1/rag/stats")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def run_all_tests(self):
        """Run all tests"""
        print("Starting RAG API Tests...")
        
        # Test health
        self.test_health()
        
        # Test indexing
        print("\nIndexing documents...")
        index_result = self.test_index()
        
        if index_result.get("status") == "success":
            # Wait for indexing to complete
            time.sleep(2)
            
            # Test stats
            self.test_stats()
            
            # Test queries
            test_queries = [
                "What is RAG?",
                "What file formats are supported?",
                "How does the system work?",
                "What are the benefits of using this system?",
                "Tell me about the architecture"
            ]
            
            for query in test_queries:
                time.sleep(1)  # Rate limiting
                self.test_query(query, limit=5)
        else:
            print("Indexing failed, skipping query tests")


if __name__ == "__main__":
    # Create tester instance
    tester = RAGAPITester()
    
    # Run all tests
    try:
        tester.run_all_tests()
        print("\n=== All tests completed ===")
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to API. Make sure the server is running.")
        print("Start the server with: python app.py")
    except Exception as e:
        print(f"\nError during testing: {str(e)}")