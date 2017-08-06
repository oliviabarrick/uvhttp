#!/bin/bash
cd /uvhttp

nginx -c /uvhttp/docker/nginx.conf
python3 ./docker/http_test_server.py

python setup.py install
nosetests -v -s 
./uvhttp.py
