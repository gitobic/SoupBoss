# ref_data - Reference Files and Prototypes

This directory contains the original prototype scripts and reference data that evolved into SoupBoss.

## Files Overview

**company_list.xlsx** - Master list of companies and their ATS backends. Generated from `utils/ats_probe.py` output. Use this to restore companies after nuking the database (delete `soupboss.db`).

**greenhouse_fetch.py, lever_fetch.py, smartrecruiters_fetch.py** - Original standalone fetchers. These were the first working prototypes before the unified CLI. The core matching logic started here and was integrated into the main SoupBoss package.

**disney_data_importer.py, disney_workday_scraper.py** - Workday experiments. Disney was the test case. Workday has no public API, so this scrapes HTML/JSON responses. Disney works, other Workday sites untested.

## Directory Structure

- `resumes/` - Sample resumes from various sources for testing
- `utils/` - ATS probe utility for testing company job board availability
- `images/` - Screenshots and reference images

## Notes for Next Developer

- The `*_fetch.py` scripts are standalone and can run independently
- `company_list.xlsx` is your friend when you need to repopulate after DB resets
- Workday integration is half-baked - Disney works, everything else is TODO
- Use `utils/ats_probe.py` to validate new companies before adding them
