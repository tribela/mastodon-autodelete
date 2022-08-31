FROM python:3.10

ENV PYTHON_UNBUFFERED 1
ENV TZ=Asia/Seoul

WORKDIR /app
ENV POETRY_VERSION 1.2.0
ENV PATH "/root/.local/bin:${PATH}"

RUN curl -sSL https://install.python-poetry.org | python -
RUN poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache \
    pip install git+https://github.com/halcy/mastodon.py@7f23466 && \
    poetry install --no-dev --no-interaction
COPY . ./

CMD ["python", "app.py"]
