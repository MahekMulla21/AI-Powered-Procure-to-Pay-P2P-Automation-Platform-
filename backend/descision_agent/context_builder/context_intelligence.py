import os
import pickle
import faiss
try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

try:
    import ollama
except ImportError:
    ollama = None

from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from pathlib import Path


# ─────────────────────────────────────────────
# LOAD ENV VARIABLES
# ─────────────────────────────────────────────

env_path = (
    Path(__file__).resolve().parent.parent
    / ".env"
)

load_dotenv(dotenv_path=env_path)


# ─────────────────────────────────────────────
# MODEL CONFIG
# ─────────────────────────────────────────────

MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "llama3"
)


# ─────────────────────────────────────────────
# NEO4J CONFIG
# ─────────────────────────────────────────────

NEO4J_URI = os.getenv("NEO4J_URI")

NEO4J_USERNAME = os.getenv(
    "NEO4J_USERNAME"
)

NEO4J_PASSWORD = os.getenv(
    "NEO4J_PASSWORD"
)

NEO4J_DATABASE = os.getenv(
    "NEO4J_DATABASE"
)


# ─────────────────────────────────────────────
# FAISS CONFIG
# ─────────────────────────────────────────────

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

FAISS_FOLDER = os.path.join(
    os.path.dirname(BASE_DIR), # backend/descision_agent/
    "rag",                     # we'll look where the main RAG search looks
    "faiss_db",
    "output"
)

# Better yet, let's use the absolute path for the main backend faiss_db
FAISS_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(BASE_DIR)), # backend/
    "faiss_db",
    "output"
)

INDEX_FILE = os.path.join(
    FAISS_FOLDER,
    "global_faiss.index"
)

MAPPING_FILE = os.path.join(
    FAISS_FOLDER,
    "global_faiss_mapping.pkl"
)


# ─────────────────────────────────────────────
# VALIDATE ENV VARIABLES
# ─────────────────────────────────────────────

required_envs = {

    "NEO4J_URI": NEO4J_URI,
    "NEO4J_USERNAME": NEO4J_USERNAME,
    "NEO4J_PASSWORD": NEO4J_PASSWORD,
    "NEO4J_DATABASE": NEO4J_DATABASE
}

missing = [

    key for key, value
    in required_envs.items()

    if not value
]

if missing:
    print(f"\n[WARN] Context Builder: Missing Neo4J ENV variables {missing}. Neo4J lookup will be disabled.")
    # No longer raising exception to prevent pipeline crash


# ─────────────────────────────────────────────
# LOAD EMBEDDING MODEL
# ─────────────────────────────────────────────

print("\nLoading embedding model...")

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# ─────────────────────────────────────────────
# LOAD FAISS
# ─────────────────────────────────────────────

print("\nLoading FAISS index...")

index = None
if os.path.exists(INDEX_FILE):
    try:
        index = faiss.read_index(INDEX_FILE)
    except Exception as e:
        print(f"Error loading FAISS index: {e}")
else:
    print(f"FAISS index not found at {INDEX_FILE}")

metadata_store = []
if os.path.exists(MAPPING_FILE):
    try:
        with open(MAPPING_FILE, "rb") as f:
            metadata_store = pickle.load(f)
        print(f"\nLoaded metadata chunks: {len(metadata_store)}")
    except Exception as e:
        print(f"Error loading mapping file: {e}")
else:
    print(f"Mapping file not found at {MAPPING_FILE}")


print("\nConnecting Neo4J...")

if GraphDatabase and not missing:
    try:
        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
        print("\nNeo4J Connected")
    except Exception as e:
        print(f"\nNeo4J Connection Failed: {e}")
        driver = None
else:
    if missing:
        print("\nNeo4J credentials missing. Email data lookup skipped.")
    else:
        print("\nNeo4J driver not installed. Email data lookup skipped.")
    driver = None


# ─────────────────────────────────────────────
# FETCH POLICY DATA
# ─────────────────────────────────────────────

def fetch_policy_data(
    top_k=3
):

    print("\nFetching policy data...")

    results = []

    total = min(
        top_k,
        len(metadata_store)
    )

    for i in range(total):

        item = metadata_store[i]

        content = item.get(
            "content",
            ""
        )

        results.append({

            "source": "policy",

            "content": content[:500],

            "page": item.get(
                "page",
                "N/A"
            ),

            "score": 0.90
        })

    print(
        f"\nPolicy records fetched: "
        f"{len(results)}"
    )

    return results


# ─────────────────────────────────────────────
# FETCH EMAIL DATA
# ─────────────────────────────────────────────

