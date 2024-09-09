import marimo

__generated_with = "0.8.13"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        To run this, press "*Runtime*" and press "*Run all*" on a **free** Tesla T4 Google Colab instance!
        <div class="align-center">
          <a href="https://github.com/unslothai/unsloth"><img src="https://github.com/unslothai/unsloth/raw/main/images/unsloth%20new%20logo.png" width="115"></a>
          <a href="https://discord.gg/u54VK8m8tk"><img src="https://github.com/unslothai/unsloth/raw/main/images/Discord button.png" width="145"></a>
          <a href="https://ko-fi.com/unsloth"><img src="https://github.com/unslothai/unsloth/raw/main/images/Kofi button.png" width="145"></a></a> Join Discord if you need help + ⭐ <i>Star us on <a href="https://github.com/unslothai/unsloth">Github</a> </i> ⭐
        </div>

        To install Unsloth on your own computer, follow the installation instructions on our Github page [here](https://github.com/unslothai/unsloth?tab=readme-ov-file#-installation-instructions).

        You will learn how to do [data prep](#Data), how to [train](#Train), how to [run the model](#Inference), & [how to save it](#Save) (eg for Llama.cpp).

        [NEW] Llama-3.1 8b, 70b & 405b are trained on a crazy 15 trillion tokens with 128K long context lengths!

        **[NEW] Try 2x faster inference in a free Colab for Llama-3.1 8b Instruct [here](https://colab.research.google.com/drive/1T-YBVfnphoVc8E2E854qF3jdia2Ll2W2?usp=sharing)**
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        * We support Llama, Mistral, Phi-3, Gemma, Yi, DeepSeek, Qwen, TinyLlama, Vicuna, Open Hermes etc
        * We support 16bit LoRA or 4bit QLoRA. Both 2x faster.
        * `max_seq_length` can be set to anything, since we do automatic RoPE Scaling via [kaiokendev's](https://kaiokendev.github.io/til) method.
        * [**NEW**] We make Gemma-2 9b / 27b **2x faster**! See our [Gemma-2 9b notebook](https://colab.research.google.com/drive/1vIrqH5uYDQwsJ4-OO3DErvuv4pBgVwk4?usp=sharing)
        * [**NEW**] To finetune and auto export to Ollama, try our [Ollama notebook](https://colab.research.google.com/drive/1WZDi7APtQ9VsvOrQSSC5DDtxq159j8iZ?usp=sharing)
        * [**NEW**] We make Mistral NeMo 12B 2x faster and fit in under 12GB of VRAM! [Mistral NeMo notebook](https://colab.research.google.com/drive/17d3U-CAIwzmbDRqbZ9NnpHxCkmXB6LZ0?usp=sharing)
        """
    )
    return


@app.cell
def __():
    from unsloth import FastLanguageModel
    import torch
    max_seq_length = 2048 # Choose any! We auto support RoPE Scaling internally!
    dtype = None # None for auto detection. Float16 for Tesla T4, V100, Bfloat16 for Ampere+
    load_in_4bit = True # Use 4bit quantization to reduce memory usage. Can be False.

    # 4bit pre quantized models we support for 4x faster downloading + no OOMs.
    fourbit_models = [
        "unsloth/Meta-Llama-3.1-8B-bnb-4bit",      # Llama-3.1 15 trillion tokens model 2x faster!
        "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
        "unsloth/Meta-Llama-3.1-70B-bnb-4bit",
        "unsloth/Meta-Llama-3.1-405B-bnb-4bit",    # We also uploaded 4bit for 405b!
        "unsloth/Mistral-Nemo-Base-2407-bnb-4bit", # New Mistral 12b 2x faster!
        "unsloth/Mistral-Nemo-Instruct-2407-bnb-4bit",
        "unsloth/mistral-7b-v0.3-bnb-4bit",        # Mistral v3 2x faster!
        "unsloth/mistral-7b-instruct-v0.3-bnb-4bit",
        "unsloth/Phi-3.5-mini-instruct",           # Phi-3.5 2x faster!
        "unsloth/Phi-3-medium-4k-instruct",
        "unsloth/gemma-2-9b-bnb-4bit",
        "unsloth/gemma-2-27b-bnb-4bit",            # Gemma 2x faster!
    ] # More models at https://huggingface.co/unsloth

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = "unsloth/Meta-Llama-3.1-8B",
        max_seq_length = max_seq_length,
        dtype = dtype,
        load_in_4bit = load_in_4bit,
        # token = "hf_...", # use one if using gated models like meta-llama/Llama-2-7b-hf
    )
    return (
        FastLanguageModel,
        dtype,
        fourbit_models,
        load_in_4bit,
        max_seq_length,
        model,
        tokenizer,
        torch,
    )


@app.cell
def __(mo):
    mo.md(r"""We now add LoRA adapters so we only need to update 1 to 10% of all parameters!""")
    return


@app.cell
def __(FastLanguageModel, model):
    model = FastLanguageModel.get_peft_model(
        model,
        r = 16, # Choose any number > 0 ! Suggested 8, 16, 32, 64, 128
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj",],
        lora_alpha = 16,
        lora_dropout = 0, # Supports any, but = 0 is optimized
        bias = "none",    # Supports any, but = "none" is optimized
        # [NEW] "unsloth" uses 30% less VRAM, fits 2x larger batch sizes!
        use_gradient_checkpointing = "unsloth", # True or "unsloth" for very long context
        random_state = 3407,
        use_rslora = False,  # We support rank stabilized LoRA
        loftq_config = None, # And LoftQ
    )
    return model,


@app.cell
def __(mo):
    mo.md(
        r"""
        <a name="Data"></a>
        ### Data Prep
        We now use the Alpaca dataset from [yahma](https://huggingface.co/datasets/yahma/alpaca-cleaned), which is a filtered version of 52K of the original [Alpaca dataset](https://crfm.stanford.edu/2023/03/13/alpaca.html). You can replace this code section with your own data prep.

        **[NOTE]** To train only on completions (ignoring the user's input) read TRL's docs [here](https://huggingface.co/docs/trl/sft_trainer#train-on-completions-only).

        **[NOTE]** Remember to add the **EOS_TOKEN** to the tokenized output!! Otherwise you'll get infinite generations!

        If you want to use the `llama-3` template for ShareGPT datasets, try our conversational [notebook](https://colab.research.google.com/drive/1XamvWYinY6FOSX9GLvnqSjjsNflxdhNc?usp=sharing).

        For text completions like novel writing, try this [notebook](https://colab.research.google.com/drive/1ef-tab5bhkvWmBOObepl1WgJvfvSzn5Q?usp=sharing).
        """
    )
    return


@app.cell
def __(tokenizer):
    alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

    ### Instruction:
    {}

    ### Input:
    {}

    ### Response:
    {}"""

    EOS_TOKEN = tokenizer.eos_token # Must add EOS_TOKEN
    def formatting_prompts_func(examples):
        instructions = examples["instruction"]
        inputs       = examples["input"]
        outputs      = examples["output"]
        texts = []
        for instruction, input, output in zip(instructions, inputs, outputs):
            # Must add EOS_TOKEN, otherwise your generation will go on forever!
            text = alpaca_prompt.format(instruction, input, output) + EOS_TOKEN
            texts.append(text)
        return { "text" : texts, }
    pass

    from datasets import load_dataset
    dataset = load_dataset("yahma/alpaca-cleaned", split = "train")
    dataset = dataset.map(formatting_prompts_func, batched = True,)
    return (
        EOS_TOKEN,
        alpaca_prompt,
        dataset,
        formatting_prompts_func,
        load_dataset,
    )


@app.cell
def __(mo):
    mo.md(
        r"""
        <a name="Train"></a>
        ### Train the model
        Now let's use Huggingface TRL's `SFTTrainer`! More docs here: [TRL SFT docs](https://huggingface.co/docs/trl/sft_trainer). We do 60 steps to speed things up, but you can set `num_train_epochs=1` for a full run, and turn off `max_steps=None`. We also support TRL's `DPOTrainer`!
        """
    )
    return


@app.cell
def __(dataset, max_seq_length, model, tokenizer):
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from unsloth import is_bfloat16_supported

    trainer = SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = dataset,
        dataset_text_field = "text",
        max_seq_length = max_seq_length,
        dataset_num_proc = 2,
        packing = False, # Can make training 5x faster for short sequences.
        args = TrainingArguments(
            per_device_train_batch_size = 2,
            gradient_accumulation_steps = 4,
            warmup_steps = 5,
            # num_train_epochs = 1, # Set this for 1 full training run.
            max_steps = 60,
            learning_rate = 2e-4,
            fp16 = not is_bfloat16_supported(),
            bf16 = is_bfloat16_supported(),
            logging_steps = 1,
            optim = "adamw_8bit",
            weight_decay = 0.01,
            lr_scheduler_type = "linear",
            seed = 3407,
            output_dir = "outputs",
        ),
    )
    return SFTTrainer, TrainingArguments, is_bfloat16_supported, trainer


@app.cell
def __(torch):
    #@title Show current memory stats
    gpu_stats = torch.cuda.get_device_properties(0)
    start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
    print(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
    print(f"{start_gpu_memory} GB of memory reserved.")
    return gpu_stats, max_memory, start_gpu_memory


@app.cell
def __(trainer):
    trainer_stats = trainer.train()
    return trainer_stats,


@app.cell
def __(max_memory, start_gpu_memory, torch, trainer_stats):
    #@title Show final memory and time stats
    used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
    used_percentage = round(used_memory         /max_memory*100, 3)
    lora_percentage = round(used_memory_for_lora/max_memory*100, 3)
    print(f"{trainer_stats.metrics['train_runtime']} seconds used for training.")
    print(f"{round(trainer_stats.metrics['train_runtime']/60, 2)} minutes used for training.")
    print(f"Peak reserved memory = {used_memory} GB.")
    print(f"Peak reserved memory for training = {used_memory_for_lora} GB.")
    print(f"Peak reserved memory % of max memory = {used_percentage} %.")
    print(f"Peak reserved memory for training % of max memory = {lora_percentage} %.")
    return (
        lora_percentage,
        used_memory,
        used_memory_for_lora,
        used_percentage,
    )


@app.cell
def __(mo):
    mo.md(
        r"""
        <a name="Inference"></a>
        ### Inference
        Let's run the model! You can change the instruction and input - leave the output blank!

        **[NEW] Try 2x faster inference in a free Colab for Llama-3.1 8b Instruct [here](https://colab.research.google.com/drive/1T-YBVfnphoVc8E2E854qF3jdia2Ll2W2?usp=sharing)**
        """
    )
    return


@app.cell
def __(FastLanguageModel, alpaca_prompt, model, tokenizer):
    # alpaca_prompt = Copied from above
    FastLanguageModel.for_inference(model) # Enable native 2x faster inference
    inputs = tokenizer(
    [
        alpaca_prompt.format(
            "Continue the fibonnaci sequence.", # instruction
            "1, 1, 2, 3, 5, 8", # input
            "", # output - leave this blank for generation!
        )
    ], return_tensors = "pt").to("cuda")

    outputs = model.generate(**inputs, max_new_tokens = 64, use_cache = True)
    tokenizer.batch_decode(outputs)
    return inputs, outputs


@app.cell
def __(mo):
    mo.md(r"""You can also use a `TextStreamer` for continuous inference - so you can see the generation token by token, instead of waiting the whole time!""")
    return


@app.cell
def __(FastLanguageModel, alpaca_prompt, model, tokenizer):
    # alpaca_prompt = Copied from above
    FastLanguageModel.for_inference(model) # Enable native 2x faster inference
    inputs = tokenizer(
    [
        alpaca_prompt.format(
            "Continue the fibonnaci sequence.", # instruction
            "1, 1, 2, 3, 5, 8", # input
            "", # output - leave this blank for generation!
        )
    ], return_tensors = "pt").to("cuda")

    from transformers import TextStreamer
    text_streamer = TextStreamer(tokenizer)
    _ = model.generate(**inputs, streamer = text_streamer, max_new_tokens = 128)
    return TextStreamer, inputs, text_streamer


@app.cell
def __(mo):
    mo.md(
        r"""
        <a name="Save"></a>
        ### Saving, loading finetuned models
        To save the final model as LoRA adapters, either use Huggingface's `push_to_hub` for an online save or `save_pretrained` for a local save.

        **[NOTE]** This ONLY saves the LoRA adapters, and not the full model. To save to 16bit or GGUF, scroll down!
        """
    )
    return


@app.cell
def __(model, tokenizer):
    model.save_pretrained("lora_model") # Local saving
    tokenizer.save_pretrained("lora_model")
    # model.push_to_hub("your_name/lora_model", token = "...") # Online saving
    # tokenizer.push_to_hub("your_name/lora_model", token = "...") # Online saving
    return


@app.cell
def __(mo):
    mo.md(r"""Now if you want to load the LoRA adapters we just saved for inference, set `False` to `True`:""")
    return


@app.cell
def __(alpaca_prompt, dtype, load_in_4bit, max_seq_length):
    if False:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name = "lora_model", # YOUR MODEL YOU USED FOR TRAINING
            max_seq_length = max_seq_length,
            dtype = dtype,
            load_in_4bit = load_in_4bit,
        )
        FastLanguageModel.for_inference(model) # Enable native 2x faster inference

    # alpaca_prompt = You MUST copy from above!

    inputs = tokenizer(
    [
        alpaca_prompt.format(
            "What is a famous tall tower in Paris?", # instruction
            "", # input
            "", # output - leave this blank for generation!
        )
    ], return_tensors = "pt").to("cuda")

    from transformers import TextStreamer
    text_streamer = TextStreamer(tokenizer)
    _ = model.generate(**inputs, streamer = text_streamer, max_new_tokens = 128)
    return (
        FastLanguageModel,
        TextStreamer,
        inputs,
        model,
        text_streamer,
        tokenizer,
    )


@app.cell
def __(mo):
    mo.md(r"""You can also use Hugging Face's `AutoModelForPeftCausalLM`. Only use this if you do not have `unsloth` installed. It can be hopelessly slow, since `4bit` model downloading is not supported, and Unsloth's **inference is 2x faster**.""")
    return


@app.cell
def __(load_in_4bit):
    if False:
        # I highly do NOT suggest - use Unsloth if possible
        from peft import AutoPeftModelForCausalLM
        from transformers import AutoTokenizer
        model = AutoPeftModelForCausalLM.from_pretrained(
            "lora_model", # YOUR MODEL YOU USED FOR TRAINING
            load_in_4bit = load_in_4bit,
        )
        tokenizer = AutoTokenizer.from_pretrained("lora_model")
    return AutoPeftModelForCausalLM, AutoTokenizer, model, tokenizer


@app.cell
def __(mo):
    mo.md(
        r"""
        ### Saving to float16 for VLLM

        We also support saving to `float16` directly. Select `merged_16bit` for float16 or `merged_4bit` for int4. We also allow `lora` adapters as a fallback. Use `push_to_hub_merged` to upload to your Hugging Face account! You can go to https://huggingface.co/settings/tokens for your personal tokens.
        """
    )
    return


@app.cell
def __(model, tokenizer):
    # Merge to 16bit
    if False: model.save_pretrained_merged("model", tokenizer, save_method = "merged_16bit",)
    if False: model.push_to_hub_merged("hf/model", tokenizer, save_method = "merged_16bit", token = "")

    # Merge to 4bit
    if False: model.save_pretrained_merged("model", tokenizer, save_method = "merged_4bit",)
    if False: model.push_to_hub_merged("hf/model", tokenizer, save_method = "merged_4bit", token = "")

    # Just LoRA adapters
    if False: model.save_pretrained_merged("model", tokenizer, save_method = "lora",)
    if False: model.push_to_hub_merged("hf/model", tokenizer, save_method = "lora", token = "")
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        ### GGUF / llama.cpp Conversion
        To save to `GGUF` / `llama.cpp`, we support it natively now! We clone `llama.cpp` and we default save it to `q8_0`. We allow all methods like `q4_k_m`. Use `save_pretrained_gguf` for local saving and `push_to_hub_gguf` for uploading to HF.

        Some supported quant methods (full list on our [Wiki page](https://github.com/unslothai/unsloth/wiki#gguf-quantization-options)):
        * `q8_0` - Fast conversion. High resource use, but generally acceptable.
        * `q4_k_m` - Recommended. Uses Q6_K for half of the attention.wv and feed_forward.w2 tensors, else Q4_K.
        * `q5_k_m` - Recommended. Uses Q6_K for half of the attention.wv and feed_forward.w2 tensors, else Q5_K.

        [**NEW**] To finetune and auto export to Ollama, try our [Ollama notebook](https://colab.research.google.com/drive/1WZDi7APtQ9VsvOrQSSC5DDtxq159j8iZ?usp=sharing)
        """
    )
    return


@app.cell
def __(model, tokenizer):
    # Save to 8bit Q8_0
    if False: model.save_pretrained_gguf("model", tokenizer,)
    # Remember to go to https://huggingface.co/settings/tokens for a token!
    # And change hf to your username!
    if False: model.push_to_hub_gguf("hf/model", tokenizer, token = "")

    # Save to 16bit GGUF
    if False: model.save_pretrained_gguf("model", tokenizer, quantization_method = "f16")
    if False: model.push_to_hub_gguf("hf/model", tokenizer, quantization_method = "f16", token = "")

    # Save to q4_k_m GGUF
    if False: model.save_pretrained_gguf("model", tokenizer, quantization_method = "q4_k_m")
    if False: model.push_to_hub_gguf("hf/model", tokenizer, quantization_method = "q4_k_m", token = "")

    # Save to multiple GGUF options - much faster if you want multiple!
    if False:
        model.push_to_hub_gguf(
            "hf/model", # Change hf to your username!
            tokenizer,
            quantization_method = ["q4_k_m", "q8_0", "q5_k_m",],
            token = "", # Get a token at https://huggingface.co/settings/tokens
        )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        Now, use the `model-unsloth.gguf` file or `model-unsloth-Q4_K_M.gguf` file in `llama.cpp` or a UI based system like `GPT4All`. You can install GPT4All by going [here](https://gpt4all.io/index.html).

        **[NEW] Try 2x faster inference in a free Colab for Llama-3.1 8b Instruct [here](https://colab.research.google.com/drive/1T-YBVfnphoVc8E2E854qF3jdia2Ll2W2?usp=sharing)**
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        And we're done! If you have any questions on Unsloth, we have a [Discord](https://discord.gg/u54VK8m8tk) channel! If you find any bugs or want to keep updated with the latest LLM stuff, or need help, join projects etc, feel free to join our Discord!

        Some other links:
        1. Zephyr DPO 2x faster [free Colab](https://colab.research.google.com/drive/15vttTpzzVXv_tJwEk-hIcQ0S9FcEWvwP?usp=sharing)
        2. Llama 7b 2x faster [free Colab](https://colab.research.google.com/drive/1lBzz5KeZJKXjvivbYvmGarix9Ao6Wxe5?usp=sharing)
        3. TinyLlama 4x faster full Alpaca 52K in 1 hour [free Colab](https://colab.research.google.com/drive/1AZghoNBQaMDgWJpi4RbffGM1h6raLUj9?usp=sharing)
        4. CodeLlama 34b 2x faster [A100 on Colab](https://colab.research.google.com/drive/1y7A0AxE3y8gdj4AVkl2aZX47Xu3P1wJT?usp=sharing)
        5. Mistral 7b [free Kaggle version](https://www.kaggle.com/code/danielhanchen/kaggle-mistral-7b-unsloth-notebook)
        6. We also did a [blog](https://huggingface.co/blog/unsloth-trl) with 🤗 HuggingFace, and we're in the TRL [docs](https://huggingface.co/docs/trl/main/en/sft_trainer#accelerate-fine-tuning-2x-using-unsloth)!
        7. `ChatML` for ShareGPT datasets, [conversational notebook](https://colab.research.google.com/drive/1Aau3lgPzeZKQ-98h69CCu1UJcvIBLmy2?usp=sharing)
        8. Text completions like novel writing [notebook](https://colab.research.google.com/drive/1ef-tab5bhkvWmBOObepl1WgJvfvSzn5Q?usp=sharing)
        9. [**NEW**] We make Phi-3 Medium / Mini **2x faster**! See our [Phi-3 Medium notebook](https://colab.research.google.com/drive/1hhdhBa1j_hsymiW9m-WzxQtgqTH_NHqi?usp=sharing)
        10. [**NEW**] We make Gemma-2 9b / 27b **2x faster**! See our [Gemma-2 9b notebook](https://colab.research.google.com/drive/1vIrqH5uYDQwsJ4-OO3DErvuv4pBgVwk4?usp=sharing)
        11. [**NEW**] To finetune and auto export to Ollama, try our [Ollama notebook](https://colab.research.google.com/drive/1WZDi7APtQ9VsvOrQSSC5DDtxq159j8iZ?usp=sharing)
        12. [**NEW**] We make Mistral NeMo 12B 2x faster and fit in under 12GB of VRAM! [Mistral NeMo notebook](https://colab.research.google.com/drive/17d3U-CAIwzmbDRqbZ9NnpHxCkmXB6LZ0?usp=sharing)

        <div class="align-center">
          <a href="https://github.com/unslothai/unsloth"><img src="https://github.com/unslothai/unsloth/raw/main/images/unsloth%20new%20logo.png" width="115"></a>
          <a href="https://discord.gg/u54VK8m8tk"><img src="https://github.com/unslothai/unsloth/raw/main/images/Discord.png" width="145"></a>
          <a href="https://ko-fi.com/unsloth"><img src="https://github.com/unslothai/unsloth/raw/main/images/Kofi button.png" width="145"></a></a> Support our work if you can! Thanks!
        </div>
        """
    )
    return


if __name__ == "__main__":
    app.run()
