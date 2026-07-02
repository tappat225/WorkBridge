# SPDX-License-Identifier: Apache-2.0
# CapOwn managed execution container.
#
# This container is used by the DockerExecutionBackend for task execution.
# It does NOT run the Worker daemon - the Worker control process runs on
# the host and uses `docker exec` to run tasks inside this container.

ARG PYTHON_IMAGE=python:3.12-slim
ARG APT_MIRROR=deb.debian.org

FROM ${PYTHON_IMAGE}

# Re-declare ARGs after FROM so they are available in RUN instructions
ARG APT_MIRROR

# Switch apt source to mirror if APT_MIRROR is set
RUN sed -i "s|http://deb.debian.org|http://${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends procps curl \
    && rm -rf /var/lib/apt/lists/*

# The workspace mount point — the deploy script mounts the host workspace here.
RUN mkdir -p /workspace

# Keep the container alive so ``docker exec`` works
CMD ["tail", "-f", "/dev/null"]
