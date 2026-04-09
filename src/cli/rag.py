#!/usr/bin/env python3
"""RAG CLI - Query event knowledge base."""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capabilities.rag.rag_minimal import build_index, query_rag


def run_build(args):
    """Build RAG index."""
    print("Building RAG index...")
    build_index()


def run_query(args):
    """Query RAG system."""
    result = query_rag(args.question, k=args.k)
    print(f"\n{'='*60}")
    print(f"问题: {args.question}")
    print(f"{'='*60}")
    print(f"\n回答:\n{result['answer']}")
    print(f"\n{'='*60}")
    print(f"参考事件 ({len(result['sources'])}条):")
    print(f"{'='*60}")
    for i, src in enumerate(result['sources'], 1):
        print(f"\n[{i}] {src['title']}")
        print(f"    时间: {src['date']} | 分类: {src['category']}")
        print(f"    公司: {src['companies']}")


def main():
    parser = argparse.ArgumentParser(description="RAG CLI for stock events")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build RAG index")

    query_parser = subparsers.add_parser("query", help="Query RAG system")
    query_parser.add_argument("question", type=str, help="Question to ask")
    query_parser.add_argument("-k", type=int, default=5,
                              help="Number of similar events to retrieve (default: 5)")

    args = parser.parse_args()

    if args.command == "build":
        run_build(args)
    elif args.command == "query":
        run_query(args)


if __name__ == "__main__":
    main()