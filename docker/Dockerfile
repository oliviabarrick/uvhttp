FROM python:3.5

RUN apt-get update && apt-get install -y nginx
COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /uvhttp
ADD . /uvhttp

CMD python setup.py install && \
    sed -i 's#ROOT#/uvhttp#g' ./docker/nginx.conf && \
    nginx -c /uvhttp/docker/nginx.conf && python3 docker/http_test_server.py && \
    nosetests -v -s && ./uvhttp.py
