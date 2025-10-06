# MongoDB Atlas AI Ops Multi-Agent System

A comprehensive **4-agent CrewAI system** that performs automated analysis of MongoDB Atlas infrastructure across performance, security, cost efficiency, and generates executive-level consolidated reports with health scoring.

## 🎯 System Overview

This multi-agent system analyzes MongoDB Atlas environments and produces AI-driven reports covering:
- **Performance optimization** (CPU, slow queries, cluster sizing)
- **Security analysis** (IP access, roles, TLS, encryption)
- **Cost optimization** (overprovisioning, backup costs, idle resources)
- **Executive synthesis** (health scoring, prioritization, ROI analysis)

## 🧠 Agent Architecture

### 1️⃣ **PerformanceAgent** ⚡
**Tool:** `atlas_performance_tool.py`

**Responsibilities:**
- Fetches 6-hour performance metrics (CPU, IOPS, memory, network, ops/sec)
- Detects bottlenecks and resource saturation
- Identifies underutilized clusters
- Generates detailed performance analysis per cluster

**Outputs:**
- Executive summary of performance health
- Per-cluster resource utilization analysis
- Critical performance issues list
- 5-7 optimization recommendations with expected impact

---

### 2️⃣ **SecurityAgent** 🔒
**Tool:** `atlas_security_tool.py`

**Responsibilities:**
- Audits IP access lists (detects 0.0.0.0/0 exposure)
- Analyzes database user roles and privileges
- Verifies TLS/SSL enforcement
- Checks encryption at rest configuration

**Outputs:**
- Security posture assessment (Critical/High/Medium/Low)
- Detailed findings per security domain
- Vulnerability analysis with attack scenarios
- Compliance implications (PCI-DSS, HIPAA, SOC2, GDPR)
- 5-7 remediation steps with urgency levels

---

### 3️⃣ **CostAgent** 💰
**Tool:** `atlas_cost_tool.py`

**Responsibilities:**
- Analyzes cluster sizing (M10/M20/M30 instances)
- Calculates actual vs provisioned capacity utilization
- Audits backup configurations and costs
- Identifies idle or overprovisioned resources
- Estimates monthly costs and potential savings

**Outputs:**
- Total monthly spend estimate
- Per-cluster cost breakdown with optimization recommendations
- Backup cost analysis
- Infrastructure waste report
- 7-10 cost-cutting actions with USD savings (monthly + annual)
- Summary table of all savings opportunities

---

### 4️⃣ **ReportSynthesizer** 📊
**Tool:** `report_synthesis_tool.py`

**Responsibilities:**
- Reads outputs from all three agents
- Calculates health scores (0-100) per domain:
  - Performance Health (35% weight)
  - Security Health (40% weight)
  - Cost Efficiency (25% weight)
- Identifies cross-cutting concerns
- Deduplicates overlapping findings
- Prioritizes issues by severity × business impact
- Generates executive summary with ROI analysis

**Outputs:**
- **Health Score Dashboard** - overall + per-domain scores
- **Executive Overview** - 3-paragraph C-level summary
- **Top 5 Critical Issues** - immediate action items
- **Cross-Domain Insights** - correlations between domains
- **Prioritized Action Plan** - 10-15 recommendations ranked by ROI
- **Risk Assessment** - quantified business impact if not addressed
- **Quick Wins** - 3-5 easy immediate optimizations
- **Long-term Strategy** - 6-12 month roadmap
- **Best Practices Comparison** - vs industry standards
- **Success Metrics** - KPIs to track improvement

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10+
- MongoDB Atlas account with API access
- OpenAI API key

### 1. Install Dependencies
```bash
pip install -e .
```

This installs:
- `crewai[tools]` - Multi-agent orchestration framework
- `requests` - HTTP library for Atlas API calls
- `python-dotenv` - Environment variable management
- `openai` - LLM integration

### 2. Configure Credentials

Create a `.env` file in the project root:

```bash
# MongoDB Atlas API Credentials
MONGODB_ATLAS_PUBLIC_KEY=your_public_key
MONGODB_ATLAS_PRIVATE_KEY=your_private_key
MONGODB_ATLAS_PROJECT_ID=your_project_id
MONGODB_ATLAS_ORG_ID=your_org_id

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key
```

**Get MongoDB Atlas API Keys:**
1. Go to MongoDB Atlas → Organization Access Manager
2. Create API Key with "Project Read Only" or higher permissions
3. Copy Public Key and Private Key

---

## 🏃 Running the System

### Run Complete Analysis (All 4 Agents)
```bash
python -m ai_latest_development.main
```
or

```bash
source venv/bin/activate && python -m ai_latest_development.main
```

Or using the installed script:
```bash
run_crew
```

### Execution Flow
1. **PerformanceAgent** runs first → appends to `report.md`
2. **SecurityAgent** runs second → appends to `report.md`
3. **CostAgent** runs third → appends to `report.md`
4. **ReportSynthesizer** runs last → reads full report, calculates health scores, appends executive summary

### Output
- **File:** `report.md` at project root
- **Sections:**
  1. Header with project info and timestamp
  2. ⚡ Performance Analysis
  3. 🔒 Security Audit
  4. 💰 Cost Optimization Analysis
  5. 📊 Executive Summary & Health Assessment

---

## 📊 Health Scoring System

### Overall Health Score (0-100)
Weighted average of three domains:
- **Performance:** 35% weight
- **Security:** 40% weight (most critical)
- **Cost Efficiency:** 25% weight

### Scoring Methodology

