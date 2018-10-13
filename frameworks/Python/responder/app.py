import asyncio
import asyncpg
import os
import responder
from random import randint
from operator import itemgetter
from urllib.parse import parse_qs


READ_ROW_SQL = 'SELECT "randomnumber" FROM "world" WHERE id = $1'
WRITE_ROW_SQL = 'UPDATE "world" SET "randomnumber"=$1 WHERE id=$2'
ADDITIONAL_ROW = [0, 'Additional fortune added at request time.']


async def setup_database():
    global connection_pool
    connection_pool = await asyncpg.create_pool(
        user=os.getenv('PGUSER', 'felix'),
        password=os.getenv('PGPASS', 'password'),
        database='hello_world',
        host='127.0.0.1',
        port=5432
    )


def load_fortunes_template():
    path = os.path.join('templates', 'fortune.html')
    return path


def get_num_queries(request):
    try:
        query_string = request['query_string']
        query_count = int(parse_qs(query_string)[b'queries'][0])
    except (KeyError, IndexError, ValueError):
        return 1

    if query_count < 1:
        return 1
    if query_count > 500:
        return 500
    return query_count


connection_pool = None
sort_fortunes_key = itemgetter(1)
template = load_fortunes_template()
loop = asyncio.get_event_loop()
loop.run_until_complete(setup_database())


api = responder.API()


@api.route('/json')
def json_serialization(req, resp):
    resp.media = {'message': 'Hello, world!'}


@api.route('/db')
async def single_database_query(req, resp):
    row_id = randint(1, 10000)

    async with connection_pool.acquire() as connection:
        number = await connection.fetchval(READ_ROW_SQL, row_id)

    resp.media = {'id': row_id, 'randomNumber': number}


@api.route('/queries')
async def multiple_database_queries(req, resp):
    num_queries = get_num_queries(req)
    row_ids = [randint(1, 10000) for _ in range(num_queries)]
    worlds = []

    async with connection_pool.acquire() as connection:
        statement = await connection.prepare(READ_ROW_SQL)
        for row_id in row_ids:
            number = await statement.fetchval(row_id)
            worlds.append({'id': row_id, 'randomNumber': number})

    resp.media = worlds


@api.route('/fortunes')
async def fortunes(req, resp):
    async with connection_pool.acquire() as connection:
        fortunes = await connection.fetch('SELECT * FROM Fortune')

    fortunes.append(ADDITIONAL_ROW)
    fortunes.sort(key=sort_fortunes_key)
    resp.content = api.template(template, fortunes=fortunes)


@api.route('/updates')
async def database_updates(req, resp):
    num_queries = get_num_queries(req)
    updates = [(randint(1, 10000), randint(1, 10000)) for _ in range(num_queries)]
    worlds = [{'id': row_id, 'randomNumber': number} for row_id, number in updates]

    async with connection_pool.acquire() as connection:
        statement = await connection.prepare(READ_ROW_SQL)
        for row_id, number in updates:
            await statement.fetchval(row_id)
        await connection.executemany(WRITE_ROW_SQL, updates)

    resp.media = worlds


@api.route('/plaintext')
def plaintext(req, resp):
    resp.text = "Hello, world!"


if __name__ == '__main__':
    api.run()