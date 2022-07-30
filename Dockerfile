from python:3.8

workdir app
run pip install poetry
run poetry config virtualenvs.create false
copy pyproject.toml poetry.lock ./
run poetry install --no-dev --no-interaction && pip install git+https://github.com/halcy/mastodon.py@7f23466
copy . ./
