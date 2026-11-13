"""Builds the SIMULATED lesson text used by the mock provider.

The mock can inject specific defects so that the retry loop has something real to fix:
  R1 = a factually wrong sentence, R5 = glossary missing terms used in the text,
  R6 = practical example not written as numbered steps.
"""
from __future__ import annotations

import re

from src.knowledge_base.loader import KnowledgeBase

WRONG_CLAIM = "RAG retrains the model every time a question is asked. [N15]"

_FULL_GLOSSARY = [
    ("RAG", "Retrieval-Augmented Generation. The AI finds information first and then writes the answer."),
    ("Language model", "An AI program that has learned from a huge amount of text and can write sentences."),
    ("Retrieval", "Finding the most useful pieces of information from a collection of documents."),
    ("Chunk", "A small piece of a document, such as one paragraph."),
    ("Embedding", "A list of numbers that shows the meaning of a piece of text."),
    ("Vector", "A list of numbers. An embedding is one kind of vector."),
    ("Vector database", "A database that stores embeddings and quickly finds the ones closest to a question."),
    ("Hallucination", "A confident answer from an AI that is wrong or has no real support."),
    ("Grounding", "Making sure an answer is based on real documents that you can check."),
    ("Fine-tuning", "Training a model more on extra data, which changes the model itself."),
]
_WEAK_GLOSSARY_KEEP = {"RAG", "Language model", "Retrieval", "Chunk", "Grounding", "Fine-tuning"}

_GOOD_EXAMPLE = """Let us follow a student named Riya. Her college library has a PDF with the library rules. She asks a chatbot: "How many books can I borrow at one time, and for how many days?" (The numbers in this example are made up.)
1. The college uploads the library rules PDF. This PDF is the document collection. [N5]
2. The system cuts the PDF into chunks. One chunk says: "Each student may borrow three books for fourteen days." [N6]
3. Each chunk is turned into an embedding and stored in the vector database. [N7]
4. Riya types her question. The system turns her question into an embedding too. [N9]
5. The vector search finds the chunk about borrowing books, because its meaning is close to her question. [N8]
6. The system sends Riya's question and that chunk to the language model. [N10]
7. The model writes: "You can borrow three books for fourteen days." It can also show which rules it used. [N11][N12]
Without RAG, the model might guess a number from some other college. With RAG, the answer comes from your own college rules."""

_WEAK_EXAMPLE = """Riya asks a chatbot about the library rules of her college. The RAG system finds the answer inside the rules PDF and the model writes it for her. [N11]"""


def build_lesson(defects: set[str], kb: KnowledgeBase) -> str:
    claim = f"\n{WRONG_CLAIM}" if "R1" in defects else ""
    glossary = [
        (t, d) for t, d in _FULL_GLOSSARY if "R5" not in defects or t in _WEAK_GLOSSARY_KEEP
    ]
    glossary_md = "\n".join(f"- **{t}**: {d}" for t, d in glossary)
    example = _WEAK_EXAMPLE if "R6" in defects else _GOOD_EXAMPLE

    body = f"""# Introduction to RAG: How AI Looks Up Facts Before It Answers

## What You Will Understand
After this lesson, you will be able to:
- Say in your own words what RAG means.
- Explain why AI needs RAG.
- Describe the steps RAG follows, from a question to an answer.
- Tell the difference between RAG and fine-tuning.

## Introduction
Imagine you ask a chatbot, "What is the last date to fill the exam form in my college?" The chatbot has never seen your college notice board. So it may guess. A wrong guess can cost you a lot. [N2]
RAG is one way to fix this problem. With RAG, the AI first looks up the right information. Then it writes the answer. This lesson explains how, in small steps.

## What It Means
RAG stands for Retrieval-Augmented Generation. Let us break the name into parts.
- Retrieval means finding the right information in a collection of documents. [N4]
- Generation means writing a new answer in simple sentences. [N4]
- Augmented means "made stronger by adding something". Here, the answer is made stronger by adding the retrieved information. [N10]
So RAG means: find useful information first, then use it to write the answer. [N3]
RAG was introduced in a research paper by Lewis and other researchers in 2020. [N1]
RAG is different from fine-tuning. Fine-tuning means training the model more on new data, so the model itself changes. RAG does not change the model. It gives the model the right information at question time. [N15]

## Why It Is Important
A language model is an AI program that has learned from a huge amount of text. The knowledge inside it is hard to update. It is also hard to know where an answer came from. [N2]
When the model does not know something, it can give an answer that sounds right but is wrong. This is called a hallucination. [N16]
RAG helps because the AI can look at real documents first. The AI can also show which documents it used, so you can check the answer. This is called grounding. [N12]

## How It Works, Step by Step
Think of RAG as a chain of six small steps.
1. Collect documents. We gather the files the AI should use, such as PDFs, notices, or web pages. [N5]
2. Cut them into chunks. A chunk is a small piece of text, like one paragraph. Small pieces are easier to search. [N6]
3. Turn chunks into embeddings. An embedding is a list of numbers that shows the meaning of a text. Texts with similar meaning get similar numbers. [N7]
4. Store them in a vector database. This is a special database that can quickly find numbers that are close to each other. [N7]
5. Retrieve. When you ask a question, the system also turns your question into numbers. It then finds the chunks whose numbers are closest. [N8][N9]
6. Generate. The best chunks are added to your question and sent to the language model. The model writes the answer using them. [N10][N11]
RAG does not retrain the model. The model stays the same. Only the information given to it changes. [N15]{claim}

## A Simple Analogy
Think of an open-book exam. In a closed-book exam, you write only from memory. You may forget things or make mistakes. In an open-book exam, you first find the right page in your book. Then you write the answer in your own words.
A plain AI is like the closed-book student. A RAG system is like the open-book student. The book is the document collection. Finding the page is retrieval. Writing the answer is generation. [N4]

## A Detailed Practical Example
{example}

## Where It Is Used
RAG is useful when an AI must answer from a particular set of documents. For example:
- A college chatbot that answers questions from admission rules. [N3]
- A company help desk that answers from its own manuals. [N3]
- A shop assistant that answers questions from a product list. [N3]
- A reading helper that answers questions from a textbook. [N3]

## Advantages and Limitations
Advantages:
- The AI can use new information without retraining the whole model. [N13]
- Answers can show their sources, so you can check them. [N12]
- You choose the documents, so the answers fit your needs. [N13]
Limitations:
- If the system finds the wrong chunk, the answer can be wrong too. [N14]
- RAG can reduce wrong answers, but it does not promise that every answer is right. [N14]
- Someone must keep the documents up to date. [N14]

## Important Terms
{glossary_md}

## Summary
- RAG means Retrieval-Augmented Generation: find information first, then write the answer. [N3]
- Documents are cut into chunks, turned into embeddings, and stored in a vector database. [N5][N7]
- At question time, the system retrieves the closest chunks and gives them to the language model. [N9][N10]
- RAG gives answers that you can check against sources, but it is not perfect. [N12][N14]

## Check Your Understanding
1. In your own words, what does the "retrieval" part of RAG do?
2. Why is an open-book exam a good picture for RAG?
3. What is a chunk, and why do we make chunks?
4. How is RAG different from fine-tuning?
5. Name one limitation of RAG.
"""
    ids = sorted(set(re.findall(r"\[(N\d+)\]", body)), key=lambda x: int(x[1:]))
    refs = "\n".join(
        f"- [{i}] " + "; ".join(kb.sources[s] for s in kb.notes[i].source_ids) for i in ids if i in kb.notes
    )
    return body + f"\n## References Used\n{refs}\n"
