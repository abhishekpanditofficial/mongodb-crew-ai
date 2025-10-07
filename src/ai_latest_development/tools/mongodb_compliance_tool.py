from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Type, ClassVar, Pattern
from datetime import datetime, timedelta

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class MongoDBComplianceInput(BaseModel):
    """Input schema for MongoDBComplianceTool."""
    database_name: Optional[str] = Field(
        default=None, description="MongoDB database name; falls back to env MONGODB_DATABASE"
    )
    sample_size: int = Field(
        default=50, description="Number of documents to sample per collection for compliance scanning (reduced for performance)"
    )


class MongoDBComplianceTool(BaseTool):
    name: str = "mongodb_compliance_tool"
    description: str = (
        "Scans MongoDB collections for data compliance violations, PII exposure, sensitive data storage, "
        "GDPR/PCI-DSS/HIPAA violations, plaintext passwords, API keys, credit card numbers, and data retention issues. "
        "Detects fields that should not be stored or need encryption/hashing."
    )
    args_schema: Type[BaseModel] = MongoDBComplianceInput

    # Regex patterns for sensitive data detection
    EMAIL_PATTERN: ClassVar[Pattern] = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN: ClassVar[Pattern] = re.compile(r'\b(\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b')
    SSN_PATTERN: ClassVar[Pattern] = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    CREDIT_CARD_PATTERN: ClassVar[Pattern] = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
    API_KEY_PATTERN: ClassVar[Pattern] = re.compile(r'\b[A-Za-z0-9_-]{32,}\b')
    JWT_PATTERN: ClassVar[Pattern] = re.compile(r'\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b')
    
    # Sensitive field names (case-insensitive)
    SENSITIVE_FIELD_NAMES: ClassVar[set] = {
        'password', 'pwd', 'passwd', 'secret', 'token', 'api_key', 'apikey', 
        'access_token', 'refresh_token', 'private_key', 'privatekey', 'ssn', 
        'social_security', 'credit_card', 'creditcard', 'cvv', 'card_number',
        'bank_account', 'routing_number', 'health_record', 'medical_record',
        'diagnosis', 'prescription', 'insurance_id'
    }
    
    # PII field names
    PII_FIELD_NAMES: ClassVar[set] = {
        'email', 'phone', 'phone_number', 'mobile', 'address', 'street_address',
        'zip', 'zipcode', 'postal_code', 'dob', 'date_of_birth', 'birthdate',
        'passport', 'driver_license', 'ssn', 'tax_id', 'national_id'
    }

    def _run(self, database_name: Optional[str] = None, sample_size: int = 50) -> Dict[str, Any]:
        connection_string = os.getenv("MONGODB_CONNECTION_STRING")
        resolved_db_name = database_name or os.getenv("MONGODB_DATABASE")

        if not connection_string or not resolved_db_name:
            return {
                "error": "Missing MongoDB credentials. Set MONGODB_CONNECTION_STRING and MONGODB_DATABASE."
            }

        try:
            client = MongoClient(connection_string, serverSelectionTimeoutMS=10000)
            
            # Test connection and check authorization
            try:
                client.admin.command('ping')
            except Exception as e:
                return {
                    "error": f"Cannot connect to MongoDB: {str(e)}. Check connection string."
                }
            
            db = client[resolved_db_name]
            
            # Test database access with better error handling
            try:
                collections = db.list_collection_names()
                if not collections:
                    return {
                        "error": f"No collections found in database '{resolved_db_name}' or insufficient permissions."
                    }
            except Exception as e:
                return {
                    "error": f"Cannot access database '{resolved_db_name}': {str(e)}. Check user permissions."
                }
            
            compliance_report: Dict[str, Any] = {
                "database": resolved_db_name,
                "scan_timestamp": datetime.utcnow().isoformat() + "Z",
                "total_collections_scanned": len(collections),
                "total_violations_found": 0,
                "compliance_summary": {
                    "critical_violations": 0,
                    "high_risk_violations": 0,
                    "medium_risk_violations": 0,
                    "low_risk_violations": 0,
                },
                "violations_by_collection": {},
                "pii_exposure": [],
                "sensitive_data_found": [],
                "compliance_violations": {
                    "gdpr": [],
                    "pci_dss": [],
                    "hipaa": [],
                    "data_retention": [],
                },
                "recommendations": [],
            }

            for collection_name in collections:
                collection = db[collection_name]
                
                # Sample most recent documents (sort by _id descending = newest first)
                # This ensures we get the latest data structure
                try:
                    sample_docs = list(collection.find().sort("_id", -1).limit(sample_size))
                except Exception as e:
                    # If sorting fails, try without sort
                    print(f"Warning: Cannot sort collection {collection_name}, using unsorted sample: {str(e)}")
                    try:
                        sample_docs = list(collection.find().limit(sample_size))
                    except Exception as e2:
                        print(f"Error: Cannot read collection {collection_name}: {str(e2)}")
                        compliance_report["violations_by_collection"][collection_name] = {
                            "error": f"Cannot read collection: {str(e2)}"
                        }
                        continue
                
                if not sample_docs:
                    continue
                
                # Analyze collection for violations
                collection_violations = self._analyze_collection_compliance(
                    collection_name, sample_docs
                )
                
                if collection_violations["violations"]:
                    compliance_report["violations_by_collection"][collection_name] = collection_violations
                    compliance_report["total_violations_found"] += len(collection_violations["violations"])
                    
                    # Categorize by severity
                    for violation in collection_violations["violations"]:
                        severity = violation["severity"]
                        if severity == "CRITICAL":
                            compliance_report["compliance_summary"]["critical_violations"] += 1
                        elif severity == "HIGH":
                            compliance_report["compliance_summary"]["high_risk_violations"] += 1
                        elif severity == "MEDIUM":
                            compliance_report["compliance_summary"]["medium_risk_violations"] += 1
                        else:
                            compliance_report["compliance_summary"]["low_risk_violations"] += 1
                        
                        # Categorize by compliance domain
                        if "PII" in violation["type"]:
                            compliance_report["pii_exposure"].append({
                                "collection": collection_name,
                                "violation": violation
                            })
                        if "SENSITIVE_DATA" in violation["type"]:
                            compliance_report["sensitive_data_found"].append({
                                "collection": collection_name,
                                "violation": violation
                            })
                        if "GDPR" in violation.get("compliance_framework", []):
                            compliance_report["compliance_violations"]["gdpr"].append({
                                "collection": collection_name,
                                "violation": violation
                            })
                        if "PCI-DSS" in violation.get("compliance_framework", []):
                            compliance_report["compliance_violations"]["pci_dss"].append({
                                "collection": collection_name,
                                "violation": violation
                            })
                        if "HIPAA" in violation.get("compliance_framework", []):
                            compliance_report["compliance_violations"]["hipaa"].append({
                                "collection": collection_name,
                                "violation": violation
                            })
            
            # Generate recommendations
            compliance_report["recommendations"] = self._generate_compliance_recommendations(
                compliance_report
            )
            
            client.close()
            return compliance_report
            
        except ConnectionFailure as e:
            return {"error": f"Failed to connect to MongoDB: {str(e)}"}
        except Exception as e:
            return {"error": f"Error scanning compliance: {str(e)}"}

    def _analyze_collection_compliance(
        self, collection_name: str, documents: List[Dict]
    ) -> Dict[str, Any]:
        """Analyze a collection for compliance violations"""
        violations = []
        
        for doc_idx, doc in enumerate(documents[:50]):  # Check first 50 docs in detail
            doc_violations = self._scan_document(doc, collection_name, doc_idx)
            violations.extend(doc_violations)
        
        # Check for missing compliance fields
        if documents:
            sample_doc = documents[0]
            missing_compliance_fields = self._check_missing_compliance_fields(
                sample_doc, collection_name
            )
            violations.extend(missing_compliance_fields)
        
        # Check for data retention issues
        retention_issues = self._check_data_retention(documents, collection_name)
        violations.extend(retention_issues)
        
        # Deduplicate similar violations
        unique_violations = self._deduplicate_violations(violations)
        
        return {
            "collection": collection_name,
            "documents_scanned": len(documents),
            "violations": unique_violations,
            "violation_count": len(unique_violations),
        }

    def _scan_document(
        self, doc: Dict, collection_name: str, doc_idx: int
    ) -> List[Dict[str, Any]]:
        """Scan a single document for violations"""
        violations = []
        
        for key, value in doc.items():
            if key == "_id":
                continue
            
            # Check for sensitive field names
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELD_NAMES):
                severity = "CRITICAL" if "password" in key.lower() or "secret" in key.lower() else "HIGH"
                
                # Check if password is hashed
                is_hashed = False
                if isinstance(value, str) and ("password" in key.lower() or "pwd" in key.lower()):
                    # Check if it looks like a hash (bcrypt, sha256, etc)
                    if len(value) >= 32 and (value.startswith('$') or all(c in '0123456789abcdef' for c in value.lower())):
                        is_hashed = True
                
                if not is_hashed or "token" in key.lower() or "secret" in key.lower():
                    violations.append({
                        "type": "SENSITIVE_DATA",
                        "severity": severity,
                        "field": key,
                        "issue": f"Sensitive field '{key}' detected in collection",
                        "recommendation": f"Ensure '{key}' is properly hashed/encrypted or should not be stored",
                        "compliance_framework": ["GDPR", "PCI-DSS", "HIPAA"],
                        "sample_document_index": doc_idx,
                    })
            
            # Check for PII fields
            if any(pii in key.lower() for pii in self.PII_FIELD_NAMES):
                violations.append({
                    "type": "PII_EXPOSURE",
                    "severity": "HIGH",
                    "field": key,
                    "issue": f"PII field '{key}' detected without encryption indication",
                    "recommendation": f"Implement field-level encryption for '{key}' or ensure proper consent tracking",
                    "compliance_framework": ["GDPR"],
                    "sample_document_index": doc_idx,
                })
            
            # Scan string values for patterns
            if isinstance(value, str):
                # Check for credit card numbers
                if self.CREDIT_CARD_PATTERN.search(value):
                    violations.append({
                        "type": "PCI_VIOLATION",
                        "severity": "CRITICAL",
                        "field": key,
                        "issue": f"Potential credit card number found in field '{key}'",
                        "recommendation": "NEVER store credit card numbers. Use tokenization via payment processor",
                        "compliance_framework": ["PCI-DSS"],
                        "sample_document_index": doc_idx,
                    })
                
                # Check for SSN
                if self.SSN_PATTERN.search(value):
                    violations.append({
                        "type": "PII_EXPOSURE",
                        "severity": "CRITICAL",
                        "field": key,
                        "issue": f"Social Security Number found in field '{key}'",
                        "recommendation": "Encrypt or hash SSN, ensure proper access controls",
                        "compliance_framework": ["GDPR", "HIPAA"],
                        "sample_document_index": doc_idx,
                    })
                
                # Check for API keys/tokens
                if self.API_KEY_PATTERN.search(value) or self.JWT_PATTERN.search(value):
                    violations.append({
                        "type": "SENSITIVE_DATA",
                        "severity": "HIGH",
                        "field": key,
                        "issue": f"Potential API key or JWT token found in field '{key}'",
                        "recommendation": "Use secure secret management service (AWS Secrets Manager, Vault)",
                        "compliance_framework": ["GDPR"],
                        "sample_document_index": doc_idx,
                    })
        
        return violations

    def _check_missing_compliance_fields(
        self, sample_doc: Dict, collection_name: str
    ) -> List[Dict[str, Any]]:
        """Check for missing GDPR/compliance fields"""
        violations = []
        
        # Check if user-related collection has consent tracking
        if any(term in collection_name.lower() for term in ['user', 'profile', 'account', 'customer']):
            if 'consent' not in str(sample_doc).lower() and 'gdpr_consent' not in str(sample_doc).lower():
                violations.append({
                    "type": "GDPR_VIOLATION",
                    "severity": "MEDIUM",
                    "field": "N/A",
                    "issue": f"Collection '{collection_name}' lacks GDPR consent tracking fields",
                    "recommendation": "Add fields: gdpr_consent, consent_date, consent_version, marketing_consent",
                    "compliance_framework": ["GDPR"],
                })
            
            # Check for data processing basis
            if 'data_processing_basis' not in str(sample_doc).lower():
                violations.append({
                    "type": "GDPR_VIOLATION",
                    "severity": "MEDIUM",
                    "field": "N/A",
                    "issue": "Missing data processing legal basis documentation",
                    "recommendation": "Add 'data_processing_basis' field (consent, contract, legal_obligation, etc.)",
                    "compliance_framework": ["GDPR"],
                })
        
        return violations

    def _check_data_retention(
        self, documents: List[Dict], collection_name: str
    ) -> List[Dict[str, Any]]:
        """Check for data retention policy violations"""
        violations = []
        
        # Check for old documents that should be purged
        old_document_count = 0
        retention_threshold = datetime.utcnow() - timedelta(days=730)  # 2 years
        
        for doc in documents:
            created_at = None
            
            # Try to find creation date
            for date_field in ['createdAt', 'created_at', 'date_created', 'timestamp', 'date']:
                if date_field in doc:
                    created_at = doc[date_field]
                    break
            
            if created_at:
                try:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    
                    if created_at < retention_threshold:
                        old_document_count += 1
                except:
                    pass
        
        if old_document_count > 10:
            violations.append({
                "type": "DATA_RETENTION",
                "severity": "MEDIUM",
                "field": "N/A",
                "issue": f"Found {old_document_count} documents older than 2 years in '{collection_name}'",
                "recommendation": "Implement data retention policy and automated purging of old data per GDPR 'storage limitation' principle",
                "compliance_framework": ["GDPR"],
            })
        
        return violations

    def _deduplicate_violations(self, violations: List[Dict]) -> List[Dict]:
        """Remove duplicate violations"""
        seen = set()
        unique = []
        
        for v in violations:
            key = (v["type"], v["field"], v["issue"])
            if key not in seen:
                seen.add(key)
                unique.append(v)
        
        return unique

    def _generate_compliance_recommendations(
        self, compliance_report: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate high-level compliance recommendations"""
        recommendations = []
        
        if compliance_report["compliance_summary"]["critical_violations"] > 0:
            recommendations.append({
                "priority": "CRITICAL",
                "category": "Immediate Action Required",
                "recommendation": f"Address {compliance_report['compliance_summary']['critical_violations']} critical violations immediately. These pose severe compliance and security risks.",
                "actions": [
                    "Remove or encrypt all plaintext passwords",
                    "Delete all credit card numbers from database",
                    "Implement field-level encryption for SSNs",
                    "Rotate all exposed API keys/tokens",
                ]
            })
        
        if len(compliance_report["pii_exposure"]) > 0:
            recommendations.append({
                "priority": "HIGH",
                "category": "PII Protection",
                "recommendation": "Implement comprehensive PII protection strategy",
                "actions": [
                    "Enable MongoDB field-level encryption for PII fields",
                    "Implement data masking for non-production environments",
                    "Add GDPR consent tracking to user collections",
                    "Create data access audit logs",
                ]
            })
        
        if len(compliance_report["compliance_violations"]["gdpr"]) > 0:
            recommendations.append({
                "priority": "HIGH",
                "category": "GDPR Compliance",
                "recommendation": "Achieve GDPR compliance",
                "actions": [
                    "Add consent tracking fields (consent_date, consent_version)",
                    "Implement 'right to erasure' (data deletion) procedures",
                    "Document data processing legal basis",
                    "Implement data retention policies with automated purging",
                    "Create data export functionality for 'right to data portability'",
                ]
            })
        
        if len(compliance_report["compliance_violations"]["pci_dss"]) > 0:
            recommendations.append({
                "priority": "CRITICAL",
                "category": "PCI-DSS Compliance",
                "recommendation": "Eliminate PCI-DSS violations immediately",
                "actions": [
                    "NEVER store credit card numbers - use Stripe/PayPal tokenization",
                    "If absolutely necessary, use PCI-compliant third-party vault",
                    "Remove all existing credit card data from database",
                    "Implement payment processor webhooks instead of storing card data",
                ]
            })
        
        return recommendations

