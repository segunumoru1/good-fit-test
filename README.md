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

- **L06** has no price listed. Without a price, there is no way to compute a rate per mile — the core metric the entire ranking depends on. Assigning a placeholder (like $0 or an average) would produce a meaningless or misleading rank, so L06 is excluded and logged.
- **L07**  has no destination. Without a destination, the loaded miles and the deadhead-home leg are both undefined. Two of the three distance components are missing, making any rate calculation impossible. L07 is excluded and logged. 

`Both are flagged in the output with an explicit reason so a human dispatcher can follow up — they are not silently dropped.`

## One rejected high-payer

**L05** pays $2.514/mi - the second-best rate among complete rows - but runs a **Flatbed**
trailer. The driver only runs a hotshot gooseneck, so L05 is ineligible regardless of rate.
