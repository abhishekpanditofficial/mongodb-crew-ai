# MongoDB Atlas AI Ops Multi-Agent System

A comprehensive **5-agent CrewAI system** that performs automated analysis of MongoDB Atlas infrastructure across performance, security, cost efficiency, schema design, and generates executive-level consolidated reports with health scoring.

## 🎯 System Overview

This multi-agent system analyzes MongoDB Atlas environments and produces AI-driven reports covering:
- **Performance optimization** (CPU, slow queries, cluster sizing, **index recommendations**)
- **Security analysis** (IP access, roles, TLS, encryption)
- **Cost optimization** (overprovisioning, backup costs, idle resources)
- **Schema analysis & data modeling** (collection schemas, relationships, embedding vs referencing)
- **Executive synthesis** (health scoring, prioritization, ROI analysis)

## ✨ Latest Enhancement: Index Analysis & Query Optimization

The PerformanceAgent now provides **comprehensive index optimization recommendations** by integrating three powerful analysis methods:

### What's New?
1. **MongoDB Performance Advisor Integration** - Gets AI-powered index suggestions directly from Atlas
2. **Slow Query Analysis** - Identifies queries >100ms with full execution details  
3. **Index Efficiency Scoring** - Calculates scan ratios to detect missing indexes
4. **Ready-to-Execute Commands** - Provides exact `createIndex()` statements

### Example Output
When the agent runs, you'll now get detailed sections like:

**🎯 Index Suggestions:**
- Specific collections that need indexes
- Exact field names and sort orders `{ email: 1, created_at: -1 }`
- Expected query performance improvement (ms saved per query)
- JavaScript commands ready to paste into `mongosh`

**🐌 Slow Query Identification:**
- Query patterns causing performance issues
- Execution times and document scan counts
- Which collections are doing full scans

**📊 Efficiency Scoring:**
- Per-process scan ratio analysis (scanned objects / returned docs)
- "Poor/Fair/Good" efficiency ratings
- Quantified impact of missing indexes

> **Note:** Performance Advisor requires M10+ cluster tier. M0/M2 free tiers will show limited data.

## 🆕 NEW: Data Compliance & Security Scanning

The **SecurityAgent** now includes **mongodb_compliance_tool** that scans your actual database collections for compliance violations!

### What It Detects:

**1. PII (Personally Identifiable Information):**
- Unencrypted emails, phone numbers, addresses
- Social Security Numbers (regex: `\d{3}-\d{2}-\d{4}`)
- Passport numbers, national IDs
- Date of birth fields

**2. Sensitive Data Storage:**
- Plaintext passwords (checks if properly hashed)
- API keys, OAuth tokens, JWT tokens
- Private keys, certificates, secrets
- Field names like: `password`, `secret`, `token`, `api_key`

**3. PCI-DSS Violations (CRITICAL):**
- Credit card numbers (regex: `\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}`)
- CVV codes, card expiration dates
- Bank account numbers, routing numbers
- **Recommendation:** NEVER store credit cards - use Stripe/PayPal tokenization

**4. HIPAA Violations:**
- Medical records, diagnoses, prescriptions
- Health insurance information
- Patient identifiers without encryption

**5. GDPR Compliance:**
- Missing consent tracking (`consent_date`, `consent_version`)
- No data processing legal basis documented
- Data older than 2 years (retention policy violations)
- Missing "right to erasure" implementation

### Example Violations Found:

```markdown
### Collection: users
**Violation 1: PII Exposure**
- **Field:** `email`
- **Severity:** HIGH
- **Issue:** Email addresses stored without field-level encryption
- **Recommendation:** Implement MongoDB field-level encryption or ensure proper access controls
- **Compliance:** GDPR

**Violation 2: Sensitive Data**
- **Field:** `password`
- **Severity:** CRITICAL
- **Issue:** Password field detected - verify it's properly hashed (bcrypt/scrypt)
- **Recommendation:** Ensure passwords use bcrypt with salt rounds ≥ 12
- **Compliance:** GDPR, PCI-DSS

**Violation 3: GDPR - Missing Consent**
- **Severity:** MEDIUM
- **Issue:** User collection lacks GDPR consent tracking fields
- **Recommendation:** Add fields: `gdpr_consent`, `consent_date`, `consent_version`, `marketing_consent`
- **Compliance:** GDPR
```

### Scan Results Include:
- **Total violations** by severity (Critical/High/Medium/Low)
- **Per-collection breakdown** with field names
- **Compliance framework violations** (GDPR: 5, PCI-DSS: 0, HIPAA: 0)
- **Actionable recommendations** (delete, encrypt, hash, tokenize)

---

## 🆕 NEW: Schema Analysis & Data Modeling Agent

