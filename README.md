# LLM-Powered Data Quality Monitor

![Preview](images/streamlit-streamlit_app.gif)

## Problem It Solves

Data quality issues lead to:

- **Broken dashboards** with incorrect visualizations
- **Revenue loss** from bad business decisions
- **Compliance violations** and regulatory issues
- **Lost trust** in data-driven insights

This tool automatically detects data anomalies and provides AI-powered explanations to help data teams quickly identify and resolve quality issues.

## Architecture

```mermaid
graph TD
    %% User Interaction
    subgraph A[User Interaction]
        direction TB
        A1[User Inputs] --> A2[Streamlit Dashboard]
        A2 --> A3[Display Metrics and Reports]
    end

    %% Data Sources
    subgraph B[User-Configured Data Sources]
        direction TB
        B1[File Upload]
        B2[S3 Connection Manager]
        B3[PostgreSQL Connection Manager]
    end

    %% Session State
    subgraph D[Session Memory Only]
        direction TB
        D1[Connection Configs]
        D2[OpenAI API Key]
        D3[Custom Rules]
    end

    %% Data Processing and Checks
    subgraph C[Processing and Checks]
        direction TB
        C1[Data Profiling] --> C2[Anomaly Detection]
        C2 --> C3[Custom Rule Evaluation]
        C3 --> C4[Row-Level Flagging]
        C4 --> C5[Summarize with OpenAI LLM]
        C5 --> C6[Generate Reports]
    end

    %% Connections
    B1 --> D1
    B2 --> D1
    B3 --> D1
    D1 --> C1
    D2 --> C5
    D3 --> C3
    C6 --> A3
```

## Technology Stack

- **Data Sources**: AWS S3, PostgreSQL, Local File Upload
- **File Formats**: CSV, Parquet, JSON, Excel
- **Processing**: Python, Pandas, NumPy
- **Visualization**: Plotly, Streamlit
- **AI**: OpenAI GPT-4o-mini (user-supplied key)
- **Security**: Session-only credential storage — nothing written to disk
- **Testing**: Pytest, Selenium, Streamlit-testing

## Pipeline Steps

1. **Connection Management**
   - Add named PostgreSQL or S3 connections within the session
   - Upload local files (CSV, Parquet, JSON, Excel)
   - All credentials held in session memory only — never written to disk
   - Test connections before use
   - Switch between multiple named connections within the same session

2. **Data Ingestion**
   - Browse and select tables from a connected PostgreSQL database
   - Browse and select objects from a connected S3 bucket
   - Upload files directly from your local machine
   - Optional row sampling to limit memory usage on large datasets
   - Load data into Pandas DataFrames

3. **Data Profiling**
   - Per-column statistics (min, max, mean, median, std, percentiles)
   - Unique value counts and cardinality analysis
   - Type inconsistency detection (mixed numeric/string in object columns)
   - Sample values for categorical columns

4. **Quality Analysis**
   - Detect missing values
   - Identify duplicate records
   - Find statistical outliers (IQR method)
   - Calculate skewness metrics
   - Check for zero-variance columns
   - Flag rows with anomalies (missing values or outliers)

5. **Custom Rules**
   - Define threshold-based quality rules
   - Check missing value percentages per column
   - Monitor duplicate row counts
   - Track outlier counts per numeric column
   - Evaluate rules and report violations

6. **AI Summarization**
   - User provides their own OpenAI API key via the sidebar (held in session memory only, never stored)
   - Send anomaly data to OpenAI
   - Generate human-readable explanations
   - Provide actionable recommendations

7. **Reporting**
   - Download CSV reports with anomaly summary, rule violations, and column profile
   - View flagged rows (up to 100) with missing values or outliers
   - Interactive visualizations of all detected issues
   - Sample data preview

## How to Run

### Prerequisites

- Python >= 3.11
- An OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- Access to a PostgreSQL database and/or AWS S3 bucket (optional)

### Run Locally

```bash
# Install the package and all dependencies
pip install -e .

# Start the Streamlit app
streamlit run src/llm_data_quality_monitor/dashboard/streamlit_app.py
```

No `.env` file or `secrets.toml` configuration is required. All credentials and connection details are entered through the app UI and held in session memory only.

### Streamlit Cloud Deployment

No secrets need to be pre-configured in the Streamlit Cloud secrets UI. Users supply their own OpenAI API key and connection credentials directly in the app — nothing is stored server-side.

## How to Test

```bash
# Run all unit tests
pytest tests/ -v

# Run specific test files
pytest tests/test_utils.py -v
pytest tests/test_anomaly_detector.py -v
pytest tests/test_streamlit_app.py -v

# Run Streamlit UI component tests
pytest tests/test_streamlit_ui.py -v

# Run Selenium integration tests (requires Chrome and ChromeDriver in PATH)
pytest tests/test_selenium_integration.py -v
```

## Usage

1. **Enter your OpenAI API key** in the sidebar — held in session memory only, never written to disk
2. **Select a data source**: File Upload, PostgreSQL, or S3
3. **For File Upload**:
   - Click "Upload a file" and select a CSV, Parquet, JSON, or Excel file
   - Optionally set a row limit in the sidebar to sample large files
4. **For PostgreSQL or S3**:
   - Add a connection using the expander form
   - PostgreSQL: host, port, database, username, password, SSL mode
   - S3: Access Key ID, Secret Access Key, region, optional session token
   - Test the connection before saving
   - Save the connection under a name to reuse within the session
   - Select a saved connection from the dropdown
   - Browse and select a table (PostgreSQL) or object (S3)
5. **Optional: Define Custom Rules**:
   - In the sidebar, expand "Custom Rules"
   - Add rules to check missing value percentages, duplicate rows, or outlier counts
   - Rules are evaluated after the quality check runs
6. **Run Data Quality Check** to analyze the data
7. **Review results**:
   - Interactive anomaly charts
   - Column profile with statistics
   - Flagged rows (rows with missing values or outliers)
   - Rule violations (if any rules were defined)
   - AI-generated summary
   - Raw anomaly data
   - Sample data preview
   - Download CSV report

## Credential Security

- All credentials (PostgreSQL passwords, AWS keys, session tokens, OpenAI API key) are held exclusively in Streamlit session state for the duration of the browser session
- Nothing is written to disk — closing the browser tab discards everything
- Each user's credentials are isolated to their own session
- No server-side storage, no encryption keys to manage, no credential files to protect

## Features

- ✅ **Multiple data sources** — File upload, PostgreSQL, S3
- ✅ **Multi-format file support** — CSV, Parquet, JSON, Excel
- ✅ **User-configurable connections** — no hardcoded credentials
- ✅ **Session-only credential storage** — nothing written to disk
- ✅ **Connection testing** before use
- ✅ **Multi-connection management** — save and switch between named connections within a session
- ✅ **Row sampling** — limit rows loaded to avoid memory issues
- ✅ **Data profiling** — per-column statistics and type validation
- ✅ **Custom rule engine** — define threshold-based quality checks
- ✅ **Row-level anomaly flagging** — identify specific rows with issues
- ✅ **Comprehensive anomaly detection** — missing values, duplicates, outliers, skewness, cardinality
- ✅ **Type inconsistency detection** — flag mixed numeric/string columns
- ✅ **AI-powered explanations** — OpenAI-generated insights
- ✅ **CSV report export** — download findings with anomalies, violations, and profiles
- ✅ **Interactive visualizations** — Plotly charts for all metrics
- ✅ **Comprehensive test suite** — 19+ unit tests
