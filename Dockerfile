ARG IMAGE_REGISTRY=docker.io
FROM ${IMAGE_REGISTRY}/library/python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc make libc6-dev curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -fsSL --retry 3 https://www.sqlite.org/2026/sqlite-autoconf-3510300.tar.gz -o sqlite.tar.gz \
 && echo '81f5be397049b0cae1b167f2225af7646fc0f82e4a9b3c48c9ea3a533e21d77a  sqlite.tar.gz' | sha256sum -c - \
 && tar -xzf sqlite.tar.gz \
 && cd sqlite-autoconf-3510300 && ./configure --prefix=/opt/sqlite && make -j2 && make install
RUN curl -fsSL --retry 3 https://github.com/FiloSottile/age/releases/download/v1.2.1/age-v1.2.1-linux-amd64.tar.gz -o age.tar.gz \
 && echo '7df45a6cc87d4da11cc03a539a7470c15b1041ab2b396af088fe9990f7c79d50  age.tar.gz' | sha256sum -c - \
 && tar -xzf age.tar.gz

FROM ${IMAGE_REGISTRY}/library/python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/srv/app/app \
    LD_LIBRARY_PATH=/opt/sqlite/lib TZ=Asia/Shanghai
COPY --from=build /opt/sqlite /opt/sqlite
COPY --from=build /build/age/age /build/age/age-keygen /usr/local/bin/
RUN python -c 'import sqlite3; assert sqlite3.sqlite_version_info >= (3,51,3)'
WORKDIR /srv/app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY app ./app
COPY tests ./tests
COPY pyproject.toml ./
RUN ln -s app/manage.py manage.py \
 && python manage.py collectstatic --noinput --settings=config.settings_test \
 && groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home app
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "/dev/null", "--error-logfile", "/dev/null"]
