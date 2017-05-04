FROM python:3.5

RUN apt-get update && apt-get install -y nginx
COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /uvhttp
ADD . /uvhttp

CMD python setup.py install && \
    sed -i 's#ROOT#/uvhttp#g' ./nginx.conf && \
    nginx -c /uvhttp/nginx.conf && \
    nosetests -v -s && ./uvhttp.py
