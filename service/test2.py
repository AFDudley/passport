#!/usr/bin/env python3

import requests

base = 'http://localhost:5000/api/'

def post(method, **data):
    return requests.post(base+method, data=data).json()

r = post('timeslot', start_time=1406052000, duration=120)
ts1 = r['id']
r = post('timeslot', start_time=1406055600, duration=120)
ts2 = r['id']
r = post('boat', capacity=8, name='Amazon Express')
boat1 = r['id']
r = post('boats')
print(r)
r = post('assignment', timeslot_id=ts1, boat_id=boat1)
r = post('assignment', timeslot_id=ts2, boat_id=boat1)
r = post('timeslots', date='2014-07-22')
print(r)
assert r[0]['availability'] == 8 and r[0]['customer_count'] == 0
assert r[1]['availability'] == 8 and r[1]['customer_count'] == 0
r = post('booking', timeslot_id=ts2, size=2)
r = post('timeslots', date='2014-07-22')
print(r)
assert r[0]['availability'] == 0 and r[0]['customer_count'] == 0
assert r[1]['availability'] == 6 and r[1]['customer_count'] == 2

