from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ReportSynthesisInput(BaseModel):
    report_file: str = Field(
        default="report.md", description="Path to the report file containing all agent outputs"
    )


class ReportSynthesisTool(BaseTool):
    name: str = "report_synthesis_tool"
    description: str = (
        "Reads and analyzes the consolidated report from all agents (Performance, Security, Cost), "
        "extracts key findings, calculates health scores, identifies cross-cutting issues, and "
        "provides prioritized recommendations."
    )
    args_schema: Type[BaseModel] = ReportSynthesisInput

    def _run(self, report_file: str = "report.md") -> Dict[str, Any]:
        """Read the report and extract structured insights"""
        
        if not os.path.exists(report_file):
            return {
                "error": f"Report file '{report_file}' not found. Run other agents first.",
                "health_score": 0,
                "status": "incomplete"
            }

        with open(report_file, 'r') as f:
            report_content = f.read()

        # Parse report sections
        sections = self._parse_report_sections(report_content)
        
        # Calculate health scores per domain
        performance_score = self._calculate_performance_score(sections.get('performance', ''))
        security_score = self._calculate_security_score(sections.get('security', ''))
        cost_score = self._calculate_cost_score(sections.get('cost', ''))
        
        # Overall health score (weighted average)
        overall_health = int(
            (performance_score * 0.35) +  # 35% weight on performance
            (security_score * 0.40) +      # 40% weight on security (most critical)
            (cost_score * 0.25)            # 25% weight on cost
        )

        # Extract key issues from each section
        performance_issues = self._extract_issues(sections.get('performance', ''), 'performance')
        security_issues = self._extract_issues(sections.get('security', ''), 'security')
        cost_issues = self._extract_issues(sections.get('cost', ''), 'cost')

        # Combine and prioritize all issues
        all_issues = performance_issues + security_issues + cost_issues
        prioritized_issues = self._prioritize_issues(all_issues)

        # Identify cross-cutting concerns
        cross_cutting = self._identify_cross_cutting_concerns(
            sections.get('performance', ''),
            sections.get('security', ''),
            sections.get('cost', '')
        )

        return {
            "overall_health_score": overall_health,
            "health_breakdown": {
                "performance": performance_score,
                "security": security_score,
                "cost_efficiency": cost_score
            },
            "health_rating": self._get_health_rating(overall_health),
            "total_issues_found": len(all_issues),
            "critical_issues": len([i for i in all_issues if i.get('severity') == 'critical']),
            "high_priority_issues": len([i for i in all_issues if i.get('severity') == 'high']),
            "prioritized_issues": prioritized_issues[:10],  # Top 10 issues
            "cross_cutting_concerns": cross_cutting,
            "report_sections": {
                "performance": len(sections.get('performance', '')) > 0,
                "security": len(sections.get('security', '')) > 0,
                "cost": len(sections.get('cost', '')) > 0
            },
            "analysis_timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def _parse_report_sections(self, content: str) -> Dict[str, str]:
        """Extract sections from the report"""
        sections = {}
        
        if '## ⚡ Performance Analysis' in content:
            start = content.find('## ⚡ Performance Analysis')
            end = content.find('---', start)
            sections['performance'] = content[start:end] if end > start else content[start:]
        
        if '## 🔒 Security Audit' in content:
            start = content.find('## 🔒 Security Audit')
            end = content.find('---', start)
            sections['security'] = content[start:end] if end > start else content[start:]
        
        if '## 💰 Cost Optimization Analysis' in content:
            start = content.find('## 💰 Cost Optimization Analysis')
            end = content.find('---', start)
            sections['cost'] = content[start:end] if end > start else content[start:]
        
        return sections

    def _calculate_performance_score(self, section: str) -> int:
        """Calculate performance health score (0-100)"""
        if not section:
            return 50  # neutral if no data
        
        score = 100
        
        # Deduct points for performance issues
        if 'high cpu' in section.lower() or 'cpu usage' in section.lower():
            score -= 15
        if 'bottleneck' in section.lower():
            score -= 20
        if 'slow' in section.lower() or 'latency' in section.lower():
            score -= 15
        if 'disk' in section.lower() and ('high' in section.lower() or 'saturated' in section.lower()):
            score -= 10
        if 'unable to retrieve metrics' in section.lower():
            score -= 25  # Missing data is concerning
        
        return max(0, min(100, score))

    def _calculate_security_score(self, section: str) -> int:
        """Calculate security health score (0-100)"""
        if not section:
            return 50
        
        score = 100
        
        # Deduct points for security issues
        if '0.0.0.0/0' in section or 'open ip' in section.lower():
            score -= 30  # Critical: open to internet
        if 'atlasadmin' in section.lower() or 'excessive privilege' in section.lower():
            score -= 20
        if 'no encryption' in section.lower() or 'encryption at rest' in section.lower():
            score -= 25
        if 'tls' in section.lower() and 'not enforced' in section.lower():
            score -= 15
        if 'critical' in section.lower():
            score -= 15
        
        return max(0, min(100, score))

    def _calculate_cost_score(self, section: str) -> int:
        """Calculate cost efficiency score (0-100)"""
        if not section:
            return 50
        
        score = 100
        
        # Deduct points for cost inefficiencies
        if 'overprovisioned' in section.lower() or 'oversized' in section.lower():
            score -= 20
        if 'waste' in section.lower() or 'idle' in section.lower():
            score -= 15
        if 'savings' in section.lower() or 'optimize' in section.lower():
            score -= 10  # Opportunities exist
        if 'expensive' in section.lower():
            score -= 10
        
        return max(0, min(100, score))

    def _extract_issues(self, section: str, category: str) -> List[Dict[str, Any]]:
        """Extract issues from a report section"""
        issues = []
        
        # Look for bullet points or warnings
        lines = section.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('⚠️') or line.startswith('-'):
                severity = 'high' if '⚠️' in line else 'medium'
                if 'critical' in line.lower():
                    severity = 'critical'
                
                issues.append({
                    'category': category,
                    'severity': severity,
                    'description': line.replace('⚠️', '').replace('-', '').strip(),
                    'source': f'{category}_agent'
                })
        
        return issues

    def _prioritize_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize issues by severity and impact"""
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        
        return sorted(issues, key=lambda x: severity_order.get(x.get('severity', 'low'), 99))

    def _identify_cross_cutting_concerns(self, perf: str, sec: str, cost: str) -> List[str]:
        """Identify issues that span multiple categories"""
        concerns = []
        
        # Check for cluster sizing issues (affects performance + cost)
        if 'instance' in perf.lower() and 'instance' in cost.lower():
            concerns.append("Cluster sizing impacts both performance and cost efficiency")
        
        # Check for backup issues (affects security + cost)
        if 'backup' in sec.lower() and 'backup' in cost.lower():
            concerns.append("Backup configuration affects both security posture and monthly costs")
        
        # Check for encryption (security + performance)
        if 'encryption' in sec.lower() and 'cpu' in perf.lower():
            concerns.append("Encryption at rest may impact CPU performance")
        
        # Autoscaling (performance + cost)
        if 'autoscaling' in perf.lower() and 'autoscaling' in cost.lower():
            concerns.append("Autoscaling configuration affects performance reliability and cost predictability")
        
        return concerns

    def _get_health_rating(self, score: int) -> str:
        """Convert numeric score to rating"""
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Fair"
        elif score >= 40:
            return "Poor"
        else:
            return "Critical"

