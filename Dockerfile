FROM python:3.12-slim-bullseye AS app

LABEL maintainer="Nicolas Schmid <nicolas.schmid@sed.ethz.ch>"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev git\
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
    && apt-get clean \
    && useradd --create-home python \
    && chown python:python -R /app

USER python

COPY --chown=python:python . .

RUN pip3 install --no-cache-dir --user -e .[hermes]

ENV PYTHONUNBUFFERED="true" \
    PYTHONPATH="." \
    PATH="${PATH}:/home/python/.local/bin" \
    USER="python"

EXPOSE 8000

CMD ["cd", "run_entrypoints", "&&", "python", "run_entrypoint_sui.py"]
