#!/usr/bin/env python3

import bisect
import collections
import datetime
import functools
import itertools
import operator
import threading

from flask import Flask, request, Response
from flask.json import dumps, jsonify

from keybisect import *

def daterange(start, end):
    start = start.date()
    end = end.date() + datetime.timedelta(days=1 if end.time() else 0)
    while start < end:
        yield start
        start += datetime.timedelta(days=1)

def max0(iterable):
    try:
        return max(iterable)
    except ValueError:
        return 0

@functools.total_ordering
class Timeslot:
    timeslots = {}
    timeslots_by_date = collections.defaultdict(set)
    def __init__(self, start, end):
        self.start, self.end = start, end
        self.boats = [] # (available, boat, booked)
        self.timeslots[id(self)] = self
        for date in daterange(start, end):
            self.timeslots_by_date[date].add(self)
    def __repr__(self):
        return 'Timeslot {}: {}-{}'.format(id(self), self.start, self.end)
    def __hash__(self):
        return hash((self.start, self.end))
    @classmethod
    def by_id(cls, id):
        return cls.timeslots[int(id)]
    @classmethod
    def by_date(cls, date):
        return cls.timeslots_by_date[date]
    def info(self):
        return {
            'id': id(self),
            'start_time': self.start.timestamp(),
            'duration': (self.end - self.start).total_seconds() * 60,
            'availability': max0(b[0] for b in self.boats),
            'customer_count': sum(b[2] for b in self.boats),
            'boats': [b[1].name for b in self.boats]
            }
    def __eq__(self, other):
        return id(self) == id(other)
    def __lt__(self, other):
        return (self.start < other.start or
                self.start == other.start and self.end < other.end)
    def overlaps(self, other, end=None):
        if end is None:
            return self.start < other.end and self.end > other.start
        else:
            return self.start < end and self.end > other
    def cmp(self, other):
        if self.end < other.start:
            return -1
        elif self.start > other.end:
            return 1
        else:
            return 0
    key = functools.cmp_to_key(cmp)
    def assign(self, boat):
        available = boat.capacity if boat.available(self) else 0
        bisect.insort(self.boats, (available, boat, 0))
        boat.assign(self, available)
    def book(self, size):
        i = bisect.bisect_left(self.boats, (size, None, 0))
        available, boat, booked = self.boats[i]
        boat.book(self, size)
        del self.boats[i]
        booking = (available - size, boat, booked + size)
        bisect.insort(self.boats, booking)
        return booking
    def mark_busy(self, boat, available):
        for i in range(bisect.bisect_left(self.boats, (available, boat, 0)),
                       bisect.bisect_right(self.boats, (available, boat, 0))):
            if self.boats[i][1] == boat:
                break
        else:
            raise ValueError('{}: never heard of boat {}'.format(self, boat.name))
        del self.boats[i]
        booking = (0, boat, 0)
        bisect.insort(self.boats, booking)

@functools.total_ordering
class Boat:
    boats = {}
    def __init__(self, capacity, name):
        self.capacity, self.name = capacity, name
        self.assignments = [] # [timeslot, available, booked]
        self.boats[id(self)] = self
    def __repr__(self):
        return 'Boat {}: {}'.format(id(self), self.name)
    @staticmethod
    def assignment_key(assignment):
        return Timeslot.key(assignment[0])
    @classmethod
    def by_id(cls, id):
        return cls.boats[int(id)]
    @classmethod
    def by_all(cls):
        return cls.boats.values()
    def __eq__(self, other):
        return id(self) == id(other)
    def __lt__(self, other):
        return id(self) < id(other)
    def info(self):
        return {
            'id': id(self),
            'capacity': self.capacity,
            'name': self.name
            }
    def assign(self, timeslot, available):
        entry = [timeslot, available, 0]
        key_insort(Boat.assignment_key, self.assignments, entry)
    def available(self, timeslot):
        entry = [timeslot, 0, 0]
        for i in range(key_bisect_left(Boat.assignment_key, self.assignments, entry),
                       key_bisect_right(Boat.assignment_key, self.assignments, entry)):
            if self.assignments[i][2]:
                return False
        return True
    def book(self, timeslot, size):
        entry = [timeslot, 0, 0]
        low = key_bisect_left(Boat.assignment_key, self.assignments, entry)
        high = key_bisect_right(Boat.assignment_key, self.assignments, entry)
        app.logger.debug('Boat.book: {}-{}'.format(low, high))
        for i in range(low, high):
            assignment = self.assignments[i]
            app.logger.warning('checking assignment #{} ({})'.format(i, self.assignments[i]))
            if assignment[0] == timeslot:
                assignment[2] += size
                assignment[1] -= size
            else:
                assignment[0].mark_busy(self, assignment[1])
                assignment[1] = 0

def getargs(req):
    data = req.get_data(as_text=True, parse_form_data=True)
    res = req.args.copy()
    res.update(req.form)
    j = req.get_json(silent=True)
    if j:
        res.update(j)
    return res

class JsonResponse(Response):
    default_mimetype = 'application/json'

app = Flask(__name__)
app.response_class = JsonResponse

@app.route('/api/timeslot', methods=['GET', 'POST'])
def timeslot():
    args = getargs(request)
    start_time = int(args['start_time'])
    duration = int(args['duration'])
    start = datetime.datetime.fromtimestamp(start_time)
    end = start + datetime.timedelta(minutes=duration)
    ts = Timeslot(start, end)
    return dumps(ts.info())

@app.route('/api/timeslots', methods=['GET', 'POST'])
def timeslots():
    args = getargs(request)
    if request.method=='POST' and 'start_time' in args:
        return timeslot()
    date = datetime.datetime.strptime(args['date'], '%Y-%m-%d').date()
    return dumps([ts.info() for ts in Timeslot.by_date(date)])

# TODO: API spec says boats, not boat... typo?
@app.route('/api/boat', methods=['GET', 'POST'])
def boat():
    args = getargs(request)
    capacity = int(args['capacity'])
    name = args['name']
    boat = Boat(capacity, name)
    return dumps(boat.info())

@app.route('/api/boats', methods=['GET', 'POST'])
def boats():
    args = getargs(request)
    if request.method == 'POST' and args:
        return boat()
    return dumps([boat.info() for boat in Boat.by_all()])

@app.route('/api/assignment', methods=['GET', 'POST'])
def assignment():
    args = getargs(request)
    timeslot = Timeslot.by_id(args['timeslot_id'])
    boat = Boat.by_id(args['boat_id'])
    timeslot.assign(boat)
    return dumps({})

@app.route('/api/booking', methods=['GET', 'POST'])
def booking():
    args = getargs(request)
    timeslot = Timeslot.by_id(args['timeslot_id'])
    size = int(args['size'])
    try:
        booking = timeslot.book(size)
        return dumps({'id': id(booking),
                      'timeslot_id': id(timeslot),
                      'size': size})
    except IndexError:
        return dumps({'error': {
            'description': 'no room',
            'timeslot_id': id(timeslot),
            'size': size}})
    
if __name__ == "__main__":
    app.run(debug=True, port=3000)
