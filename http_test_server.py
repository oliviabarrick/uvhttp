from sanic import Sanic
from sanic.response import json, text
from json import loads
import os

app = Sanic()

@app.route("/proxy/echo", [ 'GET', 'POST' ])
async def echo(request):
    try:
        parsed_json = loads(request.body)
    except (ValueError, TypeError):
        parsed_json = None

    return json({
        "form": request.form,
        "body": request.body,
        "args": request.args,
        "url": request.url,
        "query": request.query_string,
        "json": parsed_json,
        "headers": request.headers
    })

if __name__ == '__main__':
    if os.fork(): quit()
    if os.fork(): quit()

    app.run(host="127.0.0.1", port=8888)
