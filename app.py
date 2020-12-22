import os
import re
import psycopg2
import psycopg2.extras
import flask
import string
import random
from collections import namedtuple
from dotenv import load_dotenv

load_dotenv()

url_regex = re.compile(r'((http|https)://)?[a-zA-Z0-9./?:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9.&/?:@\-_=#])*',
                       re.IGNORECASE)
app: flask.Flask = flask.Flask(__name__)

database = psycopg2.connect(dbname=os.getenv("DB_NAME"),
                            user=os.getenv("DB_USER"),
                            host=os.getenv("DB_HOST"),
                            port=os.getenv("DB_PORT"),
                            password=os.getenv("DB_PASSWORD"))

Response = namedtuple('Response', ['json', 'code'])
server_error_response = Response(
    {"success": False, "message": "Internal Server Error - something went wrong while computing this request"}, 500)
not_found_response = Response({"success": False, "message": "Not Found - this slug does not exist"}, 404)


def create(body: dict, slug: str) -> Response:
    with database.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:
        if 'link' not in body or type(body['link']) is not str:
            return Response({"success": False,
                             "message": "Bad Request - please specify a string link redirect in the request body"}, 400)
        if len(body['link']) > 100:
            return Response({"success": False,
                             "message": "Bad Request - link cannot be longer than 100 characters."}, 400)
        cur.execute('SELECT link FROM links WHERE slug = %s', (slug,))
        res = cur.fetchone()
        if res:
            return Response({"success": False, "message": "Bad Request - this slug already exists"}, 400)
        cur.execute('INSERT INTO links (link, slug) VALUES (%s, %s)', (str(body['link']).lower(), str(slug)))
        return Response({"success": True, "payload": {"link": body['link'], "slug": slug}}, 201)


def get(slug: str) -> Response:
    with database.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:
        cur.execute('SELECT link FROM links WHERE slug = %s', (slug,))
        res = cur.fetchone()
        if hasattr(res, 'link'):
            return Response({"success": True, "payload": {"link": res.link}}, 200)
        return not_found_response


def delete(slug: str) -> Response:
    with database.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:
        cur.execute('SELECT link FROM links WHERE slug = %s', (slug,))
        res = cur.fetchone()
        if res:
            cur.execute('DELETE FROM links WHERE slug = %s', (slug,))
            return Response({"success": True, "message": "Success - short link deleted successfully"}, 204)
        return not_found_response


def put(slug: str) -> Response:
    with database.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:
        if 'link' not in flask.request.json or type(flask.request.json['link']) is not str:
            return Response(
                {"success": False,
                 "message": "Bad Request - body has to include a 'link' field of type 'string'."}, 400)
        link: str = flask.request.json['link']
        if len(link) > 100:
            return Response({"success": False,
                             "message": "Bad Request - link cannot be longer than 100 characters"}, 400)
        cur.execute('SELECT link FROM links WHERE slug = %s', (slug,))
        res = cur.fetchone()
        if res:
            cur.execute('UPDATE links SET link = %s WHERE slug = %s', (str(link).lower(), slug))
            return Response({"success": True, "message": "Success - link updated successfully."}, 204)
        return not_found_response


def generate_slug(length: int = 5) -> str:
    return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(length))


@app.route('/api/<slug>', methods=['GET', 'POST', 'DELETE', 'PUT'])
def redirect(slug):
    response = server_error_response
    if flask.request.method == 'GET':
        response = get(slug)
    elif flask.request.method == 'POST':
        response = create(dict(flask.request.json), slug)
    elif flask.request.method == 'DELETE':
        response = delete(slug)
    elif flask.request.method == 'PUT':
        response = put(slug)
    return flask.jsonify(response.json), response.code


@app.route('/<slug>', methods=['GET'])
def home(slug):
    response: Response = get(slug)
    if response[1] == 200:
        return flask.redirect(response.json['payload']['link'])
    return 'This doesn\'t exist.'


if __name__ == '__main__':
    app.run(port=int(os.getenv('PORT')))