def fetch_email_data(limit=3):
    print("\nFetching email data...")
    if not driver:
        print("[WARN] Neo4J driver not available — skipping email lookup.")
        return []

    cypher_query = """

    MATCH (e:Email)

    RETURN
        coalesce(e.subject, "") AS subject,
        coalesce(e.body, "") AS body

    LIMIT $limit

    """

    results_list = []

    try:

        with driver.session(
            database=NEO4J_DATABASE
        ) as session:

            results = session.run(

                cypher_query,

                limit=limit
            )

            for row in results:

                body = (
                    row["body"] or ""
                ).lower()

                score = 0.5

                if "approved" in body:
                    score += 0.3

                if "urgent" in body:
                    score += 0.1

                if "escalation" in body:
                    score += 0.1

                if "rejected" in body:
                    score += 0.2

                results_list.append({

                    "source": "email",

                    "subject": (
                        row["subject"] or ""
                    )[:200],

                    "body": (
                        row["body"] or ""
                    )[:300],

                    "score": round(
                        score,
                        4
                    )
                })

    except Exception as e:

        print(
            f"\nNeo4J Error:\n{str(e)}"
        )

    print(
        f"\nEmail records fetched: "
        f"{len(results_list)}"
    )

    return results_list


# ─────────────────────────────────────────────
# EVIDENCE AGGREGATION
# ─────────────────────────────────────────────

def aggregate_evidence(
    policy_data,
    email_data
):

    print("\nAggregating evidence...")

    aggregated = []

    aggregated.extend(policy_data)

    aggregated.extend(email_data)

    print(
        f"\nTotal evidence count: "
        f"{len(aggregated)}"
    )

    return aggregated


# ─────────────────────────────────────────────
# RELEVANCE FILTERING
# ─────────────────────────────────────────────

def filter_relevant_evidence(
    aggregated_data,
    top_k=5
):

    print(
        "\nFiltering relevant evidence..."
    )

    filtered = sorted(

        aggregated_data,

        key=lambda x: x.get(
            "score",
            0
        ),

        reverse=True
    )

    filtered = filtered[:top_k]

    print(
        f"\nFiltered evidence count: "
        f"{len(filtered)}"
    )

    return filtered


# ─────────────────────────────────────────────
# BUILD LLM PROMPT
# ─────────────────────────────────────────────

def build_llm_prompt(
    filtered_evidence
):

    print("\nBuilding LLM prompt...")

    policy_section = []

    email_section = []

    for item in filtered_evidence:

        if item["source"] == "policy":

            policy_section.append(

                f"""
Policy Content:
{item['content']}

Page:
{item['page']}
"""
            )

        elif item["source"] == "email":

            email_section.append(

                f"""
Subject:
{item['subject']}

Email Body:
{item['body']}
"""
            )

    prompt = f"""

You are an Enterprise Business Context Builder.

Analyze:
1. Policy evidence
2. Email communication evidence

Generate:

1. POLICY FINDINGS
2. EMAIL FINDINGS
3. RISK SIGNALS
4. EXCEPTION SIGNALS
5. UNIFIED BUSINESS CONTEXT

POLICY EVIDENCE:

{chr(10).join(policy_section)}

EMAIL EVIDENCE:

{chr(10).join(email_section)}

IMPORTANT:

- Do NOT make final decisions
- Keep output concise
- Keep output professional
- Keep output enterprise-ready
- Output should be less than 250 words

"""

    print("\nPrompt Length:")
    print(len(prompt))

    return prompt


# ─────────────────────────────────────────────
# GENERATE BUSINESS CONTEXT
# ─────────────────────────────────────────────

def generate_business_context(
    prompt
):

    print(
        "\nGenerating business context..."
    )

    if not ollama:
        print("[WARN] ollama library not found — skipping AI business context generation.")
        return "Business context generation skipped: 'ollama' library not installed."

    try:

        response = ollama.chat(

            model=MODEL_NAME,

            messages=[

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            options={

                "temperature": 0.2,

                "num_predict": 250
            }
        )

        print(
            "\nLLM Response Received"
        )

        return response[
            "message"
        ][
            "content"
        ]

    except Exception as e:

        raise Exception(

            f"\nLLM ERROR:\n"
            f"{str(e)}"
        )


# ─────────────────────────────────────────────
# COMPLETE PIPELINE
# ─────────────────────────────────────────────

def run_context_pipeline():

    print(
        "\nStarting Context Intelligence Engine..."
    )

    # STEP 1 → FETCH POLICY DATA

    policy_data = fetch_policy_data()

    # STEP 2 → FETCH EMAIL DATA

    email_data = fetch_email_data()

    # STEP 3 → AGGREGATE EVIDENCE

    aggregated_data = aggregate_evidence(

        policy_data,

        email_data
    )

    # STEP 4 → FILTER RELEVANT EVIDENCE

    filtered_evidence = filter_relevant_evidence(
        aggregated_data
    )

    # STEP 5 → BUILD LLM PROMPT

    llm_prompt = build_llm_prompt(
        filtered_evidence
    )

    # STEP 6 → GENERATE BUSINESS CONTEXT

    final_context = generate_business_context(
        llm_prompt
    )

    return final_context


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":

    try:

        context = run_context_pipeline()

        print("\n")
        print("=" * 80)
        print("UNIFIED BUSINESS CONTEXT")
        print("=" * 80)
        print("\n")

        print(context)

    except Exception as e:

        print(
            f"\nPIPELINE ERROR:\n{str(e)}"
        )