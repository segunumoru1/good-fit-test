# AI Dispatcher - Good Fit Test

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # add your GROQ_API_KEY
python main.py
```

## Running Tests

```bash
python -m unittest tests/test_pipeline.py
```

## What it does

**Part A - extraction (`src/extractor.py`)**  
Reads the conversation transcript directly from the `Sample Conversation` worksheet of the Excel workbook, formats it, and sends it to Groq (`llama-3.3-70b-versatile`) using a structured JSON prompt.
The model reads natural speech and returns a JSON driver profile. Fields are inferred from plain conversation: the driver never states them as neat fields.

**Part B - ranking (`src/ranker.py`)**  
Reads the loads spreadsheet (`Loads` sheet), applies three hard filters before ranking:
equipment type must match the driver's (Hotshot / Gooseneck), weight must be within
capacity (44,000 lb), and the effective rate must meet the driver's stated minimum ($2.00/mi).
Effective rate = price / (deadhead-to-origin + loaded miles + deadhead-home),
all distances via haversine from provided latitude/longitude.

## Incomplete rows

- **L06** (missing price): skipped - cannot compute any rate without a price.
- **L07** (missing destination): skipped - deadhead-home leg is undefined without coordinates.

## One rejected high-payer

**L05** pays $2.514/mi - the second-best rate among complete rows - but runs a **Flatbed**
trailer. The driver only runs a hotshot gooseneck, so L05 is ineligible regardless of rate.
