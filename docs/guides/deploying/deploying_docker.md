# Deploying with Docker

## Prerequisites

- A marimo notebook or app: `app.py` that you want to deploy
- A `requirements.txt` file that contains the dependencies needed for your application to run

## Create a Dockerfile

`Dockerfile` is a text file that contains instructions for building a Docker image. Here's an example `Dockerfile` for a marimo notebook:

```Dockerfile
# syntax=docker/dockerfile:1.4

# Choose a python version that you know works with your application
FROM python:3.9-slim

WORKDIR /app

COPY --link requirements.txt .
# Install the requirements
RUN pip install -r requirements.txt

# You may copy more files like csv, images, data
COPY --link app.py .
# COPY . .



EXPOSE 8080

# Create a non-root user and switch to it
RUN useradd -m app_user
USER app_user

CMD [ "marimo", "run", "app.py", "-p", "8080" ]
```

## Breaking it down

`FROM` instructs what base image to choose. In our case, we chose Python 3.9 with the “slim” variant. This removes a lot of extra dependencies. You can always add them back as needed.

A slimmer Dockerfile (by bytes) means quick to build, deploy, and start up.

The `WORKDIR` sets the current working directory. In most cases, this does not need to be changed.

The `COPY` steps will copy all the necessary files into your docker. By adding `--link`, we end up creating a new layer that does not get invalidated by previous changes. This can be especially important for expensive install steps that do not depend on each other.

`RUN` lets us run shell commands. We can use this to install dependencies via apt-get, pip, or package managers. In our case, we use it to install our requirements.txt with pip.

Our `EXPOSE` step tells us which port is exposed to be accessed from outside the Docker container. This will need to match the port at which we run our marimo application on.

We then create a new user and switch to it with the `USER` instruction, in order to limit the permissions of the marimo application. This is not required, but recommended.

The final step `CMD` instructions what command to run when we run our docker container. Here we run our marimo application at the port 8080.

## Running your application locally

Once you have your Dockerfile and your application files. You can test it out locally.

```bash
# Build your image, and tag it as my_app
docker build -t my_app .

# Start your container, and map our port 8080 to our containers 8080
docker run -p 8080:8080 -it my_app

# Visit http://localhost:8080
```

After you have verified your application runs without errors. You can use these files to deploy your application on your favorite cloud provider that supports deploying dockererized applications.

## Health checks

You can add a health check to your Dockerfile to ensure that your application is running as expected. This is especially useful when deploying to a cloud provider.

```Dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8080/health || exit 1
```

The following endpoints may be useful when deploying your application:

- `/health` - A health check endpoint that returns a 200 status code if the application is running as expected
- `/healthz` - Same as above, just a different name for easier integration with cloud providers
- `/api/status` - A status endpoint that returns a JSON object with the status of the server
