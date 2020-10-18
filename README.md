Flaskmarks
===============
Simple (and self educational) [Flask](http://flask.pocoo.org/) & [SQLAlchemy](http://www.sqlalchemy.org/) based bookmark and RSS feed app.

Features
========
"Flaskmarks" is a bookmark managing application. Its purpose is to be a all-in-one bookmark and RSS feed repository. Storing all bookmarks and RSS feeds in one place and make them accessible from all platforms and devices. This is by no means an original idea, but this is an interpretation of the problem.

I have added couple of features I have missed in every bookmarking app: Full Text search of bookmarked links and local copy parsed with python-readability.
This can be used as "Read latter" app.

- Bookmarking
- Full text search
- Readability



Setting up virual envirement
============================

* `$ sudo pip install virtualenv`
* `$ virtualenv venv`
* `$ . venv/bin/activate`

Install
=======
* Create and activate a python virtualenv.
* make a copy of config.py.example to config.py and edit accordingly.
* run: `pip install -r requirements.txt`.
* run: `python run.py db init`
* run: `python run.py db migrate`
* run: `python run.py db upgrade`
* run: `python run.py runserver`


Exit virtualenv
==============

$ deactivate

Ubuntu
======
Installing this app on a Ubuntu server may take a little more effort than `pip install -r requirements.txt`. On some systems the following packages need to be installed:
* run: `sudo apt-get install python-virtualenv python2.7-dev build-essential`

Upgrade
=======
* run: `python run.py db migrate`
* run: `python run.py db upgrade`

Package updates
===============
* run: `pip install --upgrade -r requirements.txt`

Simple deployment with nginx
============================
* edit and install examples/flaskmarks.nginx.example
* run: `python run.py runserver -p 5001`

Branches
========
There will at any given point be at least two branches in this repository. One
master (stable) branch, and one develop branch. The develop branch might contain
unfinished code and/or wonky solutions. I will strive to make sure that code 
merged into master is as stable as possible (given the small size of this application).

Useful Links
============
* [Flask Principal](http://pythonhosted.org/Flask-Principal/)
* [Flask SQLAlchemy](http://pythonhosted.org/Flask-SQLAlchemy/)
* [Jinja](http://jinja.pocoo.org/)
* [Filters](http://jinja.pocoo.org/docs/templates/#builtin-filters)
* [Flask and https](http://flask.pocoo.org/mailinglist/archive/2011/11/17/change-request-s-http-referer-header/#fc7dc5b7a1682ccbb4947a8013987761)
* [Flask Migrate](http://flask-migrate.readthedocs.org/en/latest/)
* [Nice Flask Tutorial](http://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world)
* [Flask online book](http://exploreflask.com/index.html)
* [Flask Blueprints](http://flask.pocoo.org/docs/blueprints/)
* [Flask-WhooshAlchemy](https://github.com/gyllstromk/Flask-WhooshAlchemy)
* [python-readability](https://github.com/buriy/python-readability)


TODO
====

* Changed flask_whooshalchemy with flask_msearch
* Adding bookmark and search is working.
* why is it not genereting tags and description?



