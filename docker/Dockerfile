FROM alpine:3.9

RUN apk add --no-cache python3 py3-lxml py3-flask py3-requests py3-simplejson uwsgi-python3 patch
RUN pip3 install --upgrade pip setuptools
RUN pip3 install geographiclib pykml
RUN mkdir /app
COPY vlm.py webvlm.py /app/
COPY pykml-py3.patch /tmp/
RUN cd /usr/lib/python3.6/site-packages/pykml && patch -p1 < /tmp/pykml-py3.patch

EXPOSE 3031
WORKDIR /app
CMD [ "uwsgi", "--socket", "0.0.0.0:3031", "--uid", "nobody", "--plugins", "python3", "--protocol", "http", "--processes", "4", "--wsgi", "webvlm:app" ]

