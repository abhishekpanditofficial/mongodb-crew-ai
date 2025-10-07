from __future__ import annotations

import os
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type

import requests
from requests.auth import HTTPDigestAuth
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class AtlasMetricsInput(BaseModel):
    project_id: Optional[str] = Field(
        default=None, description="MongoDB Atlas Project ID; falls back to env"
    )
    hours: int = Field(default=3, description="How many hours back to fetch (reduced default for large clusters)")
    process_batch_size: int = Field(
        default=2, description="Number of processes to analyze per batch (for large clusters)"
    )
    mode: str = Field(
        default="summary",
        description="Data retrieval mode: 'summary' (overview only), 'issues' (performance problems), 'indexes' (recommendations), 'queries' (slow queries), or 'full' (all insights)"
    )


class AtlasPerformanceTool(BaseTool):
    name: str = "atlas_performance_tool"
    description: str = (
        "Multi-mode MongoDB Atlas performance analysis tool. Complete data saved to performance_data_TIMESTAMP.json. "
        "MODES (use 'mode' parameter): "
        "'summary' - Cluster overview, counts, and health status (START HERE - smallest payload). "
        "'issues' - Top 3 performance problems (CPU, connections, index efficiency). "
        "'indexes' - Top 3 index recommendations from Performance Advisor. "
        "'queries' - Top 2 slow queries needing optimization. "
        "'full' - All insights in one call (larger payload, use only if needed). "
        "STRATEGY: Make multiple calls with different modes to gather all data without overwhelming context."
    )
    args_schema: Type[BaseModel] = AtlasMetricsInput

    def _run(
        self, 
        project_id: Optional[str] = None, 
        hours: int = 3,
        process_batch_size: int = 2,
        mode: str = "summary"
    ) -> Dict[str, Any]:
        public_key = os.getenv("MONGODB_ATLAS_PUBLIC_KEY")
        private_key = os.getenv("MONGODB_ATLAS_PRIVATE_KEY")
        resolved_project_id = project_id or os.getenv("MONGODB_ATLAS_PROJECT_ID")

        if not all([public_key, private_key, resolved_project_id]):
            return {
                "error": "Missing MongoDB Atlas credentials. Set MONGODB_ATLAS_PUBLIC_KEY, MONGODB_ATLAS_PRIVATE_KEY, MONGODB_ATLAS_PROJECT_ID."
            }

        auth = HTTPDigestAuth(public_key, private_key)
        headers = {"Accept": "application/json"}

        clusters_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/clusters"
        clusters_resp = requests.get(clusters_url, auth=auth, headers=headers, timeout=60)
        clusters_resp.raise_for_status()
        clusters = clusters_resp.json()

        processes_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/processes"
        processes_resp = requests.get(processes_url, auth=auth, headers=headers, timeout=60)
        processes_resp.raise_for_status()
        processes = processes_resp.json()

        now = datetime.utcnow()
        start = (now - timedelta(hours=hours)).isoformat() + "Z"
        end = now.isoformat() + "Z"

        # Split processes into batches for sequential processing
        all_processes = processes.get("results", [])
        total_processes = len(all_processes)
        
        metrics_per_process: Dict[str, Any] = {}
        performance_insights: Dict[str, Any] = {}
        
        # Process in batches to avoid overwhelming the API and reduce memory footprint
        for batch_start in range(0, total_processes, process_batch_size):
            batch_end = min(batch_start + process_batch_size, total_processes)
            batch_processes = all_processes[batch_start:batch_end]
            
            print(f"Processing batch {batch_start//process_batch_size + 1}/{(total_processes + process_batch_size - 1)//process_batch_size} "
                  f"({len(batch_processes)} processes)")
            
            for process in batch_processes:
                hostname = process.get("hostname")
                port = process.get("port")
                if not hostname or not port:
                    continue

                process_key = f"{hostname}:{port}"

                # Fetch standard performance metrics
                metrics_url = (
                    f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/processes/"
                    f"{hostname}:{port}/measurements"
                )
                params = {
                    "granularity": "PT5M",
                    "period": f"PT{hours}H",
                    "start": start,
                    "end": end,
                    "m": [
                        "PROCESS_CPU_USER",
                        "DISK_PARTITION_IOPS_TOTAL",
                        "SYSTEM_NETWORK_BYTES_IN",
                        "SYSTEM_NETWORK_BYTES_OUT",
                        "OPCOUNTER_CMD",
                        "OPCOUNTER_QUERY",
                        "OPCOUNTER_INSERT",
                        "OPCOUNTER_UPDATE",
                        "OPCOUNTER_DELETE",
                        "QUERY_EXECUTOR_SCANNED",
                        "QUERY_EXECUTOR_SCANNED_OBJECTS",
                        "CONNECTIONS",
                        "CURSORS_TOTAL_OPEN",
                    ],
                }

                try:
                    res = requests.get(
                        metrics_url, auth=auth, headers=headers, params=params, timeout=60
                    )
                    res.raise_for_status()
                    raw_metrics = res.json()
                    
                    # Always summarize metrics to reduce memory footprint
                    metrics_per_process[process_key] = self._summarize_metrics(raw_metrics)
                except requests.RequestException as e:
                    metrics_per_process[process_key] = {"error": str(e)}

                # Fetch performance advisor suggestions (index recommendations)
                try:
                    advisor_url = (
                        f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/"
                        f"processes/{hostname}:{port}/performanceAdvisor/suggestedIndexes"
                    )
                    advisor_resp = requests.get(advisor_url, auth=auth, headers=headers, timeout=60)
                    if advisor_resp.status_code == 200:
                        suggested_indexes = advisor_resp.json()
                        # Limit to top 10 suggested indexes
                        if "suggestedIndexes" in suggested_indexes:
                            suggested_indexes["suggestedIndexes"] = suggested_indexes["suggestedIndexes"][:10]
                        performance_insights[process_key] = {
                            "suggested_indexes": suggested_indexes
                        }
                    else:
                        performance_insights[process_key] = {
                            "suggested_indexes": {"note": "Performance Advisor data not available or requires M10+ cluster"}
                        }
                except requests.RequestException:
                    performance_insights[process_key] = {
                        "suggested_indexes": {"error": "Unable to fetch Performance Advisor data"}
                    }

                # Fetch slow query logs (requires M10+ and profiling enabled)
                try:
                    slow_query_url = (
                        f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{resolved_project_id}/"
                        f"processes/{hostname}:{port}/performanceAdvisor/slowQueryLogs"
                    )
                    slow_query_resp = requests.get(slow_query_url, auth=auth, headers=headers, timeout=60)
                    if slow_query_resp.status_code == 200:
                        slow_queries = slow_query_resp.json()
                        # Limit to top 10 slowest queries
                        if "slowQueries" in slow_queries:
                            slow_queries["slowQueries"] = slow_queries["slowQueries"][:10]
                        performance_insights[process_key]["slow_queries"] = slow_queries
                    else:
                        performance_insights[process_key]["slow_queries"] = {
                            "note": "Slow query logs not available. Enable profiling on cluster."
                        }
                except requests.RequestException:
                    performance_insights[process_key]["slow_queries"] = {
                        "error": "Unable to fetch slow query logs"
                    }

        # Analyze index efficiency from metrics
        index_analysis = self._analyze_index_efficiency(metrics_per_process)

        # Always reduce clusters and processes data to essential fields only
        clusters_summary = self._summarize_clusters(clusters)
        processes_summary = self._summarize_processes(processes)

        full_data = {
            "clusters": clusters_summary,
            "processes": processes_summary,
            "metrics": metrics_per_process,
            "performance_insights": performance_insights,
            "index_analysis": index_analysis,
            "window": {"start": start, "end": end, "hours": hours},
        }

        # Save full data to file for reference
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_file = f"performance_data_{timestamp}.json"
        with open(data_file, 'w') as f:
            json.dump(full_data, f, indent=2, default=str)
        print(f"✓ Full performance data saved to: {data_file}")

        # Extract insights based on mode
        insights = self._extract_insights_by_mode(full_data, mode)
        
        payload_size = len(json.dumps(insights))
        print(f"✓ Insights extracted (mode: {mode}). Payload size: {payload_size:,} bytes ({payload_size/1024:.1f} KB)")
        print(f"  - Full data available in: {data_file}")
        
        return insights

    def _extract_insights_by_mode(self, full_data: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """
        Route to appropriate extraction method based on mode.
        Enables progressive disclosure - gather data in multiple small calls.
        """
        if mode == "summary":
            return self._extract_summary_only(full_data)
        elif mode == "issues":
            return self._extract_issues_only(full_data)
        elif mode == "indexes":
            return self._extract_indexes_only(full_data)
        elif mode == "queries":
            return self._extract_queries_only(full_data)
        elif mode == "full":
            return self._extract_all_insights(full_data)
        else:
            # Default to summary
            return self._extract_summary_only(full_data)

    def _extract_summary_only(self, full_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only cluster overview and counts - smallest payload."""
        clusters = full_data.get("clusters", {}).get("results", [])
        metrics = full_data.get("metrics", {})
        
        return {
            "mode": "summary",
            "data_file": "Complete data in performance_data_*.json",
            "clusters": [{
                "name": c.get("name"),
                "size": c.get("providerSettings", {}).get("instanceSizeName"),
                "region": c.get("providerSettings", {}).get("regionName"),
                "status": c.get("stateName")
            } for c in clusters],
            "summary": {
                "total_clusters": len(clusters),
                "total_processes": len(metrics),
                "time_window_hours": full_data.get("window", {}).get("hours", 0),
            },
            "next_steps": "Use mode='issues' for performance problems, mode='indexes' for recommendations, mode='queries' for slow queries"
        }

    def _extract_issues_only(self, full_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only performance issues."""
        all_issues = []
        metrics = full_data.get("metrics", {})
        
        # Extract performance issues from metrics
        for process_key, metric_data in metrics.items():
            if "error" in metric_data:
                continue
            
            measurements = metric_data.get("measurements", [])
            for m in measurements:
                metric_name = m.get("name")
                avg = m.get("avg", 0)
                max_val = m.get("max", 0)
                
                if metric_name == "PROCESS_CPU_USER" and avg > 75:
                    all_issues.append({
                        "process": process_key,
                        "issue": "High CPU Usage",
                        "severity": "HIGH" if avg > 90 else "MEDIUM",
                        "value": f"{avg:.1f}% avg, {max_val:.1f}% max",
                        "priority": avg
                    })
                
                if metric_name == "CONNECTIONS" and avg > 1000:
                    all_issues.append({
                        "process": process_key,
                        "issue": "High Connection Count",
                        "severity": "MEDIUM",
                        "value": f"{avg:.0f} avg connections",
                        "priority": avg / 100
                    })
        
        # Index efficiency analysis
        index_analysis = full_data.get("index_analysis", {})
        for process_key, analysis in index_analysis.items():
            ratio = analysis.get("scan_ratio", 0)
            if ratio > 10:
                all_issues.append({
                    "process": process_key,
                    "issue": "Poor Index Efficiency",
                    "severity": "HIGH",
                    "value": f"Scan ratio: {ratio} - {analysis.get('efficiency')}",
                    "priority": ratio
                })
        
        all_issues.sort(key=lambda x: x.get("priority", 0), reverse=True)
        top_issues = all_issues[:3]
        for item in top_issues:
            item.pop("priority", None)
        
        return {
            "mode": "issues",
            "data_file": "Complete data in performance_data_*.json",
            "issues_found": len(top_issues),
            "top_issues": top_issues
        }

    def _extract_indexes_only(self, full_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only index recommendations."""
        all_index_recs = []
        performance_insights = full_data.get("performance_insights", {})
        
        for process_key, insight_data in performance_insights.items():
            suggested = insight_data.get("suggested_indexes", {})
            if "suggestedIndexes" in suggested:
                for idx in suggested["suggestedIndexes"][:2]:
                    impact = idx.get("impact", {})
                    if isinstance(impact, dict):
                        impact_score = impact.get("score", 0)
                    else:
                        impact_score = 50
                    
                    all_index_recs.append({
                        "process": process_key,
                        "namespace": idx.get("namespace"),
                        "index": idx.get("index", []),
                        "impact_score": impact_score,
                        "priority": impact_score
                    })
        
        all_index_recs.sort(key=lambda x: x.get("priority", 0), reverse=True)
        top_index_recs = all_index_recs[:3]
        for item in top_index_recs:
            item.pop("priority", None)
        
        return {
            "mode": "indexes",
            "data_file": "Complete data in performance_data_*.json",
            "recommendations_found": len(top_index_recs),
            "top_index_recommendations": top_index_recs
        }

    def _extract_queries_only(self, full_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only slow queries."""
        all_slow_queries = []
        performance_insights = full_data.get("performance_insights", {})
        
        for process_key, insight_data in performance_insights.items():
            slow_queries = insight_data.get("slow_queries", {})
            if "slowQueries" in slow_queries:
                for sq in slow_queries["slowQueries"][:2]:
                    count = sq.get("count", 0)
                    all_slow_queries.append({
                        "process": process_key,
                        "namespace": sq.get("namespace"),
                        "line": sq.get("line", "")[:100] + "..." if len(sq.get("line", "")) > 100 else sq.get("line", ""),
                        "count": count,
                        "priority": count
                    })
        
        all_slow_queries.sort(key=lambda x: x.get("priority", 0), reverse=True)
        top_slow_queries = all_slow_queries[:2]
        for item in top_slow_queries:
            item.pop("priority", None)
        
        return {
            "mode": "queries",
            "data_file": "Complete data in performance_data_*.json",
            "slow_queries_found": len(top_slow_queries),
            "top_slow_queries": top_slow_queries
        }

    def _extract_all_insights(self, full_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all insights in one call (original behavior).
        Use only if multiple calls aren't working.
        """
        # Get each type separately
        summary = self._extract_summary_only(full_data)
        issues = self._extract_issues_only(full_data)
        indexes = self._extract_indexes_only(full_data)
        queries = self._extract_queries_only(full_data)
        
        # Combine
        return {
            "mode": "full",
            "data_file": "Complete data in performance_data_*.json",
            "summary": summary["summary"],
            "clusters": summary["clusters"],
            "issues": issues["top_issues"],
            "index_recommendations": indexes["top_index_recommendations"],
            "slow_queries": queries["top_slow_queries"],
        }

    def _extract_insights_only(self, full_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only TOP actionable insights from full data to minimize payload.
        Ultra-aggressive filtering - returns only highest priority items ACROSS ALL PROCESSES.
        """
        # Collect all items first, then prioritize
        all_issues = []
        all_index_recs = []
        all_slow_queries = []
        
        clusters = full_data.get("clusters", {}).get("results", [])
        metrics = full_data.get("metrics", {})
        
        # Extract performance issues from metrics
        for process_key, metric_data in metrics.items():
            if "error" in metric_data:
                continue
            
            measurements = metric_data.get("measurements", [])
            for m in measurements:
                metric_name = m.get("name")
                avg = m.get("avg", 0)
                max_val = m.get("max", 0)
                
                # Flag high CPU usage
                if metric_name == "PROCESS_CPU_USER" and avg > 75:
                    all_issues.append({
                        "process": process_key,
                        "issue": "High CPU Usage",
                        "severity": "HIGH" if avg > 90 else "MEDIUM",
                        "value": f"{avg:.1f}% avg, {max_val:.1f}% max",
                        "priority": avg  # For sorting
                    })
                
                # Flag high connections
                if metric_name == "CONNECTIONS" and avg > 1000:
                    all_issues.append({
                        "process": process_key,
                        "issue": "High Connection Count",
                        "severity": "MEDIUM",
                        "value": f"{avg:.0f} avg connections",
                        "priority": avg / 100  # For sorting
                    })
        
        # Extract index recommendations with impact scores
        performance_insights = full_data.get("performance_insights", {})
        for process_key, insight_data in performance_insights.items():
            suggested = insight_data.get("suggested_indexes", {})
            if "suggestedIndexes" in suggested:
                for idx in suggested["suggestedIndexes"][:2]:  # Only top 2 per process
                    # Extract impact score for prioritization
                    impact = idx.get("impact", {})
                    if isinstance(impact, dict):
                        impact_score = impact.get("score", 0)
                    else:
                        impact_score = 50  # Default medium impact
                    
                    all_index_recs.append({
                        "process": process_key,
                        "namespace": idx.get("namespace"),
                        "index": idx.get("index", []),
                        "impact_score": impact_score,
                        "priority": impact_score  # For sorting
                    })
            
            # Extract slow queries with execution counts
            slow_queries = insight_data.get("slow_queries", {})
            if "slowQueries" in slow_queries:
                for sq in slow_queries["slowQueries"][:2]:  # Only top 2 per process
                    count = sq.get("count", 0)
                    all_slow_queries.append({
                        "process": process_key,
                        "namespace": sq.get("namespace"),
                        "line": sq.get("line", "")[:100] + "..." if len(sq.get("line", "")) > 100 else sq.get("line", ""),  # Truncate
                        "count": count,
                        "priority": count  # For sorting
                    })
        
        # Index efficiency analysis
        index_analysis = full_data.get("index_analysis", {})
        for process_key, analysis in index_analysis.items():
            ratio = analysis.get("scan_ratio", 0)
            if ratio > 10:
                all_issues.append({
                    "process": process_key,
                    "issue": "Poor Index Efficiency",
                    "severity": "HIGH",
                    "value": f"Scan ratio: {ratio} - {analysis.get('efficiency')}",
                    "priority": ratio  # For sorting
                })
        
        # Sort and take only TOP items across all processes
        all_issues.sort(key=lambda x: x.get("priority", 0), reverse=True)
        all_index_recs.sort(key=lambda x: x.get("priority", 0), reverse=True)
        all_slow_queries.sort(key=lambda x: x.get("priority", 0), reverse=True)
        
        # Keep only top items and remove priority field
        top_issues = all_issues[:3]  # Top 3 issues only
        top_index_recs = all_index_recs[:3]  # Top 3 index recommendations only
        top_slow_queries = all_slow_queries[:2]  # Top 2 slow queries only
        
        # Remove priority fields (used only for sorting)
        for item in top_issues:
            item.pop("priority", None)
        for item in top_index_recs:
            item.pop("priority", None)
        for item in top_slow_queries:
            item.pop("priority", None)
        
        # Build ultra-minimal insights
        insights = {
            "data_file": "See complete data in performance_data_*.json file",
            "summary": {
                "total_clusters": len(clusters),
                "clusters": [{"name": c.get("name"), "size": c.get("providerSettings", {}).get("instanceSizeName")} for c in clusters],
                "total_processes": len(metrics),
                "critical_issues_found": len([i for i in top_issues if i.get("severity") == "HIGH"]),
                "time_window_hours": full_data.get("window", {}).get("hours", 0),
            },
            "top_issues": top_issues,
            "top_index_recommendations": top_index_recs,
            "top_slow_queries": top_slow_queries,
        }
        
        return insights

    def _summarize_clusters(self, clusters_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only essential cluster information to reduce payload size.
        """
        clusters = clusters_data.get("results", [])
        summarized = {
            "totalCount": len(clusters),
            "results": []
        }
        
        for cluster in clusters:
            # Keep only essential fields
            cluster_summary = {
                "name": cluster.get("name"),
                "clusterType": cluster.get("clusterType"),
                "mongoDBVersion": cluster.get("mongoDBVersion"),
                "providerSettings": {
                    "providerName": cluster.get("providerSettings", {}).get("providerName"),
                    "instanceSizeName": cluster.get("providerSettings", {}).get("instanceSizeName"),
                    "regionName": cluster.get("providerSettings", {}).get("regionName"),
                },
                "numShards": cluster.get("numShards"),
                "replicationFactor": cluster.get("replicationFactor"),
                "diskSizeGB": cluster.get("diskSizeGB"),
                "stateName": cluster.get("stateName"),
                "paused": cluster.get("paused", False),
            }
            summarized["results"].append(cluster_summary)
        
        return summarized

    def _summarize_processes(self, processes_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only essential process information to reduce payload size.
        """
        processes = processes_data.get("results", [])
        summarized = {
            "totalCount": len(processes),
            "results": []
        }
        
        for process in processes:
            # Keep only essential fields
            process_summary = {
                "id": process.get("id"),
                "hostname": process.get("hostname"),
                "port": process.get("port"),
                "typeName": process.get("typeName"),
                "version": process.get("version"),
                "replicaSetName": process.get("replicaSetName"),
            }
            summarized["results"].append(process_summary)
        
        return summarized

    def _summarize_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarize raw metrics data to reduce payload size.
        Instead of returning all data points, return min, max, avg, and latest values.
        """
        summarized = {
            "measurements": []
        }
        
        measurements = raw_metrics.get("measurements", [])
        
        for measurement in measurements:
            metric_name = measurement.get("name")
            data_points = measurement.get("dataPoints", [])
            
            # Extract non-null values
            values = [dp["value"] for dp in data_points if dp["value"] is not None]
            
            if not values:
                continue
            
            # Calculate statistics
            summary = {
                "name": metric_name,
                "count": len(values),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "avg": round(sum(values) / len(values), 2),
                "latest": round(values[-1], 2) if values else None,
                "unit": measurement.get("units", "")
            }
            
            summarized["measurements"].append(summary)
        
        return summarized

    def _analyze_index_efficiency(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze index efficiency from query metrics (handles both raw and summarized formats)"""
        analysis = {}
        
        for process_key, metric_data in metrics.items():
            if "error" in metric_data:
                continue
            
            measurements = metric_data.get("measurements", [])
            
            scanned_objects = None
            scanned_docs = None
            
            for m in measurements:
                metric_name = m.get("name")
                
                # Check if this is summarized data (has 'avg' field) or raw data (has 'dataPoints')
                if "avg" in m:
                    # Summarized format
                    if metric_name == "QUERY_EXECUTOR_SCANNED_OBJECTS":
                        scanned_objects = m["avg"]
                    elif metric_name == "QUERY_EXECUTOR_SCANNED":
                        scanned_docs = m["avg"]
                elif "dataPoints" in m:
                    # Raw format
                    data_points = [dp["value"] for dp in m.get("dataPoints", []) if dp.get("value") is not None]
                    if data_points:
                        avg_value = sum(data_points) / len(data_points)
                        if metric_name == "QUERY_EXECUTOR_SCANNED_OBJECTS":
                            scanned_objects = avg_value
                        elif metric_name == "QUERY_EXECUTOR_SCANNED":
                            scanned_docs = avg_value
            
            # Calculate index efficiency ratio
            if scanned_objects and scanned_docs:
                ratio = scanned_objects / scanned_docs if scanned_docs > 0 else 0
                
                analysis[process_key] = {
                    "avg_scanned_objects": round(scanned_objects, 2),
                    "avg_scanned_docs": round(scanned_docs, 2),
                    "scan_ratio": round(ratio, 2),
                    "efficiency": "Poor - Missing indexes likely" if ratio > 10 else 
                                 "Fair - Review query patterns" if ratio > 3 else 
                                 "Good - Indexes being used effectively"
                }
        
        return analysis


