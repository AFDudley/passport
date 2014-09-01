Requirements
---

 * Install Python 3.4.
 * `pip3 install flask flask-cors`

To run
---

 * cd service
 * ./service.py
 
This will start the service on port 3000. You can then `npm start` from the parent directory to run the driver web site.

Note that in this version, the data are not persistent--every time you restart the service, you start over from scratch.

Implementation
---

To avoid linear searches, I've hacked up the following indices:

 * `Timeslot.timeslots`: a class dict (hash) mapping from id to Timeslot.
 * `Timeslot.timeslots_by_date`: a class multidict mapping from dates to Timeslots.
 * `Timeslot.boats`: a per-instance sorted list, so we can bisect to the smallest boat for a given size. This might be better with a tree instead of a sorted list; currently, assigning finds an appropriate boat in logarithmic time, but then does linear work on the timeslot and all other overlapping timeslots, which could be bad if there were a lot of boats. (I suspect there won't be, but I'd like to see how bad it is.)
 * `Boat.boats`: a class dict mapping from id to Boat.
 * `Boat.assignments`: a per-instance sorted list, so we can bisect to find all of the timeslots that intersect a given timeslot (this code is a mess; it should work, but it would be a lot more readable to write a sorted-interval-collection library...).

