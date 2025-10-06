from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Type
from collections import defaultdict

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class MongoDBSchemaInput(BaseModel):
    """Input schema for MongoDBSchemaTool."""
    database_name: Optional[str] = Field(
        default=None, description="MongoDB database name; falls back to env MONGODB_DATABASE"
    )
    sample_size: int = Field(
        default=100, description="Number of documents to sample per collection for schema inference"
    )


class MongoDBSchemaTool(BaseTool):
    name: str = "mongodb_schema_tool"
    description: str = (
        "Connects to MongoDB using connection string, discovers all collections, infers schemas by sampling documents, "
        "detects relationships and references between collections, analyzes indexing patterns, and identifies "
        "data modeling opportunities for optimization (embedding vs referencing, denormalization, etc.)."
    )
    args_schema: Type[BaseModel] = MongoDBSchemaInput

    def _run(self, database_name: Optional[str] = None, sample_size: int = 100) -> Dict[str, Any]:
        connection_string = os.getenv("MONGODB_CONNECTION_STRING")
        resolved_db_name = database_name or os.getenv("MONGODB_DATABASE")

        if not connection_string or not resolved_db_name:
            return {
                "error": "Missing MongoDB credentials. Set MONGODB_CONNECTION_STRING and MONGODB_DATABASE environment variables."
            }

        try:
            # Connect to MongoDB
            client = MongoClient(connection_string, serverSelectionTimeoutMS=10000)
            client.admin.command('ping')  # Test connection
            
            db = client[resolved_db_name]
            
            # Get all collections
            collections = db.list_collection_names()
            
            schema_analysis: Dict[str, Any] = {
                "database": resolved_db_name,
                "total_collections": len(collections),
                "collections": {},
                "detected_relationships": [],
                "modeling_recommendations": [],
            }

            # Analyze each collection
            for collection_name in collections:
                collection = db[collection_name]
                
                # Get collection stats
                try:
                    stats = db.command("collStats", collection_name)
                except OperationFailure:
                    stats = {}
                
                # Sample documents to infer schema
                sample_docs = list(collection.find().limit(sample_size))
                
                # Infer schema from samples
                schema_info = self._infer_schema(sample_docs)
                
                # Get indexes
                indexes = list(collection.list_indexes())
                
                # Detect references to other collections
                references = self._detect_references(sample_docs, collections)
                
                schema_analysis["collections"][collection_name] = {
                    "document_count": stats.get("count", len(sample_docs)),
                    "avg_document_size_bytes": stats.get("avgObjSize", 0),
                    "total_size_bytes": stats.get("size", 0),
                    "storage_size_bytes": stats.get("storageSize", 0),
                    "total_indexes": len(indexes),
                    "indexes": [
                        {
                            "name": idx.get("name"),
                            "keys": idx.get("key"),
                            "unique": idx.get("unique", False),
                        }
                        for idx in indexes
                    ],
                    "inferred_schema": schema_info,
                    "detected_references": references,
                    "sample_size": len(sample_docs),
                }
            
            # Detect relationships between collections
            schema_analysis["detected_relationships"] = self._detect_relationships(schema_analysis["collections"])
            
            # Generate modeling recommendations
            schema_analysis["modeling_recommendations"] = self._generate_modeling_recommendations(
                schema_analysis["collections"], 
                schema_analysis["detected_relationships"]
            )
            
            client.close()
            return schema_analysis
            
        except ConnectionFailure as e:
            return {"error": f"Failed to connect to MongoDB: {str(e)}"}
        except Exception as e:
            return {"error": f"Error analyzing MongoDB schema: {str(e)}"}

    def _infer_schema(self, documents: List[Dict]) -> Dict[str, Any]:
        """Infer schema from sampled documents"""
        if not documents:
            return {"fields": {}, "note": "No documents found"}
        
        field_types: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"types": set(), "null_count": 0, "sample_values": []})
        total_docs = len(documents)
        
        for doc in documents:
            self._analyze_document(doc, field_types, prefix="")
        
        # Convert sets to lists and calculate statistics
        schema = {}
        for field, info in field_types.items():
            types_list = list(info["types"])
            schema[field] = {
                "types": types_list,
                "primary_type": types_list[0] if len(types_list) == 1 else "mixed",
                "nullable": info["null_count"] > 0,
                "null_percentage": round((info["null_count"] / total_docs) * 100, 2),
                "sample_values": info["sample_values"][:5],  # First 5 unique values
            }
        
        return {"fields": schema, "total_fields": len(schema)}

    def _analyze_document(self, doc: Dict, field_types: Dict, prefix: str = ""):
        """Recursively analyze document structure"""
        for key, value in doc.items():
            field_path = f"{prefix}.{key}" if prefix else key
            
            if value is None:
                field_types[field_path]["null_count"] += 1
                field_types[field_path]["types"].add("null")
            elif isinstance(value, dict):
                field_types[field_path]["types"].add("object")
                # Recursively analyze nested object
                self._analyze_document(value, field_types, prefix=field_path)
            elif isinstance(value, list):
                field_types[field_path]["types"].add("array")
                if value and isinstance(value[0], dict):
                    field_types[field_path]["types"].add("array[object]")
                elif value:
                    field_types[field_path]["types"].add(f"array[{type(value[0]).__name__}]")
                # Sample first array element
                if value and len(field_types[field_path]["sample_values"]) < 5:
                    field_types[field_path]["sample_values"].append(str(value[0])[:50])
            else:
                type_name = type(value).__name__
                field_types[field_path]["types"].add(type_name)
                # Store sample values
                if len(field_types[field_path]["sample_values"]) < 5:
                    sample_val = str(value)[:50] if len(str(value)) > 50 else str(value)
                    if sample_val not in field_types[field_path]["sample_values"]:
                        field_types[field_path]["sample_values"].append(sample_val)

    def _detect_references(self, documents: List[Dict], all_collections: List[str]) -> List[Dict[str, Any]]:
        """Detect potential references to other collections"""
        references = []
        
        for doc in documents[:20]:  # Check first 20 docs
            for key, value in doc.items():
                # Check for common reference patterns
                if key.endswith("_id") or key.endswith("Id") or key.endswith("_ref"):
                    potential_collection = key.replace("_id", "").replace("Id", "").replace("_ref", "")
                    
                    # Pluralize to match collection name
                    if potential_collection + "s" in all_collections:
                        references.append({
                            "field": key,
                            "references_collection": potential_collection + "s",
                            "pattern": "foreign_key",
                        })
                    elif potential_collection in all_collections:
                        references.append({
                            "field": key,
                            "references_collection": potential_collection,
                            "pattern": "foreign_key",
                        })
                
                # Check for array of IDs
                if isinstance(value, list) and value and (key.endswith("_ids") or key.endswith("Ids")):
                    potential_collection = key.replace("_ids", "").replace("Ids", "")
                    if potential_collection + "s" in all_collections or potential_collection in all_collections:
                        references.append({
                            "field": key,
                            "references_collection": potential_collection + "s" if potential_collection + "s" in all_collections else potential_collection,
                            "pattern": "one_to_many",
                        })
        
        # Deduplicate
        unique_refs = []
        seen = set()
        for ref in references:
            key = (ref["field"], ref["references_collection"])
            if key not in seen:
                seen.add(key)
                unique_refs.append(ref)
        
        return unique_refs

    def _detect_relationships(self, collections_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect relationships between collections based on references"""
        relationships = []
        
        for coll_name, coll_data in collections_data.items():
            for ref in coll_data.get("detected_references", []):
                relationships.append({
                    "from_collection": coll_name,
                    "to_collection": ref["references_collection"],
                    "field": ref["field"],
                    "relationship_type": ref["pattern"],
                })
        
        return relationships

    def _generate_modeling_recommendations(
        self, collections_data: Dict[str, Any], relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate data modeling recommendations"""
        recommendations = []
        
        for coll_name, coll_data in collections_data.items():
            doc_count = coll_data.get("document_count", 0)
            avg_size = coll_data.get("avg_document_size_bytes", 0)
            
            # Recommendation 1: Missing indexes on reference fields
            reference_fields = [ref["field"] for ref in coll_data.get("detected_references", [])]
            indexed_fields = []
            for idx in coll_data.get("indexes", []):
                indexed_fields.extend(idx["keys"].keys())
            
            for ref_field in reference_fields:
                if ref_field not in indexed_fields and ref_field != "_id":
                    recommendations.append({
                        "collection": coll_name,
                        "type": "missing_index",
                        "priority": "HIGH",
                        "recommendation": f"Create index on '{ref_field}' to optimize JOIN-like queries",
                        "command": f'db.{coll_name}.createIndex({{ "{ref_field}": 1 }})',
                    })
            
            # Recommendation 2: Consider embedding for small related collections
            for rel in relationships:
                if rel["from_collection"] == coll_name:
                    related_coll = rel["to_collection"]
                    if related_coll in collections_data:
                        related_doc_count = collections_data[related_coll].get("document_count", 0)
                        
                        if related_doc_count < 10 and doc_count > 100:
                            recommendations.append({
                                "collection": coll_name,
                                "type": "embedding_opportunity",
                                "priority": "MEDIUM",
                                "recommendation": f"Consider embedding '{related_coll}' documents into '{coll_name}' to reduce lookups (related collection is small: {related_doc_count} docs)",
                                "benefit": "Reduces number of queries, improves read performance",
                            })
            
            # Recommendation 3: Large documents might need to be split
            if avg_size > 5000:  # > 5KB average
                recommendations.append({
                    "collection": coll_name,
                    "type": "document_size",
                    "priority": "MEDIUM",
                    "recommendation": f"Average document size is {avg_size} bytes. Consider splitting large fields into separate collections or using GridFS for binary data.",
                    "benefit": "Reduces memory usage, improves query performance",
                })
            
            # Recommendation 4: Check for denormalization opportunities
            schema_fields = coll_data.get("inferred_schema", {}).get("fields", {})
            array_fields = [f for f, info in schema_fields.items() if "array" in str(info.get("types", []))]
            
            if len(array_fields) > 3:
                recommendations.append({
                    "collection": coll_name,
                    "type": "denormalization_review",
                    "priority": "LOW",
                    "recommendation": f"Collection has {len(array_fields)} array fields. Review if these should be separate collections with proper indexing.",
                    "array_fields": array_fields,
                })
        
        return recommendations