The **SchemaAgent** is a powerful addition that directly connects to your MongoDB database to analyze schemas and provide expert data modeling recommendations:

### What It Does:
1. **Discovers Collections** - Automatically finds all collections in your database
2. **Infers Schemas** - Samples 100+ documents per collection to understand data structures
3. **Detects Relationships** - Identifies foreign keys and references between collections
4. **Analyzes Indexes** - Lists existing indexes and flags missing ones
5. **Evaluates Data Models** - Assesses embedding vs referencing patterns
6. **Recommends Optimizations** - Provides 10-15 specific schema improvements

### Key Features:
- **Field Type Analysis:** Detects mixed types, nullability, nested objects, arrays
- **Relationship Mapping:** Creates ASCII diagrams showing collection dependencies
- **Index Recommendations:** Provides exact `createIndex()` commands for performance
- **Embedding vs Referencing:** Advises when to embed (1-to-few) vs reference (1-to-many)
- **Denormalization Strategies:** Identifies read-heavy data that should be duplicated
- **Document Size Analysis:** Flags oversized documents (>5KB) for optimization
- **Migration Plans:** Step-by-step instructions for implementing changes

### Example Recommendations:
```markdown
### Recommendation 1: Missing Index on Foreign Key
**Collection:** `orders`
**Issue:** Field `user_id` is not indexed, causing slow lookups
**Impact:** HIGH - Affects 50,000+ queries per day
**Command:**
```javascript
db.orders.createIndex({ user_id: 1 }, { name: "idx_user_id" });
```

### Recommendation 2: Embedding Opportunity
**Collections:** `users` → `addresses`
**Current:** `addresses` is a separate collection with `user_id` reference
**Issue:** 1-to-1 relationship causing unnecessary lookups
**Recommendation:** Embed `addresses` into `users` collection
**Benefit:** Eliminates 10,000+ daily JOIN-like queries, reduces latency by 80%
```

### Configuration:
Set these environment variables in `.env`:
```bash
MONGODB_CONNECTION_STRING=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DATABASE=your_database_name
```

## 🧠 Agent Architecture

### 1️⃣ **PerformanceAgent** ⚡
**Tool:** `atlas_performance_tool.py`

**Responsibilities:**
- Fetches 6-hour performance metrics (CPU, IOPS, memory, network, ops/sec)
- **🔍 Index Analysis:** Retrieves Performance Advisor suggestions, slow query logs, and calculates index efficiency ratios
- **📊 Query Performance:** Analyzes documents scanned vs returned to identify missing indexes
- **🐌 Slow Queries:** Identifies queries >100ms with execution patterns
- Detects bottlenecks and resource saturation
- Identifies underutilized clusters
- Generates detailed performance analysis per cluster

**Outputs:**
- Executive summary of performance health
- Per-cluster resource utilization analysis
- **INDEX OPTIMIZATION SECTION** with:
  - Suggested indexes from MongoDB Performance Advisor (specific field names)
  - Slow query analysis with execution times and query shapes
  - Index efficiency ratios (scan ratios indicating index usage)
  - Ready-to-execute `CREATE INDEX` commands
- Critical performance issues list
- 7-10 optimization recommendations including specific index creation steps

---

### 2️⃣ **SecurityAgent** 🔒
**Tools:** `atlas_security_tool.py` + `mongodb_compliance_tool.py` ✨NEW

**Responsibilities:**

**Infrastructure Security:**
- Audits IP access lists (detects 0.0.0.0/0 exposure)
- Analyzes database user roles and privileges
- Verifies TLS/SSL enforcement
- Checks encryption at rest configuration

**🆕 Data Compliance Scanning:**
- **PII Detection:** Scans collections for emails, phone numbers, SSNs, addresses
- **Sensitive Data:** Detects plaintext passwords, API keys, JWT tokens, secrets
- **PCI-DSS Compliance:** Flags credit card numbers, CVV codes (should NEVER be stored)
- **HIPAA Violations:** Identifies medical records, prescriptions, health data
- **GDPR Compliance:** Checks for consent tracking, data retention policies, legal basis
- **Pattern Matching:** Uses regex to find SSNs, credit cards, API keys in field values
- **Field Name Analysis:** Detects suspicious field names (password, secret, token, ssn, credit_card)

**Outputs:**
- Security posture assessment (Critical/High/Medium/Low)
- Infrastructure findings (IP access, TLS, encryption, roles)
- **DATA COMPLIANCE VIOLATIONS** section:
  - Violation counts by severity (Critical/High/Medium/Low)
  - Per-collection breakdown with specific field names
  - PII exposure list (what personal data is unencrypted)
  - Sensitive data found (passwords, keys, tokens)
  - PCI-DSS/GDPR/HIPAA violation summaries
