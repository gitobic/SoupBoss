# utils - ATS Discovery Tools

## ats_probe.py

Company job board discovery utility. Feed it a list of company names and it tests which ATS platform they use.

**Usage:**
```bash
uv run python ats_probe.py
```

**Input:** CSV file with company names (one per line)
**Output:** CSV with company name, ATS platform (greenhouse/lever/smartrecruiters), and status

**Files:**
- `20250914list.csv` - Input company list
- `20250914list-out.csv` - Output results with ATS mappings

**Workflow:**
1. Create CSV with company names
2. Run ats_probe.py to test each company against all three ATS platforms
3. Review output CSV for successful matches
4. Use results to populate SoupBoss companies: `uv run python main.py companies add <company> --source <ats>`

**Notes:**
- Manual process but reliable
- Tests API endpoints to verify company job boards exist
- Some companies use different names for their job boards vs company name
