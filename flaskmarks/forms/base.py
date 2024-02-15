# flaskmarks/forms/base

from flask_wtf import FlaskForm as Form

strip_filter = lambda x: x.strip() if x else None
