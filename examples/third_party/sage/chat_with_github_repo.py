# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo >= 0.9.0",
#     "sage @ git+https://github.com/Storia-AI/sage.git@28ce9537e4ec08deee6b9a4e3392866819e0edac",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo, sys):
    mo.md(f"# 🤖💬 {sys.argv[-1]} ")
    return


@app.cell(hide_code=True)
def _(mo, sys):
    mo.md(
        f"""
        I'm a chatbot that can answer questions about the **{sys.argv[-1]}** GitHub repo. Ask me anything!
        """
    )
    return


@app.cell
def _():
    import sys
    import logging                                                                   

    import configargparse                                                            
    import gradio as gr                                                              
    import dotenv
    from langchain.chains import create_history_aware_retriever, create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain         
    from langchain.schema import AIMessage, HumanMessage                             
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder          

    import sage.config as sage_config                                                
    from sage.llm import build_llm_via_langchain                                     
    from sage.retriever import build_retriever_from_args                             

    _ = dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))
    return (
        AIMessage,
        ChatPromptTemplate,
        HumanMessage,
        MessagesPlaceholder,
        build_llm_via_langchain,
        build_retriever_from_args,
        configargparse,
        create_history_aware_retriever,
        create_retrieval_chain,
        create_stuff_documents_chain,
        logging,
        sage_config,
        sys,
    )


@app.cell
def _(
    ChatPromptTemplate,
    MessagesPlaceholder,
    build_llm_via_langchain,
    build_retriever_from_args,
    create_history_aware_retriever,
    create_retrieval_chain,
    create_stuff_documents_chain,
):
    def build_rag_chain(args):
        """Builds a RAG chain via LangChain."""
        llm = build_llm_via_langchain(args.llm_provider, args.llm_model)
        retriever = build_retriever_from_args(args)

        # Prompt to contextualize the latest query based on the chat history.
        contextualize_q_system_prompt = (
            "Given a chat history and the latest user question which might reference context in the chat history, "
            "formulate a standalone question which can be understood without the chat history. Do NOT answer the question, "
            "just reformulate it if needed and otherwise return it as is."
        )
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", contextualize_q_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )
        contextualize_q_llm = llm.with_config(tags=["contextualize_q_llm"])
        history_aware_retriever = create_history_aware_retriever(
            contextualize_q_llm, retriever, contextualize_q_prompt
        )

        qa_system_prompt = (
            f"You are my coding buddy, helping me quickly understand a GitHub repository called {args.repo_id}."
            "Assume I am an advanced developer and answer my questions in the most succinct way possible."
            "\n\n"
            "Here are some snippets from the codebase."
            "\n\n"
            "{context}"
        )
        qa_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", qa_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        rag_chain = create_retrieval_chain(
            history_aware_retriever, question_answer_chain
        )
        return rag_chain

    return (build_rag_chain,)


@app.cell
def _(configargparse, sage_config, sys):
    parser = configargparse.ArgParser(
        description="Batch-embeds a GitHub repository and its issues.",
        ignore_unknown_config_file_keys=True,
        prog="marimo edit chat.py --",
    )
    parser.add(
        "--share",
        default=False,
        help="Whether to make the gradio app publicly accessible.",
    )
    sage_config.add_config_args(parser)

    arg_validators = [
        sage_config.add_repo_args(parser),
        sage_config.add_embedding_args(parser),
        sage_config.add_vector_store_args(parser),
        sage_config.add_reranking_args(parser),
        sage_config.add_llm_args(parser),
    ]
    _argv = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else []
    args = parser.parse_args(_argv)
    for validator in arg_validators:
        validator(args)
    return (args,)


@app.cell
def _(args):
    args
    return


@app.cell
def _(AIMessage, HumanMessage, args, build_rag_chain, logging, mo):
    rag_chain = build_rag_chain(args)


    def source_md(file_path: str, url: str) -> str:
        """Formats a context source in Markdown."""
        return f"[{file_path}]({url})"


    async def predict(messages):
        """Performs one RAG operation."""
        message = messages[-1].content
        history_langchain_format = []
        for msg in messages[:-1]:
            if msg.role == "user":
                history_langchain_format.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history_langchain_format.append(AIMessage(content=msg.content))
        history_langchain_format.append(HumanMessage(content=message))

        query_rewrite = ""
        response = ""
        async for event in rag_chain.astream_events(
            {
                "input": message,
                "chat_history": history_langchain_format,
            },
            version="v1",
        ):
            if (
                event["name"] == "retrieve_documents"
                and "output" in event["data"]
                and event["data"]["output"] is not None
            ):
                sources = [
                    (doc.metadata["file_path"], doc.metadata["url"])
                    for doc in event["data"]["output"]
                ]
                # Deduplicate while preserving the order.
                sources = list(dict.fromkeys(sources))
                response += (
                    "## Sources:\n"
                    + "\n".join([source_md(s[0], s[1]) for s in sources])
                    + "\n## Response:\n"
                )

            elif event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"].content

                if "contextualize_q_llm" in event["tags"]:
                    query_rewrite += chunk
                else:
                    # This is the actual response to the user query.
                    if not response:
                        logging.info(f"Query rewrite: {query_rewrite}")
                    response += chunk
                    yield mo.md(response)

    return (predict,)


@app.cell
def _(mo, predict):
    mo.ui.chat(predict, prompts=["What does this repo do?", "Give me some sample code"])
    return


if __name__ == "__main__":
    app.run()
