# Deploy to Hugging Face

Hugging Face is a platform that allows you to deploy machine learning models and applications easily.
You can deploy a marimo notebook as an interactive web app on Hugging Face Spaces with just a few steps.

## Deploy

To deploy your marimo notebook to Hugging Face Spaces:

1. Create a new Space on Hugging Face by forking or copying the following template: <https://huggingface.co/spaces/marimo-team/marimo-app-template/tree/main>
2. Replace the contents of the `app.py` file with your marimo notebook.
3. Update the `requirements.txt` file to include any other dependencies your notebook requires.
4. Commit these files to your Space, and Hugging Face will automatically deploy your marimo notebook as an interactive web app.

For more detailed instructions and advanced configurations, please refer to the [Hugging Face Spaces documentation](https://huggingface.co/docs/hub/spaces-overview).
