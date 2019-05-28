FROM alpine:3.9

RUN apk add --no-cache python3 py3-lxml py3-flask py3-requests py3-simplejson uwsgi-python3 patch
RUN pip3 install --upgrade pip setuptools
RUN pip3 install geographiclib pykml
RUN mkdir /app
ARG REV=pass_me_to_force_redownload
RUN cd /usr/lib/python3.6/site-packages/pykml && wget -O - https://raw.githubusercontent.com/bazuchan/pythonvlm/master/pykml-py3.patch | patch -p1
RUN wget -O /app/vlm.py https://raw.githubusercontent.com/bazuchan/pythonvlm/master/vlm.py
RUN wget -O /app/webvlm.py https://raw.githubusercontent.com/bazuchan/pythonvlm/master/webvlm.py

EXPOSE 3031
WORKDIR /app
CMD [ "uwsgi", "--socket", "0.0.0.0:3031", "--uid", "nobody", "--plugins", "python3", "--protocol", "http", "--processes", "4", "--wsgi", "webvlm:app" ]

