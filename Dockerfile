FROM python:3.11 AS build

ENV PIPENV_VENV_IN_PROJECT=1
ARG PYPI_PASSWORD

RUN export PYPI_PASSWORD=${PYPI_PASSWORD}

# Install dependencies
RUN pip install -U pip
RUN pip install pipenv

COPY ./Pipfile.lock /app/Pipfile.lock
WORKDIR /app
RUN pipenv sync

FROM python:3.11 AS runtime

EXPOSE 3000
RUN adduser --uid 1500 flatlander
RUN mkdir -p /app/.venv
COPY --from=build --chown=flatlander /app/.venv/ /app/.venv/

COPY --chown=flatlander . /app/
WORKDIR /app

RUN chown flatlander /app
RUN chown flatlander /app/.venv

ENTRYPOINT ["/app/bin/docker_entrypoint"]
CMD ["server"]