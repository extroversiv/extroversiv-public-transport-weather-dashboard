FROM python:3.11 AS builder
RUN pip3 install pipenv
# Tell pipenv to create venv in the current directory
ENV PIPENV_VENV_IN_PROJECT=1
# copy Pipfile
ADD Pipfile.lock Pipfile /usr/src/
WORKDIR /usr/src
RUN pipenv install --deploy --ignore-pipfile

FROM python:3.11-slim AS runtime
RUN mkdir -v /usr/src/.venv
COPY --from=builder /usr/src/.venv/ /usr/src/.venv/
ADD . /usr/src/
WORKDIR /usr/src/
RUN adduser appuser
USER appuser
CMD ["./.venv/bin/python", "-m", "dashboard"]

# docker build -t dashboard .
# docker run -p 8050:8050 --restart="unless-stopped" -e TZ="Europe/Berlin" dashboard