#### Performance Score
- **100:** All metrics healthy, no bottlenecks
- **Deductions:**
  - High CPU usage (>75%): -15 points
  - Disk saturation: -10 points
  - Network latency issues: -15 points
  - Missing metrics: -25 points

#### Security Score
- **100:** No vulnerabilities, best practices followed
- **Deductions:**
  - Open IP access (0.0.0.0/0): -30 points (CRITICAL)
  - Overly privileged users: -20 points
  - No encryption at rest: -25 points
  - TLS not enforced: -15 points

#### Cost Efficiency Score
- **100:** Optimal resource utilization, no waste
- **Deductions:**
  - Overprovisioned instances: -20 points
  - Idle/underutilized clusters: -15 points
  - Expensive backup configs: -10 points
  - Unnecessary replicas: -15 points

### Health Ratings
- **90-100:** Excellent ✅
- **75-89:** Good 👍
- **60-74:** Fair ⚠️
- **40-59:** Poor 🔴
- **0-39:** Critical 🚨

---

## 🔧 Architecture Details

### Tools
All tools use **HTTP Digest Authentication** to call MongoDB Atlas Management API:

- `atlas_performance_tool.py` - Fetches clusters, processes, and measurements
- `atlas_security_tool.py` - Fetches IP access lists, users, clusters, encryption config
- `atlas_cost_tool.py` - Combines cluster config + utilization metrics for cost analysis
- `report_synthesis_tool.py` - Parses report.md, calculates scores, correlates findings

### Agent Configuration
Agents are defined in `config/agents.yaml` with:
- Role and goal
- Backstory (persona)
- LLM model: `gpt-4o-mini` (cost-effective, fast)

### Task Configuration
Tasks are defined in `config/tasks.yaml` with:
- Detailed description (what to analyze and how)
- Expected output (format and content requirements)
- Agent assignment

### Crew Orchestration
- **Process:** Sequential (agents run one after another)
- **Callbacks:** Each task appends to `report.md` (no overwriting)
- **Dependencies:** Synthesis task depends on all three analysis tasks
- **Initialization:** `@before_kickoff` creates report header

---

## 📈 Example Findings

### Actual Issues Detected in Sample Run:

#### Security Vulnerabilities ⚠️
1. **CRITICAL:** IP access list contains `0.0.0.0/0` (open to internet)
2. **HIGH:** User `spotmeapp` has `atlasAdmin` role (excessive privileges)
3. **HIGH:** Encryption at rest disabled (no external KMS)

#### Cost Inefficiencies 💸
1. **M10 instance** potentially oversized for workload
2. **Replication factor 3** = 3x cost (may be unnecessary for dev/test)
3. **Provider backup + PIT enabled** = ~$20-40/month in backup costs
4. **3000 IOPS provisioned** - may exceed actual usage
5. **Autoscaling enabled without min/max limits** - cost unpredictability

**Estimated Monthly Waste:** $150-220/month ($1,800-2,640/year)

#### Performance Issues ⚡
1. Unable to retrieve detailed metrics (API permissions or cluster tier limitation)
2. Need Query Profiler enabled to identify slow queries
3. Index coverage analysis recommended

---

## 🎯 Use Cases

### For DevOps Teams
- **Automated health checks** - Run weekly/monthly audits
- **Cost optimization** - Identify overprovisioned resources
- **Security compliance** - Continuous security monitoring
- **Performance tuning** - Data-driven optimization recommendations

### For Engineering Managers
- **Executive reports** - Health scores and prioritized action plans
- **ROI justification** - Dollar-value savings estimates for optimizations
- **Risk assessment** - Quantified business impact of unaddressed issues

### For FinOps Teams
- **Cost visibility** - Detailed spend breakdown per cluster
- **Budget planning** - Forecast savings from right-sizing
- **Waste elimination** - Identify idle resources

### For Security Teams
- **Compliance auditing** - PCI-DSS, HIPAA, SOC2, GDPR checks
- **Vulnerability tracking** - Prioritized remediation roadmap
- **Risk scoring** - Severity-based issue prioritization

---

## 🔮 Future Enhancements

### Planned Features
1. **Historical Tracking** - Compare reports over time, track improvements
2. **Alerting** - Slack/email notifications for critical issues
3. **JSON/PDF Export** - Multiple output formats
4. **Custom Thresholds** - Configurable scoring weights and alert levels
5. **Multi-Project Support** - Analyze multiple Atlas projects in one run
6. **Automated Remediation** - Optional auto-fix for low-risk issues
7. **Integration** - Jira ticket creation, ServiceNow, PagerDuty

### Additional Agents
- **ComplianceAgent** - Deep-dive PCI/HIPAA/SOC2 audit
- **AvailabilityAgent** - Uptime analysis, backup testing, DR readiness
- **SchemaAgent** - Database schema optimization, index recommendations

---

## 📚 References

- [MongoDB Atlas API Documentation](https://www.mongodb.com/docs/atlas/reference/api-resources-spec/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [MongoDB Atlas Pricing](https://www.mongodb.com/pricing)
- [OpenAI API Documentation](https://platform.openai.com/docs/)

---

## 📝 License

This project is for educational and internal use.

---

## 👥 Support

For issues or questions:
1. Check MongoDB Atlas API permissions
2. Verify all environment variables are set
3. Ensure cluster tier supports monitoring API (M10+)
4. Review OpenAI API quota limits

---

**Built with CrewAI** 🤖 | **Powered by OpenAI GPT-4o-mini** 🧠 | **MongoDB Atlas Ready** 🍃
