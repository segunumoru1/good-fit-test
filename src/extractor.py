"""
Part A — reads the raw conversation transcript directly from the Excel workbook
and uses the Groq API to extract a structured driver profile.
"""

import json
import logging
import os
import groq
import pandas as pd

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI dispatcher assistant.
Read the phone call transcript between a dispatcher and a truck driver.
Extract a structured driver profile by carefully reading the natural speech.
The driver never states these as neat fields — find them in plain conversation.
Where a value is implied rather than said outright, use your best interpretation.

Return ONLY a valid JSON object with exactly these keys:
{
  "current_location": "City, STATE",
  "current_lat": <float>,
  "current_lon": <float>,
  "home_base": "City, STATE",
  "home_lat": <float>,
  "home_lon": <float>,
  "min_rate_per_mile": <float>,
  "equipment_types": ["type1", "type2"],
  "weight_capacity_lb": <int>
}

Rules:
- current_location: where the driver says they are RIGHT NOW
- home_base: where the driver normally operates from / lives
- lat/lon: use standard coordinates for the city (accurate to 4 decimal places)
- min_rate_per_mile: the minimum $/mile the driver will accept (as a float, e.g. 2.0)
- equipment_types: list only trailer types the driver actually runs (e.g. Hotshot, Gooseneck)
  Do NOT include a type just because the dispatcher mentions it.
- weight_capacity_lb: max weight the driver can haul (infer from context if not stated directly)

Return ONLY the JSON object. No explanation, no markdown, no preamble."""


def extract_driver_profile(workbook_path: str) -> dict:
    """
    Read the Sample Conversation sheet from the workbook, format the transcript,
    send it to Groq, and return the parsed driver profile.
    """
    logger.info(f"Loading workbook from {workbook_path} to read transcript...")
    if not os.path.exists(workbook_path):
        logger.error(f"Workbook file not found at path: {workbook_path}")
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    # Read the Sample Conversation sheet
    logger.info("Reading sheet 'Sample Conversation'...")
    df = pd.read_excel(workbook_path, sheet_name="Sample Conversation")
    
    transcript_lines = []
    for idx, row in df.iterrows():
        speaker = str(row.get("Speaker", "")).strip()
        dialogue = str(row.get("Dialogue", "")).strip()
        if speaker and dialogue and speaker != "nan" and dialogue != "nan":
            transcript_lines.append(f"{speaker}: {dialogue}")
            
    transcript = "\n".join(transcript_lines)
    logger.info(f"Successfully constructed transcript. Line count: {len(transcript_lines)}, character count: {len(transcript)}")
    logger.debug(f"Formatted transcript:\n{transcript}")

    # Call Groq API
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY environment variable is not set!")
        raise ValueError("GROQ_API_KEY environment variable is missing.")

    logger.info("Initializing Groq client and requesting driver profile extraction...")
    client = groq.Groq(api_key=api_key)

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"Here is the transcript:\n\n{transcript}",
            }
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw_response = chat_completion.choices[0].message.content
    logger.info("Received response from Groq API.")
    logger.debug(f"Raw API response: {raw_response}")

    if not raw_response:
        logger.error("Empty response received from Groq API.")
        raise ValueError("Empty response from Groq API.")

    raw = raw_response.strip()

    # Strip markdown fences if the model accidentally adds them despite response_format
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        profile = json.loads(raw)
        logger.info("Successfully parsed driver profile JSON.")
        logger.debug(f"Parsed driver profile: {profile}")
        return profile
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Groq response. Error: {e}. Raw content: {raw}")
        raise e


if __name__ == "__main__":
    import pathlib
    # Setup basic logging for standalone execution
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    here = pathlib.Path(__file__).parent.parent
    workbook = here / "data" / "Good_fit_test_clean.xlsx"
    profile = extract_driver_profile(str(workbook))
    print(json.dumps(profile, indent=2))

