from python:3.8

ENV PYTHON_UNBUFFERED 1
ENV TZ=Asia/Seoul

workdir app
run --mount=type=cache,target=/root/.cache \
    pip install poetry
run poetry config virtualenvs.create false
copy pyproject.toml poetry.lock ./
run --mount=type=cache,target=/root/.cache \
    poetry install --no-dev --no-interaction && \
    pip install git+https://github.com/halcy/mastodon.py@7f23466
copy . ./

CMD ["python", "app.py"]
