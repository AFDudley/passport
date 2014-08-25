#!/usr/bin/env python3

import bisect
import datetime
import itertools
import operator

from sqlalchemy import create_engine
from sqlalchemy import Table, Column, MetaData, ForeignKey
from sqlalchemy import DateTime, Integer, String
from sqlalchemy import select
from sqlalchemy import and_, or_
from sqlalchemy.sql import func

from flask import Flask, request, Response
from flask.json import dumps, jsonify

engine = create_engine('sqlite:///test.db',
                       connect_args={'check_same_thread': False},
                       echo=True)
conn = engine.connect()

metadata = MetaData()
t_timeslots = Table('timeslots', metadata,
                    Column('id', Integer, primary_key=True),
                    Column('start', DateTime),
                    Column('end', DateTime))
t_boats = Table('boats', metadata,
                Column('id', Integer, primary_key=True),
                Column('capacity', Integer),
                Column('name', String))
t_assignments = Table('assignments', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('timeslot', Integer, ForeignKey('timeslots.id')),
                      Column('boat', Integer, ForeignKey('boats.id')))
t_bookings = Table('bookings', metadata,
                   Column('id', Integer, primary_key=True),
                   Column('size', Integer),
                   Column('timeslot', Integer, ForeignKey('timeslots.id')))
metadata.create_all(engine)

def getargs(req):
    data = req.get_data(as_text=True, parse_form_data=True)
    res = req.args.copy()
    res.update(req.form)
    j = req.get_json(silent=True)
    if j:
        res.update(j)
    return res

def query_timeslots(where):
    results = []
    slots = list(conn.execute(t_timeslots.select().where(where)))
    for slot in slots:
        where = t_assignments.c.timeslot == slot[t_timeslots.c.id]
        boats = list(conn.execute(t_assignments.join(t_boats)
                                  .select(use_labels=True).where(where)))
        names = [boat[t_boats.c.name] for boat in boats]
        # TODO: assign bookings to boats at creation time rather than query!
        # TODO: use a tree instead of re-sorting?
        sizes = sorted(boat[t_boats.c.capacity] for boat in boats)
        where = t_bookings.c.timeslot == slot[t_timeslots.c.id]
        bookings = list(conn.execute(t_bookings.select().where(where)))
        for booking in bookings:
            bsize = booking[t_bookings.c.size]
            for i, size in enumerate(sizes):
                if size >= bsize:
                    break
            else:
                return {'error': {'description': 'no room for booking',
                                  'id': booking[t_bookings.c.id],
                                  'size': booking[t_bookings.c.size],
                                  'timeslot_id': booking[t_bookings.c.timeslot],
                                  'available_sizes': sizes}}
            size = sizes[i] - bsize
            del sizes[i]
            if size:
                bisect.insort(sizes, size)
        dur = slot[t_timeslots.c.end] - slot[t_timeslots.c.start]
        dur = dur.total_seconds() * 60
        customer_count = sum(booking[t_bookings.c.size] for booking in bookings)
        availability = sizes[-1]
        results.append({
            'id': slot[t_timeslots.c.id],
            'start_time': slot[t_timeslots.c.start].timestamp(),
            'duration': dur,
            'availability': availability,
            'customer_count': customer_count,
            'boats': [row[t_boats.c.id] for row in boats]})
    return results
    
class JsonResponse(Response):
    default_mimetype = 'application/json'

app = Flask(__name__)
app.response_class = JsonResponse

@app.route("/")
def hello():
    return "Hello World!"

@app.route('/api/timeslot', methods=['GET', 'POST'])
def timeslot():
    args = getargs(request)
    start_time = int(args['start_time'])
    duration = int(args['duration'])
    start = datetime.datetime.fromtimestamp(start_time)
    end = start + datetime.timedelta(minutes=duration)
    result = conn.execute(t_timeslots.insert(), start=start, end=end)
    result = query_timeslots(t_timeslots.c.id==result.inserted_primary_key[0])
    return dumps(result[0])

@app.route('/api/timeslots', methods=['GET'])
def timeslots():
    args = getargs(request)
    date = args['date']
    start = datetime.datetime.strptime(args['date'], '%Y-%m-%d')
    end = start + datetime.timedelta(days=1)
    slots = query_timeslots(and_(t_timeslots.c.start >= start,
                                 t_timeslots.c.end < end))
    return dumps(slots)

# TODO: API spec says boats, not boat... typo?
@app.route('/api/boat', methods=['GET', 'POST'])
def boat():
    args = getargs(request)
    capacity = int(args['capacity'])
    name = args['name']
    result = conn.execute(t_boats.insert(), capacity=capacity, name=name)
    result = {'id': result.inserted_primary_key[0],
              'capacity': capacity,
              'name': name}
    return dumps(result)

@app.route('/api/boats', methods=['GET', 'POST'])
def boats():
    args = getargs(request)
    result = [{'id': row['id'], 'capacity': row['capacity'], 'name': row['name']}
              for row in conn.execute(t_boats.select())]
    return dumps(result)

# TODO: Spec says returns "none", why not the new assignment (with id)?
@app.route('/api/assignment', methods=['GET', 'POST'])
def assignment():
    args = getargs(request)
    timeslot = int(args['timeslot_id'])
    boat = int(args['boat_id'])
    result = conn.execute(t_assignments.insert(), timeslot=timeslot, boat=boat)
    return dumps({})

@app.route('/api/booking', methods=['GET', 'POST'])
def booking():
    args = getargs(request)
    timeslot = int(args['timeslot_id'])
    size = int(args['size'])
    result = conn.execute(t_bookings.insert(), timeslot=timeslot, size=size)
    result = {'id': result.inserted_primary_key[0],
              'timeslot_id': timeslot,
              'size': size}
    return dumps(result)
    
if __name__ == "__main__":
    app.run(debug=True)
