

#use ujson
import ujson

def json_response(data, **kwargs):
    kwargs.setdefault('content_type','application/json')
    return web.Response(ujson.dumps(data), **kwargs)
