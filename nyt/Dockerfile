FROM continuumio/miniconda3

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY . .
RUN conda env create -f ./conda.yml

#RUN echo "conda activate $(head -1 /tmp/conda.yml | cut -d' ' -f2)" >> ~/.bashrc
#ENV PATH /opt/conda/envs/$(head -1 ./conda.yml | cut -d' ' -f2)/bin:$PATH
#ENV CONDA_DEFAULT_ENV $(head -1 ./conda.yml | cut -d' ' -f2)

# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "bot-env", "/bin/bash", "-c"]

# Demonstrate the environment is activated:
RUN echo "Make sure pandas is installed:"
RUN python -c "import pandas"
# Uploaded needed data for nltk:
RUN python -m nltk.downloader stopwords
RUN python -m nltk.downloader punkt

# The code to run when container is started:
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "bot-env", "python", "bot.py"]