"""Search the knowledge base from the command line.

Usage (from backend/):
    python -m scripts.search "How many PTO days can I carry over?"
    python -m scripts.search "TT-200C operating temperature" --mode keyword -k 3
    python -m scripts.search "What caused the March outage?" --compare
    python -m scripts.search "..." --full              # print whole chunks
"""

import argparse
import textwrap

from app.retrieval import RetrievedChunk, search


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=5, help="number of results (default 5)")
    parser.add_argument("--mode", choices=["hybrid", "vector", "keyword"], default="hybrid")
    parser.add_argument("--compare", action="store_true", help="show vector, keyword and hybrid results")
    parser.add_argument("--full", action="store_true", help="print full chunk text")
    args = parser.parse_args()

    modes = ["vector", "keyword", "hybrid"] if args.compare else [args.mode]
    for mode in modes:
        results = search(args.query, k=args.k, mode=mode)
        print(f"\n── {mode} ──" + ("  (no matches)" if not results else ""))
        for i, chunk in enumerate(results, start=1):
            print_result(i, chunk, args.full)


def print_result(position: int, chunk: RetrievedChunk, full: bool) -> None:
    similarity = f"{chunk.similarity:.3f}" if chunk.similarity is not None else "  -  "
    ranks = " ".join(f"{name[0]}#{rank}" for name, rank in chunk.ranks.items())  # e.g. "v#2 k#1"
    print(f"{position}. sim {similarity}  {ranks:<11} {chunk.citation}")
    if full:
        print(textwrap.indent(chunk.content, "      │ "))
    else:
        print("      " + textwrap.shorten(chunk.content, width=110, placeholder=" …"))


if __name__ == "__main__":
    main()
