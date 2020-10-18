# flaskmarks/core/setup.py

from flask_sqlalchemy import SQLAlchemy
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_bootstrap import Bootstrap
from flask_debugtoolbar import DebugToolbarExtension
from .. import app

app.config.from_object('config')
config = app.config

"""
Debug mode
"""
app.debug = config['DEBUG_MODE']

"""
Toolbar
"""
toolbar = DebugToolbarExtension(app)

"""
Login manager
"""
lm = LoginManager()
lm.init_app(app)

"""
Database ORM
"""
db = SQLAlchemy(app)

"""
DB migration
"""
migrate = Migrate(app, db)

"""
Manager
"""
manager = Manager(app)
manager.add_command('db', MigrateCommand)

"""
Bcrypt
"""
bcrypt = Bcrypt(app)

"""
Bootstrap
"""
Bootstrap(app)
