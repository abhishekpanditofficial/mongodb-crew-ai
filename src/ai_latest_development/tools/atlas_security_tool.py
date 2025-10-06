from __future__ import annotations

import os
from typing import Any, Dict, Optional, Type

import requests
from requests.auth import HTTPDigestAuth
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class AtlasSecurityInput(BaseModel):
    project_id: Optional[str] = Field(
        default=None, description="MongoDB Atlas Project ID; falls back to env"
    )


class AtlasSecurityTool(BaseTool):
    name: str = "atlas_security_tool"
    description: str = (
        "Fetches MongoDB Atlas security configurations: IP access list, TLS enforcement, "
        "database users/roles, and encryption at rest settings."
    )
    args_schema: Type[BaseModel] = AtlasSecurityInput

    def _run(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        public_key = os.getenv("MONGODB_ATLAS_PUBLIC_KEY")
        private_key = os.getenv("MONGODB_ATLAS_PRIVATE_KEY")
        resolved_project_id = project_id or os.getenv("MONGODB_ATLAS_PROJECT_ID")

        if not all([public_key, private_key, resolved_project_id]):
            return {
                "error": "Missing MongoDB Atlas credentials. Set MONGODB_ATLAS_PUBLIC_KEY, "
                "MONGODB_ATLAS_PRIVATE_KEY, MONGODB_ATLAS_PROJECT_ID."
            }

        auth = HTTPDigestAuth(public_key, private_key)
        headers = {"Accept": "application/json"}

        result = {"project_id": resolved_project_id}

        # 1️⃣ IP Access List
        try:
            ip_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/accessList"
            ip_resp = requests.get(ip_url, auth=auth, headers=headers, timeout=60)
            ip_resp.raise_for_status()
            result["ip_access_list"] = ip_resp.json()
        except requests.RequestException as e:
            result["ip_access_list"] = {"error": str(e)}

        # 2️⃣ Clusters (for TLS enforcement check)
        try:
            cluster_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/clusters"
            cluster_resp = requests.get(cluster_url, auth=auth, headers=headers, timeout=60)
            cluster_resp.raise_for_status()
            result["clusters"] = cluster_resp.json()
        except requests.RequestException as e:
            result["clusters"] = {"error": str(e)}

        # 3️⃣ Database Users
        try:
            users_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/databaseUsers"
            users_resp = requests.get(users_url, auth=auth, headers=headers, timeout=60)
            users_resp.raise_for_status()
            result["database_users"] = users_resp.json()
        except requests.RequestException as e:
            result["database_users"] = {"error": str(e)}

        # 4️⃣ Encryption at Rest
        try:
            encryption_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/encryptionAtRest"
            encryption_resp = requests.get(encryption_url, auth=auth, headers=headers, timeout=60)
            encryption_resp.raise_for_status()
            result["encryption_at_rest"] = encryption_resp.json()
        except requests.RequestException as e:
            result["encryption_at_rest"] = {"error": str(e)}

        return result

