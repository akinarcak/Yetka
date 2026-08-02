ARG PYTHON_BASE_IMAGE=python:3.14-slim-trixie@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6

FROM ${PYTHON_BASE_IMAGE} AS stage-build

ARG VERSION
ARG UV_VERSION=0.11.32
ARG PIP_MIRROR=https://pypi.org/simple
ARG APT_MIRROR=http://deb.debian.org

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PATH=/opt/py3/bin:$PATH \
    UV_PROJECT_ENVIRONMENT=/opt/py3 \
    UV_FROZEN=1 \
    ANSIBLE_COLLECTIONS_PATHS=/opt/py3/lib/python3.14/site-packages/ansible_collections

WORKDIR /opt/jumpserver

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=yetka-core-build \
    --mount=type=cache,target=/var/lib/apt,sharing=locked,id=yetka-core-build \
    set -eux \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache \
    && sed -i "s@http://.*.debian.org@${APT_MIRROR}@g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update > /dev/null \
    && apt-get -y install --no-install-recommends \
       ca-certificates wget g++ make pkg-config default-libmysqlclient-dev \
       freetds-dev gettext locales libkrb5-dev libldap2-dev libsasl2-dev \
    && sed -i 's/^# *\(en_US.UTF-8 UTF-8\)/\1/' /etc/locale.gen \
    && locale-gen

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache \
    python -m pip install --no-cache-dir "uv==${UV_VERSION}" --index-url "${PIP_MIRROR}" \
    && uv sync --frozen --no-dev --no-group xpack --no-install-project

COPY . .

RUN set -eux \
    && echo > config.yml \
    && if [ -n "${VERSION:-}" ]; then \
         sed -i "s@VERSION = .*@VERSION = '${VERSION}'@g" apps/jumpserver/const.py; \
       fi \
    && ansible-galaxy collection install -r requirements/collections.yml --force \
    && bash requirements/static_files.sh \
    && bash requirements/clean_site_packages.sh \
    && export SECRET_KEY="$(head -c100 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c48)" \
    && export BOOTSTRAP_TOKEN="$(head -c100 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c48)" \
    && cd apps \
    && python manage.py compilemessages


FROM ${PYTHON_BASE_IMAGE} AS runtime

ARG TARGETARCH
ARG APT_MIRROR=http://deb.debian.org
ARG HEALTHCHECK_VERSION=1.0.13
ARG HEALTHCHECK_SHA256_AMD64=b4d11182d067f44335d720cf6812497b7868a77f86d20a30dd0c253c05e15c46
ARG HEALTHCHECK_SHA256_ARM64=4228f8c50146cc8aceb299fe4c9e848ca69c2df29624dfe53e5ded8189c09295

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PATH=/opt/py3/bin:$PATH \
    HOME=/home/yetka

RUN set -eux \
    && sed -i "s@http://.*.debian.org@${APT_MIRROR}@g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update > /dev/null \
    && apt-get -y install --no-install-recommends \
       ca-certificates default-libmysqlclient-dev libmariadb3 postgresql-client \
       freetds-dev libldap2-dev libx11-dev openssh-client sshpass bubblewrap docker-cli wget \
    && case "$TARGETARCH" in \
         amd64) healthcheck_sha256="$HEALTHCHECK_SHA256_AMD64" ;; \
         arm64) healthcheck_sha256="$HEALTHCHECK_SHA256_ARM64" ;; \
         *) echo "Unsupported healthcheck architecture: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && wget "https://github.com/jumpserver-dev/healthcheck/releases/download/v${HEALTHCHECK_VERSION}/check_linux_${TARGETARCH}.deb" \
    && echo "$healthcheck_sha256  check_linux_${TARGETARCH}.deb" | sha256sum -c - \
    && dpkg -i "check_linux_${TARGETARCH}.deb" \
    && rm -f "check_linux_${TARGETARCH}.deb" \
    && groupadd --gid 10001 yetka \
    && useradd --uid 10001 --gid yetka --create-home --home-dir /home/yetka --shell /usr/sbin/nologin yetka \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=stage-build /opt/py3 /opt/py3
COPY --from=stage-build --chown=yetka:yetka /opt/jumpserver /opt/jumpserver

RUN set -eux \
    && install -d -o yetka -g yetka -m 0750 /opt/jumpserver/data /tmp/yetka \
    && rm -rf /opt/jumpserver/tmp \
    && ln -s /tmp/yetka /opt/jumpserver/tmp

WORKDIR /opt/jumpserver

VOLUME ["/opt/jumpserver/data"]

USER 10001:10001

ENTRYPOINT ["./entrypoint.sh"]

EXPOSE 8080

STOPSIGNAL SIGQUIT

CMD ["start", "all"]
