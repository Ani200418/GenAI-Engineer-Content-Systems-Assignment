# Reference Material: Retrieval-Augmented Generation (RAG)

These notes are short paraphrased summaries written for this project. They are NOT direct quotations.
Source IDs starting with S are external documents; C1 means "author-curated general engineering explanation".
Before final submission, open each source URL and confirm the notes still match it.

## Sources
- S1: Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", NeurIPS 2020 — https://arxiv.org/abs/2005.11401
- S2: Amazon Web Services, "What is Retrieval-Augmented Generation (RAG)?" — https://aws.amazon.com/what-is/retrieval-augmented-generation/
- S3: Anthropic, "Introducing Contextual Retrieval" — https://www.anthropic.com/news/contextual-retrieval
- C1: Author-curated general explanation (no external quotation)

## Reference Notes
- N1 [S1]: The 2020 research paper by Lewis and colleagues introduced RAG models. They combine a pretrained language model (its built-in "parametric" memory) with an external, searchable collection of documents (the "non-parametric" memory).
- N2 [S1]: The paper's motivation was that knowledge stored inside a language model's parameters is hard to update and hard to trace back to a source (provenance).
- N3 [S2]: RAG means improving a large language model's answer by making it consult an authoritative knowledge source outside its training data before it writes the response.
- N4 [S2]: RAG has two parts: retrieval, which finds relevant information in external sources, and generation, which writes the response using that information.
- N5 [S2]: In document ingestion, external data (documents, databases, APIs) is prepared, converted into numerical representations, and stored in a vector database.
- N6 [S3]: Large collections of text are broken into smaller pieces called chunks, commonly no more than a few hundred tokens each.
- N7 [S3]: Each chunk is converted into a vector embedding, a list of numbers that captures its meaning, and the embeddings are stored in a vector database.
- N8 [S3]: A vector database finds the chunks whose embeddings are most similar in meaning to the user's query (semantic similarity search).
- N9 [S2]: At question time the user's question is converted into a vector representation and matched against the vector database to retrieve relevant information.
- N10 [S2]: The retrieved information is added to the prompt (the context) that is sent to the language model; this is the "augmentation" step.
- N11 [S2]: The language model then generates its answer using both the user's question and the retrieved context.
- N12 [S2, S1]: Because the answer is based on retrieved documents, the system can show which sources were used, so users can verify the answer. This is called grounding the answer in sources.
- N13 [S2]: Benefits: new information can be used without retraining the model, which is cost-effective; the answer can be based on current, specific content; developers keep control over which sources are used.
- N14 [C1]: Limitations: answer quality depends on retrieval quality; if the wrong or incomplete text is retrieved the answer can still be wrong. RAG can reduce wrong answers but cannot guarantee they never happen. The document collection must be kept up to date.
- N15 [C1, S2]: Fine-tuning means training a model further on extra data, which changes the model's internal parameters. RAG does not retrain or change the model; it supplies relevant information at question time. Updating RAG knowledge means updating documents, not retraining.
- N16 [C1]: A hallucination is a confident-sounding answer from an AI model that is wrong or has no support in real sources.
- N17 [S1]: The paper reported that its RAG models set state-of-the-art results on three open-domain question answering tasks at the time.
