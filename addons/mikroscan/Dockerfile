ARG BUILD_FROM
FROM $BUILD_FROM

ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY app/ /opt/mikroscan/
COPY run.sh /

RUN apk add --no-cache \
      bash \
      ca-certificates \
      libffi \
      openssl \
      python3 \
      py3-pip \
    && apk add --no-cache --virtual .build-deps \
      build-base \
      cargo \
      libffi-dev \
      openssl-dev \
      python3-dev \
      rust \
    && python3 -m venv "${VIRTUAL_ENV}" \
    && chmod a+x /run.sh \
    && "${VIRTUAL_ENV}/bin/pip" install --no-cache-dir --upgrade pip setuptools wheel \
    && "${VIRTUAL_ENV}/bin/pip" install --no-cache-dir -r /opt/mikroscan/requirements.txt \
    && apk del .build-deps

WORKDIR /opt/mikroscan

CMD [ "/run.sh" ]
