import marimo

__generated_with = "0.3.8"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimolabs as molabs
    return molabs,


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    from dataclasses import asdict
    return asdict,


@app.cell
def __(mo):
    models = mo.ui.dropdown(
        {
            "audio classification": "models/ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
            "audio to audio": "models/facebook/xm_transformer_sm_all-en",
            "speech recognition": "models/facebook/wav2vec2-base-960h",
            "feature extraction": "models/julien-c/distilbert-feature-extraction",
            "fill mask": "models/distilbert/distilbert-base-uncased",
            "zero-shot classification": "models/facebook/bart-large-mnli",
            "image classification": "models/google/vit-base-patch16-224",
            "visual question answering": "models/dandelin/vilt-b32-finetuned-vqa",
            "sentence similarity": "models/sentence-transformers/all-MiniLM-L6-v2",
            "question answering": "models/deepset/xlm-roberta-base-squad2",
            "summarization": "models/facebook/bart-large-cnn",
            "text-classification": "models/distilbert/distilbert-base-uncased-finetuned-sst-2-english",
            "text generation": "models/openai-community/gpt2",
            "text2text generation": "models/valhalla/t5-small-qa-qg-hl",
            "translation": "models/Helsinki-NLP/opus-mt-en-ar",
            "text to speech": "models/julien-c/ljspeech_tts_train_tacotron2_raw_phn_tacotron_g2p_en_no_space_train",
            "text to image": "models/runwayml/stable-diffusion-v1-5",
            "token classification": "huggingface-course/bert-finetuned-ner",
            "document question answering": "models/impira/layoutlm-document-qa",
            "image to text": "models/Salesforce/blip-image-captioning-base",
            "object detection": "models/microsoft/table-transformer-detection",
        },
        label="Choose a model",
    )
    models
    return models,


@app.cell
def __(mo, models, molabs):
    mo.stop(models.value is None)

    model = molabs.huggingface.load(models.value)
    return model,


@app.cell
def __(model):
    model.examples
    return


@app.cell
def __(model):
    inputs = model.inputs
    inputs
    return inputs,


@app.cell
def __(inputs, mo, model):
    mo.stop(inputs.value is None, mo.md("Output not available: submit the model inputs 👆"))

    output = model.inference_function(inputs.value)
    return output,


@app.cell
def __(mo, output):
    import io
    b = io.BytesIO()
    output.save(b, format="PNG")
    mo.image(b)
    return b, io


if __name__ == "__main__":
    app.run()
