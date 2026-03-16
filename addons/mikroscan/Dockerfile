ARG BUILD_FROM
FROM $BUILD_FROM

ENV PYTHONUNBUFFERED=1

COPY app/ /opt/mikroscan/
COPY run.sh /

RUN apk add --no-cache \
      python3 \
      py3-pip \
    && chmod a+x /run.sh \
    && pip3 install --no-cache-dir -r /opt/mikroscan/requirements.txt

WORKDIR /opt/mikroscan

CMD [ "/run.sh" ]
