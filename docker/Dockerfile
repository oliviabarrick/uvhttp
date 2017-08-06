FROM python:3.5

RUN apt-get update && apt-get install -y nginx
COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /uvhttp
ADD . /uvhttp

CMD /uvhttp/docker/run.sh
