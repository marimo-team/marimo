import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# PDF Q&A")
    return


@app.cell
def __(mo):
    mo.md(
        """
        This app lets you upload a PDF and ask questions about it.
        """
    )
    return


@app.cell
def __(mo):
    mo.accordion({
        "How is this app implemented?": """
        - Your PDF is tokenized into chunks, which are embedded using
        OpenAI's `text-embedding-ada-002`.
        - Your question is embedded using the same model.
        - We use an approximate k-nearest neighbor search on the PDF embeddings to
        retrieve relevant chunks.
        - The most relevant chunks are added to the context of your prompt, which
        is processed by a GPT model.
        """
    })
    return


@app.cell
def __(mo):
    openaikey = mo.ui.text(label="🤖 OpenAI Key", kind="password")
    config = mo.hstack([openaikey])
    mo.accordion({"⚙️ Config": config})
    return config, openaikey


@app.cell
def __(mo, openaikey):
    pdf = mo.ui.file(
        label="Upload PDF", filetypes=[".pdf"], multiple=False, kind="area"
    )
    pdf if openaikey.value else mo.md("👆 Add an Open AI Key").callout(kind="warn")
    return pdf,


@app.cell
def __(
    CharacterTextSplitter,
    FAISS,
    OpenAIEmbeddings,
    PdfReader,
    io,
    openai,
    openaikey,
    pdf,
):
    openai.api_key = openaikey.value


    def parse_pdf():
        if not pdf.value:
            print("No PDF")
            return None
        if not pdf.value[0]:
            print("No PDF")
            return None

        contents = pdf.value[0].contents
        file = io.BytesIO(contents)
        pdf_reader = PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()

        # split into chunks
        text_splitter = CharacterTextSplitter(
            separator="\n", chunk_size=1000, chunk_overlap=200, length_function=len
        )
        chunks = text_splitter.split_text(text)

        # create embeddings
        embeddings = OpenAIEmbeddings(openai_api_key=openaikey.value)
        return FAISS.from_texts(chunks, embeddings)


    knowledge_base = parse_pdf()
    return knowledge_base, parse_pdf


@app.cell
def __(mo):
    user_question = mo.ui.text_area(
        placeholder="💬 What are the 3 key points of the document?"
    ).form()
    user_question
    return user_question,


@app.cell
def __(
    OpenAI,
    get_openai_callback,
    knowledge_base,
    load_qa_chain,
    mo,
    openaikey,
    user_question,
):
    def query_pdf():
        if not user_question.value or not knowledge_base:
            return ""

        docs = knowledge_base.similarity_search(user_question.value)
        llm = OpenAI(openai_api_key=openaikey.value)
        chain = load_qa_chain(llm, chain_type="stuff")
        with get_openai_callback() as cb:
            response = chain.run(
                input_documents=docs, question=user_question.value
            )
            print(cb)
            return response


    res = query_pdf()
    mo.md(res)
    return query_pdf, res


@app.cell
def __():
    import marimo as mo
    import openai

    import io
    from PyPDF2 import PdfReader
    from langchain.text_splitter import CharacterTextSplitter
    from langchain.embeddings.openai import OpenAIEmbeddings
    from langchain.vectorstores import FAISS
    from langchain.chains.question_answering import load_qa_chain
    from langchain.llms import OpenAI
    from langchain.callbacks import get_openai_callback

    import os
    return (
        CharacterTextSplitter,
        FAISS,
        OpenAI,
        OpenAIEmbeddings,
        PdfReader,
        get_openai_callback,
        io,
        load_qa_chain,
        mo,
        openai,
        os,
    )


if __name__ == "__main__":
    app.run()
