FROM alpine:3.11

RUN apk add --no-cache python3 py3-lxml py3-flask py3-requests py3-simplejson uwsgi-python
RUN pip3 install --upgrade pip setuptools
RUN pip3 install geographiclib pykml
RUN mkdir /app
COPY vlm.py webvlm.py /app/

EXPOSE 3031
WORKDIR /app
CMD [ "uwsgi", "--socket", "0.0.0.0:3031", "--uid", "nobody", "--plugins", "python", "--protocol", "http", "--processes", "4", "--wsgi", "webvlm:app" ]