- Compliance framework analysis
- 10-15 remediation steps prioritized by urgency
- Specific recommendations (hash passwords, delete credit cards, encrypt PII)

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

### 4️⃣ **SchemaAgent** 📐
**Tool:** `mongodb_schema_tool.py`

**Responsibilities:**
- **🔍 Collection Discovery:** Connects to MongoDB and discovers all collections
- **📊 Schema Inference:** Samples documents to infer field types, nested structures, arrays
- **🔗 Relationship Detection:** Identifies foreign keys, references, one-to-many relationships
- **📇 Index Analysis:** Lists existing indexes and identifies missing ones
- **🏗️ Data Modeling Evaluation:** Analyzes embedding vs referencing patterns
- **💡 Optimization Recommendations:** Provides expert guidance on schema refactoring

**Outputs:**
- Executive summary of schema health
- Complete collection inventory with statistics (doc count, sizes, indexes)
- Per-collection schema details with field types and sample values
- Relationship diagram showing how collections reference each other
- Data modeling analysis (when to embed vs reference)
- 10-15 specific schema optimization recommendations:
  - Missing indexes with CREATE INDEX commands
  - Embedding opportunities to reduce lookups
  - Denormalization strategies for read-heavy patterns
  - Document size optimizations
  - Schema refactoring for consistency
- Migration plan with step-by-step instructions
- Code examples and aggregation pipelines

**MongoDB Best Practices Applied:**
- Embed for 1-to-1 and 1-to-few relationships
- Reference for 1-to-many and many-to-many
- Index all foreign key fields
- Denormalize read-heavy data
- Avoid unbounded arrays (>1000 items)
- Keep documents under 16MB (ideally <5KB average)
- Use discriminator patterns for polymorphic data

---

### 5️⃣ **ReportSynthesizer** 📊
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

**Atlas Management API Tools** (use HTTP Digest Authentication):
- `atlas_performance_tool.py` - Fetches clusters, processes, measurements, **Performance Advisor suggestions**, **slow query logs**, and calculates **index efficiency ratios**
- `atlas_security_tool.py` - Fetches IP access lists, users, clusters, encryption config
- `atlas_cost_tool.py` - Combines cluster config + utilization metrics for cost analysis

**Direct MongoDB Connection Tools** (use connection string):
- `mongodb_schema_tool.py` - Connects to MongoDB database, discovers collections, infers schemas, detects relationships, analyzes indexes, recommends data modeling improvements

**Synthesis & Reporting Tools**:
- `report_synthesis_tool.py` - Parses report.md, calculates scores, correlates findings

### 🔍 Index Analysis Features (PerformanceAgent)

The Performance tool now provides comprehensive index optimization insights:

**1. Performance Advisor Suggested Indexes**
- Queries MongoDB's built-in Performance Advisor API
- Returns specific field names to index
- Includes expected query time savings
- Available on M10+ clusters

**2. Slow Query Logs**
- Identifies queries with >100ms execution time
- Shows query shapes and patterns
- Reports documents examined vs documents returned ratio
- Helps prioritize index creation by impact

**3. Index Efficiency Analysis**
- Calculates scan ratios: `scanned_objects / scanned_docs`
- **Ratio > 10:** Poor efficiency - missing indexes likely
- **Ratio 3-10:** Fair efficiency - review query patterns
- **Ratio < 3:** Good efficiency - indexes being used effectively
- Based on `QUERY_EXECUTOR_SCANNED` and `QUERY_EXECUTOR_SCANNED_OBJECTS` metrics

**Example Output:**
```markdown
### Index Optimization Recommendations

#### Cluster: Cluster0 | Process: cluster0-shard-00-00.mongodb.net:27017

**Suggested Indexes (Performance Advisor):**
- `db.users` - Create index on `{ email: 1, created_at: -1 }` → Expected savings: 250ms/query
- `db.orders` - Create index on `{ user_id: 1, status: 1 }` → Expected savings: 180ms/query

**Slow Queries Detected:**
- `db.users.find({ email: "..." }).sort({ created_at: -1 })` - 312ms avg execution time
- Examined: 125,000 docs | Returned: 1 doc | Scan Ratio: 125,000x

**Index Efficiency:**
- Scan Ratio: 45.2 (Poor - Missing indexes likely)
- Average Scanned Objects: 45,203
- Average Scanned Docs: 1,000

**Ready-to-Execute Commands:**
```javascript
db.users.createIndex({ email: 1, created_at: -1 }, { name: "idx_email_created" });
db.orders.createIndex({ user_id: 1, status: 1 }, { name: "idx_user_status" });
```
```

**Note:** Performance Advisor and slow query logs require:
- M10+ cluster tier (not available on M0/M2 free/shared tiers)
- Database profiling enabled (Atlas enables this automatically on M10+)
- Sufficient query history for analysis

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
