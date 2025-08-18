import os
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd
import json
import xml.etree.ElementTree as ET
from langchain.document_loaders import (
    TextLoader,
    UnstructuredFileLoader,
    UnstructuredMarkdownLoader,
    UnstructuredHTMLLoader,
    JSONLoader,
    CSVLoader,
    UnstructuredXMLLoader,
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document


class DocumentParser:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        
        self.file_loaders = {
            '.txt': TextLoader,
            '.md': UnstructuredMarkdownLoader,
            '.pdf': PyPDFLoader,
            '.docx': Docx2txtLoader,
            '.doc': UnstructuredFileLoader,
            '.pptx': UnstructuredPowerPointLoader,
            '.ppt': UnstructuredPowerPointLoader,
            '.xlsx': UnstructuredExcelLoader,
            '.xls': UnstructuredExcelLoader,
            '.csv': CSVLoader,
            '.json': self._load_json,
            '.xml': UnstructuredXMLLoader,
            '.html': UnstructuredHTMLLoader,
            '.htm': UnstructuredHTMLLoader,
            '.rtf': UnstructuredFileLoader,
            '.odt': UnstructuredFileLoader
        }
    
    def _load_json(self, file_path: str) -> List[Document]:
        """Custom JSON loader"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        text = json.dumps(data, indent=2)
        metadata = {"source": file_path, "file_type": "json"}
        return [Document(page_content=text, metadata=metadata)]
    
    def parse_file(self, file_path: str) -> List[Document]:
        """Parse a single file and return documents"""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension not in self.file_loaders:
            print(f"Unsupported file type: {file_extension}")
            return []
        
        try:
            loader_class = self.file_loaders[file_extension]
            
            if callable(loader_class) and loader_class.__name__ == '_load_json':
                documents = loader_class(self, file_path)
            else:
                loader = loader_class(file_path)
                documents = loader.load()
            
            # Split documents into chunks
            split_documents = self.text_splitter.split_documents(documents)
            
            # Add metadata
            for doc in split_documents:
                doc.metadata.update({
                    "file_path": file_path,
                    "file_type": file_extension[1:],
                    "file_name": Path(file_path).name
                })
            
            return split_documents
            
        except Exception as e:
            print(f"Error parsing {file_path}: {str(e)}")
            return []
    
    def parse_directory(self, directory_path: str) -> List[Document]:
        """Parse all supported files in a directory"""
        all_documents = []
        supported_extensions = tuple(self.file_loaders.keys())
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith(supported_extensions):
                    file_path = os.path.join(root, file)
                    print(f"Parsing: {file_path}")
                    documents = self.parse_file(file_path)
                    all_documents.extend(documents)
        
        print(f"Total documents parsed: {len(all_documents)}")
        return all_documents